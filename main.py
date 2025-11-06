from fastmcp import FastMCP
import os
import httpx
from datetime import datetime, timedelta
from calendar_auth import get_calendar_service
import json

# --- ADD STARLETTE IMPORTS FOR HEALTH CHECK ---
from starlette.requests import Request
from starlette.responses import JSONResponse

# Initialize FastMCP server
mcp = FastMCP("IP Assistant MCP Server")

# API Keys from environment
PERPLEXITY_API_KEY = os.getenv("PERPLEXITY_API_KEY")

@mcp.tool()
async def search_patents(query: str, focus: str = "patents") -> str:
    """
    Search for patents and prior art using Perplexity AI.
    (This tool is async, which is good)
    """
    
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
                        {"role": "system", "content": "You are a patent research assistant."},
                        {"role": "user", "content": prompt}
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

# --- CALENDAR TOOLS (Synchronous / Blocking) ---
# As requested, these will run synchronously and block the server.
# This may cause Render health checks to time out if a call is slow.

@mcp.tool()
def schedule_meeting(
    title: str,
    attendee_email: str,
    date: str,
    time: str,
    duration_minutes: int = 60,
    description: str = ""
) -> str:
    """
    Schedule a meeting on Google Calendar.
    (This is a BLOCKING call)
    """
    try:
        service = get_calendar_service() # Blocking call
        
        try:
            start_dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        except ValueError:
            return f"❌ Invalid date/time format. Use YYYY-MM-DD for date and HH:MM for time. Got: {date} {time}"
        
        end_dt = start_dt + timedelta(minutes=duration_minutes)
        
        event = {
            'summary': title,
            'description': description or 'IP Intake Meeting',
            'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'America/New_York'},
            'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'America/New_York'},
            'attendees': [{'email': attendee_email}],
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
        
        event_result = service.events().insert(
            calendarId='primary',
            body=event,
            conferenceDataVersion=1,
            sendUpdates='all'
        ).execute() # Blocking call
        
        meet_link = event_result.get('hangoutLink', 'No video link')
        calendar_link = event_result.get('htmlLink', 'No calendar link')
        
        return f"✅ Meeting scheduled successfully!\n📅 {title}\n🔗 Calendar: {calendar_link}\n📹 Google Meet: {meet_link}"
        
    except Exception as e:
        return f"❌ Error creating meeting: {str(e)}"

@mcp.tool()
def find_available_times(
    date: str,
    duration_minutes: int = 60
) -> str:
    """
    Find available time slots on a specific date.
    (This is a BLOCKING call)
    """
    try:
        service = get_calendar_service() # Blocking
        
        try:
            target_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return f"❌ Invalid date format. Use YYYY-MM-DD. Got: {date}"
        
        start_of_day = target_date.replace(hour=9, minute=0, second=0)
        end_of_day = target_date.replace(hour=17, minute=0, second=0)
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=start_of_day.isoformat() + 'Z',
            timeMax=end_of_day.isoformat() + 'Z',
            singleEvents=True,
            orderBy='startTime'
        ).execute() # Blocking
        
        events = events_result.get('items', [])
        
        if not events:
            return f"✅ Fully available on {target_date.strftime('%A, %B %d, %Y')}"
        
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
        
        return f"📅 Schedule for {target_date.strftime('%A, %B %d, %Y')}:\n\nBusy times:\n{chr(10).join(busy_slots)}"
        
    except Exception as e:
        return f"❌ Error checking availability: {str(e)}"

@mcp.tool()
def list_upcoming_meetings(days_ahead: int = 7) -> str:
    """
    List upcoming meetings in the next N days.
    (This is a BLOCKING call)
    """
    try:
        service = get_calendar_service() # Blocking
        
        now = datetime.utcnow()
        end_date = now + timedelta(days=days_ahead)
        
        events_result = service.events().list(
            calendarId='primary',
            timeMin=now.isoformat() + 'Z',
            timeMax=end_of_day.isoformat() + 'Z',
            maxResults=20,
            singleEvents=True,
            orderBy='startTime'
        ).execute() # Blocking
        
        events = events_result.get('items', [])
        
        if not events:
            return f"📭 No upcoming meetings in the next {days_ahead} days."
        
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
        
        output = [f"📅 Upcoming meetings (next {days_ahead} days):\n"]
        for date_key, meetings in meetings_by_date.items():
            output.append(f"{date_key}:")
            output.extend(meetings)
            output.append("")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"❌ Error listing meetings: {str(e)}"

# --- RENDER HEALTH CHECK ---
# This is still mandatory for Render deployment,
# regardless of using 'http' or 'sse' transport.
@mcp.custom_route("/health", methods=["GET"])
async def http_health_check(request: Request) -> JSONResponse:
    """A simple HTTP health check endpoint for Render."""
    return JSONResponse({"status": "ok"})

# --- (Rest of your server info/main function) ---

@mcp.resource("server://info")
def server_info() -> str:
    """Information about this MCP server and its capabilities"""
    return """🤖 IP Assistant MCP Server

This server helps Daimler engineers move inventions through the IP pipeline.

📋 Available Tools:

1. search_patents
   - Search for patents and prior art using Perplexity AI

2. schedule_meeting
   - Create Google Calendar events

3. find_available_times
   - Check calendar availability

4. list_upcoming_meetings
   - View upcoming meetings
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
Transport: HTTP
"""


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    
    print(f"""
╔══════════════════════════════════════════════════════╗
║         IP Assistant MCP Server                     ║
║                                                      ║
║  🚀 Starting server on port {port}                    ║
║  🔧 Transport: HTTP (Switched from SSE)              ║
║                                                      ║
║  Tools available:                                    ║
║    • search_patents (Perplexity AI)                 ║
║    • schedule_meeting (Google Calendar)             ║
║    • find_available_times                           ║
║    • list_upcoming_meetings                         ║
║  🩺 Health Check: /health                           ║
╚══════════════════════════════════════════════════════╝
    """)
    
    mcp.run(transport="http", host="0.0.0.0", port=port)