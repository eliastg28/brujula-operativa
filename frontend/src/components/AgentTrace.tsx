import { useEffect, useRef } from "react";
import { Compass, Link2, PenLine, ShieldCheck, Plug, CheckCircle2, AlertTriangle, Loader2, Cpu, Brain } from "lucide-react";
import { cx } from "./ui";

export const AGENT_META: Record<string, { name: string; icon: any; color: string; ring: string; text: string }> = {
  supervisor: { name: "Supervisor · Brújula", icon: Compass, color: "bg-navy-900", ring: "ring-navy-200", text: "text-navy-900" },
  epic: { name: "Vinculador de Épicas", icon: Link2, color: "bg-blue-600", ring: "ring-blue-200", text: "text-blue-700" },
  writer: { name: "Redactor de HU", icon: PenLine, color: "bg-violet-600", ring: "ring-violet-200", text: "text-violet-700" },
  compliance: { name: "Riesgos & Compliance", icon: ShieldCheck, color: "bg-rose-600", ring: "ring-rose-200", text: "text-rose-700" },
};

const ORDER = ["supervisor", "epic", "writer", "compliance"];

function agentStatus(events: any[], agent: string) {
  const started = events.some((e) => e.type === "agent_start" && e.agent === agent);
  const done = events.find((e) => e.type === "agent_done" && e.agent === agent);
  return done ? { s: "done", ms: done.ms, engine: done.engine } : started ? { s: "running" } : { s: "idle" };
}

export default function AgentTrace({ events, running }: { events: any[]; running: boolean }) {
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }, [events.length]);

  const start = events.find((e) => e.type === "run_start");
  const discovery = events.find((e) => e.type === "mcp_discovery");
  const done = events.find((e) => e.type === "done");
  const toolCalls = events.filter((e) => e.type === "tool_call").length;
  const results = Object.fromEntries(events.filter((e) => e.type === "tool_result").map((e) => [e.call_id, e]));

  const visible = events.filter((e) => ["thought", "tool_call", "agent_done", "fallback", "error"].includes(e.type));

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-2xl border border-navy-800 bg-navy-950 text-slate-200 shadow-xl">
      {/* Header */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-white/10 px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-bold text-white">
          <Brain className="h-4 w-4 text-violet-300" /> Agent Trace
          {running && <span className="ml-1 flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10.5px] font-semibold text-emerald-300"><span className="blink h-1.5 w-1.5 rounded-full bg-emerald-400" />EN VIVO</span>}
        </div>
        {start && (
          <span className="flex items-center gap-1.5 text-[11.5px] text-slate-400">
            <Cpu className="h-3.5 w-3.5" />
            {start.engine === "claude" ? <>Claude · <span className="font-mono text-slate-300">{start.model}</span></> : <span className="text-amber-300">{start.model}</span>}
          </span>
        )}
        {discovery && (
          <span className="flex items-center gap-1.5 text-[11.5px] text-slate-400">
            <Plug className="h-3.5 w-3.5 text-cyan-300" /> MCP · {discovery.tools.length} tools descubiertas
          </span>
        )}
        <span className="ml-auto font-mono text-[11.5px] text-slate-400">
          {toolCalls} llamadas MCP{done ? ` · ${(done.ms / 1000).toFixed(1)} s` : ""}
        </span>
      </div>

      {/* Carriles de agentes */}
      <div className="grid grid-cols-2 gap-2 border-b border-white/10 px-4 py-3 xl:grid-cols-4">
        {ORDER.map((a) => {
          const m = AGENT_META[a];
          const st = agentStatus(events, a);
          const Icon = m.icon;
          return (
            <div key={a} className={cx("flex items-center gap-2 rounded-xl border px-2.5 py-2 transition-all", st.s === "running" ? "border-white/25 bg-white/10" : st.s === "done" ? "border-emerald-400/30 bg-emerald-400/5" : "border-white/5 bg-white/[.02] opacity-50")}>
              <div className={cx("grid h-7 w-7 shrink-0 place-items-center rounded-lg text-white", m.color)}>
                <Icon className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <div className="truncate text-[11.5px] font-semibold text-white">{m.name}</div>
                <div className="text-[10.5px] text-slate-400">
                  {st.s === "running" ? <span className="flex items-center gap-1 text-emerald-300"><Loader2 className="h-3 w-3 animate-spin" />trabajando…</span> : st.s === "done" ? `✓ ${(st.ms / 1000).toFixed(1)} s · ${st.engine === "claude" ? "Claude" : "offline"}` : "en espera"}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Timeline */}
      <div className="flex-1 space-y-2 overflow-y-auto px-4 py-3 font-mono text-[12px] leading-relaxed">
        {visible.length === 0 && (
          <div className="grid h-full place-items-center text-center font-sans text-sm text-slate-500">
            <div>
              <Compass className="mx-auto mb-2 h-8 w-8 text-slate-600" />
              Los agentes aparecerán aquí trabajando en vivo:<br />
              razonamiento, llamadas MCP y decisiones.
            </div>
          </div>
        )}
        {visible.map((e, i) => {
          const m = AGENT_META[e.agent] || AGENT_META.supervisor;
          if (e.type === "thought")
            return (
              <div key={i} className="anim-in flex gap-2">
                <span className={cx("mt-1.5 h-2 w-2 shrink-0 rounded-full", m.color)} />
                <div>
                  <span className={cx("font-sans text-[11px] font-bold", m.text.replace("700", "300").replace("900", "300"))}>{m.name}</span>
                  <p className="font-sans text-[12.5px] italic text-slate-300">{e.text}</p>
                </div>
              </div>
            );
          if (e.type === "tool_call") {
            const r = results[e.call_id];
            const args = Object.entries(e.args || {}).filter(([k]) => !["message", "user_story", "acceptance_criteria_gherkin", "story_text"].includes(k)).slice(0, 4);
            return (
              <div key={i} className="anim-in ml-4 rounded-lg border border-cyan-400/20 bg-cyan-400/[.06] px-3 py-2">
                <div className="flex flex-wrap items-center gap-x-2">
                  <span className="text-cyan-300">⚡ MCP</span>
                  <span className="font-semibold text-white">{e.tool}</span>
                  <span className="text-slate-500">({args.map(([k, v]) => `${k}=${typeof v === "string" ? `"${String(v).slice(0, 28)}"` : JSON.stringify(v)}`).join(", ")})</span>
                  <span className="ml-auto text-[10.5px] text-slate-500">{m.name}</span>
                </div>
                {r ? (
                  <div className={cx("mt-1", r.ok ? "text-emerald-300" : "text-red-300")}>
                    {r.ok ? "✓" : "✗"} {r.summary} <span className="text-slate-500">· {r.ms} ms</span>
                  </div>
                ) : (
                  <div className="mt-1 flex items-center gap-1 text-slate-400"><Loader2 className="h-3 w-3 animate-spin" />ejecutando…</div>
                )}
              </div>
            );
          }
          if (e.type === "agent_done")
            return (
              <div key={i} className="anim-in flex items-center gap-2 font-sans text-[12.5px]">
                <CheckCircle2 className="h-4 w-4 text-emerald-400" />
                <span className="font-semibold text-white">{m.name}</span>
                <span className="text-slate-300">→ {e.summary}</span>
              </div>
            );
          if (e.type === "fallback")
            return (
              <div key={i} className="anim-in flex items-start gap-2 rounded-lg bg-amber-400/10 px-3 py-2 font-sans text-[12px] text-amber-200">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" /> {m.name}: {e.message}
              </div>
            );
          return (
            <div key={i} className="anim-in rounded-lg bg-red-500/15 px-3 py-2 font-sans text-red-200">⛔ {e.message}</div>
          );
        })}
        <div ref={endRef} />
      </div>
    </div>
  );
}
