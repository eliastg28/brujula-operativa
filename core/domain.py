"""Lógica de dominio de lectura: tablero, capacidad, bloqueos y KPIs."""
from datetime import date, datetime, timedelta, timezone

from . import dor, store


# ───────────────────────── utilidades de fechas ─────────────────────────
def parse_iso(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def age_days(ts: str) -> float:
    return (datetime.now(timezone.utc) - parse_iso(ts)).total_seconds() / 86400


def working_days(start: date, end: date) -> list[date]:
    days, d = [], start
    while d <= end:
        if d.weekday() < 5:
            days.append(d)
        d += timedelta(days=1)
    return days


def to_date(value: str) -> date:
    return date.fromisoformat(value[:10])


# ───────────────────────── squads / sprint ─────────────────────────
def squad(squad_id: str) -> dict:
    return store.get("squads", squad_id) or {}


def current_sprint(squad_id: str) -> dict | None:
    sprints = [s for s in store.list_docs("sprints", squad_id) if s.get("state") == "next"]
    return sprints[0] if sprints else None


# ───────────────────────── historias ─────────────────────────
def deps_for(story_key: str) -> list[dict]:
    return [d for d in store.list_docs("dependencies") if d.get("story_key") == story_key]


def enrich_story(story: dict, all_deps: list[dict] | None = None, epics: dict | None = None) -> dict:
    deps = [d for d in all_deps if d.get("story_key") == story["key"]] if all_deps is not None else deps_for(story["key"])
    if epics is None:
        epics = {e["key"]: e for e in store.list_docs("epics", story.get("squad"))}
    epic = epics.get(story.get("epic_key") or "")
    out = dict(story)
    out["dependencies"] = [enrich_dependency(d) for d in deps]
    out["epic"] = {"key": epic["key"], "title": epic["title"]} if epic else None
    out["dor"] = dor.evaluate(story, deps)
    return out


def board(squad_id: str) -> list[dict]:
    deps = store.list_docs("dependencies", squad_id)
    epics = {e["key"]: e for e in store.list_docs("epics", squad_id)}
    stories = [s for s in store.list_docs("stories", squad_id) if s.get("status") != "done"]
    enriched = [enrich_story(s, deps, epics) for s in stories]
    order = {"red": 0, "yellow": 1, "green": 2}
    enriched.sort(key=lambda s: (order[s["dor"]["light"]], s.get("created_at", "")), reverse=False)
    return enriched


# ───────────────────────── dependencias / bloqueos ─────────────────────────
def enrich_dependency(dep: dict) -> dict:
    out = dict(dep)
    end = dep.get("resolved_at") if dep.get("status") == "resolved" else None
    start = parse_iso(dep["requested_at"])
    stop = parse_iso(end) if end else datetime.now(timezone.utc)
    days = (stop - start).total_seconds() / 86400
    out["age_days"] = round(days, 2)
    sla = dep.get("sla_days") or 3
    ratio = days / sla
    out["sla_ratio"] = round(ratio, 2)
    out["sla_status"] = "overdue" if ratio >= 1 else "warning" if ratio >= 0.66 else "ok"
    return out


def blockers(squad_id: str) -> dict:
    deps = [enrich_dependency(d) for d in store.list_docs("dependencies", squad_id)]
    stories = {s["key"]: s for s in store.list_docs("stories", squad_id)}
    for d in deps:
        st = stories.get(d.get("story_key"), {})
        d["story_title"] = st.get("title", "")
        d["story_assignee"] = st.get("assignee", "")
    pending = sorted([d for d in deps if d["status"] == "pending"], key=lambda d: -d["age_days"])
    resolved = sorted([d for d in deps if d["status"] == "resolved"], key=lambda d: d.get("resolved_at", ""), reverse=True)
    by_area: dict[str, float] = {}
    for d in pending:
        by_area[d["owner_area"]] = by_area.get(d["owner_area"], 0) + d["age_days"]
    return {
        "pending": pending,
        "resolved": resolved[:10],
        "total_delay_days": round(sum(d["age_days"] for d in pending), 2),
        "overdue": sum(1 for d in pending if d["sla_status"] == "overdue"),
        "by_area": [{"area": k, "days": round(v, 1)} for k, v in sorted(by_area.items(), key=lambda x: -x[1])],
    }


# ───────────────────────── capacidad vs vacaciones ─────────────────────────
def capacity(squad_id: str) -> dict:
    sprint = current_sprint(squad_id)
    if not sprint:
        return {"sprint": None, "days": [], "devs": [], "alerts": []}
    days = working_days(to_date(sprint["start"]), to_date(sprint["end"]))
    day_set = {d.isoformat() for d in days}
    vacations = store.list_docs("vacations", squad_id)
    stories = [s for s in store.list_docs("stories", squad_id) if s.get("status") != "done"]
    devs_out = []
    for dev in store.list_docs("devs", squad_id):
        vac_days: set[str] = set()
        dev_vacs = []
        for v in vacations:
            if v["dev_id"] != dev["id"]:
                continue
            dev_vacs.append(v)
            for d in working_days(to_date(v["start"]), to_date(v["end"])):
                if d.isoformat() in day_set:
                    vac_days.add(d.isoformat())
        available = len(days) - len(vac_days)
        cap = round(available * dev.get("points_per_day", 0.8), 1)
        mine = [s for s in stories if s.get("assignee") == dev["name"]]
        assigned = sum(int(s.get("points") or 0) for s in mine)
        load = round(assigned / cap * 100) if cap else (999 if assigned else 0)
        risk = "none"
        if vac_days and assigned:
            risk = "high" if assigned > cap else "medium" if load >= 75 else "low"
        elif assigned > cap:
            risk = "medium"
        devs_out.append(
            {
                **dev,
                "vacation_days": sorted(vac_days),
                "vacations": dev_vacs,
                "available_days": available,
                "capacity_pts": cap,
                "assigned_pts": assigned,
                "load_pct": load,
                "stories": [{"key": s["key"], "title": s["title"], "points": s.get("points") or 0} for s in mine],
                "risk": risk,
            }
        )

    alerts = []
    for dev in devs_out:
        if dev["risk"] not in ("high", "medium"):
            continue
        free = sorted(
            [d for d in devs_out if d["id"] != dev["id"] and not d["vacation_days"]],
            key=lambda d: d["capacity_pts"] - d["assigned_pts"],
            reverse=True,
        )
        suggestion = ""
        if free and dev["stories"]:
            target = free[0]
            room = target["capacity_pts"] - target["assigned_pts"]
            movable = sorted(dev["stories"], key=lambda s: -s["points"])
            pick = next((s for s in movable if s["points"] <= room), movable[-1])
            suggestion = (
                f'Reasignar {pick["key"]} ({pick["points"]} pts) a {target["name"]} '
                f"(capacidad libre {room:.0f} pts)."
            )
        vac_text = f'{len(dev["vacation_days"])} día(s) de vacaciones en el sprint' if dev["vacation_days"] else "sin vacaciones"
        alerts.append(
            {
                "dev_id": dev["id"],
                "dev_name": dev["name"],
                "severity": dev["risk"],
                "title": f'Riesgo de capacidad: {dev["name"]}',
                "message": f'{dev["assigned_pts"]} pts asignados vs {dev["capacity_pts"]} pts disponibles ({vac_text}).',
                "suggestion": suggestion,
            }
        )
    return {
        "sprint": sprint,
        "days": [d.isoformat() for d in days],
        "devs": devs_out,
        "alerts": alerts,
        "team_capacity": round(sum(d["capacity_pts"] for d in devs_out), 1),
        "team_assigned": sum(d["assigned_pts"] for d in devs_out),
    }


# ───────────────────────── KPIs ─────────────────────────
# Supuestos explícitos (configurables) para que las métricas sean defendibles ante el jurado.
MIN_SAVED_PER_REFINED_STORY = 45      # 60 min de refinamiento manual vs 15 min revisando el borrador IA
MIN_SAVED_PER_AUTO_NOTIFICATION = 15  # redactar y perseguir por correo/Teams a cada owner
MIN_SAVED_PER_AGENDA = 30             # armar agenda de ceremonia desde el Excel
DAYS_AVOIDED_PER_EARLY_BLOCKER = 1.8  # días promedio de bloqueo en sprint cuando la dependencia se descubre tarde


def kpis(squad_id: str) -> dict:
    base = store.get("meta", f"kpi_baseline:{squad_id}") or {}
    stories = store.list_docs("stories", squad_id)
    deps = store.list_docs("dependencies", squad_id)
    notifs = store.list_docs("notifications", squad_id)
    ceremonies = store.list_docs("ceremonies", squad_id)
    brd = board(squad_id)
    cap = capacity(squad_id)

    ai_refined = base.get("historic_ai_refined", 0) + sum(1 for s in stories if s.get("ai_generated"))
    auto_notifs = base.get("historic_notifications", 0) + len(notifs)
    agendas = base.get("historic_agendas", 0) + len(ceremonies)
    hours = (
        ai_refined * MIN_SAVED_PER_REFINED_STORY
        + auto_notifs * MIN_SAVED_PER_AUTO_NOTIFICATION
        + agendas * MIN_SAVED_PER_AGENDA
    ) / 60
    deps_detected = base.get("historic_deps", 0) + len(deps)
    dead_days = deps_detected * DAYS_AVOIDED_PER_EARLY_BLOCKER

    total = len(brd)
    counts = {"red": 0, "yellow": 0, "green": 0}
    for s in brd:
        counts[s["dor"]["light"]] += 1
    ready_pct = round(counts["green"] / total * 100) if total else 0

    planned = [s for s in brd if s.get("status") in ("planning", "in_sprint")]
    incomplete = [
        s for s in planned if not all(c["ok"] for c in s["dor"]["checks"] if c["id"] in ("epic", "user_story", "gherkin"))
    ]
    incomplete_pct = round(len(incomplete) / len(planned) * 100) if planned else 0

    trend = list(base.get("ready_trend", [])) + [ready_pct]

    tiles = [
        {
            "id": "hours_saved",
            "label": "Horas ahorradas",
            "value": round(hours, 1),
            "unit": "h",
            "delta": f"{ai_refined} historias refinadas por IA",
            "formula": f"{ai_refined} HU × {MIN_SAVED_PER_REFINED_STORY} min + {auto_notifs} notificaciones × "
            f"{MIN_SAVED_PER_AUTO_NOTIFICATION} min + {agendas} agendas × {MIN_SAVED_PER_AGENDA} min",
            "tone": "blue",
        },
        {
            "id": "ready_pct",
            "label": "Backlog Ready",
            "value": ready_pct,
            "unit": "%",
            "delta": f'{counts["green"]} de {total} historias pasan el DoR',
            "formula": "Historias en verde (pasan el DoR determinista) / historias abiertas del backlog",
            "tone": "green",
        },
        {
            "id": "dead_days",
            "label": "Días muertos evitados",
            "value": round(dead_days, 1),
            "unit": "d",
            "delta": f"{deps_detected} dependencias anticipadas antes del sprint",
            "formula": f"{deps_detected} dependencias detectadas pre-sprint × {DAYS_AVOIDED_PER_EARLY_BLOCKER} días "
            "promedio de bloqueo cuando se descubren en pleno sprint",
            "tone": "violet",
        },
        {
            "id": "incomplete",
            "label": "HU incompletas en sprint",
            "value": incomplete_pct,
            "unit": "%",
            "delta": f'antes {base.get("incomplete_before_pct", 38)}% · la Brújula bloquea el resto',
            "formula": "Historias en Planning/Sprint sin épica o sin Gherkin. Línea base histórica del squad: "
            f'{base.get("incomplete_before_pct", 38)}% (medición manual previa a Brújula).',
            "tone": "red",
        },
        {
            "id": "capacity",
            "label": "Riesgos de capacidad",
            "value": len(cap["alerts"]),
            "unit": "",
            "delta": "vacaciones que cruzan con el sprint",
            "formula": "Devs con puntos asignados mayores a su capacidad real (días hábiles − vacaciones) × foco",
            "tone": "amber",
        },
    ]
    return {"tiles": tiles, "counts": counts, "ready_trend": trend, "sprint_labels": base.get("trend_labels", [])}
