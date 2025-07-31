import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_help_articles(start_date=None):
    base_url = "https://www.help.senate.gov"
    results = []

    def parse_press(url, tag):
        response = requests.get(url)
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.select("div.PressBrowser__itemRow")
        items = []

        for row in rows:
            date_tag = row.select_one("div.PressBrowser__date time")
            link_tag = row.select_one("div.col-12.col-md a")

            if not date_tag or not link_tag:
                continue

            try:
                pub_date = datetime.strptime(date_tag["datetime"], "%B %d, %Y")
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
        url = base_url + "/hearings"
        response = requests.get(url)
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.select("div.LegislationList__item")
        items = []

        for row in rows:
            title_tag = row.select_one("a.LegislationList__link")
            date_tag = row.select_one("div.LegislationList__dateCol time")

            if not title_tag or not date_tag:
                continue

            try:
                date_str = date_tag["datetime"].strip()
                full_text = date_tag.get_text(separator="\n", strip=True)
                time_str = None
                for line in full_text.split("\n"):
                    if ":" in line and ("am" in line.lower() or "pm" in line.lower()):
                        time_str = line.strip()
                        break

                if time_str:
                    datetime_str = f"{date_str} {time_str}"
                    pub_date = datetime.strptime(datetime_str, "%B %d, %Y %I:%M%p")
                else:
                    pub_date = datetime.strptime(date_str, "%B %d, %Y")

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
                "tag": "hearing",
            })

        return items
    
    results += parse_press("https://www.help.senate.gov/chair/newsroom/press?expanded=false", "majority")
    results += parse_press("https://www.help.senate.gov/ranking/newsroom/press?expanded=false", "minority")
    results += parse_hearings()

    return {
        "base_url": base_url,
        "articles": results,
    }
