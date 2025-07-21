from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
import base64
import email
from email.header import decode_header
from email.utils import parseaddr
from bs4 import BeautifulSoup
from datetime import datetime
import re

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def authenticate():
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)
    return build('gmail', 'v1', credentials=creds)

def get_messages(service):
    query = f"is:unread"
    result = service.users().messages().list(userId='me', q=query).execute()
    return result.get('messages', [])

def should_include_link(text, href):
    text = text.strip()
    href = href.strip().lower()

    if not text or len(text) < 4:
        return False

    if len(text) > 50 and not re.search(r'[a-zA-Z]{3,}', text):
        return False

    blocked_text_keywords = [
        "unsubscribe", "update profile", "manage preferences", "view in browser", "privacy"
    ]
    blocked_href_keywords = [
        "govdelivery", "utm_", "track", "unsubscribe", "optout", "t.e2ma.net"
    ]

    if any(k in text.lower() for k in blocked_text_keywords):
        return False
    if any(k in href for k in blocked_href_keywords):
        return False

    return True

def extract_links_from_email(service, msg_id):
    msg = service.users().messages().get(userId='me', id=msg_id, format='raw').execute()
    msg_str = base64.urlsafe_b64decode(msg['raw'].encode('ASCII'))
    mime_msg = email.message_from_bytes(msg_str)

    # Decode subject
    raw_subject = mime_msg.get("Subject", "(No Subject)")
    decoded_parts = decode_header(raw_subject)
    subject = ''.join([
        (part.decode(enc or 'utf-8') if isinstance(part, bytes) else part)
        for part, enc in decoded_parts
    ])

    # Extract sender name
    from_header = mime_msg.get("From", "")
    sender_name, sender_email = parseaddr(from_header)
    sender_display = sender_name or sender_email

    links = []
    for part in mime_msg.walk():
        if part.get_content_type() == "text/html":
            soup = BeautifulSoup(part.get_payload(decode=True), "html.parser")
            for a in soup.find_all('a', href=True):
                text = a.text.strip()
                href = a['href']
                # if not text:
                #     text = a.get("title") or href.split("?")[0].split("/")[-1] or "Untitled Link"
                # if should_include_link(text, href):
                #  links.append({"title": text, "url": href})
                if text:
                  links.append({"title": text, "url": href})
            break

    return f"{sender_display} - {subject}", links