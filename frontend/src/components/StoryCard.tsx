import { Layers, AlertTriangle, Sparkles } from "lucide-react";
import { useApp } from "../lib/ctx";
import { Avatar, Badge, LightDot, cx } from "./ui";

export default function StoryCard({ story }: { story: any }) {
  const { openStory } = useApp();
  const d = story.dor;
  const pending = story.dependencies.filter((x: any) => x.status === "pending");
  const overdue = pending.filter((x: any) => x.sla_status === "overdue").length;
  const planned = ["planning", "in_sprint"].includes(story.status);
  return (
    <button
      onClick={() => openStory(story.key)}
      className={cx(
        "anim-in group w-full rounded-xl border bg-white p-3.5 text-left shadow-[0_1px_2px_rgba(15,23,42,.05)] transition-all hover:-translate-y-0.5 hover:shadow-md",
        d.light === "red" ? "border-red-200 hover:border-red-300" : d.light === "yellow" ? "border-amber-200 hover:border-amber-300" : "border-emerald-200 hover:border-emerald-300"
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <LightDot light={d.light} pulse={d.light === "red"} />
          <span className="font-mono text-[11.5px] font-semibold text-slate-500">{story.key}</span>
          {story.ai_generated && <Sparkles className="h-3.5 w-3.5 text-violet-500" aria-label="Refinada por IA" />}
        </div>
        <div className="flex items-center gap-1.5">
          {story.points ? <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] font-bold text-slate-600">{story.points} pts</span> : null}
          <Avatar name={story.assignee} size={24} />
        </div>
      </div>
      <div className="mt-2 line-clamp-2 text-[13.5px] font-semibold leading-snug text-slate-800 group-hover:text-navy-700">{story.title}</div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5">
        {story.epic ? (
          <Badge tone="blue"><Layers className="h-3 w-3" />{story.epic.title}</Badge>
        ) : (
          <Badge tone="red">Sin épica</Badge>
        )}
        {planned && <Badge tone="green">En Planning</Badge>}
        {d.reasons.filter((r: string) => r !== "Falta épica").map((r: string) => <Badge key={r} tone="red">{r}</Badge>)}
        {d.light === "yellow" && <Badge tone="amber">Falta aprobación dev</Badge>}
      </div>
      {pending.length > 0 && (
        <div className={cx("mt-2.5 flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-[11.5px] font-medium", overdue ? "bg-red-50 text-red-700" : "bg-amber-50 text-amber-800")}>
          <AlertTriangle className="h-3.5 w-3.5" />
          {pending.length} dependencia{pending.length > 1 ? "s" : ""} pendiente{pending.length > 1 ? "s" : ""}
          {overdue ? ` · ${overdue} con SLA vencido` : ""}
        </div>
      )}
      <div className="mt-2.5 flex gap-1">
        {d.checks.map((c: any) => (
          <span key={c.id} title={c.label} className={cx("h-1.5 flex-1 rounded-full", c.ok ? "bg-emerald-400" : "bg-slate-200")} />
        ))}
      </div>
    </button>
  );
}
