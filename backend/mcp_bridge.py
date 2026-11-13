"""Cliente MCP del Orquestador. Descubre las tools del MCP Server y las expone a los agentes."""
import json
import time
from typing import Any

from mcp import Client

from core import config


class MCPError(RuntimeError):
    pass


def _parse_result(result) -> Any:
    if getattr(result, "structured_content", None):
        data = result.structured_content
        # Tools con retorno no tipado vienen envueltas en {"result": ...}
        return data.get("result", data) if isinstance(data, dict) and set(data) == {"result"} else data
    texts = [c.text for c in result.content if getattr(c, "type", "") == "text"]
    raw = "\n".join(texts)
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"text": raw}


class MCPBridge:
    def __init__(self, url: str | None = None):
        self.url = url or config.MCP_URL
        self._client: Client | None = None

    async def __aenter__(self) -> "MCPBridge":
        self._client = Client(self.url, read_timeout_seconds=30)
        try:
            await self._client.__aenter__()
        except Exception as exc:  # noqa: BLE001
            raise MCPError(f"MCP server no disponible en {self.url}: {exc}") from exc
        return self

    async def __aexit__(self, *exc):
        if self._client:
            try:
                await self._client.__aexit__(*exc)
            except Exception:  # noqa: BLE001
                pass

    async def list_tools(self) -> list[dict]:
        res = await self._client.list_tools()
        return [{"name": t.name, "description": (t.description or "").strip(), "input_schema": t.input_schema}
                for t in res.tools]

    async def claude_tools(self) -> list[dict]:
        """Convierte las tools MCP al formato de tools de la API de Claude."""
        tools = []
        for t in await self.list_tools():
            schema = dict(t["input_schema"] or {"type": "object", "properties": {}})
            schema.pop("title", None)
            tools.append({"name": t["name"], "description": t["description"], "input_schema": schema})
        return tools

    async def call(self, name: str, args: dict) -> tuple[Any, int]:
        t0 = time.perf_counter()
        result = await self._client.call_tool(name, args)
        ms = round((time.perf_counter() - t0) * 1000)
        data = _parse_result(result)
        if getattr(result, "is_error", False):
            raise MCPError(f"{name}: {data}")
        return data, ms


async def call_tool(name: str, args: dict) -> Any:
    """Llamada puntual (abre y cierra la sesión MCP)."""
    async with MCPBridge() as bridge:
        data, _ = await bridge.call(name, args)
        return data


async def list_tools() -> list[dict]:
    async with MCPBridge() as bridge:
        return await bridge.list_tools()
