"""Configuration management"""
import os
from typing import Optional, Dict, Any
from pydantic import BaseModel


class Config(BaseModel):
    """CodeAgent configuration"""

    default_model: str = "gpt-4o-mini"
    default_provider: str = "openai"
    temperature: float = 0.7
    max_tokens: Optional[int] = None

    debug: bool = False
    log_level: str = "INFO"
    show_react_steps: bool = True
    show_progress: bool = True

    max_history_length: int = 100
    max_iterations: int = 100
    context_window: int = 128000
    compression_threshold: float = 0.8

    memory_file: str = "agent_memory.md"
    rules_dir: str = ".agent/rules"
    skills_dir: str = ".agent/skills"
    mcp_config: str = ".agent/mcp.json"

    enable_agent_teams: bool = False
    agent_teams_store_dir: str = ".teams"
    agent_tasks_store_dir: str = ".tasks"
    teammate_mode: str = "auto"
    delegate_mode: bool = False

    @classmethod
    def from_env(cls) -> "Config":
        """Create config from environment variables"""
        return cls(
            debug=os.getenv("DEBUG", "false").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            show_react_steps=os.getenv("SHOW_REACT_STEPS", "true").lower() == "true",
            show_progress=os.getenv("SHOW_PROGRESS", "true").lower() == "true",
            temperature=float(os.getenv("TEMPERATURE", "0.7")),
            max_tokens=int(os.getenv("MAX_TOKENS")) if os.getenv("MAX_TOKENS") else None,
            default_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            default_provider=os.getenv("OPENAI_PROVIDER", "openai"),
            max_history_length=int(os.getenv("MAX_HISTORY_LENGTH", "100")),
            max_iterations=int(os.getenv("MAX_ITERATIONS", "100")),
            context_window=int(os.getenv("CONTEXT_WINDOW", "128000")),
            compression_threshold=float(os.getenv("COMPRESSION_THRESHOLD", "0.8")),
            memory_file=os.getenv("MEMORY_FILE", "agent_memory.md"),
            rules_dir=os.getenv("RULES_DIR", ".agent/rules"),
            skills_dir=os.getenv("SKILLS_DIR", ".agent/skills"),
            mcp_config=os.getenv("MCP_CONFIG", ".agent/mcp.json"),
            enable_agent_teams=str(os.getenv("ENABLE_AGENT_TEAMS", "false")).lower() in {"1", "true", "yes", "y", "on"},
            agent_teams_store_dir=os.getenv("AGENT_TEAMS_STORE_DIR", ".teams"),
            agent_tasks_store_dir=os.getenv("AGENT_TASKS_STORE_DIR", ".tasks"),
            teammate_mode=os.getenv("TEAMMATE_MODE", "auto"),
            delegate_mode=str(os.getenv("DELEGATE_MODE", "false")).lower() in {"1", "true", "yes", "y", "on"},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return self.dict()


_config: Optional[Config] = None


def get_config() -> Config:
    """Get global config singleton"""
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config


def set_config(config: Config) -> None:
    """Set global config"""
    global _config
    _config = config
