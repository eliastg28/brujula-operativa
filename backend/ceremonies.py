"""Agente de Ceremonias: arma agendas desde el estado REAL del tablero (vía MCP)."""
import asyncio
import logging
from datetime import date, timedelta

from core import config, domain

from .agents import llm, prompts, schemas
from .mcp_bridge import MCPBridge

log = logging.getLogger("ceremonies")

META = {
    "daily": {"label": "Daily", "duration": 15, "time": "09:15"},
    "planning": {"label": "Sprint Planning", "duration": 120, "time": "09:30"},
    "refinamiento": {"label": "Refinamiento", "duration": 60, "time": "15:00"},
    "retro": {"label": "Retrospectiva", "duration": 60, "time": "16:00"},
}


def _suggest_date(ctype: str, sprint: dict | None) -> str:
    today = date.today()
    if not sprint:
        return today.isoformat()
    start, end = date.fromisoformat(sprint["start"]), date.fromisoformat(sprint["end"])
    if ctype == "planning":
        return start.isoformat()
    if ctype == "retro":
        return end.isoformat()
    if ctype == "refinamiento":
        return (start + timedelta(days=2)).isoformat()
    nxt = today + timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    return nxt.isoformat()


def _fmt_days(d: float) -> str:
    return f"{d:.1f} días"


async def generate(squad_id: str, ctype: str) -> dict:
    meta = META[ctype]
    trace = []
    async with MCPBridge() as bridge:
        backlog, ms1 = await bridge.call("get_backlog", {"squad_id": squad_id})
        trace.append({"tool": "get_backlog", "ms": ms1})
        calendar, ms2 = await bridge.call("get_team_calendar", {"squad_id": squad_id})
        trace.append({"tool": "get_team_calendar", "ms": ms2})
        pending, ms3 = await bridge.call("get_pending_dependencies", {"squad_id": squad_id})
        trace.append({"tool": "get_pending_dependencies", "ms": ms3})

    stories = backlog["stories"]
    red = [s for s in stories if s["light"] == "red"]
    yellow = [s for s in stories if s["light"] == "yellow"]
    green = [s for s in stories if s["light"] == "green"]
    ready_to_plan = [s for s in green if s["status"] not in ("planning", "in_sprint")]
    planned = [s for s in green if s["status"] in ("planning", "in_sprint")]
    alerts = calendar["alerts"]
    deps = pending["pending"]
    overdue = [d for d in deps if d["sla_status"] == "overdue"]
    sprint = calendar["sprint"]

    def story_line(s):
        extra = f' · {", ".join(s["reasons"])}' if s["reasons"] else ""
        return f'{s["key"]} {s["title"]} ({s.get("points") or "?"} pts · {s.get("assignee") or "sin asignar"}){extra}'

    def dep_line(d):
        return f'{d["story_key"]}: {d["name"]} — {d["owner_name"]} ({d["owner_area"]}) · {_fmt_days(d["age_days"])} / SLA {d["sla_days"]}d'

    blocks: list[dict] = []
    if ctype == "daily":
        blocks = [
            {"minutes": 2, "title": "Objetivo del sprint", "items": [sprint["goal"] if sprint else "—"]},
            {"minutes": 6, "title": "Bloqueos activos (con contador)", "items": [dep_line(d) for d in deps[:6]] or ["Sin bloqueos 🎉"]},
            {"minutes": 4, "title": "SLA vencidos a escalar hoy", "items": [dep_line(d) for d in overdue] or ["Ninguno"]},
            {"minutes": 3, "title": "Capacidad / ausencias", "items": [a["message"] for a in alerts] or ["Equipo completo"]},
        ]
    elif ctype == "planning":
        cap, asg = calendar.get("team_capacity") or 0, calendar.get("team_assigned") or 0
        blocks = [
            {"minutes": 10, "title": "Objetivo y capacidad real del equipo",
             "items": [sprint["goal"] if sprint else "—", f"Capacidad real (descontando vacaciones): {cap} pts · asignado: {asg} pts"]},
            {"minutes": 45, "title": "Historias READY (pasan el DoR) para comprometer",
             "items": [story_line(s) for s in ready_to_plan + planned] or ["No hay historias Ready — reforzar refinamiento"]},
            {"minutes": 20, "title": "NO entran al sprint (bloqueadas por la Brújula)", "items": [story_line(s) for s in red] or ["Ninguna"]},
            {"minutes": 20, "title": "Riesgos de capacidad por vacaciones", "items": [f'{a["message"]} {a["suggestion"]}' for a in alerts] or ["Sin riesgos"]},
            {"minutes": 25, "title": "Dependencias a destrabar antes del día 3", "items": [dep_line(d) for d in deps if d["critical"]] or ["Ninguna"]},
        ]
    elif ctype == "refinamiento":
        no_epic = [s for s in red if "Falta épica" in s["reasons"]]
        no_criteria = [s for s in red if "Faltan criterios" in s["reasons"]]
        blocks = [
            {"minutes": 15, "title": "Historias sin épica ('lo vemos después')", "items": [story_line(s) for s in no_epic] or ["Ninguna"]},
            {"minutes": 15, "title": "Historias sin criterios Gherkin", "items": [story_line(s) for s in no_criteria] or ["Ninguna"]},
            {"minutes": 15, "title": "Pendientes de aprobación DoR del dev", "items": [story_line(s) for s in yellow] or ["Ninguna"]},
            {"minutes": 15, "title": "Preguntas abiertas para el PO",
             "items": [f'{s["key"]}: {q}' for s in stories for q in s.get("open_questions", [])][:8] or ["Sin preguntas abiertas"]},
        ]
    else:  # retro
        total_delay = pending["total_delay_days"]
        by_area: dict[str, list[float]] = {}
        for d in deps:
            by_area.setdefault(d["owner_area"], []).append(d["age_days"])
        blocks = [
            {"minutes": 10, "title": "Métricas del sprint (datos, no opiniones)",
             "items": [f"Demora operativa acumulada: {_fmt_days(total_delay)}", f"SLA vencidos: {len(overdue)}",
                       f"Historias Ready: {len(green)} de {len(stories)}"]},
            {"minutes": 20, "title": "¿Dónde se nos fue el tiempo? (espera por área)",
             "items": [f"{area}: {_fmt_days(sum(v))} en {len(v)} solicitud(es)" for area, v in
                       sorted(by_area.items(), key=lambda x: -sum(x[1]))] or ["Sin esperas"]},
            {"minutes": 20, "title": "Acciones propuestas",
             "items": ["Acordar SLA formal con el área con mayor demora", "Pedir conformidades en refinamiento, no en planning",
                       "Registrar vacaciones con 2 sprints de anticipación"]},
            {"minutes": 10, "title": "Compromisos y responsables", "items": ["(completar en la sesión)"]},
        ]

    # Resumen ejecutivo: Claude si está disponible; si no, reglas.
    summary, engine = None, "offline"
    if config.ai_available():
        try:
            ctx = (f"Ceremonia: {meta['label']}\nRojas: {[story_line(s) for s in red]}\nAmarillas: {[story_line(s) for s in yellow]}\n"
                   f"Verdes: {[story_line(s) for s in green]}\nBloqueos: {[dep_line(d) for d in deps]}\n"
                   f"Alertas capacidad: {[a['message'] for a in alerts]}")
            res = await asyncio.wait_for(llm.quick_json(prompts.CEREMONY_SYSTEM, ctx, schemas.CEREMONY_SCHEMA), timeout=25)
            summary, engine = res["bullets"][:3], "claude"
        except Exception as exc:  # noqa: BLE001
            log.warning("Resumen IA de ceremonia falló, uso reglas: %r", exc)
    if not summary:
        summary = []
        if overdue:
            summary.append(f"Escalar hoy {len(overdue)} SLA vencido(s); el más antiguo: {overdue[0]['name']} ({_fmt_days(overdue[0]['age_days'])}).")
        if alerts:
            summary.append(f"Riesgo de capacidad: {alerts[0]['message']} {alerts[0]['suggestion']}")
        summary.append(f"{len(green)} historias Ready, {len(yellow)} en refinamiento y {len(red)} bloqueadas por la Brújula.")

    return {
        "type": ctype,
        "label": meta["label"],
        "date": _suggest_date(ctype, sprint),
        "time": meta["time"],
        "duration": meta["duration"],
        "attendees": [d["name"] for d in calendar["devs"]],
        "blocks": blocks,
        "summary": summary[:3],
        "engine": engine,
        "mcp_trace": trace,
        "sprint": sprint,
    }
