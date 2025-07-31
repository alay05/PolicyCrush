# Use this file for testing article scrapers. Outputs article results to the terminal.

from datetime import datetime
from websites.senate.veterans import fetch_vet_articles

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

    print(f"\n{RED}{BOLD}------------ HEADLINES SINCE {start_date} ------------{RESET}")
    articles = fetch_vet_articles(start_date)
    print(f"\n{BLUE}{BOLD}Articles:{RESET}")
    for a in articles:
        print(f"\n--> {a['date']} | {a['title']} | {a['url']} \n{BOLD}{a['tag']}{RESET}")
        # print(f"\n--> {a['date']} | {a['title']} | {a['url']}")


    print(f"\n{BOLD}{RED}DONE")

if __name__ == "__main__":
    main()