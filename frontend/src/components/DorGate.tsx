import { useState } from "react";
import { Check, X, Lock, Unlock, ThumbsUp, ArrowRight, ShieldCheck } from "lucide-react";
import { api, ApiError } from "../lib/api";
import { useApp } from "../lib/ctx";
import { Button, LIGHT, LightDot, cx } from "./ui";

export default function DorGate({ story, onChange }: { story: any; onChange: (s: any) => void }) {
  const { toast, bump } = useApp();
  const [busy, setBusy] = useState<string | null>(null);
  const [shake, setShake] = useState(0);
  const dor = story.dor;
  const light = dor.light as "red" | "yellow" | "green";
  const L = LIGHT[light];
  const planned = ["planning", "in_sprint", "done"].includes(story.status);
  const approved = !!story.dor_approved_by;

  async function approve() {
    setBusy("approve");
    try {
      const s = await api.post(`/api/stories/${story.key}/approve`, { by: story.assignee });
      onChange(s);
      bump();
      toast({ tone: "ok", title: `DoR aprobado por ${s.dor_approved_by}`, body: `${story.key} · el dev confirma que entiende y acepta los criterios.` });
    } catch (e: any) {
      setShake((n) => n + 1);
      toast({ tone: "error", title: "No se puede aprobar todavía", body: e.message });
    } finally {
      setBusy(null);
    }
  }

  async function unapprove() {
    setBusy("approve");
    try {
      onChange(await api.post(`/api/stories/${story.key}/unapprove`));
      bump();
    } finally {
      setBusy(null);
    }
  }

  async function move() {
    setBusy("move");
    try {
      const s = await api.post(`/api/stories/${story.key}/move`, { status: "planning" });
      onChange(s);
      bump();
      toast({ tone: "ok", title: `${story.key} pasó a Planning ✅`, body: "Cumple el Definition of Ready. Transición registrada en Jira vía MCP." });
    } catch (e: any) {
      if (e instanceof ApiError && e.status === 423) {
        setShake((n) => n + 1);
        if (e.data?.story) onChange(e.data.story);
        toast({ tone: "error", title: "⛔ 423 · Bloqueada por Definition of Ready", body: (e.data?.missing || []).join(" · ") });
      } else toast({ tone: "error", title: "Error", body: e.message });
    } finally {
      setBusy(null);
    }
  }

  return (
    <div key={shake} className={cx("overflow-hidden rounded-2xl border-2 bg-white", shake > 0 && "anim-shake", light === "red" ? "border-red-300" : light === "yellow" ? "border-amber-300" : "border-emerald-300")}>
      <div className={cx("flex items-center justify-between gap-3 px-5 py-4", L.bg)}>
        <div className="flex items-center gap-3">
          <div className={cx("grid h-11 w-11 place-items-center rounded-xl text-white", light === "red" ? "bg-red-600 pulse-red" : light === "yellow" ? "bg-amber-500" : "bg-emerald-600")}>
            {light === "green" ? <Unlock className="h-5 w-5" /> : <Lock className="h-5 w-5" />}
          </div>
          <div>
            <div className="text-[11px] font-bold uppercase tracking-wider text-slate-500">Gate · Definition of Ready</div>
            <div className={cx("text-lg font-extrabold", L.text)}>
              {planned ? "EN PLANNING" : light === "red" ? "BLOQUEADA PARA PLANNING" : light === "yellow" ? "FALTA APROBACIÓN DEL DEV" : "READY · PUEDE ENTRAR AL SPRINT"}
            </div>
          </div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-extrabold tabular-nums text-slate-800">{dor.passed}/{dor.total}</div>
          <div className="text-[11px] font-medium text-slate-500">controles OK</div>
        </div>
      </div>

      <ul className="divide-y divide-slate-100">
        {dor.checks.map((c: any) => (
          <li key={c.id} className="flex items-start gap-3 px-5 py-2.5">
            <span className={cx("mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full", c.ok ? "bg-emerald-100 text-emerald-700" : "bg-red-100 text-red-600")}>
              {c.ok ? <Check className="h-3.5 w-3.5" strokeWidth={3} /> : <X className="h-3.5 w-3.5" strokeWidth={3} />}
            </span>
            <div className="min-w-0">
              <div className={cx("text-[13.5px] font-semibold", c.ok ? "text-slate-800" : "text-red-700")}>{c.label}</div>
              <div className="truncate text-xs text-slate-500">{c.detail}</div>
            </div>
          </li>
        ))}
      </ul>

      {!planned && (
        <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 bg-slate-50/60 px-5 py-3">
          {approved ? (
            <Button variant="secondary" size="sm" onClick={unapprove} loading={busy === "approve"}>
              <ThumbsUp className="h-4 w-4 text-emerald-600" /> Aprobado por {story.dor_approved_by} · revocar
            </Button>
          ) : (
            <Button variant="success" onClick={approve} loading={busy === "approve"}>
              <ThumbsUp className="h-4 w-4" /> Aprobar DoR {story.assignee ? `(${story.assignee.split(" ")[0]})` : ""}
            </Button>
          )}
          <Button variant={light === "green" ? "primary" : "secondary"} onClick={move} loading={busy === "move"} className={light !== "green" ? "!text-red-700" : ""}>
            {light === "green" ? <ArrowRight className="h-4 w-4" /> : <Lock className="h-4 w-4" />} Mover a Planning
          </Button>
          <span className="ml-auto flex items-center gap-1.5 text-[11px] text-slate-400">
            <ShieldCheck className="h-3.5 w-3.5" /> Regla determinista y auditable (no la decide el LLM)
          </span>
        </div>
      )}
      {planned && (
        <div className="flex items-center gap-2 border-t border-emerald-100 bg-emerald-50 px-5 py-3 text-sm font-semibold text-emerald-700">
          <LightDot light="green" /> Comprometida en el sprint · pasó la Brújula sin retrabajo
        </div>
      )}
    </div>
  );
}
