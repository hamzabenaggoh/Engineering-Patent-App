from fastmcp import FastMCP
import os
import httpx
from datetime import datetime, timedelta
from calendar_auth import get_calendar_service
import json
import asyncio # <--- 1. IMPORT ASYNCIO

# Initialize FastMCP server
mcp = FastMCP("IP Assistant MCP Server")

# API Keys from environment
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

@mcp.tool()
async def search_patents(query: str, focus: str = "patents") -> str:
    """
    Search for patents and prior art using Perplexity AI.
    
    Args:
        query: The invention or technology to search for
        focus: Type of search - "patents", "research", or "general"
    
    Returns:
        Search results with patent numbers, dates, and technical details
    """
    
    # Craft a focused prompt for patent searching
    if focus == "patents":
        prompt = f"""Search for patents and prior art related to: {query}

Please provide:
1. Specific US patent numbers (format: US 1,234,567)
2. International patents (PCT, EPO, CN, JP)
3. Publication dates
4. Brief description of the technical approach
5. Key differences from the query

Focus on the most relevant 3-5 patents."""
    else:
        prompt = f"Search for technical information about: {query}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {PERPLEXITY_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "sonar",
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a patent research assistant. Always provide specific patent numbers and technical details. Be concise but thorough."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "temperature": 0.2,
                    "max_tokens": 1500
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                return result["choices"][0]["message"]["content"]
            else:
                return f"Error: Perplexity API returned status {response.status_code}"
            
        except httpx.TimeoutException:
            return "Error: Search request timed out. Please try again."
        except Exception as e:
            return f"Error searching patents: {str(e)}"

# --- 2. CREATE SYNCHRONOUS HELPER FUNCTIONS FOR CALENDAR ---

def _sync_schedule_meeting(
    title: str,
    attendee_email: str,
    date: str,
    time: str,
    duration_minutes: int = 60,
    description: str = ""
) -> str:
    """Synchronous helper to schedule a meeting."""
    try:
        # Get calendar service
        service = get_calendar_service() # This is a blocking call
        
        # Parse datetime
        try:
            start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        except ValueError:
            return f"❌ Invalid date/time format. Use YYYY-MM-DD for date and HH:MM for time. Got: {date} {time}"
        
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        
        # Create event
        event = {
            'summary': title,
            'description': description or 'IP Intake Meeting - Invention Disclosure Discussion\n\nScheduled via IP Assistant',
            'start': {
                'dateTime': start_dt.isoformat(),
                'timeZone': 'America/New_York', # Note: Consider making this dynamic if users are in other timezones
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': 'America/New_York',
            },
            'attendees': [
                {'email': attendee_email},
            ],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 30},
                ],
            },
            'conferenceData': {
                'createRequest': {
                    'requestId': f"ip-assistant-{int(datetime.now().timestamp())}",
                    'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                }
            }
        }
        
        # Insert event - THIS IS A BLOCKING CALL
        event_result = service.events().insert(
            calendarId='primary',
            body=event,
            conferenceDataVersion=1,
            sendUpdates='all'
        ).execute() 
        
        # Format response
        meet_link = event_result.get('hangoutLink', 'No video link')
        calendar_link = event_result.get('htmlLink', 'No calendar link')
        
        return f"""✅ Meeting scheduled successfully!

📅 {title}
📧 Attendee: {attendee_email}
🕐 {start_dt.strftime('%A, %B %d, %Y at %I:%M %p')}
⏱️  Duration: {duration_minutes} minutes

🔗 Calendar: {calendar_link}
📹 Google Meet: {meet_link}

Email invitations sent to all attendees."""
        
    except Exception as e:
        return f"❌ Error creating meeting: {str(e)}\n\nPlease check that the date/time format is correct and try again."

def _sync_find_available_times(
    date: str,
    duration_minutes: int = 60
) -> str:
    """Synchronous helper to find available time slots."""
    try:
        service = get_calendar_service() # Blocking
        
        # Parse date
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return f"❌ Invalid date format. Use YYYY-MM-DD. Got: {date}"
        
        # Get events for the day (9 AM - 5 PM)
        start_of_day = target_date.replace(hour=9, minute=0, second=0)
        end_of_day = target_date.replace(hour=17, minute=0, second=0)
        
        # BLOCKING CALL
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_of_day.isoformat() + 'Z',
            timeMax=end_of_day.isoformat() + 'Z',
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return f"""✅ Fully available on {target_date.strftime('%A, %B %d, %Y')}

Available slots (business hours 9 AM - 5 PM):
- 9:00 AM - 5:00 PM (entire day open)

Recommended times for {duration_minutes}-minute meeting:
- 10:00 AM
- 2:00 PM
- 3:00 PM"""
        
        # Format busy times
        busy_slots = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            summary = event.get('summary', 'Busy')
            
            if 'T' in start:
                start_time = datetime.fromisoformat(start.replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(end.replace('Z', '+00:00'))
                busy_slots.append(f"• {start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}: {summary}")
            else:
                busy_slots.append(f"• All day: {summary}")
        
        return f"""📅 Schedule for {target_date.strftime('%A, %B %d, %Y')}:

Busy times:
{chr(10).join(busy_slots)}

💡 Look for {duration_minutes}-minute gaps between meetings for scheduling."""
        
    except Exception as e:
        return f"❌ Error checking availability: {str(e)}"

def _sync_list_upcoming_meetings(days_ahead: int = 7) -> str:
    """Synchronous helper to list upcoming meetings."""
    try:
        service = get_calendar_service() # Blocking
        
        now = datetime.utcnow()
        end_date = now + timedelta(days=days_ahead)
        
        # BLOCKING CALL
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now.isoformat() + 'Z',
            timeMax=end_date.isoformat() + 'Z',
            maxResults=20,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        
        if not events:
            return f"📭 No upcoming meetings in the next {days_ahead} days."
        
        # Group by date
        meetings_by_date = {}
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            summary = event.get('summary', 'No title')
            
            if 'T' in start:
                dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                date_key = dt.strftime('%A, %B %d')
                time_str = dt.strftime('%I:%M %p')
                
                if date_key not in meetings_by_date:
                    meetings_by_date[date_key] = []
                meetings_by_date[date_key].append(f"  • {time_str}: {summary}")
        
        # Format output
        output = [f"📅 Upcoming meetings (next {days_ahead} days):\n"]
        for date_key, meetings in meetings_by_date.items():
            output.append(f"{date_key}:")
            output.extend(meetings)
            output.append("")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"❌ Error listing meetings: {str(e)}"

# --- 3. UPDATE @mcp.tool() DEFINITIONS TO USE THE HELPERS ---

@mcp.tool()
async def schedule_meeting(
    title: str,
    attendee_email: str,
    date: str,
    time: str,
    duration_minutes: int = 60,
    description: str = ""
) -> str:
    """
    Schedule a meeting on Google Calendar.
    ... (docstring args) ...
    """
    # Run the blocking function in a thread
    return await asyncio.to_thread(
        _sync_schedule_meeting,
        title,
        attendee_email,
        date,
        time,
        duration_minutes,
        description
    )

@mcp.tool()
async def find_available_times(
    date: str,
    duration_minutes: int = 60
) -> str:
    """
    Find available time slots on a specific date.
    ... (docstring args) ...
    """
    # Run the blocking function in a thread
    return await asyncio.to_thread(
        _sync_find_available_times,
        date,
        duration_minutes
    )

@mcp.tool()
async def list_upcoming_meetings(days_ahead: int = 7) -> str:
    """
    List upcoming meetings in the next N days.
    ... (docstring args) ...
    """
    # Run the blocking function in a thread
    return await asyncio.to_thread(
        _sync_list_upcoming_meetings,
        days_ahead
    )

# Add server info resource
@mcp.resource("server://info")
def server_info() -> str:
    """Information about this MCP server and its capabilities"""
    return """🤖 IP Assistant MCP Server

This server helps Daimler engineers move inventions through the IP pipeline.

📋 Available Tools:

1. search_patents
   - Search for patents and prior art using Perplexity AI
   - Provides patent numbers, dates, and technical details
   - Usage: "Search for patents on adaptive cooling fins"

2. schedule_meeting
   - Create Google Calendar events
   - Sends invitations to attendees
   - Includes Google Meet links
   - Usage: "Schedule meeting with paul.focke@daimler.com tomorrow at 2 PM"

3. find_available_times
   - Check calendar availability
   - Find open slots for meetings
   - Usage: "Check my availability on Friday"

4. list_upcoming_meetings
   - View upcoming meetings
   - Default: next 7 days
   - Usage: "What meetings do I have this week?"

🔧 Configuration:
- Patent Search: Powered by Perplexity AI
- Calendar: Google Calendar API with OAuth2
- Transport: Server-Sent Events (SSE)

📝 Example Usage:
"I invented a new adaptive cooling system for EV batteries. Search for similar patents and schedule a meeting with Paul for next Tuesday at 2 PM to discuss it."
"""

@mcp.resource("server://health")
def health_check() -> str:
    """Health check endpoint"""
    perplexity_status = "✅ Connected" if PERPLEXITY_API_KEY else "❌ API key missing"
    calendar_status = "✅ Configured" if os.getenv("GOOGLE_REFRESH_TOKEN") else "❌ Not authenticated"
    
    return f"""🏥 Health Status

Perplexity API: {perplexity_status}
Google Calendar: {calendar_status}

Server: Running
Transport: SSE (Server-Sent Events)
"""


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    

    
    mcp.run(transport="sse", host="0.0.0.0", port=port)