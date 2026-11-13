import { Clock, CheckCircle2, TimerOff, ShieldAlert, CalendarX2, Info } from "lucide-react";
import { Tip, cx } from "./ui";

const ICONS: Record<string, any> = {
  hours_saved: Clock,
  ready_pct: CheckCircle2,
  dead_days: TimerOff,
  incomplete: ShieldAlert,
  capacity: CalendarX2,
};

const TONE: Record<string, { icon: string; value: string }> = {
  blue: { icon: "bg-blue-50 text-blue-600", value: "text-slate-900" },
  green: { icon: "bg-emerald-50 text-emerald-600", value: "text-slate-900" },
  violet: { icon: "bg-violet-50 text-violet-600", value: "text-slate-900" },
  red: { icon: "bg-red-50 text-red-600", value: "text-slate-900" },
  amber: { icon: "bg-amber-50 text-amber-600", value: "text-slate-900" },
};

function Sparkline({ values }: { values: number[] }) {
  if (!values || values.length < 2) return null;
  const w = 72, h = 26, max = Math.max(...values, 100), min = 0;
  const pts = values.map((v, i) => `${(i / (values.length - 1)) * w},${h - ((v - min) / (max - min)) * h}`).join(" ");
  const last = pts.split(" ").pop()!.split(",");
  return (
    <svg width={w} height={h} className="overflow-visible">
      <polyline points={pts} fill="none" stroke="#10b981" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={last[0]} cy={last[1]} r={3} fill="#10b981" />
    </svg>
  );
}

export default function KpiHeader({ kpis }: { kpis: any }) {
  if (!kpis) return <div className="grid h-[104px] grid-cols-2 gap-3 lg:grid-cols-5">{[0, 1, 2, 3, 4].map((i) => <div key={i} className="animate-pulse rounded-2xl bg-white" />)}</div>;
  return (
    <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
      {kpis.tiles.map((t: any) => {
        const Icon = ICONS[t.id] || Info;
        const tone = TONE[t.tone] || TONE.blue;
        return (
          <div key={t.id} className="anim-in relative rounded-2xl border border-slate-200/80 bg-white px-4 py-3.5 shadow-[0_1px_2px_rgba(15,23,42,.04)]">
            <div className="flex items-start justify-between">
              <div className={cx("grid h-9 w-9 place-items-center rounded-xl", tone.icon)}>
                <Icon className="h-[18px] w-[18px]" />
              </div>
              {t.id === "ready_pct" ? (
                <Sparkline values={kpis.ready_trend} />
              ) : (
                <Tip text={<><b className="text-white">¿Cómo se calcula?</b><br />{t.formula}</>}>
                  <Info className="h-4 w-4 cursor-help text-slate-300 hover:text-slate-500" />
                </Tip>
              )}
            </div>
            <div className="mt-2 flex items-baseline gap-1">
              <span className={cx("text-[26px] font-extrabold tracking-tight tabular-nums", tone.value)}>{t.value}</span>
              <span className="text-sm font-semibold text-slate-400">{t.unit}</span>
            </div>
            <div className="text-[13px] font-semibold text-slate-700">{t.label}</div>
            <div className="mt-0.5 truncate text-[11.5px] text-slate-500" title={t.delta}>{t.delta}</div>
          </div>
        );
      })}
    </div>
  );
}
