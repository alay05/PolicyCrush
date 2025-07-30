import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_wam_maj_articles(start_date=None):
    results = []
    url = "https://waysandmeans.house.gov/news/"

    response = requests.get(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    })

    if response.status_code != 200:
        return results

    soup = BeautifulSoup(response.text, "html.parser")
    items = soup.select("div.news-wrap div.news-item")

    for item in items:
        date_tag = item.select_one("span.date-bar")
        title_tag = item.select_one("span.title a")

        if not date_tag or not title_tag:
            continue

        try:
            pub_date = datetime.strptime(date_tag.text.strip(), "%B %d, %Y")
        except ValueError:
            continue

        if start_date and pub_date.date() < start_date:
            continue

        results.append({
            "title": title_tag.text.strip(),
            "url": title_tag["href"],
            "date": pub_date.strftime("%Y-%m-%d")
        })

    return results
