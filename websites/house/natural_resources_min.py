import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_natr_min_articles(start_date=None):
    results = []
    url = "https://democrats-naturalresources.house.gov/media/press-releases"
    response = requests.get(url)
    if response.status_code != 200:
        return results

    soup = BeautifulSoup(response.text, "html.parser")
    press_div = soup.find("div", id="press")
    if not press_div:
        return results

    date_tags = press_div.find_all("span", class_="date black")
    for date_tag in date_tags:
        try:
            pub_date = datetime.strptime(date_tag.text.strip(), "%m.%d.%y").date()
        except:
            continue

        h2_tag = date_tag.find_next_sibling("h2", class_="title")
        if not h2_tag:
            continue

        a_tag = h2_tag.find("a")
        if not a_tag:
            continue

        title = a_tag.text.strip()
        href = a_tag.get("href", "").strip()
        full_url = "https://democrats-naturalresources.house.gov" + href if href.startswith("/") else href

        if start_date and pub_date < start_date:
            continue

        results.append({
            "title": title,
            "url": full_url,
            "date": pub_date.strftime("%Y-%m-%d")
        })

    return results
