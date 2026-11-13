import { PieChart, Pie, Cell, ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, CartesianGrid } from "recharts";
import { AlertOctagon, CalendarX2, TimerOff, TrendingUp, Activity, FileSpreadsheet } from "lucide-react";
import StoryCard from "../components/StoryCard";
import { Card, CardHeader, Empty, LIGHT, LightDot, Loading, Badge, cx } from "../components/ui";
import { fmtCounter } from "../lib/format";
import { useNow } from "../lib/hooks";

const COLS = [
  { light: "red", title: "Bloqueadas", sub: "Falta épica, criterios o dependencias operativas" },
  { light: "yellow", title: "En refinamiento", sub: "Completas · falta OK del dev" },
  { light: "green", title: "Ready / Planning", sub: "Pasan el Definition of Ready" },
] as const;

const PIE_COLORS = { red: "#ef4444", yellow: "#fbbf24", green: "#10b981" };

export default function Executive({ dash }: { dash: any }) {
  const now = useNow();
  if (!dash) return <Loading />;
  const board = dash.board;
  const counts = dash.kpis.counts;
  const pie = (["red", "yellow", "green"] as const).map((k) => ({ name: LIGHT[k].label, value: counts[k], key: k }));
  const total = board.length;
  const trend = dash.kpis.ready_trend.map((v: number, i: number) => ({ s: dash.kpis.sprint_labels[i] || "Hoy", v }));
  const overdueTop = dash.blockers.top.filter((d: any) => d.sla_status === "overdue");

  return (
    <div className="grid gap-5 xl:grid-cols-[1fr_360px]">
      {/* Semáforo */}
      <div className="min-w-0">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 className="text-lg font-bold text-slate-900">Semáforo del backlog</h2>
            <p className="text-[13px] text-slate-500">Reemplaza el Excel del LT · se actualiza solo con cada cambio en Jira, Teams o la Brújula</p>
          </div>
          <Badge tone="slate"><FileSpreadsheet className="h-3 w-3" />0 Excels manuales</Badge>
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          {COLS.map((c) => {
            const items = board.filter((s: any) => s.dor.light === c.light);
            const L = LIGHT[c.light];
            return (
              <div key={c.light} className={cx("flex min-h-[420px] flex-col rounded-2xl p-3 ring-1 ring-inset", L.bg, L.ring)}>
                <div className="mb-3 flex items-center justify-between px-1">
                  <div className="flex items-center gap-2">
                    <LightDot light={c.light} size={12} pulse={c.light === "red" && items.length > 0} />
                    <div>
                      <div className={cx("text-[14px] font-bold", L.text)}>{c.title}</div>
                      <div className="text-[11.5px] text-slate-500">{c.sub}</div>
                    </div>
                  </div>
                  <span className={cx("grid h-8 min-w-8 place-items-center rounded-lg bg-white px-2 text-[15px] font-extrabold shadow-sm", L.text)}>{items.length}</span>
                </div>
                <div className="flex-1 space-y-2.5">
                  {items.length === 0 ? <Empty title="Nada por aquí" /> : items.map((s: any) => <StoryCard key={s.key} story={s} />)}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Panel lateral del LT */}
      <div className="space-y-4">
        <Card>
          <CardHeader title="Salud del backlog" subtitle={`${total} historias abiertas`} icon={<Activity className="h-4 w-4" />} />
          <div className="flex items-center gap-2 px-4 py-3">
            <div className="h-[130px] w-[130px] shrink-0">
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={pie} dataKey="value" innerRadius={40} outerRadius={60} paddingAngle={3} stroke="none" isAnimationActive>
                    {pie.map((p) => <Cell key={p.key} fill={PIE_COLORS[p.key]} />)}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="flex-1 space-y-2">
              {pie.map((p) => (
                <div key={p.key} className="flex items-center justify-between text-[13px]">
                  <span className="flex items-center gap-2 text-slate-600"><LightDot light={p.key} />{p.name}</span>
                  <span className="font-bold tabular-nums text-slate-800">{p.value} <span className="font-medium text-slate-400">· {total ? Math.round((p.value / total) * 100) : 0}%</span></span>
                </div>
              ))}
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader title="Evolución % Ready por sprint" subtitle="Antes de Brújula vs ahora" icon={<TrendingUp className="h-4 w-4" />} />
          <div className="h-[150px] px-2 py-3">
            <ResponsiveContainer>
              <LineChart data={trend} margin={{ top: 8, right: 16, left: -18, bottom: 0 }}>
                <CartesianGrid stroke="#f1f5f9" vertical={false} />
                <XAxis dataKey="s" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} unit="%" />
                <Tooltip formatter={(v: any) => [`${v}%`, "Ready"]} contentStyle={{ borderRadius: 12, fontSize: 12 }} />
                <Line type="monotone" dataKey="v" stroke="#10b981" strokeWidth={3} dot={{ r: 4, fill: "#10b981" }} activeDot={{ r: 6 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <CardHeader title="Alertas para el LT" subtitle="Riesgos que evitan fallos y retrabajo" icon={<AlertOctagon className="h-4 w-4 text-red-600" />} />
          <div className="space-y-2.5 p-4">
            {dash.capacity_alerts.map((a: any) => (
              <a key={a.dev_id} href="#/capacidad" className="block rounded-xl border border-amber-200 bg-amber-50 p-3 hover:border-amber-300">
                <div className="flex items-center gap-2 text-[13px] font-bold text-amber-900"><CalendarX2 className="h-4 w-4" />{a.title}</div>
                <div className="mt-0.5 text-[12px] text-amber-800">{a.message}</div>
                {a.suggestion && <div className="mt-1 text-[12px] font-semibold text-amber-900">💡 {a.suggestion}</div>}
              </a>
            ))}
            {overdueTop.map((d: any) => (
              <a key={d.id} href="#/bloqueos" className="block rounded-xl border border-red-200 bg-red-50 p-3 hover:border-red-300">
                <div className="flex items-center gap-2 text-[13px] font-bold text-red-800"><TimerOff className="h-4 w-4" />SLA vencido · {d.owner_area}</div>
                <div className="mt-0.5 text-[12px] text-red-700">{d.story_key}: {d.name}</div>
                <div className="mt-1 font-mono text-[13px] font-semibold text-red-700">{fmtCounter(d.requested_at, now)}</div>
              </a>
            ))}
            {dash.capacity_alerts.length === 0 && overdueTop.length === 0 && <Empty title="Sin alertas activas" />}
          </div>
        </Card>
      </div>
    </div>
  );
}
