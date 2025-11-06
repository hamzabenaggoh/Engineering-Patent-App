import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ['https://www.googleapis.com/auth/calendar.events']

def get_calendar_service():
    """
    Get authenticated Google Calendar service.
    Uses environment variables for production (Render).
    """
    
    # Create credentials from environment variables
    creds = Credentials(
        token=None,  # Will be refreshed automatically
        refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        scopes=SCOPES
    )
    
    # Refresh the access token
    try:
        creds.refresh(Request())
    except Exception as e:
        raise Exception(f"Failed to refresh Google credentials: {e}")
    
    # Build and return the calendar service
    return build('calendar', 'v3', credentials=creds)