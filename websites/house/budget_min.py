import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_budg_min_articles(start_date=None):
    results = []
    url = "https://democrats-budget.house.gov/news/press-releases"

    response = requests.get(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    })

    if response.status_code != 200:
        return results

    soup = BeautifulSoup(response.text, "html.parser")
    articles = soup.select("div.views-row")

    for article in articles:
        try:
            # Title and URL
            title_tag = article.select_one("div.h3 a")
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            href = title_tag.get("href", "").strip()
            full_url = "https://democrats-budget.house.gov" + href

            # date
            date_div = article.select_one("div.date")
            if not date_div:
                all_divs = article.select("div.media-body > div")
                date_candidate = all_divs[1] if len(all_divs) > 1 else None
                if not date_candidate:
                    continue
                raw_date = date_candidate.get_text(strip=True)
            else:
                raw_date = date_div.get_text(strip=True)

            pub_date = datetime.strptime(raw_date, "%B %d, %Y")
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
