import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_ovs_min_articles(start_date=None):
    results = []
    base_url = "https://oversightdemocrats.house.gov"
    url = f"{base_url}/news/press-releases"

    response = requests.get(url, headers={
        "User-Agent": "Mozilla/5.0"
    })
    if response.status_code != 200:
        return results

    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.select("div.views-row.evo-views-row")

    for row in rows:
        try:
            title_tag = row.select_one("div.h3.mt-0.font-weight-bold a")
            date_tag = row.select_one("div.row .col-auto")
            if not title_tag or not date_tag:
                continue

            title = title_tag.get_text(strip=True)
            url = base_url + title_tag["href"]
            pub_date = datetime.strptime(date_tag.text.strip(), "%B %d, %Y")

            if start_date and pub_date.date() < start_date:
                continue

            results.append({
                "title": title,
                "url": url,
                "date": pub_date.strftime("%Y-%m-%d")
            })
        except Exception:
            continue

    return results
