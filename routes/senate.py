from flask import Blueprint, render_template, request
from datetime import datetime, timedelta

from sources.senate.aging import fetch_age_articles
from sources.senate.appropriations import fetch_appr_articles
from sources.senate.budget import fetch_budg_articles
from sources.senate.finance import fetch_fin_articles
from sources.senate.help import fetch_help_articles
from sources.senate.homeland import fetch_home_articles
from sources.senate.indian import fetch_ind_articles
from sources.senate.judiciary import fetch_jud_articles
from sources.senate.small_business import fetch_smb_articles
from sources.senate.veterans import fetch_vet_articles

senate = Blueprint("senate", __name__)

SENATE = {
    "Aging": fetch_age_articles,
    "Appropriations": fetch_appr_articles,
    "Budget": fetch_budg_articles,
    "Finance": fetch_fin_articles,
    "Health, Education, Labor & Pensions (HELP)": fetch_help_articles,
    "Homeland Security and Governmental Affairs (Oversight)": fetch_home_articles,
    "Indian Affairs": fetch_ind_articles,
    "Judiciary": fetch_jud_articles,
    "Veterans Affairs": fetch_vet_articles,
    "Small Business": fetch_smb_articles,
}

@senate.route("/senate", methods=["GET", "POST"])
def senate_view():
    input_date = (datetime.today() - timedelta(days=3)).strftime("%Y-%m-%d")
    start_date = None
    error = None
    committees = {}

    if request.method == "POST":
        input_date = request.form.get("start_date", "").strip()
        if input_date:
            try:
                start_date = datetime.strptime(input_date, "%Y-%m-%d").date()
            except ValueError:
                error = "Invalid date."

        if not error and start_date:
            for name, fetch in SENATE.items():
                try:
                    payload = fetch(start_date)
                    articles = payload["articles"]
                    base_url = payload["base_url"]

                    grouped = {
                        "url": base_url,
                        "majority": [],
                        "minority": [],
                        "hearing": [],
                    }

                    for article in articles:
                        tag = article.get("tag", "")
                        if tag in grouped:
                            grouped[tag].append(article)

                    committees[name] = grouped
                except Exception as e:
                    print(f"Error loading {name}: {e}")

    return render_template("senate.html", committees=committees, error=error, input_date=input_date)
