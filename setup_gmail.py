#!/usr/bin/env python3
"""
Gmail API Setup Script for Newsletter Podcast Agent

This script helps you set up Gmail API credentials for the newsletter podcast agent.
Follow these steps:

1. Go to Google Cloud Console (https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Gmail API
4. Create credentials (OAuth 2.0 Client ID)
5. Download the credentials.json file
6. Place it in this directory
7. Run this script to test the connection
"""

import os
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# Gmail API scopes
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

def setup_gmail_api():
    """Setup Gmail API credentials and test connection."""
    
    print("🔧 Gmail API Setup for Newsletter Podcast Agent")
    print("=" * 50)
    
    # Check if credentials file exists
    credentials_file = 'credentials.json'
    if not os.path.exists(credentials_file):
        print(f"❌ {credentials_file} not found!")
        print("\n📋 Setup Instructions:")
        print("1. Go to Google Cloud Console: https://console.cloud.google.com/")
        print("2. Create a new project or select existing one")
        print("3. Enable the Gmail API")
        print("4. Go to 'Credentials' → 'Create Credentials' → 'OAuth 2.0 Client ID'")
        print("5. Choose 'Desktop Application'")
        print("6. Download the JSON file and rename it to 'credentials.json'")
        print("7. Place it in this directory and run this script again")
        return False
    
    print(f"✅ Found {credentials_file}")
    
    # Initialize credentials
    creds = None
    token_file = 'token.json'
    
    # Load existing token
    if os.path.exists(token_file):
        print("✅ Found existing token file")
        creds = Credentials.from_authorized_user_file(token_file, SCOPES)
    
    # If no valid credentials, request authorization
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 Refreshing expired credentials...")
            creds.refresh(Request())
        else:
            print("🔐 Requesting new authorization...")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_file, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for next run
        with open(token_file, 'w') as token:
            token.write(creds.to_json())
        print("✅ Credentials saved to token.json")
    
    # Test Gmail API connection
    try:
        print("🔌 Testing Gmail API connection...")
        service = build('gmail', 'v1', credentials=creds)
        
        # Get user profile to test connection
        profile = service.users().getProfile(userId='me').execute()
        email = profile.get('emailAddress', 'Unknown')
        print(f"✅ Successfully connected to Gmail API")
        print(f"📧 Connected to: {email}")
        
        # Test reading emails
        print("📬 Testing email access...")
        results = service.users().messages().list(userId='me', maxResults=1).execute()
        messages = results.get('messages', [])
        
        if messages:
            print(f"✅ Successfully accessed inbox ({len(messages)} recent messages found)")
        else:
            print("⚠️  No recent messages found (this is normal for new accounts)")
        
        print("\n🎉 Setup Complete! Your newsletter podcast agent is ready to use.")
        print("\n📝 Next Steps:")
        print("1. Make sure you have newsletters from supported senders in your inbox")
        print("2. Run the agent to process your newsletters")
        print("3. Supported newsletter senders:")
        print("   - morningbrew.com, thehustle.co, axios.com")
        print("   - techcrunch.com, venturebeat.com, theverge.com")
        print("   - arstechnica.com, wired.com, bloomberg.com")
        print("   - reuters.com, wsj.com, ft.com")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Gmail API: {str(e)}")
        print("\n🔧 Troubleshooting:")
        print("1. Make sure Gmail API is enabled in Google Cloud Console")
        print("2. Check that your credentials.json file is valid")
        print("3. Ensure you have granted necessary permissions")
        return False

if __name__ == "__main__":
    setup_gmail_api()
