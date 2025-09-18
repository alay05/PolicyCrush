# routes/add_event_pull.py
from __future__ import annotations

from datetime import datetime, date
from io import BytesIO

from flask import Blueprint, render_template, request, send_file, url_for, redirect, abort, make_response

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
    """
    UI:
      - GET shows a form with start/end
      - POST pulls events and renders grouped by day
    """
    today = date.today()
    default_start = today
    default_end = today

    start_str = request.form.get("start_date") or request.args.get("start")
    end_str = request.form.get("end_date") or request.args.get("end")

    pulled = []
    grouped = {}
    error = None

    if request.method == "POST":
        start = _parse_date(start_str, default_start)
        end = _parse_date(end_str, default_end)
        if not start or not end:
            error = "Please provide valid Start and End dates (YYYY-MM-DD)."
        elif end < start:
            error = "End date must be on or after Start date."
        else:
            try:
                events = search_events_between(start, end, calendar_key=DEFAULT_CALENDAR_KEY)
                pulled = events
                grouped = group_by_day(events)
            except Exception as e:
                print("AddEvent pull error:", e)
                error = "Couldn't pull events from AddEvent. Check API key and try again."

        start_str = (start or default_start).strftime("%Y-%m-%d")
        end_str = (end or default_end).strftime("%Y-%m-%d")

    # GET (initial) – keep defaults visible
    if request.method == "GET" and (not start_str or not end_str):
        start_str = default_start.strftime("%Y-%m-%d")
        end_str = default_end.strftime("%Y-%m-%d")

    return render_template(
        "add_event_pull.html",
        start_date=start_str,
        end_date=end_str,
        grouped=grouped,
        pulled=pulled,
        error=error,
        addevent_calendar_href="https://app.addevent.com/calendars/GT179952",
    )

@add_event_pull.route("/add-event-pull/export", methods=["GET"])
def add_event_pull_export_pdf():
    """
    Render the current range to a PDF using WeasyPrint/pdfkit if available.
    Fallback to returning HTML if no PDF engine is installed.
    """
    start_str = request.args.get("start")
    end_str = request.args.get("end")

    if not (start_str and end_str):
        # Forward back to the UI
        return redirect(url_for("add_event_pull.add_event_pull_home"))

    start = _parse_date(start_str)
    end = _parse_date(end_str)
    if not start or not end or end < start:
        abort(400, "Invalid date range")

    events = search_events_between(start, end, calendar_key=DEFAULT_CALENDAR_KEY)
    grouped = group_by_day(events)

    # Render HTML first
    html = render_template(
        "pdf.html",
        title="AddEvent Pull",
        grouped=grouped,
        generated_at=datetime.now(),
        include_ics=True,
    )

    # Try WeasyPrint
    try:
        from weasyprint import HTML  # type: ignore
        pdf_bytes = HTML(string=html, base_url=request.host_url).write_pdf()
        fname = f"addEvent-{start.strftime('%m_%d')}to{end.strftime('%m_%d')}.pdf"
        return send_file(
            BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=fname,
        )
    except Exception:
        pass

    # Try pdfkit (wkhtmltopdf)
    try:
        import pdfkit  # type: ignore
        pdf_bytes = pdfkit.from_string(html, False)
        fname = f"addevent-{start.strftime('%Y%m%d')}-{end.strftime('%Y%m%d')}.pdf"
        return send_file(
            BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=fname,
        )
    except Exception:
        # Fallback HTML
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
