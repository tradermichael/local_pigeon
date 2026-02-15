"""
Gmail Tool

Provides Gmail integration for reading, searching, and sending emails.
Uses OAuth 2.0 for per-user authentication.
"""

import base64
from dataclasses import dataclass, field
from email.mime.text import MIMEText
from typing import Any

from local_pigeon.tools.registry import Tool


def get_gmail_service(credentials_path: str, token_path: str = "gmail_token.json"):
    """
    Get an authenticated Gmail service.
    
    Uses stored tokens if available, otherwise initiates OAuth flow.
    """
    import os
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    
    SCOPES = [
        "https://www.googleapis.com/auth/gmail.readonly",
        "https://www.googleapis.com/auth/gmail.send",
        "https://www.googleapis.com/auth/gmail.modify",
    ]
    
    creds = None
    
    # Load existing token
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    
    # Refresh or get new credentials
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
        
        # Save token for future use
        with open(token_path, "w") as token:
            token.write(creds.to_json())
    
    return build("gmail", "v1", credentials=creds)


@dataclass
class GmailTool(Tool):
    """
    Gmail integration tool.
    
    Supports:
    - Reading emails
    - Searching emails
    - Sending emails
    - Listing recent emails
    """
    
    name: str = "gmail"
    description: str = """Interact with Gmail to read, search, and send emails.
Actions:
- list: List recent emails from inbox
- search: Search emails with a query
- read: Read a specific email by ID
- send: Send an email"""
    parameters: dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "search", "read", "send"],
                "description": "The action to perform"
            },
            "query": {
                "type": "string",
                "description": "Search query (for search action)"
            },
            "message_id": {
                "type": "string",
                "description": "Email message ID (for read action)"
            },
            "to": {
                "type": "string",
                "description": "Recipient email address (for send action)"
            },
            "subject": {
                "type": "string",
                "description": "Email subject (for send action)"
            },
            "body": {
                "type": "string",
                "description": "Email body text (for send action)"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results (default: 10)",
                "default": 10
            }
        },
        "required": ["action"]
    })
    requires_approval: bool = False
    settings: Any = field(default=None, repr=False)
    
    def __post_init__(self):
        self._credentials_path = self.settings.credentials_path if self.settings else "credentials.json"
        self._service = None
    
    def _get_service(self):
        """Get or create Gmail service."""
        if not self._service:
            self._service = get_gmail_service(self._credentials_path)
        return self._service
    
    async def execute(self, user_id: str, **kwargs) -> str:
        """Execute a Gmail action."""
        action = kwargs.get("action", "")
        
        if not action:
            return "Error: No action specified. Use: list, search, read, or send"
        
        try:
            if action == "list":
                return await self._list_emails(kwargs.get("max_results", 10))
            elif action == "search":
                query = kwargs.get("query", "")
                if not query:
                    return "Error: Search query required for search action"
                return await self._search_emails(query, kwargs.get("max_results", 10))
            elif action == "read":
                message_id = kwargs.get("message_id", "")
                if not message_id:
                    return "Error: Message ID required for read action"
                return await self._read_email(message_id)
            elif action == "send":
                to = kwargs.get("to", "")
                subject = kwargs.get("subject", "")
                body = kwargs.get("body", "")
                if not all([to, subject, body]):
                    return "Error: 'to', 'subject', and 'body' required for send action"
                return await self._send_email(to, subject, body)
            else:
                return f"Error: Unknown action '{action}'"
                
        except FileNotFoundError as e:
            return str(e)
        except Exception as e:
            return f"Error with Gmail: {str(e)}"
    
    async def _list_emails(self, max_results: int) -> str:
        """List recent emails from inbox."""
        service = self._get_service()
        
        results = service.users().messages().list(
            userId="me",
            labelIds=["INBOX"],
            maxResults=max_results,
        ).execute()
        
        messages = results.get("messages", [])
        
        if not messages:
            return "No emails found in inbox."
        
        output = "Recent emails:\n\n"
        for msg in messages:
            msg_data = service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            
            headers = {h["name"]: h["value"] for h in msg_data.get("payload", {}).get("headers", [])}
            
            output += f"ID: {msg['id']}\n"
            output += f"From: {headers.get('From', 'Unknown')}\n"
            output += f"Subject: {headers.get('Subject', 'No subject')}\n"
            output += f"Date: {headers.get('Date', 'Unknown')}\n"
            output += "-" * 40 + "\n"
        
        return output
    
    async def _search_emails(self, query: str, max_results: int) -> str:
        """Search emails with a query."""
        service = self._get_service()
        
        results = service.users().messages().list(
            userId="me",
            q=query,
            maxResults=max_results,
        ).execute()
        
        messages = results.get("messages", [])
        
        if not messages:
            return f"No emails found matching: {query}"
        
        output = f"Search results for: {query}\n\n"
        for msg in messages:
            msg_data = service.users().messages().get(
                userId="me",
                id=msg["id"],
                format="metadata",
                metadataHeaders=["From", "Subject", "Date"],
            ).execute()
            
            headers = {h["name"]: h["value"] for h in msg_data.get("payload", {}).get("headers", [])}
            
            output += f"ID: {msg['id']}\n"
            output += f"From: {headers.get('From', 'Unknown')}\n"
            output += f"Subject: {headers.get('Subject', 'No subject')}\n"
            output += f"Date: {headers.get('Date', 'Unknown')}\n"
            output += "-" * 40 + "\n"
        
        return output
    
    async def _read_email(self, message_id: str) -> str:
        """Read a specific email."""
        service = self._get_service()
        
        msg = service.users().messages().get(
            userId="me",
            id=message_id,
            format="full",
        ).execute()
        
        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        
        output = f"From: {headers.get('From', 'Unknown')}\n"
        output += f"To: {headers.get('To', 'Unknown')}\n"
        output += f"Subject: {headers.get('Subject', 'No subject')}\n"
        output += f"Date: {headers.get('Date', 'Unknown')}\n"
        output += "\n" + "=" * 40 + "\n\n"
        
        # Extract body
        payload = msg.get("payload", {})
        body = self._extract_body(payload)
        output += body
        
        return output
    
    def _extract_body(self, payload: dict) -> str:
        """Extract text body from email payload."""
        if "body" in payload and payload["body"].get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="ignore")
        
        if "parts" in payload:
            for part in payload["parts"]:
                if part.get("mimeType") == "text/plain":
                    if part.get("body", {}).get("data"):
                        return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="ignore")
                elif part.get("mimeType", "").startswith("multipart/"):
                    return self._extract_body(part)
        
        return "[Could not extract email body]"
    
    async def _send_email(self, to: str, subject: str, body: str) -> str:
        """Send an email."""
        service = self._get_service()
        
        message = MIMEText(body)
        message["to"] = to
        message["subject"] = subject
        
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        sent = service.users().messages().send(
            userId="me",
            body={"raw": raw},
        ).execute()
        
        return f"Email sent successfully! Message ID: {sent['id']}"
