"""
Google Drive Tool

Provides Google Drive integration for file operations.
Uses OAuth 2.0 for per-user authentication.
"""

import io
from dataclasses import dataclass, field
from typing import Any

from local_pigeon.tools.registry import Tool


def get_drive_service(credentials_path: str, token_path: str | None = None):
    """
    Get an authenticated Drive service.
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
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/drive.file",
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
    
    return build("drive", "v3", credentials=creds)


@dataclass
class DriveTool(Tool):
    """
    Google Drive integration tool.
    
    Supports:
    - Listing files and folders
    - Searching files
    - Reading file content
    - Uploading files
    - Creating folders
    """
    
    name: str = "drive"
    description: str = """Access the USER'S OWN Google Drive (already authorized via OAuth).
The user has explicitly connected their Drive - you have permission to list, read, and manage files on their behalf.

Actions:
- list: List files and folders in the user's Drive
- search: Search for files in the user's Drive
- read: Read content of a text file
- upload: Upload content as a file
- create_folder: Create a new folder

This is the user's own authorized Google Drive account."""
    parameters: dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list", "search", "read", "upload", "create_folder"],
                "description": "The action to perform"
            },
            "query": {
                "type": "string",
                "description": "Search query (for search action)"
            },
            "file_id": {
                "type": "string",
                "description": "File ID (for read action)"
            },
            "folder_id": {
                "type": "string",
                "description": "Parent folder ID (for list/upload, default: root)"
            },
            "file_name": {
                "type": "string",
                "description": "File name (for upload/create_folder action)"
            },
            "content": {
                "type": "string",
                "description": "File content (for upload action)"
            },
            "mime_type": {
                "type": "string",
                "description": "MIME type (for upload, default: text/plain)",
                "default": "text/plain"
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum results (default: 20)",
                "default": 20
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
        """Get or create Drive service."""
        if not self._service:
            self._service = get_drive_service(self._credentials_path)
        return self._service
    
    async def execute(self, user_id: str, **kwargs) -> str:
        """Execute a Drive action."""
        action = kwargs.get("action", "")
        
        if not action:
            return "Error: No action specified. Use: list, search, read, upload, or create_folder"
        
        try:
            if action == "list":
                return await self._list_files(
                    folder_id=kwargs.get("folder_id", "root"),
                    max_results=kwargs.get("max_results", 20),
                )
            elif action == "search":
                query = kwargs.get("query", "")
                if not query:
                    return "Error: Search query required"
                return await self._search_files(query, kwargs.get("max_results", 20))
            elif action == "read":
                file_id = kwargs.get("file_id", "")
                if not file_id:
                    return "Error: File ID required for read action"
                return await self._read_file(file_id)
            elif action == "upload":
                return await self._upload_file(
                    file_name=kwargs.get("file_name", ""),
                    content=kwargs.get("content", ""),
                    folder_id=kwargs.get("folder_id", "root"),
                    mime_type=kwargs.get("mime_type", "text/plain"),
                )
            elif action == "create_folder":
                folder_name = kwargs.get("file_name", "")
                if not folder_name:
                    return "Error: Folder name required"
                return await self._create_folder(
                    folder_name=folder_name,
                    parent_id=kwargs.get("folder_id", "root"),
                )
            else:
                return f"Error: Unknown action '{action}'"
                
        except FileNotFoundError as e:
            return str(e)
        except Exception as e:
            return f"Error with Drive: {str(e)}"
    
    async def _list_files(self, folder_id: str, max_results: int) -> str:
        """List files in a folder."""
        service = self._get_service()
        
        # Build query to exclude trashed files and auto-generated system files
        if folder_id == "root":
            # For root, get recent files owned by user (not shared from email)
            query = "'root' in parents and trashed = false"
        else:
            query = f"'{folder_id}' in parents and trashed = false"
        
        results = service.files().list(
            q=query,
            pageSize=max_results,
            fields="files(id, name, mimeType, size, modifiedTime, owners)",
            orderBy="modifiedTime desc",
        ).execute()
        
        files = results.get("files", [])
        
        if not files:
            return "No files found in this folder."
        
        # Group by type for better readability
        folders = []
        documents = []
        spreadsheets = []
        other_files = []
        
        for f in files:
            mime = f.get("mimeType", "")
            if mime == "application/vnd.google-apps.folder":
                folders.append(f)
            elif mime in [
                "application/vnd.google-apps.document",
                "application/vnd.google-apps.presentation",
            ]:
                documents.append(f)
            elif mime == "application/vnd.google-apps.spreadsheet":
                spreadsheets.append(f)
            else:
                other_files.append(f)
        
        output = "**Your Google Drive Files:**\n\n"
        
        def format_file(f, icon):
            size = f.get("size", "")
            size_str = ""
            if size:
                size_kb = int(size) / 1024
                size_str = f" ({size_kb:.1f} KB)"
            modified = f.get("modifiedTime", "")[:10] if f.get("modifiedTime") else ""
            return f"{icon} **{f['name']}**{size_str}\n   ID: `{f['id']}` | Modified: {modified}\n"
        
        if folders:
            output += "📁 **Folders:**\n"
            for f in folders[:5]:
                output += format_file(f, "📁")
            if len(folders) > 5:
                output += f"   ... and {len(folders) - 5} more folders\n"
            output += "\n"
        
        if documents:
            output += "📝 **Documents:**\n"
            for f in documents[:5]:
                output += format_file(f, "📝")
            if len(documents) > 5:
                output += f"   ... and {len(documents) - 5} more documents\n"
            output += "\n"
        
        if spreadsheets:
            output += "📊 **Spreadsheets:**\n"
            for f in spreadsheets[:5]:
                output += format_file(f, "📊")
            if len(spreadsheets) > 5:
                output += f"   ... and {len(spreadsheets) - 5} more spreadsheets\n"
            output += "\n"
        
        if other_files:
            output += "📄 **Other Files:**\n"
            for f in other_files[:5]:
                output += format_file(f, "📄")
            if len(other_files) > 5:
                output += f"   ... and {len(other_files) - 5} more files\n"
        
        return output
    
    async def _search_files(self, query: str, max_results: int) -> str:
        """Search for files."""
        service = self._get_service()
        
        # Build search query
        search_query = f"name contains '{query}' and trashed = false"
        
        results = service.files().list(
            q=search_query,
            pageSize=max_results,
            fields="files(id, name, mimeType, size, modifiedTime, parents)",
            orderBy="modifiedTime desc",
        ).execute()
        
        files = results.get("files", [])
        
        if not files:
            return f"No files found matching: {query}"
        
        output = f"Search results for: {query}\n\n"
        for f in files:
            icon = "📁" if f["mimeType"] == "application/vnd.google-apps.folder" else "📄"
            
            output += f"{icon} {f['name']}\n"
            output += f"   ID: {f['id']}\n"
            output += f"   Type: {f['mimeType']}\n"
            output += f"   Modified: {f.get('modifiedTime', 'Unknown')[:10]}\n\n"
        
        return output
    
    async def _read_file(self, file_id: str) -> str:
        """Read content of a file."""
        from googleapiclient.http import MediaIoBaseDownload
        
        service = self._get_service()
        
        # Get file metadata
        file_meta = service.files().get(
            fileId=file_id,
            fields="name, mimeType, size",
        ).execute()
        
        mime_type = file_meta.get("mimeType", "")
        
        # Handle Google Docs types
        export_mime = None
        if mime_type == "application/vnd.google-apps.document":
            export_mime = "text/plain"
        elif mime_type == "application/vnd.google-apps.spreadsheet":
            export_mime = "text/csv"
        elif mime_type == "application/vnd.google-apps.presentation":
            export_mime = "text/plain"
        
        # Download or export
        buffer = io.BytesIO()
        
        if export_mime:
            request = service.files().export_media(fileId=file_id, mimeType=export_mime)
        else:
            request = service.files().get_media(fileId=file_id)
        
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        
        # Decode content
        buffer.seek(0)
        try:
            content = buffer.read().decode("utf-8")
        except UnicodeDecodeError:
            return f"Error: File '{file_meta['name']}' is not a text file."
        
        # Truncate if too long
        max_len = 10000
        if len(content) > max_len:
            content = content[:max_len] + "\n\n[Content truncated...]"
        
        return f"Content of: {file_meta['name']}\n\n{content}"
    
    async def _upload_file(
        self,
        file_name: str,
        content: str,
        folder_id: str,
        mime_type: str,
    ) -> str:
        """Upload content as a file."""
        from googleapiclient.http import MediaInMemoryUpload
        
        if not file_name:
            return "Error: File name is required"
        if not content:
            return "Error: Content is required"
        
        service = self._get_service()
        
        file_metadata = {
            "name": file_name,
            "parents": [folder_id] if folder_id else [],
        }
        
        media = MediaInMemoryUpload(
            content.encode("utf-8"),
            mimetype=mime_type,
            resumable=True,
        )
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields="id, name, webViewLink",
        ).execute()
        
        return f"✅ File uploaded successfully!\n\nName: {file['name']}\nID: {file['id']}\nLink: {file.get('webViewLink', 'N/A')}"
    
    async def _create_folder(self, folder_name: str, parent_id: str) -> str:
        """Create a new folder."""
        service = self._get_service()
        
        file_metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_id] if parent_id else [],
        }
        
        folder = service.files().create(
            body=file_metadata,
            fields="id, name, webViewLink",
        ).execute()
        
        return f"✅ Folder created successfully!\n\nName: {folder['name']}\nID: {folder['id']}\nLink: {folder.get('webViewLink', 'N/A')}"
