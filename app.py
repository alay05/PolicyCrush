from flask import Flask, render_template, request
from websites.whitehouse import fetch_whitehouse_articles
from websites.cms import fetch_cms_articles
from websites.fda import fetch_fda_articles
from websites.crs import fetch_crs_articles
from websites.hhs import fetch_hhs_articles
from websites.fed_reg import fetch_federal_register_articles
from gmail.messages import authenticate, get_messages, extract_links_from_email
from datetime import datetime

app = Flask(__name__)

@app.route("/", methods=["GET", "POST"])
def index():
    articles = None
    error = None
    input_date = ""

    if request.method == "POST":
        input_date = request.form.get("start_date", "").strip()
        start_date = None

        try:
            if input_date:
                start_date = datetime.strptime(input_date, "%Y-%m-%d").date()
 
            articles = {
                "White House": {
                    "url": "https://www.whitehouse.gov/news/",
                    "items": fetch_whitehouse_articles(start_date)
                },
                "CMS": {
                    "url": "https://www.cms.gov/about-cms/contact/newsroom",
                    "items": fetch_cms_articles(start_date)
                },
                "FDA": {
                    "url": "https://www.fda.gov/news-events/fda-newsroom/press-announcements",
                    "items": fetch_fda_articles(start_date)
                },
                "CRS": {
                    "url": "https://www.congress.gov/crs-products",
                    "items": fetch_crs_articles(start_date),
                },
                "HHS": {
                    "url": "https://www.hhs.gov/",
                    "items": fetch_hhs_articles(start_date),
                },
                "Federal Register Public Inspection Desk": {
                    "url": "https://www.federalregister.gov/public-inspection/search?conditions%5Bagencies%5D%5B%5D=agency-for-healthcare-research-and-quality&conditions%5Bagencies%5D%5B%5D=centers-for-medicare-medicaid-services&conditions%5Bagencies%5D%5B%5D=children-and-families-administration&conditions%5Bagencies%5D%5B%5D=defense-department&conditions%5Bagencies%5D%5B%5D=drug-enforcement-administration&conditions%5Bagencies%5D%5B%5D=employment-standards-administration&conditions%5Bagencies%5D%5B%5D=food-and-drug-administration&conditions%5Bagencies%5D%5B%5D=health-and-human-services-department&conditions%5Bagencies%5D%5B%5D=health-resources-and-services-administration&conditions%5Bagencies%5D%5B%5D=internal-revenue-service&conditions%5Bagencies%5D%5B%5D=justice-department&conditions%5Bagencies%5D%5B%5D=national-institutes-of-health&conditions%5Bagencies%5D%5B%5D=occupational-safety-and-health-administration&conditions%5Bagencies%5D%5B%5D=substance-abuse-and-mental-health-services-administration&conditions%5Bagencies%5D%5B%5D=treasury-department&conditions%5Bagencies%5D%5B%5D=centers-for-disease-control-and-prevention",
                    "items": fetch_federal_register_articles(start_date),
                }
            }

        except ValueError:
            error = "Invalid date."

    return render_template("index.html", articles=articles, error=error, input_date=input_date)

@app.route("/gmail", methods=["GET", "POST"])
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
                subject, links = extract_links_from_email(service, msg['id'])
                if links:
                    articles[subject] = {"items": links}
        except Exception as e:
            error = f"Error: {e}"

    return render_template("gmail.html", articles=articles, error=error, input_date=input_date)

if __name__ == "__main__":
    app.run(debug=True)
