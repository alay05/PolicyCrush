import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_smb_articles(start_date=None):
    base_url = "https://www.sbc.senate.gov"
    results = []

    def parse_news(url, tag):
        response = requests.get(url)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.select("table.table.recordList tbody tr")
        items = []

        for row in rows:
            date_tag = row.select_one("td.recordListDate")
            link_tag = row.select_one("td.recordListTitle a")

            if not date_tag or not link_tag:
                continue

            try:
                pub_date = datetime.strptime(date_tag.get_text(strip=True), "%m/%d/%y")
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
                "tag": tag,
            })

        return items

    def parse_hearings():
        url = "https://www.sbc.senate.gov/public/index.cfm/hearings"
        response = requests.get(url)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.select("table.table.recordList tbody tr")
        items = []

        for row in rows:
            date_tag = row.select_one("td.recordListDate")
            time_tag = row.select_one("td.recordListTime")
            link_tag = row.select_one("td.recordListTitle a")

            if not date_tag or not link_tag:
                continue

            date_str = date_tag.get_text(strip=True)
            time_str = time_tag.get_text(strip=True) if time_tag else "12:00 AM"
            dt_str = f"{date_str} {time_str}"

            try:
                pub_date = datetime.strptime(dt_str, "%m/%d/%y %I:%M %p")
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
                "date": pub_date,
                "tag": "hearing",
            })

        return items

    results += parse_news("https://www.sbc.senate.gov/public/index.cfm/republicanpressreleases", "majority")
    results += parse_news("https://www.sbc.senate.gov/public/index.cfm/democraticpressreleases", "minority")
    results += parse_hearings()

    return {
        "base_url": base_url,
        "articles": results,
    }
