import os
from openai import OpenAI
from dotenv import load_dotenv

# Load .env if available
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "You are a strict and detail-oriented editor for a healthcare policy newsletter. "
        "Your job is to filter government-related articles and determine whether they are directly relevant to U.S. healthcare policy." 
        "Only articles related to policy changes, healthcare programs, legislation, regulatory actions, or public health systems should be included."
        "Respond only with YES, MAYBE, or NO."
    )
}


def classify(title):
    prompt = f"""
You are helping curate a healthcare policy newsletter.

This newsletter includes **government-related healthcare news** such as:
- Policy changes or proposals
- Regulatory actions (CMS, HHS, FDA, etc.)
- Legislative or budget updates
- Congressional hearings
- News about Medicare, Medicaid, insurance, hospitals, public health systems, drug pricing, etc.

It does **not include** general entertainment, sports, tech, or unrelated news.

---

Here is the title of the news article:

{title}

---

**Your task**:
Estimate the likelihood that this article is relevant to healthcare policy based on the newsletter's focus.

Respond only with one of the following:
- **YES** - if you are over 70% sure it's relevant
- **MAYBE** - if you are 30-70% sure it's relevant
- **NO** - if you are less than 30% sure it's relevant

Do not explain your reasoning. Only reply: YES, MAYBE, or NO.
"""
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[SYSTEM_MESSAGE, {"role": "user", "content": prompt}],
            temperature=0
        )
        return response.choices[0].message.content.strip().upper()
    except Exception as e:
        return f"ERROR: {e}"