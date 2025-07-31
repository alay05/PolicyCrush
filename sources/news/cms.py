import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_cms_articles(start_date=None):
    results = []
    url = "https://www.cms.gov/about-cms/contact/newsroom"

    response = requests.get(url)
    if response.status_code != 200:
        return results

    soup = BeautifulSoup(response.text, "html.parser")
    items = soup.select("div.views-field.views-field-nothing")

    for item in items:
        title_tag = item.select_one("h3")
        link_tag = item.select_one("a.newsroom-main-view-link")
        date_tag = item.select_one("time")

        if not title_tag or not link_tag or not date_tag:
            continue

        try:
            pub_date = datetime.strptime(date_tag["datetime"], "%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            continue

        if start_date and pub_date.date() < start_date:
            continue

        results.append({
            "title": title_tag.text.strip(),
            "url": "https://www.cms.gov" + link_tag["href"],
            "date": pub_date.strftime("%Y-%m-%d")
        })

    return {
        "url": url,
        "articles": results,
    }
