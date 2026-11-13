"""Orquestador · API web de Brújula Operativa (FastAPI)."""
import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel

from core import config, domain, dor, store
from core.policies import load_rules
from core.seed import reset as reset_seed, seed_if_empty

from . import ceremonies, mcp_bridge
from .agents import offline, orchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [api] %(name)s: %(message)s")
log = logging.getLogger("api")


# ───────────────────────── monitor de SLA (escalamiento automático) ─────────────────────────
async def sla_monitor():
    await asyncio.sleep(5)
    while True:
        try:
            for dep in store.list_docs("dependencies"):
                if dep["status"] != "pending" or dep.get("escalated"):
                    continue
                if domain.age_days(dep["requested_at"]) < dep.get("sla_days", 3):
                    continue
                sq = domain.squad(dep["squad"])
                await mcp_bridge.call_tool("send_teams_notification", {
                    "squad_id": dep["squad"], "to_name": f'{dep["owner_name"]} · cc {sq.get("lt", "LT")}',
                    "to_area": dep["owner_area"], "channel": "email", "kind": "escalamiento", "severity": "critical",
                    "title": f'⚠ SLA vencido: {dep["name"]}',
                    "message": f'La solicitud para {dep["story_key"]} superó su SLA de {dep["sla_days"]} días. '
                               f'Se escala automáticamente a la jefatura de {dep["owner_area"]} y al LT {sq.get("lt", "")}.',
                    "story_key": dep["story_key"], "dependency_id": dep["id"],
                })
                store.patch("dependencies", dep["id"], escalated=True)
                log.info("Escalada %s", dep["id"])
        except Exception as exc:  # noqa: BLE001
            log.debug("sla_monitor: %s", exc)
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if seed_if_empty():
        log.info("Base de datos de demo sembrada")
    task = asyncio.create_task(sla_monitor())
    yield
    task.cancel()


app = FastAPI(title="Brújula Operativa · Orquestador", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ───────────────────────── modelos de request ─────────────────────────
class AnalyzeReq(BaseModel):
    squad: str
    title: str
    epic_key: str = ""
    assignee: str | None = None


class EpicCreateReq(BaseModel):
    squad: str
    title: str
    objective: str = ""


class ApproveReq(BaseModel):
    by: str | None = None


class MoveReq(BaseModel):
    status: str = "planning"


class EpicReq(BaseModel):
    epic_key: str


class StoryPatch(BaseModel):
    title: str | None = None
    user_story: str | None = None
    gherkin: str | None = None
    points: int | None = None
    assignee: str | None = None


class ResolveReq(BaseModel):
    by: str | None = None
    comment: str | None = None


class VacationReq(BaseModel):
    squad: str
    dev_id: str
    start: str
    end: str
    note: str = "Vacaciones"


class CeremonyGenReq(BaseModel):
    squad: str
    type: str


class CeremonyScheduleReq(BaseModel):
    squad: str
    type: str
    date: str
    time: str
    duration: int
    blocks: list[dict]
    summary: list[str] = []
    attendees: list[str] = []


# ───────────────────────── salud / configuración ─────────────────────────
_mcp_cache = {"t": 0.0, "ok": False, "tools": 0}


@app.get("/api/health")
async def health():
    if time.time() - _mcp_cache["t"] > 10:
        try:
            tools = await asyncio.wait_for(mcp_bridge.list_tools(), timeout=5)
            _mcp_cache.update(t=time.time(), ok=True, tools=len(tools))
        except Exception:  # noqa: BLE001
            _mcp_cache.update(t=time.time(), ok=False, tools=0)
    return {
        "mode": config.MODE,
        "ai": {"enabled": config.ai_available(), "model": config.ANTHROPIC_MODEL if config.ai_available() else None,
               "effort": config.AI_EFFORT},
        "mcp": {"ok": _mcp_cache["ok"], "tools": _mcp_cache["tools"], "url": config.MCP_URL},
        "systems": {"jira": "live" if config.jira_live() else "mock", "teams": "live" if config.teams_live() else "mock",
                    "email": "live" if config.smtp_live() else "mock"},
        "policies": len(load_rules()),
    }


@app.get("/api/squads")
def squads():
    return [{k: s.get(k) for k in ("id", "tribu", "squad_name", "jira_project", "lt", "po", "teams_channel", "color")}
            for s in store.list_docs("squads")]


# ───────────────────────── dashboard ejecutivo ─────────────────────────
@app.get("/api/dashboard")
def dashboard(squad: str):
    sq = domain.squad(squad)
    if not sq:
        raise HTTPException(404, "Squad no existe")
    cap = domain.capacity(squad)
    blk = domain.blockers(squad)
    return {
        "squad": sq,
        "sprint": cap["sprint"],
        "kpis": domain.kpis(squad),
        "board": domain.board(squad),
        "capacity_alerts": cap["alerts"],
        "blockers": {"pending": len(blk["pending"]), "overdue": blk["overdue"], "total_delay_days": blk["total_delay_days"],
                     "top": blk["pending"][:4]},
    }


@app.get("/api/portfolio")
def portfolio():
    out = []
    for sq in store.list_docs("squads"):
        k = domain.kpis(sq["id"])
        blk = domain.blockers(sq["id"])
        out.append({"id": sq["id"], "tribu": sq["tribu"], "squad_name": sq["squad_name"], "color": sq.get("color"),
                    "counts": k["counts"], "ready_pct": next(t["value"] for t in k["tiles"] if t["id"] == "ready_pct"),
                    "hours_saved": next(t["value"] for t in k["tiles"] if t["id"] == "hours_saved"),
                    "pending_blockers": len(blk["pending"]), "delay_days": blk["total_delay_days"]})
    return out


# ───────────────────────── Brújula inteligente (SSE) ─────────────────────────
_running_tasks: set[asyncio.Task] = set()


@app.post("/api/brujula/analyze")
async def analyze(req: AnalyzeReq):
    if not req.title.strip():
        raise HTTPException(400, "Ingresa un título")
    if not domain.squad(req.squad):
        raise HTTPException(404, "Squad no existe")
    epic = store.get("epics", req.epic_key) if req.epic_key else None
    if not epic or epic.get("squad") != req.squad or (config.jira_live() and not epic.get("jira")):
        raise HTTPException(400, "Selecciona una épica del squad (o crea una nueva) antes de analizar")
    queue: asyncio.Queue = asyncio.Queue()
    t0 = time.perf_counter()

    def emit(event: dict):
        event["t"] = round((time.perf_counter() - t0) * 1000)
        queue.put_nowait(event)

    async def runner():
        try:
            await orchestrator.analyze(req.squad, req.title.strip(), req.epic_key, req.assignee, emit)
        except Exception as exc:  # noqa: BLE001
            log.exception("Fallo en la Brújula")
            emit({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        finally:
            queue.put_nowait(None)

    # La tarea es independiente de la conexión: si el navegador se desconecta,
    # los agentes terminan igual y la historia queda creada.
    task = asyncio.create_task(runner())
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)

    async def stream():
        while True:
            event = await queue.get()
            if event is None:
                break
            yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ───────────────────────── historias ─────────────────────────
def _story_or_404(key: str) -> dict:
    st = store.get("stories", key)
    if not st:
        raise HTTPException(404, f"Historia {key} no existe")
    return st


@app.get("/api/stories/{key}")
def get_story(key: str):
    return domain.enrich_story(_story_or_404(key))


@app.patch("/api/stories/{key}")
def patch_story(key: str, body: StoryPatch):
    _story_or_404(key)
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if {"user_story", "gherkin", "title"} & fields.keys():
        # Cambiar el contenido invalida la aprobación previa del dev.
        fields.update(dor_approved_by=None, dor_approved_at=None)
    store.patch("stories", key, **fields)
    return domain.enrich_story(store.get("stories", key))


@app.post("/api/stories/{key}/approve")
def approve(key: str, body: ApproveReq):
    st = _story_or_404(key)
    ok, msg = dor.can_approve(st)
    if not ok:
        return JSONResponse(status_code=409, content={"detail": msg})
    who = body.by or st.get("assignee") or "Dev asignado"
    store.patch("stories", key, dor_approved_by=who, dor_approved_at=store.now_iso())
    return domain.enrich_story(store.get("stories", key))


@app.post("/api/stories/{key}/unapprove")
def unapprove(key: str):
    _story_or_404(key)
    store.patch("stories", key, dor_approved_by=None, dor_approved_at=None)
    return domain.enrich_story(store.get("stories", key))


@app.post("/api/stories/{key}/move")
async def move(key: str, body: MoveReq):
    _story_or_404(key)
    res = await mcp_bridge.call_tool("update_story_status", {"story_key": key, "status": body.status})
    story = domain.enrich_story(store.get("stories", key))
    if not res.get("ok"):
        return JSONResponse(status_code=423, content={
            "detail": "Bloqueada por Definition of Ready", "reasons": res.get("reasons", []),
            "missing": res.get("missing", []), "story": story})
    return story


@app.post("/api/stories/{key}/epic")
async def set_epic(key: str, body: EpicReq):
    _story_or_404(key)
    if body.epic_key and not store.get("epics", body.epic_key):
        raise HTTPException(404, "Épica no existe")
    # Vía MCP: actualiza el vínculo en Jira real y reinicia la aprobación DoR.
    await mcp_bridge.call_tool("link_story_to_epic", {"story_key": key, "epic_key": body.epic_key or ""})
    return domain.enrich_story(store.get("stories", key))


def _squad_epics(squad: str) -> list[dict]:
    items = store.list_docs("epics", squad)
    # En modo live solo se ofrecen épicas que existen en Jira real.
    return [e for e in items if e.get("jira")] if config.jira_live() else items


@app.get("/api/epics")
async def epics(squad: str):
    if config.jira_live():
        try:
            await mcp_bridge.call_tool("get_active_epics", {"squad_id": squad})  # refresca el espejo desde Jira
        except Exception as exc:  # noqa: BLE001
            log.warning("No se pudieron refrescar épicas desde Jira: %s", exc)
    return _squad_epics(squad)


@app.get("/api/epics/suggest")
def suggest_epics(squad: str, title: str = ""):
    """Sugiere épicas EXISTENTES para el título (ranking determinista y rápido; no crea nada)."""
    if len(title.strip()) < 4:
        return []
    ranked = offline.rank_epics(title, _squad_epics(squad))
    return [r for r in ranked if r["score"] >= offline.MIN_EPIC_SCORE][:3]


@app.post("/api/epics")
async def create_epic(body: EpicCreateReq):
    """Creación rápida de épica desde la web (vía la tool MCP create_epic)."""
    title = " ".join(body.title.split())
    if len(title) < 3:
        raise HTTPException(400, "Escribe un título para la épica")
    if not domain.squad(body.squad):
        raise HTTPException(404, "Squad no existe")
    objective = body.objective.strip() or f"Agrupar las historias de {title[:1].lower() + title[1:]}."
    res = await mcp_bridge.call_tool("create_epic", {
        "squad_id": body.squad, "title": title, "objective": objective,
        "keywords": offline.extract_keywords(title, body.objective),
    })
    return {**res, "epic": store.get("epics", res["key"])}


@app.get("/api/devs")
def devs(squad: str):
    return store.list_docs("devs", squad)


# ───────────────────────── bloqueos ─────────────────────────
@app.get("/api/blockers")
def blockers(squad: str):
    return domain.blockers(squad)


@app.post("/api/dependencies/{dep_id}/resolve")
async def resolve(dep_id: str, body: ResolveReq):
    dep = store.get("dependencies", dep_id)
    if not dep:
        raise HTTPException(404, "Dependencia no existe")
    store.patch("dependencies", dep_id, status="resolved", resolved_at=store.now_iso(),
                resolved_by=body.by or dep["owner_name"], resolution_comment=body.comment or "")
    story = store.get("stories", dep["story_key"]) or {}
    try:
        await mcp_bridge.call_tool("send_teams_notification", {
            "squad_id": dep["squad"], "to_name": story.get("assignee") or "Squad", "to_area": "Desarrollo",
            "title": f'✅ Aprobado: {dep["name"]}',
            "message": f'{body.by or dep["owner_name"]} ({dep["owner_area"]}) aprobó la solicitud para {dep["story_key"]} '
                       f'en {domain.age_days(dep["requested_at"]):.1f} días.',
            "severity": "low", "story_key": dep["story_key"], "dependency_id": dep_id, "kind": "resuelto",
        })
    except Exception as exc:  # noqa: BLE001
        log.warning("No se pudo notificar resolución: %s", exc)
    return {"ok": True, "story": domain.enrich_story(store.get("stories", dep["story_key"]))}


@app.post("/api/dependencies/{dep_id}/remind")
async def remind(dep_id: str):
    dep = store.get("dependencies", dep_id)
    if not dep:
        raise HTTPException(404, "Dependencia no existe")
    age = domain.age_days(dep["requested_at"])
    res = await mcp_bridge.call_tool("send_teams_notification", {
        "squad_id": dep["squad"], "to_name": dep["owner_name"], "to_area": dep["owner_area"],
        "to_email": dep.get("owner_email", ""),
        "title": f'🔔 Recordatorio: {dep["name"]}',
        "message": f'La historia {dep["story_key"]} sigue esperando "{dep["name"]}" hace {age:.1f} días '
                   f'(SLA {dep["sla_days"]} días). ¿Nos ayudas a destrabarla?',
        "severity": "high" if age >= dep["sla_days"] else "medium", "story_key": dep["story_key"],
        "dependency_id": dep_id, "kind": "recordatorio",
    })
    store.patch("dependencies", dep_id, reminders=int(dep.get("reminders", 0)) + 1)
    return {"ok": True, "notification": res}


# ───────────────────────── capacidad / vacaciones ─────────────────────────
@app.get("/api/capacity")
def capacity(squad: str):
    return domain.capacity(squad)


@app.post("/api/vacations")
async def add_vacation(body: VacationReq):
    if body.end < body.start:
        raise HTTPException(400, "La fecha fin debe ser posterior al inicio")
    dev = store.get("devs", body.dev_id)
    if not dev:
        raise HTTPException(404, "Dev no existe")
    vid = f"VAC-{store.next_seq('vacation', 100)}"
    store.put("vacations", vid, {"id": vid, **body.model_dump()})
    cap = domain.capacity(body.squad)
    dev_cap = next((d for d in cap["devs"] if d["id"] == body.dev_id), {})
    # Alertar solo si las vacaciones cruzan el sprint y el dev queda en riesgo
    new_alert = next((a for a in cap["alerts"] if a["dev_id"] == body.dev_id), None) if dev_cap.get("vacation_days") else None
    if new_alert:
        sq = domain.squad(body.squad)
        try:
            await mcp_bridge.call_tool("send_teams_notification", {
                "squad_id": body.squad, "to_name": sq.get("lt", "LT"), "to_area": "Líder Técnico",
                "title": f'⚠ {new_alert["title"]}', "message": f'{new_alert["message"]} {new_alert["suggestion"]}',
                "severity": "high" if new_alert["severity"] == "high" else "medium", "kind": "capacidad",
            })
        except Exception as exc:  # noqa: BLE001
            log.warning("No se pudo notificar alerta de capacidad: %s", exc)
    return {"id": vid, "capacity": cap, "new_alert": new_alert}


@app.delete("/api/vacations/{vid}")
def delete_vacation(vid: str):
    store.delete("vacations", vid)
    return {"ok": True}


# ───────────────────────── ceremonias ─────────────────────────
@app.post("/api/ceremonies/generate")
async def gen_ceremony(body: CeremonyGenReq):
    if body.type not in ceremonies.META:
        raise HTTPException(400, "Tipo de ceremonia inválido")
    return await ceremonies.generate(body.squad, body.type)


@app.post("/api/ceremonies/schedule")
async def schedule_ceremony(body: CeremonyScheduleReq):
    agenda = [f'{b["minutes"]} min · {b["title"]}' for b in body.blocks]
    res = await mcp_bridge.call_tool("schedule_ceremony", {
        "squad_id": body.squad, "ceremony_type": body.type, "date": body.date, "time": body.time,
        "duration_minutes": body.duration, "agenda": agenda, "attendees": body.attendees or None,
    })
    store.patch("ceremonies", res["id"], blocks=body.blocks, summary=body.summary,
                label=ceremonies.META[body.type]["label"])
    return {**res, "ceremony": store.get("ceremonies", res["id"])}


@app.get("/api/ceremonies")
def list_ceremonies(squad: str):
    return sorted(store.list_docs("ceremonies", squad), key=lambda c: (c["date"], c["time"]))


@app.get("/api/ceremonies/{cid}/ics")
def ceremony_ics(cid: str):
    c = store.get("ceremonies", cid)
    if not c:
        raise HTTPException(404, "Ceremonia no existe")
    start = datetime.fromisoformat(f'{c["date"]}T{c["time"]}')
    end = start + timedelta(minutes=int(c["duration"]))
    fmt = "%Y%m%dT%H%M%S"
    desc = "\\n".join(c.get("agenda_text", []))
    ics = "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Brujula Operativa//ES", "BEGIN:VEVENT",
        f"UID:{cid}@brujula-operativa", f"DTSTAMP:{datetime.now().strftime(fmt)}",
        f"DTSTART:{start.strftime(fmt)}", f"DTEND:{end.strftime(fmt)}",
        f'SUMMARY:{c.get("label", c["type"]).upper()} · {domain.squad(c["squad"]).get("squad_name", "")}',
        f"DESCRIPTION:{desc}", "END:VEVENT", "END:VCALENDAR", "",
    ])
    return Response(ics, media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{cid}.ics"'})


# ───────────────────────── notificaciones (simulador Teams / Outlook) ─────────────────────────
@app.get("/api/notifications")
def notifications(squad: str, limit: int = 60):
    items = sorted(store.list_docs("notifications", squad), key=lambda n: n.get("sent_at", ""), reverse=True)
    return {"items": items[:limit], "unread": sum(1 for n in items if not n.get("read"))}


@app.post("/api/notifications/read")
def mark_read(squad: str):
    for n in store.list_docs("notifications", squad):
        if not n.get("read"):
            store.patch("notifications", n["id"], read=True)
    return {"ok": True}


# ───────────────────────── MCP / arquitectura ─────────────────────────
@app.get("/api/mcp/tools")
async def mcp_tools():
    try:
        return {"ok": True, "url": config.MCP_URL, "tools": await mcp_bridge.list_tools()}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "url": config.MCP_URL, "tools": [], "error": str(exc)}


@app.get("/api/mcp/log")
def mcp_log(limit: int = 40):
    items = sorted(store.list_docs("mcp_log"), key=lambda x: x["id"], reverse=True)
    return items[:limit]


@app.get("/api/policies")
def policies_catalog():
    return load_rules()


@app.post("/api/demo/reset")
def demo_reset():
    reset_seed()
    return {"ok": True}
