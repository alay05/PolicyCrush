import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_jec_min_articles(start_date=None):
    results = []
    url = "https://www.jec.senate.gov/public/index.cfm/democrats/media"
    response = requests.get(url)
    if response.status_code != 200:
        return results

    soup = BeautifulSoup(response.text, "html.parser")
    articles = soup.select("article.clearfix")

    for article in articles:
        date_span = article.select_one("span.date")
        title_tag = article.select_one("h1.title a")
        if not date_span or not title_tag:
            continue

        try:
            month = date_span.select_one("span.month").text.strip()
            day = date_span.select_one("span.day").text.strip()
            year = date_span.select_one("span.year").text.strip()
            pub_date = datetime.strptime(f"{month} {day} {year}", "%b %d %Y").date()
        except (ValueError, AttributeError):
            continue

        if start_date and pub_date < start_date:
            continue

        title = title_tag.text.strip()
        url = title_tag["href"]
        full_url = url if url.startswith("http") else f"https://www.jec.senate.gov{url}"

        results.append({
            "title": title,
            "url": full_url,
            "date": pub_date.strftime("%Y-%m-%d")
        })

    return results
