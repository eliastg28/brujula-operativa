"""Supervisor de la Brújula Inteligente.

Flujo:  título vago
   ├─► [Vinculador de Épicas]  ─┐  (en paralelo)
   ├─► [Redactor de HU]        ─┤
   │                            ▼
   ├─► Supervisor: create_jira_story (MCP)
   ├─► [Riesgos & Compliance]: check_access_policies → register_dependency → send_teams_notification (MCP)
   └─► Gate DoR determinista  →  🔴 / 🟡 / 🟢
"""
import asyncio
import json
import logging
import time
from typing import Any, Callable

from core import config, domain, store

from ..mcp_bridge import MCPBridge
from . import llm, offline, prompts, schemas

log = logging.getLogger("agents.orchestrator")

Emit = Callable[[dict], None]


def summarize_tool(tool: str, args: dict, data: Any) -> str:
    try:
        if tool == "get_active_epics":
            return f'{len(data["epics"])} épicas activas · fuente: {data["source"]}'
        if tool == "create_epic":
            if data.get("duplicate"):
                return f'Ya existía: {data["key"]} · {data["title"]}'
            return f'Épica {data["key"]} creada en {data["source"]} · "{data["title"]}"'
        if tool == "check_access_policies":
            reqs = data["requirements"]
            crit = sum(1 for r in reqs if r["critical"])
            areas = ", ".join(dict.fromkeys(r["owner_area"] for r in reqs)) or "ninguna"
            return f'{len(reqs)} requisitos ({crit} críticos) de {data["rules_evaluated"]} reglas → {areas}'
        if tool == "register_dependency":
            return f'{data["id"]} ' + ("ya existía" if data.get("duplicate") else "registrada · contador de demora iniciado")
        if tool == "send_teams_notification":
            canal = "Correo" if args.get("channel") == "email" else "Teams"
            return f'{canal} → {args.get("to_name", "")} ({args.get("to_area", "")}) · {data["delivery"]}'
        if tool == "create_jira_story":
            return f'{data["key"]} creada en {data["source"]} · DoR inicial: {data["dor"]["light"]}'
        if tool == "get_backlog":
            return f'{len(data["stories"])} historias en backlog'
        if tool == "get_team_calendar":
            return f'{len(data["devs"])} devs · {len(data["alerts"])} alertas de capacidad'
        if tool == "get_pending_dependencies":
            return f'{len(data["pending"])} pendientes · {data["total_delay_days"]:.1f} días de demora acumulada'
        if tool == "update_story_status":
            return "OK" if data.get("ok") else f'Rechazado: {", ".join(data.get("reasons", []))}'
    except Exception:  # noqa: BLE001
        pass
    return json.dumps(data, ensure_ascii=False, default=str)[:160]


class Run:
    def __init__(self, squad_id: str, emit: Emit, bridge: MCPBridge, tools: list[dict]):
        self.squad_id = squad_id
        self.emit = emit
        self.bridge = bridge
        self.tools = {t["name"]: t for t in tools}
        self.story_key: str | None = None
        self.title = ""
        self._seq = 0

    def tools_for(self, agent: str) -> list[dict]:
        return [self.tools[n] for n in prompts.AGENTS[agent].get("tools", []) if n in self.tools]

    def start(self, agent: str) -> float:
        meta = prompts.AGENTS[agent]
        self.emit({"type": "agent_start", "agent": agent, "name": meta["name"], "role": meta["role"]})
        return time.perf_counter()

    def done(self, agent: str, t0: float, engine: str, summary: str) -> None:
        self.emit({"type": "agent_done", "agent": agent, "engine": engine, "summary": summary,
                   "ms": round((time.perf_counter() - t0) * 1000)})

    def thought(self, agent: str, text: str) -> None:
        self.emit({"type": "thought", "agent": agent, "text": text})

    async def exec_tool(self, agent: str, name: str, args: dict) -> Any:
        props = (self.tools.get(name) or {}).get("input_schema", {}).get("properties", {})
        if "squad_id" in props:
            args["squad_id"] = self.squad_id  # el agente no puede operar sobre otro squad
        if self.story_key and name in ("register_dependency", "send_teams_notification") and "story_key" in props:
            args["story_key"] = self.story_key
        self._seq += 1
        call_id = f"c{self._seq}"
        shown = {k: v for k, v in args.items() if k != "squad_id"}
        self.emit({"type": "tool_call", "agent": agent, "tool": name, "args": shown, "call_id": call_id})
        try:
            data, ms = await self.bridge.call(name, args)
        except Exception as exc:
            self.emit({"type": "tool_result", "agent": agent, "tool": name, "call_id": call_id, "ok": False,
                       "summary": str(exc)[:200], "ms": 0})
            raise
        self.emit({"type": "tool_result", "agent": agent, "tool": name, "call_id": call_id, "ok": True,
                   "summary": summarize_tool(name, args, data), "ms": ms})
        return data

    async def _try_claude(self, agent: str, **kwargs) -> dict | None:
        try:
            return await asyncio.wait_for(
                llm.run_agent(agent=agent, tools=self.tools_for(agent), execute_tool=self.exec_tool, emit=self.emit, **kwargs),
                timeout=config.AI_TIMEOUT,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("Agente %s cae a respaldo offline: %r", agent, exc)
            reason = "timeout" if isinstance(exc, asyncio.TimeoutError) else type(exc).__name__
            self.emit({"type": "fallback", "agent": agent,
                       "message": f"Claude no completó ({reason}). Continúa el motor de respaldo con las mismas tools MCP."})
            return None

    # ───────────────────────── agentes ─────────────────────────
    async def epic_agent(self, title: str, epic_key: str, engine: str) -> dict:
        """Valida la épica elegida por el usuario. Nunca la cambia ni crea épicas."""
        a = "epic"
        t0 = self.start(a)
        res = None
        if engine == "claude":
            res = await self._try_claude(a, system=prompts.EPIC_SYSTEM, schema=schemas.EPIC_SCHEMA,
                                         prompt=f"squad_id: {self.squad_id}\nTítulo de la historia: {title}\n"
                                                f"Épica seleccionada por el usuario: {epic_key}")
        if res is None:
            engine = "offline"
            self.thought(a, f"El usuario eligió la épica {epic_key}. Consulto en Jira (vía MCP) las épicas activas "
                            "para validar que la historia encaje con su objetivo.")
            data = await self.exec_tool(a, "get_active_epics", {"squad_id": self.squad_id})
            await offline.pause()
            res = offline.assess_epic(title, data["epics"], epic_key)
            self.thought(a, res["rationale"])
        # La decisión del usuario manda: se fuerza la épica seleccionada.
        epic = store.get("epics", epic_key) or {}
        res = {**res, "epic_key": epic_key, "epic_title": epic.get("title", res.get("epic_title", ""))}
        if res.get("alternatives"):
            alts = ", ".join(f'{x["epic_key"]} · {x["epic_title"]}' for x in res["alternatives"])
            self.thought(a, f"Sugerencia para el refinamiento (no se aplica): también podría encajar en {alts}.")
        self.done(a, t0, engine, self._epic_summary(res))
        return res

    @staticmethod
    def _epic_summary(res: dict) -> str:
        conf = round(float(res.get("confidence") or 0) * 100)
        return f'{res["epic_key"]} · {res["epic_title"]} validada (alineación {conf}%)'

    async def writer_agent(self, title: str, engine: str) -> dict:
        a = "writer"
        t0 = self.start(a)
        if engine == "claude":
            res = await self._try_claude(a, system=prompts.WRITER_SYSTEM, schema=schemas.STORY_SCHEMA,
                                         prompt=f"Título vago recibido en la Brújula: \"{title}\"")
            if res:
                self.done(a, t0, "claude", self._writer_summary(res))
                return res
        self.thought(a, f'Interpreto la intención de "{title}" y redacto la HU en formato Como/Quiero/Para.')
        await offline.pause(1.0)
        res = offline.write_story(title)
        self.thought(a, "Genero criterios Gherkin: caso feliz, borde, error y seguridad/auditoría.")
        await offline.pause(0.8)
        self.done(a, t0, "offline", self._writer_summary(res))
        return res

    @staticmethod
    def _writer_summary(res: dict) -> str:
        n = res.get("acceptance_criteria_gherkin", "").lower().count("escenario")
        return f'HU redactada · {n} escenarios Gherkin · {res.get("story_points", "?")} pts'

    async def compliance_agent(self, story_text: str, engine: str) -> dict:
        a = "compliance"
        t0 = self.start(a)
        if engine == "claude":
            res = await self._try_claude(
                a, system=prompts.COMPLIANCE_SYSTEM, schema=schemas.COMPLIANCE_SCHEMA, max_turns=10,
                prompt=f"squad_id: {self.squad_id}\nstory_key: {self.story_key}\n\nHistoria:\n{story_text}",
            )
            if res:
                self.done(a, t0, "claude", self._compliance_summary(res))
                return res
        self.thought(a, "Evalúo la historia contra el Catálogo de Políticas Corporativas vía MCP.")
        data = await self.exec_tool(a, "check_access_policies", {"squad_id": self.squad_id, "story_text": story_text})
        reqs = data["requirements"]
        crit = [r for r in reqs if r["critical"]]
        self.thought(a, f"El catálogo exige {len(reqs)} requisitos; {len(crit)} son críticos y bloquean el DoR. "
                        "Los registro y notifico a cada owner para que corra el SLA desde hoy, no desde el sprint.")
        deps = []
        for r in reqs:
            reg = await self.exec_tool(a, "register_dependency", {
                "squad_id": self.squad_id, "story_key": self.story_key, "requirement_id": r["requirement_id"],
                "name": r["name"], "dependency_type": r["type"], "owner_area": r["owner_area"],
                "owner_name": r["owner_name"], "owner_email": r["owner_email"], "critical": r["critical"],
                "sla_days": r["sla_days"], "policy_ref": r["policy_ref"], "reason": r["reason"],
            })
            notified = False
            if not reg.get("duplicate"):
                await self.exec_tool(a, "send_teams_notification", {
                    "squad_id": self.squad_id, "to_name": r["owner_name"], "to_area": r["owner_area"],
                    "to_email": r["owner_email"],
                    "title": f'Se requiere tu {r["type"]}: {r["name"]}',
                    "message": f'Hola {r["owner_name"].split()[0]}, la historia {self.story_key} necesita "{r["name"]}" '
                               f'para entrar al próximo sprint. {r["reason"]} Política: {r["policy_ref"]}. '
                               f'SLA: {r["sla_days"]} días hábiles.',
                    "severity": "high" if r["critical"] else "medium", "story_key": self.story_key,
                    "dependency_id": reg["id"], "kind": "solicitud",
                })
                notified = True
            deps.append({"dependency_id": reg["id"], "name": r["name"], "owner_area": r["owner_area"],
                         "critical": r["critical"], "notified": notified})
            await offline.pause(0.25)
        res = {
            "summary": f"{len(deps)} dependencias registradas y notificadas; {len(crit)} críticas bloquean el paso a Planning."
            if deps else "No se detectaron conformidades ni accesos requeridos por el catálogo.",
            "dependencies": deps,
            "additional_risks": [],
        }
        self.done(a, t0, "offline", self._compliance_summary(res))
        return res

    @staticmethod
    def _compliance_summary(res: dict) -> str:
        deps = res.get("dependencies", [])
        crit = sum(1 for d in deps if d.get("critical"))
        return f"{len(deps)} dependencias · {crit} críticas · owners notificados" if deps else "Sin dependencias operativas detectadas"


async def analyze(squad_id: str, title: str, epic_key: str, assignee: str | None, emit: Emit) -> dict:
    t_start = time.perf_counter()
    engine = "claude" if config.ai_available() else "offline"
    emit({
        "type": "run_start", "engine": engine,
        "model": config.ANTHROPIC_MODEL if engine == "claude" else "Motor de respaldo offline",
        "agents": {k: {"name": v["name"], "role": v["role"]} for k, v in prompts.AGENTS.items() if k != "ceremonies"},
    })
    async with MCPBridge() as bridge:
        tools = await bridge.claude_tools()
        emit({"type": "mcp_discovery", "tools": [t["name"] for t in tools], "url": config.MCP_URL})
        run = Run(squad_id, emit, bridge, tools)
        run.title = title

        sup = run.start("supervisor")
        epic = store.get("epics", epic_key) or {}
        run.thought("supervisor", f'Recibí el título "{title}" y la épica elegida {epic_key} · {epic.get("title", "")}. '
                                  "Sin criterios no puede pasar la Brújula: lanzo en paralelo al Vinculador de Épicas "
                                  "(valida la épica) y al Redactor de HU.")

        epic_res, story_res = await asyncio.gather(run.epic_agent(title, epic_key, engine), run.writer_agent(title, engine))

        run.thought("supervisor", "Consolido la propuesta y creo la historia en Jira vía MCP para empezar su trazabilidad.")
        created = await run.exec_tool("supervisor", "create_jira_story", {
            "squad_id": squad_id,
            "title": story_res["title"],
            "user_story": story_res["user_story"],
            "acceptance_criteria_gherkin": story_res["acceptance_criteria_gherkin"],
            "epic_key": epic_key,
            "epic_confidence": float(epic_res.get("confidence") or 0),
            "story_points": int(story_res.get("story_points") or 0),
            "assignee": assignee or "",
            "open_questions": story_res.get("open_questions", []),
            "risks": story_res.get("risks", []),
            "technical_notes": story_res.get("technical_notes", []),
        })
        run.story_key = created["key"]

        story_text = (f'{story_res["title"]}\n{story_res["user_story"]}\n{story_res.get("context", "")}\n'
                      f'{story_res["acceptance_criteria_gherkin"]}\nTítulo original: {title}')
        comp_res = await run.compliance_agent(story_text, engine)

        store.patch("stories", run.story_key, original_title=title, context=story_res.get("context", ""),
                    ai_analysis={"engine": engine, "epic": epic_res, "compliance": comp_res,
                                 "analyzed_at": store.now_iso()},
                    risks=list(dict.fromkeys((story_res.get("risks") or []) + (comp_res.get("additional_risks") or []))))

        story = domain.enrich_story(store.get("stories", run.story_key))
        ev = story["dor"]
        light_txt = {"red": "🔴 BLOQUEADA", "yellow": "🟡 EN REFINAMIENTO", "green": "🟢 READY"}[ev["light"]]
        motivo = f' — {", ".join(ev["reasons"])}' if ev["reasons"] else ""
        run.thought("supervisor", f"Gate DoR (regla determinista): {light_txt}{motivo}. "
                                  f'{ev["passed"]}/{ev["total"]} controles OK. '
                                  "El paso a Planning queda bloqueado hasta cumplir todos los controles.")
        run.done("supervisor", sup, engine, f'{run.story_key} → {light_txt}')

    total_ms = round((time.perf_counter() - t_start) * 1000)
    emit({"type": "story", "story": story})
    emit({"type": "done", "story_key": story["key"], "ms": total_ms, "engine": engine})
    return story
