"""
Google Calendar Tool

Provides Google Calendar integration for creating, reading, and managing events.
Uses OAuth 2.0 for per-user authentication.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from local_pigeon.tools.registry import Tool


def get_calendar_service(credentials_path: str, token_path: str | None = None):
    """
    Get an authenticated Calendar service.
    """
    import os
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from local_pigeon.config import get_data_dir
    
    # Use data directory for token storage
    if token_path is None:
        data_dir = get_data_dir()
        token_path = str(data_dir / "google_token.json")
    
    SCOPES = [
        "https://www.googleapis.com/auth/calendar",
        "https://www.googleapis.com/auth/calendar.events",
    ]
    
    creds = None
    
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"OAuth credentials file not found: {credentials_path}\n"
                    "Download from Google Cloud Console: https://console.cloud.google.com/apis/credentials"
                )
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        
        with open(token_path, "w") as token:
            token.write(creds.to_json())
    
    return build("calendar", "v3", credentials=creds)


@dataclass
class CalendarTool(Tool):
    """
    Google Calendar integration tool.
    
    Supports:
    - Listing upcoming events
    - Creating new events
    - Getting event details
    - Checking availability
    """
    
    name: str = "calendar"
    description: str = """Access the USER'S OWN Google Calendar (already authorized via OAuth).
The user has explicitly connected their calendar - you have permission to view and create events on their behalf.

Actions:
- list: List the user's upcoming events
- create: Create a new event on the user's calendar
- get: Get details of a specific event
- free: Check the user's free/busy time

This is the user's own authorized calendar account."""
    parameters: dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "create", "get", "free"],
                "description": "The action to perform"
            },
            "event_id": {
                "type": "string",
                "description": "Event ID (for get action)"
            },
            "title": {
                "type": "string",
                "description": "Event title (for create action)"
            },
            "description": {
                "type": "string",
                "description": "Event description (for create action)"
            },
            "start_time": {
                "type": "string",
                "description": "Start time in ISO format or natural language (for create/free action)"
            },
            "end_time": {
                "type": "string",
                "description": "End time in ISO format or natural language (for create/free action)"
            },
            "duration_minutes": {
                "type": "integer",
                "description": "Duration in minutes (alternative to end_time, default: 60)",
                "default": 60
            },
            "attendees": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of attendee email addresses"
            },
            "days_ahead": {
                "type": "integer",
                "description": "Number of days to look ahead (for list action, default: 7)",
                "default": 7
            }
        },
        "required": ["action"]
    })
    requires_approval: bool = False
    settings: Any = field(default=None, repr=False)
    
    def __post_init__(self):
        self._credentials_path = self.settings.credentials_path if self.settings else "credentials.json"
        self._calendar_id = self.settings.calendar_id if self.settings else "primary"
        self._service = None
    
    def _get_service(self):
        """Get or create Calendar service."""
        if not self._service:
            self._service = get_calendar_service(self._credentials_path)
        return self._service
    
    async def execute(self, user_id: str, **kwargs) -> str:
        """Execute a Calendar action."""
        action = kwargs.get("action", "")
        
        if not action:
            return "Error: No action specified. Use: list, create, get, or free"
        
        try:
            if action == "list":
                return await self._list_events(kwargs.get("days_ahead", 7))
            elif action == "create":
                return await self._create_event(
                    title=kwargs.get("title", ""),
                    description=kwargs.get("description", ""),
                    start_time=kwargs.get("start_time", ""),
                    end_time=kwargs.get("end_time"),
                    duration_minutes=kwargs.get("duration_minutes", 60),
                    attendees=kwargs.get("attendees", []),
                )
            elif action == "get":
                event_id = kwargs.get("event_id", "")
                if not event_id:
                    return "Error: Event ID required for get action"
                return await self._get_event(event_id)
            elif action == "free":
                return await self._check_free(
                    start_time=kwargs.get("start_time", ""),
                    end_time=kwargs.get("end_time", ""),
                )
            else:
                return f"Error: Unknown action '{action}'"
                
        except FileNotFoundError as e:
            return str(e)
        except Exception as e:
            return f"Error with Calendar: {str(e)}"
    
    async def _list_events(self, days_ahead: int) -> str:
        """List upcoming events."""
        service = self._get_service()
        
        now = datetime.utcnow()
        time_min = now.isoformat() + "Z"
        time_max = (now + timedelta(days=days_ahead)).isoformat() + "Z"
        
        events_result = service.events().list(
            calendarId=self._calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=20,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        
        events = events_result.get("items", [])
        
        if not events:
            return f"No upcoming events in the next {days_ahead} days."
        
        output = f"Upcoming events (next {days_ahead} days):\n\n"
        for event in events:
            start = event["start"].get("dateTime", event["start"].get("date"))
            end = event["end"].get("dateTime", event["end"].get("date"))
            
            output += f"📅 {event.get('summary', 'No title')}\n"
            output += f"   Start: {start}\n"
            output += f"   End: {end}\n"
            output += f"   ID: {event['id']}\n"
            
            if event.get("location"):
                output += f"   Location: {event['location']}\n"
            if event.get("attendees"):
                attendees = ", ".join(a.get("email", "") for a in event["attendees"][:3])
                output += f"   Attendees: {attendees}\n"
            
            output += "\n"
        
        return output
    
    async def _create_event(
        self,
        title: str,
        description: str,
        start_time: str,
        end_time: str | None,
        duration_minutes: int,
        attendees: list[str],
    ) -> str:
        """Create a new calendar event."""
        if not title:
            return "Error: Event title is required"
        if not start_time:
            return "Error: Start time is required"
        
        service = self._get_service()
        
        # Parse start time
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        except ValueError:
            # Try natural language parsing (basic)
            return f"Error: Could not parse start time: {start_time}. Use ISO format (e.g., 2024-01-15T10:00:00)"
        
        # Calculate end time
        if end_time:
            try:
                end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            except ValueError:
                return f"Error: Could not parse end time: {end_time}"
        else:
            end_dt = start_dt + timedelta(minutes=duration_minutes)
        
        # Build event
        event = {
            "summary": title,
            "description": description,
            "start": {
                "dateTime": start_dt.isoformat(),
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": end_dt.isoformat(),
                "timeZone": "UTC",
            },
        }
        
        if attendees:
            event["attendees"] = [{"email": email} for email in attendees]
        
        # Create the event
        created = service.events().insert(
            calendarId=self._calendar_id,
            body=event,
            sendUpdates="all" if attendees else "none",
        ).execute()
        
        return f"✅ Event created successfully!\n\nTitle: {title}\nStart: {start_dt}\nEnd: {end_dt}\nEvent ID: {created['id']}\nLink: {created.get('htmlLink', 'N/A')}"
    
    async def _get_event(self, event_id: str) -> str:
        """Get details of a specific event."""
        service = self._get_service()
        
        event = service.events().get(
            calendarId=self._calendar_id,
            eventId=event_id,
        ).execute()
        
        start = event["start"].get("dateTime", event["start"].get("date"))
        end = event["end"].get("dateTime", event["end"].get("date"))
        
        output = f"📅 Event Details\n\n"
        output += f"Title: {event.get('summary', 'No title')}\n"
        output += f"Start: {start}\n"
        output += f"End: {end}\n"
        output += f"Status: {event.get('status', 'Unknown')}\n"
        
        if event.get("description"):
            output += f"\nDescription:\n{event['description']}\n"
        
        if event.get("location"):
            output += f"\nLocation: {event['location']}\n"
        
        if event.get("attendees"):
            output += f"\nAttendees:\n"
            for attendee in event["attendees"]:
                status = attendee.get("responseStatus", "unknown")
                output += f"  - {attendee.get('email')}: {status}\n"
        
        if event.get("htmlLink"):
            output += f"\nLink: {event['htmlLink']}\n"
        
        return output
    
    async def _check_free(self, start_time: str, end_time: str) -> str:
        """Check free/busy time."""
        if not start_time or not end_time:
            return "Error: Both start_time and end_time are required for free/busy check"
        
        service = self._get_service()
        
        try:
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
        except ValueError:
            return "Error: Could not parse times. Use ISO format."
        
        body = {
            "timeMin": start_dt.isoformat(),
            "timeMax": end_dt.isoformat(),
            "items": [{"id": self._calendar_id}],
        }
        
        result = service.freebusy().query(body=body).execute()
        
        busy = result.get("calendars", {}).get(self._calendar_id, {}).get("busy", [])
        
        if not busy:
            return f"✅ You are free from {start_time} to {end_time}"
        
        output = f"📅 Busy times between {start_time} and {end_time}:\n\n"
        for slot in busy:
            output += f"  - {slot['start']} to {slot['end']}\n"
        
        return output
