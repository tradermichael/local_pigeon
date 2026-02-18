"""Default tool provider implementation for Local Pigeon."""

from __future__ import annotations

import logging
from typing import Any

from local_pigeon.core.interfaces import ToolProvider

logger = logging.getLogger(__name__)


class DefaultToolProvider(ToolProvider):
    """Default concrete provider used by the free/open-source runtime."""

    def get_tools(self, agent: Any) -> list[Any]:
        tools: list[Any] = []

        # Web search tools
        if agent.settings.web.search.enabled:
            from local_pigeon.tools.web.search import WebSearchTool
            tools.append(WebSearchTool(settings=agent.settings.web.search))

        if agent.settings.web.fetch.enabled:
            from local_pigeon.tools.web.fetch import WebFetchTool
            tools.append(WebFetchTool(settings=agent.settings.web.fetch))

        # Browser automation (Playwright)
        if agent.settings.web.browser.enabled:
            from local_pigeon.tools.web.browser import BrowserTool, BrowserSearchTool
            tools.append(BrowserTool(settings=agent.settings.web.browser))
            tools.append(BrowserSearchTool(settings=agent.settings.web.browser))

        # Google Workspace tools
        if agent.settings.google.gmail_enabled:
            from local_pigeon.tools.google.gmail import GmailTool
            tools.append(GmailTool(settings=agent.settings.google))

        if agent.settings.google.calendar_enabled:
            from local_pigeon.tools.google.calendar import CalendarTool
            tools.append(CalendarTool(settings=agent.settings.google))

        if agent.settings.google.drive_enabled:
            from local_pigeon.tools.google.drive import DriveTool
            tools.append(DriveTool(settings=agent.settings.google))

        # Payment tools
        if agent.settings.payments.stripe.enabled:
            from local_pigeon.tools.payments.stripe_card import StripeCardTool
            tools.append(StripeCardTool(
                stripe_settings=agent.settings.payments.stripe,
                approval_settings=agent.settings.payments.approval,
            ))

        if agent.settings.payments.crypto.enabled:
            from local_pigeon.tools.payments.crypto_wallet import CryptoWalletTool
            tools.append(CryptoWalletTool(
                crypto_settings=agent.settings.payments.crypto,
                approval_settings=agent.settings.payments.approval,
            ))

        # Self-healing tools (Ralph Loop pattern) - always enabled
        from local_pigeon.tools.self_healing import (
            ViewFailureLogTool,
            MarkFailureResolvedTool,
            AnalyzeFailurePatternsTool,
        )
        tools.append(ViewFailureLogTool(failure_log=agent.failure_log))
        tools.append(MarkFailureResolvedTool(failure_log=agent.failure_log))
        tools.append(AnalyzeFailurePatternsTool(failure_log=agent.failure_log))

        # Skills tools (RALPH loop self-improvement) - always enabled
        from local_pigeon.tools.skills_tools import (
            CreateSkillTool,
            ViewSkillsTool,
            LearnSkillTool,
            UpdateSkillTool,
            DocumentLimitationTool,
        )
        tools.append(CreateSkillTool(
            skills_manager=agent.skills,
            auto_approve=agent.settings.agent.auto_approve_skills,
        ))
        tools.append(ViewSkillsTool(skills_manager=agent.skills))
        tools.append(LearnSkillTool(skills_manager=agent.skills))
        tools.append(UpdateSkillTool(skills_manager=agent.skills))
        tools.append(DocumentLimitationTool(
            skills_manager=agent.skills,
            auto_approve=agent.settings.agent.auto_approve_skills,
        ))

        # Memory tools - always enabled
        from local_pigeon.tools.memory_tools import (
            RememberTool,
            RecallTool,
            ListMemoriesTool,
            ForgetTool,
        )
        tools.append(RememberTool(memory_manager=agent.memory))
        tools.append(RecallTool(memory_manager=agent.memory))
        tools.append(ListMemoriesTool(memory_manager=agent.memory))
        tools.append(ForgetTool(memory_manager=agent.memory))

        # Schedule tools - always enabled
        from local_pigeon.tools.schedule_tools import (
            CreateScheduleTool,
            ListSchedulesTool,
            CancelScheduleTool,
            PauseScheduleTool,
        )
        tools.append(CreateScheduleTool(scheduler=agent.scheduler))
        tools.append(ListSchedulesTool(scheduler=agent.scheduler))
        tools.append(CancelScheduleTool(scheduler=agent.scheduler))
        tools.append(PauseScheduleTool(scheduler=agent.scheduler))

        return tools

    async def get_mcp_tools(self, agent: Any) -> tuple[Any | None, list[Any]]:
        if not agent.settings.mcp.enabled:
            return None, []

        if not agent.settings.mcp.servers:
            return None, []

        from local_pigeon.tools.mcp import MCPManager, create_mcp_tools

        manager = MCPManager(connection_timeout=agent.settings.mcp.connection_timeout)

        for server_config in agent.settings.mcp.servers:
            if not server_config.name:
                continue
            try:
                if server_config.transport == "stdio":
                    await manager.connect_stdio_server(
                        name=server_config.name,
                        command=server_config.command,
                        args=server_config.args,
                        env=server_config.env or None,
                    )
                elif server_config.transport == "sse":
                    await manager.connect_sse_server(
                        name=server_config.name,
                        url=server_config.url,
                    )
                else:
                    logger.warning(
                        "Unknown MCP transport '%s' for server '%s'",
                        server_config.transport,
                        server_config.name,
                    )
            except Exception as exc:
                logger.error("Failed to connect to MCP server '%s': %s", server_config.name, exc)

        tools = create_mcp_tools(
            manager=manager,
            require_approval=not agent.settings.mcp.auto_approve,
        )
        return manager, tools

    def get_discord_tools(self, agent: Any, bot: Any) -> list[Any]:
        if not agent.settings.discord.enabled:
            return []

        from local_pigeon.tools.discord import (
            DiscordSendMessageTool,
            DiscordSendDMTool,
            DiscordGetMessagesTool,
            DiscordAddReactionTool,
            DiscordListChannelsTool,
            DiscordCreateThreadTool,
            DiscordGetServerInfoTool,
        )

        return [
            DiscordSendMessageTool(bot=bot),
            DiscordSendDMTool(bot=bot),
            DiscordGetMessagesTool(bot=bot),
            DiscordAddReactionTool(bot=bot),
            DiscordListChannelsTool(bot=bot),
            DiscordCreateThreadTool(bot=bot),
            DiscordGetServerInfoTool(bot=bot),
        ]
