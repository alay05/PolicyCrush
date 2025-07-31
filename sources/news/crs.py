from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_crs_articles(start_date=None):
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        url = "https://www.congress.gov/crs-products"
        driver.get(url)  
      
        WebDriverWait(driver, 10).until(
          EC.presence_of_element_located((By.CLASS_NAME, "column-equal"))
        )
        
        soup = BeautifulSoup(driver.page_source, "html.parser")

        containers = soup.select("div.column-equal")

        # Look for the one containing the 'Recent' header
        recent_div = None
        for div in containers:
            if div.find("h2") and div.find("h2").text.strip() == "Recent":
                recent_div = div
                break

        if not recent_div:
            return []

        p_tags = recent_div.find_all("p")

        results = []

        for p in p_tags:
            try:
                link = p.find("a")
                title = p.find("strong")
                parts = list(p.stripped_strings)
               
                if not link or not title or len(parts) < 2:
                    continue

                date_text = parts[-1].strip()
                pub_date = datetime.strptime(date_text, "%B %d, %Y")
                if start_date and pub_date.date() < start_date:
                    continue

                results.append({
                    "title": title.text.strip(),
                    "url": "https://www.congress.gov" + link["href"],
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
