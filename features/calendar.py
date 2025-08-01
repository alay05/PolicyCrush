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


# parse site w/ AI
def extract_event_info(page_text):
    prompt = f"""
Extract the following information from the congressional hearing text below:

Return ONLY raw, valid JSON with the following fields:
- "title" (string): If the full title is longer than 100 characters, summarize it to stay under 100 characters while retaining key information (e.g., names, topics, agencies, bill titles, etc.).
- "date" (YYYY-MM-DD)
- "time" (HH:MM in 24-hour format)
- "location" (string or empty)

DO NOT include any explanation, formatting, markdown, or commentary. ONLY return the JSON object.

Text:
{page_text[:4000]}
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

    response = requests.post(endpoint, json=data, headers=headers, timeout=15)

    if response.status_code not in (200, 201):
        raise Exception(f"Failed to create event: {response.status_code} — {response.text}")
    return response.json()



