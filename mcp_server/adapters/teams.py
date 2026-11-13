"""Adapter de notificaciones: Microsoft Teams (Adaptive Card vía Workflows webhook) y correo.

Siempre se guarda en el store (para el simulador visual de la web). Si hay credenciales
reales y MODE=live, además se envía de verdad.
"""
import logging
import smtplib
from email.message import EmailMessage

import httpx

from core import config

log = logging.getLogger("mcp.teams")

SEVERITY_COLOR = {"critical": "attention", "high": "warning", "medium": "accent", "low": "good"}


def adaptive_card(n: dict) -> dict:
    facts = [{"title": "Para", "value": f'{n.get("to_name", "")} · {n.get("to_area", "")}'}]
    if n.get("story_key"):
        facts.append({"title": "Historia", "value": n["story_key"]})
    if n.get("policy_ref"):
        facts.append({"title": "Política", "value": n["policy_ref"]})
    if n.get("sla_days"):
        facts.append({"title": "SLA", "value": f'{n["sla_days"]} días'})
    link = f'{config.APP_PUBLIC_URL}/#/bloqueos'
    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": [
            {"type": "TextBlock", "text": "🧭 Brújula Operativa", "weight": "Bolder", "size": "Small", "color": "Accent"},
            {"type": "TextBlock", "text": n["title"], "weight": "Bolder", "size": "Medium", "wrap": True,
             "color": SEVERITY_COLOR.get(n.get("severity", "medium"), "default")},
            {"type": "TextBlock", "text": n["message"], "wrap": True},
            {"type": "FactSet", "facts": facts},
        ],
        "actions": [
            {"type": "Action.OpenUrl", "title": "Aprobar / Responder", "url": link},
            {"type": "Action.OpenUrl", "title": "Ver historia", "url": f'{config.APP_PUBLIC_URL}/#/story/{n.get("story_key", "")}'},
        ],
    }


def deliver(n: dict) -> str:
    """Envía la notificación al canal real si está configurado. Devuelve el estado de entrega."""
    if n.get("channel") == "email":
        if not config.smtp_live():
            return "simulado"
        try:
            msg = EmailMessage()
            msg["Subject"] = f'[Brújula Operativa] {n["title"]}'
            msg["From"] = config.SMTP_FROM
            msg["To"] = n.get("to_email") or config.SMTP_FROM
            msg.set_content(f'{n["message"]}\n\nHistoria: {n.get("story_key", "-")}\n{config.APP_PUBLIC_URL}')
            with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as s:
                s.starttls()
                if config.SMTP_USER:
                    s.login(config.SMTP_USER, config.SMTP_PASSWORD)
                s.send_message(msg)
            return "enviado"
        except Exception as exc:  # noqa: BLE001
            log.warning("SMTP falló: %s", exc)
            return "error"

    if not config.teams_live():
        return "simulado"
    try:
        payload = {
            "type": "message",
            "attachments": [{"contentType": "application/vnd.microsoft.card.adaptive", "content": adaptive_card(n)}],
        }
        r = httpx.post(config.TEAMS_WEBHOOK_URL, json=payload, timeout=10)
        r.raise_for_status()
        return "enviado"
    except Exception as exc:  # noqa: BLE001
        log.warning("Webhook de Teams falló: %s", exc)
        return "error"
