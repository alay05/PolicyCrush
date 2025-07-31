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
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    )

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    try:
        url = "https://www.cms.gov/priorities/innovation/overview"
        driver.get(url)

        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "ul.cms-evo-unstyled-list.milestone-results")
            )
        )

        soup = BeautifulSoup(driver.page_source, "html.parser")
        items = soup.select("ul.cms-evo-unstyled-list.milestone-results > li")
        
        results = []
        for i, item in enumerate(items):
            try:
                date_div = item.select_one("div.cms-news--desktop-date")
                title_p = item.select_one("div.cms-news--title p")

                if not date_div or not title_p:
                    continue

                # parse the ISO date (e.g. "2025-07-15")
                pub_dt = datetime.strptime(date_div.text.strip(), "%Y-%m-%d")
                print(pub_dt)
                if start_date and pub_dt.date() < start_date:
                    continue

                # find and normalize the "Learn more" link
                link_tag = title_p.find("a", string="Learn more")
                href = ""
                if link_tag:
                    href = link_tag["href"]
                    if not href.startswith("http"):
                        href = "https://www.cms.gov" + href
                    link_tag.extract()

                # clean up the remaining text
                title = title_p.get_text(" ", strip=True)

                results.append({
                    "date":  pub_dt.strftime("%Y-%m-%d"),
                    "title": title,
                    "url":   href
                })
            except Exception:
                continue

        return results

    finally:
        driver.quit()
