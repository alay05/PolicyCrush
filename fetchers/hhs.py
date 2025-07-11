import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_hhs_articles(start_date=None):
    results = []
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    url = f"https://web.archive.org/web/{timestamp}/https://www.hhs.gov/press-room/index.html"
    
    response = requests.get(url)
    if response.status_code != 200:
        return results

    soup = BeautifulSoup(response.text, "html.parser")
    items = soup.select("li.usa-collection__item.teaser-news")

    for i, item in enumerate(items):
        try:
            link_tag = item.select_one("a.usa-link")
            date_tag = item.select_one("time")

            if not link_tag or not date_tag:
                continue

            title = link_tag.text.strip()
            href = link_tag["href"]
            date_str = date_tag.text.strip().title()  
            date = datetime.strptime(date_str, "%B %d, %Y")

            if start_date and date.date() < start_date:
                continue

            results.append({
                "title": title,
                "url": href[href.find("https://"):] if "/web/" in href else "https://www.hhs.gov" + href,
                "date": date.strftime("%Y-%m-%d")
            })

        except Exception as e:
            continue

    return results
