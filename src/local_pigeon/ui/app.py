"""
Gradio Web UI

Browser-based interface for Local Pigeon.
Provides:
- Chat interface with streaming
- Settings panel
- Integrations setup
- Memory management
- Tool execution display
"""

import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Generator, TYPE_CHECKING
import gradio as gr

# Try to import themes (may not be available in all gradio versions)
try:
    from gradio.themes import Soft as SoftTheme
    _has_themes = True
except ImportError:
    _has_themes = False

# Check Gradio version for API compatibility
_gradio_version = tuple(int(x) for x in gr.__version__.split('.')[:2])
_gradio_6_plus = _gradio_version >= (6, 0)

from local_pigeon import __version__
from local_pigeon.config import Settings, get_data_dir, ensure_data_dir, delete_local_data

if TYPE_CHECKING:
    from local_pigeon.core.agent import LocalPigeonAgent


def create_app(
    settings: Settings | None = None,
    shared_agent: "LocalPigeonAgent | None" = None,
) -> gr.Blocks:
    """
    Create the Gradio web application.
    
    Args:
        settings: Application settings (loaded from config if not provided)
        shared_agent: Optional pre-initialized agent to share with other platforms
    
    Returns:
        Gradio Blocks application
    """
    if settings is None:
        settings = Settings.load()
    
    # Import here to avoid circular imports
    from local_pigeon.core.agent import LocalPigeonAgent
    from local_pigeon.storage.memory import AsyncMemoryManager, MemoryType
    from local_pigeon.config import get_data_dir
    from pathlib import Path
    
    # Build correct database path (same logic as agent)
    data_dir = get_data_dir()
    db_filename = settings.storage.database
    if Path(db_filename).is_absolute():
        db_path = db_filename
    else:
        db_path = str(data_dir / db_filename)
    
    # Use shared agent if provided, otherwise create our own
    agent: LocalPigeonAgent | None = shared_agent
    memory_manager = AsyncMemoryManager(db_path=db_path)
    
    async def get_agent() -> LocalPigeonAgent:
        nonlocal agent
        if agent is None:
            agent = LocalPigeonAgent(settings)
            await agent.initialize()
        return agent
    
    # Modern theme CSS with light/dark mode support
    gemini_css = """
    /* ==========================================
       LIGHT MODE (default)
       ========================================== */
    :root,
    body:not(.dark) {
        --primary-color: #2563eb;
        --primary-hover: #1d4ed8;
        --bg-primary: #f8fafc;
        --bg-secondary: #ffffff;
        --bg-tertiary: #f1f5f9;
        --bg-chat: #ffffff;
        --text-primary: #0f172a;
        --text-secondary: #334155;
        --text-muted: #64748b;
        --border-color: #cbd5e1;
        --shadow-sm: 0 1px 3px rgba(0,0,0,0.08);
        --shadow-md: 0 4px 12px rgba(0,0,0,0.12);
        --radius-sm: 8px;
        --radius-md: 12px;
        --radius-lg: 20px;
        --accent-blue: #3b82f6;
        --accent-green: #16a34a;
        --accent-purple: #9333ea;
        --user-msg-bg: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        --user-msg-text: #ffffff;
        --bot-msg-bg: #f1f5f9;
        --bot-msg-text: #0f172a;
        --input-bg: #ffffff;
        --input-border: #cbd5e1;
        --focus-ring: rgba(37, 99, 235, 0.25);
        --code-bg: #f1f5f9;
        --code-text: #1e293b;
        --tab-bg: #ffffff;
        --tab-active-bg: #f8fafc;
        --btn-secondary-bg: #f1f5f9;
        --btn-secondary-text: #1e293b;
        --btn-secondary-border: #cbd5e1;
        --btn-secondary-hover: #e2e8f0;
    }
    
    /* ==========================================
       DARK MODE (triggered by .dark class on body)
       ========================================== */
    body.dark,
    body.dark :root {
        --primary-color: #8ab4f8;
        --primary-hover: #aecbfa;
        --bg-primary: #1e1e2e;
        --bg-secondary: #2d2d3d;
        --bg-tertiary: #3d3d4d;
        --bg-chat: #252535;
        --text-primary: #f4f4f5;
        --text-secondary: #d4d4d8;
        --text-muted: #a1a1aa;
        --border-color: #3f3f46;
        --shadow-sm: 0 1px 3px rgba(0,0,0,0.3);
        --shadow-md: 0 4px 12px rgba(0,0,0,0.4);
        --accent-blue: #60a5fa;
        --accent-green: #22c55e;
        --accent-purple: #a855f7;
        --user-msg-bg: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
        --user-msg-text: #ffffff;
        --bot-msg-bg: #3d3d4d;
        --bot-msg-text: #f4f4f5;
        --input-bg: #3d3d4d;
        --input-border: #3f3f46;
        --focus-ring: rgba(138, 180, 248, 0.3);
        --code-bg: #2d2d3d;
        --code-text: #e2e8f0;
        --tab-bg: #2d2d3d;
        --tab-active-bg: #1e1e2e;
        --btn-secondary-bg: #3d3d4d;
        --btn-secondary-text: #f4f4f5;
        --btn-secondary-border: #3f3f46;
        --btn-secondary-hover: #4d4d5d;
    }
    
    /* ==========================================
       LIGHT MODE — explicit overrides for Gradio components
       (these fire when body does NOT have .dark class)
       ========================================== */
    body:not(.dark) .gradio-container,
    body:not(.dark) .gradio-container * {
        color: #0f172a;
    }
    
    body:not(.dark) .gradio-container input,
    body:not(.dark) .gradio-container select,
    body:not(.dark) .gradio-container textarea,
    body:not(.dark) .gradio-container .wrap input,
    body:not(.dark) .gradio-container .wrap select {
        background-color: #ffffff !important;
        color: #0f172a !important;
        border-color: #cbd5e1 !important;
    }
    
    body:not(.dark) .gradio-container ul[role="listbox"],
    body:not(.dark) .gradio-container .options,
    body:not(.dark) .gradio-container .dropdown-content {
        background-color: #ffffff !important;
        border-color: #cbd5e1 !important;
    }
    
    body:not(.dark) .gradio-container ul[role="listbox"] li,
    body:not(.dark) .gradio-container .options li,
    body:not(.dark) .gradio-container .option {
        color: #0f172a !important;
        background-color: #ffffff !important;
    }
    
    body:not(.dark) .gradio-container ul[role="listbox"] li:hover,
    body:not(.dark) .gradio-container .options li:hover,
    body:not(.dark) .gradio-container .option:hover {
        background-color: #f1f5f9 !important;
    }
    
    body:not(.dark) .gradio-container .wrap .selected,
    body:not(.dark) .gradio-container .dropdown .selected,
    body:not(.dark) .gradio-container input[type="text"] {
        color: #0f172a !important;
        background-color: #ffffff !important;
    }
    
    body:not(.dark) .gradio-container button:not(.primary) {
        color: #1e293b !important;
        background: #f1f5f9 !important;
        border-color: #cbd5e1 !important;
    }
    
    body:not(.dark) .gradio-container button:not(.primary):hover {
        background: #e2e8f0 !important;
    }
    
    body:not(.dark) .gradio-container label span,
    body:not(.dark) .gradio-container .label-wrap span {
        color: #0f172a !important;
    }
    
    body:not(.dark) .gradio-container .chatbot {
        background: #ffffff !important;
        border-color: #cbd5e1 !important;
    }
    
    body:not(.dark) .chatbot .message-row.bot-row .message {
        background: #f1f5f9 !important;
        color: #0f172a !important;
        border-color: #e2e8f0 !important;
    }
    
    body:not(.dark) .chatbot .message-row.bot-row .message * {
        color: #0f172a !important;
    }
    
    body:not(.dark) .chatbot .message-row.user-row .message,
    body:not(.dark) .chatbot .message-row.user-row .message * {
        color: #ffffff !important;
    }
    
    body:not(.dark) .gradio-container .panel,
    body:not(.dark) .gradio-container .block,
    body:not(.dark) .gradio-container .form {
        background: #ffffff !important;
        border-color: #cbd5e1 !important;
    }
    
    body:not(.dark) .gradio-container .accordion {
        background: #ffffff !important;
        border-color: #cbd5e1 !important;
    }
    
    body:not(.dark) .gradio-container .tab-nav {
        background: #ffffff !important;
        border-color: #cbd5e1 !important;
    }
    
    body:not(.dark) .gradio-container .tab-nav button {
        color: #334155 !important;
        background: transparent !important;
    }
    
    body:not(.dark) .gradio-container .tab-nav button.selected {
        background: #f8fafc !important;
        color: #2563eb !important;
        border-bottom-color: #2563eb !important;
    }
    
    body:not(.dark) .gradio-container table {
        background: #ffffff !important;
        color: #0f172a !important;
    }
    
    body:not(.dark) .gradio-container th {
        background: #f1f5f9 !important;
        color: #0f172a !important;
    }
    
    body:not(.dark) .gradio-container td {
        color: #0f172a !important;
        border-color: #e2e8f0 !important;
    }
    
    body:not(.dark) .gradio-container pre,
    body:not(.dark) .gradio-container code {
        background: #f1f5f9 !important;
        color: #1e293b !important;
    }
    
    body:not(.dark) .gradio-container .prose,
    body:not(.dark) .gradio-container .prose *,
    body:not(.dark) .gradio-container .markdown-body,
    body:not(.dark) .gradio-container .markdown-body *,
    body:not(.dark) .gradio-container p {
        color: #0f172a !important;
    }
    
    body:not(.dark) .gradio-container h1,
    body:not(.dark) .gradio-container h2,
    body:not(.dark) .gradio-container h3,
    body:not(.dark) .gradio-container h4 {
        color: #0f172a !important;
    }
    
    body:not(.dark) .gradio-container .info-text,
    body:not(.dark) .gradio-container span.info,
    body:not(.dark) .gradio-container .wrap .info,
    body:not(.dark) .gradio-container .description {
        color: #475569 !important;
    }

    /* Theme toggle button */
    #theme-toggle-btn {
        position: fixed !important;
        bottom: 20px !important;
        right: 20px !important;
        width: 44px !important;
        height: 44px !important;
        border-radius: 50% !important;
        font-size: 20px !important;
        cursor: pointer !important;
        z-index: 9999 !important;
        border: 1px solid var(--border-color) !important;
        background: var(--bg-secondary) !important;
        box-shadow: var(--shadow-md) !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        transition: all 0.2s ease !important;
        padding: 0 !important;
        line-height: 1 !important;
    }
    
    #theme-toggle-btn:hover {
        transform: scale(1.1) !important;
    }
    
    /* Main container - full width */
    .gradio-container {
        background: var(--bg-primary) !important;
        font-family: 'Inter', 'SF Pro Display', 'Segoe UI', system-ui, sans-serif !important;
        max-width: 100% !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* Make all tabs same width */
    .tabs {
        max-width: 100% !important;
        width: 100% !important;
    }
    
    .tabitem {
        max-width: 100% !important;
        width: 100% !important;
        padding: 24px !important;
    }
    
    /* Chat container styling */
    .chatbot {
        background: var(--bg-secondary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: var(--radius-lg) !important;
        box-shadow: var(--shadow-sm) !important;
        min-height: 60vh !important;
        max-height: 70vh !important;
    }
    
    /* Gradio 4.x message bubbles */
    .chatbot .message-bubble-border {
        border: none !important;
    }
    
    .chatbot .message-row .message {
        border-radius: var(--radius-md) !important;
        padding: 14px 18px !important;
        box-shadow: none !important;
        line-height: 1.6 !important;
        border-left: none !important;
        border-right: none !important;
        caret-color: transparent !important;
    }
    
    /* Disable contenteditable styling but allow selection */
    .chatbot [contenteditable] {
        caret-color: transparent !important;
        outline: none !important;
    }
    
    .chatbot [contenteditable]:focus {
        outline: none !important;
        border: none !important;
    }
    
    /* Remove any selection/edit indicators */
    .chatbot .message-row .message::before,
    .chatbot .message-row .message::after,
    .chatbot .message::before,
    .chatbot .message::after {
        display: none !important;
        content: none !important;
        border: none !important;
    }
    
    /* Hide edit mode indicators/carets */
    .chatbot .edit-button,
    .chatbot .edit-buttons,
    .chatbot [class*="edit"],
    .chatbot .message-wrap::before,
    .chatbot .message-wrap::after {
        display: none !important;
    }
    
    /* Remove left/right borders that appear as lines */
    .chatbot .message-wrap,
    .chatbot .message-content,
    .chatbot .prose {
        border-left: none !important;
        border-right: none !important;
    }
    
    /* Hide caret/cursor indicators */
    .chatbot .caret,
    .chatbot [class*="caret"],
    .chatbot [class*="cursor"] {
        display: none !important;
    }
    
    /* Remove edit mode borders */
    .chatbot [data-testid="bot"], .chatbot [data-testid="user"] {
        border-left: none !important;
        border-right: none !important;
    }
    
    .chatbot .prose {
        border: none !important;
    }
    
    /* Aggressively hide any vertical line artifacts inside bubbles */
    .chatbot .message * {
        border-left: none !important;
        border-right: none !important;
    }
    
    /* Hide any icons/indicators inside message content */
    .chatbot .message svg:not(.prose svg),
    .chatbot .message-content > button,
    .chatbot .message-content > .icon,
    .chatbot .bubble-wrap > button {
        display: none !important;
    }
    
    /* Ensure text spans have no borders */
    .chatbot .message span,
    .chatbot .message p,
    .chatbot .message div:not(.prose) {
        border-left: none !important;
        border-right: none !important;
        border-top: none !important;
        border-bottom: none !important;
    }
    
    /* User messages - right side, accent color */
    .chatbot .message-row.user-row .message {
        background: var(--user-msg-bg) !important;
        color: var(--user-msg-text) !important;
        border-radius: var(--radius-md) var(--radius-md) 4px var(--radius-md) !important;
        border: none !important;
    }
    
    /* Assistant messages - left side */
    .chatbot .message-row.bot-row .message {
        background: var(--bot-msg-bg) !important;
        color: var(--bot-msg-text) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: var(--radius-md) var(--radius-md) var(--radius-md) 4px !important;
    }
    
    /* Remove avatar space when no avatars */
    .chatbot .avatar-container,
    .chatbot .avatar-image,
    .chatbot .avatar,
    .chatbot [class*="avatar"],
    .chatbot .bot-message > img:first-child,
    .chatbot .user-message > img:first-child {
        display: none !important;
        width: 0 !important;
        height: 0 !important;
        min-width: 0 !important;
        min-height: 0 !important;
        padding: 0 !important;
        margin: 0 !important;
    }
    
    /* Hide any message index/number markers */
    .chatbot .message-row::before,
    .chatbot .message-row::after,
    .chatbot .bubble-wrap::before,
    .chatbot .bubble-wrap::after {
        display: none !important;
        content: none !important;
    }
    
    /* Input area styling */
    textarea, input[type="text"], input[type="number"] {
        border-radius: var(--radius-md) !important;
        border: 1px solid var(--border-color) !important;
        padding: 12px 16px !important;
        font-size: 14px !important;
        background: var(--input-bg) !important;
        color: var(--text-primary) !important;
        transition: border-color 0.2s, box-shadow 0.2s !important;
    }
    
    textarea:focus, input:focus {
        border-color: var(--primary-color) !important;
        box-shadow: 0 0 0 2px var(--focus-ring) !important;
        outline: none !important;
    }
    
    /* Placeholder text */
    ::placeholder {
        color: var(--text-muted) !important;
        opacity: 1 !important;
    }
    
    /* Primary button styling */
    .primary, button.primary {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
        border: none !important;
        border-radius: var(--radius-md) !important;
        padding: 10px 24px !important;
        font-weight: 500 !important;
        font-size: 14px !important;
        color: white !important;
        transition: all 0.2s ease !important;
        box-shadow: var(--shadow-sm) !important;
    }
    
    .primary:hover, button.primary:hover {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        box-shadow: var(--shadow-md) !important;
        transform: translateY(-1px) !important;
    }
    
    /* Secondary buttons */
    button, .secondary {
        border-radius: var(--radius-md) !important;
        border: 1px solid var(--border-color) !important;
        background: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
        transition: all 0.15s ease !important;
    }
    
    button:hover {
        background: var(--bg-secondary) !important;
        border-color: var(--text-secondary) !important;
    }
    
    /* Tabs styling */
    .tabs {
        background: transparent !important;
        border: none !important;
    }
    
    .tab-nav {
        background: var(--bg-secondary) !important;
        border-radius: var(--radius-md) var(--radius-md) 0 0 !important;
        border-bottom: 1px solid var(--border-color) !important;
        padding: 8px 8px 0 !important;
        gap: 4px !important;
    }
    
    .tab-nav button {
        border-radius: var(--radius-sm) var(--radius-sm) 0 0 !important;
        padding: 10px 20px !important;
        font-weight: 500 !important;
        color: var(--text-secondary) !important;
        border: none !important;
        background: transparent !important;
    }
    
    .tab-nav button.selected {
        background: var(--bg-primary) !important;
        color: var(--primary-color) !important;
        border-bottom: 2px solid var(--primary-color) !important;
    }
    
    /* Panel/Card styling */
    .panel, .block, .form {
        border-radius: var(--radius-md) !important;
        border: 1px solid var(--border-color) !important;
        background: var(--bg-secondary) !important;
        box-shadow: var(--shadow-sm) !important;
    }
    
    /* Accordions */
    .accordion {
        background: var(--bg-secondary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: var(--radius-md) !important;
    }
    
    /* Headers */
    h1, h2, h3, h4, h5, h6 {
        color: var(--text-primary) !important;
        font-weight: 600 !important;
    }
    
    /* Labels */
    label, .label-wrap {
        color: var(--text-primary) !important;
        font-weight: 500 !important;
    }
    
    /* Markdown text */
    .prose, .markdown-body, p {
        color: var(--text-primary) !important;
    }
    
    /* Info/description text */
    .info-text, span.info, .wrap .info, .description {
        color: var(--text-secondary) !important;
    }
    
    /* Dropdown styling */
    .dropdown, select {
        border-radius: var(--radius-sm) !important;
        border: 1px solid var(--border-color) !important;
        background: var(--input-bg) !important;
        color: var(--text-primary) !important;
    }
    
    /* Dropdown options */
    .dropdown option, select option, .options, .option {
        color: var(--text-primary) !important;
        background: var(--input-bg) !important;
    }
    
    /* DataTable */
    table {
        background: var(--bg-secondary) !important;
        color: var(--text-primary) !important;
    }
    
    th {
        background: var(--bg-tertiary) !important;
        color: var(--text-primary) !important;
    }
    
    td {
        border-color: var(--border-color) !important;
    }
    
    /* Slider styling */
    input[type="range"] {
        accent-color: var(--primary-color) !important;
    }
    
    /* Chat header bar */
    .chat-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 12px 16px;
        background: var(--bg-secondary);
        border-radius: var(--radius-md);
        margin-bottom: 12px;
        border: 1px solid var(--border-color);
    }
    
    /* Model selector in header */
    .model-selector {
        display: flex;
        gap: 8px;
        align-items: center;
    }
    
    /* Smooth scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: var(--bg-primary);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: var(--border-color);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: var(--text-secondary);
    }
    
    /* Info text */
    .info {
        color: var(--text-muted) !important;
        font-size: 12px !important;
    }
    
    /* Microphone button styling */
    .mic-button {
        width: 50px !important;
        min-width: 50px !important;
        max-width: 50px !important;
        height: 50px !important;
        border-radius: 50% !important;
        background: var(--primary-color) !important;
        border: none !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 20px !important;
        cursor: pointer !important;
        transition: all 0.2s ease !important;
    }
    
    .mic-button:hover {
        background: var(--primary-hover) !important;
        transform: scale(1.05) !important;
    }
    
    .mic-button.recording {
        background: #ef4444 !important;
        animation: mic-pulse 1.5s infinite !important;
    }
    
    @keyframes mic-pulse {
        0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
        70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
        100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
    }
    
    /* Input row styling */
    .chat-input-row {
        display: flex !important;
        gap: 8px !important;
        align-items: flex-end !important;
    }
    
    /* Voice recording popup */
    .voice-recording-popup {
        background: var(--bg-secondary) !important;
        border: 1px solid var(--border-color) !important;
        border-radius: var(--radius-lg) !important;
        padding: 16px !important;
        margin-top: 12px !important;
        box-shadow: var(--shadow-md) !important;
    }
    
    .voice-recording-popup h3 {
        margin: 0 0 12px 0 !important;
        text-align: center !important;
    }
    
    .voice-recording-popup .audio-container {
        margin-bottom: 12px !important;
    }
    """
    
    # JavaScript for Ctrl+Enter to send
    ctrl_enter_js = """
    () => {
        // Wait for DOM to be ready
        setTimeout(() => {
            const textareas = document.querySelectorAll('textarea');
            textareas.forEach(textarea => {
                // Remove existing listener if any
                textarea.removeEventListener('keydown', textarea._ctrlEnterHandler);
                
                // Add Ctrl+Enter handler
                textarea._ctrlEnterHandler = (e) => {
                    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                        e.preventDefault();
                        // Find and click the send button
                        const sendBtn = document.querySelector('button.primary');
                        if (sendBtn) sendBtn.click();
                    }
                };
                textarea.addEventListener('keydown', textarea._ctrlEnterHandler);
            });
        }, 500);
    }
    """
    
    # Create theme if available
    theme = SoftTheme(primary_hue="blue", secondary_hue="slate") if _has_themes else None
    
    # JavaScript for theme management — respects OS preference, allows user toggle
    theme_js = """
    () => {
        // Determine initial theme: saved preference > OS preference > default dark
        const saved = localStorage.getItem('lp_theme');
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        const useDark = saved ? (saved === 'dark') : prefersDark;
        
        // Apply theme via Gradio's URL param if needed for initial load
        const urlTheme = new URLSearchParams(window.location.search).get('__theme');
        const targetTheme = useDark ? 'dark' : 'light';
        
        if (urlTheme !== targetTheme) {
            const url = new URL(window.location);
            url.searchParams.set('__theme', targetTheme);
            window.location.replace(url.toString());
            return;
        }
        
        // Apply body class
        if (useDark) {
            document.body.classList.add('dark');
            document.documentElement.classList.add('dark');
        } else {
            document.body.classList.remove('dark');
            document.documentElement.classList.remove('dark');
        }
        
        // Inject theme toggle button
        if (!document.getElementById('theme-toggle-btn')) {
            const btn = document.createElement('button');
            btn.id = 'theme-toggle-btn';
            btn.innerHTML = useDark ? '☀️' : '🌙';
            btn.title = useDark ? 'Switch to light mode' : 'Switch to dark mode';
            btn.addEventListener('click', () => {
                const isDark = document.body.classList.contains('dark');
                const newTheme = isDark ? 'light' : 'dark';
                localStorage.setItem('lp_theme', newTheme);
                const url = new URL(window.location);
                url.searchParams.set('__theme', newTheme);
                window.location.replace(url.toString());
            });
            document.body.appendChild(btn);
        }
        
        // Listen for OS theme changes (only if user hasn't set a preference)
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            if (!localStorage.getItem('lp_theme')) {
                const url = new URL(window.location);
                url.searchParams.set('__theme', e.matches ? 'dark' : 'light');
                window.location.replace(url.toString());
            }
        });
    }
    """
    
    # Gradio 6.0+ requires theme/css in launch(), older versions use Blocks()
    blocks_kwargs = {"title": "Local Pigeon", "js": theme_js}
    if not _gradio_6_plus:
        blocks_kwargs["theme"] = theme
        blocks_kwargs["css"] = gemini_css
    
    with gr.Blocks(**blocks_kwargs) as app:
        # Store for launch() in Gradio 6.0+
        app._lp_theme = theme
        app._lp_css = gemini_css
        # State
        conversation_state = gr.State([])
        settings_open = gr.State(False)  # Track settings accordion state
        
        # Header with logo and version
        gr.Markdown(
            f"""
# 🕊️ Local Pigeon

**v{__version__}** • Your local AI assistant powered by Ollama • 100% on-device
            """
        )
        
        with gr.Tabs():
            # Chat Tab
            with gr.Tab("💬 Chat"):
                # Header bar with model selector on the right
                with gr.Row():
                    with gr.Column(scale=3):
                        gr.Markdown("### Conversation")
                    with gr.Column(scale=2):
                        with gr.Row():
                            chat_model_dropdown = gr.Dropdown(
                                label="Model",
                                choices=[settings.ollama.model],
                                value=settings.ollama.model,
                                interactive=True,
                                scale=2,
                                container=False,
                            )
                            chat_refresh_btn = gr.Button("🔄", scale=0, min_width=40)
                            clear_btn = gr.Button("🗑️", scale=0, min_width=40)
                            chat_settings_btn = gr.Button("⚙️", scale=0, min_width=40)
                
                chatbot = gr.Chatbot(
                    label=None,
                    elem_classes="chatbot",
                    height=500,
                    show_label=False,
                    avatar_images=(None, None),
                    editable=None,
                )

                schedule_poller = gr.Timer(value=5.0)
                
                with gr.Row(elem_classes="chat-input-row"):
                    msg_input = gr.MultimodalTextbox(
                        placeholder="Type a message or attach images...",
                        file_types=["image"],
                        file_count="multiple",
                        lines=2,
                        scale=4,
                        show_label=False,
                        submit_btn=True,
                        stop_btn=False,
                    )
                
                # Voice input below text box
                with gr.Accordion("🎤 Voice Input", open=False):
                    voice_input = gr.Audio(
                        sources=["microphone"],
                        type="filepath",
                        label="Click to record, then stop when done",
                        show_label=True,
                        interactive=True,
                    )
                
                # Settings popup (hidden by default)
                with gr.Accordion("Model Settings", open=False, visible=True) as chat_settings_accordion:
                    with gr.Row():
                        vision_dropdown = gr.Dropdown(
                            label="Vision Model (for images)",
                            choices=["(auto-detect)"],
                            value="(auto-detect)",
                            interactive=True,
                        )
                    with gr.Row():
                        chat_temp_slider = gr.Slider(
                            label="Temperature",
                            minimum=0.0,
                            maximum=2.0,
                            step=0.1,
                            value=settings.ollama.temperature,
                        )
            
            # Memory Tab
            with gr.Tab("🧠 Memory"):
                gr.Markdown(
                    """
                    ### Your Memories
                    
                    Memories help Local Pigeon understand you better over time.
                    Add, edit, or remove information the agent knows about you.
                    """
                )
                
                with gr.Row():
                    with gr.Column(scale=2):
                        memories_display = gr.Dataframe(
                            headers=["Type", "Key", "Value", "Source"],
                            datatype=["str", "str", "str", "str"],
                            label="Stored Memories",
                            interactive=False,
                        )
                        refresh_memories_btn = gr.Button("🔄 Refresh Memories")
                    
                    with gr.Column(scale=1):
                        gr.Markdown("#### Add/Update Memory")
                        memory_type_dropdown = gr.Dropdown(
                            label="Memory Type",
                            choices=["core", "preference", "fact", "context", "custom"],
                            value="fact",
                        )
                        memory_key_input = gr.Textbox(
                            label="Key",
                            placeholder="e.g., favorite_color, job_title",
                        )
                        memory_value_input = gr.Textbox(
                            label="Value",
                            placeholder="e.g., blue, Software Engineer",
                            lines=2,
                        )
                        save_memory_btn = gr.Button("💾 Save Memory", variant="primary")
                        memory_status = gr.Textbox(label="Status", interactive=False)
                        
                        gr.Markdown("#### Delete Memory")
                        delete_key_input = gr.Textbox(
                            label="Key to Delete",
                            placeholder="Enter key name",
                        )
                        delete_memory_btn = gr.Button("🗑️ Delete Memory", variant="stop")
            
            # Activity Log Tab
            with gr.Tab("📊 Activity") as activity_tab:
                gr.Markdown(
                    """
                    ### Activity Log
                    
                    View recent interactions across all platforms (Web, Discord, Telegram).
                    Tool calls and messages are tracked here.
                    """
                )
                
                with gr.Row():
                    activity_platform_filter = gr.Dropdown(
                        label="Filter by Platform",
                        choices=["All", "web", "discord", "telegram", "cli"],
                        value="All",
                    )
                    refresh_activity_btn = gr.Button("🔄 Refresh Activity")
                
                activity_log = gr.Dataframe(
                    headers=["Time", "Platform", "User", "Role", "Content"],
                    datatype=["str", "str", "str", "str", "str"],
                    label="Recent Activity",
                    interactive=False,
                    row_count=15,
                )
                
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### 🔧 Tool Usage Summary")
                        tool_usage_summary = gr.Textbox(
                            label="Tools used in recent sessions",
                            lines=5,
                            interactive=False,
                        )
                    
                    with gr.Column(scale=2):
                        gr.Markdown("### 📋 Recent Tool Calls")
                        recent_tool_calls = gr.Textbox(
                            label="Detailed tool execution log",
                            lines=8,
                            interactive=False,
                        )
            
            # Settings Tab
            with gr.Tab("⚙️ Settings"):
                with gr.Accordion("🤖 Model Selection", open=True):
                    gr.Markdown(
                        """
                        ### Select AI Model
                        
                        Choose from installed models or browse & install new ones.
                        [🦙 Browse all Ollama models →](https://ollama.com/library)
                        """
                    )
                    with gr.Row():
                        model_dropdown = gr.Dropdown(
                            label="Active Model",
                            choices=[settings.ollama.model],
                            value=settings.ollama.model,
                            interactive=True,
                            scale=3,
                        )
                        refresh_models_btn = gr.Button("🔄 Refresh", scale=1)
                    model_status = gr.Textbox(label="Status", interactive=False, visible=True)
                    
                    with gr.Row():
                        vision_model_dropdown = gr.Dropdown(
                            label="Vision Model (for images)",
                            choices=["(auto-detect)", settings.ollama.vision_model] if settings.ollama.vision_model else ["(auto-detect)"],
                            value=settings.ollama.vision_model or "(auto-detect)",
                            interactive=True,
                            scale=3,
                            info="Used when you send images. Leave as auto-detect to use first available.",
                        )
                        save_vision_model_btn = gr.Button("💾 Save", scale=1)
                    
                    # --- Model Discovery & Install (integrated) ---
                    gr.Markdown("---")
                    
                    with gr.Tabs():
                        with gr.Tab("📦 Installed"):
                            models_list = gr.Dataframe(
                                headers=["Model", "Size", "Vision", "Status"],
                                datatype=["str", "str", "str", "str"],
                                label="Installed Models",
                                interactive=False,
                                row_count=5,
                            )
                            refresh_models_list_btn = gr.Button("🔄 Refresh List")
                        
                        with gr.Tab("📚 Browse & Install"):
                            gr.Markdown(
                                """
                                Browse models by category, or enter any model name from the
                                [Ollama model library](https://ollama.com/library) to install it.
                                """
                            )
                            
                            catalog_category_filter = gr.Dropdown(
                                label="Filter by Category",
                                choices=[
                                    "All Models",
                                    "⭐ Recommended",
                                    "🧠 Thinking/Reasoning",
                                    "🖼️ Vision",
                                    "💻 Coding",
                                    "💬 General",
                                    "🔧 Tool Calling",
                                    "⚡ Small/Fast",
                                ],
                                value="⭐ Recommended",
                            )
                            
                            catalog_list = gr.Dataframe(
                                headers=["Model", "Ollama Name", "Size", "Type", "Description"],
                                datatype=["str", "str", "str", "str", "str"],
                                label="Model Catalog",
                                interactive=False,
                                row_count=10,
                            )
                            
                            gr.Markdown("**Install a model** — click a row above or type a name:")
                            
                            with gr.Row():
                                install_backend = gr.Radio(
                                    label="Backend",
                                    choices=["Ollama", "GGUF"],
                                    value="Ollama",
                                    scale=1,
                                )
                                pull_model_input = gr.Textbox(
                                    label="Model Name",
                                    placeholder="e.g., deepseek-r1:7b, qwen3:8b, llava",
                                    scale=3,
                                )
                                pull_model_btn = gr.Button("📥 Install", variant="primary", scale=1)
                            
                            pull_model_status = gr.Textbox(
                                label="Install Progress",
                                lines=4,
                                interactive=False,
                            )
                        
                        with gr.Tab("🚀 Starter Pack"):
                            from local_pigeon.core.model_catalog import format_starter_pack_for_display, get_starter_pack_recommendations
                            starter_pack_content = gr.Markdown(format_starter_pack_for_display())
                            
                            gr.Markdown("---")
                            gr.Markdown("**Quick Install — download all recommended models:**")
                            with gr.Row():
                                install_tools_btn = gr.Button("🔧 Install Tool Models", variant="primary")
                                install_vision_btn = gr.Button("🖼️ Install Vision Models")
                                install_thinking_btn = gr.Button("🧠 Install Thinking Models")
                            starter_install_status = gr.Textbox(label="Install Progress", lines=4, interactive=False)
                    
                    with gr.Row():
                        check_ollama_btn = gr.Button("🔍 Check Ollama Status")
                
                with gr.Accordion("👤 Personalization", open=False):
                    gr.Markdown(
                        """
                        ### Personalize Your Assistant
                        
                        Set how you'd like to be addressed and what to call your assistant.
                        """
                    )
                    with gr.Row():
                        bot_name_input = gr.Textbox(
                            label="Assistant Name",
                            placeholder="e.g., Pigeon, Jarvis, Friday",
                            value="Pigeon",
                            info="What should your AI assistant be called?",
                        )
                        user_name_input = gr.Textbox(
                            label="Your Name",
                            placeholder="e.g., Michael, Boss, Captain",
                            value="",
                            info="How would you like to be addressed? (Leave blank for no name)",
                        )
                    save_personalization_btn = gr.Button("💾 Save Personalization", variant="primary")
                    personalization_status = gr.Textbox(label="Status", interactive=False, visible=False)
                
                with gr.Accordion("🦙 Ollama Settings", open=False):
                    with gr.Row():
                        with gr.Column():
                            ollama_host = gr.Textbox(
                                label="Ollama Host",
                                value=settings.ollama.host,
                                placeholder="http://localhost:11434",
                            )
                            
                            temperature = gr.Slider(
                                label="Temperature",
                                minimum=0.0,
                                maximum=2.0,
                                step=0.1,
                                value=settings.ollama.temperature,
                            )
                            
                            max_tokens = gr.Number(
                                label="Max Tokens",
                                value=settings.ollama.max_tokens,
                            )
                
                with gr.Accordion("� Agent Behavior (Ralph Loop)", open=False):
                    gr.Markdown(
                        "Configure how the agent executes tool loops. "
                        "[Learn about the Ralph Loop pattern](https://ghuntley.com/loop)"
                    )
                    with gr.Row():
                        with gr.Column():
                            checkpoint_mode = gr.Checkbox(
                                label="Checkpoint Mode",
                                value=settings.agent.checkpoint_mode,
                                info="Require approval before each tool execution (watch the loop)",
                            )
                            
                            max_tool_iterations = gr.Number(
                                label="Max Tool Iterations",
                                value=settings.agent.max_tool_iterations,
                                minimum=1,
                                maximum=50,
                                step=1,
                                info="Maximum tool calls per request before stopping",
                            )
                
                with gr.Accordion("�💳 Payment Settings", open=False):
                    with gr.Row():
                        with gr.Column():
                            payment_threshold = gr.Number(
                                label="Approval Threshold ($)",
                                value=settings.payments.approval.threshold,
                                info="Payments above this amount require approval",
                            )
                            
                            require_approval = gr.Checkbox(
                                label="Require Approval for All Payments",
                                value=settings.payments.approval.require_approval,
                            )
                
                with gr.Accordion("📁 Data Storage", open=False):
                    from local_pigeon.config import get_physical_data_dir, get_python_environment_info
                    
                    # Get Python environment info for display
                    env_info = get_python_environment_info()
                    env_type_display = {
                        "windows_store": "🪟 Windows Store Python",
                        "conda": "🐍 Conda/Anaconda",
                        "virtualenv": "📦 Virtual Environment",
                        "pyenv": "🔧 pyenv",
                        "homebrew": "🍺 Homebrew Python",
                        "system": "💻 System Python",
                    }.get(env_info["type"], f"Python ({env_info['type']})")
                    
                    # Get the actual physical path (resolves virtualization)
                    physical_data_dir = get_physical_data_dir()
                    logical_data_dir = ensure_data_dir()
                    
                    # Check which files actually exist using physical path
                    from pathlib import Path
                    data_path = Path(physical_data_dir)
                    db_exists = (data_path / "local_pigeon.db").exists()
                    token_exists = (data_path / "google_token.json").exists()
                    env_exists = (data_path / ".env").exists()
                    
                    # Build list of what exists
                    file_list = []
                    if db_exists:
                        file_list.append("- ✅ Conversations and chat history (`local_pigeon.db`)")
                    else:
                        file_list.append("- ⬜ Conversations and chat history (`local_pigeon.db`) - *not created yet*")
                    
                    if db_exists:  # Memories are in same db
                        file_list.append("- ✅ Memories and preferences")
                    else:
                        file_list.append("- ⬜ Memories and preferences - *not created yet*")
                    
                    if token_exists:
                        file_list.append("- ✅ Google OAuth tokens (`google_token.json`)")
                    else:
                        file_list.append("- ⬜ Google OAuth tokens (`google_token.json`) - *not connected*")
                    
                    if env_exists:
                        file_list.append("- ✅ Settings and configuration (`.env`)")
                    else:
                        file_list.append("- ⬜ Settings and configuration (`.env`) - *not created yet*")
                    
                    files_text = "\n".join(file_list)
                    
                    # Note about virtualization if different paths
                    virtualization_note = ""
                    is_virtualized = env_info["virtualized"] == "True"
                    if is_virtualized and str(physical_data_dir) != str(logical_data_dir):
                        virtualization_note = f"""
                        > ⚠️ **Sandboxed Storage:** Your Python installation uses virtualized file storage.  
                        > The app sees `{logical_data_dir}` but files are physically at the location below.
                        """
                    
                    gr.Markdown(
                        f"""
                        ### Your Data Location
                        
                        **Environment:** {env_type_display} {env_info['version']}
                        
                        All your data is stored locally on your device at:
                        
                        📂 **`{physical_data_dir}`**
                        {virtualization_note}
                        **Files:**
                        {files_text}
                        """
                    )
                    with gr.Row():
                        open_folder_btn = gr.Button("📂 Open Data Folder", scale=2)
                        delete_data_btn = gr.Button("🗑️ Delete Local Data", variant="stop", scale=1)
                    
                    with gr.Row():
                        delete_config_too = gr.Checkbox(
                            label="Also delete configuration files (.env, credentials)",
                            value=False,
                            info="Check this to completely remove all data including settings",
                        )
                    
                    folder_status = gr.Textbox(label="Status", interactive=False, visible=True)
                
                save_settings_btn = gr.Button("💾 Save Settings", variant="primary")
                settings_status = gr.Textbox(label="Status", interactive=False)
            
            # Integrations Tab (renamed from OAuth Setup)
            with gr.Tab("🔗 Integrations"):
                gr.Markdown(
                    """
                    ### Connect Your Services
                    
                    Configure connections to external services like Discord, Telegram, and Google.
                    """
                )
                
                # Determine Discord status for accordion label
                _discord_label = "💬 Discord Bot"
                if settings.discord.enabled and settings.discord.bot_token:
                    _discord_label = "✅ Discord Bot"
                elif settings.discord.bot_token:
                    _discord_label = "⚠️ Discord Bot (disabled)"
                
                with gr.Accordion(_discord_label, open=True):
                    gr.Markdown(
                        """
                        **Setup Instructions:**
                        1. Go to [discord.com/developers/applications](https://discord.com/developers/applications)
                        2. Click **"New Application"** and name it
                        3. Go to **Bot** section → Click **"Add Bot"**
                        4. **Disable** "Requires OAuth2 Code Grant" (if enabled)
                        5. Enable **MESSAGE CONTENT INTENT** under Privileged Intents
                        6. Copy the **Bot Token** and **Application ID** (from General Information)
                        7. Generate the invite link below and add the bot to your server
                        """
                    )
                    discord_enabled = gr.Checkbox(
                        label="Enable Discord Bot",
                        value=settings.discord.enabled,
                    )
                    discord_token = gr.Textbox(
                        label="Bot Token",
                        type="password",
                        value=settings.discord.bot_token if settings.discord.bot_token else "",
                        placeholder="Paste your Discord bot token here",
                    )
                    discord_app_id = gr.Textbox(
                        label="Application ID (for invite link)",
                        value=settings.discord.app_id if settings.discord.app_id else "",
                        placeholder="Found on General Information page (e.g., 123456789012345678)",
                    )
                    discord_invite_url = gr.Textbox(
                        label="Bot Invite URL",
                        value="",
                        interactive=False,
                        placeholder="Enter Application ID above to generate invite link",
                    )
                    generate_invite_btn = gr.Button("🔗 Generate Invite Link")
                    discord_status = gr.Textbox(
                        label="Status",
                        value="✅ Configured" if settings.discord.bot_token else "⚠️ Not configured",
                        interactive=False,
                    )
                    with gr.Row():
                        save_discord_btn = gr.Button("💾 Save Discord Settings")
                        restart_discord_btn = gr.Button("🔄 Save & Restart App", variant="primary")
                
                # Determine Telegram status for accordion label
                _telegram_label = "📱 Telegram Bot"
                if settings.telegram.bot_token:
                    _telegram_label = "✅ Telegram Bot"
                
                with gr.Accordion(_telegram_label, open=False):
                    gr.Markdown(
                        """
                        **Setup Instructions:**
                        1. Open Telegram and search for **@BotFather**
                        2. Send `/newbot` command
                        3. Choose a name and username for your bot
                        4. Copy the token (looks like `123456:ABCdef...`)
                        """
                    )
                    telegram_enabled = gr.Checkbox(
                        label="Enable Telegram Bot",
                        value=settings.telegram.enabled,
                    )
                    telegram_token = gr.Textbox(
                        label="Bot Token",
                        type="password",
                        value=settings.telegram.bot_token if settings.telegram.bot_token else "",
                        placeholder="Paste your Telegram bot token here",
                    )
                    telegram_status = gr.Textbox(
                        label="Status",
                        value="✅ Configured" if settings.telegram.bot_token else "⚠️ Not configured",
                        interactive=False,
                    )
                    with gr.Row():
                        save_telegram_btn = gr.Button("💾 Save Telegram Settings")
                        restart_telegram_btn = gr.Button("🔄 Save & Restart App", variant="primary")
                
                # Determine Google status for accordion label
                _google_token_exists = (get_data_dir() / "google_token.json").exists()
                _google_any_enabled = settings.google.gmail_enabled or settings.google.calendar_enabled or settings.google.drive_enabled
                _google_label = "📧 Google Workspace"
                if _google_token_exists and _google_any_enabled:
                    _google_label = "✅ Google Workspace"
                elif _google_token_exists:
                    _google_label = "⚠️ Google Workspace (authorized but disabled)"
                elif settings.google.credentials_path:
                    _google_label = "⚠️ Google Workspace (needs authorization)"
                
                with gr.Accordion(_google_label, open=False):
                    gr.Markdown(
                        """
                        **Setup Instructions:**
                        1. Go to [console.cloud.google.com](https://console.cloud.google.com)
                        2. Create a new project
                        3. Enable **Gmail**, **Calendar**, and **Drive** APIs
                        4. Create OAuth credentials (Desktop app)
                        5. Download the JSON file
                        6. **Upload** the file below, or enter the path manually
                        """
                    )
                    google_creds_upload = gr.File(
                        label="Upload credentials.json",
                        file_types=[".json"],
                        type="filepath",
                    )
                    google_creds_path = gr.Textbox(
                        label="Or enter path manually",
                        value=settings.google.credentials_path if settings.google.credentials_path else "",
                        placeholder="Path to your credentials.json file",
                    )
                    
                    gr.Markdown("**Enable Services:**")
                    with gr.Row():
                        google_gmail_enabled = gr.Checkbox(
                            label="Gmail",
                            value=settings.google.gmail_enabled,
                        )
                        google_calendar_enabled = gr.Checkbox(
                            label="Calendar",
                            value=settings.google.calendar_enabled,
                        )
                        google_drive_enabled = gr.Checkbox(
                            label="Drive",
                            value=settings.google.drive_enabled,
                        )
                    
                    google_status = gr.Textbox(
                        label="Status",
                        value="✅ Credentials uploaded" if settings.google.credentials_path else "⚠️ Upload credentials.json first",
                        interactive=False,
                    )
                    with gr.Row():
                        save_google_btn = gr.Button("💾 Save Google Settings")
                        authorize_google_btn = gr.Button("🔑 Authorize with Google", variant="primary")
                        test_google_btn = gr.Button("🧪 Test Connection")
                    
                    google_auth_info = gr.Markdown(
                        value="",
                        visible=False,
                    )
                
                # Determine Stripe status for accordion label
                _stripe_label = "💳 Stripe Payments"
                if settings.payments.stripe.enabled and settings.payments.stripe.api_key:
                    _stripe_label = "✅ Stripe Payments"
                elif settings.payments.stripe.api_key:
                    _stripe_label = "⚠️ Stripe Payments (disabled)"
                
                with gr.Accordion(_stripe_label, open=False):
                    gr.Markdown(
                        """
                        **Setup Instructions:**
                        1. Go to [dashboard.stripe.com/apikeys](https://dashboard.stripe.com/apikeys)
                        2. Copy your **Secret Key** (starts with `sk_`)
                        """
                    )
                    stripe_enabled = gr.Checkbox(
                        label="Enable Stripe Payments",
                        value=settings.payments.stripe.enabled,
                    )
                    stripe_key_input = gr.Textbox(
                        label="Stripe Secret Key",
                        type="password",
                        value=settings.payments.stripe.api_key if settings.payments.stripe.api_key else "",
                        placeholder="sk_...",
                    )
                    stripe_status = gr.Textbox(
                        label="Status",
                        value="✅ Configured" if settings.payments.stripe.api_key else "⚠️ Not configured",
                        interactive=False,
                    )
                    save_stripe_btn = gr.Button("💾 Save Stripe Settings")
                
                # MCP Servers section
                _mcp_label = "🔌 MCP Servers"
                if settings.mcp.enabled and settings.mcp.servers:
                    _mcp_label = f"✅ MCP Servers ({len(settings.mcp.servers)} configured)"
                
                with gr.Accordion(_mcp_label, open=False):
                    gr.Markdown(
                        """
                        **Model Context Protocol (MCP)** allows you to connect external tool servers
                        that extend your agent's capabilities. MCP servers provide additional tools
                        like filesystem access, database queries, API integrations, and more.
                        
                        Tools from connected MCP servers appear automatically and the agent can use them.
                        
                        **Requires Node.js/npm** for most MCP servers (stdio transport via npx).
                        """
                    )
                    
                    mcp_enabled = gr.Checkbox(
                        label="Enable MCP Integration",
                        value=settings.mcp.enabled,
                    )
                    
                    mcp_auto_approve = gr.Checkbox(
                        label="Auto-approve MCP tool calls (skip confirmation)",
                        value=settings.mcp.auto_approve,
                    )
                    
                    # Connected servers display
                    gr.Markdown("### Connected Servers")
                    mcp_servers_display = gr.Dataframe(
                        headers=["Name", "Status", "Tools"],
                        value=[["No servers connected", "", ""]],
                        label="",
                        interactive=False,
                    )
                    mcp_refresh_btn = gr.Button("🔄 Refresh Status", size="sm")
                    
                    gr.Markdown("---")
                    gr.Markdown("### Add Popular Server")
                    
                    mcp_popular_choice = gr.Radio(
                        choices=[
                            "🔍 brave-search - Web search via Brave API",
                            "🐙 github - GitHub repos, issues, PRs",
                            "📁 filesystem - Read/write local files",
                            "🗄️ postgres - PostgreSQL database queries",
                            "🔗 fetch - HTTP requests to external APIs",
                            "💾 memory - Persistent key-value store",
                            "🎭 puppeteer - Browser automation",
                            "💬 slack - Slack workspace integration",
                        ],
                        label="Select a server template",
                        value=None,
                    )
                    
                    # Dynamic config fields
                    with gr.Group():
                        mcp_server_name = gr.Textbox(
                            label="Server Name",
                            placeholder="e.g., my-github",
                            interactive=True,
                        )
                        mcp_api_key = gr.Textbox(
                            label="API Key / Token (if required)",
                            type="password",
                            placeholder="Enter API key or token",
                        )
                        mcp_path_input = gr.Textbox(
                            label="Allowed Path (for filesystem server)",
                            placeholder="C:/Users/YourName/Documents",
                            visible=True,
                        )
                    
                    with gr.Row():
                        mcp_test_btn = gr.Button("🔌 Test Connection")
                        mcp_add_btn = gr.Button("➕ Add Server", variant="primary")
                    
                    mcp_result = gr.Textbox(
                        label="Result",
                        interactive=False,
                        lines=3,
                    )
                    
                    gr.Markdown("---")
                    gr.Markdown("### Add Custom Server")
                    
                    with gr.Row():
                        mcp_custom_name = gr.Textbox(
                            label="Server Name",
                            placeholder="my-custom-server",
                        )
                        mcp_custom_transport = gr.Dropdown(
                            choices=["stdio", "sse"],
                            value="stdio",
                            label="Transport",
                        )
                    
                    with gr.Row():
                        mcp_custom_command = gr.Textbox(
                            label="Command",
                            value="npx",
                            placeholder="npx",
                        )
                        mcp_custom_args = gr.Textbox(
                            label="Arguments (comma-separated)",
                            placeholder="-y, @org/mcp-server-name",
                        )
                    
                    mcp_custom_env = gr.Textbox(
                        label="Environment Variables (KEY=value, one per line)",
                        placeholder="API_KEY=your_key_here\nANOTHER_VAR=value",
                        lines=3,
                    )
                    
                    mcp_custom_url = gr.Textbox(
                        label="URL (for SSE transport only)",
                        placeholder="http://localhost:3000/sse",
                        visible=False,
                    )
                    
                    with gr.Row():
                        mcp_test_custom_btn = gr.Button("🔌 Test Custom Connection")
                        mcp_add_custom_btn = gr.Button("➕ Add Custom Server", variant="primary")
                    
                    mcp_custom_result = gr.Textbox(
                        label="Result",
                        interactive=False,
                        lines=3,
                    )
                    
                    # Remove server
                    gr.Markdown("---")
                    gr.Markdown("### Remove Server")
                    mcp_remove_choice = gr.Dropdown(
                        choices=[],
                        label="Select server to remove",
                    )
                    mcp_remove_btn = gr.Button("🗑️ Remove Server", variant="stop")
            
            # Tools Tab
            with gr.Tab("🧰 Tools"):
                gr.Markdown("### Available Tools")
                gr.Markdown(
                    """
                    This shows which tools are **configured** vs which are **actually loaded**.
                    Tools must be enabled AND authorized to appear in the "Loaded" list.
                    """
                )
                
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("**Configured (in settings):**")
                        tools_table = gr.Dataframe(
                            headers=["Tool", "Description", "Enabled"],
                            datatype=["str", "str", "bool"],
                            value=[
                                ["Web Search", "Search the web using DuckDuckGo", settings.web.search.enabled],
                                ["Web Fetch", "Fetch and extract content from web pages", settings.web.fetch.enabled],
                                ["Browser", "Navigate dynamic websites (Google Flights, etc.)", settings.web.browser.enabled],
                                ["Gmail", "Read and send emails", settings.google.gmail_enabled],
                                ["Calendar", "Manage Google Calendar events", settings.google.calendar_enabled],
                                ["Drive", "Access Google Drive files", settings.google.drive_enabled],
                                ["Stripe Payments", "Make payments with virtual card", settings.payments.stripe.enabled],
                                ["Crypto Wallet", "Manage crypto payments", settings.payments.crypto.enabled],
                            ],
                            interactive=False,
                        )
                    
                    with gr.Column(scale=1):
                        gr.Markdown("**Loaded (available to AI):**")
                        loaded_tools_display = gr.Textbox(
                            label="",
                            value="Click 'Refresh' to see loaded tools",
                            lines=8,
                            interactive=False,
                        )
                        refresh_loaded_tools_btn = gr.Button("🔄 Refresh Loaded Tools")
                
                with gr.Accordion("🌐 Browser Automation (Playwright)", open=True):
                    gr.Markdown(
                        """
                        **Browser automation** allows the AI to navigate websites that require JavaScript,
                        fill forms, and extract data from dynamic content (like Google Flights prices).
                        
                        **First-time setup:** Run `playwright install chromium` after enabling.
                        """
                    )
                    with gr.Row():
                        browser_enabled = gr.Checkbox(
                            label="Enable Browser Automation",
                            value=settings.web.browser.enabled,
                        )
                        browser_headless = gr.Checkbox(
                            label="Headless Mode (no visible window)",
                            value=settings.web.browser.headless,
                            info="Uncheck to see the browser window during automation",
                        )
                    
                    browser_status = gr.Textbox(
                        label="Status",
                        value="✅ Enabled (headless)" if settings.web.browser.enabled and settings.web.browser.headless 
                              else "✅ Enabled (GUI mode)" if settings.web.browser.enabled 
                              else "⚠️ Disabled",
                        interactive=False,
                    )
                    
                    with gr.Row():
                        save_browser_btn = gr.Button("💾 Save Browser Settings", variant="primary")
                        install_playwright_btn = gr.Button("📦 Install Playwright")
            
            # Documentation Tab
            with gr.Tab("📚 Docs"):
                with gr.Tabs():
                    with gr.Tab("Getting Started"):
                        gr.Markdown(
                            """
                            ## Getting Started with Local Pigeon
                            
                            Local Pigeon is your personal AI assistant that runs entirely on your device.
                            All your data stays local - nothing is sent to external servers.
                            
                            ### Quick Start
                            
                            1. **Chat**: Just type in the Chat tab and press Enter
                            2. **Tools**: The AI can search the web, manage emails, and more
                            3. **Memory**: Local Pigeon remembers things about you over time
                            4. **Integrations**: Connect Discord, Telegram, or Google services
                            
                            ### LLM Backends
                            
                            Local Pigeon supports two backends:
                            
                            | Backend | Description |
                            |---------|-------------|
                            | **Ollama** | Recommended. Install from [ollama.ai](https://ollama.ai) |
                            | **llama-cpp-python** | Fallback. Auto-downloads models from HuggingFace |
                            
                            The system automatically detects which backend is available.
                            
                            ### Data Storage
                            
                            Your data is stored locally:
                            - **Windows:** `%LOCALAPPDATA%\\LocalPigeon`
                            - **macOS:** `~/Library/Application Support/LocalPigeon`
                            - **Linux:** `~/.local/share/local_pigeon`
                            """
                        )
                    
                    with gr.Tab("Adding Tools"):
                        gr.Markdown(
                            '''
                            ## Creating Custom Tools
                            
                            Tools give Local Pigeon new capabilities. Here's how to create your own:
                            
                            ### 1. Create a Tool File
                            
                            Create a new file in `src/local_pigeon/tools/` (e.g., `my_tool.py`):
                            
                            ```python
                            """My Custom Tool"""
                            
                            from dataclasses import dataclass, field
                            from typing import Any
                            
                            from local_pigeon.tools.registry import Tool
                            
                            
                            @dataclass
                            class MyTool(Tool):
                                """A custom tool that does something useful."""
                                
                                settings: Any = field(default=None)
                                
                                def __post_init__(self):
                                    # Initialize your tool here
                                    pass
                                
                                @property
                                def name(self) -> str:
                                    return "my_custom_tool"
                                
                                @property
                                def description(self) -> str:
                                    return "Description of what this tool does"
                                
                                @property
                                def parameters(self) -> dict:
                                    return {
                                        "type": "object",
                                        "properties": {
                                            "input_text": {
                                                "type": "string",
                                                "description": "The input to process"
                                            }
                                        },
                                        "required": ["input_text"]
                                    }
                                
                                async def execute(self, **kwargs) -> str:
                                    """Execute the tool with given parameters."""
                                    input_text = kwargs.get("input_text", "")
                                    
                                    # Your tool logic here
                                    result = f"Processed: {input_text}"
                                    
                                    return result
                            ```
                            
                            ### 2. Register the Tool
                            
                            Add your tool to the agent's `_register_default_tools()` method in 
                            `src/local_pigeon/core/agent.py`:
                            
                            ```python
                            from local_pigeon.tools.my_tool import MyTool
                            
                            # In _register_default_tools():
                            self.tools.register(MyTool())
                            ```
                            
                            ### 3. Tool Best Practices
                            
                            - **Clear descriptions**: The AI uses these to decide when to use your tool
                            - **Specific parameters**: Define exactly what inputs your tool needs
                            - **Error handling**: Return helpful error messages
                            - **Async execution**: Use `async def execute()` for I/O operations
                            
                            ### Example Tools
                            
                            Look at existing tools for reference:
                            - `tools/web/search.py` - Web search
                            - `tools/web/fetch.py` - Fetch web pages
                            - `tools/google/gmail.py` - Email integration
                            '''
                        )
                    
                    with gr.Tab("Adding Integrations"):
                        gr.Markdown(
                            '''
                            ## Creating Platform Integrations
                            
                            Integrations let users interact with Local Pigeon through different platforms.
                            
                            ### Platform Adapter Pattern
                            
                            Create a new file in `src/local_pigeon/platforms/` (e.g., `slack_adapter.py`):
                            
                            ```python
                            """Slack Integration"""
                            
                            import asyncio
                            from local_pigeon.platforms.base import PlatformAdapter
                            from local_pigeon.core.agent import LocalPigeonAgent
                            
                            
                            class SlackAdapter(PlatformAdapter):
                                """Adapter for Slack integration."""
                                
                                def __init__(self, agent: LocalPigeonAgent, settings):
                                    self.agent = agent
                                    self.settings = settings
                                    self.client = None  # Your Slack client
                                
                                async def start(self):
                                    """Start the Slack bot."""
                                    # Initialize Slack client
                                    # Set up event handlers
                                    # Run the event loop
                                    pass
                                
                                async def stop(self):
                                    """Stop the Slack bot."""
                                    pass
                                
                                async def handle_message(self, message: str, user_id: str):
                                    """Handle incoming message."""
                                    response = await self.agent.chat(
                                        user_message=message,
                                        user_id=f"slack_{user_id}",
                                        platform="slack",
                                    )
                                    return response
                            ```
                            
                            ### Adding Settings
                            
                            Add settings to `src/local_pigeon/config.py`:
                            
                            ```python
                            class SlackSettings(BaseSettings):
                                """Slack bot settings."""
                                
                                enabled: bool = Field(default=False)
                                bot_token: str | None = Field(default=None)
                                app_token: str | None = Field(default=None)
                                
                                model_config = SettingsConfigDict(env_prefix="SLACK_")
                            ```
                            
                            ### Running the Integration
                            
                            Add to the CLI run command in `src/local_pigeon/cli.py`:
                            
                            ```python
                            if settings.slack.enabled and settings.slack.bot_token:
                                from local_pigeon.platforms.slack_adapter import SlackAdapter
                                tasks.append(SlackAdapter(agent, settings.slack).start())
                            ```
                            '''
                        )
                    
                    with gr.Tab("Configuration"):
                        gr.Markdown(
                            """
                            ## Configuration Options
                            
                            Local Pigeon can be configured via environment variables or `config.yaml`.
                            
                            ### Environment Variables
                            
                            Create a `.env` file in your data directory:
                            
                            ```bash
                            # LLM Settings
                            OLLAMA_HOST=http://localhost:11434
                            OLLAMA_MODEL=gemma3:latest
                            OLLAMA_TEMPERATURE=0.7
                            
                            # Discord Bot
                            DISCORD_ENABLED=true
                            DISCORD_BOT_TOKEN=your_token_here
                            
                            # Telegram Bot
                            TELEGRAM_ENABLED=true
                            TELEGRAM_BOT_TOKEN=your_token_here
                            
                            # Google Workspace
                            GOOGLE_CREDENTIALS_PATH=/path/to/credentials.json
                            
                            # Payments
                            STRIPE_ENABLED=true
                            STRIPE_API_KEY=sk_...
                            PAYMENT_APPROVAL_THRESHOLD=25.00
                            ```
                            
                            ### config.yaml
                            
                            For more complex settings, use `config.yaml`:
                            
                            ```yaml
                            model:
                              name: gemma3:latest
                              temperature: 0.7
                              context_length: 8192
                            
                            agent:
                              system_prompt: |
                                You are a helpful assistant...
                              max_history_messages: 20
                            
                            payments:
                              approval:
                                threshold: 25.00
                                daily_limit: 100.00
                            ```
                            
                            ### Priority Order
                            
                            Settings are loaded in this order (later overrides earlier):
                            1. Defaults in code
                            2. `config.yaml`
                            3. `.env` file
                            4. System environment variables
                            """
                        )
                    
                    with gr.Tab("API Reference"):
                        gr.Markdown(
                            """
                            ## Key Classes and Functions
                            
                            ### LocalPigeonAgent
                            
                            The main agent class that orchestrates everything:
                            
                            ```python
                            from local_pigeon.core.agent import LocalPigeonAgent
                            from local_pigeon.config import Settings
                            
                            settings = Settings.load()
                            agent = LocalPigeonAgent(settings)
                            await agent.initialize()
                            
                            # Chat with the agent
                            response = await agent.chat(
                                user_message="Hello!",
                                user_id="user123",
                            )
                            ```
                            
                            ### Dependency Injection (Enterprise)

                            Swap core components without forking:

                            ```python
                            from local_pigeon.core.agent import LocalPigeonAgent
                            from local_pigeon.core.interfaces import (
                                MemoryProvider,
                                NetworkProvider,
                                ToolProvider,
                            )

                            agent = LocalPigeonAgent(
                                settings=settings,
                                memory_provider=my_memory_provider,
                                network_provider=my_network_provider,
                                tool_provider=my_tool_provider,
                            )
                            await agent.initialize()
                            ```

                            The default runtime uses `DefaultToolProvider`.

                            ### Tool Registry
                            
                            Register and manage tools:
                            
                            ```python
                            from local_pigeon.tools.registry import ToolRegistry, Tool
                            
                            registry = ToolRegistry()
                            registry.register(MyTool())
                            
                            # Get all tools
                            tools = registry.get_all()
                            
                            # Execute a tool
                            result = await registry.execute("tool_name", param1="value")
                            ```
                            
                            ### Memory Provider
                            
                            Store and retrieve user memories:
                            
                            ```python
                            # Your provider implements the MemoryProvider interface
                            await my_memory_provider.save_context(
                                user_id="user123",
                                key="favorite_color",
                                text="blue",
                                memory_type="preference",
                            )
                            
                            # Retrieve relevant context
                            memories = await my_memory_provider.retrieve_context(
                                user_id="user123",
                                query="favorite color",
                            )
                            ```
                            
                            ### Conversation Manager
                            
                            Manage conversation history:
                            
                            ```python
                            from local_pigeon.core.conversation import AsyncConversationManager
                            
                            conversations = AsyncConversationManager(db_path="local_pigeon.db")
                            
                            # Get or create a conversation
                            conv_id = await conversations.get_or_create_conversation(
                                user_id="user123",
                                platform="web",
                            )
                            
                            # Add a message
                            await conversations.add_message(conv_id, "user", "Hello!")
                            ```
                            """
                        )
            
            # About Tab
            with gr.Tab("ℹ️ About"):
                data_dir = get_data_dir()
                gr.Markdown(
                    f"""
                    ### BOTF AI (Local Pigeon)
                    
                    **Version:** {__version__}
                    
                    A fully local AI agent powered by Ollama. Your data stays on your device.
                    
                    **Features:**
                    - 🧠 Local LLM inference via Ollama
                    - 🔧 Dependency-injection ready tool system
                    - 💳 Payment capabilities (Stripe + Crypto)
                    - 📧 Google Workspace integration
                    - 🔐 Human-in-the-loop approvals
                    - 🌐 Optional mesh plumbing (`--enable-mesh`)
                    - 💬 Multi-platform support (Discord, Telegram, Web)
                    
                    **Current Model:** {settings.ollama.model}

                    **Mesh Enabled:** {'Yes' if getattr(settings, 'mesh', None) and settings.mesh.enabled else 'No'}
                    
                    **Data Directory:** `{data_dir}`

                    **CLI:** `botf run` (alias: `local-pigeon run`)
                    
                    **Links:**
                    - [GitHub Repository](https://github.com/tradermichael/local_pigeon)
                    - [Ollama](https://ollama.ai)
                    """
                )
        
        # Event handlers - split into add_message (instant) and generate (streaming)
        def add_user_message(
            message: dict | str,
            history: list[dict],
        ) -> tuple[dict | None, list[dict]]:
            """Instantly add user message to chat - no waiting.
            
            message can be:
              - A string (plain text, e.g. from voice input)
              - A dict with 'text' and 'files' keys (from MultimodalTextbox)
            """
            # Handle MultimodalTextbox dict format
            if isinstance(message, dict):
                text = (message.get("text") or "").strip()
                files = message.get("files") or []
            else:
                text = (message or "").strip()
                files = []
            
            if not text and not files:
                return message, history
            
            # Build content parts for the chat message
            # Gradio 6 Chatbot supports mixed content in a list
            content_parts = []
            
            # Add image files as gr.Image components for display
            for f in files:
                file_path = f if isinstance(f, str) else (f.get("path") if isinstance(f, dict) else getattr(f, "path", str(f)))
                if file_path:
                    content_parts.append(gr.Image(file_path))
            
            # Add text part
            if text:
                content_parts.append(text)
            
            # If only text (no files), use simple string content
            if not files and text:
                content = text
            else:
                content = content_parts if content_parts else text
            
            history = history + [
                {"role": "user", "content": content},
            ]
            return None, history  # Clear input immediately
        
        async def generate_response(
            history: list[dict],
        ):
            """Generate assistant response with streaming."""
            if not history or history[-1].get("role") != "user":
                yield history
                return
            
            # Extract user message and images from the last user message
            user_content = history[-1]["content"]
            user_message = ""
            image_paths = []
            
            if isinstance(user_content, list):
                # Multi-part content (text + gr.Image components)
                for part in user_content:
                    if isinstance(part, str):
                        user_message += part
                    elif hasattr(part, 'value') and hasattr(part, '__class__'):
                        # gr.Image or gr.File component - extract path
                        val = part.value
                        if isinstance(val, dict):
                            path = val.get('path') or val.get('url', '')
                        elif hasattr(val, 'path'):
                            path = val.path
                        elif isinstance(val, str):
                            path = val
                        else:
                            path = str(val) if val else ''
                        if path:
                            image_paths.append(path)
                    elif isinstance(part, dict):
                        if "text" in part:
                            user_message += part["text"]
                        elif "path" in part:
                            image_paths.append(part["path"])
            else:
                user_message = str(user_content)
            
            if not user_message.strip() and not image_paths:
                user_message = "What do you see in this image?"
            
            # Convert image files to base64 for the agent
            images_b64 = []
            if image_paths:
                import base64
                for img_path in image_paths:
                    try:
                        with open(img_path, "rb") as f:
                            img_data = base64.b64encode(f.read()).decode("utf-8")
                            images_b64.append(img_data)
                    except Exception as img_err:
                        pass  # Skip unreadable images
            
            try:
                from local_pigeon.core.agent import StatusEvent, StatusType
                
                current_agent = await get_agent()
                
                # Add placeholder for assistant response
                history = history + [{"role": "assistant", "content": "Thinking..."}]
                yield history
                
                # Collect response with streaming and track status events
                response_parts = []
                status_lines = []
                
                def stream_callback(chunk: str) -> None:
                    response_parts.append(chunk)
                
                def status_callback(event: StatusEvent) -> None:
                    """Track status events for display."""
                    details = event.details or {}
                    # Format status based on event type
                    if event.type == StatusType.THINKING:
                        status_lines.append("💭 Thinking...")
                    elif event.type == StatusType.TOOL_START:
                        status_lines.append(f"🔧 Using tool: **{details.get('tool', 'unknown')}**")
                    elif event.type == StatusType.TOOL_ARGS:
                        status_lines.append(f"   ↳ {event.message}")
                    elif event.type == StatusType.TOOL_RESULT:
                        tool = details.get('tool', 'tool')
                        result_preview = str(details.get('result', ''))[:80]
                        if len(str(details.get('result', ''))) > 80:
                            result_preview += "..."
                        status_lines.append(f"   ✓ {tool} completed")
                    elif event.type == StatusType.TOOL_ERROR:
                        status_lines.append(f"   ✗ Error: {event.message}")
                    elif event.type == StatusType.ITERATION:
                        status_lines.append(f"🔄 {event.message}")
                    elif event.type == StatusType.DONE:
                        pass  # Don't show "done" - final response will follow
                
                response = await current_agent.chat(
                    user_message=user_message,
                    user_id="web_user",
                    session_id="web_session",
                    platform="web",
                    stream_callback=stream_callback,
                    status_callback=status_callback,
                    images=images_b64 or None,
                )
                
                # Build final content with status log if tools were actually used
                tool_call_count = len([l for l in status_lines if '🔧' in l])
                
                # Safety guard - ensure we have a response
                if not response or not response.strip():
                    response = "I received your message but couldn't generate a response. Please try again."
                
                if tool_call_count > 0:
                    # Format status as a collapsible details block
                    status_log = "\n".join(status_lines)
                    final_content = f"<details><summary>🔍 Agent activity ({tool_call_count} tool calls)</summary>\n\n```\n{status_log}\n```\n\n</details>\n\n{response}"
                else:
                    final_content = response
                
                # Update with final response
                history[-1]["content"] = final_content
                yield history
                
            except Exception as e:
                error_str = str(e)
                
                # Auto-download model if 404 (not found)
                if "404" in error_str or "not found" in error_str.lower():
                    model = settings.ollama.model
                    history[-1]["content"] = f"Downloading model {model}... This may take a few minutes."
                    yield history
                    
                    try:
                        import httpx
                        async with httpx.AsyncClient(timeout=600.0) as client:
                            async with client.stream(
                                "POST",
                                f"{settings.ollama.host}/api/pull",
                                json={"name": model},
                            ) as resp:
                                async for line in resp.aiter_lines():
                                    pass  # Consume stream
                        
                        # Retry the chat
                        history[-1]["content"] = "Model downloaded! Let me try again..."
                        yield history
                        
                        current_agent = await get_agent()
                        response = await current_agent.chat(
                            user_message=user_message,
                            user_id="web_user",
                            session_id="web_session",
                            platform="web",
                        )
                        history[-1]["content"] = response
                        yield history
                        return
                    except Exception as download_err:
                        error_str = f"Failed to download model: {download_err}"
                
                error_msg = f"Error: {error_str}"
                if history and history[-1].get("role") == "assistant":
                    history[-1]["content"] = error_msg
                else:
                    history = history + [{"role": "assistant", "content": error_msg}]
                yield history
        
        async def clear_history() -> list:
            """Clear chat history."""
            try:
                current_agent = await get_agent()
                await current_agent.clear_history("web_user")
            except Exception:
                pass
            return []

        async def poll_web_scheduled_notifications(history: list[dict] | None) -> list[dict]:
            """Poll and surface queued scheduler notifications in the chat UI."""
            try:
                current_agent = await get_agent()
                pending = await current_agent.scheduler.store.get_pending_notifications(
                    platform="web",
                    user_id="web_user",
                    limit=20,
                )

                if not pending:
                    return history or []

                updated_history = list(history or [])
                for notification in pending:
                    updated_history.append(
                        {
                            "role": "assistant",
                            "content": notification["message"],
                        }
                    )
                    await current_agent.scheduler.store.mark_notification_delivered(notification["id"])

                return updated_history
            except Exception:
                return history or []
        
        async def refresh_models() -> tuple[gr.Dropdown, gr.Dropdown]:
            """Refresh available models - shows catalog models plus installed."""
            try:
                import httpx
                from local_pigeon.core.llm_client import OllamaClient
                from local_pigeon.core.model_catalog import MODEL_CATALOG, ModelCategory
                
                # Create a temporary client to check capabilities
                temp_client = OllamaClient(host=settings.ollama.host)
                
                # Get installed models from Ollama
                installed_models = set()
                try:
                    async with httpx.AsyncClient() as client:
                        resp = await client.get(
                            f"{settings.ollama.host}/api/tags",
                            timeout=10.0,
                        )
                        data = resp.json()
                        for m in data.get("models", []):
                            installed_models.add(m["name"])
                except Exception:
                    pass
                
                # Build model choices from catalog
                model_choices = []
                vision_choices = [("(auto-detect)", "(auto-detect)")]  # Always include auto-detect
                seen_names = set()
                
                # Add catalog models with install status
                for model in MODEL_CATALOG:
                    if not model.ollama_name:
                        continue
                    
                    name = model.ollama_name
                    seen_names.add(name)
                    
                    # Check if installed
                    is_installed = name in installed_models
                    
                    # Category indicators
                    cat_icons = []
                    is_vision = ModelCategory.VISION in model.categories
                    if is_vision:
                        cat_icons.append("🖼️")
                    if ModelCategory.THINKING in model.categories:
                        cat_icons.append("🧠")
                    if ModelCategory.CODING in model.categories:
                        cat_icons.append("💻")
                    
                    status = "✅" if is_installed else "📥"
                    icons = " ".join(cat_icons)
                    display = f"{status} {name} {icons}".strip()
                    
                    model_choices.append((display, name))
                    
                    # Add to vision choices if it's a vision model and installed
                    if is_vision and is_installed:
                        vision_choices.append((f"🖼️ {name}", name))
                
                # Add installed models not in catalog
                for name in sorted(installed_models):
                    if name not in seen_names:
                        is_vision = temp_client.is_vision_model(name)
                        if is_vision:
                            display = f"✅ {name} 🖼️"
                            vision_choices.append((f"🖼️ {name}", name))
                        else:
                            display = f"✅ {name}"
                        model_choices.append((display, name))
                
                if not model_choices:
                    model_choices = [(settings.ollama.model, settings.ollama.model)]
                
                # Current model value
                current = settings.ollama.model
                current_vision = settings.ollama.vision_model or "(auto-detect)"
                
                return (
                    gr.Dropdown(
                        choices=model_choices,
                        value=current if any(c[1] == current for c in model_choices) else model_choices[0][1],
                    ),
                    gr.Dropdown(
                        choices=vision_choices,
                        value=current_vision if any(c[1] == current_vision for c in vision_choices) else "(auto-detect)",
                    ),
                )
            except Exception:
                return (
                    gr.Dropdown(
                        choices=[settings.ollama.model],
                        value=settings.ollama.model,
                    ),
                    gr.Dropdown(
                        choices=["(auto-detect)"],
                        value="(auto-detect)",
                    ),
                )
        
        async def change_model(model: str):
            """Change the active model and persist to settings. Auto-downloads if needed."""
            try:
                import httpx
                import json as _json
                
                # Check if model is installed
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{settings.ollama.host}/api/tags",
                        timeout=10.0,
                    )
                    data = resp.json()
                    installed = {m["name"] for m in data.get("models", [])}
                
                if model not in installed:
                    # Model not installed - try to pull it with progress
                    gr.Info(f"Downloading {model}... Check the Status field for progress.")
                    try:
                        async with httpx.AsyncClient(timeout=httpx.Timeout(1800.0)) as client:
                            async with client.stream(
                                "POST",
                                f"{settings.ollama.host}/api/pull",
                                json={"name": model, "stream": True},
                            ) as resp:
                                async for line in resp.aiter_lines():
                                    if not line.strip():
                                        continue
                                    try:
                                        prog = _json.loads(line)
                                        if "error" in prog:
                                            gr.Warning(f"Failed: {prog['error']}")
                                            return (
                                                f"❌ {prog['error']}",
                                                gr.update(value=settings.ollama.model),
                                                gr.update(value=settings.ollama.model),
                                            )
                                    except (ValueError, KeyError):
                                        continue
                        gr.Info(f"Downloaded {model} successfully!")
                    except Exception as e:
                        gr.Warning(f"Failed to download {model}: {e}")
                        return (
                            f"❌ Failed to download {model}: {e}",
                            gr.update(value=settings.ollama.model),
                            gr.update(value=settings.ollama.model),
                        )
                
                current_agent = await get_agent()
                current_agent.set_model(model)
                
                # Update settings object so UI reflects change
                settings.ollama.model = model
                
                # Persist to .env so it's remembered on restart
                _save_env_var("OLLAMA_MODEL", model)
                gr.Info(f"Switched to {model}")
                return (
                    f"✅ Active model: {model}",
                    gr.update(value=model),
                    gr.update(value=model),
                )
            except Exception as e:
                gr.Warning(f"Error: {e}")
                return (
                    f"❌ Error: {e}",
                    gr.update(value=settings.ollama.model),
                    gr.update(value=settings.ollama.model),
                )
        
        async def list_installed_models() -> list:
            """List installed models with their capabilities."""
            try:
                import httpx
                from local_pigeon.core.llm_client import OllamaClient
                
                temp_client = OllamaClient(host=settings.ollama.host)
                
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{settings.ollama.host}/api/tags",
                        timeout=10.0,
                    )
                    data = resp.json()
                    
                    rows = []
                    for m in data.get("models", []):
                        name = m["name"]
                        size_bytes = m.get("size", 0)
                        size_gb = size_bytes / (1024 ** 3)
                        size_display = f"{size_gb:.1f} GB" if size_gb >= 1 else f"{size_bytes / (1024 ** 2):.0f} MB"
                        
                        is_vision = temp_client.is_vision_model(name)
                        vision_display = "🖼️ Yes" if is_vision else "No"
                        
                        # Check if it's the current model
                        status = "✅ Active" if name == settings.ollama.model else "Available"
                        
                        rows.append([name, size_display, vision_display, status])
                    
                    return rows
            except Exception as e:
                return [[f"Error: {e}", "", "", ""]]
        
        async def pull_model(model_name: str, backend: str):
            """Pull/download a model from Ollama or HuggingFace with live progress."""
            if not model_name.strip():
                yield "⚠️ Please enter a model name"
                return
            
            model_name = model_name.strip()
            is_ollama = "Ollama" in backend
            
            if is_ollama:
                try:
                    import httpx
                    import json as _json
                    
                    # Check if Ollama is running
                    yield f"🔍 Checking Ollama connection..."
                    async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                        try:
                            check = await client.get(f"{settings.ollama.host}/api/tags")
                            if check.status_code != 200:
                                yield "❌ Ollama is not running. Start it with: `ollama serve`"
                                return
                        except Exception:
                            yield "❌ Cannot connect to Ollama. Make sure it's running with: `ollama serve`"
                            return
                    
                    yield f"📥 Starting download of {model_name}...\nThis may take several minutes for large models."
                    
                    # Stream the pull with progress updates
                    async with httpx.AsyncClient(timeout=httpx.Timeout(1800.0)) as client:
                        async with client.stream(
                            "POST",
                            f"{settings.ollama.host}/api/pull",
                            json={"name": model_name, "stream": True},
                        ) as resp:
                            if resp.status_code != 200:
                                yield f"❌ Failed to start download (HTTP {resp.status_code})"
                                return
                            
                            last_status = ""
                            async for line in resp.aiter_lines():
                                if not line.strip():
                                    continue
                                try:
                                    data = _json.loads(line)
                                    status = data.get("status", "")
                                    
                                    # Build progress display
                                    if "total" in data and "completed" in data:
                                        total = data["total"]
                                        completed = data["completed"]
                                        if total > 0:
                                            pct = completed / total * 100
                                            # Format sizes
                                            def _fmt_size(b):
                                                if b >= 1_073_741_824:
                                                    return f"{b / 1_073_741_824:.1f} GB"
                                                elif b >= 1_048_576:
                                                    return f"{b / 1_048_576:.0f} MB"
                                                else:
                                                    return f"{b / 1024:.0f} KB"
                                            
                                            bar_len = 20
                                            filled = int(bar_len * pct / 100)
                                            bar = "█" * filled + "░" * (bar_len - filled)
                                            
                                            progress_line = f"📥 {model_name}\n{status}\n[{bar}] {pct:.1f}%  ({_fmt_size(completed)} / {_fmt_size(total)})"
                                            if progress_line != last_status:
                                                last_status = progress_line
                                                yield progress_line
                                    elif status:
                                        status_line = f"📥 {model_name}\n⏳ {status}..."
                                        if status_line != last_status:
                                            last_status = status_line
                                            yield status_line
                                    
                                    # Check for error
                                    if "error" in data:
                                        yield f"❌ Error: {data['error']}"
                                        return
                                        
                                except (ValueError, KeyError):
                                    continue
                    
                    yield f"✅ Successfully installed {model_name}!\n\nSelect it from the Active Model dropdown above."
                            
                except Exception as e:
                    yield f"❌ Error pulling model: {str(e)}"
            else:
                # GGUF download via llama-cpp-python
                yield f"📥 Downloading GGUF model: {model_name}..."
                try:
                    from local_pigeon.core.llama_cpp_client import download_model, AVAILABLE_MODELS
                    from local_pigeon.core.model_catalog import find_model
                    
                    # Check if it's in our catalog
                    catalog_model = find_model(model_name)
                    if catalog_model and catalog_model.gguf_repo:
                        model_name = f"{catalog_model.gguf_repo.split('/')[-1]}"
                    
                    # Check if it's a known model
                    if model_name.lower().replace("-", "_").replace(" ", "_") in AVAILABLE_MODELS:
                        key = model_name.lower().replace("-", "_").replace(" ", "_")
                        path = download_model(key)
                        yield f"✅ Downloaded GGUF model to:\n{path}\n\nThe model is ready to use with llama-cpp-python backend."
                    elif "/" in model_name:
                        # Assume HuggingFace format: repo/filename.gguf
                        path = download_model(model_name)
                        yield f"✅ Downloaded GGUF model to:\n{path}"
                    else:
                        available = ", ".join(AVAILABLE_MODELS.keys())
                        yield f"❌ Unknown GGUF model: {model_name}\n\nAvailable: {available}\n\nOr use HuggingFace format: owner/repo/filename.gguf"
                        
                except ImportError:
                    yield "❌ GGUF support requires:\n`pip install llama-cpp-python huggingface_hub`"
                except Exception as e:
                    yield f"❌ Error downloading GGUF: {str(e)}"
        
        async def check_ollama_status() -> str:
            """Check if Ollama is running and get status."""
            try:
                import httpx
                
                async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                    resp = await client.get(f"{settings.ollama.host}/api/tags")
                    if resp.status_code == 200:
                        data = resp.json()
                        model_count = len(data.get("models", []))
                        return f"✅ Ollama is running at {settings.ollama.host}\n\n📦 {model_count} model(s) installed"
                    else:
                        return f"⚠️ Ollama responded but with status {resp.status_code}"
            except Exception as e:
                return f"❌ Ollama is not running or not reachable.\n\nStart it with: `ollama serve`\n\nError: {str(e)}"
        
        def load_model_catalog(category_filter: str) -> list:
            """Load model catalog filtered by category."""
            try:
                from local_pigeon.core.model_catalog import (
                    MODEL_CATALOG, ModelCategory,
                    get_recommended_models, get_thinking_models,
                    get_vision_models, get_coding_models,
                    get_small_models, get_models_by_category,
                    get_tool_calling_models,
                )
                
                # Map filter to category
                if category_filter == "⭐ Recommended":
                    models = get_recommended_models()
                elif category_filter == "🧠 Thinking/Reasoning":
                    models = get_thinking_models()
                elif category_filter == "🖼️ Vision":
                    models = get_vision_models()
                elif category_filter == "💻 Coding":
                    models = get_coding_models()
                elif category_filter == "💬 General":
                    models = get_models_by_category(ModelCategory.GENERAL)
                elif category_filter == "⚡ Small/Fast":
                    models = get_small_models()
                elif category_filter == "🔧 Tool Calling":
                    models = get_tool_calling_models()
                else:
                    models = MODEL_CATALOG
                
                # Format for display
                rows = []
                for model in models:
                    # Format categories with emojis
                    cat_emojis = {
                        ModelCategory.THINKING: "🧠",
                        ModelCategory.VISION: "🖼️",
                        ModelCategory.CODING: "💻",
                        ModelCategory.GENERAL: "💬",
                        ModelCategory.SMALL: "⚡",
                        ModelCategory.MULTILINGUAL: "🌍",
                        ModelCategory.TOOL_CALLING: "🔧",
                    }
                    categories = " ".join(cat_emojis.get(c, "") for c in model.categories)
                    
                    # Get Ollama name for display
                    ollama_name = model.ollama_name if model.ollama_name else "(GGUF only)"
                    
                    # Recommended indicator
                    name = f"⭐ {model.name}" if model.recommended else model.name
                    
                    rows.append([
                        name,
                        ollama_name,
                        model.size_label,
                        categories,
                        model.description,
                    ])
                
                return rows
            except Exception as e:
                return [[f"Error: {e}", "", "", "", ""]]
        
        def save_settings_handler(
            host: str,
            temp: float,
            tokens: int,
            checkpoint_mode_val: bool,
            max_iterations_val: int,
            threshold: float,
            require_approval_val: bool,
        ) -> str:
            """Save settings to config."""
            try:
                # Update settings object
                settings.ollama.host = host
                settings.ollama.temperature = temp
                settings.ollama.max_tokens = int(tokens)
                settings.agent.checkpoint_mode = checkpoint_mode_val
                settings.agent.max_tool_iterations = int(max_iterations_val)
                settings.payments.approval.threshold = threshold
                settings.payments.approval.require_approval = require_approval_val
                
                return "✅ Settings saved successfully!"
            except Exception as e:
                return f"❌ Error saving settings: {str(e)}"
        
        def save_vision_model_handler(vision_model: str) -> str:
            """Save vision model preference."""
            try:
                # Handle auto-detect selection
                if vision_model == "(auto-detect)":
                    settings.ollama.vision_model = ""
                else:
                    settings.ollama.vision_model = vision_model
                
                # Also save to .env file for persistence
                data_dir = get_data_dir()
                env_path = data_dir / ".env"
                
                # Read existing env
                env_lines = []
                if env_path.exists():
                    with open(env_path, 'r') as f:
                        env_lines = [l for l in f.readlines() if not l.startswith("OLLAMA_VISION_MODEL=")]
                
                # Add or update vision model setting
                if settings.ollama.vision_model:
                    env_lines.append(f"OLLAMA_VISION_MODEL={settings.ollama.vision_model}\\n")
                
                with open(env_path, 'w') as f:
                    f.writelines(env_lines)
                
                if vision_model == "(auto-detect)":
                    return "✅ Vision model set to auto-detect"
                return f"✅ Vision model set to: {vision_model}"
            except Exception as e:
                return f"❌ Error: {str(e)}"
        
        def open_data_folder() -> str:
            """Open the data folder in file explorer."""
            try:
                from local_pigeon.config import get_physical_data_dir
                # Use physical path to open the actual folder (resolves Windows Store virtualization)
                data_dir = get_physical_data_dir()
                if sys.platform == "win32":
                    os.startfile(data_dir)
                elif sys.platform == "darwin":
                    subprocess.run(["open", str(data_dir)])
                else:
                    subprocess.run(["xdg-open", str(data_dir)])
                return "📂 Opened data folder"
            except Exception as e:
                return f"❌ Error: {str(e)}"
        
        def handle_delete_data(include_config: bool) -> str:
            """Delete local data with user confirmation."""
            nonlocal agent
            try:
                results = delete_local_data(keep_config=not include_config)
                
                # Build status message
                deleted = [k for k, v in results.items() if v is True]
                not_found = [k for k, v in results.items() if v is False]
                errors = [f"{k}: {v}" for k, v in results.items() if isinstance(v, str)]
                
                msg_parts = []
                if deleted:
                    msg_parts.append(f"✅ **Deleted:** {', '.join(deleted)}")
                if not_found:
                    msg_parts.append(f"ℹ️ **Not found:** {', '.join(not_found)}")
                if errors:
                    msg_parts.append(f"❌ **Errors:** {', '.join(errors)}")
                
                if not msg_parts:
                    return "ℹ️ No data to delete"
                
                # Reset agent to clear any cached data
                agent = None
                
                return "\\n".join(msg_parts) + "\\n\\n⚠️ Please restart the app to fully reset."
            except Exception as e:
                return f"❌ Error deleting data: {str(e)}"
        
        # Memory handlers
        async def load_memories() -> list:
            """Load all memories for display."""
            try:
                memories = await memory_manager.get_all_memories("web_user")
                return [
                    [m.memory_type.value, m.key, m.value, m.source]
                    for m in memories
                ]
            except Exception:
                return []
        
        async def save_memory(mem_type: str, key: str, value: str) -> tuple[list, str]:
            """Save a new memory."""
            if not key.strip() or not value.strip():
                return await load_memories(), "❌ Key and value are required"
            
            try:
                memory_type = MemoryType(mem_type)
                await memory_manager.set_memory(
                    user_id="web_user",
                    key=key.strip(),
                    value=value.strip(),
                    memory_type=memory_type,
                    source="user",
                )
                return await load_memories(), f"✅ Saved: {key}"
            except Exception as e:
                return await load_memories(), f"❌ Error: {str(e)}"
        
        async def delete_memory(key: str) -> tuple[list, str]:
            """Delete a memory."""
            if not key.strip():
                return await load_memories(), "❌ Key is required"
            
            try:
                deleted = await memory_manager.delete_memory("web_user", key.strip())
                if deleted:
                    return await load_memories(), f"✅ Deleted: {key}"
                else:
                    return await load_memories(), f"⚠️ Not found: {key}"
            except Exception as e:
                return await load_memories(), f"❌ Error: {str(e)}"
        
        # Personalization handlers
        async def load_personalization() -> tuple[str, str]:
            """Load current personalization settings."""
            try:
                current_agent = await get_agent()
                user_settings = await current_agent.user_settings.get("web_user")
                return user_settings.bot_name, user_settings.user_display_name
            except Exception:
                return "Pigeon", ""
        
        async def save_personalization(bot_name: str, user_name: str) -> str:
            """Save personalization settings."""
            try:
                current_agent = await get_agent()
                
                # Validate bot name
                clean_bot_name = bot_name.strip() if bot_name else "Pigeon"
                if not clean_bot_name:
                    clean_bot_name = "Pigeon"
                
                clean_user_name = user_name.strip() if user_name else ""
                
                # Update settings
                await current_agent.user_settings.update(
                    "web_user",
                    bot_name=clean_bot_name,
                    user_display_name=clean_user_name,
                )
                
                greeting = f"Hi{', ' + clean_user_name if clean_user_name else ''}! "
                return f"✅ {greeting}I'm now {clean_bot_name}. Nice to meet you!"
            except Exception as e:
                return f"❌ Error saving settings: {str(e)}"
        
        # Voice transcription handler
        async def transcribe_audio(audio_path: str) -> dict | None:
            """Transcribe audio using speech recognition.
            
            Returns a MultimodalTextbox-compatible dict with text + empty files.
            """
            if not audio_path:
                return None
            
            try:
                # Try speech recognition with SpeechRecognition library
                try:
                    import speech_recognition as sr
                    recognizer = sr.Recognizer()
                    
                    with sr.AudioFile(audio_path) as source:
                        audio = recognizer.record(source)
                    
                    # Use Google's free speech recognition
                    text = recognizer.recognize_google(audio)
                    return {"text": text, "files": []}
                except ImportError:
                    return {"text": "[Voice input requires: pip install SpeechRecognition]", "files": []}
                except Exception as e:
                    return {"text": f"[Transcription error: {e}]", "files": []}
            
            except Exception as e:
                return {"text": f"[Error: {str(e)}]", "files": []}
        
        # Activity log handlers
        async def load_activity(platform_filter: str) -> tuple[list, str, str]:
            """Load recent activity across all platforms."""
            try:
                from local_pigeon.core.conversation import AsyncConversationManager
                from local_pigeon.config import get_data_dir
                from pathlib import Path
                from datetime import datetime, timezone
                import json
                
                # Build correct database path (same logic as agent)
                data_dir = get_data_dir()
                db_filename = settings.storage.database
                if Path(db_filename).is_absolute():
                    db_path = db_filename
                else:
                    db_path = str(data_dir / db_filename)
                
                conv_manager = AsyncConversationManager(db_path=db_path)
                
                platforms = None if platform_filter == "All" else [platform_filter]
                activity = await conv_manager.get_recent_activity(limit=50, platforms=platforms)
                
                # Format for display
                rows = []
                tool_usage = {}
                recent_tool_calls = []
                
                def convert_to_local_time(timestamp_str: str) -> str:
                    """Convert UTC timestamp to local time."""
                    if not timestamp_str:
                        return ""
                    try:
                        # Parse the UTC timestamp (stored as ISO format)
                        dt_utc = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                        if dt_utc.tzinfo is None:
                            dt_utc = dt_utc.replace(tzinfo=timezone.utc)
                        # Convert to local time
                        dt_local = dt_utc.astimezone()
                        return dt_local.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        return timestamp_str[:19] if len(timestamp_str) >= 19 else timestamp_str
                
                for item in activity:
                    # Parse and convert timestamp to local time
                    timestamp = convert_to_local_time(item.get("timestamp", ""))
                    
                    # Track tool usage and recent calls
                    if item.get("tool_calls"):
                        try:
                            calls = json.loads(item["tool_calls"])
                            for call in calls:
                                tool_name = call.get("name", "unknown")
                                tool_usage[tool_name] = tool_usage.get(tool_name, 0) + 1
                                
                                # Add to recent calls log
                                args_str = json.dumps(call.get("arguments", {}))
                                if len(args_str) > 80:
                                    args_str = args_str[:77] + "..."
                                recent_tool_calls.append(
                                    f"[{timestamp}] 🔧 {tool_name}({args_str})"
                                )
                        except Exception:
                            pass
                    
                    # Platform emoji
                    platform = item.get("platform", "")
                    platform_display = {
                        "web": "🌐 Web",
                        "discord": "💬 Discord",
                        "telegram": "📱 Telegram",
                        "cli": "💻 CLI",
                    }.get(platform, platform)
                    
                    rows.append([
                        timestamp,
                        platform_display,
                        item.get("user_id", "")[:20],
                        item.get("role", ""),
                        item.get("content", "")[:100] + ("..." if len(item.get("content", "")) > 100 else ""),
                    ])
                
                # Tool usage summary
                if tool_usage:
                    summary_lines = [f"• {name}: {count} calls" for name, count in sorted(tool_usage.items(), key=lambda x: -x[1])]
                    summary = "\n".join(summary_lines)
                else:
                    summary = "No tool usage recorded yet."
                
                # Recent tool calls log
                if recent_tool_calls:
                    recent_calls_text = "\n".join(recent_tool_calls[:20])  # Show last 20
                else:
                    recent_calls_text = "No recent tool calls."
                
                return rows, summary, recent_calls_text
            
            except Exception as e:
                return [], f"Error loading activity: {e}", ""
        
        # Integration handlers
        def generate_discord_invite(app_id: str) -> str:
            """Generate Discord bot invite URL."""
            if not app_id or not app_id.strip():
                return "⚠️ Enter your Application ID above"
            
            app_id = app_id.strip()
            if not app_id.isdigit():
                return "❌ Invalid Application ID (should be numbers only)"
            
            # Permissions bitmap:
            # - View Channels (1024)
            # - Send Messages (2048)
            # - Send Messages in Threads (274877906944)
            # - Embed Links (16384)
            # - Attach Files (32768)
            # - Add Reactions (64)
            # - Read Message History (65536)
            # - Use External Emojis (262144)
            # - Create Public Threads (34359738368)
            permissions = 309237981248
            
            invite_url = f"https://discord.com/api/oauth2/authorize?client_id={app_id}&permissions={permissions}&scope=bot%20applications.commands"
            return invite_url
        
        def save_discord_settings(enabled: bool, token: str, app_id: str) -> str:
            """Save Discord settings."""
            try:
                settings.discord.enabled = enabled
                settings.discord.bot_token = token
                # Save to .env file
                _save_env_var("DISCORD_ENABLED", str(enabled).lower())
                _save_env_var("DISCORD_BOT_TOKEN", token)
                if app_id:
                    _save_env_var("DISCORD_APP_ID", app_id)
                return "✅ Discord settings saved! Click 'Save & Restart' to apply."
            except Exception as e:
                return f"❌ Error: {str(e)}"
        
        def save_telegram_settings(enabled: bool, token: str) -> str:
            """Save Telegram settings."""
            try:
                settings.telegram.enabled = enabled
                settings.telegram.bot_token = token
                _save_env_var("TELEGRAM_ENABLED", str(enabled).lower())
                _save_env_var("TELEGRAM_BOT_TOKEN", token)
                return "✅ Telegram settings saved! Click 'Save & Restart' to apply."
            except Exception as e:
                return f"❌ Error: {str(e)}"
        
        def save_google_settings(uploaded_file: str | None, creds_path: str, gmail_enabled: bool, calendar_enabled: bool, drive_enabled: bool) -> str:
            """Save Google settings, handling uploaded file or manual path."""
            nonlocal agent
            try:
                final_path = creds_path
                
                # If a file was uploaded, copy it to the data directory
                if uploaded_file:
                    data_dir = get_data_dir()
                    dest_path = data_dir / "google_credentials.json"
                    
                    # Validate it's valid JSON with expected structure
                    try:
                        with open(uploaded_file, "r") as f:
                            creds_data = json.load(f)
                        # Check for expected OAuth credentials structure
                        if "installed" not in creds_data and "web" not in creds_data:
                            return "❌ Invalid credentials file. Expected OAuth client credentials from Google Cloud Console."
                    except json.JSONDecodeError:
                        return "❌ Invalid JSON file."
                    
                    # Copy file to data directory
                    shutil.copy2(uploaded_file, dest_path)
                    final_path = str(dest_path)
                
                if final_path and not Path(final_path).exists():
                    return f"❌ File not found: {final_path}"
                
                # Save enabled flags
                settings.google.gmail_enabled = gmail_enabled
                settings.google.calendar_enabled = calendar_enabled
                settings.google.drive_enabled = drive_enabled
                _save_env_var("GOOGLE_GMAIL_ENABLED", str(gmail_enabled).lower())
                _save_env_var("GOOGLE_CALENDAR_ENABLED", str(calendar_enabled).lower())
                _save_env_var("GOOGLE_DRIVE_ENABLED", str(drive_enabled).lower())
                
                if final_path:
                    settings.google.credentials_path = final_path
                    _save_env_var("GOOGLE_CREDENTIALS_PATH", final_path)
                
                # Reload agent tools if agent exists
                tools_reloaded = ""
                if agent is not None:
                    registered = agent.reload_tools()
                    enabled_tools = [t for t in registered if any(x in t.lower() for x in ["gmail", "calendar", "drive"])]
                    if enabled_tools:
                        tools_reloaded = f" Tools reloaded: {', '.join(enabled_tools)}"
                    else:
                        tools_reloaded = " (Google tools will be available after authorization)"
                
                if final_path:
                    return f"✅ Google settings saved!{tools_reloaded} Click 'Authorize with Google' to complete setup."
                else:
                    return f"✅ Google service settings saved!{tools_reloaded} Upload credentials.json to enable."
            except Exception as e:
                return f"❌ Error: {str(e)}"
        
        def authorize_google() -> tuple:
            """Trigger Google OAuth authorization flow."""
            nonlocal agent
            creds_path = settings.google.credentials_path
            if not creds_path or not Path(creds_path).exists():
                return (
                    "❌ Upload credentials.json first",
                    gr.update(visible=True, value="**Error:** You need to upload your `credentials.json` file before authorizing.\n\n1. Upload the file above\n2. Click 'Save Google Settings'\n3. Then click 'Authorize with Google'")
                )
            
            try:
                # Import here to avoid circular imports
                from google_auth_oauthlib.flow import InstalledAppFlow
                
                # Combined scopes for all services (matching what tools use)
                SCOPES = [
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
                
                # Run OAuth flow - opens browser automatically and handles callback
                flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
                creds = flow.run_local_server(port=0)
                
                # Save token
                data_dir = get_data_dir()
                token_path = data_dir / "google_token.json"
                with open(token_path, "w") as token:
                    token.write(creds.to_json())
                
                success_info = """### ✅ Authorization Complete!

**Your Google account is now connected.** Here's what you can do:

**Available Services:**
- 📧 **Gmail**: Read, search, and send emails
- 📅 **Calendar**: View and create events
- 📁 **Drive**: List, search, and read files

**Test it out:**
- Click the **🧪 Test Connection** button to verify everything works
- Or ask the AI: *"What's on my calendar today?"* or *"Show my recent emails"*

**Token saved to:** `{token_path}`
""".format(token_path=token_path)
                
                # Reload tools so Google tools are immediately available
                if agent is not None:
                    registered = agent.reload_tools()
                    google_tools = [t for t in registered if any(x in t.lower() for x in ["gmail", "calendar", "drive"])]
                    if google_tools:
                        success_info += f"\n**Tools loaded:** {', '.join(google_tools)}"
                
                return (
                    "✅ Google authorized successfully!",
                    gr.update(visible=True, value=success_info)
                )
            except Exception as e:
                error_info = f"""### ❌ Authorization Failed

**Error:** `{str(e)}`

**Troubleshooting:**
1. Make sure you complete the sign-in in your browser
2. Check that your OAuth credentials are for a "Desktop app" type
3. Ensure Gmail, Calendar, and Drive APIs are enabled in Google Cloud Console
4. Try uploading your credentials.json file again
"""
                return (
                    f"❌ Authorization failed: {str(e)}",
                    gr.update(visible=True, value=error_info)
                )
        
        def test_google_connection() -> tuple:
            """Test that Google services are accessible."""
            data_dir = get_data_dir()
            token_path = data_dir / "google_token.json"
            
            if not token_path.exists():
                return (
                    "⚠️ Not authorized yet",
                    gr.update(visible=True, value="**Not Authorized:** Click 'Authorize with Google' first to connect your account.")
                )
            
            results = []
            try:
                from google.oauth2.credentials import Credentials
                from googleapiclient.discovery import build
                
                creds = Credentials.from_authorized_user_file(str(token_path))
                
                # Direct links to enable each API
                API_ENABLE_LINKS = {
                    "Gmail": "https://console.cloud.google.com/apis/library/gmail.googleapis.com",
                    "Google Calendar": "https://console.cloud.google.com/apis/library/calendar-json.googleapis.com",
                    "Google Drive": "https://console.cloud.google.com/apis/library/drive.googleapis.com",
                }
                
                def _format_google_error(e: Exception, service_name: str) -> str:
                    """Format Google API errors with helpful messages."""
                    err_str = str(e)
                    if "403" in err_str:
                        link = API_ENABLE_LINKS.get(service_name, "https://console.cloud.google.com/apis/library")
                        return f"API not enabled - [Enable {service_name} API]({link})"
                    elif "401" in err_str or "invalid_grant" in err_str.lower():
                        return "Token expired - click 'Authorize with Google' again"
                    elif "404" in err_str:
                        return "Resource not found"
                    else:
                        return err_str[:60]
                
                # Test Gmail
                if settings.google.gmail_enabled:
                    try:
                        service = build("gmail", "v1", credentials=creds)
                        profile = service.users().getProfile(userId="me").execute()
                        results.append(f"✅ **Gmail**: Connected as `{profile.get('emailAddress', 'unknown')}`")
                    except Exception as e:
                        results.append(f"❌ **Gmail**: {_format_google_error(e, 'Gmail')}")
                else:
                    results.append("⏸️ **Gmail**: Not enabled (check the Gmail checkbox above and save)")
                
                # Test Calendar
                if settings.google.calendar_enabled:
                    try:
                        service = build("calendar", "v3", credentials=creds)
                        calendar = service.calendars().get(calendarId="primary").execute()
                        results.append(f"✅ **Calendar**: Connected - {calendar.get('summary', 'Primary')}")
                    except Exception as e:
                        results.append(f"❌ **Calendar**: {_format_google_error(e, 'Google Calendar')}")
                else:
                    results.append("⏸️ **Calendar**: Not enabled (check the Calendar checkbox above and save)")
                
                # Test Drive
                if settings.google.drive_enabled:
                    try:
                        service = build("drive", "v3", credentials=creds)
                        about = service.about().get(fields="user").execute()
                        user = about.get("user", {})
                        results.append(f"✅ **Drive**: Connected as `{user.get('displayName', 'unknown')}`")
                    except Exception as e:
                        results.append(f"❌ **Drive**: {_format_google_error(e, 'Google Drive')}")
                else:
                    results.append("⏸️ **Drive**: Not enabled (check the Drive checkbox above and save)")
                
                all_ok = all("✅" in r for r in results if "⏸️" not in r)
                has_errors = any("❌" in r for r in results)
                
                if has_errors:
                    status = "❌ Some services failed"
                elif all_ok and not all("⏸️" in r for r in results):
                    status = "✅ All enabled services working!"
                else:
                    status = "⚠️ No services enabled"
                
                test_info = "### 🧪 Connection Test Results\n\n" + "\n".join(results)
                
                # Add helpful tips based on results
                if has_errors:
                    test_info += "\n\n**Troubleshooting:**\n"
                    if any("API not enabled" in r for r in results):
                        test_info += "- Click the links above to enable each API, or enable all at once:\n"
                        test_info += "  - [Enable Gmail API](https://console.cloud.google.com/apis/library/gmail.googleapis.com)\n"
                        test_info += "  - [Enable Calendar API](https://console.cloud.google.com/apis/library/calendar-json.googleapis.com)\n"
                        test_info += "  - [Enable Drive API](https://console.cloud.google.com/apis/library/drive.googleapis.com)\n"
                    if any("Token expired" in r for r in results):
                        test_info += "- Click 'Authorize with Google' to refresh your token\n"
                elif all_ok:
                    test_info += "\n\n**Ready to use!** Ask the AI to interact with your Google services."
                
                return (status, gr.update(visible=True, value=test_info))
                
            except Exception as e:
                return (
                    f"❌ Test failed: {str(e)}",
                    gr.update(visible=True, value=f"**Error loading credentials:** `{str(e)}`\n\nTry re-authorizing with Google.")
                )
        
        def save_stripe_settings(enabled: bool, api_key: str) -> str:
            """Save Stripe settings."""
            try:
                settings.payments.stripe.enabled = enabled
                settings.payments.stripe.api_key = api_key
                _save_env_var("STRIPE_ENABLED", str(enabled).lower())
                _save_env_var("STRIPE_API_KEY", api_key)
                return "✅ Stripe settings saved!"
            except Exception as e:
                return f"❌ Error: {str(e)}"
        
        def save_browser_settings(enabled: bool, headless: bool) -> str:
            """Save browser automation settings."""
            nonlocal agent
            try:
                settings.web.browser.enabled = enabled
                settings.web.browser.headless = headless
                _save_env_var("BROWSER_ENABLED", str(enabled).lower())
                _save_env_var("BROWSER_HEADLESS", str(headless).lower())
                
                # Reload agent tools to pick up the change
                if agent is not None:
                    agent.settings.web.browser.enabled = enabled
                    agent.settings.web.browser.headless = headless
                    agent.reload_tools()
                
                if enabled and headless:
                    status = "✅ Enabled (headless) - Tools reloaded"
                elif enabled:
                    status = "✅ Enabled (GUI mode) - Tools reloaded"
                else:
                    status = "⚠️ Disabled - Tools reloaded"
                
                return status
            except Exception as e:
                return f"❌ Error: {str(e)}"
        
        def install_playwright() -> str:
            """Install Playwright and Chromium browser."""
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "playwright"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if result.returncode != 0:
                    return f"❌ pip install failed: {result.stderr}"
                
                # Install Chromium
                result = subprocess.run(
                    [sys.executable, "-m", "playwright", "install", "chromium"],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode != 0:
                    return f"❌ Browser install failed: {result.stderr}"
                
                return "✅ Playwright and Chromium installed successfully!"
            except subprocess.TimeoutExpired:
                return "❌ Installation timed out. Try running manually: pip install playwright && playwright install chromium"
            except Exception as e:
                return f"❌ Error: {str(e)}"
        
        def save_and_restart_discord(enabled: bool, token: str, app_id: str) -> str:
            """Save Discord settings and restart the app."""
            save_discord_settings(enabled, token, app_id)
            return restart_app()
        
        def save_and_restart_telegram(enabled: bool, token: str) -> str:
            """Save Telegram settings and restart the app."""
            save_telegram_settings(enabled, token)
            return restart_app()
        
        def restart_app() -> str:
            """Restart the Local Pigeon application."""
            import sys
            import os
            import subprocess
            
            # Schedule restart
            def do_restart():
                import time
                time.sleep(0.5)  # Brief delay to let response go through
                python = sys.executable
                # Use subprocess with proper list args to handle spaces in paths
                try:
                    subprocess.Popen([python] + sys.argv)
                except Exception:
                    # Fallback: try with shell=True for Windows paths with spaces
                    subprocess.Popen(f'"{python}" ' + ' '.join(f'"{a}"' for a in sys.argv), shell=True)
                os._exit(0)
            
            import threading
            threading.Thread(target=do_restart, daemon=True).start()
            
            return "🔄 Restarting Local Pigeon... The page will refresh automatically."
        
        # Wire up events - MultimodalTextbox has built-in submit button
        msg_input.submit(
            fn=add_user_message,
            inputs=[msg_input, chatbot],
            outputs=[msg_input, chatbot],
        ).then(
            fn=generate_response,
            inputs=[chatbot],
            outputs=[chatbot],
        )

        schedule_poller.tick(
            fn=poll_web_scheduled_notifications,
            inputs=[chatbot],
            outputs=[chatbot],
        )
        
        clear_btn.click(
            fn=clear_history,
            outputs=[chatbot],
        )
        
        refresh_models_btn.click(
            fn=refresh_models,
            outputs=[model_dropdown, vision_model_dropdown],
        )
        
        save_vision_model_btn.click(
            fn=save_vision_model_handler,
            inputs=[vision_model_dropdown],
            outputs=[model_status],
        )
        
        model_dropdown.change(
            fn=change_model,
            inputs=[model_dropdown],
            outputs=[model_status, model_dropdown, chat_model_dropdown],
        )
        
        # Chat tab model selector events - sync with main dropdown
        chat_model_dropdown.change(
            fn=change_model,
            inputs=[chat_model_dropdown],
            outputs=[model_status, model_dropdown, chat_model_dropdown],
        )
        
        async def refresh_chat_models():
            """Refresh models for chat tab dropdown."""
            result = await refresh_models()
            # Return just the first dropdown for chat
            return result[0]
        
        chat_refresh_btn.click(
            fn=refresh_chat_models,
            outputs=[chat_model_dropdown],
        )
        
        # Settings button toggles accordion
        def toggle_settings(current_state):
            new_state = not current_state
            return new_state, gr.update(open=new_state)
        
        chat_settings_btn.click(
            fn=toggle_settings,
            inputs=[settings_open],
            outputs=[settings_open, chat_settings_accordion],
        )
        
        save_settings_btn.click(
            fn=save_settings_handler,
            inputs=[
                ollama_host,
                temperature,
                max_tokens,
                checkpoint_mode,
                max_tool_iterations,
                payment_threshold,
                require_approval,
            ],
            outputs=[settings_status],
        )
        
        # Model discovery events
        refresh_models_list_btn.click(
            fn=list_installed_models,
            outputs=[models_list],
        )
        
        pull_model_btn.click(
            fn=pull_model,
            inputs=[pull_model_input, install_backend],
            outputs=[pull_model_status],
        )
        
        check_ollama_btn.click(
            fn=check_ollama_status,
            outputs=[pull_model_status],
        )
        
        catalog_category_filter.change(
            fn=load_model_catalog,
            inputs=[catalog_category_filter],
            outputs=[catalog_list],
        )
        
        # Starter pack install handlers
        async def install_starter_models(category: str):
            """Install recommended models for a category with streaming progress."""
            from local_pigeon.core.model_catalog import get_starter_pack_recommendations
            import httpx
            import json as _json
            
            recs = get_starter_pack_recommendations()
            models = recs.get(category, [])
            
            if not models:
                yield f"No {category} models found in recommendations."
                return
            
            ollama_models = [m for m in models if m.ollama_name]
            total = len(ollama_models)
            installed = 0
            
            yield f"📦 Installing {total} {category} model(s)..."
            
            for i, model in enumerate(ollama_models):
                model_name = model.ollama_name
                yield f"📥 [{i+1}/{total}] Downloading {model_name}...\n⏳ Starting download..."
                
                try:
                    async with httpx.AsyncClient(timeout=httpx.Timeout(1800.0)) as client:
                        async with client.stream(
                            "POST",
                            f"{settings.ollama.host}/api/pull",
                            json={"name": model_name, "stream": True},
                        ) as resp:
                            if resp.status_code != 200:
                                yield f"❌ [{i+1}/{total}] Failed to download {model_name} (HTTP {resp.status_code})\n\nContinuing with next model..."
                                continue
                            
                            last_status = ""
                            async for line in resp.aiter_lines():
                                if not line.strip():
                                    continue
                                try:
                                    data = _json.loads(line)
                                    status = data.get("status", "")
                                    
                                    if "total" in data and "completed" in data:
                                        total_bytes = data["total"]
                                        completed_bytes = data["completed"]
                                        if total_bytes > 0:
                                            pct = completed_bytes / total_bytes * 100
                                            def _fmt(b):
                                                if b >= 1_073_741_824: return f"{b/1_073_741_824:.1f} GB"
                                                elif b >= 1_048_576: return f"{b/1_048_576:.0f} MB"
                                                else: return f"{b/1024:.0f} KB"
                                            bar_len = 20
                                            filled = int(bar_len * pct / 100)
                                            bar = "█" * filled + "░" * (bar_len - filled)
                                            progress_line = f"📥 [{i+1}/{total}] {model_name}\n{status}\n[{bar}] {pct:.1f}%  ({_fmt(completed_bytes)} / {_fmt(total_bytes)})"
                                            if progress_line != last_status:
                                                last_status = progress_line
                                                yield progress_line
                                    elif status:
                                        status_line = f"📥 [{i+1}/{total}] {model_name}\n⏳ {status}..."
                                        if status_line != last_status:
                                            last_status = status_line
                                            yield status_line
                                    
                                    if "error" in data:
                                        yield f"❌ [{i+1}/{total}] {model_name}: {data['error']}"
                                        break
                                except (ValueError, KeyError):
                                    continue
                    
                    installed += 1
                    yield f"✅ [{i+1}/{total}] {model_name} installed!\n\n{'⏳ Next model...' if i+1 < total else ''}"
                    
                except Exception as e:
                    yield f"❌ [{i+1}/{total}] {model_name}: {str(e)[:80]}\n\nContinuing..."
            
            yield f"✅ Done! Installed {installed}/{total} {category} model(s).\n\nRefresh the model list to see them."
        
        async def install_tool_calling_models():
            async for msg in install_starter_models("tool_calling"):
                yield msg
        
        async def install_vision_models():
            async for msg in install_starter_models("vision"):
                yield msg
        
        async def install_thinking_models():
            async for msg in install_starter_models("thinking"):
                yield msg
        
        install_tools_btn.click(
            fn=install_tool_calling_models,
            outputs=[starter_install_status],
        )
        
        install_vision_btn.click(
            fn=install_vision_models,
            outputs=[starter_install_status],
        )
        
        install_thinking_btn.click(
            fn=install_thinking_models,
            outputs=[starter_install_status],
        )
        
        # Click on catalog row to populate install input
        def on_catalog_select(evt: gr.SelectData, current_data: list) -> str:
            """Handle catalog row selection - populate model name for install."""
            try:
                if evt.index is not None and len(evt.index) >= 1:
                    row_idx = evt.index[0]
                    if row_idx < len(current_data):
                        # Column 1 is Ollama Name
                        ollama_name = current_data[row_idx][1]
                        if ollama_name and "(GGUF only)" not in ollama_name:
                            return ollama_name
                return ""
            except Exception:
                return ""
        
        catalog_list.select(
            fn=on_catalog_select,
            inputs=[catalog_list],
            outputs=[pull_model_input],
        )
        
        # Load catalog on app start
        app.load(
            fn=load_model_catalog,
            inputs=[catalog_category_filter],
            outputs=[catalog_list],
        )
        
        open_folder_btn.click(
            fn=open_data_folder,
            outputs=[folder_status],
        )
        
        delete_data_btn.click(
            fn=handle_delete_data,
            inputs=[delete_config_too],
            outputs=[folder_status],
        )
        
        # Memory events
        refresh_memories_btn.click(
            fn=load_memories,
            outputs=[memories_display],
        )
        
        save_memory_btn.click(
            fn=save_memory,
            inputs=[memory_type_dropdown, memory_key_input, memory_value_input],
            outputs=[memories_display, memory_status],
        )
        
        delete_memory_btn.click(
            fn=delete_memory,
            inputs=[delete_key_input],
            outputs=[memories_display, memory_status],
        )
        
        # Personalization events
        save_personalization_btn.click(
            fn=save_personalization,
            inputs=[bot_name_input, user_name_input],
            outputs=[personalization_status],
        ).then(
            fn=lambda: gr.update(visible=True),
            outputs=[personalization_status],
        )
        
        # Load personalization on startup
        app.load(
            fn=load_personalization,
            outputs=[bot_name_input, user_name_input],
        )
        
        # Voice input events - transcribe and populate message box
        voice_input.change(
            fn=transcribe_audio,
            inputs=[voice_input],
            outputs=[msg_input],
        )
        
        # Activity log events
        refresh_activity_btn.click(
            fn=load_activity,
            inputs=[activity_platform_filter],
            outputs=[activity_log, tool_usage_summary, recent_tool_calls],
        )
        
        activity_platform_filter.change(
            fn=load_activity,
            inputs=[activity_platform_filter],
            outputs=[activity_log, tool_usage_summary, recent_tool_calls],
        )
        
        # Auto-refresh activity when tab is selected
        activity_tab.select(
            fn=load_activity,
            inputs=[activity_platform_filter],
            outputs=[activity_log, tool_usage_summary, recent_tool_calls],
        )
        
        # Integration events
        generate_invite_btn.click(
            fn=generate_discord_invite,
            inputs=[discord_app_id],
            outputs=[discord_invite_url],
        )
        
        save_discord_btn.click(
            fn=save_discord_settings,
            inputs=[discord_enabled, discord_token, discord_app_id],
            outputs=[discord_status],
        )
        
        restart_discord_btn.click(
            fn=save_and_restart_discord,
            inputs=[discord_enabled, discord_token, discord_app_id],
            outputs=[discord_status],
        )
        
        save_telegram_btn.click(
            fn=save_telegram_settings,
            inputs=[telegram_enabled, telegram_token],
            outputs=[telegram_status],
        )
        
        restart_telegram_btn.click(
            fn=save_and_restart_telegram,
            inputs=[telegram_enabled, telegram_token],
            outputs=[telegram_status],
        )
        
        save_google_btn.click(
            fn=save_google_settings,
            inputs=[google_creds_upload, google_creds_path, google_gmail_enabled, google_calendar_enabled, google_drive_enabled],
            outputs=[google_status],
        )
        
        authorize_google_btn.click(
            fn=authorize_google,
            outputs=[google_status, google_auth_info],
        )
        
        test_google_btn.click(
            fn=test_google_connection,
            outputs=[google_status, google_auth_info],
        )
        
        save_stripe_btn.click(
            fn=save_stripe_settings,
            inputs=[stripe_enabled, stripe_key_input],
            outputs=[stripe_status],
        )
        
        # ========== MCP Handlers ==========
        
        async def refresh_mcp_status():
            """Get status of connected MCP servers."""
            try:
                current_agent = await get_agent()
                rows = []
                
                if current_agent.mcp_manager:
                    for conn in current_agent.mcp_manager.list_connections():
                        status = "✅ Connected" if conn.connected else "❌ Disconnected"
                        tool_count = len(conn.tools)
                        tool_names = ", ".join(t.name for t in conn.tools[:3])
                        if len(conn.tools) > 3:
                            tool_names += f" (+{len(conn.tools) - 3} more)"
                        rows.append([conn.name, status, f"{tool_count}: {tool_names}"])
                
                if not rows:
                    rows.append(["No servers connected", "", ""])
                
                # Get list of server names for removal dropdown
                server_names = []
                if current_agent.mcp_manager:
                    server_names = [conn.name for conn in current_agent.mcp_manager.list_connections()]
                
                return rows, gr.update(choices=server_names)
            except Exception as e:
                return [["Error", str(e), ""]], gr.update(choices=[])
        
        mcp_refresh_btn.click(
            fn=refresh_mcp_status,
            outputs=[mcp_servers_display, mcp_remove_choice],
        )
        
        def on_popular_server_selected(choice: str | None):
            """Update config fields based on selected popular server."""
            if not choice:
                return "", "", gr.update(visible=True)
            
            # Parse server name from choice
            parts = choice.split(" - ")
            server_key = parts[0].split(" ")[-1] if parts else ""
            
            from local_pigeon.tools.mcp.manager import POPULAR_MCP_SERVERS
            server_info = POPULAR_MCP_SERVERS.get(server_key, {})
            
            show_path = server_info.get("requires_path", False)
            
            return (
                server_key,  # name
                "",  # api key
                gr.update(visible=show_path),  # path input visibility
            )
        
        mcp_popular_choice.change(
            fn=on_popular_server_selected,
            inputs=[mcp_popular_choice],
            outputs=[mcp_server_name, mcp_api_key, mcp_path_input],
        )
        
        def toggle_custom_url_visibility(transport: str):
            """Show/hide URL field based on transport type."""
            return gr.update(visible=(transport == "sse"))
        
        mcp_custom_transport.change(
            fn=toggle_custom_url_visibility,
            inputs=[mcp_custom_transport],
            outputs=[mcp_custom_url],
        )
        
        async def test_mcp_server(choice: str | None, name: str, api_key: str, path: str):
            """Test connection to an MCP server."""
            if not choice or not name:
                return "❌ Please select a server and enter a name"
            
            parts = choice.split(" - ")
            server_key = parts[0].split(" ")[-1] if parts else ""
            
            from local_pigeon.tools.mcp.manager import POPULAR_MCP_SERVERS, MCPManager
            server_info = POPULAR_MCP_SERVERS.get(server_key)
            
            if not server_info:
                return f"❌ Unknown server: {server_key}"
            
            # Build args
            args = list(server_info["args"])
            if server_info.get("requires_path") and path:
                args.append(path)
            
            # Build env
            env = {}
            if server_info.get("requires_env"):
                for env_key in server_info["requires_env"]:
                    if api_key:
                        env[env_key] = api_key
            
            manager = MCPManager(connection_timeout=15)
            
            try:
                connection = await manager.connect_stdio_server(
                    name=name,
                    command=server_info["command"],
                    args=args,
                    env=env if env else None,
                )
                
                tool_names = [t.name for t in connection.tools]
                await manager.disconnect_all()
                
                return f"✅ Connected! Found {len(tool_names)} tools:\n" + "\n".join(f"  • {t}" for t in tool_names[:10])
                
            except Exception as e:
                return f"❌ Connection failed: {str(e)}"
        
        mcp_test_btn.click(
            fn=test_mcp_server,
            inputs=[mcp_popular_choice, mcp_server_name, mcp_api_key, mcp_path_input],
            outputs=[mcp_result],
        )
        
        async def add_mcp_server(
            choice: str | None,
            name: str,
            api_key: str,
            path: str,
            mcp_enabled_val: bool,
            auto_approve_val: bool,
        ):
            """Add an MCP server to config and connect."""
            if not choice or not name:
                return "❌ Please select a server and enter a name", [["No servers connected", "", ""]], gr.update()
            
            parts = choice.split(" - ")
            server_key = parts[0].split(" ")[-1] if parts else ""
            
            from local_pigeon.tools.mcp.manager import POPULAR_MCP_SERVERS
            server_info = POPULAR_MCP_SERVERS.get(server_key)
            
            if not server_info:
                return f"❌ Unknown server: {server_key}", [["No servers connected", "", ""]], gr.update()
            
            # Build args
            args = list(server_info["args"])
            if server_info.get("requires_path") and path:
                args.append(path)
            
            # Build env
            env = {}
            if server_info.get("requires_env"):
                for env_key in server_info["requires_env"]:
                    if api_key:
                        env[env_key] = api_key
            
            # Build server config
            server_config = {
                "name": name,
                "transport": server_info["transport"],
                "command": server_info["command"],
                "args": args,
            }
            if env:
                server_config["env"] = env
            
            # Save to config.yaml
            import yaml
            config_path = get_data_dir() / "config.yaml"
            
            if config_path.exists():
                with open(config_path) as f:
                    config = yaml.safe_load(f) or {}
            else:
                config = {}
            
            if "mcp" not in config:
                config["mcp"] = {"enabled": True, "servers": []}
            
            config["mcp"]["enabled"] = mcp_enabled_val
            config["mcp"]["auto_approve"] = auto_approve_val
            
            if "servers" not in config["mcp"]:
                config["mcp"]["servers"] = []
            
            # Check if already exists
            existing_names = [s.get("name") for s in config["mcp"]["servers"]]
            if name in existing_names:
                for i, s in enumerate(config["mcp"]["servers"]):
                    if s.get("name") == name:
                        config["mcp"]["servers"][i] = server_config
                        break
            else:
                config["mcp"]["servers"].append(server_config)
            
            with open(config_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False)
            
            # Reload MCP servers in agent
            try:
                current_agent = await get_agent()
                tools = await current_agent.reload_mcp_servers()
                
                # Refresh display
                rows = []
                if current_agent.mcp_manager:
                    for conn in current_agent.mcp_manager.list_connections():
                        status = "✅ Connected" if conn.connected else "❌ Disconnected"
                        tool_count = len(conn.tools)
                        rows.append([conn.name, status, f"{tool_count} tools"])
                
                if not rows:
                    rows.append(["No servers connected", "", ""])
                
                server_names = []
                if current_agent.mcp_manager:
                    server_names = [conn.name for conn in current_agent.mcp_manager.list_connections()]
                
                return (
                    f"✅ Added server '{name}' with {len(tools)} total MCP tools now available",
                    rows,
                    gr.update(choices=server_names),
                )
            except Exception as e:
                return (
                    f"⚠️ Saved to config but failed to connect: {str(e)}",
                    [["Error connecting", "", ""]],
                    gr.update(choices=[]),
                )
        
        mcp_add_btn.click(
            fn=add_mcp_server,
            inputs=[mcp_popular_choice, mcp_server_name, mcp_api_key, mcp_path_input, mcp_enabled, mcp_auto_approve],
            outputs=[mcp_result, mcp_servers_display, mcp_remove_choice],
        )
        
        async def add_custom_mcp_server(
            name: str,
            transport: str,
            command: str,
            args_str: str,
            env_str: str,
            url: str,
            mcp_enabled_val: bool,
            auto_approve_val: bool,
        ):
            """Add a custom MCP server to config and connect."""
            if not name:
                return "❌ Please enter a server name", [["No servers connected", "", ""]], gr.update()
            
            # Parse args
            args = [a.strip() for a in args_str.split(",") if a.strip()] if args_str else []
            
            # Parse env
            env = {}
            if env_str:
                for line in env_str.strip().split("\n"):
                    if "=" in line:
                        key, val = line.split("=", 1)
                        env[key.strip()] = val.strip()
            
            # Build server config
            server_config = {
                "name": name,
                "transport": transport,
            }
            
            if transport == "stdio":
                server_config["command"] = command or "npx"
                server_config["args"] = args
            else:
                server_config["url"] = url
            
            if env:
                server_config["env"] = env
            
            # Save to config.yaml
            import yaml
            config_path = get_data_dir() / "config.yaml"
            
            if config_path.exists():
                with open(config_path) as f:
                    config = yaml.safe_load(f) or {}
            else:
                config = {}
            
            if "mcp" not in config:
                config["mcp"] = {"enabled": True, "servers": []}
            
            config["mcp"]["enabled"] = mcp_enabled_val
            config["mcp"]["auto_approve"] = auto_approve_val
            
            if "servers" not in config["mcp"]:
                config["mcp"]["servers"] = []
            
            # Check if already exists
            existing_names = [s.get("name") for s in config["mcp"]["servers"]]
            if name in existing_names:
                for i, s in enumerate(config["mcp"]["servers"]):
                    if s.get("name") == name:
                        config["mcp"]["servers"][i] = server_config
                        break
            else:
                config["mcp"]["servers"].append(server_config)
            
            with open(config_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False)
            
            # Reload MCP servers in agent
            try:
                current_agent = await get_agent()
                tools = await current_agent.reload_mcp_servers()
                
                # Refresh display
                rows = []
                if current_agent.mcp_manager:
                    for conn in current_agent.mcp_manager.list_connections():
                        status = "✅ Connected" if conn.connected else "❌ Disconnected"
                        tool_count = len(conn.tools)
                        rows.append([conn.name, status, f"{tool_count} tools"])
                
                if not rows:
                    rows.append(["No servers connected", "", ""])
                
                server_names = []
                if current_agent.mcp_manager:
                    server_names = [conn.name for conn in current_agent.mcp_manager.list_connections()]
                
                return (
                    f"✅ Added custom server '{name}' with {len(tools)} total MCP tools",
                    rows,
                    gr.update(choices=server_names),
                )
            except Exception as e:
                return (
                    f"⚠️ Saved to config but failed to connect: {str(e)}",
                    [["Error connecting", "", ""]],
                    gr.update(choices=[]),
                )
        
        mcp_add_custom_btn.click(
            fn=add_custom_mcp_server,
            inputs=[mcp_custom_name, mcp_custom_transport, mcp_custom_command, mcp_custom_args, mcp_custom_env, mcp_custom_url, mcp_enabled, mcp_auto_approve],
            outputs=[mcp_custom_result, mcp_servers_display, mcp_remove_choice],
        )
        
        async def test_custom_mcp_server(
            name: str,
            transport: str,
            command: str,
            args_str: str,
            env_str: str,
            url: str,
        ):
            """Test connection to a custom MCP server."""
            if not name:
                return "❌ Please enter a server name"
            
            from local_pigeon.tools.mcp.manager import MCPManager
            
            # Parse args
            args = [a.strip() for a in args_str.split(",") if a.strip()] if args_str else []
            
            # Parse env
            env = {}
            if env_str:
                for line in env_str.strip().split("\n"):
                    if "=" in line:
                        key, val = line.split("=", 1)
                        env[key.strip()] = val.strip()
            
            manager = MCPManager(connection_timeout=15)
            
            try:
                if transport == "stdio":
                    connection = await manager.connect_stdio_server(
                        name=name,
                        command=command or "npx",
                        args=args,
                        env=env if env else None,
                    )
                else:
                    connection = await manager.connect_sse_server(
                        name=name,
                        url=url,
                    )
                
                tool_names = [t.name for t in connection.tools]
                await manager.disconnect_all()
                
                return f"✅ Connected! Found {len(tool_names)} tools:\n" + "\n".join(f"  • {t}" for t in tool_names[:10])
                
            except Exception as e:
                return f"❌ Connection failed: {str(e)}"
        
        mcp_test_custom_btn.click(
            fn=test_custom_mcp_server,
            inputs=[mcp_custom_name, mcp_custom_transport, mcp_custom_command, mcp_custom_args, mcp_custom_env, mcp_custom_url],
            outputs=[mcp_custom_result],
        )
        
        async def remove_mcp_server(server_name: str | None):
            """Remove an MCP server from config."""
            if not server_name:
                return "❌ Please select a server to remove", [["No servers connected", "", ""]], gr.update()
            
            import yaml
            config_path = get_data_dir() / "config.yaml"
            
            if config_path.exists():
                with open(config_path) as f:
                    config = yaml.safe_load(f) or {}
            else:
                return "❌ No config file found", [["No servers connected", "", ""]], gr.update()
            
            if "mcp" not in config or "servers" not in config["mcp"]:
                return "❌ No MCP servers configured", [["No servers connected", "", ""]], gr.update()
            
            # Remove server
            config["mcp"]["servers"] = [
                s for s in config["mcp"]["servers"]
                if s.get("name") != server_name
            ]
            
            with open(config_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False)
            
            # Reload MCP servers
            try:
                current_agent = await get_agent()
                await current_agent.reload_mcp_servers()
                
                # Refresh display
                rows = []
                if current_agent.mcp_manager:
                    for conn in current_agent.mcp_manager.list_connections():
                        status = "✅ Connected" if conn.connected else "❌ Disconnected"
                        tool_count = len(conn.tools)
                        rows.append([conn.name, status, f"{tool_count} tools"])
                
                if not rows:
                    rows.append(["No servers connected", "", ""])
                
                server_names = []
                if current_agent.mcp_manager:
                    server_names = [conn.name for conn in current_agent.mcp_manager.list_connections()]
                
                return (
                    f"✅ Removed server '{server_name}'",
                    rows,
                    gr.update(choices=server_names),
                )
            except Exception as e:
                return (
                    f"⚠️ Removed from config but error reloading: {str(e)}",
                    [["Error", "", ""]],
                    gr.update(choices=[]),
                )
        
        mcp_remove_btn.click(
            fn=remove_mcp_server,
            inputs=[mcp_remove_choice],
            outputs=[mcp_result, mcp_servers_display, mcp_remove_choice],
        )
        
        save_browser_btn.click(
            fn=save_browser_settings,
            inputs=[browser_enabled, browser_headless],
            outputs=[browser_status],
        )
        
        install_playwright_btn.click(
            fn=install_playwright,
            outputs=[browser_status],
        )
        
        async def get_loaded_tools() -> str:
            """Get list of tools actually loaded in the agent."""
            try:
                current_agent = await get_agent()
                tools = current_agent.tools.list_tools()
                if not tools:
                    return "⚠️ No tools loaded.\n\nMake sure to:\n1. Enable tools in Integrations tab\n2. Save settings\n3. Authorize (for Google tools)"
                tool_names = sorted([t.name for t in tools])
                return "✅ " + "\n✅ ".join(tool_names)
            except Exception as e:
                return f"❌ Error: {e}"
        
        refresh_loaded_tools_btn.click(
            fn=get_loaded_tools,
            outputs=[loaded_tools_display],
        )
        
        # Load memories on startup
        app.load(
            fn=load_memories,
            outputs=[memories_display],
        )
        
        # Add Ctrl+Enter keyboard shortcut for sending messages
        app.load(
            fn=None,
            js=ctrl_enter_js,
        )
        
        # Cleanup on close
        async def cleanup_on_close():
            nonlocal agent
            if agent is not None:
                await agent.shutdown()
        
        app.unload(fn=cleanup_on_close)
    
    return app


def _save_env_var(key: str, value: str) -> None:
    """Save an environment variable to the .env file and current process."""
    import os
    
    # Set in current process immediately
    os.environ[key] = value
    
    data_dir = get_data_dir()
    env_path = data_dir / ".env"
    
    # Read existing
    existing = {}
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    existing[k] = v
    
    # Update
    existing[key] = value
    
    # Write back
    with open(env_path, "w") as f:
        for k, v in existing.items():
            f.write(f"{k}={v}\n")


def launch_ui(
    settings: Settings | None = None,
    share: bool = False,
    server_name: str = "127.0.0.1",
    server_port: int = 7860,
    shared_agent: "LocalPigeonAgent | None" = None,
) -> None:
    """
    Launch the Gradio web UI.
    
    Args:
        settings: Application settings
        share: Create a public share link
        server_name: Server hostname
        server_port: Server port
        shared_agent: Optional pre-initialized agent to share with Discord/Telegram
    """
    app = create_app(settings, shared_agent=shared_agent)
    
    launch_kwargs = {
        "server_name": server_name,
        "server_port": server_port,
        "share": share,
        "show_error": True,
    }
    
    # Gradio 6.0+ expects theme/css in launch()
    if _gradio_6_plus:
        if hasattr(app, '_lp_theme'):
            launch_kwargs["theme"] = app._lp_theme
        if hasattr(app, '_lp_css'):
            launch_kwargs["css"] = app._lp_css
    
    app.launch(**launch_kwargs)


if __name__ == "__main__":
    launch_ui()
