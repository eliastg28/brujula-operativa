"""Store documental sobre SQLite (WAL) compartido entre procesos.

En Modo Demo actúa como "Jira/Teams simulado". En Modo Live es el espejo local
de lo que se crea en los sistemas reales (para que el dashboard siga siendo instantáneo).
"""
import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

from .config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS docs(
    collection TEXT NOT NULL,
    id TEXT NOT NULL,
    squad TEXT,
    data TEXT NOT NULL,
    updated REAL NOT NULL,
    PRIMARY KEY (collection, id)
);
CREATE INDEX IF NOT EXISTS idx_docs_coll_squad ON docs(collection, squad);
CREATE TABLE IF NOT EXISTS counters(name TEXT PRIMARY KEY, value INTEGER NOT NULL);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


@contextmanager
def connect():
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


def init() -> None:
    with connect() as c:
        c.executescript(SCHEMA)


def put(collection: str, doc_id: str, data: dict[str, Any], squad: str | None = None) -> dict:
    data = dict(data)
    squad = squad if squad is not None else data.get("squad")
    with connect() as c:
        c.execute(
            "INSERT INTO docs(collection,id,squad,data,updated) VALUES(?,?,?,?,?) "
            "ON CONFLICT(collection,id) DO UPDATE SET squad=excluded.squad, data=excluded.data, updated=excluded.updated",
            (collection, doc_id, squad, json.dumps(data, ensure_ascii=False), time.time()),
        )
    return data


def get(collection: str, doc_id: str) -> dict | None:
    with connect() as c:
        row = c.execute("SELECT data FROM docs WHERE collection=? AND id=?", (collection, doc_id)).fetchone()
    return json.loads(row[0]) if row else None


def list_docs(collection: str, squad: str | None = None) -> list[dict]:
    with connect() as c:
        if squad:
            rows = c.execute(
                "SELECT data FROM docs WHERE collection=? AND squad=? ORDER BY id", (collection, squad)
            ).fetchall()
        else:
            rows = c.execute("SELECT data FROM docs WHERE collection=? ORDER BY id", (collection,)).fetchall()
    return [json.loads(r[0]) for r in rows]


def patch(collection: str, doc_id: str, **fields: Any) -> dict | None:
    doc = get(collection, doc_id)
    if doc is None:
        return None
    doc.update(fields)
    return put(collection, doc_id, doc)


def delete(collection: str, doc_id: str) -> None:
    with connect() as c:
        c.execute("DELETE FROM docs WHERE collection=? AND id=?", (collection, doc_id))


def next_seq(name: str, start: int = 1) -> int:
    with connect() as c:
        c.execute("BEGIN IMMEDIATE")
        row = c.execute("SELECT value FROM counters WHERE name=?", (name,)).fetchone()
        value = start if row is None else row[0] + 1
        c.execute(
            "INSERT INTO counters(name,value) VALUES(?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",
            (name, value),
        )
        c.execute("COMMIT")
    return value


def set_counter(name: str, value: int) -> None:
    with connect() as c:
        c.execute(
            "INSERT INTO counters(name,value) VALUES(?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",
            (name, value),
        )


def is_empty() -> bool:
    with connect() as c:
        row = c.execute("SELECT COUNT(*) FROM docs WHERE collection='squads'").fetchone()
    return row[0] == 0


def wipe() -> None:
    with connect() as c:
        c.execute("DELETE FROM docs")
        c.execute("DELETE FROM counters")
