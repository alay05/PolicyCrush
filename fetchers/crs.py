import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_crs_articles(start_date=None):
    results = []
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    url = f"https://web.archive.org/web/{timestamp}/https://www.congress.gov/crs-products"

    response = requests.get(url)
    if response.status_code != 200:
        return results

    soup = BeautifulSoup(response.text, "html.parser")
    crs_items = soup.select("div.column-equal p")

    for p in crs_items:
        try:
            link = p.find("a")
            title = p.find("strong")
            text_parts = list(p.stripped_strings)
            
            if not link or not title or len(text_parts) < 2:
                continue

            date_text = text_parts[-1]
            pub_date = datetime.strptime(date_text, "%B %d, %Y")
            if start_date and pub_date.date() < start_date:
                continue

            raw_href = link["href"]
            real_href = raw_href.split("/https://www.congress.gov")[-1]
            full_url = "https://www.congress.gov" + real_href

            results.append({
                "title": title.text.strip(),
                "url": full_url,
                "date": pub_date.strftime("%Y-%m-%d")
            })

        except:
            continue

    return results
