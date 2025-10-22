from typing import Dict, List, Optional
import pathlib
import wave
import re
from urllib.parse import urlparse
from datetime import datetime, timedelta
import base64
import json
import time

from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools import ToolContext
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import html2text
from bs4 import BeautifulSoup
import yfinance as yf

class NewsletterStory(BaseModel):
    """A single news story extracted from a newsletter."""
    newsletter_name: str = Field(description="Name of the newsletter source (e.g., 'Morning Brew', 'The Hustle')")
    newsletter_sender: str = Field(description="Email sender of the newsletter")
    story_title: str = Field(description="Title or headline of the story")
    company: str = Field(description="Company name associated with the story (e.g., 'Nvidia', 'OpenAI'). Use 'N/A' if not applicable.")
    ticker: str = Field(description="Stock ticker for the company (e.g., 'NVDA'). Use 'N/A' if private or not found.")
    summary: str = Field(description="A brief, one-sentence summary of the news story.")
    why_it_matters: str = Field(description="A concise explanation of the story's significance or impact.")
    financial_context: str = Field(description="Current stock price and change, e.g., '$950.00 (+1.5%)'. Use 'No financial data' if not applicable.")
    received_date: str = Field(description="Date when the newsletter was received")
    process_log: str = Field(description="Processing notes about how this story was extracted")

class NewsletterReport(BaseModel):
    """A structured report of newsletter-based news."""
    title: str = Field(default="Newsletter News Report", description="The main title of the report.")
    report_summary: str = Field(description="A brief, high-level summary of the key findings from newsletters.")
    stories: List[NewsletterStory] = Field(description="A list of the individual news stories found in newsletters.")
    newsletters_processed: List[str] = Field(description="List of newsletter names that were processed")
    total_newsletters: int = Field(description="Total number of newsletters processed")

# Gmail API configuration
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
NEWSLETTER_SENDERS = [
    'morningbrew.com', 'thehustle.co', 'axios.com', 'techcrunch.com',
    'venturebeat.com', 'theverge.com', 'arstechnica.com', 'wired.com',
    'bloomberg.com', 'reuters.com', 'wsj.com', 'ft.com', 'cnn.com',
    'bbc.com', 'npr.org', 'nytimes.com', 'washingtonpost.com',
    'theguardian.com', 'forbes.com', 'businessinsider.com', 'cnbc.com',
    'marketwatch.com', 'yahoo.com', 'msn.com', 'tldr.tech', 'tldrnewsletter.com'
]

def get_today_date():
    """Get today's date in the format required by Gmail API."""
    try:
        # Get current date
        today = datetime.now()
        
        # Format for Gmail API (YYYY/MM/DD)
        formatted_date = today.strftime('%Y/%m/%d')
        
        # Also try alternative formats in case Gmail API is picky
        alt_formats = [
            today.strftime('%Y/%m/%d'),
            today.strftime('%Y-%m-%d'),
            today.strftime('%Y%m%d')
        ]
        
        return {
            "status": "success",
            "primary_date": formatted_date,
            "alt_dates": alt_formats,
            "raw_date": today.isoformat()
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to get date: {str(e)}"
        }

def get_gmail_service():
    """Initialize Gmail API service with OAuth2 authentication."""
    creds = None
    token_file = 'token.json'
    credentials_file = 'credentials.json'
    
    # Load existing credentials
    if pathlib.Path(token_file).exists():
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    
    # If no valid credentials, request authorization
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not pathlib.Path(credentials_file).exists():
                return {"status": "error", "message": "credentials.json file not found. Please download it from Google Cloud Console."}
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for next run
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
    
    try:
        service = build('gmail', 'v1', credentials=creds)
        return {"status": "success", "service": service}
    except Exception as e:
        return {"status": "error", "message": f"Failed to initialize Gmail service: {str(e)}"}

def extract_html_part(part):
    """Recursively extract HTML content from MIME parts."""
    if part.get('mimeType') == 'text/html':
        if 'data' in part.get('body', {}):
            return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
    elif part.get('mimeType') == 'text/plain':
        if 'data' in part.get('body', {}):
            return base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
    
    # Check subparts recursively
    if 'parts' in part:
        for subpart in part['parts']:
            html_content = extract_html_part(subpart)
            if html_content:
                return html_content
    
    return None

def extract_text_from_html(html_content: str) -> str:
    """Extract clean text from HTML content, preserving line breaks."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()

        # Get text with separator to preserve structure
        text = soup.get_text(separator='\n')

        # Clean up excessive blank lines but preserve single line breaks
        lines = [line.strip() for line in text.splitlines()]
        # Remove excessive consecutive blank lines
        cleaned_lines = []
        prev_blank = False
        for line in lines:
            if line:
                cleaned_lines.append(line)
                prev_blank = False
            elif not prev_blank:
                cleaned_lines.append('')
                prev_blank = True

        return '\n'.join(cleaned_lines)
    except Exception as e:
        return html_content  # Return original if parsing fails

def is_valid_newsletter(sender: str, subject: str, content: str, headers: List[Dict] = None) -> bool:
    """Check if an email is a valid newsletter (not promotional/webinar)."""
    sender_lower = sender.lower()
    subject_lower = subject.lower()
    content_lower = content.lower()

    # Check for List-ID header (present in almost all newsletters)
    if headers:
        list_id = next((h['value'] for h in headers if h['name'] == 'List-ID'), None)
        if list_id:
            return True  # If List-ID exists, it's likely a newsletter

    # Check if it's from a known newsletter domain - if yes, auto-accept
    is_newsletter_domain = any(domain in sender_lower for domain in NEWSLETTER_SENDERS)
    if is_newsletter_domain:
        return True  # Trust known newsletter sources

    # For unknown senders, be more selective
    # Exclude obvious promotional keywords (reduced list)
    promotional_keywords = [
        'webinar registration', 'join our webinar', 'register now', 'limited time offer',
        'exclusive offer', 'claim your discount', 'act now', 'hurry',
        'hackathon registration', 'event registration', 'rsvp now'
    ]

    # Newsletter indicators
    newsletter_keywords = [
        'newsletter', 'daily', 'weekly', 'digest', 'roundup', 'briefing',
        'news', 'report', 'summary', 'recap', 'update', 'bulletin'
    ]

    # Check if it contains strong promotional content (subject only for unknown senders)
    is_promotional = any(keyword in subject_lower for keyword in promotional_keywords)

    # Check if it looks like a newsletter
    looks_like_newsletter = any(keyword in subject_lower for keyword in newsletter_keywords)

    # Special case for TLDR newsletters - always valid
    is_tldr = 'tldr' in sender_lower or 'tldr' in subject_lower
    if is_tldr:
        return True

    # It's a valid newsletter if it looks like a newsletter and is not strongly promotional
    return looks_like_newsletter and not is_promotional

def parse_newsletter_content(email_content: str, sender: str, subject: str) -> List[Dict]:
    """Parse newsletter content to extract individual stories."""
    stories = []

    try:
        # Extract text from HTML if needed
        clean_text = extract_text_from_html(email_content)

        # For TLDR newsletters, parse the structured format BEFORE normalizing whitespace
        # TLDR format: "ALL CAPS HEADLINE (X MINUTE READ) [link] \n Content here..."
        if 'tldr' in sender.lower():
            # Clean up zero-width chars but preserve newlines
            clean_text = re.sub(r'‌', '', clean_text)  # Remove zero-width chars
            clean_text = re.sub(r' +', ' ', clean_text)  # Multiple spaces to single space

            # Split text into lines first to preserve structure
            lines = clean_text.split('\n')

            i = 0
            while i < len(lines) and len(stories) < 5:
                line = lines[i].strip()

                # Look for headline pattern: ALL CAPS with (X MINUTE READ) and [link]
                # Example: "CHATGPT ATLAS (4 MINUTE READ) [5]"
                headline_pattern = r'^([A-Z][A-Z\s&\',AI-]+)\s*\((\d+)\s+MINUTE\s+READ\)\s*\[\d+\]'
                match = re.match(headline_pattern, line)

                if match:
                    headline = match.group(1).strip()
                    read_time = match.group(2)

                    # Collect content from following lines until next headline or empty lines
                    content_lines = []
                    j = i + 1
                    while j < len(lines) and len(content_lines) < 10:  # Limit content lines
                        next_line = lines[j].strip()

                        # Stop at next headline or section marker
                        if re.match(headline_pattern, next_line):
                            break
                        if re.match(r'^[🚀🧠💼📱🎯🔥]+\s*$', next_line):  # Emoji section markers
                            break
                        if re.match(r'^[A-Z\s&]+$', next_line) and len(next_line) > 20:  # Section headers
                            break

                        if next_line and len(next_line) > 20:  # Skip very short lines
                            content_lines.append(next_line)

                        j += 1

                    if content_lines:
                        content = ' '.join(content_lines)

                        # Extract first 2-3 sentences for summary
                        sentences = re.split(r'[.!?]\s+', content)
                        summary = '. '.join(sentences[:3])
                        if summary and not summary.endswith('.'):
                            summary += '.'

                        # Extract company names
                        company_patterns = [
                            r'\b(Google|Amazon|Microsoft|Apple|Meta|OpenAI|Anthropic|Tesla|Nvidia|AMD|Intel|AWS|DeepSeek|ChatGPT)\b',
                            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\s+(?:announced|launched|released|unveiled|introduced|revealed)',
                            r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\'s\s+',
                        ]

                        company = "N/A"
                        for pattern in company_patterns:
                            company_match = re.search(pattern, content)
                            if company_match:
                                company = company_match.group(1)
                                break

                        stories.append({
                            "title": headline[:200],
                            "content": summary[:1000] if summary else content[:1000],
                            "company": company,
                            "newsletter": sender,
                            "subject": subject
                        })
                        i = j  # Skip to where we left off
                    else:
                        # No content found for this headline, move to next line
                        i += 1
                else:
                    i += 1

        else:
            # Generic parsing for other newsletters
            # Normalize whitespace for non-TLDR newsletters
            clean_text = re.sub(r'\s+', ' ', clean_text)
            clean_text = re.sub(r'\s*‌\s*', ' ', clean_text)

            # Split on paragraph breaks and bullet points
            story_sections = re.split(r'(?:\n\s*\n|[•·▪▫]\s+|\d+\.\s+)', clean_text)

            for section in story_sections:
                section = section.strip()
                if len(section) < 100:  # Skip short sections
                    continue

                lines = [l.strip() for l in section.split('.') if l.strip()]
                title = lines[0][:200] if lines else "Untitled Story"

                # Look for company mentions
                company_match = re.search(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})\b', section)
                company = company_match.group(1) if company_match else "N/A"

                stories.append({
                    "title": title,
                    "content": section[:1000],
                    "company": company,
                    "newsletter": sender,
                    "subject": subject
                })

                if len(stories) >= 5:
                    break

        return stories if stories else [{
            "title": subject,
            "content": clean_text[:500],
            "company": "N/A",
            "newsletter": sender,
            "subject": subject
        }]

    except Exception as e:
        return [{"title": "Parse Error", "content": f"Failed to parse newsletter: {str(e)}", "company": "N/A", "newsletter": sender, "subject": subject}]

def test_gmail_connection(tool_context: ToolContext) -> Dict[str, any]:
    """Test Gmail API connection and get basic inbox info."""
    try:
        # Initialize Gmail service
        gmail_result = get_gmail_service()
        if gmail_result["status"] != "success":
            return gmail_result
        
        service = gmail_result["service"]
        
        # Get user profile
        profile = service.users().getProfile(userId='me').execute()
        email = profile.get('emailAddress', 'Unknown')
        
        # Get today's date
        today = datetime.now().strftime('%Y/%m/%d')
        
        # Get recent emails (last 10)
        results = service.users().messages().list(userId='me', maxResults=10).execute()
        messages = results.get('messages', [])
        
        recent_emails = []
        for message in messages[:5]:  # Just get first 5 for testing
            try:
                msg = service.users().messages().get(userId='me', id=message['id']).execute()
                headers = msg['payload'].get('headers', [])
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
                date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')
                
                recent_emails.append({
                    "subject": subject,
                    "sender": sender,
                    "date": date
                })
            except Exception as e:
                continue
        
        return {
            "status": "success",
            "email": email,
            "today_date": today,
            "recent_emails": recent_emails,
            "total_recent": len(messages)
        }
        
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Failed to test Gmail connection: {str(e)}"
        }

def fetch_newsletters_from_inbox(tool_context: ToolContext) -> Dict[str, any]:
    """Fetch newsletters from Gmail inbox for the current day."""
    newsletters = []
    process_log = []
    
    try:
        # Initialize Gmail service
        gmail_result = get_gmail_service()
        if gmail_result["status"] != "success":
            process_log.append(f"Gmail service error: {gmail_result.get('message', 'Unknown error')}")
            return {
                "status": "error",
                "message": gmail_result.get('message', 'Unknown error'),
                "newsletters": [],
                "process_log": process_log,
                "total_processed": 0
            }
        
        service = gmail_result["service"]
        
        # Get today's date using our dedicated function
        date_result = get_today_date()
        if date_result["status"] != "success":
            return {
                "status": "error",
                "message": f"Failed to get date: {date_result['message']}",
                "newsletters": [],
                "process_log": [f"Date error: {date_result['message']}"],
                "total_processed": 0
            }
        
        today = date_result["primary_date"]
        query = f'newer_than:1d'
        
        # First try: Search for emails from known newsletter domains
        sender_query = ' OR '.join([f'from:{sender}' for sender in NEWSLETTER_SENDERS])
        query_with_senders = f'{query} AND ({sender_query})'
        
        # Search for emails
        results = service.users().messages().list(userId='me', q=query_with_senders, maxResults=50).execute()
        messages = results.get('messages', [])
        
        process_log.append(f"Found {len(messages)} emails from known newsletter domains")
        
        # If no emails found, try broader search for newsletter-like emails
        if len(messages) == 0:
            process_log.append("No emails from known domains, trying broader search...")
            # Search for emails that might be newsletters (contain "newsletter", "daily", "weekly", etc.)
            broader_query = f'{query} AND (subject:newsletter OR subject:daily OR subject:weekly OR subject:digest OR subject:roundup OR subject:briefing OR from:tldr OR subject:tldr)'
            results = service.users().messages().list(userId='me', q=broader_query, maxResults=50).execute()
            messages = results.get('messages', [])
            process_log.append(f"Found {len(messages)} emails from broader search")
        
        # If still no emails, try even broader search
        if len(messages) == 0:
            process_log.append("Still no emails, trying even broader search...")
            # Just search for recent emails and filter manually
            results = service.users().messages().list(userId='me', q=query, maxResults=100).execute()
            messages = results.get('messages', [])
            process_log.append(f"Found {len(messages)} total recent emails to filter manually")

        # Final count after all search attempts
        process_log.append(f"Total messages to process: {len(messages)}")
        
        for message in messages:
            try:
                # Get full message
                msg = service.users().messages().get(userId='me', id=message['id']).execute()
                
                headers = msg['payload'].get('headers', [])
                subject = next((h['value'] for h in headers if h['name'] == 'Subject'), 'No Subject')
                sender = next((h['value'] for h in headers if h['name'] == 'From'), 'Unknown Sender')
                date = next((h['value'] for h in headers if h['name'] == 'Date'), 'Unknown Date')
                
                # Extract email body using recursive function
                body = extract_html_part(msg['payload']) or ""
                
                # Check if this is a valid newsletter (not promotional)
                is_valid = is_valid_newsletter(sender, subject, body, headers)
                process_log.append(f"Email from {sender}: '{subject}' - Valid: {is_valid}")
                
                if not is_valid:
                    process_log.append(f"Skipped promotional email from {sender}: {subject}")
                    continue
                
                # Parse newsletter content
                stories = parse_newsletter_content(body, sender, subject)
                
                newsletters.append({
                    "sender": sender,
                    "subject": subject,
                    "date": date,
                    "stories": stories
                })
                
                process_log.append(f"Processed newsletter from {sender}: {len(stories)} stories found")
                
            except Exception as e:
                process_log.append(f"Error processing message {message['id']}: {str(e)}")
                continue
        
        return {
            "status": "success",
            "newsletters": newsletters,
            "process_log": process_log,
            "total_processed": len(newsletters)
        }
        
    except Exception as e:
        return {
            "status": "error", 
            "message": f"Failed to fetch newsletters: {str(e)}",
            "newsletters": [],
            "process_log": [f"Error: {str(e)}"],
            "total_processed": 0
        }

def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
    """Helper function to save audio data as a wave file"""
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)
        

async def generate_podcast_audio(podcast_script: str, tool_context: ToolContext, filename: str = "'ai_today_podcast") -> Dict[str, str]:
    """
    Generates audio from a podcast script using Gemini API and saves it as a WAV file.
    Includes retry logic for handling API overload errors.

    Args:
        podcast_script: The conversational script to be converted to audio.
        tool_context: The ADK tool context.
        filename: Base filename for the audio file (without extension).

    Returns:
        Dictionary with status and file information.
    """
    max_retries = 3
    retry_delay = 5  # seconds

    for attempt in range(max_retries):
        try:
            client = genai.Client()
            prompt = f"TTS the following conversation between Joe and Jane:\n\n{podcast_script}"

            response = client.models.generate_content(
                model="gemini-2.5-flash-preview-tts",
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                            speaker_voice_configs=[
                                types.SpeakerVoiceConfig(speaker='Joe',
                                                         voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name='Kore'))),
                                types.SpeakerVoiceConfig(speaker='Jane',
                                                         voice_config=types.VoiceConfig(prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name='Puck')))
                            ]
                        )
                    )
                )
            )

            data = response.candidates[0].content.parts[0].inline_data.data

            if not filename.endswith(".wav"):
                filename += ".wav"

            # ** BUG FIX **: This logic now runs for all cases, not just when the extension is added.
            current_directory = pathlib.Path.cwd()
            file_path = current_directory / filename
            wave_file(str(file_path), data)

            return {
                "status": "success",
                "message": f"Successfully generated and saved podcast audio to {file_path.resolve()}",
                "file_path": str(file_path.resolve()),
                "file_size": len(data)
            }

        except Exception as e:
            error_msg = str(e)

            # Check if it's a 503/overload error
            if "503" in error_msg or "overloaded" in error_msg.lower() or "UNAVAILABLE" in error_msg:
                if attempt < max_retries - 1:
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    print(f"⚠️  API overloaded, retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    continue
                else:
                    return {"status": "error", "message": f"Audio generation failed after {max_retries} attempts: API overloaded. Please try again later."}

            # For other errors, don't retry
            return {"status": "error", "message": f"Audio generation failed: {error_msg[:200]}"}

def get_financial_context(tickers: List[str]) -> Dict[str, str]:
    """
    Fetches the current stock price and daily change for a list of stock tickers.
    """
    financial_data: Dict[str, str] = {}

    # Filter out invalid tickers upfront
    valid_tickers = [ticker.upper().strip() for ticker in tickers 
                    if ticker and ticker.upper() not in ['N/A', 'NA', '']]
    
    if not valid_tickers:
        return {ticker: "No financial data" for ticker in tickers}
        
    for ticker_symbol in valid_tickers:
        try:
            stock = yf.Ticker(ticker_symbol)
            info = stock.info
            price = info.get("currentPrice") or info.get("regularMarketPrice")
            change_percent = info.get("regularMarketChangePercent")
            
            if price is not None and change_percent is not None:
                change_str = f"{change_percent * 100:+.2f}%"
                financial_data[ticker_symbol] = f"${price:.2f} ({change_str})"
            else:
                financial_data[ticker_symbol] = "Price data not available."
        except Exception:
            financial_data[ticker_symbol] = "Invalid Ticker or Data Error"
            
    return financial_data

def save_news_to_markdown(filename: str, content: str) -> Dict[str, str]:
    """
    Saves the given content to a Markdown file in the current directory.
    """
    try:
        if not filename.endswith(".md"):
            filename += ".md"
        current_directory = pathlib.Path.cwd()
        file_path = current_directory / filename
        file_path.write_text(content, encoding="utf-8")
        return {
            "status": "success",
            "message": f"Successfully saved news to {file_path.resolve()}",
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to save file: {str(e)}"}


podcaster_agent = Agent(
    name="podcaster_agent",
    model="gemini-2.5-flash-lite",
    instruction="""
    You are an Audio Generation Specialist. Your single task is to take a provided text script
    and convert it into a multi-speaker audio file using the `generate_podcast_audio` tool.

    Workflow:
    1. Receive the text script from the user or another agent.
    2. Immediately call the `generate_podcast_audio` tool with the provided script and the filename of 'ai_today_podcast'
    3. Report the result of the audio generation back to the user.
    """,
    tools=[generate_podcast_audio],
)

root_agent = Agent(
    name="newsletter_podcast_producer",
    model="gemini-2.5-flash", 
    instruction="""
    **Your Core Identity:**
    You are a Newsletter Podcast Producer. Your job is to orchestrate a complete workflow: fetch newsletters from the user's inbox, extract news stories, compile a report, write a script, and generate a podcast audio file, all while keeping the user informed.

    **Crucial Rules:**
    1.  **Resilience is Key:** If you encounter an error or cannot find specific information for one item (like fetching a stock ticker), you MUST NOT halt the entire process. Use a placeholder value like "Not Available", and continue to the next step. Your primary goal is to deliver the final report and podcast, even if some data points are missing.
    2.  **Newsletter Focus:** Your research is based on newsletters received in the user's inbox today. Focus on extracting meaningful business and tech news stories from newsletter content.
    3.  **User-Facing Communication:** Your interaction has only two user-facing messages: the initial acknowledgment and the final confirmation. All complex work must happen silently in the background between these two messages.

    **Understanding Newsletter Tool Outputs:**
    The `fetch_newsletters_from_inbox` tool returns a JSON object with these keys:
    1.  `newsletters`: A list of newsletter objects with sender, subject, date, and stories.
    2.  `process_log`: A list of strings describing the processing actions performed.
    3.  `total_processed`: Number of newsletters processed.

    **Required Conversational Workflow:**
    1.  **Acknowledge and Inform:** The VERY FIRST thing you do is respond to the user with: "Okay, I'll scan your inbox for today's newsletters, extract the key news stories, enrich them with financial data where available, and compile a podcast for you. This might take a moment."
    2.  **Fetch Newsletters (Background Step):** Immediately after acknowledging, use the `fetch_newsletters_from_inbox` tool to get today's newsletters from the user's inbox.
    3.  **Analyze & Extract Stories (Internal Step):** Process newsletter content to identify individual news stories, company names, and potential stock tickers. If a company is not publicly traded or a ticker cannot be found, use 'N/A'.
    4.  **Get Financial Data (Background Step):** Call the `get_financial_context` tool with the extracted tickers. If the tool returns "Not Available" for any ticker, you will accept this and proceed. Do not stop or report an error.
    5.  **Structure the Report (Internal Step):** Use the `NewsletterReport` schema to structure all gathered information. If financial data was not found for a story, you MUST use "Not Available" in the `financial_context` field. You MUST also populate the `process_log` field with processing notes.
    6.  **Format for Markdown (Internal Step):** Convert the structured `NewsletterReport` data into a well-formatted Markdown string. This MUST include a section at the end called "## Newsletter Processing Notes" where you list the items from the `process_log`.
    7.  **Save the Report (Background Step):** Save the Markdown string using `save_news_to_markdown` with the filename `newsletter_report.md`.
    8.  **Create Podcast Script (Internal Step):** After saving the report, you MUST convert the structured `NewsletterReport` data into a natural, conversational podcast script between two hosts, 'Joe' (enthusiastic) and 'Jane' (analytical).
    9.  **Generate Audio (Background Step):** Call the `podcaster_agent` tool, passing the complete conversational script you just created to it.
    10. **Final Confirmation:** After the audio is successfully generated, your final response to the user MUST be: "All done. I've processed your newsletters, compiled the report, saved it to `newsletter_report.md`, and generated the podcast audio file for you."
    """,
    tools=[
        fetch_newsletters_from_inbox,
        get_financial_context,
        save_news_to_markdown,
        AgentTool(agent=podcaster_agent) 
    ],
    output_schema=NewsletterReport,
    disallow_transfer_to_parent=True,
    disallow_transfer_to_peers=True,
)