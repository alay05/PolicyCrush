import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_smb_maj_articles(start_date=None):
    results = []
    base_url = "https://smallbusiness.house.gov/"
    url = f"{base_url}news/"

    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    if response.status_code != 200:
        return results

    soup = BeautifulSoup(response.text, "html.parser")
    articles = soup.select("article.newsblocker")

    for article in articles:
        try:
            title_tag = article.select_one("h2.newsie-titler a")
            date_tag = article.select_one("div.newsie-details time")

            if not title_tag or not date_tag:
                continue

            title = title_tag.get_text(strip=True)
            href = title_tag.get("href", "")
            url = href if href.startswith("http") else base_url + href.lstrip("/")
            pub_date = datetime.strptime(date_tag["datetime"], "%Y-%m-%d")

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
