"""
RALPH Loop - Reflect, Analyze, Learn, Plan, Handle

A self-improvement loop that helps the model learn from tool usage failures.
When tool calls fail or the model doesn't use tools when it should:

1. **Reflect**: What did the user ask for? What tool should have been used?
2. **Analyze**: Why did the tool call fail or not happen?
3. **Learn**: Generate/update a skill with the correct pattern
4. **Plan**: How to apply this skill in the future
5. **Handle**: Retry with the new knowledge

The RALPH loop creates skills in the skills/learned/ directory that persist
and improve the model's tool usage over time.
"""

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from local_pigeon.core.skills import Skill, SkillsManager
from local_pigeon.storage.failure_log import FailureLog, FailureRecord, AsyncFailureLog


@dataclass
class RALPHAnalysis:
    """Result of RALPH loop analysis."""
    user_message: str
    expected_tool: str | None
    actual_tool: str | None
    failure_reason: str
    suggested_skill: Skill | None
    retry_recommended: bool
    confidence: float  # 0.0 - 1.0


class RALPHLoop:
    """
    Self-improvement loop for tool usage.
    
    Detects tool usage problems and learns from them to improve future responses.
    """
    
    # Patterns that strongly indicate tool usage is needed
    TOOL_TRIGGER_PATTERNS = {
        "gmail": [
            r"\b(email|inbox|mail|gmail)\b",
            r"\b(check|read|show|get|list)\b.*\b(email|mail|inbox)\b",
            r"\bunread\b",
        ],
        "calendar": [
            r"\b(calendar|schedule|meeting|event|appointment)\b",
            r"\b(free|busy|available)\b.*\b(time|today|tomorrow)\b",
            r"\bwhat('s| is| do i have)\b.*\b(today|tomorrow|this week)\b",
        ],
        "web_search": [
            r"\b(search|look up|find|google)\b",
            r"\b(weather|news|stock|price)\b",
            r"\b(what|who|when|where|how)\b.*\b(current|latest|recent|today)\b",
        ],
        "drive": [
            r"\b(drive|google drive|files|documents)\b",
            r"\b(upload|download|share)\b.*\b(file|document)\b",
        ],
        "discord": [
            r"\b(discord|server|channel|dm)\b",
            r"\b(send|post|message)\b.*\b(discord)\b",
        ],
    }
    
    # Phrases indicating the model refused/failed to use tools
    REFUSAL_PATTERNS = [
        r"I('m| am) (unable|not able|cannot) to (access|retrieve|check|read)",
        r"I (don't|do not) have (access|the ability)",
        r"(cannot|can't) (directly )?(access|retrieve|check|read)",
        r"I('m| am) an AI (and|so) I (cannot|can't)",
        r"I (don't|do not) have (real-time|live) access",
        r"(unfortunately|sorry),? I (cannot|can't)",
    ]
    
    def __init__(
        self,
        skills_manager: SkillsManager,
        failure_log: FailureLog | AsyncFailureLog,
        llm_client=None,  # Optional: for LLM-powered analysis
    ):
        self.skills = skills_manager
        self.failures = failure_log
        self.llm = llm_client
        self._compile_patterns()
    
    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        self._tool_patterns = {
            tool: [re.compile(p, re.IGNORECASE) for p in patterns]
            for tool, patterns in self.TOOL_TRIGGER_PATTERNS.items()
        }
        self._refusal_patterns = [
            re.compile(p, re.IGNORECASE) for p in self.REFUSAL_PATTERNS
        ]
    
    def detect_expected_tool(self, user_message: str) -> str | None:
        """
        Detect which tool should have been used based on user message.
        
        Returns the tool name or None if no tool seems needed.
        """
        user_lower = user_message.lower()
        
        # Check each tool's patterns
        scores = {}
        for tool, patterns in self._tool_patterns.items():
            score = sum(1 for p in patterns if p.search(user_lower))
            if score > 0:
                scores[tool] = score
        
        if scores:
            # Return tool with highest score
            return max(scores.keys(), key=lambda k: scores[k])
        
        return None
    
    def detect_refusal(self, response: str) -> bool:
        """Check if the response indicates the model refused to use tools."""
        for pattern in self._refusal_patterns:
            if pattern.search(response):
                return True
        return False
    
    def analyze_tool_failure(
        self,
        user_message: str,
        model_response: str,
        actual_tool_call: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> RALPHAnalysis:
        """
        Analyze why tool usage failed.
        
        This is the REFLECT + ANALYZE phases of the RALPH loop.
        
        Args:
            user_message: What the user asked
            model_response: What the model responded
            actual_tool_call: The tool call made (if any)
            error: Error message if tool execution failed
        
        Returns:
            RALPHAnalysis with diagnosis and suggested fix
        """
        expected_tool = self.detect_expected_tool(user_message)
        actual_tool = actual_tool_call.get("name") if actual_tool_call else None
        
        # Determine failure reason
        if actual_tool_call and error:
            # Tool was called but execution failed
            failure_reason = f"Tool '{actual_tool}' was called but failed: {error}"
            confidence = 0.9
        elif expected_tool and not actual_tool:
            # Tool should have been used but wasn't
            if self.detect_refusal(model_response):
                failure_reason = (
                    f"Model refused to use '{expected_tool}' tool, saying it cannot access the service. "
                    f"The tool IS available and should have been used."
                )
                confidence = 0.95
            else:
                failure_reason = (
                    f"Expected '{expected_tool}' tool to be called based on user message, "
                    f"but no tool was used. Model may not have recognized the trigger."
                )
                confidence = 0.8
        elif expected_tool and actual_tool != expected_tool:
            # Wrong tool was used
            failure_reason = (
                f"Expected '{expected_tool}' tool but '{actual_tool}' was called instead."
            )
            confidence = 0.7
        else:
            # Not clear what went wrong
            failure_reason = "Unable to determine the specific failure reason."
            confidence = 0.3
        
        # Generate suggested skill
        suggested_skill = None
        if expected_tool and confidence > 0.5:
            suggested_skill = self._generate_skill(
                tool=expected_tool,
                user_message=user_message,
                failure_reason=failure_reason,
            )
        
        return RALPHAnalysis(
            user_message=user_message,
            expected_tool=expected_tool,
            actual_tool=actual_tool,
            failure_reason=failure_reason,
            suggested_skill=suggested_skill,
            retry_recommended=expected_tool is not None and confidence > 0.6,
            confidence=confidence,
        )
    
    def _generate_skill(
        self,
        tool: str,
        user_message: str,
        failure_reason: str,
    ) -> Skill:
        """
        Generate a new skill based on the failure.
        
        This is the LEARN phase of the RALPH loop.
        """
        # Extract key phrases from user message
        words = user_message.lower().split()
        triggers = []
        
        # Find 2-3 word phrases that are good triggers
        for i in range(len(words) - 1):
            phrase = " ".join(words[i:i+2])
            if len(phrase) > 5:  # Skip very short phrases
                triggers.append(phrase)
        
        # Also add single important words
        important_words = {"email", "calendar", "search", "weather", "inbox", "schedule"}
        for word in words:
            if word in important_words:
                triggers.append(word)
        
        # Generate skill ID
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        skill_id = f"learned_{tool}_{timestamp}"
        
        # Build example from the user message
        example = {
            "user": user_message,
            "tool_call": {"name": tool, "arguments": self._guess_arguments(tool, user_message)},
        }
        
        # Generate instructions
        instructions = (
            f"When the user says something like '{user_message}', "
            f"ALWAYS use the {tool} tool. Do not say you cannot access this - "
            f"the tool is integrated and ready to use."
        )
        
        return Skill(
            id=skill_id,
            name=f"Learned: {tool.title()} pattern",
            tool=tool,
            triggers=triggers[:5],  # Limit to 5 triggers
            examples=[example],
            instructions=instructions,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            source="ralph_loop",
        )
    
    def _guess_arguments(self, tool: str, user_message: str) -> dict[str, Any]:
        """Guess reasonable tool arguments based on the message."""
        args: dict[str, Any] = {}
        
        if tool == "gmail":
            if any(word in user_message.lower() for word in ["search", "find", "from"]):
                args["action"] = "search"
            else:
                args["action"] = "list"
            
            # Try to extract count
            import re
            count_match = re.search(r"(\d+)\s*(latest|recent|emails?|messages?)", user_message, re.IGNORECASE)
            if count_match:
                args["max_results"] = int(count_match.group(1))
        
        elif tool == "calendar":
            if any(word in user_message.lower() for word in ["free", "busy", "available"]):
                args["action"] = "free"
            else:
                args["action"] = "list"
        
        elif tool == "web_search":
            # Extract the search query
            args["query"] = user_message
        
        return args
    
    def learn_from_failure(
        self,
        user_message: str,
        model_response: str,
        actual_tool_call: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> Skill | None:
        """
        Complete RALPH loop: analyze failure and learn a new skill.
        
        Returns the learned skill if one was created.
        """
        # Analyze
        analysis = self.analyze_tool_failure(
            user_message=user_message,
            model_response=model_response,
            actual_tool_call=actual_tool_call,
            error=error,
        )
        
        if analysis.suggested_skill and analysis.confidence > 0.6:
            # Check if we already have a similar skill
            existing = self.skills.find_matching_skills(user_message)
            
            if existing:
                # Update existing skill with new trigger
                skill = existing[0]
                new_triggers = list(set(skill.triggers + analysis.suggested_skill.triggers))
                self.skills.update_skill(skill.id, {
                    "triggers": new_triggers,
                    "failure_count": skill.failure_count + 1,
                })
                return skill
            else:
                # Create new skill
                path = self.skills.add_learned_skill(analysis.suggested_skill)
                print(f"RALPH: Learned new skill '{analysis.suggested_skill.name}' saved to {path}")
                return analysis.suggested_skill
        
        return None
    
    def learn_from_user_feedback(
        self,
        user_message: str,
        correct_tool: str,
        correct_arguments: dict[str, Any] | None = None,
    ) -> Skill:
        """
        Learn from explicit user feedback about correct tool usage.
        
        Called when user says something like:
        "You should have used the gmail tool for that"
        """
        skill = Skill(
            id=f"learned_{correct_tool}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            name=f"User-taught: {correct_tool.title()}",
            tool=correct_tool,
            triggers=[user_message.lower()],
            examples=[{
                "user": user_message,
                "tool_call": {"name": correct_tool, "arguments": correct_arguments or {}},
            }],
            instructions=f"When the user says '{user_message}', use the {correct_tool} tool.",
            source="user_feedback",
        )
        
        self.skills.add_learned_skill(skill)
        return skill
    
    async def run_diagnostic(self) -> dict[str, Any]:
        """
        Run a full diagnostic of tool usage patterns.
        
        Analyzes failure logs to identify systemic issues and generate
        improvement recommendations.
        """
        # Handle both sync and async failure logs
        if isinstance(self.failures, AsyncFailureLog):
            summary = await self.failures.get_failure_summary()
        else:
            summary = self.failures.get_failure_summary()
        
        recommendations = []
        
        # Analyze top failing tools
        for tool_info in summary.get("top_failing_tools", []):
            tool = tool_info["tool"]
            count = tool_info["count"]
            
            if count > 3:
                recommendations.append({
                    "tool": tool,
                    "issue": f"Tool '{tool}' has {count} failures",
                    "action": f"Review skill definitions for {tool} and add more trigger patterns",
                })
        
        # Check for refusal patterns in errors
        if isinstance(self.failures, AsyncFailureLog):
            recent = await self.failures.get_recent_failures(limit=10)
        else:
            recent = self.failures.get_recent_failures(limit=10)
        refusal_count = sum(
            1 for f in recent 
            if any(p.search(f.error_message) for p in self._refusal_patterns)
        )
        
        if refusal_count > 2:
            recommendations.append({
                "issue": f"Model is frequently refusing to use tools ({refusal_count} times)",
                "action": "Strengthen system prompt to emphasize tool availability",
            })
        
        return {
            "total_failures": summary.get("unresolved_count", 0) + summary.get("resolved_count", 0),
            "unresolved": summary.get("unresolved_count", 0),
            "top_failing_tools": summary.get("top_failing_tools", []),
            "recommendations": recommendations,
            "skills_count": len(self.skills.get_all_skills()),
        }
    
    def get_enhanced_prompt(self, user_message: str) -> str:
        """
        Get additional prompt content based on learned skills.
        
        This is the PLAN + HANDLE phase - providing learned knowledge
        to improve the next response.
        """
        return self.skills.get_skill_prompt_section(user_message)
