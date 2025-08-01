from flask import Blueprint, render_template, request
from add_event.calendar import fetch_hearing_html, extract_event_info, create_event_addevent
import json
from datetime import datetime, timedelta

add_event = Blueprint("add_event", __name__)

@add_event.route("/add-event", methods=["GET", "POST"])
def hearing_form():
    result = None
    error = None

    if request.method == "POST":
        url = request.form.get("hearing_url")
        if not url:
            error = "Please enter a hearing URL."
        else:
            try:
                raw_text = fetch_hearing_html(url)
                extracted = extract_event_info(raw_text)

                parsed = json.loads(extracted)
                start_dt = datetime.strptime(f"{parsed['date']} {parsed['time']}", "%Y-%m-%d %H:%M")
                end_dt = start_dt + timedelta(hours=1)

                event = {
                    "title": "[AUTO-TEST]" + parsed["title"],
                    "start": start_dt.strftime("%Y-%m-%d %H:%M"),
                    "end": end_dt.strftime("%Y-%m-%d %H:%M"),
                    "location": parsed.get("location", ""),
                    "description": parsed.get("description", ""),
                    "timezone": "America/New_York"
                }

                response = create_event_addevent(event)
                result = {
                    "title": event["title"],
                    "datetime": event["start"],
                    "location": event["location"],
                    "addevent_link": response.get("calendar_url", None) or "https://www.addevent.com"
                }

            except Exception as e:
                error = f"Error: {e}"

    return render_template("add_event.html", result=result, error=error)