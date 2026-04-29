"""Agent module"""
from typing import Optional

from .code_agent import CodeAgent

_current_agent: Optional[CodeAgent] = None


def get_agent() -> Optional[CodeAgent]:
    """Get current agent instance"""
    return _current_agent


def set_agent(agent: CodeAgent) -> None:
    """Set current agent instance"""
    global _current_agent
    _current_agent = agent


__all__ = ["CodeAgent", "get_agent", "set_agent"]
