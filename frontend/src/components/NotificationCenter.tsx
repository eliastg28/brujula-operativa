import { useState } from "react";
import { MessageSquare, Mail, Bot, CheckCircle2, ExternalLink, Paperclip, Inbox } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../lib/ctx";
import { fmtAgo } from "../lib/format";
import { Avatar, Badge, Drawer, Empty, cx } from "./ui";

const SEV: Record<string, { bar: string; label: string; tone: string }> = {
  critical: { bar: "bg-red-600", label: "Crítico", tone: "red" },
  high: { bar: "bg-amber-500", label: "Alta", tone: "amber" },
  medium: { bar: "bg-teams", label: "Media", tone: "teams" },
  low: { bar: "bg-emerald-500", label: "Info", tone: "green" },
};

const KIND: Record<string, string> = {
  solicitud: "Solicitud", recordatorio: "Recordatorio", escalamiento: "Escalamiento",
  ceremonia: "Ceremonia", capacidad: "Capacidad", resuelto: "Resuelto",
};

function TeamsCard({ n, deps, onAction }: { n: any; deps: Record<string, any>; onAction: () => void }) {
  const { openStory, toast } = useApp();
  const [busy, setBusy] = useState(false);
  const sev = SEV[n.severity] || SEV.medium;
  const dep = n.dependency_id ? deps[n.dependency_id] : null;
  const canApprove = dep && dep.status === "pending" && ["solicitud", "recordatorio", "escalamiento"].includes(n.kind);

  async function approve() {
    setBusy(true);
    try {
      await api.post(`/api/dependencies/${dep.id}/resolve`, { by: dep.owner_name, comment: "Aprobado desde Teams" });
      toast({ tone: "ok", title: `${dep.owner_name} aprobó desde Teams`, body: dep.name });
      onAction();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="anim-in flex gap-3">
      <div className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-gradient-to-br from-navy-700 to-teams text-white shadow">
        <Bot className="h-5 w-5" />
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2 text-[12px]">
          <span className="font-bold text-slate-800">Brújula Bot</span>
          <span className="text-slate-400">{fmtAgo(n.sent_at)}</span>
          <span className="text-slate-400">→ {n.to_name}</span>
          {n.delivery === "enviado" && <Badge tone="green">Entregado en Teams real</Badge>}
        </div>
        <div className="mt-1 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
          <div className={cx("h-1", sev.bar)} />
          <div className="p-3.5">
            <div className="flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-wide text-teams">🧭 Brújula Operativa · {KIND[n.kind] || n.kind}</div>
            <div className="mt-1 text-[14px] font-bold leading-snug text-slate-900">{n.title}</div>
            <p className="mt-1 whitespace-pre-line text-[13px] leading-relaxed text-slate-600">{n.message}</p>
            <div className="mt-2.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 text-[12px]">
              <span className="font-semibold text-slate-500">Para</span><span className="text-slate-700">{n.to_name} · {n.to_area}</span>
              {n.story_key && (<><span className="font-semibold text-slate-500">Historia</span><span className="font-mono text-slate-700">{n.story_key}</span></>)}
              {n.policy_ref && (<><span className="font-semibold text-slate-500">Política</span><span className="text-slate-700">{n.policy_ref}</span></>)}
              {n.sla_days && (<><span className="font-semibold text-slate-500">SLA</span><span className="text-slate-700">{n.sla_days} días</span></>)}
            </div>
          </div>
          {(canApprove || n.story_key) && (
            <div className="flex border-t border-slate-100">
              {canApprove && (
                <button disabled={busy} onClick={approve} className="flex-1 py-2.5 text-[13px] font-semibold text-teams hover:bg-indigo-50 disabled:opacity-50">
                  {busy ? "Aprobando…" : "✓ Aprobar conformidad"}
                </button>
              )}
              {dep && dep.status === "resolved" && (
                <span className="flex flex-1 items-center justify-center gap-1 py-2.5 text-[13px] font-semibold text-emerald-600"><CheckCircle2 className="h-4 w-4" />Aprobado</span>
              )}
              {n.story_key && (
                <button onClick={() => openStory(n.story_key)} className="flex-1 border-l border-slate-100 py-2.5 text-[13px] font-semibold text-slate-600 hover:bg-slate-50">
                  Ver historia
                </button>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function EmailItem({ n }: { n: any }) {
  const { openStory } = useApp();
  const sev = SEV[n.severity] || SEV.medium;
  return (
    <div className="anim-in rounded-xl border border-slate-200 bg-white p-4">
      <div className="flex items-start gap-3">
        <Avatar name="Brújula Operativa" size={34} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="text-[13px] font-bold text-slate-800">Brújula Operativa &lt;noreply@banco.demo&gt;</span>
            <span className="shrink-0 text-[11px] text-slate-400">{fmtAgo(n.sent_at)}</span>
          </div>
          <div className="text-[12px] text-slate-500">Para: {n.to_name}{n.to_email ? ` <${n.to_email}>` : ""}</div>
          <div className="mt-1.5 flex items-center gap-2">
            <Badge tone={sev.tone}>{sev.label}</Badge>
            <span className="text-[14px] font-semibold text-slate-900">{n.title}</span>
          </div>
          <p className="mt-1.5 text-[13px] leading-relaxed text-slate-600">{n.message}</p>
          <div className="mt-2 flex items-center gap-3 text-[12px]">
            {n.story_key && <button onClick={() => openStory(n.story_key)} className="inline-flex items-center gap-1 font-semibold text-blue-600 hover:underline">Abrir {n.story_key} <ExternalLink className="h-3 w-3" /></button>}
            <span className="inline-flex items-center gap-1 text-slate-400"><Paperclip className="h-3 w-3" />evidencia-politica.pdf</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function NotificationCenter({ open, onClose, data, deps, reload }: { open: boolean; onClose: () => void; data: any; deps: Record<string, any>; reload: () => void }) {
  const [tab, setTab] = useState<"teams" | "email">("teams");
  const items = data?.items || [];
  const teams = items.filter((n: any) => n.channel !== "email");
  const emails = items.filter((n: any) => n.channel === "email");
  return (
    <Drawer
      open={open}
      onClose={onClose}
      width={560}
      title={
        <div>
          <div className="text-[15px] font-bold text-slate-900">Simulador de notificaciones</div>
          <div className="text-xs text-slate-500">Lo que reciben los owners en Teams y correo · enviado por la tool MCP <span className="font-mono">send_teams_notification</span></div>
        </div>
      }
    >
      <div className="sticky top-0 z-10 flex gap-1 border-b border-slate-200 bg-white px-4 pt-2">
        {[
          { id: "teams", label: "Microsoft Teams", icon: MessageSquare, n: teams.length },
          { id: "email", label: "Correo", icon: Mail, n: emails.length },
        ].map((t: any) => (
          <button key={t.id} onClick={() => setTab(t.id)} className={cx("flex items-center gap-2 border-b-2 px-3 py-2.5 text-sm font-semibold", tab === t.id ? "border-teams text-teams" : "border-transparent text-slate-500 hover:text-slate-700")}>
            <t.icon className="h-4 w-4" /> {t.label} <span className="rounded-full bg-slate-100 px-1.5 text-[11px] text-slate-600">{t.n}</span>
          </button>
        ))}
      </div>
      {tab === "teams" ? (
        <div className="min-h-full bg-[#f5f5f5] px-4 py-4">
          <div className="mb-3 flex items-center gap-2 rounded-lg bg-white px-3 py-2 text-[12.5px] font-semibold text-slate-600 shadow-sm">
            <span className="grid h-6 w-6 place-items-center rounded bg-teams text-[11px] font-bold text-white">#</span> Gobierno TI · solicitudes del squad
          </div>
          <div className="space-y-4">
            {teams.length === 0 ? <Empty icon={<Inbox className="h-10 w-10" />} title="Sin mensajes" /> : teams.map((n: any) => <TeamsCard key={n.id} n={n} deps={deps} onAction={reload} />)}
          </div>
        </div>
      ) : (
        <div className="space-y-3 px-4 py-4">
          {emails.length === 0 ? <Empty icon={<Mail className="h-10 w-10" />} title="Sin correos" /> : emails.map((n: any) => <EmailItem key={n.id} n={n} />)}
        </div>
      )}
    </Drawer>
  );
}
