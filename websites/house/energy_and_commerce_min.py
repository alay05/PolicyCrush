import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_eac_min_articles(start_date=None):
    results = []
    url = "https://democrats-energycommerce.house.gov/media"

    response = requests.get(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    })
    if response.status_code != 200:
        return results

    soup = BeautifulSoup(response.text, "html.parser")
    items = soup.select("div.views-row")

    for item in items:
        try:
            title_tag = item.select_one("div.media-body div.h3 a")
            date_span = item.select_one("div.evo-card-date-bundle span")
            if not title_tag or not date_span:
                continue

            title = title_tag.get_text(strip=True)
            href = title_tag.get("href", "")
            full_url = "https://democrats-energycommerce.house.gov" + href

            pub_date = datetime.strptime(date_span.get_text(strip=True), "%B %d, %Y")
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
