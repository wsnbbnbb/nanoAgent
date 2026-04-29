"""
MCP 加载器 - 从 .agent/mcp.json 加载 MCP 工具配置
"""
import os
import json
from typing import List, Dict, Any
from ..core.config import Config


class McpLoader:
    """MCP 配置加载器，负责加载 MCP (Model Context Protocol) 工具配置"""

    def __init__(self, mcp_config: str = None):
        """
        初始化 MCP 加载器

        Args:
            mcp_config: MCP 配置文件路径，默认使用 Config.MCP_CONFIG
        """
        self.mcp_config = mcp_config or Config.MCP_CONFIG

    def load(self) -> List[Dict[str, Any]]:
        """
        加载 MCP 配置并转换为工具定义格式

        Returns:
            工具定义列表
        """
        if not os.path.exists(self.mcp_config):
            return []

        try:
            with open(self.mcp_config, 'r', encoding='utf-8') as f:
                config = json.load(f)

            mcp_tools = []
            servers = config.get("mcpServers", {})

            for server_name, server_config in servers.items():
                # 跳过禁用的服务器
                if server_config.get("disabled", False):
                    continue

                # 加载该服务器的工具
                tools = server_config.get("tools", [])
                for tool in tools:
                    # 包装为 OpenAI Function Calling 格式
                    mcp_tools.append({
                        "type": "function",
                        "function": tool
                    })

            return mcp_tools

        except json.JSONDecodeError as e:
            print(f"Warning: Invalid JSON in MCP config: {e}")
            return []
        except Exception as e:
            print(f"Warning: Failed to load MCP config: {e}")
            return []

    def list_servers(self) -> List[Dict[str, Any]]:
        """
        列出所有配置的服务器

        Returns:
            服务器信息列表
        """
        if not os.path.exists(self.mcp_config):
            return []

        try:
            with open(self.mcp_config, 'r', encoding='utf-8') as f:
                config = json.load(f)

            servers = config.get("mcpServers", {})
            return [
                {
                    "name": name,
                    "disabled": info.get("disabled", False),
                    "tools_count": len(info.get("tools", []))
                }
                for name, info in servers.items()
            ]

        except Exception as e:
            print(f"Warning: Failed to list MCP servers: {e}")
            return []

    def get_server_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """
        获取特定服务器的工具列表

        Args:
            server_name: 服务器名称

        Returns:
            工具定义列表
        """
        if not os.path.exists(self.mcp_config):
            return []

        try:
            with open(self.mcp_config, 'r', encoding='utf-8') as f:
                config = json.load(f)

            server = config.get("mcpServers", {}).get(server_name, {})
            return server.get("tools", [])

        except Exception:
            return []


def load_mcp_tools(mcp_config: str = None) -> List[Dict[str, Any]]:
    """
    便捷函数：加载 MCP 工具

    Args:
        mcp_config: MCP 配置文件路径

    Returns:
        工具定义列表
    """
    loader = McpLoader(mcp_config)
    return loader.load()
