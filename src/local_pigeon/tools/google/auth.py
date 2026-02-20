"""
Shared Google OAuth authentication.

All Google tools share a single token file with combined scopes.
This prevents individual tools from overwriting the token with
a narrower scope set.
"""

import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

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

_REQUIRED_SCOPES = set(ALL_SCOPES)


def _has_all_scopes(creds) -> bool:
    """Check whether credentials carry every required scope."""
    return _REQUIRED_SCOPES.issubset(set(creds.scopes or []))


def _run_full_auth(credentials_path: str):
    """Run the interactive OAuth flow for all scopes."""
    from google_auth_oauthlib.flow import InstalledAppFlow

    if not os.path.exists(credentials_path):
        raise FileNotFoundError(
            f"OAuth credentials file not found: {credentials_path}\n"
            "Download from Google Cloud Console: "
            "https://console.cloud.google.com/apis/credentials"
        )
    flow = InstalledAppFlow.from_client_secrets_file(credentials_path, ALL_SCOPES)
    return flow.run_local_server(port=0)


def get_google_credentials(
    credentials_path: str,
    token_path: str | None = None,
):
    """
    Load or create Google OAuth credentials with ALL combined scopes.

    If the existing token is missing any of the required scopes — even
    after a refresh — a new OAuth flow is triggered so the user grants
    all permissions at once.  The token is saved back to disk after any
    refresh or re-auth.

    Returns:
        google.oauth2.credentials.Credentials
    """
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from local_pigeon.config import get_data_dir

    if token_path is None:
        data_dir = get_data_dir()
        token_path = str(data_dir / "google_token.json")

    creds = None

    # ── 1. Load existing token (no scope filter — we check manually) ────
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path)

    # ── 2. Refresh if expired ────────────────────────────────────────────
    if creds is not None and not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                # Preserve the original scopes list so we can restore it
                # if Google's refresh response omits some.
                original_scopes = list(creds.scopes or [])
                creds.refresh(Request())
                # Google sometimes returns a narrower scope set on refresh.
                # Restore the original (broader) list so the saved token
                # stays complete — the access token is still valid for all
                # scopes the refresh_token was granted.
                if not _has_all_scopes(creds) and _REQUIRED_SCOPES.issubset(set(original_scopes)):
                    logger.debug("Restoring original scopes after refresh (server returned fewer)")
                    creds._scopes = frozenset(original_scopes)
                # Save refreshed token
                with open(token_path, "w") as f:
                    f.write(creds.to_json())
            except Exception:
                logger.warning("Token refresh failed; will re-authorize")
                creds = None

    # ── 3. Check scopes — re-auth if anything is missing ─────────────────
    if creds is not None and not _has_all_scopes(creds):
        logger.info(
            "Token missing scopes %s — re-authorizing",
            _REQUIRED_SCOPES - set(creds.scopes or []),
        )
        creds = _run_full_auth(credentials_path)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    # ── 4. No token at all — first-time auth ─────────────────────────────
    if creds is None:
        creds = _run_full_auth(credentials_path)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return creds
