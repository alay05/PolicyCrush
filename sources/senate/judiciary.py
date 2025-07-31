import requests
from bs4 import BeautifulSoup
from datetime import datetime
from zoneinfo import ZoneInfo

def fetch_jud_articles(start_date=None):
    base_url = "https://www.judiciary.senate.gov"
    results = []

    def parse_news(url, tag):
        response = requests.get(url)
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.text, "html.parser")
        items = []

        for li in soup.select("li.PageList__item"):
            date_tag = li.select_one("p.Heading--time")
            link_tag = li.select_one("a.ArticleBlockLink")
            title_tag = link_tag.select_one("h2") if link_tag else None

            if not date_tag or not link_tag or not title_tag:
                continue

            try:
                pub_date = datetime.strptime(date_tag.get_text(strip=True), "%m.%d.%Y")
            except ValueError:
                continue

            if start_date and pub_date.date() < start_date:
                continue

            url = link_tag["href"].strip()
            if not url.startswith("http"):
                url = base_url + url

            items.append({
                "title": title_tag.get_text(strip=True),
                "url": url,
                "date": pub_date.date() if pub_date.time().isoformat() == "00:00:00" else pub_date,
                "tag": tag,
            })

        return items

    def parse_hearings():
        url = base_url + "/committee-activity/hearings"
        response = requests.get(url)
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.text, "html.parser")
        items = []

        for div in soup.select("div.LegislationList__item"):
            title_tag = div.select_one("a.LegislationList__title")
            time_tag = div.select_one("div.LegislationList__colDate time")

            if not title_tag or not time_tag:
                continue

            try:
                utc_dt = datetime.strptime(time_tag["datetime"], "%Y-%m-%dT%H:%M:%SZ")
                utc_dt = utc_dt.replace(tzinfo=ZoneInfo("UTC"))
                pub_date = utc_dt.astimezone(ZoneInfo("America/New_York"))
            except ValueError:
                continue

            if start_date and pub_date.date() < start_date:
                continue

            url = title_tag["href"].strip()
            if not url.startswith("http"):
                url = base_url + url

            items.append({
                "title": title_tag.get_text(strip=True),
                "url": url,
                "date": pub_date,
                "tag": "hearing",
            })

        return items

    results += parse_news("https://www.judiciary.senate.gov/press/majority?expanded=true", "majority")
    results += parse_news("https://www.judiciary.senate.gov/press/minority?expanded=true", "minority")
    results += parse_hearings()

    return {
        "base_url": base_url,
        "articles": results,
    }
