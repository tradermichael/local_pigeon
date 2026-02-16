"""
Memory Tools

Tools that allow the model to read and write user memories.
Memories persist information about the user across conversations.
"""

from typing import Any

from local_pigeon.storage.memory import AsyncMemoryManager, MemoryType
from local_pigeon.tools.registry import Tool


class RememberTool(Tool):
    """
    Tool for saving information about the user.
    
    The model uses this to remember preferences, facts, and context
    that should persist across conversations.
    """
    
    name = "remember"
    description = (
        "Save information about the user to memory. Use this to remember their name, "
        "preferences, important facts, or anything they want you to remember. "
        "Examples: 'remember my name is John', 'remember I prefer morning meetings'"
    )
    parameters = {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "A short key for this memory (e.g., 'user_name', 'timezone', 'coffee_preference')",
            },
            "value": {
                "type": "string",
                "description": "The information to remember",
            },
            "memory_type": {
                "type": "string",
                "enum": ["core", "preference", "fact", "instruction", "episodic"],
                "description": "Type of memory: core (essential info), preference (likes/dislikes), fact (things about user), instruction (how to behave), episodic (events)",
                "default": "fact",
            },
        },
        "required": ["key", "value"],
    }
    requires_approval = False
    
    def __init__(self, memory_manager: AsyncMemoryManager):
        self.memory = memory_manager
    
    async def execute(
        self,
        user_id: str,
        key: str,
        value: str,
        memory_type: str = "fact",
        **kwargs,
    ) -> str:
        """Save a memory."""
        try:
            mem_type = MemoryType(memory_type)
        except ValueError:
            mem_type = MemoryType.FACT
        
        await self.memory.set_memory(
            user_id=user_id,
            key=key,
            value=value,
            memory_type=mem_type,
        )
        
        return f"✅ Remembered: {key} = {value}"


class RecallTool(Tool):
    """
    Tool for retrieving stored memories about the user.
    """
    
    name = "recall"
    description = (
        "Retrieve a specific memory about the user by key. "
        "Use this to look up information you previously saved."
    )
    parameters = {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "The key of the memory to retrieve",
            },
        },
        "required": ["key"],
    }
    requires_approval = False
    
    def __init__(self, memory_manager: AsyncMemoryManager):
        self.memory = memory_manager
    
    async def execute(
        self,
        user_id: str,
        key: str,
        **kwargs,
    ) -> str:
        """Retrieve a memory."""
        memory = await self.memory.get_memory(user_id=user_id, key=key)
        
        if memory:
            return f"Memory '{key}': {memory.value} (type: {memory.memory_type.value})"
        else:
            return f"No memory found with key '{key}'"


class ListMemoriesTool(Tool):
    """
    Tool for listing all memories about the user.
    """
    
    name = "list_memories"
    description = (
        "List all saved memories about the user. "
        "Returns all information you have stored about them."
    )
    parameters = {
        "type": "object",
        "properties": {},
        "required": [],
    }
    requires_approval = False
    
    def __init__(self, memory_manager: AsyncMemoryManager):
        self.memory = memory_manager
    
    async def execute(
        self,
        user_id: str,
        **kwargs,
    ) -> str:
        """List all memories."""
        memories = await self.memory.get_all_memories(user_id=user_id)
        
        if not memories:
            return "No memories stored for this user yet."
        
        lines = [f"## Memories ({len(memories)} total)\n"]
        
        # Group by type
        by_type: dict[str, list] = {}
        for mem in memories:
            type_name = mem.memory_type.value
            if type_name not in by_type:
                by_type[type_name] = []
            by_type[type_name].append(mem)
        
        for type_name, mems in by_type.items():
            lines.append(f"### {type_name.title()}")
            for mem in mems:
                lines.append(f"- **{mem.key}**: {mem.value}")
            lines.append("")
        
        return "\n".join(lines)


class ForgetTool(Tool):
    """
    Tool for deleting a memory about the user.
    """
    
    name = "forget"
    description = (
        "Delete a specific memory about the user. "
        "Use this when the user asks you to forget something."
    )
    parameters = {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "The key of the memory to delete",
            },
        },
        "required": ["key"],
    }
    requires_approval = False
    
    def __init__(self, memory_manager: AsyncMemoryManager):
        self.memory = memory_manager
    
    async def execute(
        self,
        user_id: str,
        key: str,
        **kwargs,
    ) -> str:
        """Delete a memory."""
        success = await self.memory.delete_memory(user_id=user_id, key=key)
        
        if success:
            return f"✅ Forgotten: {key}"
        else:
            return f"No memory found with key '{key}'"
