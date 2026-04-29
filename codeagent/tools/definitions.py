"""Tool definitions - Original flavor with simple dict structure"""

from typing import Any, Dict, Optional, List, Callable
from dataclasses import dataclass


@dataclass
class ToolDefinition:
    """Tool definition - simple structure maintaining original flavor"""
    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable


BASE_TOOLS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "Read",
            "description": "Read file with line numbers. Shows content from a file with each line numbered.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The file path to read"},
                    "offset": {"type": "integer", "description": "Line offset to start reading from"},
                    "limit": {"type": "integer", "description": "Maximum number of lines to read"}
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Write",
            "description": "Write content to a file. Creates new file or overwrites existing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The file path to write"},
                    "content": {"type": "string", "description": "The content to write"}
                },
                "required": ["path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Edit",
            "description": "Edit a file by replacing old_str with new_str. old_str must appear exactly once.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "The file path to edit"},
                    "old_str": {"type": "string", "description": "The exact string to replace"},
                    "new_str": {"type": "string", "description": "The replacement string"}
                },
                "required": ["path", "old_str", "new_str"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Glob",
            "description": "Find files by glob pattern. Returns list of matching file paths.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Glob pattern to match files"}
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Grep",
            "description": "Search files for pattern. Returns matching lines with file paths.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {"type": "string", "description": "Regex pattern to search"},
                    "path": {"type": "string", "description": "Directory or file to search in"},
                    "recursive": {"type": "boolean", "description": "Search recursively in directories"}
                },
                "required": ["pattern"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Bash",
            "description": "Run shell command. Returns command output.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "Shell command to execute"},
                    "timeout": {"type": "integer", "description": "Command timeout in seconds"}
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "Plan",
            "description": "Break down complex task into steps. Returns execution plan.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "The task to plan"}
                },
                "required": ["task"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "TodoWrite",
            "description": "Create and manage todo list. Use to track task progress.",
            "parameters": {
                "type": "object",
                "properties": {
                    "todos": {"type": "array", "description": "List of todos"}
                }
            }
        }
    }
]


def get_all_tool_definitions() -> List[Dict[str, Any]]:
    """Get all tool definitions"""
    return BASE_TOOLS
