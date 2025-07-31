from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_hhs_articles(start_date=None):
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
     
    try:
        url = "https://www.hhs.gov/press-room/index.html"
        driver.get(url)

        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ul.usa-collection"))
        )

        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        items = soup.select("li.usa-collection__item")
        
        results = []

        for i, item in enumerate(items):
            try:
                link_tag = item.select_one("a.usa-link")
                time_tag = item.select_one("time")

                if not link_tag or not time_tag:
                    continue

                title = link_tag.text.strip()
                href = link_tag["href"]
                full_url = href if href.startswith("http") else "https://www.hhs.gov" + href

                date_str = time_tag["datetime"]  # e.g. "2025-07-17T16:15:00-0400"
                pub_date = datetime.fromisoformat(date_str.split("T")[0])

                if start_date and pub_date.date() < start_date:
                    continue

                results.append({
                    "title": title,
                    "url": full_url,
                    "date": pub_date.strftime("%Y-%m-%d")
                })

            except Exception as e:
                continue

        return {
            "url": url,
            "articles": results,
        }

    finally:
        driver.quit()
