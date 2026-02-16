"""
Telegram Bot Adapter

Integrates Local Pigeon with Telegram using aiogram.
Supports:
- Message handling with user whitelist
- Streaming responses with message edits
- Commands for model switching
- Payment approval with inline keyboards
"""

import asyncio
from typing import TYPE_CHECKING

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from local_pigeon.platforms.base import BasePlatformAdapter

if TYPE_CHECKING:
    from local_pigeon.core.agent import LocalPigeonAgent, PendingApproval
    from local_pigeon.config import TelegramSettings


class TelegramAdapter(BasePlatformAdapter):
    """
    Telegram platform adapter.
    
    Handles:
    - Bot initialization
    - Message processing with user filtering
    - Streaming responses
    - Approval workflows with inline keyboards
    """
    
    def __init__(
        self,
        agent: "LocalPigeonAgent",
        settings: "TelegramSettings",
    ):
        super().__init__(agent, "telegram")
        self.settings = settings
        
        # Create bot and dispatcher
        self.bot = Bot(
            token=settings.bot_token,
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML if settings.parse_mode == "HTML" else ParseMode.MARKDOWN,
            ),
        )
        self.dp = Dispatcher()
        
        # Pending approvals
        self._pending_approvals: dict[str, asyncio.Future[bool]] = {}
        
        # Register handlers
        self._setup_handlers()
    
    def _setup_handlers(self) -> None:
        """Set up Telegram message handlers."""
        
        @self.dp.message(CommandStart())
        async def start_handler(message: Message):
            if not self._is_allowed_user(message.from_user.id if message.from_user else 0):
                await message.answer("❌ You are not authorized to use this bot.")
                return
            
            await message.answer(
                "🐦 <b>Welcome to Local Pigeon!</b>\n\n"
                "I'm your local AI assistant powered by Ollama.\n\n"
                "Just send me a message to start chatting!\n\n"
                "<b>Commands:</b>\n"
                "/model &lt;name&gt; - Switch AI model\n"
                "/clear - Clear conversation history\n"
                "/status - Check bot status"
            )
        
        @self.dp.message(Command("model"))
        async def model_handler(message: Message):
            if not self._is_allowed_user(message.from_user.id if message.from_user else 0):
                return
            
            # Extract model name from command
            text = message.text or ""
            parts = text.split(maxsplit=1)
            
            if len(parts) < 2:
                await message.answer(
                    "Usage: /model &lt;model_name&gt;\n\n"
                    "Examples:\n"
                    "  /model gemma3:latest\n"
                    "  /model mistral\n"
                    "  /model qwen2.5"
                )
                return
            
            model_name = parts[1].strip()
            self.agent.set_model(model_name)
            
            await message.answer(f"✅ Model switched to: <b>{model_name}</b>")
        
        @self.dp.message(Command("clear"))
        async def clear_handler(message: Message):
            if not self._is_allowed_user(message.from_user.id if message.from_user else 0):
                return
            
            user_id = str(message.from_user.id) if message.from_user else ""
            await self.agent.clear_history(user_id)
            
            await message.answer("✅ Conversation history cleared.")
        
        @self.dp.message(Command("status"))
        async def status_handler(message: Message):
            if not self._is_allowed_user(message.from_user.id if message.from_user else 0):
                return
            
            model = self.agent.settings.ollama.model
            await message.answer(
                f"🐦 <b>Local Pigeon Status</b>\n\n"
                f"Model: <code>{model}</code>\n"
                f"Platform: Telegram\n"
                f"Status: Online"
            )
        
        @self.dp.message(F.text)
        async def message_handler(message: Message):
            if not message.from_user:
                return
            
            if not self._is_allowed_user(message.from_user.id):
                await message.answer("❌ You are not authorized to use this bot.")
                return
            
            content = message.text or ""
            if not content:
                return
            
            user_id = str(message.from_user.id)
            chat_id = str(message.chat.id)
            
            # Check for approval responses
            if content.lower() in ("approve", "yes", "y"):
                if self._handle_approval_response(user_id, True):
                    await message.answer("✅ Approved!")
                    return
            elif content.lower() in ("deny", "no", "n"):
                if self._handle_approval_response(user_id, False):
                    await message.answer("❌ Denied.")
                    return
            
            # Send "thinking" message
            if self.settings.show_typing:
                await self.bot.send_chat_action(message.chat.id, "typing")
            
            thinking_msg = await message.answer("🤔 Thinking...")
            
            # Process message
            await self._process_message(
                user_id=user_id,
                chat_id=chat_id,
                content=content,
                thinking_msg=thinking_msg,
            )
        
        @self.dp.callback_query(F.data.startswith("approve_"))
        async def approval_callback(callback: CallbackQuery):
            if not callback.data or not callback.from_user:
                return
            
            approval_id = callback.data.replace("approve_", "")
            user_id = str(callback.from_user.id)
            
            key = f"{user_id}_{approval_id}"
            if key in self._pending_approvals:
                future = self._pending_approvals[key]
                if not future.done():
                    future.set_result(True)
                    await callback.answer("✅ Payment approved!")
                    
                    if callback.message:
                        await callback.message.edit_text(
                            callback.message.text + "\n\n✅ <b>APPROVED</b>",
                        )
            else:
                await callback.answer("This approval request has expired.")
        
        @self.dp.callback_query(F.data.startswith("deny_"))
        async def deny_callback(callback: CallbackQuery):
            if not callback.data or not callback.from_user:
                return
            
            approval_id = callback.data.replace("deny_", "")
            user_id = str(callback.from_user.id)
            
            key = f"{user_id}_{approval_id}"
            if key in self._pending_approvals:
                future = self._pending_approvals[key]
                if not future.done():
                    future.set_result(False)
                    await callback.answer("❌ Payment denied.")
                    
                    if callback.message:
                        await callback.message.edit_text(
                            callback.message.text + "\n\n❌ <b>DENIED</b>",
                        )
            else:
                await callback.answer("This approval request has expired.")
    
    def _is_allowed_user(self, user_id: int) -> bool:
        """Check if user is allowed to use the bot."""
        if not self.settings.allowed_users:
            return True
        return str(user_id) in self.settings.allowed_users
    
    async def _process_message(
        self,
        user_id: str,
        chat_id: str,
        content: str,
        thinking_msg: Message,
    ) -> None:
        """Process a user message and send response."""
        # Collect streamed response
        full_response = ""
        last_update = 0
        update_interval = 1.5  # Telegram has stricter rate limits
        
        async def stream_callback(chunk: str):
            nonlocal full_response, last_update
            full_response += chunk
            
            import time
            current_time = time.time()
            if current_time - last_update > update_interval:
                last_update = current_time
                # Truncate if too long for Telegram (4096 char limit)
                display = full_response[:4000] + "..." if len(full_response) > 4000 else full_response
                try:
                    await thinking_msg.edit_text(display)
                except Exception:
                    pass
        
        try:
            response = await self.agent.chat(
                user_message=content,
                user_id=user_id,
                session_id=chat_id,
                platform="telegram",
                stream_callback=stream_callback,
            )
            
            # Send final response
            await self._send_long_message(thinking_msg, response)
            
        except Exception as e:
            await thinking_msg.edit_text(f"❌ Error: {str(e)[:200]}")
    
    async def _send_long_message(
        self,
        initial_message: Message,
        content: str,
    ) -> None:
        """Send a long message, splitting if necessary."""
        # Guard against empty messages
        if not content or not content.strip():
            content = "I received your message but couldn't generate a response. Please try again."
        
        max_len = 4096  # Telegram limit
        
        if len(content) <= max_len:
            await initial_message.edit_text(content)
            return
        
        # Split into chunks
        chunks = []
        while content:
            if len(content) <= max_len:
                chunks.append(content)
                break
            
            split_at = content.rfind("\n", 0, max_len)
            if split_at == -1:
                split_at = content.rfind(" ", 0, max_len)
            if split_at == -1:
                split_at = max_len
            
            chunks.append(content[:split_at])
            content = content[split_at:].lstrip()
        
        # Edit first message
        await initial_message.edit_text(chunks[0])
        
        # Send remaining chunks
        for chunk in chunks[1:]:
            await self.bot.send_message(initial_message.chat.id, chunk)
    
    def _handle_approval_response(self, user_id: str, approved: bool) -> bool:
        """Handle text-based approval response."""
        for key, future in list(self._pending_approvals.items()):
            if key.startswith(user_id) and not future.done():
                future.set_result(approved)
                return True
        return False
    
    async def start(self) -> None:
        """Start the Telegram bot."""
        if not self.settings.bot_token:
            raise ValueError("Telegram bot token not configured")
        
        # Register approval handler
        self.register_with_agent()
        
        # Start polling
        await self.dp.start_polling(self.bot)
    
    async def stop(self) -> None:
        """Stop the Telegram bot."""
        await self.dp.stop_polling()
        await self.bot.session.close()
    
    async def send_message(
        self,
        user_id: str,
        message: str,
        **kwargs,
    ) -> None:
        """Send a message to a user."""
        await self.bot.send_message(int(user_id), message)
    
    async def request_approval(
        self,
        pending: "PendingApproval",
    ) -> bool:
        """Send approval request with inline keyboard."""
        approval_text = (
            f"🔐 <b>Payment Approval Required</b>\n\n"
            f"<b>Tool:</b> {pending.tool_name}\n"
            f"<b>Amount:</b> ${pending.amount:.2f}\n"
            f"<b>Description:</b> {pending.description}\n\n"
            f"<i>This request expires in 5 minutes.</i>"
        )
        
        # Create inline keyboard
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Approve",
                    callback_data=f"approve_{pending.id[:8]}",
                ),
                InlineKeyboardButton(
                    text="❌ Deny",
                    callback_data=f"deny_{pending.id[:8]}",
                ),
            ]
        ])
        
        # Create future for response
        key = f"{pending.user_id}_{pending.id[:8]}"
        future: asyncio.Future[bool] = asyncio.Future()
        self._pending_approvals[key] = future
        
        try:
            await self.bot.send_message(
                int(pending.user_id),
                approval_text,
                reply_markup=keyboard,
            )
            
            return await asyncio.wait_for(future, timeout=300)
            
        except asyncio.TimeoutError:
            return False
        except Exception:
            return False
        finally:
            if key in self._pending_approvals:
                del self._pending_approvals[key]
