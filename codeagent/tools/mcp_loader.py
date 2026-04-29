"""MCP tools loader"""
import json
import os
from typing import Any, Dict, List, Optional


def load_mcp_tools(config_path: str = ".agent/mcp.json") -> List[Dict[str, Any]]:
    """
    Load MCP tools config

    Original flavor: simple JSON loading, return MCP tools list directly
    """
    if not os.path.exists(config_path):
        return []

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        mcp_tools = []
        for server_name, server_config in config.get("mcpServers", {}).items():
            if server_config.get("disabled", False):
                continue
            for tool in server_config.get("tools", []):
                mcp_tools.append({
                    "type": "function",
                    "function": tool
                })

        return mcp_tools
    except json.JSONDecodeError as e:
        return []
    except Exception as e:
        return []


def get_mcp_tools() -> List[Dict[str, Any]]:
    """Get MCP tools list"""
    config_path = os.getenv("MCP_CONFIG", ".agent/mcp.json")
    return load_mcp_tools(config_path)
