"""Datos de demo realistas. Las fechas son relativas a HOY para que los contadores
de demora y los cruces de vacaciones siempre tengan sentido el día de la demo."""
from datetime import date, datetime, timedelta, timezone

from . import store
from .policies import load_squads


def _ago(days: float = 0, hours: float = 0) -> str:
    ts = datetime.now(timezone.utc) - timedelta(days=days, hours=hours)
    return ts.isoformat(timespec="seconds").replace("+00:00", "Z")


def _next_monday(today: date) -> date:
    return today + timedelta(days=(7 - today.weekday()) % 7)


TODAY = date.today()
SPRINT_START = _next_monday(TODAY)
SPRINT_END = SPRINT_START + timedelta(days=11)


def _d(offset: int) -> str:
    return (SPRINT_START + timedelta(days=offset)).isoformat()


# ─────────────────────────────── Gherkin de ejemplo ───────────────────────────────
G_REEMBOLSO = """Escenario: Reembolso parcial exitoso
  Dado un pago capturado de S/ 500.00 en estado "Liquidado"
  Cuando el operador de backoffice solicita un reembolso parcial de S/ 120.00
  Entonces el sistema registra el reembolso y el saldo reembolsable queda en S/ 380.00
  Y se notifica al cliente por correo

Escenario: Reembolso mayor al saldo disponible
  Dado un pago con saldo reembolsable de S/ 50.00
  Cuando el operador solicita un reembolso de S/ 80.00
  Entonces el sistema rechaza la operación con el mensaje "Monto excede el saldo reembolsable"

Escenario: Reembolso sobre un pago no liquidado
  Dado un pago en estado "Autorizado"
  Cuando el operador intenta reembolsarlo
  Entonces el sistema sugiere anular la autorización en lugar de reembolsar"""

G_PUSH = """Escenario: Push de pago confirmado
  Dado un cliente con notificaciones habilitadas en la app
  Cuando su pago con tarjeta es confirmado por la pasarela
  Entonces recibe una notificación push en menos de 5 segundos con monto y comercio

Escenario: Cliente sin notificaciones habilitadas
  Dado un cliente con notificaciones deshabilitadas
  Cuando su pago es confirmado
  Entonces el evento queda registrado en la bandeja de la app sin enviar push"""

G_CONCILIACION = """Escenario: Exportación diaria exitosa
  Dado que el cierre del día D finalizó
  Cuando el analista de conciliación descarga el reporte del día D
  Entonces obtiene un CSV con todas las transacciones liquidadas y sus comisiones

Escenario: Cierre aún en proceso
  Dado que el cierre del día D no ha finalizado
  Cuando el analista intenta descargar el reporte
  Entonces el sistema muestra "Cierre en proceso" y la hora estimada de disponibilidad"""

G_LIMITE_QR = """Escenario: Transferencia QR dentro del límite
  Dado un cliente con límite diario QR de S/ 2,000.00 y consumo de S/ 500.00
  Cuando realiza una transferencia QR de S/ 300.00
  Entonces la transferencia se procesa y el consumo diario queda en S/ 800.00

Escenario: Transferencia QR que excede el límite
  Dado un cliente con consumo diario QR de S/ 1,900.00
  Cuando intenta transferir S/ 200.00
  Entonces la operación se rechaza y se ofrece aumentar el límite con token digital"""

G_SELFIE = """Escenario: Validación biométrica exitosa
  Dado un prospecto que inicia la apertura de cuenta desde la app
  Cuando captura su selfie y la foto de su DNI
  Entonces el sistema valida identidad con score mayor a 0.85 y continúa el onboarding

Escenario: Selfie con baja calidad
  Dado un prospecto que captura una selfie con poca luz
  Cuando el score de calidad es menor a 0.5
  Entonces la app solicita repetir la captura con indicaciones visuales"""

G_HOME = """Escenario: Home con ofertas personalizadas
  Dado un cliente con historial de consumo en la app
  Cuando abre la pantalla de inicio
  Entonces ve hasta 3 ofertas ordenadas por afinidad

Escenario: Cliente nuevo sin historial
  Dado un cliente sin historial
  Cuando abre la pantalla de inicio
  Entonces ve las ofertas generales de la campaña vigente"""

G_SCORING = """Escenario: Evaluación aprobada automáticamente
  Dado un solicitante con score interno mayor a 720
  Cuando solicita un préstamo personal menor a S/ 15,000
  Entonces el motor aprueba la solicitud sin revisión manual

Escenario: Evaluación derivada a analista
  Dado un solicitante con score entre 600 y 720
  Cuando solicita un préstamo personal
  Entonces el motor deriva la solicitud a la bandeja del analista con el detalle del score"""

G_REGULATORIO = """Escenario: Generación del anexo mensual
  Dado el cierre contable del mes M
  Cuando el analista de cumplimiento genera el anexo de créditos
  Entonces el sistema produce el archivo con el formato oficial y su hash de integridad"""


def _story(squad, key, title, *, epic=None, user_story="", gherkin="", points=None, assignee=None,
           status="refinement", approved_by=None, created_days=3, ai=False, open_questions=None, risks=None):
    return {
        "key": key,
        "squad": squad,
        "title": title,
        "user_story": user_story,
        "gherkin": gherkin,
        "epic_key": epic,
        "epic_confidence": 0.9 if epic else None,
        "points": points,
        "assignee": assignee,
        "status": status,
        "dor_approved_by": approved_by,
        "dor_approved_at": _ago(created_days - 1) if approved_by else None,
        "ai_generated": ai,
        "source": "seed",
        "created_at": _ago(created_days),
        "open_questions": open_questions or [],
        "risks": risks or [],
        "technical_notes": [],
        "jira_url": None,
    }


def _dep(squad, dep_id, story_key, req_id, name, dtype, area, owner, email, sla, critical, policy, days_ago,
         hours_ago=0, status="pending", escalated=False, reminders=0):
    return {
        "id": dep_id,
        "squad": squad,
        "story_key": story_key,
        "requirement_id": req_id,
        "name": name,
        "type": dtype,
        "owner_area": area,
        "owner_name": owner,
        "owner_email": email,
        "sla_days": sla,
        "critical": critical,
        "policy_ref": policy,
        "reason": "",
        "requested_at": _ago(days_ago, hours_ago),
        "status": status,
        "resolved_at": _ago(max(days_ago - 1.5, 0)) if status == "resolved" else None,
        "escalated": escalated,
        "reminders": reminders,
    }


DATA = {
    "pagos": {
        "epics": [
            ("PAG-E1", "Pagos Digitales Omnicanal", "Habilitar cobros con tarjeta, QR y billeteras en todos los canales del banco.",
             ["pago", "pasarela", "tarjeta", "checkout", "cobro", "qr", "billetera", "transaccion"], 46, "Rodrigo Salinas"),
            ("PAG-E2", "Conciliación y Liquidación Automática", "Eliminar la conciliación manual diaria con adquirentes.",
             ["conciliacion", "liquidacion", "cierre", "contable", "reporte", "comision"], 62, "Rodrigo Salinas"),
            ("PAG-E3", "Antifraude Transaccional", "Reducir el fraude en pagos digitales con reglas y scoring en línea.",
             ["fraude", "riesgo", "limite", "alerta", "3ds", "contracargo"], 23, "Martín Salas"),
            ("PAG-E4", "Experiencia Post-Pago", "Notificaciones, comprobantes y reembolsos sin fricción.",
             ["reembolso", "notificacion", "comprobante", "devolucion", "push"], 38, "Rodrigo Salinas"),
        ],
        "devs": [
            ("ana", "Ana Torres", "Backend Sr", 0.9), ("diego", "Diego Ríos", "Frontend", 0.8),
            ("luis", "Luis Herrera", "Backend", 0.9), ("valeria", "Valeria Campos", "QA Automation", 0.8),
            ("sofia", "Sofía Paredes", "Mobile", 0.8),
        ],
        "vacations": [("ana", 2, 8, "Vacaciones programadas"), ("sofia", 9, 11, "Día libre + feriado puente")],
        "stories": lambda: [
            _story("pagos", "PAG-131", "Reembolsos parciales desde backoffice", epic="PAG-E4",
                   user_story="Como operador de backoffice, quiero emitir reembolsos parciales sobre un pago liquidado, para resolver reclamos sin anular la venta completa.",
                   gherkin=G_REEMBOLSO, points=8, assignee="Ana Torres", status="planning", approved_by="Ana Torres", created_days=9, ai=True),
            _story("pagos", "PAG-134", "Push de pago confirmado", epic="PAG-E4",
                   user_story="Como cliente, quiero recibir una notificación push cuando mi pago se confirme, para tener certeza inmediata de la operación.",
                   gherkin=G_PUSH, points=3, assignee="Sofía Paredes", status="refinement", approved_by="Sofía Paredes", created_days=6, ai=True),
            _story("pagos", "PAG-137", "Exportar conciliación diaria en CSV", epic="PAG-E2",
                   user_story="Como analista de conciliación, quiero descargar el reporte diario en CSV, para cuadrar con el adquirente sin pedirlo a TI.",
                   gherkin=G_CONCILIACION, points=5, assignee="Luis Herrera", status="refinement", created_days=4, ai=True),
            _story("pagos", "PAG-138", "Límite diario de transferencias QR", epic="PAG-E3",
                   user_story="Como cliente, quiero un límite diario configurable para transferencias QR, para protegerme ante fraude.",
                   gherkin=G_LIMITE_QR, points=5, assignee="Ana Torres", status="refinement", approved_by="Ana Torres", created_days=7, ai=True),
            _story("pagos", "PAG-139", "Tokenización de tarjetas", assignee="Luis Herrera", created_days=11,
                   open_questions=["¿Proveedor de tokenización definido?"]),
            _story("pagos", "PAG-141", "Dashboard de rechazos de tarjeta", assignee="Diego Ríos", created_days=2, points=5),
        ],
        "deps": lambda: [
            _dep("pagos", "DEP-001", "PAG-138", "POL-ROP-005", "Conformidad de Riesgo Operacional — matriz de fraude", "conformidad",
                 "Riesgo Operacional", "Martín Salas", "martin.salas@banco.demo", 3, True,
                 "POL-ROP-005 · Riesgo operacional y prevención de fraude", 5, 3, escalated=True, reminders=2),
            _dep("pagos", "DEP-002", "PAG-138", "POL-DAT-007", "Acceso a BD QA (lectura/escritura esquema transaccional)", "acceso",
                 "DBA / Datos", "Lucía Ramos", "lucia.ramos@banco.demo", 2, True,
                 "POL-DAT-007 · Gestión de accesos a datos en ambientes no productivos", 1, 6),
            _dep("pagos", "DEP-003", "PAG-139", "DEF-NEG", "Definición de negocio: proveedor de tokenización", "definicion",
                 "Producto / Negocio", "Rodrigo Salinas", "rodrigo.salinas@banco.demo", 5, True,
                 "DoR · Definición funcional pendiente", 8, 2, escalated=True, reminders=3),
            _dep("pagos", "DEP-004", "PAG-134", "POL-INF-030", "Solicitud de ambiente / recurso de infraestructura", "ambiente",
                 "Plataforma Cloud", "Kevin Lozano", "kevin.lozano@banco.demo", 2, False,
                 "POL-INF-030 · Aprovisionamiento de ambientes y servicios", 1, 2),
            _dep("pagos", "DEP-005", "PAG-131", "POL-ROP-005", "Conformidad de Riesgo Operacional — matriz de fraude", "conformidad",
                 "Riesgo Operacional", "Martín Salas", "martin.salas@banco.demo", 3, True,
                 "POL-ROP-005 · Riesgo operacional y prevención de fraude", 6, status="resolved"),
        ],
        "baseline": {"historic_ai_refined": 34, "historic_notifications": 51, "historic_agendas": 9, "historic_deps": 17,
                     "incomplete_before_pct": 38, "ready_trend": [12, 17, 23, 28], "trend_labels": ["S20", "S21", "S22", "S23"]},
        "sprint_no": 24,
        "goal": "Habilitar pagos con pasarela externa y reducir reclamos post-pago",
    },
    "canales": {
        "epics": [
            ("APP-E1", "Onboarding Digital 100%", "Apertura de cuenta sin visitar agencia.",
             ["onboarding", "registro", "apertura", "cuenta", "biometria", "selfie", "dni"], 55, "Daniela Ortiz"),
            ("APP-E2", "Home Personalizada", "Pantalla de inicio con ofertas y accesos según el perfil del cliente.",
             ["home", "inicio", "oferta", "personalizacion", "campaña", "banner"], 30, "Daniela Ortiz"),
            ("APP-E3", "Seguridad y Acceso", "Login sin fricción y seguro: biometría, token digital y gestión de dispositivos.",
             ["login", "contrasena", "token", "2fa", "dispositivo", "sesion", "autenticacion"], 41, "Carla Mendoza"),
        ],
        "devs": [
            ("carlos", "Carlos Medina", "Mobile Sr", 0.9), ("lucia_d", "Lucía Fernández", "Mobile", 0.8),
            ("pedro", "Pedro Alarcón", "Backend", 0.9), ("maria", "María José León", "QA", 0.8),
        ],
        "vacations": [("carlos", 0, 4, "Vacaciones"), ("maria", 7, 7, "Capacitación")],
        "stories": lambda: [
            _story("canales", "APP-305", "Validación biométrica con selfie", epic="APP-E1",
                   user_story="Como prospecto, quiero validar mi identidad con una selfie y mi DNI, para abrir mi cuenta sin ir a una agencia.",
                   gherkin=G_SELFIE, points=8, assignee="Carlos Medina", status="refinement", approved_by="Carlos Medina", created_days=8, ai=True),
            _story("canales", "APP-309", "Ofertas personalizadas en home", epic="APP-E2",
                   user_story="Como cliente, quiero ver ofertas relevantes al abrir la app, para aprovechar beneficios sin buscarlos.",
                   gherkin=G_HOME, points=5, assignee="Lucía Fernández", status="planning", approved_by="Lucía Fernández", created_days=10, ai=True),
            _story("canales", "APP-312", "Cerrar sesión en otros dispositivos", epic="APP-E3",
                   user_story="Como cliente, quiero cerrar sesión remotamente en otros dispositivos, para proteger mi cuenta si pierdo mi celular.",
                   gherkin="Escenario: Cierre remoto\n  Dado un cliente con sesión activa en 2 dispositivos\n  Cuando cierra sesión en 'otros dispositivos'\n  Entonces las demás sesiones se invalidan en menos de 30 segundos",
                   points=3, assignee="Pedro Alarcón", status="refinement", created_days=3, ai=True),
            _story("canales", "APP-315", "Modo oscuro", assignee="Lucía Fernández", created_days=1),
            _story("canales", "APP-316", "Mejorar onboarding", assignee="Carlos Medina", created_days=5, points=8),
        ],
        "deps": lambda: [
            _dep("canales", "DEP-101", "APP-305", "POL-PRV-003", "Conformidad de Legal / Privacidad de datos", "conformidad",
                 "Legal / Privacidad", "Patricia Núñez", "patricia.nunez@banco.demo", 4, True,
                 "POL-PRV-003 · Protección de datos personales del cliente", 6, 1, escalated=True, reminders=2),
            _dep("canales", "DEP-102", "APP-312", "POL-SEG-020", "Conformidad de Ciberseguridad — pentest de autenticación", "conformidad",
                 "Ciberseguridad", "Carla Mendoza", "carla.mendoza@banco.demo", 3, True,
                 "POL-SEG-020 · Autenticación y gestión de identidades", 2, 4),
        ],
        "baseline": {"historic_ai_refined": 21, "historic_notifications": 33, "historic_agendas": 6, "historic_deps": 11,
                     "incomplete_before_pct": 42, "ready_trend": [6, 9, 13, 16], "trend_labels": ["S20", "S21", "S22", "S23"]},
        "sprint_no": 31,
        "goal": "Onboarding 100% digital en producción para el Black Friday",
    },
    "riesgos": {
        "epics": [
            ("RSK-E1", "Motor de Decisión Crediticia", "Automatizar la aprobación de préstamos personales.",
             ["credito", "scoring", "prestamo", "evaluacion", "motor", "decision", "buro"], 48, "Andrés Molina"),
            ("RSK-E2", "Reportería Regulatoria", "Generar automáticamente los anexos regulatorios mensuales.",
             ["regulatorio", "anexo", "reporte", "auditoria", "cumplimiento"], 35, "Silvia Herrera"),
        ],
        "devs": [
            ("jorge_r", "Jorge Ramírez", "Data Engineer", 0.9), ("elena", "Elena Vargas", "Backend Sr", 0.9),
            ("tomas", "Tomás Gutiérrez", "Data Scientist", 0.7),
        ],
        "vacations": [("elena", 5, 9, "Vacaciones")],
        "stories": lambda: [
            _story("riesgos", "RSK-071", "Aprobación automática de préstamos personales", epic="RSK-E1",
                   user_story="Como analista de créditos, quiero que el motor apruebe automáticamente las solicitudes de bajo riesgo, para enfocarme en los casos complejos.",
                   gherkin=G_SCORING, points=13, assignee="Elena Vargas", status="refinement", approved_by="Elena Vargas", created_days=9, ai=True),
            _story("riesgos", "RSK-074", "Anexo mensual de créditos", epic="RSK-E2",
                   user_story="Como analista de cumplimiento, quiero generar el anexo mensual de créditos desde el sistema, para evitar armarlo en Excel.",
                   gherkin=G_REGULATORIO, points=5, assignee="Jorge Ramírez", status="planning", approved_by="Jorge Ramírez", created_days=12, ai=True),
            _story("riesgos", "RSK-076", "Consulta a buró externo", assignee="Tomás Gutiérrez", created_days=4),
        ],
        "deps": lambda: [
            _dep("riesgos", "DEP-201", "RSK-071", "POL-DAT-007", "Acceso a BD QA (lectura/escritura esquema transaccional)", "acceso",
                 "DBA / Datos", "Lucía Ramos", "lucia.ramos@banco.demo", 2, True,
                 "POL-DAT-007 · Gestión de accesos a datos en ambientes no productivos", 3, 5, escalated=True, reminders=1),
        ],
        "baseline": {"historic_ai_refined": 15, "historic_notifications": 22, "historic_agendas": 4, "historic_deps": 8,
                     "incomplete_before_pct": 35, "ready_trend": [10, 15, 21, 26], "trend_labels": ["S20", "S21", "S22", "S23"]},
        "sprint_no": 18,
        "goal": "Primer piloto del motor de decisión con 20% del flujo",
    },
}


def seed() -> None:
    store.init()
    for sq in load_squads():
        sid = sq["id"]
        data = DATA.get(sid)
        store.put("squads", sid, {**sq, "squad_name": sq["squad"], "squad": sid}, squad=sid)
        store.set_counter(f"story:{sid}", sq.get("story_seq_start", 100) - 1)
        if not data:
            continue
        for key, title, objective, kws, progress, owner in data["epics"]:
            store.put("epics", key, {"key": key, "squad": sid, "title": title, "objective": objective,
                                     "keywords": kws, "status": "En curso", "progress": progress, "owner": owner})
        for dev_id, name, role, ppd in data["devs"]:
            initials = "".join(p[0] for p in name.split()[:2]).upper()
            store.put("devs", f"{sid}:{dev_id}", {"id": f"{sid}:{dev_id}", "squad": sid, "name": name, "role": role,
                                                  "initials": initials, "points_per_day": ppd})
        for i, (dev_id, start, end, note) in enumerate(data["vacations"]):
            vid = f"VAC-{sid}-{i + 1}"
            store.put("vacations", vid, {"id": vid, "squad": sid, "dev_id": f"{sid}:{dev_id}", "start": _d(start),
                                         "end": _d(end), "note": note})
        n = data["sprint_no"]
        store.put("sprints", f"{sid}:S{n}", {"id": f"{sid}:S{n}", "squad": sid, "name": f"Sprint {n}",
                                             "start": SPRINT_START.isoformat(), "end": SPRINT_END.isoformat(),
                                             "goal": data["goal"], "state": "next"})
        for st in data["stories"]():
            store.put("stories", st["key"], st)
        for dep in data["deps"]():
            store.put("dependencies", dep["id"], dep)
            _seed_notifications(dep)
        store.put("meta", f"kpi_baseline:{sid}", {"id": f"kpi_baseline:{sid}", **data["baseline"]}, squad=sid)
    store.set_counter("dep", 300)
    store.put("meta", "seeded", {"at": store.now_iso()})


def _seed_notifications(dep: dict) -> None:
    nid = f"N-{dep['id']}-a"
    store.put("notifications", nid, {
        "id": nid, "squad": dep["squad"], "channel": "teams", "kind": "solicitud",
        "to_name": dep["owner_name"], "to_area": dep["owner_area"], "to_email": dep["owner_email"],
        "title": f"Solicitud: {dep['name']}",
        "message": f"La historia {dep['story_key']} requiere tu {dep['type']} para entrar al sprint. Política: {dep['policy_ref']}.",
        "severity": "high" if dep["critical"] else "medium", "story_key": dep["story_key"], "dependency_id": dep["id"],
        "sent_at": dep["requested_at"], "delivery": "simulado", "read": True,
    })
    if dep.get("escalated"):
        nid = f"N-{dep['id']}-e"
        store.put("notifications", nid, {
            "id": nid, "squad": dep["squad"], "channel": "email", "kind": "escalamiento",
            "to_name": dep["owner_name"], "to_area": dep["owner_area"], "to_email": dep["owner_email"],
            "title": f"⚠ SLA vencido: {dep['name']}",
            "message": f"La solicitud para {dep['story_key']} superó su SLA de {dep['sla_days']} días. Se escala al Líder Técnico y a la jefatura del área.",
            "severity": "critical", "story_key": dep["story_key"], "dependency_id": dep["id"],
            "sent_at": _ago(0, 20), "delivery": "simulado", "read": True,
        })


def seed_if_empty() -> bool:
    store.init()
    if store.is_empty():
        seed()
        return True
    return False


def reset() -> None:
    store.init()
    store.wipe()
    seed()
