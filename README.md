# Newsletter Podcast Agent

An AI-powered system that automatically processes newsletters from your inbox and creates professional podcasts based on the content.

## 🚀 Features

- **Inbox Integration**: Automatically scans your Gmail inbox for newsletters
- **Content Extraction**: Intelligently parses newsletter content to extract individual stories
- **Financial Data**: Enriches stories with real-time stock prices and market data
- **Multi-speaker Audio**: Generates professional podcasts with distinct host personalities
- **Automated Workflow**: Complete end-to-end processing from inbox to audio file

## 📋 Prerequisites

- Python 3.9+
- Gmail account with newsletters
- Google Cloud Console project with Gmail API enabled

## 🛠️ Installation

1. **Clone and setup environment:**
   ```bash
   cd NewsCast
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Setup Gmail API credentials:**
   ```bash
   python setup_gmail.py
   ```
   
   Follow the instructions to:
   - Create a Google Cloud Console project
   - Enable the Gmail API
   - Download credentials.json
   - Authorize the application

## 🎯 Supported Newsletter Sources

The agent automatically processes newsletters from these trusted sources:

- **Business News**: Morning Brew, The Hustle, Axios
- **Tech News**: TechCrunch, VentureBeat, The Verge, Ars Technica, Wired
- **Financial News**: Bloomberg, Reuters, Wall Street Journal, Financial Times

## 🔧 Usage

### Basic Usage

```python
from ai_news_agent.agent import root_agent

# The agent will automatically:
# 1. Scan your inbox for today's newsletters
# 2. Extract news stories and company information
# 3. Fetch financial data for public companies
# 4. Generate a structured report
# 5. Create a podcast script
# 6. Generate audio with multi-speaker voices

# Run the agent
result = await root_agent.run("Process my newsletters")
```

### Output Files

- **`newsletter_report.md`**: Structured markdown report with all stories
- **`ai_today_podcast.wav`**: Professional audio podcast file

## 🏗️ Architecture

### Agent Structure

- **`newsletter_podcast_producer`**: Main orchestrator agent
- **`podcaster_agent`**: Specialized audio generation agent

### Data Flow

```
Gmail Inbox → Newsletter Parsing → Story Extraction → 
Financial Enrichment → Report Generation → Script Creation → Audio Output
```

### Data Models

- **`NewsletterStory`**: Individual story with company, financial, and source data
- **`NewsletterReport`**: Complete report with multiple stories and processing notes

## 🎭 Podcast Features

- **Dual Hosts**: Joe (enthusiastic) and Jane (analytical)
- **Professional Voices**: Uses Gemini's advanced TTS with distinct personalities
- **High Quality**: 24kHz WAV output for maximum compatibility
- **Natural Flow**: Conversational dialogue between contrasting perspectives

## 🔒 Security & Privacy

- **Read-only Access**: Only reads emails, never modifies or sends
- **Local Processing**: All data processing happens locally
- **Secure Credentials**: OAuth2 authentication with token management
- **No Data Storage**: No persistent storage of email content

## 🛠️ Configuration

### Environment Variables

```bash
# Optional: Disable Vertex AI (uses Gemini API directly)
GOOGLE_GENAI_USE_VERTEXAI=0

# Required: Your Google API key
GOOGLE_API_KEY=your_api_key_here
```

### Newsletter Sources

Modify `NEWSLETTER_SENDERS` in `agent.py` to add or remove newsletter sources:

```python
NEWSLETTER_SENDERS = [
    'morningbrew.com', 'thehustle.co', 'axios.com',
    'techcrunch.com', 'venturebeat.com', 'theverge.com',
    # Add your preferred newsletter sources here
]
```

## 🚨 Troubleshooting

### Common Issues

1. **"credentials.json not found"**
   - Run `python setup_gmail.py` and follow the setup instructions
   - Ensure you've downloaded the OAuth2 credentials from Google Cloud Console

2. **"No newsletters found"**
   - Check that you have newsletters from supported senders in your inbox
   - Verify the newsletters were received today
   - Add your newsletter sources to `NEWSLETTER_SENDERS`

3. **"Gmail API error"**
   - Ensure Gmail API is enabled in Google Cloud Console
   - Check that your OAuth2 credentials are valid
   - Re-run the setup script to refresh tokens

### Debug Mode

Enable detailed logging by modifying the agent configuration:

```python
# Add to agent initialization
debug=True
```

## 📈 Advanced Features

### Custom Newsletter Parsing

Modify `parse_newsletter_content()` to improve story extraction for specific newsletter formats.

### Financial Data Integration

The system automatically:
- Identifies company names in stories
- Looks up stock tickers
- Fetches real-time prices and changes
- Handles private companies gracefully

### Audio Customization

Modify voice configurations in `generate_podcast_audio()`:
- Change speaker personalities
- Adjust voice characteristics
- Modify audio quality settings

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Google ADK for agent framework
- Gemini API for text-to-speech
- yfinance for financial data
- BeautifulSoup for HTML parsing
