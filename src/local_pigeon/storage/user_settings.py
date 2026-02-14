"""
User Settings Store

Per-user configuration and preferences.
"""

import json
from typing import Any
from pydantic import BaseModel

from local_pigeon.storage.database import Database


class UserSettings(BaseModel):
    """
    User-specific settings.
    
    These override global settings on a per-user basis.
    """
    
    # Payment approval settings
    payment_approval_threshold: float = 25.0
    auto_approve_trusted_merchants: bool = False
    trusted_merchants: list[str] = []
    
    # Model preferences
    preferred_model: str | None = None
    temperature: float = 0.7
    max_tokens: int = 2048
    
    # Tool settings
    enabled_tools: list[str] | None = None  # None = all tools
    disabled_tools: list[str] = []
    
    # Privacy settings
    save_conversation_history: bool = True
    allow_tool_logging: bool = True
    
    # Notification settings
    notify_on_payment_request: bool = True
    notify_on_tool_error: bool = True
    
    # Timezone for calendar/scheduling
    timezone: str = "UTC"


class UserSettingsStore:
    """
    Store for per-user settings.
    
    Settings are JSON-serialized and stored in SQLite.
    """
    
    def __init__(self, database: Database):
        self.database = database
        self._cache: dict[str, UserSettings] = {}
    
    async def get(self, user_id: str) -> UserSettings:
        """
        Get settings for a user.
        
        Returns default settings if none exist.
        """
        # Check cache first
        if user_id in self._cache:
            return self._cache[user_id]
        
        # Load from database
        async with self.database.connection() as db:
            cursor = await db.execute(
                "SELECT settings FROM user_settings WHERE user_id = ?",
                (user_id,),
            )
            row = await cursor.fetchone()
        
        if row:
            settings_dict = json.loads(row["settings"])
            settings = UserSettings(**settings_dict)
        else:
            settings = UserSettings()
        
        # Cache and return
        self._cache[user_id] = settings
        return settings
    
    async def save(
        self,
        user_id: str,
        settings: UserSettings,
    ) -> None:
        """Save settings for a user."""
        settings_json = settings.model_dump_json()
        
        async with self.database.connection() as db:
            await db.execute(
                """
                INSERT INTO user_settings (user_id, settings)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    settings = excluded.settings,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (user_id, settings_json),
            )
            await db.commit()
        
        # Update cache
        self._cache[user_id] = settings
    
    async def update(
        self,
        user_id: str,
        **updates: Any,
    ) -> UserSettings:
        """
        Update specific settings for a user.
        
        Returns the updated settings.
        """
        settings = await self.get(user_id)
        
        # Apply updates
        settings_dict = settings.model_dump()
        settings_dict.update(updates)
        
        new_settings = UserSettings(**settings_dict)
        await self.save(user_id, new_settings)
        
        return new_settings
    
    async def delete(self, user_id: str) -> bool:
        """Delete settings for a user."""
        async with self.database.connection() as db:
            cursor = await db.execute(
                "DELETE FROM user_settings WHERE user_id = ?",
                (user_id,),
            )
            await db.commit()
        
        # Clear cache
        if user_id in self._cache:
            del self._cache[user_id]
        
        return cursor.rowcount > 0
    
    async def get_payment_threshold(self, user_id: str) -> float:
        """Get the payment approval threshold for a user."""
        settings = await self.get(user_id)
        return settings.payment_approval_threshold
    
    async def set_payment_threshold(
        self,
        user_id: str,
        threshold: float,
    ) -> None:
        """Set the payment approval threshold for a user."""
        await self.update(user_id, payment_approval_threshold=threshold)
    
    async def is_tool_enabled(
        self,
        user_id: str,
        tool_name: str,
    ) -> bool:
        """Check if a specific tool is enabled for a user."""
        settings = await self.get(user_id)
        
        # Check disabled list first
        if tool_name in settings.disabled_tools:
            return False
        
        # Check enabled list if specified
        if settings.enabled_tools is not None:
            return tool_name in settings.enabled_tools
        
        # Default: all tools enabled
        return True
    
    async def add_trusted_merchant(
        self,
        user_id: str,
        merchant: str,
    ) -> None:
        """Add a trusted merchant for auto-approval."""
        settings = await self.get(user_id)
        
        if merchant not in settings.trusted_merchants:
            new_list = settings.trusted_merchants + [merchant]
            await self.update(user_id, trusted_merchants=new_list)
    
    async def should_auto_approve(
        self,
        user_id: str,
        merchant: str | None,
        amount: float,
    ) -> bool:
        """
        Check if a payment should be auto-approved.
        
        Returns True if:
        - Amount is below threshold, OR
        - Merchant is trusted AND auto_approve_trusted_merchants is enabled
        """
        settings = await self.get(user_id)
        
        # Below threshold
        if amount <= settings.payment_approval_threshold:
            return True
        
        # Trusted merchant
        if (
            settings.auto_approve_trusted_merchants
            and merchant
            and merchant in settings.trusted_merchants
        ):
            return True
        
        return False
    
    def clear_cache(self) -> None:
        """Clear the settings cache."""
        self._cache.clear()
    
    def invalidate_cache(self, user_id: str) -> None:
        """Invalidate cache for a specific user."""
        if user_id in self._cache:
            del self._cache[user_id]
