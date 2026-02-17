"""
Skills Tools

Tools that allow the model to view, create, and manage learned skills.
Part of the RALPH loop self-improvement system.

Skills are now stored as Markdown files that both humans and the agent
can easily read and write.
"""

from datetime import datetime
from typing import Any

from local_pigeon.core.skills import SkillsManager, Skill
from local_pigeon.tools.registry import Tool


class CreateSkillTool(Tool):
    """
    Tool for creating a new skill from scratch.
    
    Creates a markdown skill file that can be approved by the user
    or auto-approved based on settings.
    """
    
    name = "create_skill"
    description = (
        "Create a new skill to teach yourself how to handle specific requests. "
        "Use this when you realize you should remember a pattern for future use. "
        "The skill will be saved for user approval unless auto-approve is enabled."
    )
    parameters = {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "A short descriptive name for the skill (e.g., 'Check Weather', 'Send Email')",
            },
            "tool": {
                "type": "string",
                "description": "The tool this skill teaches how to use (e.g., 'web_search', 'gmail', 'calendar')",
            },
            "triggers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of phrases that should trigger this skill (e.g., ['check weather', 'what\\'s the weather'])",
            },
            "instructions": {
                "type": "string",
                "description": "Clear instructions for when and how to use this tool",
            },
            "example_request": {
                "type": "string",
                "description": "An example user request that would trigger this skill",
            },
            "example_action": {
                "type": "string",
                "description": "The tool call to make for that example (as JSON string)",
            },
        },
        "required": ["name", "tool", "instructions"],
    }
    requires_approval = False
    
    def __init__(self, skills_manager: SkillsManager, auto_approve: bool = False):
        self.skills = skills_manager
        self.auto_approve = auto_approve
    
    async def execute(
        self,
        user_id: str,
        name: str,
        tool: str,
        instructions: str,
        triggers: list[str] | None = None,
        example_request: str | None = None,
        example_action: str | None = None,
        **kwargs,
    ) -> str:
        """Create a new skill."""
        import json
        
        skill_id = f"skill_{datetime.now().strftime('%Y%m%d%H%M%S')}_{name.lower().replace(' ', '_')[:20]}"
        
        # Build examples list
        examples = []
        if example_request:
            try:
                action = json.loads(example_action) if example_action else {"name": tool}
            except json.JSONDecodeError:
                action = {"name": tool}
            examples.append({"user": example_request, "tool_call": action})
        
        skill = Skill(
            id=skill_id,
            name=name,
            tool=tool,
            triggers=triggers or [],
            examples=examples,
            instructions=instructions,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            source="agent",
            status="approved" if self.auto_approve else "pending",
        )
        
        # Save to appropriate directory
        if self.auto_approve:
            path = self.skills.skills_dir / "learned" / f"{skill_id}.md"
        else:
            path = self.skills.skills_dir / "pending" / f"{skill_id}.md"
        
        path.parent.mkdir(parents=True, exist_ok=True)
        self.skills._save_skill_md(skill, path)
        
        if self.auto_approve:
            return (
                f"✅ Created and enabled new skill: **{name}**\n\n"
                f"**Tool:** {tool}\n"
                f"**Triggers:** {', '.join(triggers or ['(none specified)'])}\n"
                f"**File:** `{path}`\n\n"
                f"I'll use this skill for similar requests in the future."
            )
        else:
            return (
                f"📝 Proposed new skill: **{name}**\n\n"
                f"**Tool:** {tool}\n"
                f"**Instructions:** {instructions}\n\n"
                f"This skill is pending your approval. You can review it in:\n"
                f"`{path}`\n\n"
                f"Approve it in the Settings > Skills tab or edit the file directly."
            )


class ViewSkillsTool(Tool):
    """
    Tool for viewing current skills.
    
    Allows the model to see what skills have been learned and
    understand how to use tools correctly.
    """
    
    name = "view_skills"
    description = (
        "View learned skills that teach how to use tools correctly. "
        "Use this to understand patterns for tools like gmail, calendar, etc."
    )
    parameters = {
        "type": "object",
        "properties": {
            "tool_filter": {
                "type": "string",
                "description": "Optional: filter skills for a specific tool (e.g., 'gmail', 'calendar')",
            },
        },
        "required": [],
    }
    requires_approval = False
    
    def __init__(self, skills_manager: SkillsManager):
        self.skills = skills_manager
    
    async def execute(
        self,
        user_id: str,
        tool_filter: str | None = None,
        **kwargs,
    ) -> str:
        """View skills."""
        if tool_filter:
            skills = self.skills.get_skills_for_tool(tool_filter)
        else:
            skills = self.skills.get_all_skills()
        
        if not skills:
            return "No skills found matching your criteria."
        
        lines = [f"## Learned Skills ({len(skills)} total)\n"]
        
        for skill in skills:
            lines.append(f"### {skill.name}")
            lines.append(f"**Tool:** {skill.tool}")
            lines.append(f"**Triggers:** {', '.join(skill.triggers[:5])}")
            lines.append(f"**Instructions:** {skill.instructions}")
            lines.append(f"**Source:** {skill.source}")
            lines.append(f"**Success/Fail:** {skill.success_count}/{skill.failure_count}")
            lines.append("")
            
            if skill.examples:
                lines.append("**Examples:**")
                for ex in skill.examples[:2]:
                    lines.append(f"  User: \"{ex['user']}\"")
                    lines.append(f"  Tool: {ex['tool_call']}")
            lines.append("")
        
        return "\n".join(lines)


class LearnSkillTool(Tool):
    """
    Tool for learning a new skill from user feedback.
    
    When the user tells the model it should have used a tool,
    the model can use this to learn the correct pattern.
    """
    
    name = "learn_skill"
    description = (
        "Learn a new skill pattern from user feedback. Use this when the user "
        "tells you that you should have used a specific tool for their request."
    )
    parameters = {
        "type": "object",
        "properties": {
            "tool": {
                "type": "string",
                "description": "The tool that should be used (e.g., 'gmail', 'calendar', 'web_search')",
            },
            "trigger_phrase": {
                "type": "string",
                "description": "The user phrase that should trigger this tool",
            },
            "instructions": {
                "type": "string",
                "description": "Instructions for when to use this tool",
            },
        },
        "required": ["tool", "trigger_phrase"],
    }
    requires_approval = False
    
    def __init__(self, skills_manager: SkillsManager):
        self.skills = skills_manager
    
    async def execute(
        self,
        user_id: str,
        tool: str,
        trigger_phrase: str,
        instructions: str | None = None,
        **kwargs,
    ) -> str:
        """Learn a new skill."""
        from datetime import datetime
        
        skill_id = f"learned_{tool}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        skill = Skill(
            id=skill_id,
            name=f"User-taught: {tool.title()}",
            tool=tool,
            triggers=[trigger_phrase.lower()],
            examples=[{
                "user": trigger_phrase,
                "tool_call": {"name": tool, "arguments": {}},
            }],
            instructions=instructions or f"When the user says '{trigger_phrase}', use the {tool} tool.",
            source="user_feedback",
        )
        
        path = self.skills.add_learned_skill(skill)
        
        return (
            f"✅ Learned new skill!\n\n"
            f"**Tool:** {tool}\n"
            f"**Trigger:** {trigger_phrase}\n"
            f"**Saved to:** {path}\n\n"
            f"I'll remember to use the {tool} tool for similar requests in the future."
        )


class UpdateSkillTool(Tool):
    """
    Tool for updating an existing skill.
    
    Allows adding new triggers or updating instructions.
    """
    
    name = "update_skill"
    description = (
        "Update an existing skill - add new trigger phrases or update instructions."
    )
    parameters = {
        "type": "object",
        "properties": {
            "skill_id": {
                "type": "string",
                "description": "The ID of the skill to update",
            },
            "add_trigger": {
                "type": "string",
                "description": "A new trigger phrase to add",
            },
            "new_instructions": {
                "type": "string",
                "description": "New instructions to replace the existing ones",
            },
        },
        "required": ["skill_id"],
    }
    requires_approval = False
    
    def __init__(self, skills_manager: SkillsManager):
        self.skills = skills_manager
    
    async def execute(
        self,
        user_id: str,
        skill_id: str,
        add_trigger: str | None = None,
        new_instructions: str | None = None,
        **kwargs,
    ) -> str:
        """Update a skill."""
        skill = self.skills.get_skill(skill_id)
        
        if not skill:
            return f"❌ Skill '{skill_id}' not found."
        
        updates = {}
        messages = []
        
        if add_trigger:
            new_triggers = skill.triggers + [add_trigger.lower()]
            updates["triggers"] = list(set(new_triggers))  # Dedupe
            messages.append(f"Added trigger: '{add_trigger}'")
        
        if new_instructions:
            updates["instructions"] = new_instructions
            messages.append(f"Updated instructions")
        
        if not updates:
            return "No updates provided."
        
        success = self.skills.update_skill(skill_id, updates)
        
        if success:
            return f"✅ Skill '{skill.name}' updated!\n" + "\n".join(f"- {m}" for m in messages)
        else:
            return f"❌ Failed to update skill '{skill_id}'."


class DocumentLimitationTool(Tool):
    """
    Tool for documenting limitations and creating self-improvement skills.
    
    When the agent encounters something it cannot do or is limited in doing,
    it can use this tool to:
    1. Document the limitation
    2. Suggest workarounds
    3. Propose needed capabilities
    4. Create a complex skill directory for future reference
    
    This enables self-critique and continuous improvement.
    """
    
    name = "document_limitation"
    description = (
        "Document when you encounter a limitation or cannot fulfill a request. "
        "Use this for self-improvement - describe what you couldn't do, why, "
        "and what workarounds exist. This creates a skill that helps you handle "
        "similar situations better in the future."
    )
    parameters = {
        "type": "object",
        "properties": {
            "limitation": {
                "type": "string",
                "description": "Clear description of what you cannot do (e.g., 'Cannot access real-time stock prices')",
            },
            "context": {
                "type": "string",
                "description": "What the user was trying to do when this limitation was encountered",
            },
            "workaround": {
                "type": "string",
                "description": "Possible workaround or alternative approach (e.g., 'Use web_search to find recent prices')",
            },
            "needed_capability": {
                "type": "string",
                "description": "What tool or capability would solve this limitation (e.g., 'Real-time stock API integration')",
            },
            "severity": {
                "type": "string",
                "enum": ["minor", "moderate", "major"],
                "description": "How significant is this limitation? minor=has workaround, moderate=partial workaround, major=no workaround",
            },
        },
        "required": ["limitation", "workaround"],
    }
    requires_approval = False
    
    def __init__(self, skills_manager: SkillsManager, auto_approve: bool = False):
        self.skills = skills_manager
        self.auto_approve = auto_approve
    
    async def execute(
        self,
        user_id: str,
        limitation: str,
        workaround: str,
        context: str | None = None,
        needed_capability: str | None = None,
        severity: str = "moderate",
        **kwargs,
    ) -> str:
        """Document a limitation and create a self-improvement skill."""
        import json
        
        # Generate a descriptive skill ID
        limitation_slug = limitation.lower().replace(" ", "_")[:30]
        skill_id = f"limitation_{datetime.now().strftime('%Y%m%d%H%M%S')}_{limitation_slug}"
        
        # For major limitations, create a complex skill directory
        is_complex = severity == "major" or needed_capability
        
        # Build instructions
        instructions = f"""## Limitation
{limitation}

## Workaround
{workaround}
"""
        if needed_capability:
            instructions += f"""
## Needed Capability
{needed_capability}
"""
        
        # Build skill
        skill = Skill(
            id=skill_id,
            name=f"Limitation: {limitation[:50]}",
            tool="self_improvement",
            triggers=[
                limitation.lower(),
                context.lower() if context else "",
            ],
            examples=[{
                "user": context or limitation,
                "tool_call": {"workaround": workaround},
            }],
            instructions=instructions,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            source="self_critique",
            status="approved" if self.auto_approve else "pending",
        )
        
        # Add extended info for complex skills
        if is_complex:
            skill.is_directory = True
            skill.readme = f"""# {limitation}

This skill documents a limitation encountered during operation.

## Context
{context or 'Not specified'}

## Workaround
{workaround}

## Needed Capability
{needed_capability or 'No specific capability identified'}

## Severity
{severity}

---
*This skill was auto-generated by self-critique on {datetime.now().strftime('%Y-%m-%d %H:%M')}*
"""
            skill.reference = f"""# Technical Reference

## Limitation Details
- **Type**: {severity} limitation
- **Affects**: User requests involving: {context or limitation}

## Potential Solutions
1. {workaround}
{f'2. Implement: {needed_capability}' if needed_capability else ''}

## Related Tools
- Check if any existing tools can partially address this
- Consider combining multiple tools as a workaround
"""
        
        # Save the skill
        if is_complex:
            # Create directory-based skill
            if self.auto_approve:
                skill_dir = self.skills.skills_dir / "learned" / skill_id
            else:
                skill_dir = self.skills.skills_dir / "pending" / skill_id
            
            self.skills._save_skill_dir(skill, skill_dir)
            location = f"directory: {skill_dir}"
        else:
            # Create simple skill file
            if self.auto_approve:
                path = self.skills.skills_dir / "learned" / f"{skill_id}.md"
            else:
                path = self.skills.skills_dir / "pending" / f"{skill_id}.md"
            
            path.parent.mkdir(parents=True, exist_ok=True)
            self.skills._save_skill_md(skill, path)
            location = f"file: {path}"
        
        status = "enabled" if self.auto_approve else "pending approval"
        return (
            f"📝 Documented limitation ({status})\n\n"
            f"**Limitation:** {limitation}\n"
            f"**Workaround:** {workaround}\n"
            f"**Severity:** {severity}\n"
            f"**Location:** {location}\n\n"
            "This will help me handle similar situations better in the future."
        )
