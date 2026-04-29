"""Memory module - Original flavor"""
import os
from datetime import datetime
from typing import Optional


MEMORY_FILE = "agent_memory.md"


def load_memory(memory_file: Optional[str] = None) -> str:
    """
    Load memory (last 50 lines)

    Original flavor: simple file reading
    """
    filepath = memory_file or os.getenv("MEMORY_FILE", MEMORY_FILE)
    if not os.path.exists(filepath):
        return ""

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')
            return '\n'.join(lines[-50:]) if len(lines) > 50 else content
    except Exception:
        return ""


def save_memory(task: str, result: str, memory_file: Optional[str] = None) -> None:
    """
    Save memory

    Original flavor: append in markdown format
    """
    filepath = memory_file or os.getenv("MEMORY_FILE", MEMORY_FILE)
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entry = f"\n## {timestamp}\n**Task:** {task}\n**Result:** {result}\n"

    try:
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(entry)
    except Exception:
        pass


def clear_memory(memory_file: Optional[str] = None) -> str:
    """Clear memory"""
    filepath = memory_file or os.getenv("MEMORY_FILE", MEMORY_FILE)
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
        return f"Memory file {filepath} cleared"
    except Exception as e:
        return f"Error: {str(e)}"
