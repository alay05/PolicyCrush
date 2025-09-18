# features/calendar_pull.py
"""
Pull events from AddEvent within a date range, extract the original link
(from the event description), and generate per-event ICS content.

ENV required:
    ADDEVENT_API_KEY        -> Your AddEvent API key (Bearer)

Optional:
    ADDEVENT_CALENDAR_KEY   -> e.g. "GT179952" (AddEvent unique_key)
    LOCAL_TZ                -> IANA tz name, default "America/New_York"

Notes:
- Uses AddEvent v2 endpoints under https://api.addevent.com/calevent/v2
- Correct query params for date filtering are: datetime_min / datetime_max
- sort_by should be 'datetime_start' (asc/desc)
"""

from __future__ import annotations

import os
import re
import typing as t
from datetime import datetime, date, timedelta, timezone, time as dtime

import requests

try:
    from zoneinfo import ZoneInfo  # py3.9+
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

API_BASE = "https://api.addevent.com/calevent/v2"
DEFAULT_CALENDAR_KEY = os.getenv("ADDEVENT_CALENDAR_KEY", "GT179952")
DEBUG = os.getenv("PC_DEBUG", "").lower() in {"1", "true", "yes"}


# ---- Timezone helpers --------------------------------------------------------

def _get_local_tz():
    name = os.getenv("LOCAL_TZ", "America/New_York")
    if ZoneInfo is not None:
        try:
            return ZoneInfo(name)
        except Exception:
            pass
    try:
        return datetime.now().astimezone().tzinfo or timezone.utc
    except Exception:
        return timezone.utc

LOCAL_TZ = _get_local_tz()

def _ensure_aware_local(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=LOCAL_TZ)
    return dt


# ---- HTTP session ------------------------------------------------------------

def _api_session() -> requests.Session:
    api_key = os.getenv("ADDEVENT_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Missing ADDEVENT_API_KEY in environment.")
    s = requests.Session()
    s.headers.update({
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "PolicyCrush/addevent-pull"
    })
    return s


# ---- Parse / format ----------------------------------------------------------

def _parse_iso(s: str | None) -> datetime | None:
    """Parse common AddEvent datetime strings. If tz-naive, assume LOCAL_TZ."""
    if not s:
        return None
    try:
        # Handle 'Z' -> +00:00 and also plain 'YYYY-MM-DD hh:mm[:ss]'
        s2 = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s2)
    except Exception:
        try:
            base = s.split(".")[0]
            if base.endswith("Z"):
                base = base[:-1] + "+00:00"
            dt = datetime.fromisoformat(base)
        except Exception:
            # Last resort: try date-only
            try:
                dt = datetime.strptime(s, "%Y-%m-%d")
            except Exception:
                return None
    return _ensure_aware_local(dt)

def _api_date_bounds_str(start: date, end: date) -> tuple[str, str]:
    """
    Build naive local strings for AddEvent search:
    - docs say comparisons ignore TZ; pass local wall time.
    """
    start_local = datetime.combine(start, dtime(0, 0, 0)).replace(tzinfo=LOCAL_TZ)
    end_local   = datetime.combine(end,   dtime(23, 59, 59)).replace(tzinfo=LOCAL_TZ)
    # Return as naive 'YYYY-MM-DD HH:MM:SS'
    return (start_local.strftime("%Y-%m-%d %H:%M:%S"),
            end_local.strftime("%Y-%m-%d %H:%M:%S"))

def _utc_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    """Inclusive bounds in UTC for our own local filtering/safety."""
    start_local = datetime.combine(start, dtime(0,0,0)).replace(tzinfo=LOCAL_TZ)
    end_local   = datetime.combine(end,   dtime(23,59,59)).replace(tzinfo=LOCAL_TZ)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


_URL_RE = re.compile(r"https?://[^\s)>\]]+", re.IGNORECASE)
def _extract_first_url(text: str | None) -> str | None:
    if not text:
        return None
    m = _URL_RE.search(text)
    return m.group(0) if m else None


# ---- Calendar lookups --------------------------------------------------------

def resolve_calendar_id(session: requests.Session, calendar_key: str) -> str | None:
    """
    Resolve numeric calendar_id from unique_key (e.g., 'GT179952').
    Falls back gracefully if not found.
    """
    # Try direct (some setups allow /calendars/{unique_key})
    try:
        resp = session.get(f"{API_BASE}/calendars/{calendar_key}", timeout=20)
        if resp.ok:
            data = resp.json() or {}
            cal = data.get("calendar") if isinstance(data.get("calendar"), dict) else data
            if isinstance(cal, dict) and "id" in cal:
                return str(cal["id"])
            if "id" in data:
                return str(data["id"])
    except Exception:
        pass

    # Try search
    try:
        resp = session.get(f"{API_BASE}/calendars", params={"q": calendar_key, "page_size": 20}, timeout=20)
        if resp.ok:
            data = resp.json() or {}
            items = data.get("calendars") or data.get("calendar") or []
            if isinstance(items, list) and items:
                for c in items:
                    if str(c.get("unique_key") or "").strip() == calendar_key:
                        return str(c.get("id"))
                return str(items[0].get("id"))
    except Exception:
        pass

    return None


# ---- Data model --------------------------------------------------------------

class PulledEvent(t.TypedDict, total=False):
    id: str
    title: str
    description: str
    starts_at: str
    ends_at: str
    starts_at_dt: datetime
    ends_at_dt: datetime | None
    original_link: str | None
    calendar_id: str | None
    addevent_url: str | None


def _shape_event(raw: dict) -> PulledEvent:
    ev: PulledEvent = {}

    ev["id"] = str(
        raw.get("id") or raw.get("event_id") or raw.get("_id") or raw.get("uid") or ""
    )
    ev["title"] = (
        raw.get("title") or raw.get("name") or raw.get("summary") or "(Untitled Event)"
    )
    desc = raw.get("description") or raw.get("body") or raw.get("details") or ""
    ev["description"] = desc

    starts = (
        raw.get("datetime_start")
        or raw.get("starts_at")
        or raw.get("start_at")
        or raw.get("start_time")
        or raw.get("start")
        or raw.get("when_start")
    )
    ends = (
        raw.get("datetime_end")
        or raw.get("ends_at")
        or raw.get("end_at")
        or raw.get("end_time")
        or raw.get("end")
        or raw.get("when_end")
    )
    ev["starts_at"] = str(starts) if starts else ""
    ev["ends_at"] = str(ends) if ends else ""

    sdt = _parse_iso(ev["starts_at"])
    edt = _parse_iso(ev["ends_at"]) if ev["ends_at"] else None
    ev["starts_at_dt"] = sdt or datetime.min.replace(tzinfo=timezone.utc)
    ev["ends_at_dt"] = edt

    ev["original_link"] = _extract_first_url(desc)

    cal_id = None
    if isinstance(raw.get("calendar"), dict):
        cal_id = raw["calendar"].get("id") or raw["calendar"].get("calendar_id")
    cal_id = cal_id or raw.get("calendar_id")
    ev["calendar_id"] = str(cal_id) if cal_id else None

    ev["addevent_url"] = (
        raw.get("landing_page_url") or raw.get("event_url") or raw.get("url") or None
    )

    return ev


# ---- Search ------------------------------------------------------------------

def search_events_between(
    start: date,
    end: date,
    calendar_key: str = DEFAULT_CALENDAR_KEY,
    page_size: int = 20,   # AddEvent caps page_size low; use 20 max
) -> list[PulledEvent]:
    """
    Pull events in the [start, end] inclusive date range using the correct
    v2 search params: datetime_min / datetime_max, sort_by=datetime_start.
    Locally filter as a safety net.
    """
    session = _api_session()
    cal_id = resolve_calendar_id(session, calendar_key)

    # For server-side filter
    dt_min_str, dt_max_str = _api_date_bounds_str(start, end)
    # For local safety filter
    min_utc, max_utc = _utc_bounds(start, end)

    events: list[PulledEvent] = []
    page = 1

    params: dict[str, t.Any] = {
        "page": page,
        "page_size": min(max(1, page_size), 20),
        "sort_by": "datetime_start",   # correct field per docs
        "sort_order": "asc",
        "datetime_min": dt_min_str,    # correct date filters per docs
        "datetime_max": dt_max_str,
    }
    if cal_id:
        params["calendar_id"] = cal_id

    while True:
        params["page"] = page
        try:
            resp = session.get(f"{API_BASE}/events", params=params, timeout=30)
        except Exception as e:
            if DEBUG:
                print(f"[AddEvent] HTTP error: {e}")
            break

        if not resp.ok:
            if DEBUG:
                print(f"[AddEvent] search status={resp.status_code} body={resp.text[:300]}")
            break

        data = resp.json() or {}
        raw_items = data.get("events") or data.get("data") or data.get("items") or []
        if DEBUG and page == 1:
            print(f"[AddEvent] results page 1 count={len(raw_items)} params={params}")

        if not isinstance(raw_items, list) or not raw_items:
            break

        for raw in raw_items:
            ev = _shape_event(raw)

            # safety: calendar filter
            if cal_id and ev.get("calendar_id") and str(ev["calendar_id"]) != str(cal_id):
                continue

            # safety: date filter (compare in UTC)
            sdt = _ensure_aware_local(ev["starts_at_dt"]).astimezone(timezone.utc)
            if not (min_utc <= sdt <= max_utc):
                continue

            events.append(ev)

        # simple numeric paging: stop if fewer than page_size returned
        if len(raw_items) < params["page_size"]:
            break

        page += 1
        if page > 1000:  # safety
            break

    # final sort by local start time
    events.sort(key=lambda e: _ensure_aware_local(e["starts_at_dt"]))
    if DEBUG:
        print(f"[AddEvent] total kept={len(events)}")
    return events


def retrieve_event(event_id: str) -> PulledEvent | None:
    session = _api_session()
    try:
        resp = session.get(f"{API_BASE}/events/{event_id}", timeout=20)
    except Exception:
        return None
    if not resp.ok:
        if DEBUG:
            print(f"[AddEvent] retrieve status={resp.status_code} body={resp.text[:200]}")
        return None
    data = resp.json() or {}
    raw = data.get("event") if isinstance(data.get("event"), dict) else data
    return _shape_event(raw)


# ---- ICS generation ----------------------------------------------------------

def _fmt_ics_dt(dt: datetime | None) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LOCAL_TZ)
    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc.strftime("%Y%m%dT%H%M%SZ")

def make_ics_for_event(ev: PulledEvent) -> str:
    uid = (ev.get("id") or f"pc-{int(datetime.now().timestamp())}") + "@policycrush"
    title = (ev.get("title") or "").replace("\n", " ").strip()
    desc = (ev.get("description") or "").strip()
    url = ev.get("original_link") or ev.get("addevent_url") or ""

    sdt: datetime = _ensure_aware_local(ev.get("starts_at_dt")) or datetime.now().astimezone(LOCAL_TZ)
    edt: datetime | None = _ensure_aware_local(ev.get("ends_at_dt"))
    if not edt:
        edt = sdt + timedelta(hours=1)

    dtstamp = _fmt_ics_dt(datetime.now().astimezone(LOCAL_TZ))
    dtstart = _fmt_ics_dt(sdt)
    dtend = _fmt_ics_dt(edt)

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//PolicyCrush//AddEvent Pull//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{dtstamp}",
        f"DTSTART:{dtstart}",
        f"DTEND:{dtend}",
        f"SUMMARY:{title}",
    ]
    if url:
        lines.append(f"URL:{url}")
    if desc:
        safe = desc.replace("\\", "\\\\").replace(",", r"\,").replace(";", r"\;")
        lines.append(f"DESCRIPTION:{safe}")
    lines += ["END:VEVENT", "END:VCALENDAR", ""]
    return "\r\n".join(lines)


# ---- Grouping for UI/PDF -----------------------------------------------------

def group_by_day(events: list[PulledEvent]) -> dict[str, list[PulledEvent]]:
    grouped: dict[str, list[PulledEvent]] = {}
    for ev in events:
        sdt = _ensure_aware_local(ev.get("starts_at_dt"))
        if not sdt:
            continue
        key = sdt.astimezone(LOCAL_TZ).strftime("%Y-%m-%d")
        grouped.setdefault(key, []).append(ev)
    for k in grouped:
        grouped[k].sort(key=lambda e: _ensure_aware_local(e["starts_at_dt"]))
    return dict(sorted(grouped.items(), key=lambda kv: kv[0]))
