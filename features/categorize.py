# features/categorize.py
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load API key exactly like classify.py
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# Exact labels you gave (spelling & casing matter)
SPECIAL_CALENDAR = "Calendar (HEARINGS ONLY)"
CATEGORIES = [
    "Congress and the Administration",
    "Health Insurance",
    "Health Tech",
    "Medicaid",
    "Medicare",
    "Pharmaceuticals and Medical Devices",
    "Quality and Innovation",
]

SYSTEM_MESSAGE = {
    "role": "system",
    "content": (
        "You are a precise taxonomy assistant for a healthcare policy newsletter. "
        "Given an article title, pick exactly ONE category label from the allowed set. "
        "Respond with ONLY the label text, nothing else."
    ),
}

USER_INSTRUCTIONS = (
    "Choose ONE category for the article title below.\n\n"
    "Allowed categories:\n"
    f"- {SPECIAL_CALENDAR}  # (use ONLY for hearings; otherwise pick one of the items below)\n"
    "- Congress and the Administration\n"
    "- Health Insurance\n"
    "- Health Tech\n"
    "- Medicaid\n"
    "- Medicare\n"
    "- Pharmaceuticals and Medical Devices\n"
    "- Quality and Innovation\n\n"
    "Output: EXACT label text only. No extra words."
)

def _normalize(label: str) -> str:
    """Map model output to the exact allowed label; fallback to a catch-all."""
    if not label:
        return "Quality and Innovation"
    label = label.strip()
    # Perfect match first
    if label == SPECIAL_CALENDAR:
        return SPECIAL_CALENDAR
    for c in CATEGORIES:
        if label.lower() == c.lower():
            return c
    # Some light forgiving mapping
    aliases = {
        "pharmaceuticals": "Pharmaceuticals and Medical Devices",
        "devices": "Pharmaceuticals and Medical Devices",
        "pharma": "Pharmaceuticals and Medical Devices",
        "innovation": "Quality and Innovation",
        "quality": "Quality and Innovation",
        "medicare/medicaid": "Medicare",   # prefer a specific bucket if model is vague
        "congress": "Congress and the Administration",
        "administration": "Congress and the Administration",
        "health insurance": "Health Insurance",
        "health tech": "Health Tech",
    }
    if label.lower() in aliases:
        return aliases[label.lower()]
    return "Quality and Innovation"

def categorize_article(title: str, is_hearing: bool = False) -> str:
    """
    Return a single category label for an article title.
    Hearings short-circuit into 'Calendar (HEARINGS ONLY)'.
    """
    if is_hearing:
        return SPECIAL_CALENDAR

    try:
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",  # matching your classify.py choice
            temperature=0,
            messages=[
                SYSTEM_MESSAGE,
                {"role": "user", "content": f"{USER_INSTRUCTIONS}\n\nTitle: {title}"},
            ],
        )
        raw = resp.choices[0].message.content
        return _normalize(raw)
    except Exception:
        # Safe fallback
        return "Quality and Innovation"
