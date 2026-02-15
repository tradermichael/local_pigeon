"""
Discord Channel Tools

Tools for managing and interacting with Discord channels.
"""

from dataclasses import dataclass, field
from typing import Any, TYPE_CHECKING

from local_pigeon.tools.registry import Tool

if TYPE_CHECKING:
    import discord
    from discord.ext import commands


@dataclass
class DiscordListChannelsTool(Tool):
    """
    List Discord channels the bot has access to.
    
    The agent can use this to discover available channels.
    """
    
    name: str = "discord_list_channels"
    description: str = """List Discord channels the bot can access.
Use this to discover what channels are available in a server.
Returns channel names and IDs."""
    parameters: dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "guild_id": {
                "type": "string",
                "description": "The Discord server (guild) ID to list channels from. If not provided, lists channels from all servers."
            },
            "channel_type": {
                "type": "string",
                "description": "Filter by channel type: 'text', 'voice', or 'all' (default: 'text')",
                "enum": ["text", "voice", "all"],
                "default": "text"
            }
        },
        "required": []
    })
    requires_approval: bool = False
    bot: Any = field(default=None, repr=False)
    
    async def execute(self, user_id: str, **kwargs) -> str:
        """List Discord channels."""
        if not self.bot:
            return "Error: Discord bot not connected."
        
        guild_id = kwargs.get("guild_id")
        channel_type = kwargs.get("channel_type", "text")
        
        try:
            import discord
            
            results = []
            guilds = self.bot.guilds
            
            # Filter to specific guild if provided
            if guild_id:
                guilds = [g for g in guilds if str(g.id) == guild_id]
                if not guilds:
                    return f"Error: Server {guild_id} not found or bot not in that server."
            
            for guild in guilds:
                guild_channels = []
                
                for channel in guild.channels:
                    # Filter by type
                    if channel_type == "text" and not isinstance(channel, discord.TextChannel):
                        continue
                    elif channel_type == "voice" and not isinstance(channel, discord.VoiceChannel):
                        continue
                    
                    if isinstance(channel, discord.TextChannel):
                        guild_channels.append(f"  📝 #{channel.name} (ID: {channel.id})")
                    elif isinstance(channel, discord.VoiceChannel):
                        guild_channels.append(f"  🔊 {channel.name} (ID: {channel.id})")
                    elif isinstance(channel, discord.CategoryChannel):
                        guild_channels.append(f"  📁 {channel.name} (ID: {channel.id})")
                
                if guild_channels:
                    results.append(f"**{guild.name}** (ID: {guild.id}):")
                    results.extend(guild_channels)
                    results.append("")
            
            if not results:
                return "No channels found."
            
            return "Available Discord channels:\n\n" + "\n".join(results)
        except Exception as e:
            return f"Error listing channels: {str(e)}"


@dataclass
class DiscordCreateThreadTool(Tool):
    """
    Create a thread in a Discord channel.
    
    The agent can use this to organize discussions.
    """
    
    name: str = "discord_create_thread"
    description: str = """Create a new thread in a Discord channel.
Use this to start a focused discussion thread."""
    parameters: dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "channel_id": {
                "type": "string",
                "description": "The Discord channel ID to create the thread in"
            },
            "name": {
                "type": "string",
                "description": "The name of the thread (max 100 characters)"
            },
            "message": {
                "type": "string",
                "description": "Optional initial message for the thread"
            },
            "auto_archive_duration": {
                "type": "integer",
                "description": "Minutes until thread auto-archives (60, 1440, 4320, or 10080)",
                "enum": [60, 1440, 4320, 10080],
                "default": 1440
            }
        },
        "required": ["channel_id", "name"]
    })
    requires_approval: bool = False
    bot: Any = field(default=None, repr=False)
    
    async def execute(self, user_id: str, **kwargs) -> str:
        """Create a thread in a Discord channel."""
        if not self.bot:
            return "Error: Discord bot not connected."
        
        channel_id = kwargs.get("channel_id", "")
        name = kwargs.get("name", "")
        message = kwargs.get("message", "")
        auto_archive = kwargs.get("auto_archive_duration", 1440)
        
        if not channel_id or not name:
            return "Error: channel_id and name are required."
        
        # Truncate name if too long
        name = name[:100]
        
        try:
            import discord
            
            channel = self.bot.get_channel(int(channel_id))
            if not channel:
                return f"Error: Channel {channel_id} not found."
            
            if not isinstance(channel, discord.TextChannel):
                return "Error: Threads can only be created in text channels."
            
            # Create thread
            thread = await channel.create_thread(
                name=name,
                auto_archive_duration=auto_archive,
                type=discord.ChannelType.public_thread,
            )
            
            # Send initial message if provided
            if message:
                await thread.send(message)
            
            return f"Thread '{name}' created in #{channel.name} (Thread ID: {thread.id})"
        except ValueError:
            return f"Error: Invalid channel ID format: {channel_id}"
        except Exception as e:
            return f"Error creating thread: {str(e)}"


@dataclass
class DiscordGetServerInfoTool(Tool):
    """
    Get information about Discord servers the bot is in.
    
    The agent can use this to understand the server context.
    """
    
    name: str = "discord_get_server_info"
    description: str = """Get information about Discord servers (guilds) the bot is in.
Returns server names, member counts, and IDs."""
    parameters: dict[str, Any] = field(default_factory=lambda: {
        "type": "object",
        "properties": {
            "guild_id": {
                "type": "string",
                "description": "Optional: specific server ID to get info about. If not provided, lists all servers."
            }
        },
        "required": []
    })
    requires_approval: bool = False
    bot: Any = field(default=None, repr=False)
    
    async def execute(self, user_id: str, **kwargs) -> str:
        """Get Discord server information."""
        if not self.bot:
            return "Error: Discord bot not connected."
        
        guild_id = kwargs.get("guild_id")
        
        try:
            if guild_id:
                guild = self.bot.get_guild(int(guild_id))
                if not guild:
                    return f"Error: Server {guild_id} not found."
                
                return (
                    f"**{guild.name}**\n"
                    f"ID: {guild.id}\n"
                    f"Members: {guild.member_count}\n"
                    f"Owner: {guild.owner}\n"
                    f"Created: {guild.created_at.strftime('%Y-%m-%d')}\n"
                    f"Text Channels: {len(guild.text_channels)}\n"
                    f"Voice Channels: {len(guild.voice_channels)}"
                )
            else:
                results = ["**Bot is in these servers:**\n"]
                for guild in self.bot.guilds:
                    results.append(
                        f"• {guild.name} (ID: {guild.id}) - {guild.member_count} members"
                    )
                return "\n".join(results)
        except ValueError:
            return f"Error: Invalid guild ID format."
        except Exception as e:
            return f"Error getting server info: {str(e)}"
