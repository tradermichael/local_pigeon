"""
Tool Usage Evaluations

Tests whether the model correctly uses tools when asked.
Each test case has:
- user_message: What the user says
- expected_tool: Tool that should be called (or None)
- expected_action: Action parameter (for multi-action tools)
- description: What we're testing
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any
from pathlib import Path


@dataclass
class ToolEvalCase:
    """A single evaluation case for tool usage."""
    id: str
    user_message: str
    expected_tool: str | None  # None means no tool expected
    expected_action: str | None = None  # For tools with action param
    expected_args: dict[str, Any] = field(default_factory=dict)
    description: str = ""
    tags: list[str] = field(default_factory=list)


@dataclass
class EvalResult:
    """Result of running an eval case."""
    case_id: str
    passed: bool
    expected_tool: str | None
    actual_tool: str | None
    expected_action: str | None
    actual_action: str | None
    model_response: str
    error: str | None = None


# =============================================================================
# EVAL CASES: Gmail Tool
# =============================================================================

GMAIL_EVAL_CASES = [
    ToolEvalCase(
        id="gmail_list_basic",
        user_message="what are my latest emails?",
        expected_tool="gmail",
        expected_action="list",
        description="Basic request to list emails",
        tags=["gmail", "list", "basic"],
    ),
    ToolEvalCase(
        id="gmail_list_five",
        user_message="show me my 5 latest emails",
        expected_tool="gmail",
        expected_action="list",
        description="Request for specific number of emails",
        tags=["gmail", "list"],
    ),
    ToolEvalCase(
        id="gmail_check",
        user_message="check my email",
        expected_tool="gmail",
        expected_action="list",
        description="Informal request to check email",
        tags=["gmail", "list", "informal"],
    ),
    ToolEvalCase(
        id="gmail_unread",
        user_message="do I have any new emails?",
        expected_tool="gmail",
        expected_action="list",
        description="Question about new emails",
        tags=["gmail", "list", "question"],
    ),
    ToolEvalCase(
        id="gmail_search",
        user_message="find emails from Amazon",
        expected_tool="gmail",
        expected_action="search",
        expected_args={"query": "from:Amazon"},
        description="Search for emails from specific sender",
        tags=["gmail", "search"],
    ),
    ToolEvalCase(
        id="gmail_inbox",
        user_message="what's in my inbox?",
        expected_tool="gmail",
        expected_action="list",
        description="Question about inbox contents",
        tags=["gmail", "list", "informal"],
    ),
]

# =============================================================================
# EVAL CASES: Calendar Tool  
# =============================================================================

CALENDAR_EVAL_CASES = [
    ToolEvalCase(
        id="calendar_today",
        user_message="what's on my calendar today?",
        expected_tool="calendar",
        expected_action="list",
        description="Request for today's events",
        tags=["calendar", "list", "basic"],
    ),
    ToolEvalCase(
        id="calendar_week",
        user_message="what do I have this week?",
        expected_tool="calendar",
        expected_action="list",
        description="Request for week's events",
        tags=["calendar", "list"],
    ),
    ToolEvalCase(
        id="calendar_schedule",
        user_message="show me my schedule",
        expected_tool="calendar",
        expected_action="list",
        description="General schedule request",
        tags=["calendar", "list", "informal"],
    ),
    ToolEvalCase(
        id="calendar_meetings",
        user_message="what meetings do I have?",
        expected_tool="calendar",
        expected_action="list",
        description="Request for meetings",
        tags=["calendar", "list"],
    ),
    ToolEvalCase(
        id="calendar_free",
        user_message="am I free tomorrow at 2pm?",
        expected_tool="calendar",
        expected_action="free",
        description="Free/busy check",
        tags=["calendar", "free"],
    ),
]

# =============================================================================
# EVAL CASES: Web Search Tool
# =============================================================================

WEB_SEARCH_EVAL_CASES = [
    ToolEvalCase(
        id="search_weather",
        user_message="what's the weather today?",
        expected_tool="web_search",
        description="Weather query requires search",
        tags=["search", "weather"],
    ),
    ToolEvalCase(
        id="search_news",
        user_message="what's happening in the news?",
        expected_tool="web_search",
        description="News query requires search",
        tags=["search", "news"],
    ),
    ToolEvalCase(
        id="search_stock",
        user_message="what's the Apple stock price?",
        expected_tool="web_search",
        description="Stock price requires search",
        tags=["search", "stock"],
    ),
]

# =============================================================================
# EVAL CASES: No Tool Expected
# =============================================================================

NO_TOOL_EVAL_CASES = [
    ToolEvalCase(
        id="no_tool_greeting",
        user_message="hello!",
        expected_tool=None,
        description="Greeting doesn't need tools",
        tags=["no_tool", "greeting"],
    ),
    ToolEvalCase(
        id="no_tool_math",
        user_message="what's 2 + 2?",
        expected_tool=None,
        description="Simple math doesn't need tools",
        tags=["no_tool", "math"],
    ),
    ToolEvalCase(
        id="no_tool_knowledge",
        user_message="what is the capital of France?",
        expected_tool=None,
        description="Basic knowledge doesn't need tools",
        tags=["no_tool", "knowledge"],
    ),
]

# Combine all cases
ALL_EVAL_CASES = (
    GMAIL_EVAL_CASES + 
    CALENDAR_EVAL_CASES + 
    WEB_SEARCH_EVAL_CASES + 
    NO_TOOL_EVAL_CASES
)


def get_cases_by_tag(tag: str) -> list[ToolEvalCase]:
    """Get all eval cases with a specific tag."""
    return [c for c in ALL_EVAL_CASES if tag in c.tags]


def get_cases_by_tool(tool_name: str) -> list[ToolEvalCase]:
    """Get all eval cases for a specific tool."""
    return [c for c in ALL_EVAL_CASES if c.expected_tool == tool_name]


class ToolUsageEvaluator:
    """
    Evaluator for tool usage.
    
    Tests whether the model calls the expected tools for various prompts.
    """
    
    def __init__(self, agent):
        """
        Initialize the evaluator.
        
        Args:
            agent: LocalPigeonAgent instance to test
        """
        self.agent = agent
        self.results: list[EvalResult] = []
    
    async def run_case(self, case: ToolEvalCase) -> EvalResult:
        """
        Run a single eval case.
        
        Returns:
            EvalResult with pass/fail status
        """
        from local_pigeon.core.llm_client import parse_tool_calls_from_text
        
        try:
            # Get the raw model response (before tool execution)
            # We need to check if it contains tool calls
            
            # Build messages like the agent does
            system_prompt = await self.agent.get_personalized_system_prompt("eval_user")
            
            from local_pigeon.core.llm_client import Message
            messages = [
                Message(role="system", content=system_prompt),
                Message(role="user", content=case.user_message),
            ]
            
            # Get tool definitions
            tools = self.agent.tools.get_tool_definitions()
            
            # Call the LLM
            response = await self.agent.llm.achat(messages, tools)
            
            # Parse tool calls from response
            actual_tool = None
            actual_action = None
            
            if response.tool_calls:
                # Native tool calling
                actual_tool = response.tool_calls[0].name
                actual_action = response.tool_calls[0].arguments.get("action")
            else:
                # Check for prompt-based tool calls
                tool_calls = parse_tool_calls_from_text(response.content or "")
                if tool_calls:
                    actual_tool = tool_calls[0]["name"]
                    actual_action = tool_calls[0]["arguments"].get("action")
            
            # Evaluate
            tool_match = actual_tool == case.expected_tool
            action_match = (
                case.expected_action is None or 
                actual_action == case.expected_action
            )
            passed = tool_match and action_match
            
            return EvalResult(
                case_id=case.id,
                passed=passed,
                expected_tool=case.expected_tool,
                actual_tool=actual_tool,
                expected_action=case.expected_action,
                actual_action=actual_action,
                model_response=response.content or "",
            )
            
        except Exception as e:
            return EvalResult(
                case_id=case.id,
                passed=False,
                expected_tool=case.expected_tool,
                actual_tool=None,
                expected_action=case.expected_action,
                actual_action=None,
                model_response="",
                error=str(e),
            )
    
    async def run_cases(
        self, 
        cases: list[ToolEvalCase] | None = None,
        tags: list[str] | None = None,
    ) -> list[EvalResult]:
        """
        Run multiple eval cases.
        
        Args:
            cases: Specific cases to run (default: all)
            tags: Filter by tags
        
        Returns:
            List of EvalResults
        """
        if cases is None:
            cases = ALL_EVAL_CASES
        
        if tags:
            cases = [c for c in cases if any(t in c.tags for t in tags)]
        
        results = []
        for case in cases:
            print(f"Running: {case.id}... ", end="", flush=True)
            result = await self.run_case(case)
            results.append(result)
            print("✅ PASS" if result.passed else f"❌ FAIL (got {result.actual_tool})")
        
        self.results = results
        return results
    
    def print_summary(self) -> None:
        """Print a summary of eval results."""
        if not self.results:
            print("No results to summarize")
            return
        
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        
        print("\n" + "=" * 60)
        print(f"EVAL SUMMARY: {passed}/{total} passed ({100*passed/total:.1f}%)")
        print("=" * 60)
        
        # Group by tool
        by_tool: dict[str | None, list[EvalResult]] = {}
        for r in self.results:
            tool = r.expected_tool or "no_tool"
            if tool not in by_tool:
                by_tool[tool] = []
            by_tool[tool].append(r)
        
        for tool, results in by_tool.items():
            tool_passed = sum(1 for r in results if r.passed)
            print(f"\n{tool}: {tool_passed}/{len(results)}")
            for r in results:
                status = "✅" if r.passed else "❌"
                print(f"  {status} {r.case_id}")
                if not r.passed:
                    print(f"      Expected: {r.expected_tool}:{r.expected_action}")
                    print(f"      Got:      {r.actual_tool}:{r.actual_action}")
                    if r.error:
                        print(f"      Error: {r.error}")
    
    def save_results(self, path: str | Path) -> None:
        """Save results to JSON file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            "total": len(self.results),
            "passed": sum(1 for r in self.results if r.passed),
            "results": [
                {
                    "case_id": r.case_id,
                    "passed": r.passed,
                    "expected_tool": r.expected_tool,
                    "actual_tool": r.actual_tool,
                    "expected_action": r.expected_action,
                    "actual_action": r.actual_action,
                    "error": r.error,
                }
                for r in self.results
            ],
        }
        
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        
        print(f"Results saved to {path}")


async def run_evals(
    model: str | None = None,
    tags: list[str] | None = None,
    save_path: str | None = None,
) -> list[EvalResult]:
    """
    Run evaluations.
    
    Args:
        model: Override the model to test
        tags: Filter cases by tags
        save_path: Path to save results JSON
    
    Returns:
        List of EvalResults
    """
    from local_pigeon.core.agent import LocalPigeonAgent
    from local_pigeon.config import Settings
    
    settings = Settings.load()
    
    if model:
        settings.ollama.model = model
    
    print(f"Running evals with model: {settings.ollama.model}")
    print("-" * 60)
    
    agent = LocalPigeonAgent(settings)
    await agent.initialize()
    
    evaluator = ToolUsageEvaluator(agent)
    results = await evaluator.run_cases(tags=tags)
    
    evaluator.print_summary()
    
    if save_path:
        evaluator.save_results(save_path)
    
    return results


# CLI entry point
if __name__ == "__main__":
    import sys
    
    tags = None
    model = None
    save_path = None
    
    # Parse simple CLI args
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--model" and i + 1 < len(args):
            model = args[i + 1]
            i += 2
        elif args[i] == "--tags" and i + 1 < len(args):
            tags = args[i + 1].split(",")
            i += 2
        elif args[i] == "--save" and i + 1 < len(args):
            save_path = args[i + 1]
            i += 2
        else:
            i += 1
    
    asyncio.run(run_evals(model=model, tags=tags, save_path=save_path))
