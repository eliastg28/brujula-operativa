import { useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import { Hourglass, AlertTriangle, Users, Bell, ExternalLink, CheckCircle2, ShieldAlert, KeyRound, Server, FileQuestion } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../lib/ctx";
import { usePoll, useNow } from "../lib/hooks";
import { elapsedParts, fmtAgo } from "../lib/format";
import DelayCounter from "../components/DelayCounter";
import { Avatar, Badge, Button, Card, CardHeader, Empty, Loading, cx } from "../components/ui";

const TYPE_ICON: Record<string, any> = { conformidad: ShieldAlert, acceso: KeyRound, ambiente: Server, definicion: FileQuestion };

function Row({ d, reload }: { d: any; reload: () => void }) {
  const { openStory, toast, bump } = useApp();
  const [busy, setBusy] = useState<string | null>(null);
  const Icon = TYPE_ICON[d.type] || ShieldAlert;
  async function act(kind: "remind" | "resolve") {
    setBusy(kind);
    try {
      if (kind === "remind") {
        await api.post(`/api/dependencies/${d.id}/remind`);
        toast({ tone: "teams", title: `Recordatorio enviado a ${d.owner_name}`, body: `${d.name} · vía MCP → Teams` });
      } else {
        await api.post(`/api/dependencies/${d.id}/resolve`, { by: d.owner_name });
        toast({ tone: "ok", title: `${d.owner_area} aprobó`, body: `${d.story_key} se acerca al DoR` });
      }
      reload();
      bump();
    } finally {
      setBusy(null);
    }
  }
  return (
    <tr className="anim-in border-t border-slate-100 align-middle hover:bg-slate-50/60">
      <td className="py-3 pl-5 pr-3">
        <div className="flex items-start gap-3">
          <div className={cx("mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl", d.critical ? "bg-red-50 text-red-600" : "bg-amber-50 text-amber-600")}>
            <Icon className="h-[18px] w-[18px]" />
          </div>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="text-[13.5px] font-semibold text-slate-800">{d.name}</span>
              {d.critical && <Badge tone="red">Crítica</Badge>}
              {d.escalated && <Badge tone="red">Escalada</Badge>}
              {d.reminders > 0 && <Badge tone="slate">{d.reminders} recordatorio{d.reminders > 1 ? "s" : ""}</Badge>}
            </div>
            <div className="mt-0.5 font-mono text-[11px] text-slate-400">{d.policy_ref}</div>
          </div>
        </div>
      </td>
      <td className="px-3 py-3">
        <button onClick={() => openStory(d.story_key)} className="text-left">
          <div className="font-mono text-[12px] font-semibold text-blue-600 hover:underline">{d.story_key}</div>
          <div className="max-w-[220px] truncate text-[12.5px] text-slate-600">{d.story_title}</div>
        </button>
      </td>
      <td className="px-3 py-3">
        <div className="flex items-center gap-2">
          <Avatar name={d.owner_name} size={28} />
          <div>
            <div className="text-[13px] font-semibold text-slate-700">{d.owner_name}</div>
            <div className="text-[11.5px] text-slate-500">{d.owner_area}</div>
          </div>
        </div>
      </td>
      <td className="px-3 py-3"><DelayCounter dep={d} /></td>
      <td className="py-3 pl-3 pr-5 text-right">
        <div className="flex justify-end gap-1.5">
          <Button size="sm" variant="secondary" onClick={() => act("remind")} loading={busy === "remind"}><Bell className="h-3.5 w-3.5" />Recordar</Button>
          <Button size="sm" variant="success" onClick={() => act("resolve")} loading={busy === "resolve"}>Resolver</Button>
        </div>
      </td>
    </tr>
  );
}

export default function Blockers() {
  const { squad, tick } = useApp();
  const now = useNow();
  const { data, reload } = usePoll(() => api.get(`/api/blockers?squad=${squad}`), [squad, tick], 6000);
  if (!data) return <Loading />;
  const pending = data.pending;
  const liveTotal = pending.reduce((acc: number, d: any) => acc + elapsedParts(d.requested_at, now).totalDays, 0);
  const totalHours = liveTotal * 24;
  const areas = data.by_area;

  return (
    <div className="space-y-5">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card className="bg-gradient-to-br from-navy-900 to-navy-700 p-5 text-white md:col-span-2 xl:col-span-1">
          <div className="flex items-center gap-2 text-[12px] font-bold uppercase tracking-wide text-slate-300"><Hourglass className="h-4 w-4" />Demora operativa acumulada</div>
          <div className="mt-2 font-mono text-[34px] font-bold tabular-nums leading-none">{liveTotal.toFixed(2)}<span className="ml-1 text-lg text-slate-300">días</span></div>
          <div className="mt-1.5 text-[12.5px] text-slate-300">≈ {Math.round(totalHours)} horas-persona esperando · contador en tiempo real</div>
        </Card>
        <Card className="p-5">
          <div className="flex items-center gap-2 text-[12px] font-bold uppercase tracking-wide text-slate-500"><AlertTriangle className="h-4 w-4 text-amber-500" />Pendientes</div>
          <div className="mt-2 text-[34px] font-extrabold leading-none text-slate-900">{pending.length}</div>
          <div className="mt-1.5 text-[12.5px] text-slate-500">{pending.filter((d: any) => d.critical).length} críticas bloquean el DoR</div>
        </Card>
        <Card className="p-5">
          <div className="flex items-center gap-2 text-[12px] font-bold uppercase tracking-wide text-slate-500"><AlertTriangle className="h-4 w-4 text-red-500" />SLA vencidos</div>
          <div className="mt-2 text-[34px] font-extrabold leading-none text-red-600">{data.overdue}</div>
          <div className="mt-1.5 text-[12.5px] text-slate-500">Escalados automáticamente al LT y jefaturas</div>
        </Card>
        <Card className="p-5">
          <div className="flex items-center gap-2 text-[12px] font-bold uppercase tracking-wide text-slate-500"><CheckCircle2 className="h-4 w-4 text-emerald-500" />Resueltas recientes</div>
          <div className="mt-2 text-[34px] font-extrabold leading-none text-emerald-600">{data.resolved.length}</div>
          <div className="mt-1.5 truncate text-[12.5px] text-slate-500">{data.resolved[0] ? `Última: ${data.resolved[0].owner_area} ${fmtAgo(data.resolved[0].resolved_at)}` : "—"}</div>
        </Card>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_340px]">
        <Card className="overflow-hidden">
          <CardHeader title="Dashboard de bloqueos" subtitle="Cada definición, acceso o conformidad pendiente con su contador de demora en vivo" icon={<Hourglass className="h-4 w-4" />} />
          {pending.length === 0 ? (
            <Empty icon={<CheckCircle2 className="h-10 w-10" />} title="Sin bloqueos pendientes 🎉" text="Todas las conformidades y accesos del squad están resueltos." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] text-left">
                <thead>
                  <tr className="text-[11px] font-bold uppercase tracking-wide text-slate-400">
                    <th className="py-2.5 pl-5 pr-3">Dependencia</th>
                    <th className="px-3 py-2.5">Historia</th>
                    <th className="px-3 py-2.5">Owner</th>
                    <th className="px-3 py-2.5">Demora en vivo</th>
                    <th className="py-2.5 pl-3 pr-5 text-right">Acciones</th>
                  </tr>
                </thead>
                <tbody>{pending.map((d: any) => <Row key={d.id} d={d} reload={reload} />)}</tbody>
              </table>
            </div>
          )}
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader title="¿Dónde se va el tiempo?" subtitle="Días de espera acumulados por área" icon={<Users className="h-4 w-4" />} />
            <div className="h-[240px] px-2 py-3">
              {areas.length ? (
                <ResponsiveContainer>
                  <BarChart data={areas} layout="vertical" margin={{ left: 8, right: 24 }}>
                    <XAxis type="number" hide />
                    <YAxis type="category" dataKey="area" width={120} tick={{ fontSize: 11.5, fill: "#475569" }} axisLine={false} tickLine={false} />
                    <Tooltip formatter={(v: any) => [`${v} días`, "Espera"]} contentStyle={{ borderRadius: 12, fontSize: 12 }} />
                    <Bar dataKey="days" radius={[0, 6, 6, 0]} barSize={18}>
                      {areas.map((_: any, i: number) => <Cell key={i} fill={i === 0 ? "#dc2626" : i === 1 ? "#f59e0b" : "#3b82f6"} />)}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : <Empty title="Sin esperas" />}
            </div>
          </Card>
          <Card>
            <CardHeader title="Resueltas" subtitle="Tiempo real de respuesta por área" icon={<CheckCircle2 className="h-4 w-4 text-emerald-600" />} />
            <div className="divide-y divide-slate-100">
              {data.resolved.length === 0 && <Empty title="Aún no hay resueltas" />}
              {data.resolved.map((d: any) => (
                <div key={d.id} className="flex items-center justify-between gap-2 px-5 py-2.5">
                  <div className="min-w-0">
                    <div className="truncate text-[13px] font-semibold text-slate-700">{d.owner_area}</div>
                    <div className="truncate text-[11.5px] text-slate-500">{d.story_key} · {d.name}</div>
                  </div>
                  <Badge tone={d.age_days > d.sla_days ? "red" : "green"}>{d.age_days.toFixed(1)} d</Badge>
                </div>
              ))}
            </div>
          </Card>
          <a href="#/integraciones" className="flex items-center gap-1 px-1 text-[12px] text-slate-400 hover:text-slate-600">
            Las notificaciones salen por la tool MCP send_teams_notification <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </div>
    </div>
  );
}
