from flask import Blueprint, render_template, request
from datetime import datetime, timedelta

from sources.news.cms_inov import fetch_cms_inov_articles
from sources.news.cms import fetch_cms_articles
from sources.news.crs import fetch_crs_articles
from sources.news.fda import fetch_fda_articles
from sources.news.fed_reg import fetch_federal_register_articles
from sources.news.hhs import fetch_hhs_articles
from sources.news.whitehouse import fetch_whitehouse_articles

news = Blueprint("news", __name__)

NEWS = {
    "White House": fetch_whitehouse_articles,
    "CMS": fetch_cms_articles,
    "FDA": fetch_fda_articles,
    "CRS": fetch_crs_articles,
    "HHS": fetch_hhs_articles,
    "Federal Register Public Inspection Desk": fetch_federal_register_articles,
    "CMS Innovation Center": fetch_cms_inov_articles,
}

@news.route("/news", methods=["GET", "POST"])
def news_view():
    input_date = (datetime.today() - timedelta(days=3)).strftime("%Y-%m-%d")
    start_date = None
    error = None
    articles = {}

    if request.method == "POST":
        input_date = request.form.get("start_date", "").strip()
        if input_date:
            try:
                start_date = datetime.strptime(input_date, "%Y-%m-%d").date()
            except ValueError:
                error = "Invalid date."

        if not error and start_date:
            for name, fetch in NEWS.items():
                try:
                    payload = fetch(start_date) 
                    articles[name] = {
                        "url": payload["url"],
                        "items": payload["articles"]
                    }
                except Exception as e:
                    print(f"Error fetching {name}: {e}")

    return render_template("news.html", articles=articles, error=error, input_date=input_date)