"""
Theme configuration and CSS for the Local Pigeon Gradio UI.

Extracted from app.py to keep the main file focused on layout and logic.
Provides light/dark mode CSS variables, theme toggle JS, and Ctrl+Enter JS.
"""

# Try to import themes (may not be available in all gradio versions)
try:
    from gradio.themes import Soft as SoftTheme

    _has_themes = True
except ImportError:
    SoftTheme = None
    _has_themes = False


def create_theme():
    """Create the Gradio Soft theme if available."""
    if _has_themes and SoftTheme is not None:
        return SoftTheme(primary_hue="blue", secondary_hue="slate")
    return None


# ── JavaScript ─────────────────────────────────────────────────────

THEME_JS = """
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

CTRL_ENTER_JS = """
() => {
    setTimeout(() => {
        const textareas = document.querySelectorAll('textarea');
        textareas.forEach(textarea => {
            textarea.removeEventListener('keydown', textarea._ctrlEnterHandler);
            textarea._ctrlEnterHandler = (e) => {
                if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
                    e.preventDefault();
                    const sendBtn = document.querySelector('button.primary');
                    if (sendBtn) sendBtn.click();
                }
            };
            textarea.addEventListener('keydown', textarea._ctrlEnterHandler);
        });
    }, 500);
}
"""

# ── CSS ────────────────────────────────────────────────────────────

GEMINI_CSS = """
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
