import { useState } from "react";
import { Monitor, Workflow, Brain, Plug, Database, ChevronRight, Activity, Copy, Check, Building2, ShieldCheck, Wrench } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../lib/ctx";
import { usePoll } from "../lib/hooks";
import { fmtAgo } from "../lib/format";
import { Badge, Card, CardHeader, Empty, LightDot, cx } from "../components/ui";

function Node({ icon: Icon, title, sub, status, tone }: any) {
  return (
    <div className="relative flex-1 rounded-2xl border border-slate-200 bg-white p-4 text-center shadow-sm">
      <div className={cx("mx-auto grid h-12 w-12 place-items-center rounded-xl text-white shadow", tone)}>
        <Icon className="h-6 w-6" />
      </div>
      <div className="mt-2 text-[13.5px] font-bold text-slate-900">{title}</div>
      <div className="mt-0.5 text-[11.5px] leading-snug text-slate-500">{sub}</div>
      <div className="mt-2 flex justify-center">{status}</div>
    </div>
  );
}

const Arrow = () => (
  <div className="hidden shrink-0 items-center text-slate-300 lg:flex">
    <div className="h-0.5 w-5 bg-gradient-to-r from-slate-200 to-slate-400" />
    <ChevronRight className="-ml-1.5 h-5 w-5" />
  </div>
);

function Status({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span className={cx("inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-[11px] font-semibold", ok ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700")}>
      <span className={cx("h-1.5 w-1.5 rounded-full", ok ? "bg-emerald-500" : "bg-amber-500")} />
      {label}
    </span>
  );
}

export default function Integrations() {
  const { health, squads, setSquad } = useApp();
  const { data: tools } = usePoll(() => api.get("/api/mcp/tools"), [], 0);
  const { data: log } = usePoll(() => api.get("/api/mcp/log?limit=30"), [], 3000);
  const { data: portfolio } = usePoll(() => api.get("/api/portfolio"), [], 8000);
  const { data: policies } = usePoll(() => api.get("/api/policies"), [], 0);
  const [copied, setCopied] = useState(false);

  const desktopCfg = JSON.stringify(
    { mcpServers: { "brujula-operativa": { command: "python", args: ["-m", "mcp_server.server", "--stdio"], cwd: "<ruta>/brujula-operativa" } } },
    null, 2
  );

  return (
    <div className="space-y-5">
      <Card className="p-6">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Arquitectura en vivo</h2>
            <p className="text-[13px] text-slate-500">Canal ➔ Orquestador ➔ IA ➔ MCP ➔ Sistemas · cada capa es reemplazable sin tocar las demás</p>
          </div>
          <Badge tone={health?.mode === "live" ? "green" : "violet"}>Modo {health?.mode === "live" ? "LIVE" : "DEMO"}</Badge>
        </div>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-stretch">
          <Node icon={Monitor} title="Canal web" sub="React + Tailwind · SSE en vivo" tone="bg-slate-800" status={<Status ok label="conectado" />} />
          <Arrow />
          <Node icon={Workflow} title="Orquestador" sub="FastAPI (Python) · Supervisor + gate DoR determinista" tone="bg-navy-900" status={<Status ok label=":8000" />} />
          <Arrow />
          <Node icon={Brain} title="Agentes IA" sub={health?.ai?.enabled ? `Claude ${health.ai.model} · effort ${health.ai.effort}` : "Motor offline de respaldo (sin API key)"} tone="bg-violet-600" status={<Status ok={!!health?.ai?.enabled} label={health?.ai?.enabled ? "Claude activo" : "respaldo offline"} />} />
          <Arrow />
          <Node icon={Plug} title="MCP Server" sub={`${health?.mcp?.tools ?? "…"} tools estandarizadas · streamable HTTP`} tone="bg-cyan-600" status={<Status ok={!!health?.mcp?.ok} label={health?.mcp?.ok ? ":8001/mcp" : "sin conexión"} />} />
          <Arrow />
          <Node
            icon={Database}
            title="Sistemas"
            sub="Jira · Microsoft Teams · Correo · Catálogo de políticas"
            tone="bg-emerald-600"
            status={
              <div className="flex flex-wrap justify-center gap-1">
                {["jira", "teams", "email"].map((s) => <Badge key={s} tone={health?.systems?.[s] === "live" ? "green" : "slate"}>{s}: {health?.systems?.[s] || "…"}</Badge>)}
              </div>
            }
          />
        </div>
      </Card>

      <div className="grid gap-5 xl:grid-cols-2">
        <Card>
          <CardHeader title="Tools del MCP Server" subtitle="Descubiertas en vivo con list_tools · las mismas que usan los agentes" icon={<Wrench className="h-4 w-4" />} right={<Badge tone="teams">{tools?.tools?.length || 0} tools</Badge>} />
          <div className="max-h-[420px] divide-y divide-slate-100 overflow-y-auto">
            {!tools && <Empty title="Cargando…" />}
            {tools && !tools.ok && <Empty title="MCP server no disponible" text={tools.error} />}
            {tools?.tools?.map((t: any) => (
              <div key={t.name} className="px-5 py-3">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[13px] font-semibold text-cyan-700">{t.name}</span>
                  <span className="text-[11px] text-slate-400">({Object.keys(t.input_schema?.properties || {}).join(", ")})</span>
                </div>
                <p className="mt-0.5 text-[12.5px] leading-relaxed text-slate-600">{t.description}</p>
              </div>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader title="Log de llamadas MCP en vivo" subtitle="Toda acción de los agentes sobre Jira/Teams queda auditada" icon={<Activity className="h-4 w-4" />} />
          <div className="max-h-[420px] overflow-y-auto font-mono text-[12px]">
            {!log?.length && <Empty title="Sin llamadas todavía" text="Ejecuta la Brújula IA para ver tráfico MCP." />}
            {log?.map((l: any) => (
              <div key={l.id} className="anim-in flex items-center gap-3 border-b border-slate-50 px-5 py-1.5">
                <span className={cx("h-1.5 w-1.5 shrink-0 rounded-full", l.ok ? "bg-emerald-500" : "bg-red-500")} />
                <span className="w-[200px] shrink-0 truncate font-semibold text-slate-700">{l.tool}</span>
                <span className="min-w-0 flex-1 truncate text-slate-400">{Object.entries(l.args || {}).map(([k, v]) => `${k}=${typeof v === "string" ? v : JSON.stringify(v)}`).join(" ")}</span>
                <span className="shrink-0 text-slate-400">{l.duration_ms}ms</span>
                <span className="w-20 shrink-0 text-right text-slate-400">{fmtAgo(l.ts)}</span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_420px]">
        <Card>
          <CardHeader title="Vista multi-tribu" subtitle="Mismo orquestador, mismos agentes, mismo MCP · onboarding de un squad = 1 bloque YAML" icon={<Building2 className="h-4 w-4" />} />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[640px] text-left text-[13px]">
              <thead>
                <tr className="text-[11px] font-bold uppercase tracking-wide text-slate-400">
                  <th className="py-2.5 pl-5">Tribu / Squad</th><th>Semáforo</th><th>% Ready</th><th>Bloqueos</th><th>Demora</th><th className="pr-5">Horas ahorradas</th>
                </tr>
              </thead>
              <tbody>
                {portfolio?.map((p: any) => (
                  <tr key={p.id} onClick={() => setSquad(p.id)} className="cursor-pointer border-t border-slate-100 hover:bg-slate-50">
                    <td className="py-3 pl-5">
                      <div className="flex items-center gap-2">
                        <span className="h-8 w-1.5 rounded-full" style={{ background: p.color }} />
                        <div><div className="font-semibold text-slate-800">{p.squad_name}</div><div className="text-[11.5px] text-slate-500">{p.tribu}</div></div>
                      </div>
                    </td>
                    <td>
                      <div className="flex items-center gap-2 text-[12.5px] font-semibold">
                        <span className="flex items-center gap-1"><LightDot light="red" />{p.counts.red}</span>
                        <span className="flex items-center gap-1"><LightDot light="yellow" />{p.counts.yellow}</span>
                        <span className="flex items-center gap-1"><LightDot light="green" />{p.counts.green}</span>
                      </div>
                    </td>
                    <td className="font-bold">{p.ready_pct}%</td>
                    <td>{p.pending_blockers}</td>
                    <td>{p.delay_days.toFixed(1)} d</td>
                    <td className="pr-5 font-bold text-blue-700">{p.hours_saved} h</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="border-t border-slate-100 px-5 py-3 text-[12px] text-slate-500">{squads.length} squads activos · catálogo corporativo compartido de {policies?.length || "…"} políticas</div>
        </Card>

        <div className="space-y-5">
          <Card>
            <CardHeader title="Conéctalo a Claude Desktop / IDE" subtitle="El mismo MCP server sirve a cualquier cliente MCP" icon={<Plug className="h-4 w-4" />}
              right={<button onClick={() => { navigator.clipboard?.writeText(desktopCfg); setCopied(true); setTimeout(() => setCopied(false), 1500); }} className="rounded-lg p-2 text-slate-400 hover:bg-slate-100">{copied ? <Check className="h-4 w-4 text-emerald-600" /> : <Copy className="h-4 w-4" />}</button>} />
            <pre className="overflow-x-auto bg-navy-950 px-5 py-4 font-mono text-[12px] leading-relaxed text-cyan-200">{desktopCfg}</pre>
          </Card>
          <Card>
            <CardHeader title="Catálogo de políticas" subtitle="config/politicas.yaml · el agente cita, no inventa" icon={<ShieldCheck className="h-4 w-4" />} />
            <div className="max-h-[260px] divide-y divide-slate-100 overflow-y-auto">
              {policies?.map((p: any) => (
                <div key={p.id} className="flex items-center justify-between gap-2 px-5 py-2">
                  <div className="min-w-0">
                    <div className="truncate text-[12.5px] font-semibold text-slate-700">{p.politica}</div>
                    <div className="font-mono text-[11px] text-slate-400">{p.id} · {p.area} · SLA {p.sla_dias}d</div>
                  </div>
                  {p.critica ? <Badge tone="red">Crítica</Badge> : <Badge>Normal</Badge>}
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
