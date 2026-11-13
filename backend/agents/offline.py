"""Motor de respaldo offline (sin LLM).

Garantiza que la demo nunca falle: si no hay API key, o si Claude excede el timeout,
los agentes siguen ejecutando las MISMAS tools MCP reales; solo la redacción se genera
con plantillas por dominio en lugar del modelo.
"""
import asyncio
import re

from core.policies import normalize

# ───────────────────────── plantillas de dominio ─────────────────────────
TEMPLATES = [
    {
        "match": ["pasarela", "checkout"],
        "title": "Integrar pasarela de pagos con tarjeta en canales digitales",
        "role": "cliente de banca digital",
        "want": "pagar mis compras con tarjeta a través de la nueva pasarela de pagos",
        "benefit": "completar la operación de forma segura sin salir del canal del banco",
        "context": "Se integra la pasarela del proveedor adquirente para autorizar y capturar pagos con tarjeta de crédito y débito. "
                   "Incluye autorización, captura, confirmación por webhook y manejo de errores. Fuera de alcance: pagos recurrentes y flujos post-venta (otra historia).",
        "gherkin": """Escenario: Pago con tarjeta autorizado
  Dado un cliente autenticado con un carrito de S/ 250.00
  Cuando paga con una tarjeta válida a través de la pasarela
  Entonces la pasarela autoriza la transacción en menos de 3 segundos
  Y el cliente ve el comprobante con el código de autorización

Escenario: Pago rechazado por fondos insuficientes
  Dado un cliente cuya tarjeta no tiene saldo suficiente
  Cuando intenta pagar S/ 250.00
  Entonces el sistema muestra "Pago rechazado: fondos insuficientes" sin exponer el código interno
  Y se registra el intento en la auditoría transaccional

Escenario: Timeout de la pasarela con reintento idempotente
  Dado que la pasarela no responde en 10 segundos
  Cuando el sistema reintenta la autorización con la misma Idempotency-Key
  Entonces no se genera un doble cobro al cliente
  Y la operación queda en estado "Pendiente de confirmación"

Escenario: Los datos de tarjeta nunca se almacenan
  Dado un pago procesado exitosamente
  Cuando se revisan los logs y la base de datos del banco
  Entonces solo existe el token del proveedor y los últimos 4 dígitos
  Y no existe PAN ni CVV en ningún registro""",
        "points": 8,
        "open_questions": [
            "¿El proveedor adquirente ya está contratado y tiene sandbox disponible?",
            "¿Se exige 3-D Secure para todos los montos o solo sobre un umbral?",
            "¿Cuál es el monto máximo por transacción en el canal?",
        ],
        "technical_notes": [
            "Tokenización del lado del proveedor: el PAN nunca toca servidores del banco (alcance PCI reducido).",
            "Idempotency-Key en cada autorización para evitar doble cobro.",
            "Webhook de confirmación firmado (HMAC) y validado antes de cambiar estado.",
        ],
        "risks": [
            "Si la conformidad PCI-DSS se demora, se bloquean las pruebas end-to-end.",
            "Inestabilidad del sandbox del proveedor puede afectar la automatización QA.",
        ],
    },
    {
        "match": ["login", "biometr", "contrasena", "autentic", "token", "2fa", "otp", "huella"],
        "role": "cliente de la app",
        "want": "{t}",
        "benefit": "acceder a mis productos de forma rápida y segura",
        "context": "Mejora el flujo de autenticación manteniendo los controles de seguridad vigentes. Incluye manejo de bloqueos y auditoría de accesos.",
        "gherkin": """Escenario: Autenticación exitosa
  Dado un cliente con su dispositivo enrolado
  Cuando se autentica con el nuevo mecanismo
  Entonces accede a su posición consolidada en menos de 2 segundos

Escenario: Intentos fallidos consecutivos
  Dado un cliente que falla la autenticación 3 veces seguidas
  Cuando intenta un cuarto acceso
  Entonces el acceso se bloquea por 15 minutos y se notifica al cliente

Escenario: Dispositivo no reconocido
  Dado un cliente que inicia sesión desde un dispositivo nuevo
  Cuando completa la autenticación
  Entonces se solicita validación adicional con token digital
  Y el evento queda registrado en la auditoría de seguridad""",
        "points": 5,
        "open_questions": ["¿Aplica a todos los segmentos de clientes o solo a un piloto?", "¿Cuál es el fallback si el dispositivo no soporta biometría?"],
        "technical_notes": ["Reutilizar el servicio corporativo de identidad (IAM).", "Registrar eventos en el SIEM corporativo."],
        "risks": ["Pentest de autenticación es prerrequisito para pasar a producción."],
    },
    {
        "match": ["reporte", "dashboard", "export", "csv", "excel", "anexo", "tablero"],
        "role": "analista del negocio",
        "want": "{t}",
        "benefit": "tomar decisiones con información confiable sin pedir extracciones manuales a TI",
        "context": "Se construye la vista o reporte a partir de las fuentes oficiales. Incluye filtros por fecha y exportación. No incluye nuevas fuentes de datos.",
        "gherkin": """Escenario: Consulta con datos disponibles
  Dado que existen datos para el rango de fechas seleccionado
  Cuando el analista consulta el reporte
  Entonces visualiza los indicadores en menos de 5 segundos

Escenario: Exportación del reporte
  Dado un reporte con resultados
  Cuando el analista selecciona "Exportar"
  Entonces descarga un archivo CSV con las mismas cifras que en pantalla

Escenario: Rango sin datos
  Dado un rango de fechas sin movimientos
  Cuando el analista consulta el reporte
  Entonces el sistema muestra "Sin datos para el periodo" en lugar de un error

Escenario: Usuario sin permisos
  Dado un usuario sin el rol de analista
  Cuando intenta acceder al reporte
  Entonces el acceso se deniega y el intento queda auditado""",
        "points": 5,
        "open_questions": ["¿Cuál es la fuente oficial de los datos y su frecuencia de actualización?", "¿Quiénes deben tener acceso?"],
        "technical_notes": ["Consultas sobre réplica de lectura, no sobre la BD transaccional.", "Paginar resultados de más de 10k filas."],
        "risks": ["Diferencias de cifras con reportes manuales actuales pueden generar desconfianza."],
    },
    {
        "match": ["notific", "push", "alerta", "correo", "sms"],
        "role": "cliente",
        "want": "{t}",
        "benefit": "enterarme a tiempo de los eventos importantes de mis productos",
        "context": "Se publica un evento y se entrega la notificación por el canal preferido del cliente, respetando sus preferencias de contacto.",
        "gherkin": """Escenario: Notificación entregada
  Dado un cliente con notificaciones habilitadas
  Cuando ocurre el evento de negocio
  Entonces recibe la notificación en menos de 10 segundos

Escenario: Cliente con notificaciones deshabilitadas
  Dado un cliente que deshabilitó este tipo de aviso
  Cuando ocurre el evento
  Entonces no se envía la notificación y se registra en su bandeja de la app

Escenario: Falla del proveedor de mensajería
  Dado que el proveedor de envío no está disponible
  Cuando se intenta entregar la notificación
  Entonces se reintenta hasta 3 veces con backoff y luego se registra como fallida""",
        "points": 3,
        "open_questions": ["¿Qué canales aplican: push, correo, SMS?", "¿Hay horario restringido de envío?"],
        "technical_notes": ["Publicar el evento en el bus corporativo y consumirlo de forma asíncrona."],
        "risks": ["Saturación del proveedor en campañas masivas."],
    },
]

GENERIC = {
    "role": "usuario del negocio",
    "want": 'disponer de la funcionalidad "{T}"',
    "benefit": "resolver la necesidad sin procesos manuales ni dependencias de otras áreas",
    "context": "Historia derivada del título '{T}'. El alcance debe confirmarse con el PO en refinamiento; se proponen criterios base para habilitar la conversación.",
    "gherkin": """Escenario: Flujo principal exitoso
  Dado un usuario autenticado con los permisos necesarios
  Cuando ejecuta "{T}" con datos válidos
  Entonces el sistema completa la operación y muestra la confirmación

Escenario: Datos inválidos
  Dado un usuario autenticado
  Cuando envía información incompleta o con formato incorrecto
  Entonces el sistema indica exactamente qué campo corregir sin perder lo ingresado

Escenario: Falla de un servicio dependiente
  Dado que un servicio del que depende la funcionalidad no responde
  Cuando el usuario ejecuta la operación
  Entonces se muestra un mensaje amigable y el error queda registrado para soporte

Escenario: Trazabilidad y auditoría
  Dado una operación completada
  Cuando auditoría revisa los registros
  Entonces existe el evento con usuario, fecha, hora y resultado""",
    "points": 5,
    "open_questions": ["¿Cuál es el resultado de negocio esperado y cómo se mide?", "¿Qué queda fuera del alcance de esta historia?"],
    "technical_notes": ["Validar con Arquitectura si reutiliza un servicio existente."],
    "risks": ["Alcance ambiguo: riesgo de retrabajo si no se acota en refinamiento."],
}


def _pick_template(title: str) -> dict:
    norm = normalize(title)
    for tpl in TEMPLATES:
        if any(k in norm for k in tpl["match"]):
            return tpl
    return GENERIC


def _lower_first(text: str) -> str:
    return text[:1].lower() + text[1:] if text else text


def write_story(title: str) -> dict:
    tpl = _pick_template(title)
    clean = title.strip().rstrip(".")
    t_lower = _lower_first(clean)
    fmt = lambda s: s.replace("{t}", t_lower).replace("{T}", clean)  # noqa: E731
    new_title = tpl.get("title") or (clean[:1].upper() + clean[1:])
    return {
        "title": new_title,
        "user_story": f'Como {tpl["role"]}, quiero {fmt(tpl["want"])}, para {tpl["benefit"]}.',
        "context": fmt(tpl["context"]),
        "acceptance_criteria_gherkin": fmt(tpl["gherkin"]),
        "story_points": tpl["points"],
        "open_questions": tpl["open_questions"],
        "technical_notes": tpl["technical_notes"],
        "risks": tpl["risks"],
    }




MIN_EPIC_SCORE = 2  # al menos una palabra clave de la épica o dos coincidencias con su título/objetivo
STOPWORDS = {"para", "como", "desde", "hacia", "entre", "sobre", "with", "nuevo", "nueva", "nuevos", "nuevas",
             "mejorar", "agregar", "integrar", "crear", "implementar", "habilitar", "permitir", "todos", "todas",
             "historias", "relacionadas", "cliente", "clientes"}


def _confidence(score: int) -> float:
    return round(min(0.97, 0.45 + 0.12 * score), 2) if score > 0 else 0.0


def rank_epics(title: str, epics: list[dict]) -> list[dict]:
    """Ordena las épicas EXISTENTES por afinidad con el título (no crea nada)."""
    norm = normalize(title)
    words = set(re.findall(r"[a-z]{4,}", norm))
    ranked = []
    for e in epics:
        kws = [normalize(k) for k in e.get("keywords") or [] if k]
        kw_hits = sum(1 for k in kws if re.search(r"(?<![a-z0-9])" + re.escape(k), norm))
        epic_words = set(re.findall(r"[a-z]{4,}", normalize(e["title"] + " " + (e.get("objective") or "")))) - STOPWORDS
        score = kw_hits * 2 + len((words - STOPWORDS) & epic_words)
        ranked.append({"epic_key": e["key"], "epic_title": e["title"], "score": score, "confidence": _confidence(score)})
    ranked.sort(key=lambda r: -r["score"])
    return ranked


def assess_epic(title: str, epics: list[dict], selected_key: str) -> dict:
    """Valida la épica elegida por el usuario y sugiere alternativas existentes si encajan mejor."""
    ranked = rank_epics(title, epics)
    sel = next((r for r in ranked if r["epic_key"] == selected_key), None)
    epic = next((e for e in epics if e["key"] == selected_key), {})
    sel_score = sel["score"] if sel else 0
    better = [r for r in ranked if r["epic_key"] != selected_key and r["score"] >= MIN_EPIC_SCORE and r["score"] > sel_score][:2]
    if sel_score >= MIN_EPIC_SCORE:
        confidence = sel["confidence"]
        rationale = (f'La historia encaja con el objetivo de la épica seleccionada: '
                     f'"{epic.get("objective") or epic.get("title", "")}".')
    else:
        # Épicas nuevas aún no tienen historial: se respeta la decisión del usuario con confianza media.
        confidence = 0.6 if not better else 0.4
        rationale = ("Se respeta la épica elegida por el usuario."
                     + (" Hay épicas existentes con mayor afinidad; revísalas antes del refinamiento." if better else ""))
    return {
        "epic_key": selected_key,
        "epic_title": epic.get("title", ""),
        "confidence": confidence,
        "rationale": rationale,
        "alternatives": [{"epic_key": r["epic_key"], "epic_title": r["epic_title"], "confidence": r["confidence"],
                          "rationale": f'Mayor coincidencia con "{r["epic_title"]}".'} for r in better],
    }


def extract_keywords(*texts: str, limit: int = 8) -> list[str]:
    words = []
    for t in texts:
        words += [w for w in re.findall(r"[a-z]{4,}", normalize(t or "")) if w not in STOPWORDS]
    return list(dict.fromkeys(words))[:limit]


async def pause(seconds: float = 0.7) -> None:
    """Pequeña pausa para que el jurado pueda leer la traza en pantalla."""
    await asyncio.sleep(seconds)
