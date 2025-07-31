import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_ind_articles(start_date=None):
    base_url = "https://www.indian.senate.gov"
    results = []

    def parse_section(url, tag):
        response = requests.get(url)
        if response.status_code != 200:
            return []

        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.select("div.jet-listing-grid__item")
        items = []

        for article in articles:
            date_tag = article.select_one("div.jet-listing-dynamic-field__content")
            title_tag = article.select_one("div.elementor-heading-title a")

            if not date_tag or not title_tag:
                continue

            try:
                pub_date = datetime.strptime(date_tag.get_text(strip=True), "%B %d, %Y")
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
        hearings = soup.select("div.jet-listing-grid__item")
        items = []

        for hearing in hearings:
            date_tag = hearing.select_one("div.jet-listing-dynamic-field__content")
            title_tag = hearing.select_one("div.elementor-heading-title a")

            if not date_tag or not title_tag:
                continue

            try:
                pub_date = datetime.strptime(date_tag.get_text(strip=True), "%B %d, %Y at %I:%M %p")
            except ValueError:
                try:
                    pub_date = datetime.strptime(date_tag.get_text(strip=True), "%B %d, %Y")
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
    
    results += parse_section(base_url + "/newsroom/republican-news", "majority")
    results += parse_section(base_url + "/newsroom/democratic-news", "minority")
    results += parse_hearings()

    return {
        "base_url": base_url,
        "articles": results,
    }
