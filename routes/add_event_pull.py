# routes/add_event_pull.py
from __future__ import annotations

from datetime import datetime, date
from io import BytesIO

from flask import Blueprint, render_template, request, send_file, url_for, redirect, abort, make_response, session, jsonify
from features.categorize import categorize_article, CATEGORIES
from collections import OrderedDict
import hashlib, json

from features.calendar_pull import (
    search_events_between,
    retrieve_event,
    make_ics_for_event,
    group_by_day,
    DEFAULT_CALENDAR_KEY,
)

add_event_pull = Blueprint("add_event_pull", __name__)

def _parse_date(s: str, fallback: date | None = None) -> date | None:
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return fallback

@add_event_pull.route("/add-event-pull", methods=["GET", "POST"])
def add_event_pull_home():
    today = date.today()
    default_start = today
    default_end = today

    start_str = request.form.get("start_date") or request.args.get("start")
    end_str   = request.form.get("end_date")   or request.args.get("end")


    pulled, grouped, error = [], {}, None

    # NEW: default + compute from session so GET works
    categorize_ready = False
    cur_events = session.get("addevent_pulled") or []
    if cur_events:
        cur_sig = _event_signature(cur_events)
        cache = session.get("addevent_categories_cache") or {}
        categorize_ready = bool(cache.get("sig") == cur_sig and cache.get("index"))

    if request.method == "POST":
        start = _parse_date(start_str, default_start)
        end   = _parse_date(end_str, default_end)
        if not start or not end:
            error = "Please provide valid Start and End dates (YYYY-MM-DD)."
        elif end < start:
            error = "End date must be on or after Start date."
        else:
            try:
                events  = search_events_between(start, end, calendar_key=DEFAULT_CALENDAR_KEY)
                pulled  = events
                grouped = group_by_day(events)

                session["addevent_pulled"] = [_event_minimal(ev) for ev in (events or [])]
                session.modified = True

                # Recompute after updating session
                cur_events = session.get("addevent_pulled") or []
                cur_sig = _event_signature(cur_events)
                cache = session.get("addevent_categories_cache") or {}
                categorize_ready = bool(cache.get("sig") == cur_sig and cache.get("index"))
            except Exception as e:
                print("AddEvent pull error:", e)
                error = "Couldn't pull events from AddEvent. Check API key and try again."

        start_str = (start or default_start).strftime("%Y-%m-%d")
        end_str   = (end   or default_end  ).strftime("%Y-%m-%d")
        session["addevent_last_range"] = {"start": start_str, "end": end_str}
        session.modified = True

    # GET (initial) – keep defaults visible
    if request.method == "GET" and (not start_str or not end_str):
        start_str = default_start.strftime("%Y-%m-%d")
        end_str   = default_end.strftime("%Y-%m-%d")
        session["addevent_last_range"] = {"start": start_str, "end": end_str}
        session.modified = True

    return render_template(
        "add_event_pull.html",
        start_date=start_str,
        end_date=end_str,
        grouped=grouped,
        pulled=pulled,
        error=error,
        addevent_calendar_href="https://app.addevent.com/calendars/GT179952",
        categorize_ready=categorize_ready,
    )

@add_event_pull.route("/add-event-pull/export", methods=["GET"])
def add_event_pull_export_pdf():
    # Require built categories that match current pulled set
    cache = session.get("addevent_categories_cache") or {}
    events_min = session.get("addevent_pulled") or []
    if not cache.get("index") or not events_min:
        return redirect(url_for("add_event_pull.add_event_categories_review"))
    if cache.get("sig") != _event_signature(events_min):
        return redirect(url_for("add_event_pull.add_event_categories_review"))

    # Use last pulled range (or explicit query args) to re-pull full event objects
    last_range = session.get("addevent_last_range") or {}
    start_str = request.args.get("start") or last_range.get("start")
    end_str   = request.args.get("end")   or last_range.get("end")
    if not (start_str and end_str):
        return redirect(url_for("add_event_pull.add_event_categories_review"))

    start = _parse_date(start_str)
    end   = _parse_date(end_str)
    if not start or not end or end < start:
        abort(400, "Invalid date range")

    # Re-pull full events so PDF has full fields (starts_at_dt, original_link, etc.)
    events_full = search_events_between(start, end, calendar_key=DEFAULT_CALENDAR_KEY) or []
    by_id = {str((e.get("id") if isinstance(e, dict) else getattr(e, "id", ""))): e for e in events_full}

    # Build ordered categories from cache index -> list of full event objs
    index = cache.get("index") or {}
    preferred = [*CATEGORIES]
    ordered = OrderedDict()

    # helper to get printable dt inside template
    def _attach_dt(ev):
        # ensure attribute access works in Jinja either way
        if isinstance(ev, dict):
            return ev
        return ev  # Jinja handles attr/item lookup; no change needed

    for lab in preferred:
        if lab in index:
            items = []
            for ref in index[lab] or []:
                ev = by_id.get(str(ref))
                if ev:
                    items.append(_attach_dt(ev))
            if items:
                ordered[lab] = items

    # append any unexpected categories
    for lab, refs in index.items():
        if lab in ordered:
            continue
        items = []
        for ref in refs or []:
            ev = by_id.get(str(ref))
            if ev:
                items.append(_attach_dt(ev))
        if items:
            ordered[lab] = items

    if not ordered:
        # nothing matched the current range; bounce to review
        return redirect(url_for("add_event_pull.add_event_categories_review"))

    # Render HTML (category-grouped) then to PDF
    html = render_template(
        "pdf.html",
        title="AddEvent Categories",
        categories=ordered,
        generated_at=datetime.now(),
        include_ics=True,
    )

    try:
        from weasyprint import HTML  # type: ignore
        pdf_bytes = HTML(string=html, base_url=request.host_url).write_pdf()
        fname = f"addevent-categories-{start.strftime('%m_%d')}to{end.strftime('%m_%d')}.pdf"
        return send_file(BytesIO(pdf_bytes), mimetype="application/pdf", as_attachment=True, download_name=fname)
    except Exception:
        pass
    try:
        import pdfkit  # type: ignore
        pdf_bytes = pdfkit.from_string(html, False)
        fname = f"addevent-categories-{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}.pdf"
        return send_file(BytesIO(pdf_bytes), mimetype="application/pdf", as_attachment=True, download_name=fname)
    except Exception:
        resp = make_response(html)
        resp.headers["Content-Type"] = "text/html; charset=utf-8"
        return resp


@add_event_pull.route("/add-event-pull/ics/<event_id>.ics", methods=["GET"])
def add_event_pull_event_ics(event_id: str):
    """
    Build and return a per-event .ics using live data from AddEvent.
    """
    ev = retrieve_event(event_id)
    if not ev:
        abort(404, "Event not found")

    ics = make_ics_for_event(ev)
    fname = f"addevent-{event_id}.ics"
    return send_file(
        BytesIO(ics.encode("utf-8")),
        mimetype="text/calendar; charset=utf-8",
        as_attachment=True,
        download_name=fname,
    )

def _event_minimal(ev: dict) -> dict:
    """Normalize an AddEvent record into the minimal shape used for categorizing."""
    title = (ev.get("title") or "")[:240]  # trim to keep cookie small
    url   = (ev.get("original_link") or ev.get("addevent_url") or "")[:300]
    date_str = ev.get("when_text") or ev.get("start") or ""
    if isinstance(date_str, (datetime, date)):
        date_str = date_str.isoformat()
    return {
        "id": ev.get("id"),
        "title": title,
        "url": url,
        "date": (date_str or "")[:40],
        "source": "addevent",
    }

def _event_signature(events: list[dict]) -> str:
    base = [(str(e.get("id")), e.get("title") or "") for e in events]
    return hashlib.sha1(json.dumps(sorted(base), separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()

def _resolve_event_ref(ref: str, events_by_id: dict[str, dict]) -> dict | None:
    return events_by_id.get(str(ref))

@add_event_pull.post("/add-event-pull/build-categories")
def add_event_pull_build_categories():
    """Build (or rebuild) a categories index for the *current pulled* AddEvent events."""
    events = session.get("addevent_pulled") or []

    # Fallback: if session is empty (e.g., cookie too big or new tab),
    # re-pull using the hidden range fields we added to the form.
    if not events:
        start_str = request.form.get("start") or request.args.get("start")
        end_str   = request.form.get("end")   or request.args.get("end")
        s = _parse_date(start_str)
        e = _parse_date(end_str)
        if s and e and e >= s:
            try:
                fresh = search_events_between(s, e, calendar_key=DEFAULT_CALENDAR_KEY)
                events = [_event_minimal(ev) for ev in (fresh or [])]
                # write back so the review page can hydrate
                session["addevent_pulled"] = events
                session.modified = True
            except Exception as e:
                print("AddEvent pull (build) error:", e)
                return redirect(url_for("add_event_pull.add_event_pull_home"))
        else:
            return redirect(url_for("add_event_pull.add_event_pull_home"))

    # Build signature + cache
    sig = _event_signature(events)
    cache = session.get("addevent_categories_cache") or {}
    if cache.get("sig") == sig and cache.get("index"):
        session["addevent_categorize_ready"] = True
        session.modified = True
        return redirect(url_for("add_event_pull.add_event_categories_review"))

    categories_index = {
        "Congress and the Administration": [],
        "Health Insurance": [],
        "Health Tech": [],
        "Medicaid": [],
        "Medicare": [],
        "Pharmaceuticals and Medical Devices": [],
        "Quality and Innovation": [],
    }

    # AddEvent pulls are all "events"
    for ev in events:
        label = categorize_article(ev.get("title", ""), is_hearing=False)
        if label not in categories_index:
            label = "Quality and Innovation"
        categories_index[label].append(str(ev.get("id")))

    session["addevent_categories_cache"] = {
        "built_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "sig": sig,
        "count": len(events),
        "index": categories_index,
    }
    session["addevent_categorize_ready"] = True
    session.modified = True
    return redirect(url_for("add_event_pull.add_event_categories_review"))

@add_event_pull.get("/add-event-pull/review")
def add_event_categories_review():
    cache = session.get("addevent_categories_cache")
    if not isinstance(cache, dict) or "index" not in cache:
        return redirect(url_for("add_event_pull.add_event_pull_home"))

    index = cache.get("index") or {}
    events = session.get("addevent_pulled") or []
    by_id = {str(e.get("id")): e for e in events}

    hydrated = {}
    for label, refs in index.items():
        items = []
        for ref in refs or []:
            resolved = _resolve_event_ref(ref, by_id)
            if not resolved:
                continue
            item = dict(resolved)
            item["_ref"] = str(ref)  # stick the ref on for the DOM
            items.append(item)
        hydrated[label] = items

    preferred = [*CATEGORIES]
    ordered = OrderedDict((lab, hydrated.get(lab, [])) for lab in preferred if lab in hydrated)
    for lab, items in hydrated.items():
        if lab not in ordered:
            ordered[lab] = items

    last_range = session.get("addevent_last_range") or {}
    return render_template(
        "add_event_categories.html",
        categories=ordered,
        built_at=cache.get("built_at"),
        last_range=last_range, 
    )

@add_event_pull.post("/add-event-pull/move-article")
def add_event_pull_move_article():
    """
    Body: { id: str, from_category: str|None, to_category: str, new_index: int }
    Mutates session['addevent_categories_cache']['index'].
    """
    payload = request.get_json(silent=True) or {}
    art_id = (payload.get("id") or "").strip()
    from_cat = payload.get("from_category")
    to_cat = payload.get("to_category")
    new_index = payload.get("new_index")

    if not art_id or not to_cat or new_index is None:
        return jsonify(ok=False, error="Missing id/to_category/new_index"), 400

    cache = session.get("addevent_categories_cache")
    if not isinstance(cache, dict) or "index" not in cache:
        return jsonify(ok=False, error="No category index in session"), 400

    index = cache.get("index") or {}
    dest_list = index.setdefault(to_cat, [])

    # try to remove the first matching ref
    removed_ref = None
    if from_cat in index:
        lst = index[from_cat] or []
        for i, ref in enumerate(lst):
            if str(ref) == str(art_id):
                removed_ref = lst.pop(i)
                break
    if removed_ref is None:
        # search all categories if from_cat wasn't accurate
        for lst in index.values():
            for i, ref in enumerate(lst or []):
                if str(ref) == str(art_id):
                    removed_ref = lst.pop(i)
                    break
            if removed_ref is not None:
                break

    if removed_ref is None:
        return jsonify(ok=False, error="Article not found in index"), 404

    insert_at = max(0, min(int(new_index), len(dest_list)))
    dest_list.insert(insert_at, removed_ref)

    cache["index"] = index
    cache["built_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session["addevent_categories_cache"] = cache
    session.modified = True
    return jsonify(ok=True)

