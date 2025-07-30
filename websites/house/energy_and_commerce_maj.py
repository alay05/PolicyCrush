import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_eac_maj_articles(start_date=None):
    results = []
    url = "https://energycommerce.house.gov/news"

    response = requests.get(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    })

    if response.status_code != 200:
        return results

    soup = BeautifulSoup(response.text, "html.parser")
    items = soup.select("article.shadow-md")

    for item in items:
        try:
            # Date
            date_div = item.select_one("div.flex.flex-col.flex-wrap div")
            if not date_div:
                continue
            pub_date = datetime.strptime(date_div.get_text(strip=True), "%b %d, %Y")
            if start_date and pub_date.date() < start_date:
                continue

            # Title
            title_tag = item.select_one("h3[data-ig-id='card-title']")
            title = title_tag.get_text(strip=True) if title_tag else None

            # URL
            link_tag = item.select_one("a.mt-auto")
            href = link_tag.get("href") if link_tag else None
            full_url = "https://energycommerce.house.gov" + href if href else None

            if not title or not full_url:
                continue

            results.append({
                "title": title,
                "url": full_url,
                "date": pub_date.strftime("%Y-%m-%d")
            })
        except Exception:
            continue

    return results
