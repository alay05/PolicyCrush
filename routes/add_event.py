from flask import Blueprint, render_template, request
from features.calendar import fetch_hearing_html, extract_event_info, create_event_addevent
import json
from datetime import datetime, timedelta

add_event = Blueprint("add_event", __name__)

@add_event.route("/add-event", methods=["GET", "POST"])
def hearing_form():
    result = None
    error = None

    if request.method == "POST":
        url = request.form.get("event-url")
        if not url:
            error = "Please enter a URL."
        else:
            try:
                raw_text = fetch_hearing_html(url)
                extracted = extract_event_info(raw_text)    

                parsed = json.loads(extracted)
                start_dt = datetime.strptime(f"{parsed['date']} {parsed['time']}", "%Y-%m-%d %H:%M")
                end_dt = start_dt + timedelta(hours=1)

                event = {
                    "title": "[AUTO-TEST]" + parsed["title"],
                    "datetime_start": start_dt.strftime("%Y-%m-%d %H:%M"),
                    "datetime_end": end_dt.strftime("%Y-%m-%d %H:%M"),
                    "location": parsed.get("location", ""),
                    "description": url,
                    "timezone": "America/New_York"
                }

                create_event_addevent(event)

                result = {
                    "title": event["title"],
                    "datetime": event["datetime_start"],
                    "location": event["location"],
                    "addevent_link": "https://app.addevent.com/calendars/GT179952"
                }

            except Exception as e:
                print(e)
                error = "Invalid Link"

    return render_template("add_event.html", result=result, error=error)