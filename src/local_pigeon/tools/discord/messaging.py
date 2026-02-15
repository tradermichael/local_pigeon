"""
Discord Messaging Tools

Tools for sending messages, reactions, and reading messages on Discord.
"""

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from local_pigeon.tools.registry import Tool

if TYPE_CHECKING:
    import discord
    from discord.ext import commands


@dataclass
class DiscordSendMessageTool(Tool):
    """
    Send a message to a Discord channel.
    
    The agent can use this to send messages to channels it has access to.
    """
    
    name: str = "discord_send_message"
    description: str = """Send a message to a Discord channel.
Use this to post messages, announcements, or respond in a specific channel.
You need the channel ID or channel name."""
    parameters: dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "channel_id": {
                "type": "string",
                "description": "The Discord channel ID to send the message to"
            },
            "message": {
                "type": "string",
                "description": "The message content to send"
            }
        },
        "required": ["channel_id", "message"]
    })
    requires_approval: bool = False
    bot: Any = field(default=None, repr=False)
    
    async def execute(self, user_id: str, **kwargs) -> str:
        """Send a message to a Discord channel."""
        if not self.bot:
            return "Error: Discord bot not connected."
        
        channel_id = kwargs.get("channel_id", "")
        message = kwargs.get("message", "")
        
        if not channel_id:
            return "Error: No channel_id provided."
        if not message:
            return "Error: No message provided."
        
        try:
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                return f"Error: Channel {channel_id} not found. Make sure the bot has access to this channel."
            
            await channel.send(message)
            return f"Message sent to #{channel.name} (ID: {channel_id})"
        except ValueError:
            return f"Error: Invalid channel ID format: {channel_id}"
        except Exception as e:
            return f"Error sending message: {str(e)}"


@dataclass
class DiscordSendDMTool(Tool):
    """
    Send a direct message to a Discord user.
    
    The agent can use this to DM users privately.
    """
    
    name: str = "discord_send_dm"
    description: str = """Send a direct message (DM) to a Discord user.
Use this to send private messages to a user."""
    parameters: dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "target_user_id": {
                "type": "string",
                "description": "The Discord user ID to send the DM to"
            },
            "message": {
                "type": "string",
                "description": "The message content to send"
            }
        },
        "required": ["target_user_id", "message"]
    })
    requires_approval: bool = False
    bot: Any = field(default=None, repr=False)
    
    async def execute(self, user_id: str, **kwargs) -> str:
        """Send a DM to a Discord user."""
        if not self.bot:
            return "Error: Discord bot not connected."
        
        target_user_id = kwargs.get("target_user_id", "")
        message = kwargs.get("message", "")
        
        if not target_user_id:
            return "Error: No target_user_id provided."
        if not message:
            return "Error: No message provided."
        
        try:
            user = await self.bot.fetch_user(int(target_user_id))
            if not user:
                return f"Error: User {target_user_id} not found."
            
            await user.send(message)
            return f"DM sent to {user.name}#{user.discriminator} (ID: {target_user_id})"
        except ValueError:
            return f"Error: Invalid user ID format: {target_user_id}"
        except Exception as e:
            return f"Error sending DM: {str(e)}"


@dataclass
class DiscordGetMessagesTool(Tool):
    """
    Get recent messages from a Discord channel.
    
    The agent can use this to read channel history.
    """
    
    name: str = "discord_get_messages"
    description: str = """Get recent messages from a Discord channel.
Use this to read the conversation history in a channel.
Returns the most recent messages with author and content."""
    parameters: dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "channel_id": {
                "type": "string",
                "description": "The Discord channel ID to read messages from"
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of messages to retrieve (default: 10, max: 50)",
                "default": 10
            }
        },
        "required": ["channel_id"]
    })
    requires_approval: bool = False
    bot: Any = field(default=None, repr=False)
    
    async def execute(self, user_id: str, **kwargs) -> str:
        """Get recent messages from a Discord channel."""
        if not self.bot:
            return "Error: Discord bot not connected."
        
        channel_id = kwargs.get("channel_id", "")
        limit = min(kwargs.get("limit", 10), 50)  # Cap at 50
        
        if not channel_id:
            return "Error: No channel_id provided."
        
        try:
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                return f"Error: Channel {channel_id} not found."
            
            messages = []
            async for msg in channel.history(limit=limit):
                timestamp = msg.created_at.strftime("%Y-%m-%d %H:%M")
                messages.append(f"[{timestamp}] {msg.author.name}: {msg.content}")
            
            if not messages:
                return f"No messages found in #{channel.name}"
            
            messages.reverse()  # Oldest first
            result = f"Recent messages from #{channel.name}:\n\n"
            result += "\n".join(messages)
            return result
        except ValueError:
            return f"Error: Invalid channel ID format: {channel_id}"
        except Exception as e:
            return f"Error fetching messages: {str(e)}"


@dataclass
class DiscordAddReactionTool(Tool):
    """
    Add a reaction to a Discord message.
    
    The agent can use this to react to messages with emojis.
    """
    
    name: str = "discord_add_reaction"
    description: str = """Add an emoji reaction to a Discord message.
Use this to react to a message with an emoji."""
    parameters: dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "channel_id": {
                "type": "string",
                "description": "The Discord channel ID where the message is"
            },
            "message_id": {
                "type": "string",
                "description": "The Discord message ID to react to"
            },
            "emoji": {
                "type": "string",
                "description": "The emoji to react with (e.g., '👍', '❤️', '🎉')"
            }
        },
        "required": ["channel_id", "message_id", "emoji"]
    })
    requires_approval: bool = False
    bot: Any = field(default=None, repr=False)
    
    async def execute(self, user_id: str, **kwargs) -> str:
        """Add a reaction to a Discord message."""
        if not self.bot:
            return "Error: Discord bot not connected."
        
        channel_id = kwargs.get("channel_id", "")
        message_id = kwargs.get("message_id", "")
        emoji = kwargs.get("emoji", "")
        
        if not all([channel_id, message_id, emoji]):
            return "Error: channel_id, message_id, and emoji are all required."
        
        try:
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                return f"Error: Channel {channel_id} not found."
            
            message = await channel.fetch_message(int(message_id))
            await message.add_reaction(emoji)
            return f"Added {emoji} reaction to message in #{channel.name}"
        except ValueError:
            return "Error: Invalid channel or message ID format."
        except Exception as e:
            return f"Error adding reaction: {str(e)}"
