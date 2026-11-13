"""Adapter de Jira: Mock (store local) o Jira Cloud real (REST API v3).

En modo live todo lo creado en Jira se refleja en el store local (espejo) para que
el dashboard siga siendo instantáneo. Si Jira real falla, se degrada a mock y se informa.
"""
import logging
from functools import lru_cache

import httpx

from core import config, store

log = logging.getLogger("mcp.jira")

STORY_NAMES = {"historia", "story", "user story", "historia de usuario"}


def _auth():
    return (config.JIRA_EMAIL, config.JIRA_API_TOKEN)


def _url(path: str) -> str:
    return f"{config.JIRA_BASE_URL}{path}"


def project_key(squad_id: str) -> str:
    """En live, todos los squads usan el proyecto de JIRA_PROJECT_KEY (si está definido)."""
    if config.jira_live() and config.JIRA_PROJECT_KEY:
        return config.JIRA_PROJECT_KEY
    return (store.get("squads", squad_id) or {}).get("jira_project", "DEMO")


@lru_cache(maxsize=8)
def issue_types(project: str) -> dict:
    """Descubre los ids reales de Épica e Historia del proyecto (los nombres varían por idioma)."""
    r = httpx.get(_url(f"/rest/api/3/project/{project}"), auth=_auth(), timeout=15)
    r.raise_for_status()
    types = r.json().get("issueTypes", [])
    epic = next((t for t in types if t.get("hierarchyLevel") == 1), None)
    story = next((t for t in types if t["name"].lower() in STORY_NAMES), None) or \
        next((t for t in types if t.get("hierarchyLevel") == 0 and not t.get("subtask")), None)
    return {"epic": epic["id"] if epic else None, "story": story["id"] if story else None,
            "epic_name": epic["name"] if epic else "Epic"}


# ─────────────────────────── Atlassian Document Format ───────────────────────────
def _para(text: str, bold: bool = False) -> dict:
    node = {"type": "text", "text": text}
    if bold:
        node["marks"] = [{"type": "strong"}]
    return {"type": "paragraph", "content": [node]}


def _heading(text: str, level: int = 3) -> dict:
    return {"type": "heading", "attrs": {"level": level}, "content": [{"type": "text", "text": text}]}


def _bullets(items: list[str]) -> dict:
    return {"type": "bulletList", "content": [
        {"type": "listItem", "content": [_para(i)]} for i in items if i]}


def _adf(text: str) -> dict:
    blocks = [_para(b.strip()) for b in (text or "").split("\n\n") if b.strip()]
    return {"type": "doc", "version": 1, "content": blocks or [{"type": "paragraph", "content": []}]}


def story_adf(story: dict) -> dict:
    content = []
    if story.get("user_story"):
        content += [_heading("Historia de usuario"), _para(story["user_story"])]
    if story.get("context"):
        content.append(_para(story["context"]))
    if story.get("gherkin"):
        content += [_heading("Criterios de aceptación (Gherkin)"),
                    {"type": "codeBlock", "attrs": {"language": "gherkin"},
                     "content": [{"type": "text", "text": story["gherkin"]}]}]
    if story.get("open_questions"):
        content += [_heading("Preguntas abiertas para el PO"), _bullets(story["open_questions"])]
    if story.get("technical_notes"):
        content += [_heading("Notas técnicas"), _bullets(story["technical_notes"])]
    if story.get("risks"):
        content += [_heading("Riesgos"), _bullets(story["risks"])]
    content.append(_para("Generada y validada por Brújula Operativa (agentes IA + MCP)."))
    return {"type": "doc", "version": 1, "content": content}


def add_comment(issue_key: str, text: str) -> bool:
    if not config.jira_live():
        return False
    try:
        r = httpx.post(_url(f"/rest/api/3/issue/{issue_key}/comment"), json={"body": _adf(text)},
                       auth=_auth(), timeout=10)
        r.raise_for_status()
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("No se pudo comentar en %s: %s", issue_key, exc)
        return False


def _add_labels(issue_key: str, labels: list[str]) -> None:
    httpx.put(_url(f"/rest/api/3/issue/{issue_key}"),
              json={"update": {"labels": [{"add": lbl} for lbl in labels]}},
              auth=_auth(), timeout=10).raise_for_status()


# ─────────────────────────── épicas ───────────────────────────
def active_epics(squad_id: str) -> tuple[list[dict], str]:
    local = [e for e in store.list_docs("epics", squad_id) if e.get("status") != "Cerrada"]
    if not config.jira_live():
        return local, "mock"
    project = project_key(squad_id)
    try:
        jql = f'project = "{project}" AND issuetype = {issue_types(project)["epic"]} AND statusCategory != Done ORDER BY created DESC'
        r = httpx.post(_url("/rest/api/3/search/jql"), auth=_auth(), timeout=10,
                       json={"jql": jql, "maxResults": 50, "fields": ["summary", "description", "status", "assignee", "labels"]})
        r.raise_for_status()
        epics = []
        for issue in r.json().get("issues", []):
            f = issue["fields"]
            prev = store.get("epics", issue["key"]) or {}
            epic = {
                "key": issue["key"], "squad": squad_id, "title": f.get("summary", ""),
                "objective": prev.get("objective", ""), "keywords": prev.get("keywords", []),
                "status": (f.get("status") or {}).get("name", ""), "progress": prev.get("progress", 0),
                "owner": ((f.get("assignee") or {}).get("displayName") or ""), "jira": True,
                "jira_url": _url(f"/browse/{issue['key']}"),
            }
            store.put("epics", epic["key"], epic)
            epics.append(epic)
        return epics, "jira"
    except Exception as exc:  # noqa: BLE001 — degradación controlada
        log.warning("Jira real no disponible, uso mock: %s", exc)
        return local, "mock (fallback)"


def create_epic(squad_id: str, title: str, objective: str, keywords: list[str]) -> tuple[dict, str]:
    sq = store.get("squads", squad_id) or {}
    project = project_key(squad_id)
    origin, key, url = "mock", None, None
    if config.jira_live():
        try:
            fields = {"project": {"key": project}, "summary": title,
                      "issuetype": {"id": issue_types(project)["epic"]},
                      "description": _adf(objective), "labels": ["brujula-operativa", f"squad-{squad_id}"]}
            r = httpx.post(_url("/rest/api/3/issue"), json={"fields": fields}, auth=_auth(), timeout=15)
            r.raise_for_status()
            key, origin = r.json()["key"], "jira"
            url = _url(f"/browse/{key}")
        except Exception as exc:  # noqa: BLE001
            log.warning("No se pudo crear la épica en Jira real, se crea en mock: %s", exc)
            origin = "mock (fallback)"
    if key is None:
        existing = len(store.list_docs("epics", squad_id))
        key = f"{project}-E{store.next_seq(f'epic:{squad_id}', existing + 1)}"
        while store.get("epics", key):  # por si el contador quedó desfasado
            key = f"{project}-E{store.next_seq(f'epic:{squad_id}', existing + 1)}"
    epic = {"key": key, "squad": squad_id, "title": title, "objective": objective, "keywords": keywords,
            "status": "Por hacer" if origin == "jira" else "En curso", "progress": 0, "owner": sq.get("po", ""),
            "created_by": "usuario", "created_at": store.now_iso(), "jira": origin == "jira", "jira_url": url}
    store.put("epics", key, epic)
    return epic, origin


# ─────────────────────────── historias ───────────────────────────
def create_story(squad_id: str, story: dict) -> tuple[dict, str]:
    project = project_key(squad_id)
    origin, key, url = "mock", None, None
    if config.jira_live():
        try:
            fields = {
                "project": {"key": project},
                "summary": story["title"],
                "issuetype": {"id": issue_types(project)["story"]},
                "description": story_adf(story),
                "labels": ["brujula-operativa", "brujula-ia", f"squad-{squad_id}"],
            }
            if story.get("epic_key"):
                fields["parent"] = {"key": story["epic_key"]}
            r = httpx.post(_url("/rest/api/3/issue"), json={"fields": fields}, auth=_auth(), timeout=15)
            if r.status_code >= 400 and "parent" in fields:
                log.warning("Jira rechazó el parent %s (%s); se crea sin épica", story.get("epic_key"), r.text[:200])
                fields.pop("parent")
                r = httpx.post(_url("/rest/api/3/issue"), json={"fields": fields}, auth=_auth(), timeout=15)
            r.raise_for_status()
            key = r.json()["key"]
            url = _url(f"/browse/{key}")
            origin = "jira"
        except Exception as exc:  # noqa: BLE001
            log.warning("No se pudo crear en Jira real, se crea en mock: %s", exc)
            origin = "mock (fallback)"
    if key is None:
        key = f"{project}-{store.next_seq(f'story:{squad_id}', 100)}"
        url = f"{config.APP_PUBLIC_URL}/#/story/{key}"
    doc = {**story, "key": key, "squad": squad_id, "jira_url": url, "jira": origin == "jira",
           "created_at": store.now_iso()}
    store.put("stories", key, doc)
    return doc, origin


def set_parent(story_key: str, epic_key: str) -> str:
    if not config.jira_live():
        return "mock"
    try:
        r = httpx.put(_url(f"/rest/api/3/issue/{story_key}"),
                      json={"fields": {"parent": {"key": epic_key} if epic_key else None}}, auth=_auth(), timeout=10)
        r.raise_for_status()
        return "jira"
    except Exception as exc:  # noqa: BLE001
        log.warning("No se pudo vincular %s a %s en Jira: %s", story_key, epic_key, exc)
        return "mock (fallback)"


TRANSITIONS = {
    "in_sprint": ["en curso", "in progress"],
    "done": ["listo", "finalizada", "done"],
    "refinement": ["por hacer", "to do"],
}


def transition(story_key: str, status: str) -> str:
    """Refleja el cambio en Jira real. Planning = etiqueta dor-ready + comentario (el estado sigue 'Por hacer')."""
    story = store.get("stories", story_key) or {}
    if not config.jira_live() or not story.get("jira"):
        return "mock"
    try:
        if status == "planning":
            _add_labels(story_key, ["dor-ready"])
            add_comment(story_key, "✅ Pasó el Definition of Ready en Brújula Operativa: épica vinculada, "
                                   "criterios Gherkin válidos, dependencias críticas resueltas y aprobación del dev. "
                                   "Lista para comprometer en el sprint.")
            return "jira"
        r = httpx.get(_url(f"/rest/api/3/issue/{story_key}/transitions"), auth=_auth(), timeout=10)
        r.raise_for_status()
        wanted = TRANSITIONS.get(status, [])
        for t in r.json().get("transitions", []):
            if t["name"].lower() in wanted or (t.get("to") or {}).get("name", "").lower() in wanted:
                httpx.post(_url(f"/rest/api/3/issue/{story_key}/transitions"),
                           json={"transition": {"id": t["id"]}}, auth=_auth(), timeout=10).raise_for_status()
                return "jira"
        return "jira (sin transición equivalente)"
    except Exception as exc:  # noqa: BLE001
        log.warning("Transición Jira falló: %s", exc)
        return "mock (fallback)"
