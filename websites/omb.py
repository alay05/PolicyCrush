from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from datetime import datetime

def fetch_omb_articles(start_date=None):
    print("Opening page...")

    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36")
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        url = "https://www.reginfo.gov/public/jsp/EO/eoDashboard.myjsp?agency_cd=0900&agency_nm=HHS&stage_cd=6&from_page=index.jsp&sub_index=0"
        driver.get(url)

        # Wait a moment for frames to load
        WebDriverWait(driver, 10).until(lambda d: len(d.find_elements(By.TAG_NAME, "iframe")) > 0)

        # Try switching into the frame that contains the eoList
        found = False
        for frame in driver.find_elements(By.TAG_NAME, "iframe"):
            driver.switch_to.default_content()
            driver.switch_to.frame(frame)
            if "eoList" in driver.page_source:
                found = True
                break

        if not found:
            raise Exception("Could not find frame containing 'eoList' table")

        # Wait for table to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "eoList"))
        )

        print("Page loaded. Parsing...")
        soup = BeautifulSoup(driver.page_source, "html.parser")
        results = []

        rows = soup.select("#eoList td[width='35%']:nth-of-type(1)")
        print(f"Found {len(rows)} candidate rows.")

        for row in rows:
            try:
                agency_text = row.get_text(strip=True)
                if not agency_text or "AGENCY:" not in agency_text:
                    continue

                rin_link = row.find_next_sibling("td").find("a", href=True)
                rin = rin_link.text.strip()
                detail_url = "https://www.reginfo.gov" + rin_link["href"]

                title_row = row.find_parent("tr").find_next_sibling("tr")
                title_span = title_row.find("span", class_="TCJATitle")
                title = title_span.get_text(strip=True) if title_span else "Untitled"

                received_row = title_row.find_next_sibling("tr")
                received_date = None

                if received_row:
                    date_cells = received_row.find_all("td")
                    for idx, td in enumerate(date_cells):
                        if "RECEIVED DATE" in td.text:
                            date_str = date_cells[idx + 1].get_text(strip=True)
                            received_date = datetime.strptime(date_str, "%m/%d/%Y").date()
                            break

                if start_date and received_date and received_date < start_date:
                    continue

                results.append({
                    "title": f"{title} ({rin})",
                    "url": detail_url,
                    "date": received_date.strftime("%Y-%m-%d") if received_date else "N/A"
                })

            except Exception as e:
                print(f"Skipping row due to error: {e}")
                continue

        print(f"Finished. Extracted {len(results)} articles.")
        return results

    finally:
        driver.quit()
