from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_omb_articles(start_date=None):
    url = "https://www.reginfo.gov/public/jsp/EO/eoDashboard.myjsp?agency_cd=0900&agency_nm=HHS&stage_cd=4&from_page=index.jsp&sub_index=0"

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        driver.get(url)
        WebDriverWait(driver, 100).until(EC.presence_of_element_located((By.CLASS_NAME, "generalTxt")))

        soup = BeautifulSoup(driver.page_source, "html.parser")
        tables = soup.select("table.generalTxt")

        results = []

        for table in tables:
            agency_text = table.find("b", string="AGENCY:")
            if not agency_text:
                continue

            agency_cell = agency_text.parent
            agency_name = agency_cell.get_text(strip=True).replace("AGENCY:", "").strip()

            if not agency_name.startswith("HHS-"):
                continue

            title_tag = table.select_one("span.TCJATitle")
            rin_tag = table.select_one("td a[href*='eAgendaViewRule']")
            stage_td = next((td for td in table.find_all("td") if "STAGE:" in td.text), None)
            date_td = next((td for td in table.find_all("td") if "RECEIVED DATE:" in td.text), None)

            if not title_tag or not rin_tag or not date_td or not stage_td:
                continue

            try:
                date_str = date_td.text.split("RECEIVED DATE:")[-1].strip()
                pub_date = datetime.strptime(date_str, "%m/%d/%Y")
            except ValueError:
                continue

            if start_date and pub_date.date() < start_date:
                continue

            stage = stage_td.text.split("STAGE:")[-1].strip()
            title = f"{stage} - {title_tag.text.strip()}"
            article_url = "https://www.reginfo.gov" + rin_tag["href"]

            results.append({
                "title": title,
                "url": article_url,
                "date": pub_date.strftime("%Y-%m-%d")
            })

        return {
            "url": url,
            "articles": results,
        }

    finally:
        driver.quit()
