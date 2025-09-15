# features/categorize.py
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load API key exactly like classify.py
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# Exact labels you gave (spelling & casing matter)
SPECIAL_CALENDAR = "Events"
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
        "medicare/medicaid": "Medicare", 
        "congress": "Congress and the Administration",
        "administration": "Congress and the Administration",
        "health insurance": "Health Insurance",
        "health tech": "Health Tech",
    }
    if label.lower() in aliases:
        return aliases[label.lower()]
    return "Quality and Innovation"


def _build_instructions(allowed_labels):
    return (
        "Choose ONE category for the article title below.\n\n"
        "Allowed categories:\n"
        + "\n".join(f"- {c}" for c in allowed_labels)
        + "\n\nOutput: EXACT label text only. No extra words."
    )

def categorize_article(title: str, is_hearing: bool = False) -> str:
    """
    Return a single category label for an article title.
    ONLY entries with a time (is_hearing=True) may be 'Events'.
    """
    # If it has a time, force 'Events' and skip the model.
    if is_hearing:
        return SPECIAL_CALENDAR

    # Otherwise, do NOT include 'Events' in the allowed set.
    allowed = list(CATEGORIES)  # no SPECIAL_CALENDAR here
    instructions = _build_instructions(allowed)

    try:
        resp = client.chat.completions.create(
            model="gpt-3.5-turbo",
            temperature=0,
            messages=[
                SYSTEM_MESSAGE,
                {"role": "user", "content": f"{instructions}\n\nTitle: {title}"},
            ],
        )
        raw = resp.choices[0].message.content
        label = _normalize(raw)

        # Belt-and-suspenders: if the model still says 'Events', override.
        if label == SPECIAL_CALENDAR:
            return "Quality and Innovation"

        return label
    except Exception:
        return "Quality and Innovation"
