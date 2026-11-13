import { useEffect, useRef, useState } from "react";
import { ScanSearch, Sparkles, Wand2, ArrowDown, RotateCcw } from "lucide-react";
import { api, streamAnalyze } from "../lib/api";
import { useApp } from "../lib/ctx";
import AgentTrace from "../components/AgentTrace";
import StoryDetail from "../components/StoryDetail";
import EpicPicker from "../components/EpicPicker";
import { Button, Card } from "../components/ui";

const EXAMPLES: Record<string, string[]> = {
  pagos: ["Integrar pasarela de pagos", "Devoluciones automáticas por contracargo", "Reporte de comisiones por adquirente"],
  canales: ["Login con biometría facial", "Notificación push de ofertas", "Onboarding con selfie y DNI"],
  riesgos: ["Consulta a buró externo para scoring", "Anexo regulatorio de créditos", "Alertas de fraude en préstamos"],
};

export default function Brujula({ autoTitle }: { autoTitle?: string }) {
  const { squad, toast, bump } = useApp();
  const [title, setTitle] = useState("");
  const [epicKey, setEpicKey] = useState("");
  const [assignee, setAssignee] = useState("");
  const [devs, setDevs] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);
  const [running, setRunning] = useState(false);
  const [story, setStory] = useState<any>(null);
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.get(`/api/devs?squad=${squad}`).then((d) => { setDevs(d); setAssignee(d[2]?.name || d[0]?.name || ""); });
    setEvents([]); setStory(null); setTitle(""); setEpicKey("");
  }, [squad]);

  const canRun = !!title.trim() && !!epicKey && !running;

  async function run() {
    if (running) return;
    if (!title.trim()) return toast({ tone: "error", title: "Escribe el título de la historia" });
    if (!epicKey) return toast({ tone: "warn", title: "Selecciona una épica", body: "Elige una existente o crea una nueva con «Nueva épica»." });
    setEvents([]);
    setStory(null);
    setRunning(true);
    try {
      await streamAnalyze({ squad, title, epic_key: epicKey, assignee: assignee || null }, (e) => {
        setEvents((prev) => [...prev, e]);
        if (e.type === "story") {
          setStory(e.story);
          bump();
          setTimeout(() => resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 250);
        }
        if (e.type === "error") toast({ tone: "error", title: "Error en los agentes", body: e.message });
      });
    } catch (e: any) {
      toast({ tone: "error", title: "No se pudo ejecutar la Brújula", body: e.message });
    } finally {
      setRunning(false);
    }
  }

  // Atajo de demo: #/brujula/<título> precarga el título (la épica la elige el usuario)
  const autoFilled = useRef(false);
  useEffect(() => {
    if (autoTitle && !autoFilled.current && devs.length) {
      autoFilled.current = true;
      setTitle(decodeURIComponent(autoTitle));
    }
  }, [autoTitle, devs]);

  const done = events.find((e) => e.type === "done");

  return (
    <div className="space-y-5">
      <div className="grid gap-5 xl:grid-cols-[420px_1fr]">
        {/* Entrada */}
        <Card className="flex flex-col p-6">
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-xl bg-gradient-to-br from-navy-800 to-violet-600 text-white shadow">
              <ScanSearch className="h-5 w-5" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-slate-900">Brújula Inteligente</h2>
              <p className="text-[13px] text-slate-500">Anti "lo vemos después"</p>
            </div>
          </div>
          <p className="mt-4 text-[13.5px] leading-relaxed text-slate-600">
            Escribe <b>el título</b> y elige su <b>épica</b> (o crea una en segundos). Los agentes validan la épica en Jira, redactan la historia
            con criterios Gherkin, detectan las dependencias operativas y notifican a los owners. Todo vía <b>MCP</b>.
          </p>

          <label className="mt-5 text-[12px] font-bold uppercase tracking-wide text-slate-500">1 · Título de la historia</label>
          <textarea
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); run(); } }}
            rows={2}
            placeholder='Ej. "Integrar pasarela de pagos"'
            className="mt-1.5 w-full resize-none rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-[16px] font-semibold text-slate-900 outline-none placeholder:font-normal placeholder:text-slate-400 focus:border-violet-300 focus:bg-white focus:ring-4 focus:ring-violet-100"
          />
          <div className="mt-2 flex flex-wrap gap-1.5">
            {(EXAMPLES[squad] || []).map((ex) => (
              <button key={ex} disabled={running} onClick={() => setTitle(ex)} className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[12px] font-medium text-slate-600 hover:border-violet-300 hover:bg-violet-50 hover:text-violet-700 disabled:opacity-50">
                {ex}
              </button>
            ))}
          </div>

          <label className="mt-4 mb-1.5 flex items-center justify-between text-[12px] font-bold uppercase tracking-wide text-slate-500">
            2 · Épica <span className="normal-case tracking-normal text-[11px] font-semibold text-red-500">{epicKey ? "" : "obligatoria"}</span>
          </label>
          <EpicPicker squad={squad} value={epicKey} onChange={setEpicKey} title={title} disabled={running} />

          <label className="mt-4 text-[12px] font-bold uppercase tracking-wide text-slate-500">3 · Dev asignado (aprobará el DoR)</label>
          <select value={assignee} onChange={(e) => setAssignee(e.target.value)} className="mt-1.5 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm font-medium text-slate-800 outline-none focus:ring-4 focus:ring-violet-100">
            <option value="">Sin asignar</option>
            {devs.map((d) => <option key={d.id} value={d.name}>{d.name} · {d.role}</option>)}
          </select>

          <Button size="lg" className="mt-5 !bg-gradient-to-r from-navy-900 to-violet-700" onClick={() => run()} loading={running} disabled={!canRun}>
            <Wand2 className="h-5 w-5" /> {running ? "Agentes trabajando…" : "Analizar con agentes IA"}
          </Button>
          {!running && !canRun && (
            <p className="mt-2 text-center text-[12px] text-slate-400">
              {!title.trim() ? "Escribe el título" : "Elige o crea la épica"} para continuar
            </p>
          )}

          {done && (
            <div className="anim-in mt-4 rounded-xl bg-emerald-50 px-4 py-3 text-[13px] text-emerald-800 ring-1 ring-emerald-200">
              <div className="flex items-center gap-2 font-bold"><Sparkles className="h-4 w-4" />Refinamiento completo en {(done.ms / 1000).toFixed(1)} s</div>
              <div className="mt-0.5">Hoy esto toma ~60 min de reunión y varios correos. <button onClick={() => resultRef.current?.scrollIntoView({ behavior: "smooth" })} className="inline-flex items-center gap-0.5 font-semibold underline">Ver resultado <ArrowDown className="h-3 w-3" /></button></div>
            </div>
          )}
          {story && !running && (
            <Button variant="ghost" size="sm" className="mt-2 self-start" onClick={() => { setEvents([]); setStory(null); setTitle(""); }}>
              <RotateCcw className="h-3.5 w-3.5" /> Nueva historia
            </Button>
          )}
        </Card>

        {/* Traza de agentes */}
        <div className="h-[600px]">
          <AgentTrace events={events} running={running} />
        </div>
      </div>

      {story && (
        <div ref={resultRef} className="anim-in scroll-mt-4">
          <div className="mb-3 flex items-center gap-2">
            <h3 className="text-lg font-bold text-slate-900">Resultado de la Brújula</h3>
            <span className="text-[13px] text-slate-500">· creada en Jira vía MCP · aprueba el DoR o destraba dependencias para pasar a Planning</span>
          </div>
          <StoryDetail story={story} onChange={setStory} />
        </div>
      )}
    </div>
  );
}
