import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_appr_articles(start_date=None):
    base_url = "https://www.appropriations.senate.gov"
    results = []

    def parse_news(url):
        response = requests.get(url)
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.select("table.table tbody tr")
        items = []

        for row in rows:
            date_tag = row.select_one("td.date time")
            link_tag = row.select_one("td a")

            if not date_tag or not link_tag:
                continue

            try:
                pub_date = datetime.strptime(date_tag["datetime"], "%Y-%m-%d")
            except ValueError:
                continue

            if start_date and pub_date.date() < start_date:
                continue

            title = link_tag.get_text(strip=True)
            url = link_tag["href"].strip()
            if not url.startswith("http"):
                url = base_url + url

            items.append({
                "title": title,
                "url": url,
                "date": pub_date.date() if pub_date.time().isoformat() == "00:00:00" else pub_date,
            })

        return items

    def parse_hearings():
        url = base_url + "/hearings"
        response = requests.get(url)
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.select("tr.vevent")
        items = []

        for row in rows:
            title_tag = row.select_one("a.url.summary")
            date_tag = row.select_one("time.dtstart")

            if not title_tag or not date_tag:
                continue

            try:
                pub_date = datetime.strptime(date_tag["datetime"], "%Y-%m-%dT%H:%M")
            except ValueError:
                continue

            if start_date and pub_date.date() < start_date:
                continue

            title = title_tag.get_text(strip=True)
            url = title_tag["href"].strip()
            if not url.startswith("http"):
                url = base_url + url

            items.append({
                "title": title,
                "url": url,
                "date": pub_date,
            })

        return items

    # Majority News
    results += parse_news("https://www.appropriations.senate.gov/news/majority/table")
    # Minority News
    results += parse_news("https://www.appropriations.senate.gov/news/minority/table")
    # Hearings
    results += parse_hearings()

    return results
