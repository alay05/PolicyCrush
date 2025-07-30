import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_age_articles(start_date=None):
    base_url = "https://www.aging.senate.gov"
    results = []

    def contains_accented_chars(text):
        return any(char in text for char in "áéíóúñÁÉÍÓÚÑ")

    def parse_news(url):
        response = requests.get(url)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        rows = soup.select("div.PressBrowser__itemRow")
        items = []

        for row in rows:
            date_tag = row.select_one("time")
            link_tag = row.select_one("a")

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

            # remove spanish (not foolproof, but works)
            if contains_accented_chars(title):
                continue
            spanish_keywords = ["aviso", "el presidente", "la miembro", "/press-releases/aviso-"]
            if any(keyword in title.lower() or keyword in url.lower() for keyword in spanish_keywords):
                continue

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
        blocks = soup.select("div.LegislationList__item")
        items = []

        for block in blocks:
            title_tag = block.select_one("a.LegislationList__link")
            time_tag = block.select_one("div.col-12.col-md-auto time")

            if not title_tag or not time_tag:
                continue

            time_lines = [line.strip() for line in time_tag.get_text(separator="\n").splitlines() if line.strip()]
            if len(time_lines) < 2:
                continue

            try:
                date_str = time_lines[0]
                time_str = time_lines[1].lower().replace("am", "AM").replace("pm", "PM")
                dt = datetime.strptime(f"{date_str} {time_str}", "%m/%d/%y %I:%M%p")
                dt = dt.replace(year=2000 + int(date_str.split('/')[2]))
            except Exception:
                continue

            if start_date and dt.date() < start_date:
                continue

            title = title_tag.get_text(strip=True)
            url = title_tag["href"].strip()
            if not url.startswith("http"):
                url = base_url + url

            items.append({
                "title": title,
                "url": url,
                "date": dt,
            })

        return items

    results += parse_news(base_url + "/press-room/majority?expanded=false")
    results += parse_news(base_url + "/press-room/minority?expanded=false")
    results += parse_hearings()

    return results
