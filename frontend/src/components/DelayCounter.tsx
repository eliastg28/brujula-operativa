import { useNow } from "../lib/hooks";
import { elapsedParts, fmtCounter } from "../lib/format";
import { cx } from "./ui";

export function slaState(dep: any, now = Date.now()) {
  const end = dep.status === "resolved" && dep.resolved_at ? new Date(dep.resolved_at).getTime() : now;
  const days = elapsedParts(dep.requested_at, end).totalDays;
  const ratio = days / (dep.sla_days || 3);
  return { days, ratio, status: ratio >= 1 ? "overdue" : ratio >= 0.66 ? "warning" : "ok" };
}

export default function DelayCounter({ dep, compact = false }: { dep: any; compact?: boolean }) {
  const now = useNow();
  const resolved = dep.status === "resolved";
  const end = resolved && dep.resolved_at ? new Date(dep.resolved_at).getTime() : now;
  const st = slaState(dep, now);
  const color = resolved ? "text-emerald-600" : st.status === "overdue" ? "text-red-600" : st.status === "warning" ? "text-amber-600" : "text-slate-700";
  const bar = resolved ? "bg-emerald-500" : st.status === "overdue" ? "bg-red-500" : st.status === "warning" ? "bg-amber-400" : "bg-blue-500";
  return (
    <div className={cx("min-w-[132px]", compact && "min-w-[110px]")}>
      <div className={cx("font-mono font-semibold tabular-nums", compact ? "text-[13px]" : "text-[17px]", color)}>
        {fmtCounter(dep.requested_at, end)}
      </div>
      <div className="mt-1 h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
        <div className={cx("h-full rounded-full transition-all", bar)} style={{ width: `${Math.min(100, st.ratio * 100)}%` }} />
      </div>
      <div className="mt-0.5 text-[10.5px] font-medium text-slate-400">
        {resolved ? "resuelto" : st.status === "overdue" ? `SLA vencido (${dep.sla_days}d)` : `SLA ${dep.sla_days} días`}
      </div>
    </div>
  );
}
