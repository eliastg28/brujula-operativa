"""MCP Server · Brújula Operativa

Expone herramientas estandarizadas (Model Context Protocol) sobre Jira, Microsoft Teams,
el catálogo de políticas corporativas y el calendario del equipo. Cualquier cliente MCP
(nuestro orquestador, Claude Desktop, GitHub Copilot, etc.) puede usarlas sin cambios.

Ejecutar:
    python -m mcp_server.server            # streamable HTTP en :8001/mcp
    python -m mcp_server.server --stdio    # para Claude Desktop / IDEs
"""
import logging
import sys
import time
from contextlib import contextmanager

from mcp.server.mcpserver import MCPServer

from core import config, domain, dor, policies, store
from core.seed import seed_if_empty
from mcp_server.adapters import jira, teams

logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(asctime)s [mcp] %(message)s")
log = logging.getLogger("mcp")

mcp = MCPServer(
    "brujula-operativa",
    title="Brújula Operativa · MCP",
    version="1.0.0",
    instructions=(
        "Herramientas de gobierno del ciclo de desarrollo (SDLC) para equipos de un banco: "
        "épicas e historias en Jira, catálogo de políticas de seguridad/arquitectura, "
        "registro de dependencias operativas, notificaciones a Microsoft Teams y calendario del squad. "
        "Todas las herramientas reciben squad_id (ej. 'pagos', 'canales', 'riesgos')."
    ),
)


@contextmanager
def _logged(tool: str, args: dict):
    t0 = time.perf_counter()
    ok = True
    try:
        yield
    except Exception:
        ok = False
        raise
    finally:
        ms = round((time.perf_counter() - t0) * 1000)
        entry_id = f"L{store.next_seq('mcp_log'):06d}"
        summary = {k: (v if not isinstance(v, str) or len(v) < 80 else v[:77] + "…") for k, v in args.items()}
        store.put("mcp_log", entry_id, {"id": entry_id, "ts": store.now_iso(), "tool": tool, "args": summary,
                                        "duration_ms": ms, "ok": ok, "squad": args.get("squad_id")})
        log.info("%s %s (%d ms)", tool, "ok" if ok else "ERROR", ms)


def _create_notification(squad_id: str, **fields) -> dict:
    nid = f"N-{store.next_seq('notification', 1000)}"
    n = {"id": nid, "squad": squad_id, "sent_at": store.now_iso(), "read": False, **fields}
    n["delivery"] = teams.deliver(n)
    store.put("notifications", nid, n)
    return n


# ═════════════════════════════ JIRA ═════════════════════════════
@mcp.tool()
def get_active_epics(squad_id: str) -> dict:
    """Lista las épicas activas del squad en Jira: key, título, objetivo de negocio, palabras clave,
    % de avance y owner. Úsala SIEMPRE antes de vincular una historia a una épica."""
    with _logged("get_active_epics", {"squad_id": squad_id}):
        epics, source = jira.active_epics(squad_id)
        return {
            "source": source,
            "epics": [{k: e.get(k) for k in ("key", "title", "objective", "keywords", "progress", "owner")} for e in epics],
        }


@mcp.tool()
def create_epic(squad_id: str, title: str, objective: str, keywords: list[str] | None = None) -> dict:
    """Crea una Épica nueva en Jira a pedido del usuario (creación rápida desde la web o desde cualquier
    cliente MCP). Recibe un título de negocio, el objetivo y palabras clave (para sugerirla en historias
    futuras). Es idempotente por título: si ya existe una épica con el mismo título, la devuelve."""
    with _logged("create_epic", {"squad_id": squad_id, "title": title}):
        norm = policies.normalize(title).strip()
        for e in store.list_docs("epics", squad_id):
            if policies.normalize(e["title"]).strip() == norm:
                return {"key": e["key"], "title": e["title"], "source": "existente", "duplicate": True}
        kws = [policies.normalize(k).strip() for k in (keywords or []) if k and k.strip()]
        epic, source = jira.create_epic(squad_id, title.strip(), objective.strip(), kws)
        return {"key": epic["key"], "title": epic["title"], "source": source, "duplicate": False}


@mcp.tool()
def create_jira_story(
    squad_id: str,
    title: str,
    user_story: str,
    acceptance_criteria_gherkin: str,
    epic_key: str = "",
    epic_confidence: float = 0.0,
    story_points: int = 0,
    assignee: str = "",
    open_questions: list[str] | None = None,
    risks: list[str] | None = None,
    technical_notes: list[str] | None = None,
) -> dict:
    """Crea una Historia de Usuario en Jira con su descripción (Como/Quiero/Para), criterios de
    aceptación en Gherkin y épica padre. Devuelve la key creada y la evaluación inicial del DoR."""
    with _logged("create_jira_story", {"squad_id": squad_id, "title": title, "epic_key": epic_key}):
        story = {
            "title": title.strip(),
            "user_story": user_story.strip(),
            "gherkin": acceptance_criteria_gherkin.strip(),
            "epic_key": epic_key or None,
            "epic_confidence": epic_confidence or None,
            "points": story_points or None,
            "assignee": assignee or None,
            "status": "refinement",
            "dor_approved_by": None,
            "dor_approved_at": None,
            "ai_generated": True,
            "source": "brujula",
            "open_questions": open_questions or [],
            "risks": risks or [],
            "technical_notes": technical_notes or [],
        }
        doc, source = jira.create_story(squad_id, story)
        evaluation = dor.evaluate(doc, [])
        return {"key": doc["key"], "url": doc["jira_url"], "source": source,
                "dor": {"light": evaluation["light"], "reasons": evaluation["reasons"]}}


@mcp.tool()
def get_backlog(squad_id: str, light: str = "") -> dict:
    """Devuelve el backlog abierto del squad con el semáforo DoR de cada historia
    (red = bloqueada, yellow = en refinamiento, green = ready). Filtro opcional por light."""
    with _logged("get_backlog", {"squad_id": squad_id, "light": light}):
        items = domain.board(squad_id)
        if light:
            items = [s for s in items if s["dor"]["light"] == light]
        return {
            "stories": [
                {
                    "key": s["key"], "title": s["title"], "epic": (s.get("epic") or {}).get("title"),
                    "assignee": s.get("assignee"), "points": s.get("points"), "status": s.get("status"),
                    "light": s["dor"]["light"], "reasons": s["dor"]["reasons"],
                    "pending_dependencies": [d["name"] for d in s["dependencies"] if d["status"] == "pending"],
                    "open_questions": s.get("open_questions", []),
                }
                for s in items
            ]
        }


@mcp.tool()
def update_story_status(story_key: str, status: str) -> dict:
    """Cambia el estado de una historia (planning | in_sprint | done | refinement).
    El paso a 'planning' está protegido por el gate de Definition of Ready: si la historia
    no cumple el DoR, la operación se rechaza y se devuelven los motivos."""
    with _logged("update_story_status", {"story_key": story_key, "status": status}):
        story = store.get("stories", story_key)
        if not story:
            return {"ok": False, "error": f"Historia {story_key} no existe"}
        if status in ("planning", "in_sprint"):
            ev = dor.evaluate({**story, "status": "refinement"}, domain.deps_for(story_key))
            if not ev["ready"]:
                missing = [c["label"] for c in ev["checks"] if not c["ok"]]
                return {"ok": False, "blocked": True, "error": "Bloqueada por Definition of Ready",
                        "reasons": ev["reasons"], "missing": missing}
        sprint = domain.current_sprint(story["squad"])
        fields = {"status": status}
        if status == "planning" and sprint:
            fields["sprint_id"] = sprint["id"]
            fields["planned_at"] = store.now_iso()
        store.patch("stories", story_key, **fields)
        return {"ok": True, "story_key": story_key, "status": status, "source": jira.transition(story_key, status)}


# ═════════════════════════════ POLÍTICAS Y DEPENDENCIAS ═════════════════════════════
@mcp.tool()
def check_access_policies(squad_id: str, story_text: str) -> dict:
    """Evalúa el texto de una historia contra el Catálogo de Políticas Corporativas
    (PCI-DSS, arquitectura, privacidad, accesos a datos, fraude, regulatorio, infraestructura).
    Devuelve las conformidades, accesos y ambientes requeridos con su owner, SLA, criticidad
    y la política que los exige."""
    with _logged("check_access_policies", {"squad_id": squad_id, "story_text": story_text}):
        reqs = policies.evaluate(story_text, squad_id)
        return {"rules_evaluated": len(policies.load_rules()), "requirements": reqs}


@mcp.tool()
def register_dependency(
    squad_id: str,
    story_key: str,
    requirement_id: str,
    name: str,
    dependency_type: str,
    owner_area: str,
    owner_name: str,
    critical: bool,
    sla_days: int,
    policy_ref: str,
    reason: str = "",
    owner_email: str = "",
) -> dict:
    """Registra una dependencia operativa (conformidad, acceso, ambiente o definición) pendiente
    para una historia. Inicia el contador de demora y el seguimiento de SLA. Idempotente por
    (story_key, requirement_id)."""
    with _logged("register_dependency", {"squad_id": squad_id, "story_key": story_key, "requirement_id": requirement_id}):
        for d in store.list_docs("dependencies", squad_id):
            if d["story_key"] == story_key and d["requirement_id"] == requirement_id:
                return {"id": d["id"], "status": d["status"], "requested_at": d["requested_at"], "duplicate": True}
        dep_id = f"DEP-{store.next_seq('dep', 300)}"
        dep = {
            "id": dep_id, "squad": squad_id, "story_key": story_key, "requirement_id": requirement_id,
            "name": name, "type": dependency_type, "owner_area": owner_area, "owner_name": owner_name,
            "owner_email": owner_email, "critical": bool(critical), "sla_days": int(sla_days or 3),
            "policy_ref": policy_ref, "reason": reason, "requested_at": store.now_iso(),
            "status": "pending", "resolved_at": None, "escalated": False, "reminders": 0,
        }
        store.put("dependencies", dep_id, dep)
        return {"id": dep_id, "status": "pending", "requested_at": dep["requested_at"], "duplicate": False}


@mcp.tool()
def get_pending_dependencies(squad_id: str) -> dict:
    """Lista las dependencias operativas pendientes del squad con días de demora y estado de SLA."""
    with _logged("get_pending_dependencies", {"squad_id": squad_id}):
        b = domain.blockers(squad_id)
        return {
            "total_delay_days": b["total_delay_days"],
            "overdue": b["overdue"],
            "pending": [{k: d.get(k) for k in ("id", "story_key", "name", "owner_area", "owner_name", "age_days",
                                                 "sla_days", "sla_status", "critical")} for d in b["pending"]],
        }


# ═════════════════════════════ MICROSOFT TEAMS ═════════════════════════════
@mcp.tool()
def send_teams_notification(
    squad_id: str,
    to_name: str,
    to_area: str,
    title: str,
    message: str,
    severity: str = "medium",
    story_key: str = "",
    dependency_id: str = "",
    channel: str = "teams",
    kind: str = "solicitud",
    to_email: str = "",
) -> dict:
    """Envía una notificación (Adaptive Card de Microsoft Teams, o correo si channel='email') al owner
    responsable de una conformidad/acceso. severity: low|medium|high|critical.
    kind: solicitud|recordatorio|escalamiento|ceremonia|capacidad."""
    with _logged("send_teams_notification", {"squad_id": squad_id, "to_area": to_area, "title": title}):
        dep = store.get("dependencies", dependency_id) if dependency_id else None
        n = _create_notification(
            squad_id, channel=channel, kind=kind, to_name=to_name, to_area=to_area,
            to_email=to_email or (dep or {}).get("owner_email", ""), title=title, message=message,
            severity=severity, story_key=story_key, dependency_id=dependency_id,
            policy_ref=(dep or {}).get("policy_ref", ""), sla_days=(dep or {}).get("sla_days"),
        )
        return {"id": n["id"], "delivery": n["delivery"], "channel": channel}


# ═════════════════════════════ CALENDARIO Y CEREMONIAS ═════════════════════════════
@mcp.tool()
def get_team_calendar(squad_id: str) -> dict:
    """Devuelve el sprint próximo, los devs, sus vacaciones, puntos asignados vs capacidad real
    y las alertas de riesgo de capacidad."""
    with _logged("get_team_calendar", {"squad_id": squad_id}):
        cap = domain.capacity(squad_id)
        return {
            "sprint": cap["sprint"],
            "team_capacity": cap.get("team_capacity"),
            "team_assigned": cap.get("team_assigned"),
            "devs": [{k: d[k] for k in ("name", "role", "vacation_days", "capacity_pts", "assigned_pts", "risk")}
                     for d in cap["devs"]],
            "alerts": cap["alerts"],
        }


@mcp.tool()
def schedule_ceremony(
    squad_id: str,
    ceremony_type: str,
    date: str,
    time: str,
    duration_minutes: int,
    agenda: list[str],
    attendees: list[str] | None = None,
) -> dict:
    """Agenda una ceremonia ágil (daily | planning | refinamiento | retro) con su agenda
    y notifica al canal del squad en Teams."""
    with _logged("schedule_ceremony", {"squad_id": squad_id, "ceremony_type": ceremony_type, "date": date}):
        cid = f"CER-{store.next_seq('ceremony', 1)}"
        sq = store.get("squads", squad_id) or {}
        attendees = attendees or [d["name"] for d in store.list_docs("devs", squad_id)]
        doc = {"id": cid, "squad": squad_id, "type": ceremony_type, "date": date, "time": time,
               "duration": duration_minutes, "agenda_text": agenda, "attendees": attendees,
               "created_at": store.now_iso()}
        store.put("ceremonies", cid, doc)
        n = _create_notification(
            squad_id, channel="teams", kind="ceremonia", to_name=sq.get("teams_channel", "Canal del squad"),
            to_area=sq.get("squad_name", ""), title=f"📅 {ceremony_type.capitalize()} agendada — {date} {time}",
            message="Agenda:\n• " + "\n• ".join(agenda[:8]), severity="low", story_key="", dependency_id="",
        )
        return {"id": cid, "notification_id": n["id"], "delivery": n["delivery"]}


def main() -> None:
    seed_if_empty()
    if "--stdio" in sys.argv:
        mcp.run(transport="stdio")
    else:
        log.info("MCP server escuchando en http://127.0.0.1:%s/mcp (modo %s)", config.MCP_PORT, config.MODE)
        mcp.run(transport="streamable-http", host="127.0.0.1", port=config.MCP_PORT)


if __name__ == "__main__":
    main()
