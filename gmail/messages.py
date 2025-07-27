from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
import base64
import email
from email.header import decode_header
from email.utils import parseaddr

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

# Authenticates Gmail User
def authenticate():
    flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
    creds = flow.run_local_server(port=0)
    return build('gmail', 'v1', credentials=creds)

# Pulls unread messages
def get_messages(service):
    query = f"is:unread"
    result = service.users().messages().list(userId='me', q=query).execute()
    return result.get('messages', [])

# Formats sender, subject, and content
def extract_html_from_email(service, msg_id):
    msg = service.users().messages().get(userId='me', id=msg_id, format='raw').execute()
    msg_str = base64.urlsafe_b64decode(msg['raw'].encode('ASCII'))
    mime_msg = email.message_from_bytes(msg_str)

    # subject
    raw_subject = mime_msg.get("Subject", "(No Subject)")
    decoded_parts = decode_header(raw_subject)
    subject = ''.join([
        (part.decode(enc or 'utf-8') if isinstance(part, bytes) else part)
        for part, enc in decoded_parts
    ])

    # sender
    from_header = mime_msg.get("From", "")
    sender_name, sender_email = parseaddr(from_header)
    sender_display = sender_name or sender_email

    # html
    for part in mime_msg.walk():
        if part.get_content_type() == "text/html":
            html = part.get_payload(decode=True).decode(errors="replace")
            return f"FROM: {sender_display} \n SUBJECT: {subject}", html

    # returns empty html if none present
    return f"FROM: {sender_display} \n SUBJECT: {subject}", ""