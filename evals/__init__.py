"""
Local Pigeon Evaluation Framework

Provides structured evaluations to test:
- Tool usage (does the model call the right tools?)
- Response quality (is the response helpful?)
- Instruction following (does the model follow system prompts?)
"""

from .tool_usage import (
    ALL_EVAL_CASES,
    GMAIL_EVAL_CASES,
    CALENDAR_EVAL_CASES,
    WEB_SEARCH_EVAL_CASES,
    NO_TOOL_EVAL_CASES,
    ToolEvalCase,
    EvalResult,
    ToolUsageEvaluator,
    run_evals,
    get_cases_by_tag,
    get_cases_by_tool,
)

__all__ = [
    "ALL_EVAL_CASES",
    "GMAIL_EVAL_CASES",
    "CALENDAR_EVAL_CASES", 
    "WEB_SEARCH_EVAL_CASES",
    "NO_TOOL_EVAL_CASES",
    "ToolEvalCase",
    "EvalResult",
    "ToolUsageEvaluator",
    "run_evals",
    "get_cases_by_tag",
    "get_cases_by_tool",
]