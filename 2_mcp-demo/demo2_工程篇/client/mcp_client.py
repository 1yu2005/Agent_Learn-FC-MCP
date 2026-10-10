"""MCP Client 层（官方 SDK）：连接多个 Server，发现并聚合工具。

对应 MCP 架构图中的 Client 层：与每个 Server 建立会话，
把各 Server 暴露的工具统一提供给上层 Host（Agent）。
原理篇 client.py 的 _request("tools/list") 在这里就是 session.list_tools()。
"""
from mcp import ClientSession, StdioServerParameters   # 导入 MCP 官方 SDK
from mcp.client.stdio import stdio_client    # 导入 stdio 传输客户端


class MCPToolClient:
    """对单个 MCP Server 的客户端封装（stdio 传输）"""

    def __init__(self, command: str, args: list[str]):
        # StdioServerParameters：配置如何拉起 Server 子进程（对应原理篇 subprocess.Popen）  ⭐⭐⭐
        self._params = StdioServerParameters(command=command, args=args)

    async def list_tools(self) -> list[dict]:
        """协议方法 tools/list：发现工具，转换为 OpenAI Function Calling 格式"""
        async with stdio_client(self._params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()           # 握手（原理篇的 initialize）  ⭐⭐⭐
                tools = await session.list_tools()   # 协议方法 tools/list  ⭐⭐⭐
                return [
                    {
                        "type": "function",
                        "function": {
                            "name": t.name,
                            "description": t.description,
                            "parameters": t.inputSchema,  # MCP Schema → FC Schema
                        },
                    }
                    for t in tools.tools
                ]

    async def call_tool(self, name: str, arguments: dict) -> str:
        """协议方法 tools/call：调用 Server 侧工具，返回文本结果（供回填模型）"""
        async with stdio_client(self._params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()           # 握手（原理篇的 initialize）  ⭐⭐⭐
                result = await session.call_tool(name, arguments)  # 协议方法 tools/call  ⭐⭐⭐
                parts = [item.text for item in result.content if hasattr(item, "text")]
                return "\n".join(parts) if parts else str(result)


class MCPClientManager:
    """多 Server 聚合管理器：维护 工具名 → Server 的归属路由"""

    def __init__(self, servers: list[dict]):
        self._clients = {
            s["name"]: MCPToolClient(s["command"], s["args"]) for s in servers
        }
        self._tool_owner: dict[str, str] = {}   # 工具名 -> Server 名

    async def list_all_tools(self) -> list[dict]:
        """聚合所有 Server 的工具，并记录每个工具的归属 Server"""
        merged: list[dict] = []
        for server_name, client in self._clients.items():
            for tool in await client.list_tools():
                tool_name = tool["function"]["name"]
                self._tool_owner[tool_name] = server_name
                merged.append(tool)
        return merged

    async def call_tool(self, name: str, arguments: dict) -> str:
        """按路由表把工具调用分发到正确的 Server"""
        owner = self._tool_owner.get(name)
        if owner is None:
            return f"错误：未知工具 {name}"
        return await self._clients[owner].call_tool(name, arguments)
