from flask import Blueprint, render_template, request, redirect, url_for
from sources.messages import authenticate, logout, get_messages, extract_html_from_email

gmail = Blueprint("gmail", __name__)

@gmail.route("/gmail", methods=["GET", "POST"])
def gmail_view():
    articles = None
    error = None
    input_date = ""

    if request.method == "POST":
        try:
            service = authenticate()
            messages = get_messages(service)
            articles = {}

            for msg in messages:
                subject, html = extract_html_from_email(service, msg['id'])
                if html:
                    articles[subject] = {"html": html}
        except Exception as e:
            error = f"Error: {e}"

    return render_template("gmail.html", articles=articles, error=error, input_date=input_date)

@gmail.route("/gmail/logout")
def gmail_logout():
    logout()
    return redirect(url_for("gmail.gmail_view"))