"""
Discord Bot Adapter

Integrates Local Pigeon with Discord using discord.py.
Supports:
- Message handling (mentions and direct messages)
- Streaming responses with message edits
- Slash commands for model switching
- Payment approval with reaction buttons
"""

import asyncio
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from local_pigeon.platforms.base import BasePlatformAdapter

if TYPE_CHECKING:
    from local_pigeon.core.agent import LocalPigeonAgent, PendingApproval
    from local_pigeon.config import DiscordSettings


class DiscordAdapter(BasePlatformAdapter):
    """
    Discord platform adapter.
    
    Handles:
    - Bot initialization and connection
    - Message processing
    - Streaming responses
    - Approval workflows
    """
    
    def __init__(
        self,
        agent: "LocalPigeonAgent",
        settings: "DiscordSettings",
    ):
        super().__init__(agent, "discord")
        self.settings = settings
        
        # Set up intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.dm_messages = True
        
        # Create bot
        self.bot = commands.Bot(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )
        
        # Pending approvals
        self._pending_approvals: dict[str, asyncio.Future[bool]] = {}
        
        # Register event handlers
        self._setup_handlers()
    
    def _setup_handlers(self) -> None:
        """Set up Discord event handlers."""
        
        @self.bot.event
        async def on_ready():
            print(f"Discord bot logged in as {self.bot.user}")
            
            # Register Discord tools with the agent
            self.agent.register_discord_tools(self.bot)
            
            # Sync slash commands
            try:
                synced = await self.bot.tree.sync()
                print(f"Synced {len(synced)} slash commands")
            except Exception as e:
                print(f"Failed to sync commands: {e}")
        
        @self.bot.event
        async def on_message(message: discord.Message):
            # Ignore own messages
            if message.author == self.bot.user:
                return
            
            # Check if we should respond
            should_respond = False
            
            # DMs
            if isinstance(message.channel, discord.DMChannel):
                should_respond = True
            
            # Mentions
            elif self.bot.user and self.bot.user.mentioned_in(message):
                should_respond = True
            
            # Non-mention mode (if configured)
            elif not self.settings.mention_only:
                # Check allowed channels
                if not self.settings.allowed_channels:
                    should_respond = True
                elif str(message.channel.id) in self.settings.allowed_channels:
                    should_respond = True
            
            if not should_respond:
                return
            
            # Extract message content (remove mention)
            content = message.content
            if self.bot.user:
                content = content.replace(f"<@{self.bot.user.id}>", "").strip()
                content = content.replace(f"<@!{self.bot.user.id}>", "").strip()
            
            # Extract images from attachments
            images = await self._extract_images(message)
            
            # Allow messages with just images (no text content required)
            if not content and not images:
                return
            
            # If only images, add a default prompt
            if not content and images:
                content = "What's in this image?"
            
            # Show typing indicator
            if self.settings.show_typing:
                async with message.channel.typing():
                    await self._process_message(message, content, images)
            else:
                await self._process_message(message, content, images)
        
        # Slash commands
        @self.bot.tree.command(name="model", description="Switch the AI model")
        @app_commands.describe(model="The model name to switch to")
        async def model_command(interaction: discord.Interaction, model: str):
            # Check if user is admin
            if self.settings.admin_users and str(interaction.user.id) not in self.settings.admin_users:
                await interaction.response.send_message(
                    "❌ You don't have permission to change the model.",
                    ephemeral=True,
                )
                return
            
            self.agent.set_model(model)
            await interaction.response.send_message(
                f"✅ Model switched to: **{model}**",
                ephemeral=True,
            )
        
        @self.bot.tree.command(name="clear", description="Clear conversation history")
        async def clear_command(interaction: discord.Interaction):
            user_id = str(interaction.user.id)
            await self.agent.clear_history(user_id)
            await interaction.response.send_message(
                "✅ Conversation history cleared.",
                ephemeral=True,
            )
        
        @self.bot.tree.command(name="status", description="Check bot status")
        async def status_command(interaction: discord.Interaction):
            model = self.agent.settings.ollama.model
            await interaction.response.send_message(
                f"🐦 **Local Pigeon Status**\n\n"
                f"Model: `{model}`\n"
                f"Platform: Discord\n"
                f"Status: Online",
                ephemeral=True,
            )
    
    async def _extract_images(self, message: discord.Message) -> list[str]:
        """
        Extract images from Discord message attachments.
        
        Downloads image attachments and converts them to base64 for vision models.
        Supports common image formats: PNG, JPG, JPEG, GIF, WEBP.
        
        Returns:
            List of base64-encoded image strings
        """
        import base64
        import aiohttp
        
        images = []
        image_types = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
        
        for attachment in message.attachments:
            # Check if it's an image
            filename_lower = attachment.filename.lower()
            is_image = any(filename_lower.endswith(ext) for ext in image_types)
            is_image = is_image or (attachment.content_type and attachment.content_type.startswith("image/"))
            
            if not is_image:
                continue
            
            try:
                # Download the image
                async with aiohttp.ClientSession() as session:
                    async with session.get(attachment.url) as resp:
                        if resp.status == 200:
                            image_data = await resp.read()
                            # Convert to base64
                            b64_image = base64.b64encode(image_data).decode("utf-8")
                            images.append(b64_image)
            except Exception as e:
                print(f"Failed to download image attachment: {e}")
                continue
        
        return images
    
    async def _process_message(
        self,
        message: discord.Message,
        content: str,
        images: list[str] | None = None,
    ) -> None:
        """Process a user message and send response."""
        user_id = str(message.author.id)
        session_id = str(message.channel.id)
        
        # Check for approval responses
        if content.lower() in ("approve", "yes", "y"):
            if self._handle_approval_response(user_id, True):
                await message.add_reaction("✅")
                return
        elif content.lower() in ("deny", "no", "n"):
            if self._handle_approval_response(user_id, False):
                await message.add_reaction("❌")
                return
        
        # Send initial response
        response_msg = await message.reply("🤔 Thinking...")
        
        # Collect streamed response
        full_response = ""
        last_update = 0
        update_interval = 1.0  # Update message every 1 second
        
        async def stream_callback(chunk: str):
            nonlocal full_response, last_update
            full_response += chunk
            
            # Rate limit message edits
            import time
            current_time = time.time()
            if current_time - last_update > update_interval:
                last_update = current_time
                # Truncate if too long for Discord
                display = full_response[:1900] + "..." if len(full_response) > 1900 else full_response
                try:
                    await response_msg.edit(content=display)
                except discord.errors.HTTPException:
                    pass
        
        try:
            # Get agent response
            response = await self.agent.chat(
                user_message=content,
                user_id=user_id,
                session_id=session_id,
                platform="discord",
                stream_callback=stream_callback,
                images=images,
            )
            
            # Send final response (may need to split)
            await self._send_long_message(response_msg, response)
            
        except asyncio.TimeoutError:
            await response_msg.edit(content="⏰ Response timed out. The model may be too slow. Try a faster model like `gemma3:latest`.")
        except Exception as e:
            import traceback
            print(f"Discord error processing message: {e}")
            traceback.print_exc()
            await response_msg.edit(content=f"❌ Error: {str(e)[:200]}")
    
    async def _send_long_message(
        self,
        initial_message: discord.Message,
        content: str,
    ) -> None:
        """Send a long message, splitting if necessary."""
        max_len = self.settings.max_message_length
        
        if len(content) <= max_len:
            await initial_message.edit(content=content)
            return
        
        # Split into chunks
        chunks = []
        while content:
            if len(content) <= max_len:
                chunks.append(content)
                break
            
            # Find a good split point
            split_at = content.rfind("\n", 0, max_len)
            if split_at == -1:
                split_at = content.rfind(" ", 0, max_len)
            if split_at == -1:
                split_at = max_len
            
            chunks.append(content[:split_at])
            content = content[split_at:].lstrip()
        
        # Edit first message with first chunk
        await initial_message.edit(content=chunks[0])
        
        # Send remaining chunks as new messages
        for chunk in chunks[1:]:
            await initial_message.channel.send(chunk)
    
    def _handle_approval_response(self, user_id: str, approved: bool) -> bool:
        """Handle an approval response from a user."""
        # Find pending approval for this user
        for key, future in list(self._pending_approvals.items()):
            if key.startswith(user_id) and not future.done():
                future.set_result(approved)
                return True
        return False
    
    async def start(self) -> None:
        """Start the Discord bot."""
        if not self.settings.bot_token:
            raise ValueError("Discord bot token not configured")
        
        # Register approval handler
        self.register_with_agent()
        
        # Start bot
        await self.bot.start(self.settings.bot_token)
    
    async def stop(self) -> None:
        """Stop the Discord bot."""
        await self.bot.close()
    
    async def send_message(
        self,
        user_id: str,
        message: str,
        channel_id: str | None = None,
        **kwargs,
    ) -> None:
        """Send a message to a user or channel."""
        if channel_id:
            channel = self.bot.get_channel(int(channel_id))
            if channel and isinstance(channel, discord.TextChannel):
                await channel.send(message)
        else:
            user = await self.bot.fetch_user(int(user_id))
            if user:
                await user.send(message)
    
    async def request_approval(
        self,
        pending: "PendingApproval",
    ) -> bool:
        """Send approval request and wait for response."""
        # Create approval message
        approval_text = f"""🔐 **Payment Approval Required**

**Tool:** {pending.tool_name}
**Amount:** ${pending.amount:.2f}
**Description:** {pending.description}

Reply with **approve** or **deny** within 5 minutes."""
        
        # Create future for response
        key = f"{pending.user_id}_{pending.id}"
        future: asyncio.Future[bool] = asyncio.Future()
        self._pending_approvals[key] = future
        
        try:
            # Send DM to user
            user = await self.bot.fetch_user(int(pending.user_id))
            if user:
                await user.send(approval_text)
            else:
                return False
            
            # Wait for response
            return await asyncio.wait_for(future, timeout=300)
            
        except asyncio.TimeoutError:
            return False
        except Exception:
            return False
        finally:
            # Cleanup
            if key in self._pending_approvals:
                del self._pending_approvals[key]
