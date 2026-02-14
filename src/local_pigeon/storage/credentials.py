"""
Credential Store

Encrypted storage for OAuth tokens and API credentials.
"""

import json
import base64
import hashlib
import secrets
from pathlib import Path
from typing import Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from local_pigeon.storage.database import Database


class CredentialStore:
    """
    Encrypted credential storage.
    
    Uses Fernet symmetric encryption derived from a master password.
    Each user's credentials are encrypted separately.
    """
    
    def __init__(
        self,
        database: Database,
        encryption_key: str | None = None,
        key_file: str | Path | None = None,
    ):
        self.database = database
        self._fernet: Fernet | None = None
        
        # Load or generate encryption key
        if encryption_key:
            self._init_from_password(encryption_key)
        elif key_file:
            self._init_from_keyfile(Path(key_file))
        else:
            # Generate a new key and store it
            self._generate_key()
    
    def _init_from_password(self, password: str) -> None:
        """Derive encryption key from password."""
        # Use a fixed salt for consistency
        # In production, you'd want a unique salt per installation
        salt = b"local_pigeon_salt_v1"
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        self._fernet = Fernet(key)
    
    def _init_from_keyfile(self, key_file: Path) -> None:
        """Load encryption key from file."""
        if key_file.exists():
            key = key_file.read_bytes()
            self._fernet = Fernet(key)
        else:
            # Generate new key and save
            key = Fernet.generate_key()
            key_file.parent.mkdir(parents=True, exist_ok=True)
            key_file.write_bytes(key)
            key_file.chmod(0o600)  # Restrict permissions
            self._fernet = Fernet(key)
    
    def _generate_key(self) -> None:
        """Generate a new encryption key."""
        key = Fernet.generate_key()
        self._fernet = Fernet(key)
    
    def _encrypt(self, data: dict[str, Any]) -> bytes:
        """Encrypt data to bytes."""
        if not self._fernet:
            raise RuntimeError("Encryption not initialized")
        
        json_bytes = json.dumps(data).encode("utf-8")
        return self._fernet.encrypt(json_bytes)
    
    def _decrypt(self, encrypted: bytes) -> dict[str, Any]:
        """Decrypt bytes to data."""
        if not self._fernet:
            raise RuntimeError("Encryption not initialized")
        
        json_bytes = self._fernet.decrypt(encrypted)
        return json.loads(json_bytes.decode("utf-8"))
    
    async def store(
        self,
        user_id: str,
        service: str,
        credentials: dict[str, Any],
    ) -> None:
        """
        Store encrypted credentials for a user.
        
        Args:
            user_id: User identifier
            service: Service name (e.g., "google", "stripe")
            credentials: Credential data to store
        """
        encrypted = self._encrypt(credentials)
        
        async with self.database.connection() as db:
            await db.execute(
                """
                INSERT INTO credentials (user_id, service, encrypted_data)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id, service) DO UPDATE SET
                    encrypted_data = excluded.encrypted_data,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, service, encrypted),
            )
            await db.commit()
    
    async def retrieve(
        self,
        user_id: str,
        service: str,
    ) -> dict[str, Any] | None:
        """
        Retrieve decrypted credentials for a user.
        
        Returns None if credentials don't exist.
        """
        async with self.database.connection() as db:
            cursor = await db.execute(
                """
                SELECT encrypted_data FROM credentials
                WHERE user_id = ? AND service = ?
                """,
                (user_id, service),
            )
            row = await cursor.fetchone()
        
        if not row:
            return None
        
        try:
            return self._decrypt(row["encrypted_data"])
        except Exception:
            return None
    
    async def delete(
        self,
        user_id: str,
        service: str,
    ) -> bool:
        """
        Delete credentials for a user.
        
        Returns True if credentials were deleted.
        """
        async with self.database.connection() as db:
            cursor = await db.execute(
                """
                DELETE FROM credentials
                WHERE user_id = ? AND service = ?
                """,
                (user_id, service),
            )
            await db.commit()
            return cursor.rowcount > 0
    
    async def list_services(
        self,
        user_id: str,
    ) -> list[str]:
        """List all services with stored credentials for a user."""
        async with self.database.connection() as db:
            cursor = await db.execute(
                """
                SELECT service FROM credentials
                WHERE user_id = ?
                ORDER BY service
                """,
                (user_id,),
            )
            rows = await cursor.fetchall()
        
        return [row["service"] for row in rows]
    
    async def has_credentials(
        self,
        user_id: str,
        service: str,
    ) -> bool:
        """Check if credentials exist for a user and service."""
        async with self.database.connection() as db:
            cursor = await db.execute(
                """
                SELECT 1 FROM credentials
                WHERE user_id = ? AND service = ?
                """,
                (user_id, service),
            )
            row = await cursor.fetchone()
        
        return row is not None


class GoogleCredentialStore:
    """
    Specialized store for Google OAuth credentials.
    
    Handles token refresh and expiration.
    """
    
    def __init__(self, credential_store: CredentialStore):
        self.store = credential_store
    
    async def store_tokens(
        self,
        user_id: str,
        access_token: str,
        refresh_token: str | None,
        expires_at: float | None,
        scopes: list[str],
    ) -> None:
        """Store Google OAuth tokens."""
        await self.store.store(
            user_id=user_id,
            service="google",
            credentials={
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_at": expires_at,
                "scopes": scopes,
            },
        )
    
    async def get_tokens(
        self,
        user_id: str,
    ) -> dict[str, Any] | None:
        """Get Google OAuth tokens."""
        return await self.store.retrieve(user_id, "google")
    
    async def is_token_valid(
        self,
        user_id: str,
    ) -> bool:
        """Check if the stored token is still valid."""
        import time
        
        tokens = await self.get_tokens(user_id)
        if not tokens:
            return False
        
        expires_at = tokens.get("expires_at")
        if expires_at is None:
            return True  # No expiration set
        
        # Add 5 minute buffer
        return time.time() < (expires_at - 300)
    
    async def delete_tokens(
        self,
        user_id: str,
    ) -> bool:
        """Delete Google OAuth tokens."""
        return await self.store.delete(user_id, "google")
