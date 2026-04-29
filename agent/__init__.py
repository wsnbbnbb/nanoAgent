"""
nanoAgent - 轻量级 AI Agent 框架

基于函数调用(Function Calling)的智能代理系统，支持：
- 文件读写与编辑
- 代码搜索与全局查找
- 命令行执行
- 任务规划与拆解
- 记忆持久化
- 规则与技能系统
"""

__version__ = "0.3.0"

from .core.config import Config, AgentState
from .memory.manager import MemoryManager
from .loaders.rules import load_rules
from .loaders.skills_loader import load_skills, SkillLoader, SkillMeta, SkillDefinition, create_skill_template
from .core.agent import run_agent_claudecode, run_agent_stream
from .mcp.mcp_client import MCPClient, MCPClientManager, MCPTool, load_mcp_config

__all__ = [
    # Core
    "Config",
    "AgentState",
    "run_agent_claudecode",
    "run_agent_stream",
    # Memory
    "MemoryManager",
    # Skills
    "SkillLoader",
    "SkillMeta",
    "SkillDefinition",
    "create_skill_template",
    "load_skills",
    # MCP
    "MCPClient",
    "MCPClientManager",
    "MCPTool",
    "load_mcp_config",
    # Loaders
    "load_rules",
]