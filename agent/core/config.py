"""
配置模块 - 管理所有环境变量和配置项
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent.resolve()


class Config:
    """应用配置类"""

    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("LLM_API_KEY")
    OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL") or os.environ.get("LLM_BASE_URL")
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")

    MEMORY_FILE = str(PROJECT_ROOT / "agent_memory.md")
    RULES_DIR = str(PROJECT_ROOT / ".agent" / "rules")
    SKILLS_DIR = str(PROJECT_ROOT / ".agent" / "skills")
    MCP_CONFIG = str(PROJECT_ROOT / ".agent" / "mcp.json")

    MAX_ITERATIONS = 15
    MAX_MEMORY_LINES = 50
    COMMAND_TIMEOUT = 30


class AgentState:
    """Agent 运行时状态"""
    current_plan = []
    plan_mode = False

class ToolState:
    """工具状态类"""
    state = {}
