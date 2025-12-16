"""
MCPOrchestrator - Enchance orchestrator for Notion Assistant
Manages Weather and Notion MCP server with OAuth support
"""

import json
import asyncio
from contextlib import AsyncExitStack
from typing import Any, Dict, List, Optional, Tuple

from fastmcp import Client as MCPClient
from fastmcp.client.auth import OAuth


def to_plain_json_schema(schema_obj: Any) -> Dict[str,Any]:
    """Best-effort conversion to a plain JSON Schema dict (model-agnostic)."""
    if isinstance(schema_obj, dict):
        return schema_obj
    if hasattr(schema_obj, "model_dump"):
        return schema_obj.model_dump()
    if hasattr(schema_obj, "dict"):
        return schema_obj.dict()
    
    return json.loads(json.dumps(schema_obj, default=lambda o: getattr(o, "__dict__",{})))


def tool_result_to_text(result):
    try:
        sc = getattr(result, "structured_content", None) or getattr(result, "structuredContent", None)
        if sc is not None:
            return sc
        content = getattr(result, "content", None)

        if isinstance(content, (list, tuple)):
            texts = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    texts.append(block.get("text", ""))
                else:
                    t= getattr(block, "text", None)
                    if isinstance(t, str):
                        texts.append(t)
                
            if texts:
                return "\n".join(texts)
        return str(result)
    except Exception:
        return str(result)


class MCPOrchestrator:

    def __init__(self, weather_url: str= "http://localhost:3000/mcp", notion_url: str="https://mcp.notion.com/mcp"):

        self.weather_url = weather_url
        self.notion_url = notion_url
        self._clients: Dict[str, MCPClient] = {}
        self._stack: Optional[AsyncExitStack] = None

    async def __aenter__(self) -> "MCPOrchestrator":
        self._stack = AsyncExitStack()

        weather_client = MCPClient(self.weather_url)
        await self._stack.enter_async_context(weather_client)
        self._clients["weather"]= weather_client

        #connect to notion
        notion_client = MCPClient(self.notion_url, auth= OAuth(self.notion_url))
        await self._stack.enter_async_context(notion_client)
        self._clients["notion"] = notion_client

        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._stack:
            await self._stack.aclose()
        self._clients.clear()
        self._stack= None

    async def list_tools(self, server: str) -> List[Any]:
        """ Returns raw tools from specific server ."""
        if server not in self._clients:
            raise ValueError(f"Unknown server: {server}. Avaliable: {list(self._clients.keys())}")

        return await self._clients[server].list_tools()
    
    async def list_all_tools(self) -> Dict[str, List[Any]]:
        """Retruns mapping server -> list of raw tool objects"""
        out : Dict[str, List[Any]] = {}
        for name, c in self._clients.items():
            out[name] =  await c.list_tools()
        return out

    async def get_all_tool_specs(self, namespaced: bool = True) -> List[Dict[str,Any]]:
        
        specs: List[Dict[str, Any]]=[]

        for server, c in self._clients.items():
            tools = await c.list_tools()
            for t in tools:
                desc = getattr(t, "description", "") or getattr(t, "title", "")
                inputSchema = to_plain_json_schema(getattr(t, "inputSchema", {}) or {})
                bare_name = t.name
                full_name = f"{server}_{bare_name}" if namespaced else bare_name
                specs.append({
                    "server" : server,
                    "name" : full_name,
                    "bare_name" : bare_name,
                    "description" : desc,
                    "inputSchema" : inputSchema,
                })

        return specs

    async def call_tool(self, server: str, tool_name: str, args: Dict[str, Any]) -> Any:
        """Execute a tool on a specific server."""
        if server not in self._clients:
            raise ValueError(f"Unknown server: {server}. Available: {list(self._clients.keys())}")

        return await self._clients[server].call_tool(tool_name, args or {})

    async def call_tool_by_fullname(self, fullname: str, args: Dict[str, Any]) -> Tuple[str, Any]:

        if "_" not in fullname:
            raise ValueError("Expected namespaced tool name like 'notion_get-document'")
        
        server, bare = fullname.split("_", 1)
        res = await self.call_tool(server, bare, args)
        return server, res