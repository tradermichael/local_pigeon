"""
Heartbeat System

Background task that runs periodically to enable self-improvement:
- Analyze recent interactions for skill gaps
- Propose new skills based on patterns
- Add missing memories
- Clean up and optimize

Part of the RALPH loop self-improvement system.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any

from local_pigeon.config import Settings, get_data_dir

if TYPE_CHECKING:
    from local_pigeon.core.agent import LocalPigeonAgent


logger = logging.getLogger(__name__)


class Heartbeat:
    """
    Background heartbeat that enables agent self-improvement.
    
    Runs every N minutes to:
    1. Review recent interactions for patterns
    2. Identify skill gaps (failed tool calls, user corrections)
    3. Propose new skills for approval
    4. Add insights to memory
    """
    
    def __init__(
        self,
        agent: "LocalPigeonAgent",
        interval_minutes: int = 5,
        enabled: bool = True,
        auto_approve_skills: bool = False,
    ):
        self.agent = agent
        self.interval = interval_minutes * 60  # Convert to seconds
        self.enabled = enabled
        self.auto_approve = auto_approve_skills
        self._task: asyncio.Task | None = None
        self._running = False
        self._last_reflection: datetime | None = None
        self.data_dir = get_data_dir()
        
    async def start(self) -> None:
        """Start the heartbeat background task."""
        if not self.enabled:
            logger.info("Heartbeat disabled, not starting")
            return
            
        if self._running:
            logger.warning("Heartbeat already running")
            return
            
        self._running = True
        self._task = asyncio.create_task(self._heartbeat_loop())
        logger.info(f"Heartbeat started (interval: {self.interval // 60} minutes)")
        
    async def stop(self) -> None:
        """Stop the heartbeat background task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, RuntimeError):
                pass
            self._task = None
        logger.info("Heartbeat stopped")
        
    async def _heartbeat_loop(self) -> None:
        """Main heartbeat loop."""
        while self._running:
            try:
                await asyncio.sleep(self.interval)
                
                if not self._running:
                    break
                    
                logger.debug("Heartbeat tick - running reflection")
                await self._reflect()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Heartbeat error: {e}", exc_info=True)
                # Continue running despite errors
                
    async def _reflect(self) -> None:
        """
        Perform self-reflection on recent interactions.
        
        This is the core of the self-improvement system.
        """
        self._last_reflection = datetime.now()
        
        try:
            # Get recent interactions from memory
            recent = await self._get_recent_interactions()
            
            if not recent:
                logger.debug("No recent interactions to reflect on")
                return
                
            # Analyze for skill gaps
            analysis = await self._analyze_interactions(recent)
            
            if analysis.get("proposed_skills"):
                await self._handle_proposed_skills(analysis["proposed_skills"])
                
            if analysis.get("missing_memories"):
                await self._add_memories(analysis["missing_memories"])
                
            logger.info(f"Reflection complete: {len(analysis.get('proposed_skills', []))} skills proposed")
            
        except Exception as e:
            logger.error(f"Reflection failed: {e}", exc_info=True)
            
    async def _get_recent_interactions(self) -> list[dict]:
        """Get interactions since last reflection."""
        try:
            # Get recent interactions via the agent's memory manager
            since = self._last_reflection or (datetime.now() - timedelta(minutes=self.interval // 60))
            
            # Get all memories for system user (reflection context)
            recent = await self.agent.memory.get_all_memories(user_id="system")
            
            # Convert to list of dicts for processing
            return [{"content": m.value, "type": m.memory_type.value} for m in recent[-20:]]
            
        except Exception as e:
            logger.error(f"Failed to get recent interactions: {e}")
            return []
            
    async def _analyze_interactions(self, interactions: list[dict]) -> dict[str, Any]:
        """
        Use the LLM to analyze interactions and identify improvement opportunities.
        """
        if not interactions:
            return {"proposed_skills": [], "missing_memories": []}
            
        # Format interactions for analysis
        interaction_text = "\n".join([
            f"- {i.get('content', '')[:200]}"
            for i in interactions[:10]
        ])
        
        reflection_prompt = f"""You are analyzing recent user interactions to identify self-improvement opportunities.

Recent interactions:
{interaction_text}

Analyze these interactions and identify:

1. **Skill Gaps**: Did the user ask for something you couldn't do well? 
   - What tool should have been used?
   - What trigger phrases indicate this need?

2. **Missing Memories**: Are there facts about the user you should remember?
   - Preferences, routines, important dates, etc.

3. **Pattern Improvements**: Are there repeated requests that could be handled better?

Respond in this format (leave sections empty if nothing to add):

## Proposed Skills
- skill_name: description of when to use this tool
- skill_name2: description

## Missing Memories
- memory: fact to remember about user
- memory2: another fact

## Insights
Brief notes on how to improve."""

        try:
            # Use the agent's LLM to analyze
            response = await self.agent.llm.chat(
                messages=[{"role": "user", "content": reflection_prompt}],
                model=self.agent.settings.ollama.model,
            )
            
            # Parse the response
            return self._parse_reflection_response(response.get("content", ""))
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            return {"proposed_skills": [], "missing_memories": []}
            
    def _parse_reflection_response(self, response: str) -> dict[str, Any]:
        """Parse the LLM's reflection response."""
        result: dict[str, Any] = {
            "proposed_skills": [],
            "missing_memories": [],
            "insights": "",
        }
        
        current_section = None
        
        for line in response.split("\n"):
            line = line.strip()
            
            if "## Proposed Skills" in line:
                current_section = "skills"
            elif "## Missing Memories" in line:
                current_section = "memories"
            elif "## Insights" in line:
                current_section = "insights"
            elif line.startswith("- ") and current_section == "skills":
                # Parse skill line: "- skill_name: description"
                parts = line[2:].split(":", 1)
                if len(parts) == 2:
                    result["proposed_skills"].append({
                        "name": parts[0].strip(),
                        "description": parts[1].strip(),
                    })
            elif line.startswith("- ") and current_section == "memories":
                # Parse memory line
                parts = line[2:].split(":", 1)
                if len(parts) == 2:
                    result["missing_memories"].append({
                        "key": parts[0].strip(),
                        "value": parts[1].strip(),
                    })
            elif current_section == "insights" and line:
                result["insights"] += line + "\n"
                
        return result
        
    async def _handle_proposed_skills(self, skills: list[dict]) -> None:
        """Handle proposed skills - either auto-approve or queue for user approval."""
        from local_pigeon.core.skills import SkillsManager
        
        skills_mgr = SkillsManager(self.data_dir)
        
        for skill_data in skills:
            skill_id = f"proposed_{datetime.now().strftime('%Y%m%d%H%M%S')}_{skill_data['name'].replace(' ', '_')}"
            
            # Create markdown skill file
            skill_md = f"""---
id: {skill_id}
name: {skill_data['name']}
status: {'approved' if self.auto_approve else 'pending'}
source: heartbeat_reflection
created: {datetime.now().isoformat()}
---

# {skill_data['name']}

## Description
{skill_data['description']}

## Triggers
- (Add trigger phrases here)

## Instructions
When the user asks about {skill_data['name']}, I should...

## Examples
- User: "example request"
- Action: (what tool to call)
"""
            
            # Save to appropriate directory
            if self.auto_approve:
                skill_path = self.data_dir / "skills" / "learned" / f"{skill_id}.md"
            else:
                skill_path = self.data_dir / "skills" / "pending" / f"{skill_id}.md"
                
            skill_path.parent.mkdir(parents=True, exist_ok=True)
            skill_path.write_text(skill_md, encoding="utf-8")
            
            logger.info(f"{'Created' if self.auto_approve else 'Proposed'} skill: {skill_data['name']}")
            
    async def _add_memories(self, memories: list[dict]) -> None:
        """Add identified memories to the memory store."""
        try:
            from local_pigeon.storage.memory import MemoryType
            
            for mem in memories:
                # Use set_memory with a key and value
                await self.agent.memory.set_memory(
                    user_id="system",
                    key=f"fact_{mem['key'].lower().replace(' ', '_')}",
                    value=f"{mem['key']}: {mem['value']}",
                    memory_type=MemoryType.FACT,
                )
                logger.info(f"Added memory: {mem['key']}")
                
        except Exception as e:
            logger.error(f"Failed to add memories: {e}")
            
    def trigger_reflection(self) -> asyncio.Task:
        """Manually trigger a reflection (for testing or UI)."""
        return asyncio.create_task(self._reflect())
        
    @property
    def status(self) -> dict:
        """Get heartbeat status."""
        return {
            "enabled": self.enabled,
            "running": self._running,
            "interval_minutes": self.interval // 60,
            "auto_approve_skills": self.auto_approve,
            "last_reflection": self._last_reflection.isoformat() if self._last_reflection else None,
        }
