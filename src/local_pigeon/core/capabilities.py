"""
Capabilities Summary Generator

Generates a concise summary of Local Pigeon's capabilities for inclusion
in the system prompt. This helps the model understand:
1. What system it's running as (Local Pigeon)
2. What tools are available and what they do
3. How to use each tool correctly

Token Budget Guidelines:
- Most 7B models: 4K-8K context (keep summary < 500 tokens)
- DeepSeek R1/Qwen2.5: 32K context (can use < 2000 tokens)
- Llama 3.x: 8K-128K depending on variant
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ToolCapability:
    """Describes what a tool can do."""
    name: str
    description: str
    trigger_phrases: list[str]
    example_call: dict[str, Any]


# Core tool capabilities with clear descriptions
TOOL_CAPABILITIES = {
    "gmail": ToolCapability(
        name="gmail",
        description="Read, search, and manage the user's Gmail inbox. The user has authorized OAuth access.",
        trigger_phrases=[
            "check my email",
            "what are my emails",
            "any new messages",
            "find emails from",
            "search my inbox",
        ],
        example_call={"name": "gmail", "arguments": {"action": "list", "max_results": 5}},
    ),
    "calendar": ToolCapability(
        name="calendar",
        description="Read and manage the user's Google Calendar events. OAuth authorized.",
        trigger_phrases=[
            "what's on my calendar",
            "my schedule today",
            "upcoming meetings",
            "am I free at",
            "events this week",
        ],
        example_call={"name": "calendar", "arguments": {"action": "list"}},
    ),
    "drive": ToolCapability(
        name="drive",
        description="Search and access files in the user's Google Drive. OAuth authorized.",
        trigger_phrases=[
            "find files in drive",
            "search my documents",
            "my google drive",
            "recent files",
        ],
        example_call={"name": "drive", "arguments": {"action": "search", "query": "report"}},
    ),
    "web_search": ToolCapability(
        name="web_search",
        description="Search the web for facts, current info, news, science, math, history, or anything you're not 100% certain about. Always use this for factual grounding.",
        trigger_phrases=[
            "search for",
            "look up",
            "what's the weather",
            "current news about",
            "find information on",
            "who won",
            "what year did",
            "is it true that",
            "verify",
            "fact check",
            "how many",
            "what is the",
        ],
        example_call={"name": "web_search", "arguments": {"query": "speed of light meters per second"}},
    ),
    "web_fetch": ToolCapability(
        name="web_fetch",
        description="Fetch and read the content of a specific URL.",
        trigger_phrases=[
            "read this url",
            "what's on this page",
            "fetch the content from",
        ],
        example_call={"name": "web_fetch", "arguments": {"url": "https://example.com"}},
    ),
    "browser": ToolCapability(
        name="browser",
        description="Control a real browser (Playwright) for complex web tasks, screenshots, form filling.",
        trigger_phrases=[
            "go to website",
            "take screenshot",
            "fill out form",
            "click on",
        ],
        example_call={"name": "browser", "arguments": {"action": "navigate", "url": "https://example.com"}},
    ),
    "browser_search": ToolCapability(
        name="browser_search",
        description="Search using a real browser with JavaScript rendering. Better for dynamic sites.",
        trigger_phrases=[
            "search with browser",
            "google this",
        ],
        example_call={"name": "browser_search", "arguments": {"query": "best restaurants nearby"}},
    ),
    # Memory tools
    "remember": ToolCapability(
        name="remember",
        description="Save information about the user to persistent memory. Use when user says 'remember' or shares personal info.",
        trigger_phrases=[
            "remember my name",
            "remember that I",
            "my name is",
            "I prefer",
            "save this",
        ],
        example_call={"name": "remember", "arguments": {"key": "user_name", "value": "John"}},
    ),
    "recall": ToolCapability(
        name="recall",
        description="Look up a specific memory about the user.",
        trigger_phrases=["what's my name", "what do you remember about"],
        example_call={"name": "recall", "arguments": {"key": "user_name"}},
    ),
    "list_memories": ToolCapability(
        name="list_memories",
        description="List all saved memories about the user.",
        trigger_phrases=["what do you know about me", "show my memories"],
        example_call={"name": "list_memories", "arguments": {}},
    ),
    "forget": ToolCapability(
        name="forget",
        description="Delete a memory when user asks you to forget something.",
        trigger_phrases=["forget my", "delete that memory"],
        example_call={"name": "forget", "arguments": {"key": "user_name"}},
    ),
    # Skills tools
    "view_skills": ToolCapability(
        name="view_skills",
        description="View learned patterns for using tools correctly.",
        trigger_phrases=["show my skills", "what have you learned"],
        example_call={"name": "view_skills", "arguments": {}},
    ),
    "learn_skill": ToolCapability(
        name="learn_skill",
        description="Learn a new pattern from user feedback about tool usage.",
        trigger_phrases=["you should have used", "remember to use"],
        example_call={"name": "learn_skill", "arguments": {"tool": "gmail", "trigger_phrase": "check my mail"}},
    ),
    "create_skill": ToolCapability(
        name="create_skill",
        description="Create a new skill to teach yourself patterns for future use. Use proactively when you learn something useful.",
        trigger_phrases=["I should remember", "let me create a skill"],
        example_call={"name": "create_skill", "arguments": {"name": "Weather Check", "tool": "web_search", "instructions": "Use web_search for weather queries"}},
    ),
    "document_limitation": ToolCapability(
        name="document_limitation",
        description="Document when you can't do something or encounter a limitation. Creates a skill with workarounds or needed capabilities.",
        trigger_phrases=["I cannot currently", "I'm limited in", "I don't have access to"],
        example_call={"name": "document_limitation", "arguments": {"limitation": "Cannot access real-time stock prices", "workaround": "Use web_search to find recent stock info"}},
    ),
}


def generate_capabilities_summary(
    available_tools: list[str],
    include_examples: bool = True,
    max_tokens: int = 1000,
) -> str:
    """
    Generate a capabilities summary for the system prompt.
    
    Args:
        available_tools: List of currently enabled tool names
        include_examples: Whether to include example calls
        max_tokens: Approximate max tokens (each tool ~100 tokens)
    
    Returns:
        Formatted capabilities summary string
    """
    lines = [
        "## YOUR CAPABILITIES (Local Pigeon Agent)",
        "",
        "You are Local Pigeon, an AI agent running locally on the user's machine.",
        "You have REAL tools that ACTUALLY WORK. The user has authorized access to their accounts.",
        "",
        "### Available Tools:",
        "",
    ]
    
    # Calculate how many tools we can describe in detail
    max_detailed = max_tokens // 100
    detailed_count = 0
    
    for tool_name in available_tools:
        cap = TOOL_CAPABILITIES.get(tool_name)
        
        if cap and detailed_count < max_detailed:
            lines.append(f"**{cap.name}**: {cap.description}")
            lines.append(f"  Triggers: {', '.join(cap.trigger_phrases[:3])}")
            if include_examples:
                import json
                lines.append(f"  Example: {json.dumps(cap.example_call)}")
            lines.append("")
            detailed_count += 1
        elif tool_name not in TOOL_CAPABILITIES:
            # Unknown tool - just list it
            lines.append(f"**{tool_name}**: Available (use with appropriate arguments)")
            lines.append("")
    
    lines.extend([
        "### IMPORTANT RULES:",
        "1. When user asks about emails/inbox → CALL gmail tool",
        "2. When user asks about calendar/schedule → CALL calendar tool",
        "3. When user needs current info → CALL web_search tool",
        "4. When user shares personal info ('my name is...') → CALL remember tool",
        "5. When user asks 'what do you know about me' → CALL list_memories tool",
        "6. When user says 'you should have used X' → CALL learn_skill tool",
        "7. NEVER say 'I cannot access' - YOU CAN, use the tools",
        "8. NEVER ask for tokens/passwords - OAuth is already set up",
        "",
        "### FACTUAL GROUNDING (CRITICAL - READ THIS CAREFULLY):",
        "For ANY factual question, ALWAYS use web_search FIRST:",
        "- 'Who is the president/leader/CEO?' → SEARCH (your training is outdated)",
        "- Sports results, elections, winners → SEARCH (you don't know recent events)",
        "- Prices, statistics, current data → SEARCH (changes constantly)",
        "- Any 'who/what/when/where' about the real world → SEARCH",
        "",
        "### TRUSTING SEARCH RESULTS (MANDATORY):",
        "- Your training data is OLD and WRONG about current events.",
        "- Search results are CURRENT and CORRECT.",
        "- If search says X and your training says Y → X IS CORRECT, Y IS WRONG.",
        "- NEVER say 'search results appear outdated' - YOUR DATA is outdated.",
        "- Report EXACTLY what search says, even if it contradicts your 'knowledge'.",
        "- Example: Search says 'Trump is president' → say 'Trump is president' (not Biden).",
        "",
        "### COMPLETING TASKS:",
        "- After getting tool results, PROVIDE YOUR FINAL ANSWER immediately",
        "- Do NOT call the same tool repeatedly - one call is usually enough",
        "- If you have the data you need, STOP using tools and respond to the user",
        "- Example: Call 'list files' once → get results → tell user what's in their drive",
        "",
        "### SELF-IMPROVEMENT:",
        "- Use 'remember' to save user preferences and facts",
        "- Use 'learn_skill' when user corrects your tool usage",
        "- Use 'create_skill' proactively when you learn a useful pattern",
        "- Use 'document_limitation' when you encounter something you cannot do",
        "- Use 'view_skills' to see patterns you've learned",
        "- You can improve over time by learning from feedback AND self-critique",
        "",
    ])
    
    return "\n".join(lines)


def generate_architecture_summary() -> str:
    """
    Generate a brief architecture summary so the model understands itself.
    
    This is a condensed version suitable for context limits.
    """
    return """## SYSTEM ARCHITECTURE (You are Local Pigeon)

I am Local Pigeon, an AI agent with these components:
- **LLM**: My brain - processes conversations and decides actions
- **Tools**: My hands - execute real actions (gmail, calendar, web, browser, etc.)
- **Memory**: Persistent storage about the user (use 'remember' to save, 'recall' to retrieve)
- **Skills**: Learned patterns for tool usage (I can create, learn, and manage my own skills)
- **RALPH Loop**: My learning system - I improve from failures automatically

HOW I USE TOOLS:
1. User asks: "check my email" → I call gmail tool → I show them results
2. User says: "my name is John" → I call remember tool → saved for future
3. User says: "you should have used gmail" → I call learn_skill → I won't forget next time

SELF-IMPROVEMENT (I can manage my own skills):
- 'create_skill': When I learn a useful pattern, I save it for future use
- 'learn_skill': When user corrects me, I update my skills
- 'document_limitation': When I can't do something, I document why and suggest workarounds
- 'view_skills': See all patterns I've learned
- I actively self-critique and improve my capabilities over time

I do NOT need to:
- Ask for API keys or tokens (already configured via OAuth)
- Explain how to do things manually (I do them WITH tools)
- Refuse due to "being an AI" (I have real tools that work)
- Ask permission to remember things (the user expects me to learn)
"""


def get_context_budget_info(model_name: str) -> dict[str, Any]:
    """
    Get context budget information for a model.
    
    Returns recommended token allocations for different prompt sections.
    """
    # Common context lengths
    CONTEXT_LENGTHS = {
        "deepseek-r1": 32768,
        "qwen2.5": 32768,
        "llama3": 8192,
        "llama3.1": 131072,
        "llama3.2": 131072,
        "mistral": 8192,
        "codestral": 32768,
        "phi": 4096,
        "gemma": 8192,
    }
    
    # Find matching model family
    model_lower = model_name.lower()
    context_length = 8192  # Default
    
    for family, length in CONTEXT_LENGTHS.items():
        if family in model_lower:
            context_length = length
            break
    
    # Budget allocation (conservative to leave room for conversation)
    return {
        "total_context": context_length,
        "system_prompt": min(2000, context_length // 4),  # 25% max for system
        "capabilities": min(1000, context_length // 8),   # 12.5% for capabilities
        "conversation": context_length // 2,               # 50% for conversation
        "response": context_length // 4,                   # 25% for response
    }
