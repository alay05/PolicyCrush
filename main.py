# for local terminal testing

from fetchers.whitehouse import fetch_whitehouse_articles
from fetchers.cms import fetch_cms_articles
from datetime import datetime

BLUE = "\033[36m"
RED = "\033[31m"
BOLD = "\033[1m"
RESET = "\033[0m"

def main():
    input_str = input("\nEnter start date (YYYY-MM-DD), or leave blank for all: ").strip()

    start_date = None
    if input_str:
        try:
            start_date = datetime.strptime(input_str, "%Y-%m-%d").date()
        except ValueError:
            print("[ERROR] Invalid date format. Use YYYY-MM-DD.")
            return

    # Header
    print(f"\n{RED}{BOLD}------------ HEADLINES SINCE {start_date} ------------{RESET}")

    # White House
    wh_articles = fetch_whitehouse_articles(start_date)
    print(f"\n{BLUE}{BOLD}WHITE HOUSE (from www.whitehouse.gov/news):{RESET}")
    for a in wh_articles:
        print(f"\n--> {a['date']} | {a['title']} | {a['url']}")

    # CMS
    cms_articles = fetch_cms_articles(start_date)
    print(f"\n{BLUE}{BOLD}CMS (from www.cms.gov/about-cms/contact/newsroom):{RESET}")
    for a in cms_articles:
        print(f"\n--> {a['date']} | {a['title']} | {a['url']}")

    print(f"\n{BOLD}{RED}DONE")

if __name__ == "__main__":
    main()