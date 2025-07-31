import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_wam_min_articles(start_date=None):
    results = []
    url = "https://democrats-waysandmeans.house.gov/media-center"

    response = requests.get(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    })

    if response.status_code != 200:
        return results

    soup = BeautifulSoup(response.text, "html.parser")
    items = soup.select("div.views-row")

    for item in items:
        try:
            media_body = item.select_one("div.media-body")
            if not media_body:
                continue

            title_div = media_body.select_one("div.h3 a")
            if not title_div:
                continue

            title = title_div.text.strip()
            href = title_div["href"].strip()
            full_url = "https://democrats-waysandmeans.house.gov" + href

            date_div = title_div.find_parent("div").find_next_sibling("div")
            if not date_div:
                continue

            raw_date = date_div.text.strip()
            pub_date = datetime.strptime(raw_date, "%B %d, %Y")

            if start_date and pub_date.date() < start_date:
                continue

            results.append({
                "title": title,
                "url": full_url,
                "date": pub_date.strftime("%Y-%m-%d")
            })

        except:
            continue

    return results
