"""
Shared Google OAuth authentication.

All Google tools share a single token file with combined scopes.
This prevents individual tools from overwriting the token with
a narrower scope set.
"""

import os
from pathlib import Path

# Combined scopes for all Google services
ALL_SCOPES = [
    # Gmail
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
    # Calendar
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/calendar.events",
    # Drive
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
]


def get_google_credentials(
    credentials_path: str,
    token_path: str | None = None,
):
    """
    Load or create Google OAuth credentials with ALL combined scopes.

    If the existing token is missing any of the required scopes, a new
    OAuth flow is triggered so the user grants all permissions at once.
    The token is saved back to disk after refresh or re-auth.

    Returns:
        google.oauth2.credentials.Credentials
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from local_pigeon.config import get_data_dir

    if token_path is None:
        data_dir = get_data_dir()
        token_path = str(data_dir / "google_token.json")

    creds = None

    # Load existing token (without scope filtering — we check manually)
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path)

    needs_reauth = False
    if creds is not None:
        # Check that all required scopes are present
        token_scopes = set(creds.scopes or [])
        required_scopes = set(ALL_SCOPES)
        if not required_scopes.issubset(token_scopes):
            needs_reauth = True

    if creds is None or needs_reauth:
        # Try refresh first if we have a refresh token
        if creds and creds.refresh_token and not needs_reauth:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None

        if creds is None or needs_reauth:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"OAuth credentials file not found: {credentials_path}\n"
                    "Download from Google Cloud Console: "
                    "https://console.cloud.google.com/apis/credentials"
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, ALL_SCOPES
            )
            creds = flow.run_local_server(port=0)

        # Save unified token
        with open(token_path, "w") as token:
            token.write(creds.to_json())

    elif not creds.valid:
        # Token exists with correct scopes but expired — just refresh
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, "w") as token:
                token.write(creds.to_json())

    return creds
