# GET API KEYS
import os
import requests
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADDEVENT_API_KEY = os.getenv("ADDEVENT_API_KEY")
ADDEVENT_CALENDAR_ID = os.getenv("ADDEVENT_CALENDAR_ID")  # optional but recommended

client = OpenAI(api_key=OPENAI_API_KEY)

# ----------------------------
# Web fetch (unchanged)
# ----------------------------
def fetch_hearing_html(url: str) -> str:
    resp = requests.get(url, timeout=20)
    if resp.status_code != 200:
        raise Exception(f"Failed to fetch page: {resp.status_code}")
    return BeautifulSoup(resp.text, "html.parser").get_text()

# ----------------------------
# AI extraction (unchanged)
# ----------------------------
def extract_event_info(page_text: str) -> str:
    prompt = f"""
Extract the following information from the congressional hearing text below:

Return ONLY raw, valid JSON with the following fields:
- "title" (string): If the full title is longer than 100 characters, summarize it to stay under 100 characters while retaining key information (e.g., names, topics, agencies, bill titles, etc.).
- "date" (YYYY-MM-DD)
- "time" (HH:MM in 24-hour format)
- "location" (string or empty)

DO NOT include any explanation, formatting, markdown, or commentary. DO NOT make up or infer any information. ONLY return the JSON object.

Text:
{page_text[:4000]}
"""
    resp = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant extracting congressional hearing event details."},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
    )
    return resp.choices[0].message.content

# ------------------------------------------------
# AddEvent helpers: search + create (with de-dupe)
# ------------------------------------------------

_ADDEVENT_API_BASE = "https://api.addevent.com/calevent/v2"
_ADDEVENT_HEADERS = {"Authorization": f"Bearer {ADDEVENT_API_KEY}"} if ADDEVENT_API_KEY else {}

def _parse_dt_minute(dt_str: str):
    """
    Parse 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD HH:MM:SS' safely to minute precision.
    Returns datetime or None.
    """
    if not dt_str:
        return None
    dt_str = dt_str.strip()
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(dt_str[:len(fmt)], fmt)
        except Exception:
            pass
    return None

def _search_events_addevent(q: str = None,
                            calendar_id: str = None,
                            starts_after: datetime = None,
                            starts_before: datetime = None,
                            page_size: int = 20) -> dict:
    """
    Query AddEvent for existing events (v2). Returns JSON.
    We use 'q' to match text (title/description), and optionally narrow by start window.
    """
    if not ADDEVENT_API_KEY:
        # If no key configured, just act like there's nothing found.
        return {"events": []}

    params = {"page_size": max(1, min(int(page_size or 20), 20))}
    if q:
        params["q"] = q
    if calendar_id:
        params["calendar_id"] = calendar_id
    if starts_after:
        params["starts_after"] = starts_after.strftime("%Y-%m-%dT%H:%M:%S")
    if starts_before:
        params["starts_before"] = starts_before.strftime("%Y-%m-%dT%H:%M:%S")

    r = requests.get(f"{_ADDEVENT_API_BASE}/events", headers=_ADDEVENT_HEADERS, params=params, timeout=15)
    r.raise_for_status()
    return r.json()

def create_event_addevent(data: dict,
                          *,
                          dedupe: bool = True,
                          dedupe_window_hours: int = 3,
                          calendar_id: str = None) -> dict:
    """
    Create an AddEvent event. If dedupe=True (default), first search the calendar
    for an existing event with the same source URL (in 'description') around the same start time.
    If found, return that existing event instead of creating a duplicate.

    Expected keys in `data` (same as your current usage):
      - title: str
      - datetime_start: 'YYYY-MM-DD HH:MM'
      - datetime_end:   'YYYY-MM-DD HH:MM'
      - location: str (optional)
      - description: str (we put the source URL here)
      - timezone: str

    Returns JSON with at least 'id' and 'url' keys (compatible with your current route).
    """
    if not ADDEVENT_API_KEY:
        raise Exception("Missing ADDEVENT_API_KEY")

    # --- Optional de-duplication ---
    if dedupe:
        try:
            url_tag = (data.get("description") or "").strip()
            dt_start = _parse_dt_minute(data.get("datetime_start") or "")
            if url_tag and dt_start:
                win = timedelta(hours=max(1, int(dedupe_window_hours)))
                sr = _search_events_addevent(
                    q=url_tag,
                    calendar_id=(calendar_id or ADDEVENT_CALENDAR_ID),
                    starts_after=dt_start - win,
                    starts_before=dt_start + win,
                    page_size=20,
                )
                for ev in (sr.get("events") or []):
                    # Normalize candidate start time
                    ev_start = _parse_dt_minute(ev.get("datetime_start") or ev.get("start") or "")
                    # Confirm same URL is present in description
                    desc = (ev.get("description") or "")
                    if ev_start and abs((ev_start - dt_start).total_seconds()) <= win.total_seconds() and url_tag in desc:
                        # Build a minimal compatible response
                        existing_id = ev.get("id") or ev.get("event_id")
                        existing_url = ev.get("url") or ev.get("link")
                        return {"id": existing_id, "url": existing_url, "deduped": True}
        except Exception:
            # If search fails, just fall through and create.
            pass

    # --- Create new event ---
    endpoint = f"{_ADDEVENT_API_BASE}/events"
    r = requests.post(endpoint, json=data, headers=_ADDEVENT_HEADERS, timeout=15)
    if r.status_code not in (200, 201):
        raise Exception(f"Failed to create event: {r.status_code} — {r.text}")
    res = r.json()

    # Ensure compatibility keys exist on return
    event_id = res.get("id") or res.get("event", {}).get("id")
    event_url = res.get("url") or res.get("event", {}).get("url") or res.get("link")
    if event_id or event_url:
        res.setdefault("id", event_id)
        res.setdefault("url", event_url)
    res.setdefault("deduped", False)
    return res
