import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_fda_articles(start_date=None):
    results = []
    url = "https://www.fda.gov/news-events/fda-newsroom/press-announcements"

    response = requests.get(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    })
    
    if response.status_code != 200:
        return results

    soup = BeautifulSoup(response.text, "html.parser")
    items = soup.select("div.views-field.views-field-title span.field-content")

    for item in items:
        link_tag = item.find("a")
        date_tag = item.find("time")

        if not link_tag or not date_tag:
            continue

        try:
            pub_date = datetime.strptime(date_tag["datetime"], "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue

        if start_date and pub_date.date() < start_date:
            continue

        results.append({
            "title": link_tag.text.strip().split(" - ", 1)[-1],
            "url": "https://www.fda.gov" + link_tag["href"],
            "date": pub_date.strftime("%Y-%m-%d")
        })

    return {
        "url": url,
        "articles": results,
    }
