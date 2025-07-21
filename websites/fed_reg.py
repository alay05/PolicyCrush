import requests
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_federal_register_articles(start_date=None):
    results = []
    url = "https://www.federalregister.gov/public-inspection/search?conditions%5Bagencies%5D%5B%5D=agency-for-healthcare-research-and-quality&conditions%5Bagencies%5D%5B%5D=centers-for-medicare-medicaid-services&conditions%5Bagencies%5D%5B%5D=children-and-families-administration&conditions%5Bagencies%5D%5B%5D=defense-department&conditions%5Bagencies%5D%5B%5D=drug-enforcement-administration&conditions%5Bagencies%5D%5B%5D=employment-standards-administration&conditions%5Bagencies%5D%5B%5D=food-and-drug-administration&conditions%5Bagencies%5D%5B%5D=health-and-human-services-department&conditions%5Bagencies%5D%5B%5D=health-resources-and-services-administration&conditions%5Bagencies%5D%5B%5D=internal-revenue-service&conditions%5Bagencies%5D%5B%5D=justice-department&conditions%5Bagencies%5D%5B%5D=national-institutes-of-health&conditions%5Bagencies%5D%5B%5D=occupational-safety-and-health-administration&conditions%5Bagencies%5D%5B%5D=substance-abuse-and-mental-health-services-administration&conditions%5Bagencies%5D%5B%5D=treasury-department&conditions%5Bagencies%5D%5B%5D=centers-for-disease-control-and-prevention"

    response = requests.get(url, headers={
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"
    })

    if response.status_code != 200:
        return results

    soup = BeautifulSoup(response.text, "html.parser")
    articles = soup.select("li.search-result-document")

    for i, article in enumerate(articles):
        try:
            link_tag = article.select_one("div.document-wrapper h5 a")
            meta_div = article.select_one("p.metadata")

            if not link_tag:
                continue
            
            title = link_tag.text.strip()
            url = link_tag["href"]
            
            if not meta_div:
                continue

            meta_text = meta_div.get_text(strip=True)
            if "on" not in meta_text:
                continue

            date_str = meta_text.split("on")[-1].strip().rstrip(".")
            pub_date = datetime.strptime(date_str, "%m/%d/%Y")

            if start_date and pub_date.date() < start_date:
                continue

            results.append({
                "title": title,
                "url": url,
                "date": pub_date.strftime("%Y-%m-%d")
            })          

        except Exception as e:
            continue

    return results
