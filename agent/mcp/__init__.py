"""
MCP 模块 - Model Context Protocol 支持

包含两个实现：
- agent.mcp.mcp_client: 自定义 MCP 实现  
- agent.mcp_client: 使用官方 mcp 包的实现
"""

from .mcp_client import MCPClient, MCPTool

__all__ = [
    "MCPClient",
    "MCPTool",
]
