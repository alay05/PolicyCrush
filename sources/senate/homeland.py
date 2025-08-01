import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_home_articles(start_date=None):
    base_url = "https://www.hsgac.senate.gov"
    results = []

    def parse_news(url, tag):
        response = requests.get(url)
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.text, "html.parser")
        blocks = soup.select("div.jet-listing-grid__item")
        items = []

        for block in blocks:
            # URL
            link_tag = block.select_one("a.jet-engine-listing-overlay-link")
            url = link_tag["href"].strip() if link_tag else None
            if not url:
                continue

            # Title
            title_tag = block.select_one("h5.jet-listing-dynamic-field__content")
            title = title_tag.get_text(strip=True).replace("➞", "").strip() if title_tag else None
            if not title:
                continue

            # Date
            month_tag = block.select_one("div.sen-listing-month time")
            day_tag = block.select_one("div.sen-listing-day time")
            if not month_tag or not day_tag:
                continue

            try:
                raw_date = f"{month_tag.text.strip()} {day_tag.text.strip()} {datetime.now().year}"
                pub_date = datetime.strptime(raw_date, "%b %d %Y")
            except ValueError:
                continue

            if start_date and pub_date.date() < start_date:
                continue

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
        blocks = soup.select("div.jet-listing-grid__item")
        items = []

        for block in blocks:
            title_tag = block.select_one("h3.jet-listing-dynamic-field__content a")
            date_tag = block.select_one("div.elementor-element-1c6a5ff .jet-listing-dynamic-field__content")
            time_tag = block.select_one("div.elementor-element-930df5a .jet-listing-dynamic-field__content")

            if not title_tag or not date_tag:
                continue

            try:
                date_str = date_tag.get_text(strip=True)
                time_str = time_tag.get_text(strip=True).lower().replace(" ", "")
                dt = datetime.strptime(date_str + time_str, "%m/%d/%Y%I:%M%p")
            except Exception:
                try:
                    dt = datetime.strptime(date_str, "%m/%d/%Y")
                except ValueError:
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
                "tag": "hearing",
            })

        return items


    results += parse_news("https://www.hsgac.senate.gov/media/majority-news/", "majority")
    results += parse_news("https://www.hsgac.senate.gov/media/minority-news/", "minority")
    results += parse_hearings()

    return {
        "base_url": base_url,
        "articles": results,
    }
