from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_congress_articles(start_date=None):
    url = "https://www.congress.gov/search?q=%7B%22source%22%3A%22legislation%22%7D"

    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        driver.get(url)
        WebDriverWait(driver, 100).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "li.expanded"))
        )

        soup = BeautifulSoup(driver.page_source, "html.parser")
        items = soup.select("li.expanded")

        results = []

        for item in items:
            title_tag = item.select_one("span.result-title")
            link_tag = item.select_one("span.result-heading a")
            latest_action_span = next(
                (span for span in item.select("span.result-item") if "Latest Action:" in span.text), None
            )

            if not title_tag or not link_tag or not latest_action_span:
                continue

            try:
                action_text = latest_action_span.text.strip()
                date_part = action_text.split(" - ")[-1].split()[0]
                pub_date = datetime.strptime(date_part, "%m/%d/%Y")
            except Exception:
                continue

            if start_date and pub_date.date() < start_date:
                continue

            results.append({
                "title": title_tag.text.strip(),
                "url": "https://www.congress.gov" + link_tag["href"],
                "date": pub_date.strftime("%Y-%m-%d")
            })

        return {
            "url": url,
            "articles": results
        }

    finally:
        driver.quit()
