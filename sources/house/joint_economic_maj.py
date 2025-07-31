import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_jec_maj_articles(start_date=None):
    results = []
    url = "https://www.jec.senate.gov/public/index.cfm/republicans/newsroom"
    response = requests.get(url)
    if response.status_code != 200:
        return results

    soup = BeautifulSoup(response.text, "html.parser")
    items = soup.select("a[href*='/republicans/newsroom?id=']")

    for item in items:
        span = item.select_one("span.post-date")
        title_tag = item.select_one("h3")
        if not span or not title_tag:
            continue

        try:
            pub_date = datetime.strptime(span.text.strip(), "%B %d, %Y").date()
        except ValueError:
            continue

        if start_date and pub_date < start_date:
            continue

        url = item["href"]
        full_url = url if url.startswith("http") else f"https://www.jec.senate.gov{url}"
        title = title_tag.text.strip()

        results.append({
            "title": title,
            "url": full_url,
            "date": pub_date.strftime("%Y-%m-%d")
        })

    return results
