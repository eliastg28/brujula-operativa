"""Evaluación determinista de historias contra el catálogo de políticas."""
import re
import unicodedata
from functools import lru_cache

import yaml

from .config import CONFIG_DIR


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


@lru_cache(maxsize=1)
def load_rules() -> list[dict]:
    with open(CONFIG_DIR / "politicas.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["reglas"]


@lru_cache(maxsize=1)
def load_squads() -> list[dict]:
    with open(CONFIG_DIR / "squads.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["squads"]


def evaluate(text: str, squad_id: str | None = None) -> list[dict]:
    """Devuelve los requisitos (conformidades/accesos) que exige el catálogo."""
    norm = normalize(text)
    results = []
    for rule in load_rules():
        tribus = rule.get("tribus")
        if tribus and squad_id not in tribus:
            continue
        # Coincidencia al inicio de palabra (raíz): "tokeniz" → "tokenización", pero "visa" no matchea "revisa".
        hits = sorted({kw for kw in rule["keywords"] if re.search(r"(?<![a-z0-9])" + re.escape(normalize(kw)), norm)})
        if not hits:
            continue
        results.append(
            {
                "requirement_id": rule["id"],
                "policy_ref": f'{rule["id"]} · {rule["politica"]}',
                "name": rule["requisito"],
                "type": rule["tipo"],
                "owner_area": rule["area"],
                "owner_name": rule["owner"],
                "owner_email": rule["email"],
                "sla_days": rule["sla_dias"],
                "critical": bool(rule["critica"]),
                "reason": rule["motivo"],
                "matched_keywords": hits,
            }
        )
    results.sort(key=lambda r: (not r["critical"], r["sla_days"]))
    return results
