"""Adapter de Jira: Mock (store local) o Jira Cloud real (REST API v3).

En modo live todo lo creado en Jira se refleja en el store local (espejo) para que
el dashboard siga siendo instantáneo. Si Jira real falla, se degrada a mock y se informa.
"""
import logging

import httpx

from core import config, store

log = logging.getLogger("mcp.jira")


def _auth():
    return (config.JIRA_EMAIL, config.JIRA_API_TOKEN)


def _adf(text: str) -> dict:
    """Convierte texto plano a Atlassian Document Format."""
    content = []
    for block in text.split("\n\n"):
        lines = [ln for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        para = []
        for i, ln in enumerate(lines):
            if i:
                para.append({"type": "hardBreak"})
            para.append({"type": "text", "text": ln})
        content.append({"type": "paragraph", "content": para})
    return {"type": "doc", "version": 1, "content": content or [{"type": "paragraph", "content": []}]}


# ─────────────────────────── épicas ───────────────────────────
def active_epics(squad_id: str) -> tuple[list[dict], str]:
    local = [e for e in store.list_docs("epics", squad_id) if e.get("status") != "Cerrada"]
    sq = store.get("squads", squad_id) or {}
    if not config.jira_live() or not sq.get("jira_project"):
        return local, "mock"
    try:
        jql = f'project = "{sq["jira_project"]}" AND issuetype = Epic AND statusCategory != Done ORDER BY updated DESC'
        r = httpx.post(
            f"{config.JIRA_BASE_URL}/rest/api/3/search/jql",
            json={"jql": jql, "maxResults": 25, "fields": ["summary", "description", "status", "assignee"]},
            auth=_auth(), timeout=10,
        )
        r.raise_for_status()
        epics = []
        for issue in r.json().get("issues", []):
            f = issue["fields"]
            epic = {
                "key": issue["key"], "squad": squad_id, "title": f.get("summary", ""),
                "objective": "", "keywords": [], "status": (f.get("status") or {}).get("name", ""),
                "progress": 0, "owner": ((f.get("assignee") or {}).get("displayName") or ""),
            }
            store.put("epics", epic["key"], epic)
            epics.append(epic)
        return epics or local, "jira"
    except Exception as exc:  # noqa: BLE001 — degradación controlada
        log.warning("Jira real no disponible, uso mock: %s", exc)
        return local, "mock (fallback)"


def create_epic(squad_id: str, title: str, objective: str, keywords: list[str]) -> tuple[dict, str]:
    sq = store.get("squads", squad_id) or {}
    project = sq.get("jira_project", "DEMO")
    origin, key = "mock", None
    if config.jira_live():
        try:
            fields = {"project": {"key": project}, "summary": title, "issuetype": {"name": "Epic"},
                      "description": _adf(objective), "labels": ["brujula-operativa", "epica-auto"]}
            r = httpx.post(f"{config.JIRA_BASE_URL}/rest/api/3/issue", json={"fields": fields}, auth=_auth(), timeout=15)
            r.raise_for_status()
            key, origin = r.json()["key"], "jira"
        except Exception as exc:  # noqa: BLE001
            log.warning("No se pudo crear la épica en Jira real, se crea en mock: %s", exc)
            origin = "mock (fallback)"
    if key is None:
        existing = len(store.list_docs("epics", squad_id))
        key = f"{project}-E{store.next_seq(f'epic:{squad_id}', existing + 1)}"
        while store.get("epics", key):  # por si el contador quedó desfasado
            key = f"{project}-E{store.next_seq(f'epic:{squad_id}', existing + 1)}"
    epic = {"key": key, "squad": squad_id, "title": title, "objective": objective, "keywords": keywords,
            "status": "En curso", "progress": 0, "owner": sq.get("po", ""), "created_by": "usuario",
            "created_at": store.now_iso()}
    store.put("epics", key, epic)
    return epic, origin


# ─────────────────────────── historias ───────────────────────────
def create_story(squad_id: str, story: dict) -> tuple[dict, str]:
    sq = store.get("squads", squad_id) or {}
    project = sq.get("jira_project", "DEMO")
    origin = "mock"
    key = None
    url = None
    if config.jira_live():
        try:
            description = (
                f'{story.get("user_story", "")}\n\nCriterios de aceptación (Gherkin):\n{story.get("gherkin", "")}'
            )
            fields = {
                "project": {"key": project},
                "summary": story["title"],
                "issuetype": {"name": "Story"},
                "description": _adf(description),
                "labels": ["brujula-operativa", "brujula-ia"],
            }
            if story.get("epic_key"):
                fields["parent"] = {"key": story["epic_key"]}
            r = httpx.post(f"{config.JIRA_BASE_URL}/rest/api/3/issue", json={"fields": fields}, auth=_auth(), timeout=15)
            if r.status_code >= 400 and "parent" in fields:
                fields.pop("parent")
                r = httpx.post(f"{config.JIRA_BASE_URL}/rest/api/3/issue", json={"fields": fields}, auth=_auth(), timeout=15)
            r.raise_for_status()
            key = r.json()["key"]
            url = f"{config.JIRA_BASE_URL}/browse/{key}"
            origin = "jira"
        except Exception as exc:  # noqa: BLE001
            log.warning("No se pudo crear en Jira real, se crea en mock: %s", exc)
            origin = "mock (fallback)"
    if key is None:
        key = f"{project}-{store.next_seq(f'story:{squad_id}', 100)}"
        url = f"{config.APP_PUBLIC_URL}/#/story/{key}"
    doc = {**story, "key": key, "squad": squad_id, "jira_url": url, "created_at": store.now_iso()}
    store.put("stories", key, doc)
    return doc, origin


def transition(story_key: str, status: str) -> str:
    """Refleja el cambio de estado. En Jira real intenta la transición homónima."""
    if not config.jira_live():
        return "mock"
    names = {"planning": ["Ready for Sprint", "Selected for Development", "Listo", "To Do"],
             "in_sprint": ["In Progress", "En curso"], "done": ["Done", "Finalizada"]}
    try:
        r = httpx.get(f"{config.JIRA_BASE_URL}/rest/api/3/issue/{story_key}/transitions", auth=_auth(), timeout=10)
        r.raise_for_status()
        wanted = [n.lower() for n in names.get(status, [])]
        for t in r.json().get("transitions", []):
            if t["name"].lower() in wanted:
                httpx.post(f"{config.JIRA_BASE_URL}/rest/api/3/issue/{story_key}/transitions",
                           json={"transition": {"id": t["id"]}}, auth=_auth(), timeout=10).raise_for_status()
                return "jira"
        return "jira (sin transición equivalente)"
    except Exception as exc:  # noqa: BLE001
        log.warning("Transición Jira falló: %s", exc)
        return "mock (fallback)"
