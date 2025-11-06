from google_auth_oauthlib.flow import InstalledAppFlow
import json
import os

SCOPES = ['https://www.googleapis.com/auth/calendar.events']

# Your actual credentials filename
CREDENTIALS_FILE = ''

# Check for credentials file
if not os.path.exists(CREDENTIALS_FILE):
    print(f"❌ Error: {CREDENTIALS_FILE} not found!")
    print("\nPlease make sure the file is in this directory:")
    print(f"   {os.getcwd()}")
    exit(1)

print("=" * 70)
print("🔐 GOOGLE CALENDAR AUTHENTICATION")
print("=" * 70)
print("\nStarting OAuth flow...")
print("A browser window will open for you to authorize the app.")
print("If the browser doesn't open, copy the URL from the console.\n")

# Create flow from credentials file
flow = InstalledAppFlow.from_client_secrets_file(
    CREDENTIALS_FILE,
    SCOPES
)

try:
    # Run local server on port 8080
    # This will open your browser automatically
    creds = flow.run_local_server(
        port=8080,
        open_browser=True,
        success_message='✅ Authentication successful! You can close this window and return to the terminal.'
    )
    
    print("\n" + "=" * 70)
    print("✅ AUTHENTICATION SUCCESSFUL!")
    print("=" * 70)
    
    # Save token.json for local testing
    with open('token.json', 'w') as token:
        token.write(creds.to_json())
    print("\n✅ Saved token.json for local development")
    
    # Extract values from credentials file
    with open(CREDENTIALS_FILE, 'r') as f:
        creds_data = json.load(f)
    
    client_id = creds_data['installed']['client_id']
    client_secret = creds_data['installed']['client_secret']
    refresh_token = creds.refresh_token
    
    print("\n" + "=" * 70)
    print("🚀 COPY THESE TO YOUR RENDER ENVIRONMENT VARIABLES:")
    print("=" * 70)
    print(f"\nGOOGLE_CLIENT_ID={client_id}")
    print(f"\nGOOGLE_CLIENT_SECRET={client_secret}")
    print(f"\nGOOGLE_REFRESH_TOKEN={refresh_token}")
    print("\n" + "=" * 70)
    
    print("\n✅ Setup complete!")
    print("\nNext steps:")
    print("1. Copy the three environment variables above")
    print("2. Add them to your Render dashboard")
    print("3. Also add: PERPLEXITY_API_KEY=your_key_here")
    print("4. Deploy your app to Render")
    print("5. Connect to ElevenLabs\n")
    
except Exception as e:
    print(f"\n❌ Error during authentication: {e}")
    print("\n🔧 Troubleshooting:")
    print("1. Make sure http://localhost:8080/ is in your Google Cloud Console")
    print("   Authorized redirect URIs")
    print("2. Wait 5 minutes after adding the redirect URI")
    print("3. Make sure port 8080 is not already in use")
    print("4. Try running: lsof -ti:8080 | xargs kill  (to free port 8080)")
    print("\nIf this continues to fail, try the manual method instead.\n")