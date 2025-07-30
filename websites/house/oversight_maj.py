import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_ovs_maj_articles(start_date=None):
    results = []
    url = "https://oversight.house.gov/release/"

    response = requests.get(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    })
    if response.status_code != 200:
        return results

    soup = BeautifulSoup(response.text, "html.parser")
    posts = soup.select("div.post.featured-post")

    for post in posts:
        try:
            link_tag = post.select_one("a")
            title_tag = post.select_one("div.title")
            date_tag = post.select_one("time")

            if not link_tag or not title_tag or not date_tag:
                continue

            title = title_tag.get_text(strip=True)
            url = link_tag["href"].strip()
            pub_date = datetime.strptime(date_tag["datetime"][:10], "%Y-%m-%d")

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
