import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_home_min_articles(start_date=None):
    results = []
    url = "https://democrats-homeland.house.gov/news/press-releases/table/"

    response = requests.get(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    })
    if response.status_code != 200:
        return results

    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.select("table#browser_table tbody tr")

    for row in rows:
        try:
            date_tag = row.select_one("td.date time")
            link_tag = row.select_one("td a")

            if not date_tag or not link_tag:
                continue

            title = link_tag.get_text(strip=True)
            href = link_tag.get("href", "").strip()
            full_url = href if href.startswith("http") else "https://democrats-homeland.house.gov" + href

            pub_date = datetime.strptime(date_tag["datetime"], "%Y-%m-%d")
            if start_date and pub_date.date() < start_date:
                continue

            results.append({
                "title": title,
                "url": full_url,
                "date": pub_date.strftime("%Y-%m-%d")
            })
        except Exception:
            continue

    return results
