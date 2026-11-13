import { useEffect, useState } from "react";
import { Layers, MessageCircleQuestion, Wrench, AlertTriangle, Sparkles, Pencil, Save, ExternalLink, ShieldAlert, Bell, CheckCircle2 } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../lib/ctx";
import { Avatar, Badge, Button, cx } from "./ui";
import DorGate from "./DorGate";
import GherkinView from "./GherkinView";
import DelayCounter from "./DelayCounter";
import EpicPicker from "./EpicPicker";

function Section({ title, icon, children, right }: any) {
  return (
    <section className="rounded-2xl border border-slate-200/80 bg-white p-5">
      <div className="mb-3 flex items-center justify-between">
        <h4 className="flex items-center gap-2 text-[13px] font-bold uppercase tracking-wide text-slate-500">
          {icon}
          {title}
        </h4>
        {right}
      </div>
      {children}
    </section>
  );
}

function List({ items, empty }: { items: string[]; empty: string }) {
  if (!items?.length) return <p className="text-sm text-slate-400">{empty}</p>;
  return (
    <ul className="space-y-1.5">
      {items.map((x, i) => (
        <li key={i} className="flex gap-2 text-[13.5px] text-slate-700">
          <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-300" />
          {x}
        </li>
      ))}
    </ul>
  );
}

export function DependencyRow({ dep, onResolved }: { dep: any; onResolved?: (s: any) => void }) {
  const { toast, bump } = useApp();
  const [busy, setBusy] = useState<string | null>(null);
  const pending = dep.status === "pending";
  async function resolve() {
    setBusy("resolve");
    try {
      const r = await api.post(`/api/dependencies/${dep.id}/resolve`, { by: dep.owner_name });
      toast({ tone: "ok", title: `${dep.owner_area} aprobó`, body: dep.name });
      onResolved?.(r.story);
      bump();
    } finally {
      setBusy(null);
    }
  }
  async function remind() {
    setBusy("remind");
    try {
      await api.post(`/api/dependencies/${dep.id}/remind`);
      toast({ tone: "teams", title: `Recordatorio enviado a ${dep.owner_name}`, body: "Tarjeta de Teams vía MCP" });
      bump();
    } finally {
      setBusy(null);
    }
  }
  return (
    <div className={cx("flex flex-wrap items-center gap-4 rounded-xl border px-4 py-3", pending ? (dep.critical ? "border-red-200 bg-red-50/40" : "border-amber-200 bg-amber-50/40") : "border-emerald-200 bg-emerald-50/40")}>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[13.5px] font-semibold text-slate-800">{dep.name}</span>
          {dep.critical ? <Badge tone="red">Crítica</Badge> : <Badge tone="slate">No crítica</Badge>}
          {dep.escalated && pending && <Badge tone="red">Escalada</Badge>}
          {!pending && <Badge tone="green"><CheckCircle2 className="h-3 w-3" />Resuelta</Badge>}
        </div>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-3 text-xs text-slate-500">
          <span className="flex items-center gap-1.5"><Avatar name={dep.owner_name} size={16} />{dep.owner_name} · {dep.owner_area}</span>
          <span className="font-mono text-[11px]">{dep.policy_ref}</span>
        </div>
      </div>
      <DelayCounter dep={dep} compact />
      {pending && (
        <div className="flex gap-1.5">
          <Button size="sm" variant="secondary" onClick={remind} loading={busy === "remind"} title="Reenviar recordatorio por Teams">
            <Bell className="h-3.5 w-3.5" />
          </Button>
          <Button size="sm" variant="success" onClick={resolve} loading={busy === "resolve"} title={`Simular aprobación de ${dep.owner_name}`}>
            Aprobar
          </Button>
        </div>
      )}
    </div>
  );
}

export default function StoryDetail({ story: initial, onChange }: { story: any; onChange?: (s: any) => void }) {
  const { squad, toast, bump } = useApp();
  const [story, setStory] = useState(initial);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(initial.gherkin || "");
  const [saving, setSaving] = useState(false);

  useEffect(() => { setStory(initial); setDraft(initial.gherkin || ""); }, [initial]);

  const update = (s: any) => { setStory(s); onChange?.(s); };
  const ai = story.ai_analysis;

  async function changeEpic(key: string) {
    const s = await api.post(`/api/stories/${story.key}/epic`, { epic_key: key });
    update(s);
    bump();
    toast({ tone: "info", title: key ? `Épica vinculada: ${s.epic?.title}` : "Épica desvinculada", body: "La aprobación del dev se reinicia al cambiar el alcance." });
  }

  async function saveGherkin() {
    setSaving(true);
    try {
      const s = await api.patch(`/api/stories/${story.key}`, { gherkin: draft });
      update(s);
      setEditing(false);
      bump();
    } finally {
      setSaving(false);
    }
  }

  const pendingDeps = story.dependencies.filter((d: any) => d.status === "pending");

  return (
    <div className="space-y-4">
      {/* Encabezado */}
      <div className="rounded-2xl border border-slate-200/80 bg-white p-5">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-md bg-navy-900 px-2 py-0.5 font-mono font-semibold text-white">{story.key}</span>
          {story.ai_generated && <Badge tone="violet"><Sparkles className="h-3 w-3" />Refinada por agentes IA</Badge>}
          {story.points ? <Badge>{story.points} pts</Badge> : <Badge tone="amber">Sin estimar</Badge>}
          {story.jira_url && (
            <a href={story.jira_url} target="_blank" rel="noreferrer" className="ml-auto inline-flex items-center gap-1 text-slate-400 hover:text-navy-700">
              Ver en Jira <ExternalLink className="h-3 w-3" />
            </a>
          )}
        </div>
        <h2 className="mt-2 text-xl font-bold leading-snug text-slate-900">{story.title}</h2>
        {story.original_title && story.original_title !== story.title && (
          <p className="mt-1 text-xs text-slate-400">Título original ingresado: <span className="italic">"{story.original_title}"</span></p>
        )}
        <div className="mt-3 flex flex-wrap items-start gap-4 text-sm">
          <div className="flex items-center gap-2 pt-1">
            <Avatar name={story.assignee} size={26} />
            <span className="font-medium text-slate-700">{story.assignee || "Sin asignar"}</span>
          </div>
          <div className="min-w-[320px] flex-1">
            <EpicPicker squad={squad} value={story.epic_key || ""} onChange={changeEpic} compact />
          </div>
        </div>
      </div>

      <DorGate story={story} onChange={update} />

      {/* Historia */}
      <Section title="Historia de usuario" icon={<Sparkles className="h-4 w-4 text-violet-500" />}>
        {story.user_story ? (
          <blockquote className="border-l-4 border-violet-400 pl-4 text-[15px] leading-relaxed text-slate-800">{story.user_story}</blockquote>
        ) : (
          <p className="rounded-xl border border-dashed border-red-300 bg-red-50/50 px-4 py-4 text-sm text-red-600">Solo hay un título. Pásala por la Brújula IA para redactarla.</p>
        )}
        {story.context && <p className="mt-3 text-[13.5px] leading-relaxed text-slate-600">{story.context}</p>}
      </Section>

      <Section
        title="Criterios de aceptación · Gherkin"
        icon={<CheckCircle2 className="h-4 w-4 text-emerald-600" />}
        right={
          editing ? (
            <div className="flex gap-2">
              <Button size="sm" variant="ghost" onClick={() => { setEditing(false); setDraft(story.gherkin || ""); }}>Cancelar</Button>
              <Button size="sm" onClick={saveGherkin} loading={saving}><Save className="h-3.5 w-3.5" />Guardar</Button>
            </div>
          ) : (
            <Button size="sm" variant="ghost" onClick={() => setEditing(true)}><Pencil className="h-3.5 w-3.5" />Editar</Button>
          )
        }
      >
        {editing ? (
          <textarea value={draft} onChange={(e) => setDraft(e.target.value)} rows={14} className="w-full rounded-xl border border-slate-200 bg-slate-50 p-3 font-mono text-[12.5px] leading-relaxed outline-none focus:ring-2 focus:ring-blue-200" />
        ) : (
          <GherkinView text={story.gherkin} />
        )}
        {story.dor.scenarios?.length > 0 && !editing && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {story.dor.scenarios.map((s: any, i: number) => (
              <Badge key={i} tone={s.valid ? "green" : "red"}>{s.valid ? "✓" : "✗"} {s.name}</Badge>
            ))}
          </div>
        )}
      </Section>

      <Section title={`Dependencias operativas (${pendingDeps.length} pendientes)`} icon={<ShieldAlert className="h-4 w-4 text-red-500" />}>
        {story.dependencies.length === 0 ? (
          <p className="text-sm text-slate-400">Sin conformidades ni accesos requeridos por el catálogo.</p>
        ) : (
          <div className="space-y-2">
            {story.dependencies.map((d: any) => <DependencyRow key={d.id} dep={d} onResolved={update} />)}
          </div>
        )}
      </Section>

      {ai?.epic && (
        <Section title="Razonamiento del Vinculador de Épicas" icon={<Layers className="h-4 w-4 text-blue-600" />}>
          <p className="text-[13.5px] text-slate-700">{ai.epic.rationale}</p>
          {ai.epic.alternatives?.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {ai.epic.alternatives.map((a: any) => (
                <button key={a.epic_key} onClick={() => changeEpic(a.epic_key)} className="rounded-lg border border-slate-200 px-2.5 py-1.5 text-left text-xs hover:border-blue-300 hover:bg-blue-50">
                  <span className="font-semibold text-slate-700">Alternativa: {a.epic_title}</span>
                  <span className="ml-1 text-slate-400">{Math.round(a.confidence * 100)}%</span>
                </button>
              ))}
            </div>
          )}
        </Section>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        <Section title="Preguntas al PO" icon={<MessageCircleQuestion className="h-4 w-4 text-blue-500" />}>
          <List items={story.open_questions} empty="Sin preguntas abiertas" />
        </Section>
        <Section title="Notas técnicas" icon={<Wrench className="h-4 w-4 text-slate-500" />}>
          <List items={story.technical_notes} empty="—" />
        </Section>
        <Section title="Riesgos" icon={<AlertTriangle className="h-4 w-4 text-amber-500" />}>
          <List items={story.risks} empty="—" />
        </Section>
      </div>
    </div>
  );
}
