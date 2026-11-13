"""Esquemas de salida estructurada (JSON Schema) de cada agente."""


def _obj(props: dict) -> dict:
    return {"type": "object", "properties": props, "required": list(props), "additionalProperties": False}


_STR = {"type": "string"}
_NUM = {"type": "number"}
_STR_LIST = {"type": "array", "items": _STR}

EPIC_SCHEMA = _obj({
    "epic_key": _STR,
    "epic_title": _STR,
    "confidence": _NUM,
    "rationale": _STR,
    "alternatives": {"type": "array", "items": _obj({"epic_key": _STR, "epic_title": _STR, "confidence": _NUM, "rationale": _STR})},
})

STORY_SCHEMA = _obj({
    "title": _STR,
    "user_story": _STR,
    "context": _STR,
    "acceptance_criteria_gherkin": _STR,
    "story_points": {"type": "integer"},
    "open_questions": _STR_LIST,
    "technical_notes": _STR_LIST,
    "risks": _STR_LIST,
})

COMPLIANCE_SCHEMA = _obj({
    "summary": _STR,
    "dependencies": {"type": "array", "items": _obj({
        "dependency_id": _STR, "name": _STR, "owner_area": _STR, "critical": {"type": "boolean"}, "notified": {"type": "boolean"},
    })},
    "additional_risks": _STR_LIST,
})

CEREMONY_SCHEMA = _obj({"bullets": _STR_LIST})
