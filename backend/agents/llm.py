"""Bucle agéntico con Claude (tool use sobre tools MCP + salida estructurada)."""
import json
import logging
import time
from typing import Any, Callable

import anthropic

from core import config

log = logging.getLogger("agents.llm")

_client: anthropic.AsyncAnthropic | None = None
_fallbacks_supported = True
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AgentError(RuntimeError):
    pass


def client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        _client = anthropic.AsyncAnthropic(max_retries=1, timeout=config.AI_TIMEOUT)
    return _client


async def _create(**kwargs):
    """Llama a Messages con fallback del lado del servidor ante rechazos; si la cuenta no tiene
    habilitada la beta, reintenta sin ella."""
    global _fallbacks_supported
    if _fallbacks_supported:
        try:
            return await client().beta.messages.create(betas=[FALLBACK_BETA], fallbacks="default", **kwargs)
        except anthropic.BadRequestError as exc:
            if "fallback" not in str(exc).lower() and "beta" not in str(exc).lower():
                raise
            log.warning("Fallbacks no disponibles, se desactivan: %s", exc)
            _fallbacks_supported = False
    return await client().beta.messages.create(**kwargs)


def _short(text: str, n: int = 320) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


async def run_agent(
    *,
    agent: str,
    system: str,
    prompt: str,
    schema: dict,
    tools: list[dict],
    execute_tool: Callable[[str, str, dict], Any],
    emit: Callable[[dict], None],
    max_turns: int = 8,
) -> dict:
    messages: list[dict] = [{"role": "user", "content": prompt}]
    for _ in range(max_turns):
        kwargs: dict[str, Any] = dict(
            model=config.ANTHROPIC_MODEL,
            max_tokens=16000,
            system=system,
            messages=messages,
            thinking={"type": "adaptive", "display": "summarized"},
            output_config={"effort": config.AI_EFFORT, "format": {"type": "json_schema", "schema": schema}},
        )
        if tools:
            kwargs["tools"] = tools
        t0 = time.perf_counter()
        resp = await _create(**kwargs)
        log.info("%s turno %s en %.1fs (stop=%s)", agent, len(messages), time.perf_counter() - t0, resp.stop_reason)

        for block in resp.content:
            if block.type == "thinking" and getattr(block, "thinking", ""):
                emit({"type": "thought", "agent": agent, "text": _short(block.thinking)})
            elif block.type == "text" and resp.stop_reason == "tool_use" and block.text.strip():
                emit({"type": "thought", "agent": agent, "text": _short(block.text)})

        if resp.stop_reason == "refusal":
            raise AgentError("El modelo declinó la solicitud")
        if resp.stop_reason == "max_tokens":
            raise AgentError("Respuesta truncada por max_tokens")
        if resp.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": resp.content})
            continue
        if resp.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for block in resp.content:
                if block.type != "tool_use":
                    continue
                try:
                    data = await execute_tool(agent, block.name, dict(block.input or {}))
                    results.append({"type": "tool_result", "tool_use_id": block.id,
                                    "content": json.dumps(data, ensure_ascii=False, default=str)})
                except Exception as exc:  # noqa: BLE001
                    results.append({"type": "tool_result", "tool_use_id": block.id, "content": f"Error: {exc}",
                                    "is_error": True})
            messages.append({"role": "user", "content": results})
            continue

        text = "".join(b.text for b in resp.content if b.type == "text")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise AgentError(f"Salida no es JSON válido: {exc}") from exc
    raise AgentError("Se alcanzó el máximo de turnos")


async def quick_json(system: str, prompt: str, schema: dict) -> dict:
    """Llamada única sin tools (resúmenes cortos)."""
    resp = await _create(
        model=config.ANTHROPIC_MODEL,
        max_tokens=4000,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": schema}},
    )
    if resp.stop_reason == "refusal":
        raise AgentError("refusal")
    return json.loads("".join(b.text for b in resp.content if b.type == "text"))
