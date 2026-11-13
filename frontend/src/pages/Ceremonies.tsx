import { useState } from "react";
import { Sun, ClipboardList, Sparkles, RefreshCcw, CalendarPlus, Download, Clock, Users, Plug, Bot } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../lib/ctx";
import { usePoll } from "../lib/hooks";
import { fmtDate } from "../lib/format";
import { Badge, Button, Card, CardHeader, Empty, cx } from "../components/ui";

const TYPES = [
  { id: "daily", label: "Daily", icon: Sun, desc: "15 min · bloqueos con contador, SLA vencidos, ausencias", color: "from-amber-400 to-orange-500" },
  { id: "planning", label: "Sprint Planning", icon: ClipboardList, desc: "Solo entra lo que pasa el DoR · capacidad real", color: "from-blue-500 to-indigo-600" },
  { id: "refinamiento", label: "Refinamiento", icon: Sparkles, desc: "Historias sin épica, sin Gherkin o sin OK del dev", color: "from-violet-500 to-fuchsia-600" },
  { id: "retro", label: "Retrospectiva", icon: RefreshCcw, desc: "Datos de demora por área, no opiniones", color: "from-emerald-500 to-teal-600" },
];

export default function Ceremonies() {
  const { squad, tick, toast, bump } = useApp();
  const [agenda, setAgenda] = useState<any>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const [scheduling, setScheduling] = useState(false);
  const { data: scheduled, reload } = usePoll(() => api.get(`/api/ceremonies?squad=${squad}`), [squad, tick], 0);

  async function generate(type: string) {
    setLoading(type);
    try {
      setAgenda(await api.post("/api/ceremonies/generate", { squad, type }));
    } catch (e: any) {
      toast({ tone: "error", title: "No se pudo generar", body: e.message });
    } finally {
      setLoading(null);
    }
  }

  async function schedule() {
    setScheduling(true);
    try {
      const r = await api.post("/api/ceremonies/schedule", {
        squad, type: agenda.type, date: agenda.date, time: agenda.time, duration: agenda.duration,
        blocks: agenda.blocks, summary: agenda.summary, attendees: agenda.attendees,
      });
      toast({ tone: "teams", title: `${agenda.label} agendada`, body: `Invitación publicada en el canal del squad (${r.delivery})` });
      reload();
      bump();
    } finally {
      setScheduling(false);
    }
  }

  const totalMin = agenda?.blocks.reduce((a: number, b: any) => a + b.minutes, 0) || 0;

  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {TYPES.map((t) => (
          <button key={t.id} onClick={() => generate(t.id)} disabled={!!loading} className={cx("group rounded-2xl border bg-white p-5 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:shadow-md disabled:opacity-60", agenda?.type === t.id ? "border-navy-700 ring-2 ring-navy-200" : "border-slate-200")}>
            <div className={cx("grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br text-white shadow", t.color)}>
              <t.icon className="h-5 w-5" />
            </div>
            <div className="mt-3 text-[15px] font-bold text-slate-900">{t.label}</div>
            <div className="mt-0.5 text-[12.5px] text-slate-500">{t.desc}</div>
            <div className="mt-3 text-[12.5px] font-semibold text-navy-700 group-hover:underline">{loading === t.id ? "El agente está armando la agenda…" : "Generar agenda con datos reales →"}</div>
          </button>
        ))}
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_340px]">
        <Card>
          {!agenda ? (
            <Empty icon={<ClipboardList className="h-12 w-12" />} title="Elige una ceremonia" text="El Agente de Ceremonias consulta el tablero, los bloqueos y el calendario vía MCP y arma la agenda en segundos." />
          ) : (
            <div className="anim-in">
              <CardHeader
                title={`${agenda.label} · ${fmtDate(agenda.date, true)} ${agenda.time}`}
                subtitle={`${agenda.duration} min programados · ${totalMin} min de agenda · ${agenda.attendees.length} participantes`}
                icon={<CalendarPlus className="h-4 w-4" />}
                right={<Button variant="teams" onClick={schedule} loading={scheduling}><CalendarPlus className="h-4 w-4" />Agendar y notificar</Button>}
              />
              <div className="border-b border-slate-100 bg-gradient-to-r from-violet-50 to-blue-50 px-5 py-4">
                <div className="flex items-center gap-2 text-[12px] font-bold uppercase tracking-wide text-violet-700">
                  <Bot className="h-4 w-4" /> Resumen ejecutivo para abrir la ceremonia
                  <Badge tone={agenda.engine === "claude" ? "violet" : "slate"}>{agenda.engine === "claude" ? "Claude" : "reglas"}</Badge>
                </div>
                <ul className="mt-2 space-y-1">
                  {agenda.summary.map((s: string, i: number) => (
                    <li key={i} className="flex gap-2 text-[13.5px] font-medium text-slate-800"><span className="font-bold text-violet-600">{i + 1}.</span>{s}</li>
                  ))}
                </ul>
              </div>
              <div className="divide-y divide-slate-100">
                {agenda.blocks.map((b: any, i: number) => (
                  <div key={i} className="flex gap-4 px-5 py-4">
                    <div className="w-16 shrink-0">
                      <div className="flex items-center gap-1 text-[13px] font-bold text-slate-700"><Clock className="h-3.5 w-3.5 text-slate-400" />{b.minutes}′</div>
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-[14px] font-bold text-slate-900">{b.title}</div>
                      <ul className="mt-1.5 space-y-1">
                        {b.items.map((it: string, j: number) => (
                          <li key={j} className="flex gap-2 text-[13px] text-slate-600"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-300" />{it}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                ))}
              </div>
              <div className="flex flex-wrap items-center gap-3 border-t border-slate-100 px-5 py-3 text-[11.5px] text-slate-500">
                <Plug className="h-3.5 w-3.5 text-cyan-600" /> Datos obtenidos vía MCP:
                {agenda.mcp_trace.map((t: any) => <span key={t.tool} className="font-mono">{t.tool} ({t.ms} ms)</span>)}
                <span className="ml-auto flex items-center gap-1"><Users className="h-3.5 w-3.5" />{agenda.attendees.join(", ")}</span>
              </div>
            </div>
          )}
        </Card>

        <Card>
          <CardHeader title="Ceremonias agendadas" subtitle="Con invitación .ics y aviso en Teams" icon={<CalendarPlus className="h-4 w-4" />} />
          <div className="divide-y divide-slate-100">
            {!scheduled?.length && <Empty title="Aún no hay ceremonias" text="Genera una agenda y agéndala." />}
            {scheduled?.map((c: any) => (
              <div key={c.id} className="flex items-center justify-between gap-2 px-5 py-3">
                <div>
                  <div className="text-[13.5px] font-semibold text-slate-800">{c.label || c.type}</div>
                  <div className="text-[12px] text-slate-500">{fmtDate(c.date, true)} · {c.time} · {c.duration} min</div>
                </div>
                <a href={`/api/ceremonies/${c.id}/ics`} className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2 py-1 text-[12px] font-semibold text-slate-600 hover:bg-slate-50">
                  <Download className="h-3.5 w-3.5" />.ics
                </a>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
