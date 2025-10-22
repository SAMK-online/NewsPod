#!/usr/bin/env python3
"""Debug the parsing directly."""

import re
import base64
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from bs4 import BeautifulSoup

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def extract_text_from_html(html_content: str) -> str:
    """Extract clean text from HTML content."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        for script in soup(["script", "style"]):
            script.decompose()
        text = soup.get_text()
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        return text
    except Exception as e:
        return html_content

token_file = 'token.json'
creds = Credentials.from_authorized_user_file(token_file, SCOPES)
service = build('gmail', 'v1', credentials=creds)

results = service.users().messages().list(userId='me', q='from:tldr', maxResults=1).execute()
messages = results.get('messages', [])

msg = service.users().messages().get(userId='me', id=messages[0]['id']).execute()

def extract_html_part(part):
    if part.get('mimeType') == 'text/html':
        if 'data' in part.get('body', {}):
            return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
    if part.get('mimeType') == 'text/plain':
        if 'data' in part.get('body', {}):
            return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
    if 'parts' in part:
        for subpart in part['parts']:
            result = extract_html_part(subpart)
            if result:
                return result
    return None

body = extract_html_part(msg['payload'])
clean_text = extract_text_from_html(body)

# Clean up
clean_text = re.sub(r'‌', '', clean_text)
clean_text = re.sub(r' +', ' ', clean_text)

lines = clean_text.split('\n')

print(f"Total lines: {len(lines)}\n")
print("=" * 80)

headline_pattern = r'^([A-Z][A-Z\s&\',AI-]+)\s*\((\d+)\s+MINUTE\s+READ\)\s*\[\d+\]'
stories = []

i = 0
while i < len(lines) and len(stories) < 5:
    line = lines[i].strip()
    match = re.match(headline_pattern, line)

    if match:
        headline = match.group(1).strip()
        print(f"\n✅ Found headline at line {i}: {headline}")

        # Collect content
        content_lines = []
        j = i + 1
        while j < len(lines) and len(content_lines) < 10:
            next_line = lines[j].strip()

            if re.match(headline_pattern, next_line):
                print(f"  Stopped at next headline (line {j})")
                break
            if re.match(r'^[🚀🧠💼📱🎯🔥]+\s*$', next_line):
                print(f"  Stopped at emoji marker (line {j})")
                break
            if re.match(r'^[A-Z\s&]+$', next_line) and len(next_line) > 20:
                print(f"  Stopped at section header (line {j})")
                break

            if next_line and len(next_line) > 20:
                content_lines.append(next_line)
                if len(content_lines) <= 2:
                    print(f"  Added content: {next_line[:60]}...")

            j += 1

        print(f"  Collected {len(content_lines)} content lines")

        if content_lines:
            stories.append({"headline": headline, "content": ' '.join(content_lines)[:200]})
            print(f"  ✅ Added story #{len(stories)}")
            i = j
        else:
            print(f"  ⚠️  No content, skipping")
            i += 1
    else:
        i += 1

print("\n" + "=" * 80)
print(f"\n📊 FINAL: Extracted {len(stories)} stories\n")

for i, story in enumerate(stories, 1):
    print(f"{i}. {story['headline']}")
    print(f"   Content: {story['content'][:100]}...")
