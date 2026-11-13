"""Motor de Definition of Ready (DoR).

La decisión de bloquear el paso a Planning es CÓDIGO DETERMINISTA y auditable,
no una decisión del LLM. La IA redacta; el gate lo controla esta regla:

    READY  ⇔  épica vinculada ∧ HU en formato Como/Quiero/Para ∧ Gherkin válido
              ∧ aprobación explícita del dev asignado ∧ sin dependencias críticas pendientes
"""
import re

from .policies import normalize

SCENARIO_RE = re.compile(r"^\s*(escenario|esquema del escenario|scenario outline|scenario)\s*:", re.I)
STEP_RE = {
    "given": re.compile(r"^\s*(dado|dada|dados|dadas|given)\b", re.I),
    "when": re.compile(r"^\s*(cuando|when)\b", re.I),
    "then": re.compile(r"^\s*(entonces|then)\b", re.I),
    "and": re.compile(r"^\s*(y|e|pero|and|but)\b", re.I),
}

PLANNED_STATUSES = {"planning", "in_sprint", "done"}


def parse_gherkin(text: str) -> list[dict]:
    scenarios: list[dict] = []
    current = None
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if SCENARIO_RE.match(line):
            current = {"name": line.split(":", 1)[1].strip(), "given": 0, "when": 0, "then": 0}
            scenarios.append(current)
            continue
        for step in ("given", "when", "then"):
            if STEP_RE[step].match(line):
                if current is None:
                    current = {"name": "(sin nombre)", "given": 0, "when": 0, "then": 0}
                    scenarios.append(current)
                current[step] += 1
                break
    for sc in scenarios:
        sc["valid"] = sc["given"] > 0 and sc["when"] > 0 and sc["then"] > 0
    return scenarios


def has_user_story_format(text: str) -> bool:
    norm = normalize(text)
    return "como" in norm and "quiero" in norm and "para" in norm


def evaluate(story: dict, deps: list[dict]) -> dict:
    scenarios = parse_gherkin(story.get("gherkin", ""))
    valid_scenarios = [s for s in scenarios if s["valid"]]
    pending_critical = [d for d in deps if d.get("status") == "pending" and d.get("critical")]
    pending_other = [d for d in deps if d.get("status") == "pending" and not d.get("critical")]

    checks = [
        {
            "id": "epic",
            "label": "Épica vinculada",
            "ok": bool(story.get("epic_key")),
            "detail": story.get("epic_key") or "Sin épica — 'lo vemos después' no pasa la Brújula",
        },
        {
            "id": "user_story",
            "label": "Historia en formato Como / Quiero / Para",
            "ok": has_user_story_format(story.get("user_story", "")),
            "detail": "Redactada" if has_user_story_format(story.get("user_story", "")) else "Solo hay un título",
        },
        {
            "id": "gherkin",
            "label": "Criterios de aceptación Gherkin válidos",
            "ok": len(valid_scenarios) > 0,
            "detail": f"{len(valid_scenarios)} escenario(s) válidos (Dado/Cuando/Entonces)"
            if valid_scenarios
            else "Sin criterios de aceptación verificables",
        },
        {
            "id": "dependencies",
            "label": "Conformidades y accesos críticos resueltos",
            "ok": not pending_critical,
            "detail": "Sin dependencias operativas pendientes"
            if not pending_critical
            else f"{len(pending_critical)} pendiente(s): " + ", ".join(d["owner_area"] for d in pending_critical),
        },
        {
            "id": "approval",
            "label": "Aprobación DoR del desarrollador asignado",
            "ok": bool(story.get("dor_approved_by")),
            "detail": f'Aprobado por {story["dor_approved_by"]}'
            if story.get("dor_approved_by")
            else f'Pendiente de {story.get("assignee") or "asignar dev"}',
        },
    ]
    by_id = {c["id"]: c for c in checks}

    reasons = []
    if not by_id["epic"]["ok"]:
        reasons.append("Falta épica")
    if not by_id["user_story"]["ok"] or not by_id["gherkin"]["ok"]:
        reasons.append("Faltan criterios")
    if not by_id["dependencies"]["ok"]:
        reasons.append("Dependencia operativa pendiente")

    if reasons:
        light, state = "red", "blocked"
    elif not by_id["approval"]["ok"]:
        light, state = "yellow", "refinement"
    else:
        light, state = "green", "ready"

    if story.get("status") in PLANNED_STATUSES:
        # Ya pasó la Brújula; se muestra en verde con su estado de ciclo de vida.
        light, state = "green", story["status"]

    return {
        "light": light,
        "state": state,
        "ready": light == "green",
        "checks": checks,
        "passed": sum(1 for c in checks if c["ok"]),
        "total": len(checks),
        "reasons": reasons,
        "scenarios": scenarios,
        "warnings": [f'{d["name"]} (no crítica)' for d in pending_other],
    }


def can_approve(story: dict) -> tuple[bool, str]:
    if not story.get("epic_key"):
        return False, "No se puede aprobar el DoR: la historia no tiene épica vinculada."
    if not any(s["valid"] for s in parse_gherkin(story.get("gherkin", ""))):
        return False, "No se puede aprobar el DoR: faltan criterios de aceptación Gherkin válidos."
    return True, ""
