"""Tool execution functions - Original flavor"""
import os
import json
import subprocess
import glob as glob_module
from pathlib import Path
from typing import Any, Dict, Optional


def read(path: str, offset: Optional[int] = None, limit: Optional[int] = None) -> str:
    """Read file with line numbers"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        start = offset if offset else 0
        end = start + limit if limit else len(lines)
        numbered = [f"{i+1:4d} {line}" for i, line in enumerate(lines[start:end], start)]
        return ''.join(numbered) if numbered else f"Error: File '{path}' is empty or does not exist"
    except FileNotFoundError:
        return f"Error: File '{path}' not found"
    except Exception as e:
        return f"Error: {str(e)}"


def write(path: str, content: str) -> str:
    """Write file"""
    try:
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error: {str(e)}"


def edit(path: str, old_str: str, new_str: str) -> str:
    """Edit file (replace first match)"""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        if old_str not in content:
            return f"Error: old_str not found in file or appears multiple times"
        if content.count(old_str) != 1:
            return f"Error: old_str must appear exactly once"
        new_content = content.replace(old_str, new_str, 1)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        return f"Successfully edited {path}"
    except FileNotFoundError:
        return f"Error: File '{path}' not found"
    except Exception as e:
        return f"Error: {str(e)}"


def glob(pattern: str) -> str:
    """Find files by pattern"""
    try:
        files = glob_module.glob(pattern, recursive=True)
        files.sort(key=lambda x: os.path.getmtime(x), reverse=True)
        return '\n'.join(files) if files else "No files found"
    except Exception as e:
        return f"Error: {str(e)}"


def grep(pattern: str, path: str = ".", recursive: bool = True) -> str:
    """Search files for pattern"""
    try:
        matches = []
        if recursive:
            for root, dirs, files in os.walk(path):
                if '.git' in root or '__pycache__' in root:
                    continue
                for file in files:
                    if file.endswith(('.py', '.js', '.ts', '.md', '.txt', '.json', '.yaml', '.yml')):
                        filepath = os.path.join(root, file)
                        try:
                            with open(filepath, 'r', encoding='utf-8') as f:
                                for i, line in enumerate(f, 1):
                                    if pattern.lower() in line.lower():
                                        matches.append(f"{filepath}:{i}: {line.rstrip()}")
                        except:
                            pass
        else:
            if os.path.isfile(path):
                with open(path, 'r', encoding='utf-8') as f:
                    for i, line in enumerate(f, 1):
                        if pattern.lower() in line.lower():
                            matches.append(f"{path}:{i}: {line.rstrip()}")
        return '\n'.join(matches) if matches else f"No matches found for '{pattern}'"
    except Exception as e:
        return f"Error: {str(e)}"


def bash(command: str, timeout: Optional[int] = None) -> str:
    """Run shell command"""
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout or 60
        )
        output = result.stdout + result.stderr
        return output if output else "Command executed with no output"
    except subprocess.TimeoutExpired:
        return f"Error: Command timed out after {timeout}s"
    except Exception as e:
        return f"Error: {str(e)}"


def list_files(directory: str = ".") -> str:
    """List files in directory"""
    try:
        items = os.listdir(directory)
        items.sort()
        return '\n'.join(items) if items else f"Directory '{directory}' is empty"
    except Exception as e:
        return f"Error: {str(e)}"


_todos: list = []


def todo_write(todos: list) -> str:
    """Write todo list"""
    global _todos
    _todos = todos
    return f"Todo list updated with {len(todos)} items"


def todo_read() -> str:
    """Read current todo list"""
    if not _todos:
        return "No todos"
    return '\n'.join([f"- {t.get('content', t)}" for t in _todos])


AVAILABLE_FUNCTIONS: Dict[str, callable] = {
    "Read": read,
    "Write": write,
    "Edit": edit,
    "Glob": glob,
    "Grep": grep,
    "Bash": bash,
    "Plan": None,
    "TodoWrite": todo_write,
    "TodoRead": todo_read,
}


def get_function(name: str) -> Optional[callable]:
    """Get function by name"""
    return AVAILABLE_FUNCTIONS.get(name)


_plan_func: Optional[callable] = None


def set_plan_function(func: callable) -> None:
    """Set plan function"""
    global _plan_func
    _plan_func = func
    AVAILABLE_FUNCTIONS["Plan"] = func


def get_plan_function() -> Optional[callable]:
    """Get plan function"""
    return _plan_func
