from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_cms_inov_articles(start_date=None):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        url = "https://www.cms.gov/priorities/innovation/models/recent-milestones-updates"
        driver.get(url)

        WebDriverWait(driver, 100).until(
            EC.presence_of_element_located((By.CLASS_NAME, "milestone-updates__results"))
        )

        soup = BeautifulSoup(driver.page_source, "html.parser")
        items = soup.select("ul.milestone-updates__results > li.ds-u-display--flex")

        results = []

        for item in items:
            try:
                date_tag = item.select_one(".cms-news--desktop-date")
                title_tag = item.select_one(".cms-news--title p")
                link_tag = item.select_one(".cms-news--title a")

                if not (date_tag and title_tag and link_tag):
                    continue

                pub_date = datetime.strptime(date_tag.text.strip(), "%Y-%m-%d")
                if start_date and pub_date.date() < start_date:
                    continue

                results.append({
                    "title": title_tag.text.strip(),
                    "url": link_tag["href"],
                    "date": pub_date.strftime("%Y-%m-%d"),
                })

            except Exception as e:
                continue

        return {
            "url": url,
            "articles": results,
        }

    finally:
        driver.quit()
