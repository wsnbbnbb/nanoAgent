"""
MCP (Model Context Protocol) 客户端实现

支持：
- stdio 传输（本地 MCP 服务器）
- HTTP/SSE 传输（远程 MCP 服务器）
- 工具调用
- 资源读写
- Prompt 获取
"""
import asyncio
import json
import logging
import os
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Callable

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    input_schema: Dict[str, Any]


@dataclass
class MCPResource:
    """MCP 资源定义"""
    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None


class MCPClient:
    """
    MCP 客户端

    支持 stdio 和 HTTP 两种传输方式。
    使用方式：

    stdio 模式：
    ```python
    client = MCPClient(transport="stdio", command="npx", args=["mcp-server-mytool"])
    await client.connect()
    tools = await client.list_tools()
    result = await client.call_tool("my_tool", {"arg": "value"})
    ```

    HTTP 模式：
    ```python
    client = MCPClient(transport="http", url="http://localhost:8080/mcp")
    await client.connect()
    tools = await client.list_tools()
    ```
    """

    def __init__(
        self,
        transport: str = "stdio",
        command: Optional[str] = None,
        args: Optional[List[str]] = None,
        url: Optional[str] = None,
        env: Optional[Dict[str, str]] = None,
    ):
        self.transport = transport
        self.command = command
        self.args = args or []
        self.url = url
        self.env = env

        self._session: Optional[Any] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._proc: Optional[subprocess.Popen] = None
        self._connected = False

    async def connect(self) -> bool:
        """连接到 MCP 服务器"""
        if self._connected:
            return True

        try:
            if self.transport == "stdio":
                return await self._connect_stdio()
            elif self.transport == "http":
                return await self._connect_http()
            else:
                raise ValueError(f"Unknown transport: {self.transport}")
        except Exception as e:
            logger.error(f"Failed to connect to MCP server: {e}")
            return False

    async def _connect_stdio(self) -> bool:
        """通过 stdio 连接本地 MCP 服务器"""
        try:
            from mcp.client.session import ClientSession
            from mcp.client.stdio import StdioServerParameters, stdio_client

            env = None
            if self.env:
                env = dict(os.environ)
                env.update(self.env)

            params = StdioServerParameters(
                command=self.command,
                args=self.args,
                env=env,
            )

            self._conn = stdio_client(params)
            read, write, proc = await self._conn.__aenter__()
            self._proc = proc

            session = ClientSession(read, write)
            await session.__aenter__()
            await session.initialize()

            self._session = session
            self._connected = True
            return True

        except ImportError:
            logger.error("mcp package not installed. Install with: pip install mcp")
            return False
        except Exception as e:
            logger.error(f"Failed to connect via stdio: {e}")
            return False

    async def _connect_http(self) -> bool:
        """通过 HTTP/SSE 连接远程 MCP 服务器"""
        try:
            from mcp.client.streamable_http import streamablehttp_client
            from mcp.client.session import ClientSession

            self._conn = streamablehttp_client(self.url)
            read, write, _ = await self._conn.__aenter__()

            session = ClientSession(read, write)
            await session.__aenter__()
            await session.initialize()

            self._session = session
            self._connected = True
            return True

        except ImportError:
            logger.error("mcp package not installed. Install with: pip install mcp")
            return False
        except Exception as e:
            logger.error(f"Failed to connect via HTTP: {e}")
            return False

    async def close(self) -> None:
        """关闭连接"""
        if self._session:
            try:
                await self._session.__aexit__(None, None, None)
            except Exception:
                pass
            self._session = None

        if self._conn:
            try:
                await self._conn.__aexit__(None, None, None)
            except Exception:
                pass
            self._conn = None

        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception:
                pass
            self._proc = None

        self._connected = False

    async def list_tools(self) -> List[MCPTool]:
        """列出所有可用工具"""
        if not self._connected:
            await self.connect()

        if not self._session:
            return []

        try:
            response = await self._session.list_tools()
            tools = []

            for tool in response.tools:
                tools.append(MCPTool(
                    name=tool.name,
                    description=tool.description or "",
                    input_schema=tool.inputSchema if hasattr(tool, 'inputSchema') else {},
                ))

            return tools

        except Exception as e:
            logger.error(f"Failed to list tools: {e}")
            return []

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用工具"""
        if not self._connected:
            await self.connect()

        if not self._session:
            return {"error": "Not connected to MCP server"}

        try:
            response = await self._session.call_tool(name, arguments)

            result = {
                "content": [],
            }

            if hasattr(response, 'content'):
                for item in response.content:
                    if hasattr(item, 'text'):
                        result["content"].append({"type": "text", "text": item.text})
                    elif hasattr(item, 'data'):
                        result["content"].append({"type": "data", "data": item.data})

            return result

        except Exception as e:
            logger.error(f"Failed to call tool {name}: {e}")
            return {"error": str(e)}

    async def list_resources(self) -> List[MCPResource]:
        """列出所有可用资源"""
        if not self._connected:
            await self.connect()

        if not self._session:
            return []

        try:
            response = await self._session.list_resources()
            resources = []

            for resource in response.resources:
                resources.append(MCPResource(
                    uri=resource.uri,
                    name=resource.name or "",
                    description=resource.description if hasattr(resource, 'description') else None,
                    mime_type=resource.mimeType if hasattr(resource, 'mimeType') else None,
                ))

            return resources

        except Exception as e:
            logger.error(f"Failed to list resources: {e}")
            return []

    async def read_resource(self, uri: str) -> Optional[str]:
        """读取资源内容"""
        if not self._connected:
            await self.connect()

        if not self._session:
            return None

        try:
            response = await self._session.read_resource(uri)

            if hasattr(response, 'contents') and response.contents:
                for item in response.contents:
                    if hasattr(item, 'text'):
                        return item.text

            return None

        except Exception as e:
            logger.error(f"Failed to read resource {uri}: {e}")
            return None

    def get_definitions(self) -> List[Dict[str, Any]]:
        """获取工具定义（同步版本，返回 OpenAI Function 格式）"""
        if not hasattr(self, '_tools'):
            return []

        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                }
            }
            for tool in self._tools
        ]


class MCPClientManager:
    """
    MCP 客户端管理器

    管理多个 MCP 服务器连接。
    """

    def __init__(self):
        self._clients: Dict[str, MCPClient] = {}
        self._tools: Dict[str, List[MCPTool]] = {}

    def add_client(self, name: str, client: MCPClient) -> None:
        """添加 MCP 客户端"""
        self._clients[name] = client

    def remove_client(self, name: str) -> bool:
        """移除 MCP 客户端"""
        if name in self._clients:
            asyncio.create_task(self._clients[name].close())
            del self._clients[name]
            if name in self._tools:
                del self._tools[name]
            return True
        return False

    async def connect_all(self) -> Dict[str, bool]:
        """连接所有客户端"""
        results = {}
        for name, client in self._clients.items():
            results[name] = await client.connect()
        return results

    async def close_all(self) -> None:
        """关闭所有连接"""
        for client in self._clients.values():
            await client.close()

    def get_all_tools(self) -> List[Dict[str, Any]]:
        """获取所有工具定义"""
        all_tools = []
        for name, client in self._clients.items():
            tools = client.get_definitions()
            for tool in tools:
                tool["function"]["name"] = f"{name}/{tool['function']['name']}"
            all_tools.extend(tools)
        return all_tools

    async def call_tool(self, full_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用工具（使用完全限定名）"""
        if "/" not in full_name:
            return {"error": "Invalid tool name format. Expected: client_name/tool_name"}

        client_name, tool_name = full_name.split("/", 1)

        if client_name not in self._clients:
            return {"error": f"Unknown MCP client: {client_name}"}

        return await self._clients[client_name].call_tool(tool_name, arguments)

    def list_clients(self) -> List[str]:
        """列出所有客户端"""
        return list(self._clients.keys())


def load_mcp_config(config_path: str) -> List[Dict[str, Any]]:
    """
    加载 MCP 配置文件

    配置文件格式：
    ```json
    {
        "mcpServers": {
            "filesystem": {
                "command": "npx",
                "args": ["mcp-server-filesystem", "/path/to/dir"],
                "env": {}
            },
            "remote": {
                "transport": "http",
                "url": "http://localhost:8080/mcp"
            }
        }
    }
    ```
    """
    import json
    from pathlib import Path

    config_file = Path(config_path)
    if not config_file.exists():
        return []

    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)

    servers = config.get("mcpServers", {})
    clients = []

    for name, server_config in servers.items():
        if server_config.get("disabled", False):
            continue

        client_config = {
            "name": name,
            "transport": server_config.get("transport", "stdio"),
        }

        if client_config["transport"] == "stdio":
            client_config["command"] = server_config.get("command")
            client_config["args"] = server_config.get("args", [])
            client_config["env"] = server_config.get("env")
        else:
            client_config["url"] = server_config.get("url")

        clients.append(client_config)

    return clients
