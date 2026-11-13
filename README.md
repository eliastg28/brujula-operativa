# 🧭 Brújula Operativa

**SDLC sin fricción operativa, con agentes IA y MCP.** Las historias ya no llegan a las ceremonias con solo un título: una
*Brújula inteligente* las completa (épica, HU y criterios Gherkin), detecta las dependencias operativas (conformidades y
accesos), notifica a los owners y **bloquea** el paso a Planning hasta cumplir el Definition of Ready.

```
Canal (React) ➔ Orquestador (FastAPI) ➔ Agentes IA (Claude) ➔ MCP Server ➔ Sistemas (Jira · Teams · Correo · Políticas)
   :5173              :8000                                       :8001/mcp
```

## Arranque rápido (Windows)

```powershell
.\setup.ps1          # una sola vez: venv + pip + npm + .env
.\start.ps1          # levanta MCP :8001, Orquestador :8000 y Web :5173 y abre el navegador
.\start.ps1 -Reset   # igual, pero reinicia los datos de demo
```

Manual (3 terminales, desde la raíz):

```powershell
.\.venv\Scripts\python.exe -m mcp_server.server
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --port 8000
cd frontend; npm run dev
```

## Modos

| Variable (`.env`) | Efecto |
|---|---|
| sin nada | **Modo Demo**: Jira y Teams simulados con datos realistas; agentes con motor de respaldo offline |
| `ANTHROPIC_API_KEY` | Los agentes razonan con **Claude** (`claude-opus-5-5`, adaptive thinking, salidas estructuradas). Si Claude excede `AI_TIMEOUT`, ese agente cae al motor offline **con las mismas tools MCP**: la demo nunca se cae |
| `MODE=live` + `JIRA_*` | Crea historias y lee épicas en Jira Cloud real (REST v3); el store local queda como espejo |
| `MODE=live` + `TEAMS_WEBHOOK_URL` | Envía Adaptive Cards reales a Teams (webhook de *Workflows*) |
| `MODE=live` + `SMTP_*` | Envía los escalamientos por correo real |

## Guion de demo (3 min)

1. **Vista Ejecutiva** (`#/ejecutiva`): KPIs del header (horas ahorradas, % Ready, días muertos evitados, 0 % de HU incompletas en sprint) y el semáforo que reemplaza el Excel.
2. **Brújula IA** (`#/brujula`): escribir *"Integrar pasarela de pagos"*, **elegir la épica** (aparece como sugerida, un clic) y lanzar el análisis. En el **Agent Trace** se ve a los agentes trabajar en paralelo y cada llamada MCP. Atajo: `#/brujula/Integrar%20pasarela%20de%20pagos` precarga el título.
   Para mostrar la **creación rápida de épicas**, escribe *"Programa de lealtad con puntos"*: como ninguna épica coincide, la web ofrece **"Crear una nueva"**. Escribes el nombre, Enter, y la épica se crea en Jira vía MCP y queda seleccionada. Los agentes nunca crean épicas por su cuenta: solo validan la que eligió el usuario.
3. Resultado en 🔴: **Aprobar DoR** (dev) y luego **Mover a Planning** → ⛔ *423 Bloqueada por DoR* (siguen dependencias operativas pendientes).
4. **Teams / Correo** (campana o `#/inbox`): las tarjetas ya llegaron a Ciberseguridad, Arquitectura y DBA. Clic en **✓ Aprobar conformidad** como owner.
5. **Bloqueos** (`#/bloqueos`): contadores de demora en vivo, SLA vencidos escalados automáticamente y la espera por área.
6. Volver a la historia → 🟢 → **Mover a Planning** ✅.
7. **Capacidad**: registrar vacaciones que cruzan el sprint, ver la alerta de riesgo con sugerencia de reasignación y el aviso al LT por Teams.
8. **Ceremonias**: generar la agenda de Planning a partir del tablero real, agendarla y descargar el `.ics`.
9. **Selector de squad** (Pagos → Canales Digitales): todo cambia. **Arquitectura MCP**: tools descubiertas en vivo, log auditable y vista multi-tribu.

## Tools MCP (`mcp_server/server.py`)

| Tool | Qué hace |
|---|---|
| `get_active_epics` | Épicas activas del squad en Jira |
| `create_epic` | Crea una épica a pedido del usuario (creación rápida desde la web; idempotente por título) |
| `create_jira_story` | Crea la HU (Como/Quiero/Para + Gherkin + épica padre) |
| `check_access_policies` | Evalúa la historia contra `config/politicas.yaml` (PCI-DSS, Arquitectura, BD QA, Privacidad, Fraude…) |
| `register_dependency` | Registra la conformidad o el acceso pendiente e inicia el contador de SLA |
| `send_teams_notification` | Adaptive Card a Teams (o correo) para el owner |
| `get_backlog` / `update_story_status` | Backlog con semáforo DoR / transición protegida por el gate DoR |
| `get_pending_dependencies` | Bloqueos con días de demora |
| `get_team_calendar` / `schedule_ceremony` | Capacidad vs vacaciones / agenda de ceremonias con aviso en Teams |

Para usar el mismo servidor desde **Claude Desktop** o un IDE:

```json
{ "mcpServers": { "brujula-operativa": { "command": "python", "args": ["-m", "mcp_server.server", "--stdio"], "cwd": "<ruta>/brujula-operativa" } } }
```

## Estructura

```
config/          squads.yaml (onboarding de tribus) · politicas.yaml (catálogo de políticas)
core/            dominio compartido: store SQLite, motor DoR, capacidad, KPIs, seed de demo
mcp_server/      MCP Server + adapters Jira / Teams (mock y real)
backend/         Orquestador FastAPI · agents/ (supervisor, prompts, esquemas, Claude, respaldo offline) · ceremonias
frontend/        React + Vite + Tailwind (Vista Ejecutiva, Brújula, Bloqueos, Capacidad, Ceremonias, Arquitectura)
```

## Decisiones de diseño

- **El gate DoR es código determinista** (`core/dor.py`), no una decisión del LLM: es auditable y se aplica también si otro cliente MCP intenta mover la historia.
- **Los agentes citan el catálogo de políticas**, no inventan conformidades. Agregar una política es editar un YAML.
- **Agregar un squad** es un bloque en `config/squads.yaml`. Agregar un sistema (ServiceNow, Azure DevOps) es un adapter MCP nuevo; orquestador, agentes y UI no cambian.
- **Los KPIs muestran su fórmula** (ícono ⓘ) con supuestos explícitos y configurables en `core/domain.py`.
