# GET API KEYS
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv
import os


load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ADDEVENT_API_KEY = os.getenv("ADDEVENT_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# get html
def fetch_hearing_html(url):
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch page: {response.status_code}")
    return BeautifulSoup(response.text, "html.parser").get_text()

# parse html
def extract_event_info(page_text):
    prompt = f"""
Extract the following information from the congressional hearing text below:
- Title
- Date (in YYYY-MM-DD format)
- Time (in HH:MM 24-hour format)
- Location (if any)

Hearing Page Text:
{page_text[:4000]}

Respond in valid JSON format:
{{
  "title": "...",
  "date": "YYYY-MM-DD",
  "time": "HH:MM",
  "location": "...",
}}
"""

    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a helpful assistant extracting congressional hearing event details."},
            {"role": "user", "content": prompt}
        ],
        temperature=0
    )

    return response.choices[0].message.content


# add event
def create_event_addevent(data):
    endpoint = "https://api.addevent.com/calevent/v2/events"
    headers = {"Authorization": f"Bearer {ADDEVENT_API_KEY}"}
    
    payload = {
        "datetime_start": data["start"],
        "datetime_end": data["end"],
        "title": data["title"],
        "location": data.get("location", ""),
        "description": data.get("description", ""),
        "timezone": data.get("timezone", "America/New_York")
    }

    response = requests.post(endpoint, json=payload, headers=headers)
    if response.status_code not in (200, 201):
        raise Exception(f"Failed to create event: {response.status_code} — {response.text}")
    return response.json()



