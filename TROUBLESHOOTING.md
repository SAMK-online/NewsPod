# NewsCast Troubleshooting Guide

## Common Issues and Solutions

### 1. 503 UNAVAILABLE / Model Overloaded Error

**Error Message:**
```
503 UNAVAILABLE. {'error': {'code': 503, 'message': 'The model is overloaded. Please try again later.', 'status': 'UNAVAILABLE'}}
```

**Cause:** Google's Gemini API is experiencing high traffic and temporarily cannot handle your request.

**Solutions:**

#### ✅ Automatic Retry (Already Implemented)
The system now automatically retries 3 times with exponential backoff:
- Attempt 1: Wait 5 seconds
- Attempt 2: Wait 10 seconds
- Attempt 3: Wait 20 seconds

#### ⏰ Manual Solutions:
1. **Wait and Retry** (Simplest)
   - Wait 2-5 minutes
   - Run your agent again
   - The API usually recovers quickly

2. **Use Different Model** (If persistent)
   ```python
   # In agent.py, line 536, change:
   model="gemini-2.5-flash-preview-tts"
   # to:
   model="gemini-1.5-flash"  # More stable, but no multi-speaker TTS
   ```

3. **Run During Off-Peak Hours**
   - Try early morning (2-6 AM PST)
   - Weekends usually have less traffic

4. **Reduce Podcast Length**
   - Limit stories to top 3 instead of 5
   - Generate shorter scripts

---

### 2. No Newsletters Found

**Error Message:**
```
No relevant newsletters with news stories were found in your inbox today.
```

**Solutions:**

1. **Check Email Subscriptions**
   ```bash
   python test_inbox.py
   ```
   This shows what newsletters you actually have.

2. **Subscribe to More Newsletters**
   - TLDR: https://tldr.tech/
   - Morning Brew: https://www.morningbrew.com/
   - The Hustle: https://thehustle.co/

3. **Adjust Date Filter**
   In `agent.py`, line 420, change:
   ```python
   query = f'newer_than:1d'  # Last 24 hours
   # to:
   query = f'newer_than:2d'  # Last 48 hours
   ```

---

### 3. Gmail API Authentication Issues

**Error Message:**
```
credentials.json file not found
```

**Solutions:**

1. **Re-run Gmail Setup**
   ```bash
   python setup_gmail.py
   ```

2. **Check Token Expiration**
   - Delete `token.json`
   - Run `python setup_gmail.py` again
   - Re-authorize the application

3. **Verify API Enablement**
   - Go to Google Cloud Console
   - Ensure Gmail API is enabled
   - Check OAuth 2.0 credentials are configured

---

### 4. Story Extraction Issues

**Problem:** Only getting 1 story per newsletter

**Already Fixed!** The issue was:
- HTML text extraction was removing line breaks
- Pattern matching couldn't find multiple stories

If you still see this issue:
1. Check the newsletter format hasn't changed
2. Run: `python test_parse_function.py`
3. Verify the output shows 5 stories

---

### 5. Audio Generation Quality Issues

**Problem:** Podcast audio sounds off or voices don't match

**Solutions:**

1. **Verify Voice Names**
   Check available voices at: https://cloud.google.com/text-to-speech/docs/voices

2. **Adjust Voice Configuration**
   In `agent.py`, lines 544-547:
   ```python
   # Try different voice combinations:
   voice_name='Kore'   # Joe (enthusiastic)
   voice_name='Puck'   # Jane (analytical)

   # Other options:
   voice_name='Aoede'  # Feminine
   voice_name='Charon' # Masculine
   ```

---

## Testing Commands

```bash
# Test Gmail connection
python test_inbox.py

# Test newsletter fetching
python test_full_fetch.py

# Test story parsing
python test_parse_function.py

# Test TLDR parsing specifically
python test_tldr_fetch.py

# Run the full agent
python app.py
```

---

## Rate Limits

### Gemini API Limits:
- **Free Tier**: 15 requests/minute, 1,500 requests/day
- **Paid Tier**: 1,000 requests/minute, unlimited daily

If you hit rate limits:
1. Add delays between requests
2. Upgrade to paid tier
3. Implement request queuing

---

## Getting Help

1. **Check Logs**
   - Look at `newsletter_report.md` for processing notes
   - Check console output for error details

2. **Enable Debug Mode**
   Add print statements in `agent.py`:
   ```python
   print(f"Debug: {variable_name}")
   ```

3. **GitHub Issues**
   Report bugs with:
   - Error message
   - Steps to reproduce
   - Environment details (Python version, OS)

---

## Performance Optimization

### Speed Up Processing:
1. **Limit Newsletter Count**
   ```python
   # In fetch_newsletters_from_inbox, line 427:
   maxResults=50  # Reduce to 20 or 10
   ```

2. **Parallel Processing**
   Process multiple newsletters simultaneously (future enhancement)

3. **Cache Results**
   Store parsed newsletters to avoid re-processing (future enhancement)

---

## Environment Variables

Create a `.env` file:
```bash
# Optional: Disable Vertex AI
GOOGLE_GENAI_USE_VERTEXAI=0

# Required: Your Google API key
GOOGLE_API_KEY=your_api_key_here

# Optional: Custom retry settings
MAX_RETRIES=3
RETRY_DELAY=5
```

---

**Last Updated:** October 2025
