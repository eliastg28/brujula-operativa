import { useCallback, useEffect, useRef, useState } from "react";
import {
  Compass, LayoutDashboard, ScanSearch, Hourglass, CalendarDays, CalendarClock, Network, Bell, RotateCcw,
  ChevronDown, CheckCircle2, XCircle, Info, MessageSquare, AlertTriangle, Brain, Plug,
} from "lucide-react";
import { api } from "./lib/api";
import { Ctx, Toast } from "./lib/ctx";
import { useHashRoute, usePoll } from "./lib/hooks";
import { fmtDate } from "./lib/format";
import KpiHeader from "./components/KpiHeader";
import NotificationCenter from "./components/NotificationCenter";
import StoryDetail from "./components/StoryDetail";
import { Avatar, Drawer, Loading, cx } from "./components/ui";
import Executive from "./pages/Executive";
import Brujula from "./pages/Brujula";
import Blockers from "./pages/Blockers";
import Capacity from "./pages/Capacity";
import Ceremonies from "./pages/Ceremonies";
import Integrations from "./pages/Integrations";

const NAV = [
  { id: "ejecutiva", label: "Vista Ejecutiva", icon: LayoutDashboard, title: "Vista Ejecutiva del Líder Técnico", sub: "Semáforo del backlog, KPIs y alertas" },
  { id: "brujula", label: "Brújula IA", icon: ScanSearch, title: "Brújula Inteligente de Historias", sub: "Del título vago a historia lista para el DoR" },
  { id: "bloqueos", label: "Bloqueos", icon: Hourglass, title: "Dependencias operativas", sub: "Contador de demora en tiempo real por cada pendiente" },
  { id: "capacidad", label: "Capacidad", icon: CalendarDays, title: "Vacaciones vs Sprint", sub: "Riesgo de capacidad antes de comprometer" },
  { id: "ceremonias", label: "Ceremonias", icon: CalendarClock, title: "Ceremonias con agenda automática", sub: "Daily, Planning, Refinamiento y Retro según el tablero real" },
  { id: "integraciones", label: "Arquitectura MCP", icon: Network, title: "Arquitectura e integraciones", sub: "Canal ➔ Orquestador ➔ IA ➔ MCP ➔ Sistemas" },
];

const TOAST_STYLE: Record<string, { icon: any; cls: string }> = {
  ok: { icon: CheckCircle2, cls: "border-emerald-200 text-emerald-600" },
  error: { icon: XCircle, cls: "border-red-200 text-red-600" },
  info: { icon: Info, cls: "border-blue-200 text-blue-600" },
  warn: { icon: AlertTriangle, cls: "border-amber-200 text-amber-600" },
  teams: { icon: MessageSquare, cls: "border-indigo-200 text-teams" },
};

export default function App() {
  const route = useHashRoute();
  const [squads, setSquads] = useState<any[]>([]);
  const [squad, setSquadState] = useState<string>(() => {
    try { return localStorage.getItem("brujula.squad") || "pagos"; } catch { return "pagos"; }
  });
  const [tick, setTick] = useState(0);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [storyKey, setStoryKey] = useState<string | null>(null);
  const [story, setStory] = useState<any>(null);
  const [inboxOpen, setInboxOpen] = useState(false);
  const [squadMenu, setSquadMenu] = useState(false);
  const seenNotifs = useRef<Set<string> | null>(null);

  const bump = useCallback(() => setTick((t) => t + 1), []);
  const toast = useCallback((t: Omit<Toast, "id">) => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev.slice(-3), { ...t, id }]);
    setTimeout(() => setToasts((prev) => prev.filter((x) => x.id !== id)), 5500);
  }, []);
  const setSquad = useCallback((id: string) => {
    setSquadState(id);
    seenNotifs.current = null;
    try { localStorage.setItem("brujula.squad", id); } catch { /* sin storage */ }
  }, []);

  useEffect(() => { api.get("/api/squads").then(setSquads).catch(() => {}); }, []);

  const { data: health } = usePoll(() => api.get("/api/health"), [], 10000);
  const { data: dash } = usePoll(() => api.get(`/api/dashboard?squad=${squad}`), [squad, tick], 5000);
  const { data: notifs, reload: reloadNotifs } = usePoll(() => api.get(`/api/notifications?squad=${squad}`), [squad, tick], 3000);
  const { data: blk, reload: reloadBlk } = usePoll(() => api.get(`/api/blockers?squad=${squad}`), [squad, tick, inboxOpen], 0);

  // Toast cuando llega una notificación nueva (efecto "le llegó a Teams")
  useEffect(() => {
    if (!notifs) return;
    const ids = notifs.items.map((n: any) => n.id);
    if (seenNotifs.current === null) { seenNotifs.current = new Set(ids); return; }
    const fresh = notifs.items.filter((n: any) => !seenNotifs.current!.has(n.id));
    fresh.slice(0, 3).reverse().forEach((n: any) =>
      toast({ tone: "teams", title: `${n.channel === "email" ? "✉ Correo" : "💬 Teams"} → ${n.to_name}`, body: n.title })
    );
    ids.forEach((id: string) => seenNotifs.current!.add(id));
  }, [notifs, toast]);

  // Abrir historia desde un deep-link (#/story/KEY), p. ej. desde la tarjeta de Teams
  useEffect(() => {
    if (route.page === "story" && route.param) {
      setStoryKey(route.param);
      window.location.hash = "#/ejecutiva";
    }
    if (route.page === "inbox") {
      setInboxOpen(true);
      window.location.hash = "#/ejecutiva";
    }
  }, [route.page, route.param]);

  useEffect(() => {
    if (!storyKey) { setStory(null); return; }
    api.get(`/api/stories/${storyKey}`).then(setStory).catch(() => toast({ tone: "error", title: `No se encontró ${storyKey}` }));
  }, [storyKey, tick, toast]);

  async function resetDemo() {
    if (!confirm("¿Reiniciar los datos de demo? Se borran las historias creadas en esta sesión.")) return;
    await api.post("/api/demo/reset");
    seenNotifs.current = null;
    bump();
    toast({ tone: "info", title: "Demo reiniciada", body: "Datos de ejemplo recargados" });
  }

  async function openInbox() {
    setInboxOpen(true);
    reloadBlk();
    await api.post(`/api/notifications/read?squad=${squad}`).catch(() => {});
    reloadNotifs();
  }

  const pageId = route.page === "aduana" ? "brujula" : route.page; // alias de enlaces antiguos
  const page = NAV.find((n) => n.id === pageId) || NAV[0];
  const current = squads.find((s) => s.id === squad);
  const sprint = dash?.sprint;
  const depsMap = Object.fromEntries([...(blk?.pending || []), ...(blk?.resolved || [])].map((d: any) => [d.id, d]));

  const ctx = { squad, squads, setSquad, health, toast, openStory: setStoryKey, openInbox, bump, tick };

  return (
    <Ctx.Provider value={ctx}>
      <div className="flex h-full">
        {/* Sidebar */}
        <aside className="hidden w-[248px] shrink-0 flex-col bg-navy-900 text-slate-300 md:flex">
          <div className="flex items-center gap-3 px-5 py-5">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-gradient-to-br from-blue-500 to-violet-600 text-white shadow-lg">
              <Compass className="h-6 w-6" />
            </div>
            <div>
              <div className="text-[16px] font-extrabold leading-tight text-white">Brújula Operativa</div>
              <div className="text-[11px] text-slate-400">SDLC sin fricción · IA + MCP</div>
            </div>
          </div>
          <nav className="mt-2 flex-1 space-y-1 px-3">
            {NAV.map((n) => {
              const active = n.id === page.id;
              const badge = n.id === "bloqueos" ? dash?.blockers?.pending : n.id === "capacidad" ? dash?.capacity_alerts?.length : 0;
              return (
                <a key={n.id} href={`#/${n.id}`} className={cx("flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13.5px] font-semibold transition-colors", active ? "bg-white/10 text-white" : "hover:bg-white/5 hover:text-white")}>
                  <n.icon className={cx("h-[18px] w-[18px]", active ? "text-blue-300" : "text-slate-400")} />
                  {n.label}
                  {badge ? <span className={cx("ml-auto rounded-full px-1.5 py-0.5 text-[10.5px] font-bold", n.id === "bloqueos" ? "bg-red-500 text-white" : "bg-amber-400 text-navy-900")}>{badge}</span> : null}
                  {n.id === "brujula" && <span className="ml-auto rounded-md bg-violet-500/30 px-1.5 py-0.5 text-[10px] font-bold text-violet-200">IA</span>}
                </a>
              );
            })}
          </nav>
          <div className="space-y-2 border-t border-white/10 px-4 py-4 text-[11.5px]">
            <div className="flex items-center gap-2"><Brain className="h-3.5 w-3.5 text-violet-300" /><span className="text-slate-400">IA:</span><span className="font-semibold text-white">{health?.ai?.enabled ? "Claude" : "Respaldo offline"}</span></div>
            <div className="flex items-center gap-2"><Plug className="h-3.5 w-3.5 text-cyan-300" /><span className="text-slate-400">MCP:</span><span className={cx("font-semibold", health?.mcp?.ok ? "text-emerald-300" : "text-amber-300")}>{health?.mcp?.ok ? `${health.mcp.tools} tools online` : "sin conexión"}</span></div>
            <div className="flex items-center gap-2"><span className={cx("h-2 w-2 rounded-full", health?.mode === "live" ? "bg-emerald-400" : "bg-violet-400")} /><span className="text-slate-400">Modo:</span><span className="font-semibold text-white">{health?.mode === "live" ? "Live (Jira/Teams reales)" : "Demo (mock realista)"}</span></div>
            <button onClick={resetDemo} className="mt-1 flex items-center gap-1.5 text-slate-500 hover:text-slate-300"><RotateCcw className="h-3 w-3" />Reiniciar demo</button>
          </div>
        </aside>

        {/* Main */}
        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex flex-wrap items-center gap-3 border-b border-slate-200 bg-white px-4 py-3 md:px-6">
            <div className="relative">
              <button onClick={() => setSquadMenu((v) => !v)} className="flex items-center gap-3 rounded-xl border border-slate-200 px-3 py-1.5 hover:bg-slate-50">
                <span className="h-7 w-1.5 rounded-full" style={{ background: current?.color || "#2563eb" }} />
                <div className="text-left">
                  <div className="text-[11px] font-semibold text-slate-500">{current?.tribu || "Tribu"}</div>
                  <div className="text-[14px] font-bold leading-tight text-slate-900">{current?.squad_name || "Squad"}</div>
                </div>
                <ChevronDown className="h-4 w-4 text-slate-400" />
              </button>
              {squadMenu && (
                <>
                  <div className="fixed inset-0 z-30" onClick={() => setSquadMenu(false)} />
                  <div className="anim-in absolute left-0 top-full z-40 mt-2 w-80 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl">
                    <div className="border-b border-slate-100 px-4 py-2.5 text-[11px] font-bold uppercase tracking-wide text-slate-400">Selecciona tribu / squad</div>
                    {squads.map((s) => (
                      <button key={s.id} onClick={() => { setSquad(s.id); setSquadMenu(false); }} className={cx("flex w-full items-center gap-3 px-4 py-3 text-left hover:bg-slate-50", s.id === squad && "bg-blue-50/60")}>
                        <span className="h-8 w-1.5 rounded-full" style={{ background: s.color }} />
                        <div className="min-w-0 flex-1">
                          <div className="text-[13.5px] font-semibold text-slate-800">{s.squad_name}</div>
                          <div className="text-[11.5px] text-slate-500">{s.tribu} · Jira {s.jira_project} · LT {s.lt}</div>
                        </div>
                        {s.id === squad && <CheckCircle2 className="h-4 w-4 text-blue-600" />}
                      </button>
                    ))}
                    <div className="border-t border-slate-100 bg-slate-50 px-4 py-2.5 text-[11.5px] text-slate-500">+ Nuevo squad = 1 bloque en <span className="font-mono">config/squads.yaml</span></div>
                  </div>
                </>
              )}
            </div>

            {sprint && (
              <div className="hidden items-center gap-2 rounded-xl bg-slate-50 px-3 py-2 text-[12.5px] lg:flex">
                <CalendarDays className="h-4 w-4 text-slate-400" />
                <span className="font-bold text-slate-800">{sprint.name}</span>
                <span className="text-slate-500">{fmtDate(sprint.start)} → {fmtDate(sprint.end)}</span>
              </div>
            )}

            <div className="ml-auto flex items-center gap-2">
              <button onClick={openInbox} className="relative flex items-center gap-2 rounded-xl border border-slate-200 px-3 py-2 text-[13px] font-semibold text-slate-700 hover:bg-slate-50" title="Simulador de Teams y correo">
                <Bell className="h-4 w-4" />
                <span className="hidden sm:inline">Teams / Correo</span>
                {notifs?.unread > 0 && <span className="absolute -right-1.5 -top-1.5 grid h-5 min-w-5 place-items-center rounded-full bg-red-500 px-1 text-[10.5px] font-bold text-white">{notifs.unread}</span>}
              </button>
              <div className="hidden items-center gap-2 pl-2 sm:flex">
                <Avatar name={current?.lt} size={34} />
                <div className="leading-tight">
                  <div className="text-[13px] font-semibold text-slate-800">{current?.lt}</div>
                  <div className="text-[11px] text-slate-500">Líder Técnico</div>
                </div>
              </div>
            </div>
          </header>

          {/* Navegación móvil */}
          <div className="flex gap-1 overflow-x-auto border-b border-slate-200 bg-white px-3 py-2 md:hidden">
            {NAV.map((n) => (
              <a key={n.id} href={`#/${n.id}`} className={cx("shrink-0 rounded-lg px-3 py-1.5 text-[12.5px] font-semibold", n.id === page.id ? "bg-navy-900 text-white" : "text-slate-600")}>{n.label}</a>
            ))}
          </div>

          <main className="flex-1 overflow-y-auto">
            <div className="mx-auto max-w-[1680px] space-y-5 px-4 py-5 md:px-6">
              <div>
                <h1 className="text-[22px] font-extrabold tracking-tight text-slate-900">{page.title}</h1>
                <p className="text-[13.5px] text-slate-500">{page.sub}</p>
              </div>
              <KpiHeader kpis={dash?.kpis} />
              {page.id === "ejecutiva" && <Executive dash={dash} />}
              {page.id === "brujula" && <Brujula autoTitle={route.param} />}
              {page.id === "bloqueos" && <Blockers />}
              {page.id === "capacidad" && <Capacity />}
              {page.id === "ceremonias" && <Ceremonies />}
              {page.id === "integraciones" && <Integrations />}
            </div>
          </main>
        </div>
      </div>

      {/* Drawer de historia */}
      <Drawer
        open={!!storyKey}
        onClose={() => setStoryKey(null)}
        width={820}
        title={<div className="text-[15px] font-bold text-slate-900">Detalle de historia <span className="font-mono text-slate-400">{storyKey}</span></div>}
      >
        <div className="p-5">{story ? <StoryDetail story={story} onChange={(s) => { setStory(s); bump(); }} /> : <Loading />}</div>
      </Drawer>

      <NotificationCenter open={inboxOpen} onClose={() => setInboxOpen(false)} data={notifs} deps={depsMap} reload={() => { reloadNotifs(); reloadBlk(); bump(); }} />

      {/* Toasts */}
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-[360px] max-w-[calc(100vw-2rem)] flex-col gap-2">
        {toasts.map((t) => {
          const st = TOAST_STYLE[t.tone || "info"];
          return (
            <div key={t.id} className={cx("anim-in pointer-events-auto flex gap-3 rounded-2xl border bg-white px-4 py-3 shadow-xl", st.cls)}>
              <st.icon className="mt-0.5 h-5 w-5 shrink-0" />
              <div className="min-w-0">
                <div className="text-[13.5px] font-bold text-slate-900">{t.title}</div>
                {t.body && <div className="mt-0.5 text-[12.5px] leading-snug text-slate-600">{t.body}</div>}
              </div>
            </div>
          );
        })}
      </div>
    </Ctx.Provider>
  );
}
