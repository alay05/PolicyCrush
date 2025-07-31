import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_vet_articles(start_date=None):
    base_url = "https://www.veterans.senate.gov"
    results = []

    def parse_news(url, tag):
        response = requests.get(url)
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.text, "html.parser")
        items = []

        for article in soup.select("div.element"):
            date_tag = article.select_one(".post-media-list-date")
            title_tag = article.select_one(".post-media-list-title")
            link_tag = article.select_one("a.media-list-body-link")

            if not date_tag or not title_tag or not link_tag:
                continue

            try:
                pub_date = datetime.strptime(date_tag.text.strip(), "%B %d, %Y")
            except ValueError:
                continue

            if start_date and pub_date.date() < start_date:
                continue

            title = title_tag.get_text(strip=True)
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
        url = "https://www.veterans.senate.gov/hearings"
        response = requests.get(url)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        blocks = soup.select("div.hearing-list-item")
        items = []

        for block in blocks:
            title_tag = block.select_one("div.hearing-list-title")
            link_tag = block.select_one("a")
            datetime_tag = block.select_one("span.hearing-list-datetime")

            if not title_tag or not link_tag or not datetime_tag:
                continue

            try:
                parts = list(datetime_tag.stripped_strings)
                if len(parts) < 2:
                    continue

                month_day = parts[0].strip()
                time_str = parts[1].strip().upper().replace(" ", "")
                full_date_str = f"{month_day} 2025 {time_str}"
                pub_date = datetime.strptime(full_date_str, "%b %d %Y %I:%M%p")
            except Exception:
                continue

            if start_date and pub_date.date() < start_date:
                continue

            title = title_tag.get_text(strip=True)
            url = link_tag["href"].strip()
            if not url.startswith("http"):
                url = "https://www.veterans.senate.gov" + url

            items.append({
                "title": title,
                "url": url,
                "date": pub_date,
                "tag": "hearing",
            })

        return items

    results += parse_news("https://www.veterans.senate.gov/majority-news", "majority")
    results += parse_news("https://www.veterans.senate.gov/minority-news", "minority")
    results += parse_hearings()

    return {
        "base_url": base_url,
        "articles": results,
    }
