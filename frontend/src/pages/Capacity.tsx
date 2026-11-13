import { useState } from "react";
import { CalendarDays, Palmtree, AlertTriangle, Plus, Trash2, Lightbulb, Users } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../lib/ctx";
import { usePoll } from "../lib/hooks";
import { dayName, fmtDate } from "../lib/format";
import { Avatar, Badge, Button, Card, CardHeader, Empty, Loading, cx } from "../components/ui";

const RISK: Record<string, { tone: string; label: string; bar: string }> = {
  high: { tone: "red", label: "Riesgo alto", bar: "bg-red-500" },
  medium: { tone: "amber", label: "Riesgo medio", bar: "bg-amber-400" },
  low: { tone: "blue", label: "Atento", bar: "bg-blue-500" },
  none: { tone: "green", label: "OK", bar: "bg-emerald-500" },
};

export default function Capacity() {
  const { squad, tick, toast, bump } = useApp();
  const { data, reload } = usePoll(() => api.get(`/api/capacity?squad=${squad}`), [squad, tick], 0);
  const [form, setForm] = useState({ dev_id: "", start: "", end: "", note: "Vacaciones" });
  const [saving, setSaving] = useState(false);

  if (!data) return <Loading />;
  if (!data.sprint) return <Empty title="Sin sprint configurado" />;
  const days: string[] = data.days;

  async function save() {
    if (!form.dev_id || !form.start || !form.end) return toast({ tone: "error", title: "Completa dev y fechas" });
    setSaving(true);
    try {
      const r = await api.post("/api/vacations", { squad, ...form });
      if (r.new_alert) toast({ tone: "warn", title: `⚠ ${r.new_alert.title}`, body: `${r.new_alert.message} Se notificó al LT por Teams.` });
      else toast({ tone: "ok", title: "Vacaciones registradas", body: "Sin impacto en la capacidad del sprint." });
      setForm({ ...form, start: "", end: "" });
      await reload();
      bump();
    } catch (e: any) {
      toast({ tone: "error", title: "No se pudo registrar", body: e.message });
    } finally {
      setSaving(false);
    }
  }

  async function removeVacation(id: string) {
    await api.del(`/api/vacations/${id}`);
    await reload();
    bump();
  }

  const loadPct = data.team_capacity ? Math.round((data.team_assigned / data.team_capacity) * 100) : 0;

  return (
    <div className="space-y-5">
      {data.alerts.length > 0 && (
        <div className="space-y-2">
          {data.alerts.map((a: any) => (
            <div key={a.dev_id} className={cx("anim-in flex flex-wrap items-center gap-3 rounded-2xl border-2 px-5 py-3.5", a.severity === "high" ? "border-red-300 bg-red-50" : "border-amber-300 bg-amber-50")}>
              <AlertTriangle className={cx("h-6 w-6 shrink-0", a.severity === "high" ? "text-red-600" : "text-amber-600")} />
              <div className="min-w-0 flex-1">
                <div className={cx("text-[14px] font-bold", a.severity === "high" ? "text-red-800" : "text-amber-900")}>{a.title}</div>
                <div className="text-[13px] text-slate-700">{a.message}</div>
              </div>
              {a.suggestion && (
                <div className="flex items-center gap-2 rounded-xl bg-white px-3 py-2 text-[12.5px] font-semibold text-slate-700 shadow-sm">
                  <Lightbulb className="h-4 w-4 text-amber-500" />{a.suggestion}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-[1fr_320px]">
        <Card className="overflow-hidden">
          <CardHeader
            title={`Calendario de vacaciones vs ${data.sprint.name}`}
            subtitle={`${fmtDate(data.sprint.start, true)} → ${fmtDate(data.sprint.end, true)} · ${days.length} días hábiles · objetivo: ${data.sprint.goal}`}
            icon={<CalendarDays className="h-4 w-4" />}
            right={<Badge tone={loadPct > 100 ? "red" : loadPct > 85 ? "amber" : "green"}>Equipo {data.team_assigned}/{data.team_capacity} pts · {loadPct}%</Badge>}
          />
          <div className="overflow-x-auto">
            <table className="w-full min-w-[960px] border-collapse">
              <thead>
                <tr>
                  <th className="sticky left-0 z-10 bg-white py-2.5 pl-5 pr-3 text-left text-[11px] font-bold uppercase tracking-wide text-slate-400">Dev</th>
                  {days.map((d, i) => (
                    <th key={d} className={cx("px-1 py-2 text-center", i === 5 && "border-l-2 border-slate-200")}>
                      <div className="text-[10.5px] font-semibold uppercase text-slate-400">{dayName(d)}</div>
                      <div className="text-[12.5px] font-bold text-slate-700">{fmtDate(d)}</div>
                    </th>
                  ))}
                  <th className="px-4 py-2 text-left text-[11px] font-bold uppercase tracking-wide text-slate-400">Carga</th>
                </tr>
              </thead>
              <tbody>
                {data.devs.map((dev: any) => {
                  const r = RISK[dev.risk];
                  const vac = new Set(dev.vacation_days);
                  return (
                    <tr key={dev.id} className="border-t border-slate-100">
                      <td className="sticky left-0 z-10 bg-white py-2.5 pl-5 pr-3">
                        <div className="flex items-center gap-2.5">
                          <Avatar name={dev.name} size={32} />
                          <div className="min-w-0">
                            <div className="truncate text-[13px] font-semibold text-slate-800">{dev.name}</div>
                            <div className="text-[11.5px] text-slate-500">{dev.role}</div>
                          </div>
                        </div>
                      </td>
                      {days.map((d, i) => {
                        const isVac = vac.has(d);
                        const conflict = isVac && dev.assigned_pts > 0;
                        return (
                          <td key={d} className={cx("px-0.5 py-1.5", i === 5 && "border-l-2 border-slate-200")}>
                            <div
                              title={isVac ? "Vacaciones" : "Disponible"}
                              className={cx(
                                "grid h-10 place-items-center rounded-lg text-[11px] font-bold",
                                isVac ? (conflict ? "bg-red-100 text-red-600 ring-1 ring-inset ring-red-200" : "bg-sky-100 text-sky-700") : "bg-slate-50"
                              )}
                            >
                              {isVac && <Palmtree className="h-4 w-4" />}
                            </div>
                          </td>
                        );
                      })}
                      <td className="px-4 py-2.5">
                        <div className="flex items-center justify-between gap-2 text-[12px]">
                          <span className="font-bold tabular-nums text-slate-700">{dev.assigned_pts}/{dev.capacity_pts} pts</span>
                          <Badge tone={r.tone}>{r.label}</Badge>
                        </div>
                        <div className="mt-1 h-1.5 w-40 overflow-hidden rounded-full bg-slate-100">
                          <div className={cx("h-full rounded-full", r.bar)} style={{ width: `${Math.min(100, dev.load_pct)}%` }} />
                        </div>
                        <div className="mt-0.5 max-w-[160px] truncate text-[10.5px] text-slate-400">{dev.stories.map((s: any) => s.key).join(", ") || "sin historias"}</div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="flex flex-wrap items-center gap-4 border-t border-slate-100 px-5 py-3 text-[11.5px] text-slate-500">
            <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded bg-sky-100" />Vacaciones sin impacto</span>
            <span className="flex items-center gap-1.5"><span className="h-3 w-3 rounded bg-red-100 ring-1 ring-red-200" />Vacaciones con trabajo asignado</span>
            <span>Capacidad = días hábiles disponibles × foco del dev (pts/día)</span>
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Registrar vacaciones" subtitle="El sistema recalcula la capacidad y alerta al LT" icon={<Palmtree className="h-4 w-4" />} />
            <div className="space-y-3 p-5">
              <div>
                <label className="text-[11.5px] font-bold uppercase tracking-wide text-slate-500">Dev</label>
                <select value={form.dev_id} onChange={(e) => setForm({ ...form, dev_id: e.target.value })} className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-4 focus:ring-blue-100">
                  <option value="">Selecciona…</option>
                  {data.devs.map((d: any) => <option key={d.id} value={d.id}>{d.name}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[11.5px] font-bold uppercase tracking-wide text-slate-500">Desde</label>
                  <input type="date" value={form.start} onChange={(e) => setForm({ ...form, start: e.target.value })} className="mt-1 w-full rounded-xl border border-slate-200 px-2 py-2 text-sm outline-none focus:ring-4 focus:ring-blue-100" />
                </div>
                <div>
                  <label className="text-[11.5px] font-bold uppercase tracking-wide text-slate-500">Hasta</label>
                  <input type="date" value={form.end} onChange={(e) => setForm({ ...form, end: e.target.value })} className="mt-1 w-full rounded-xl border border-slate-200 px-2 py-2 text-sm outline-none focus:ring-4 focus:ring-blue-100" />
                </div>
              </div>
              <input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} placeholder="Motivo" className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:ring-4 focus:ring-blue-100" />
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={() => setForm({ ...form, start: days[3], end: days[6] })}>Sugerir fechas del sprint</Button>
              </div>
              <Button className="w-full" onClick={save} loading={saving}><Plus className="h-4 w-4" />Registrar</Button>
            </div>
          </Card>

          <Card>
            <CardHeader title="Ausencias registradas" icon={<Users className="h-4 w-4" />} />
            <div className="divide-y divide-slate-100">
              {data.devs.flatMap((d: any) => d.vacations.map((v: any) => ({ ...v, dev: d.name }))).length === 0 && <Empty title="Sin ausencias" />}
              {data.devs.flatMap((d: any) => d.vacations.map((v: any) => ({ ...v, dev: d.name }))).map((v: any) => (
                <div key={v.id} className="flex items-center justify-between gap-2 px-5 py-2.5">
                  <div className="min-w-0">
                    <div className="text-[13px] font-semibold text-slate-700">{v.dev}</div>
                    <div className="text-[11.5px] text-slate-500">{fmtDate(v.start)} → {fmtDate(v.end)} · {v.note}</div>
                  </div>
                  <button onClick={() => removeVacation(v.id)} className="rounded-lg p-1.5 text-slate-300 hover:bg-red-50 hover:text-red-500"><Trash2 className="h-4 w-4" /></button>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
