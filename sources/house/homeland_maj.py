import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_home_maj_articles(start_date=None):
    results = []
    url = "https://homeland.house.gov/press/"

    response = requests.get(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    })

    if response.status_code != 200:
        return results

    soup = BeautifulSoup(response.text, "html.parser")
    articles = soup.select("a.news-post")

    for article in articles:
        try:
            title_tag = article.select_one("div.title")
            date_tag = article.select_one("div.date")

            if not title_tag or not date_tag:
                continue

            title = title_tag.get_text(strip=True)
            href = article.get("href", "").strip()
            full_url = href if href.startswith("http") else "https://homeland.house.gov" + href

            # Convert MM/DD/YY to YYYY-MM-DD
            pub_date = datetime.strptime(date_tag.text.strip(), "%m/%d/%y")

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
