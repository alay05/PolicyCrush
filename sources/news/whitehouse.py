import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_whitehouse_articles(start_date=None):
    results = []
    page = 1
    keep_going = True

    while keep_going and page < 5:
        url = f"https://www.whitehouse.gov/news/page/{page}/"
        response = requests.get(url)
        if response.status_code != 200:
            break

        soup = BeautifulSoup(response.text, "html.parser")
        items = soup.select("div.wp-block-whitehouse-post-template")

        if not items:
            break 

        for item in items:
            title_tag = item.select_one("h2.wp-block-post-title a")
            date_tag = item.select_one("div.wp-block-post-date")

            if not title_tag or not date_tag:
                continue

            try:
                pub_date = datetime.strptime(date_tag.text.strip(), "%B %d, %Y")
            except ValueError:
                continue

            if start_date and pub_date.date() < start_date:
                keep_going = False
                break

            results.append({
                "title": title_tag.text.strip(),
                "url": title_tag["href"],
                "date": pub_date.strftime("%Y-%m-%d")
            })

        page += 1

    return {
        "url": url,
        "articles": results,
    }
