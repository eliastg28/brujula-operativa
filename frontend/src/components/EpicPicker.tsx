import { useEffect, useRef, useState } from "react";
import { Layers, Plus, Sparkles, Check, X } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../lib/ctx";
import { Button, cx } from "./ui";

type Props = {
  squad: string;
  value: string;
  onChange: (key: string) => void;
  title?: string;          // título de la historia, para sugerir épicas existentes
  compact?: boolean;       // versión para el detalle de historia
  disabled?: boolean;
};

/** Selector de épica + sugerencias de épicas existentes + creación rápida en línea. */
export default function EpicPicker({ squad, value, onChange, title = "", compact = false, disabled }: Props) {
  const { toast, bump, tick } = useApp();
  const [epics, setEpics] = useState<any[]>([]);
  const [suggestions, setSuggestions] = useState<any[]>([]);
  const [creating, setCreating] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newObjective, setNewObjective] = useState("");
  const [saving, setSaving] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => { api.get(`/api/epics?squad=${squad}`).then(setEpics).catch(() => {}); }, [squad, tick]);

  // Sugerencias de épicas existentes según el título (con debounce)
  useEffect(() => {
    if (compact || title.trim().length < 4) { setSuggestions([]); return; }
    const id = setTimeout(() => {
      api.get(`/api/epics/suggest?squad=${squad}&title=${encodeURIComponent(title)}`).then(setSuggestions).catch(() => {});
    }, 350);
    return () => clearTimeout(id);
  }, [title, squad, compact]);

  useEffect(() => { if (creating) inputRef.current?.focus(); }, [creating]);

  async function create() {
    if (newTitle.trim().length < 3) return toast({ tone: "error", title: "Escribe un nombre para la épica" });
    setSaving(true);
    try {
      const r = await api.post("/api/epics", { squad, title: newTitle, objective: newObjective });
      setEpics((prev) => (prev.some((e) => e.key === r.key) ? prev : [...prev, r.epic]));
      onChange(r.key);
      setCreating(false);
      setNewTitle("");
      setNewObjective("");
      bump();
      toast({
        tone: "ok",
        title: r.duplicate ? `Ya existía: ${r.key}` : `Épica ${r.key} creada en Jira`,
        body: `${r.title} · seleccionada para esta historia`,
      });
    } catch (e: any) {
      toast({ tone: "error", title: "No se pudo crear la épica", body: e.message });
    } finally {
      setSaving(false);
    }
  }

  const selected = epics.find((e) => e.key === value);
  const showSuggest = !compact && !creating && suggestions.length > 0 && !suggestions.some((s) => s.epic_key === value);
  const showNoMatch = !compact && !creating && !value && title.trim().length >= 4 && suggestions.length === 0;

  return (
    <div className={cx(!compact && "space-y-2")}>
      <div className="flex items-center gap-2">
        {compact && <Layers className="h-4 w-4 shrink-0 text-blue-600" />}
        <select
          value={value}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
          className={cx(
            "min-w-0 flex-1 rounded-xl border bg-white text-sm font-medium outline-none focus:ring-4 focus:ring-blue-100",
            compact ? "px-2 py-1.5" : "px-3 py-2.5",
            value ? "border-slate-200 text-slate-800" : "border-amber-300 text-slate-500"
          )}
        >
          <option value="">{compact ? "— Sin épica —" : "Selecciona una épica…"}</option>
          {epics.map((e) => <option key={e.key} value={e.key}>{e.key} · {e.title}</option>)}
        </select>
        <Button
          type="button"
          variant={creating ? "ghost" : "secondary"}
          size={compact ? "sm" : "md"}
          disabled={disabled}
          onClick={() => setCreating((v) => !v)}
          title="Crear una épica nueva en Jira"
        >
          {creating ? <X className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
          {creating ? "Cancelar" : "Nueva épica"}
        </Button>
      </div>

      {/* Creación rápida en línea */}
      {creating && (
        <div className={cx("anim-in rounded-xl border-2 border-dashed border-violet-300 bg-violet-50/60 p-3", compact && "mt-2")}>
          <div className="mb-2 flex items-center gap-1.5 text-[12px] font-bold text-violet-800">
            <Layers className="h-3.5 w-3.5" /> Nueva épica · se crea en Jira y queda seleccionada
          </div>
          <input
            ref={inputRef}
            value={newTitle}
            onChange={(e) => setNewTitle(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); create(); } if (e.key === "Escape") setCreating(false); }}
            placeholder="Nombre de la épica (ej. Programa de Lealtad)"
            className="w-full rounded-lg border border-violet-200 bg-white px-3 py-2 text-sm font-semibold text-slate-900 outline-none placeholder:font-normal focus:ring-4 focus:ring-violet-100"
          />
          <input
            value={newObjective}
            onChange={(e) => setNewObjective(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); create(); } if (e.key === "Escape") setCreating(false); }}
            placeholder="Objetivo de negocio (opcional)"
            className="mt-2 w-full rounded-lg border border-violet-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:ring-4 focus:ring-violet-100"
          />
          <div className="mt-2 flex items-center justify-between gap-2">
            <span className="text-[11px] text-violet-700">Enter para crear · Esc para cancelar</span>
            <Button type="button" size="sm" onClick={create} loading={saving} disabled={newTitle.trim().length < 3} className="!bg-violet-700 hover:!bg-violet-800">
              <Check className="h-3.5 w-3.5" /> Crear y seleccionar
            </Button>
          </div>
        </div>
      )}

      {/* Info de la épica elegida */}
      {!compact && selected && !creating && (
        <div className="flex items-center gap-2 text-[12px] text-slate-500">
          <span className="truncate">{selected.objective || "Sin objetivo registrado"}</span>
          <span className="ml-auto shrink-0 font-semibold text-slate-600">{selected.progress ?? 0}% avance</span>
        </div>
      )}

      {/* Sugerencias de épicas EXISTENTES */}
      {showSuggest && (
        <div className="anim-in flex flex-wrap items-center gap-1.5">
          <span className="flex items-center gap-1 text-[11.5px] font-semibold text-slate-500"><Sparkles className="h-3.5 w-3.5 text-violet-500" />Sugeridas:</span>
          {suggestions.map((s) => (
            <button
              key={s.epic_key}
              type="button"
              onClick={() => onChange(s.epic_key)}
              className="rounded-full border border-blue-200 bg-blue-50 px-2.5 py-1 text-[12px] font-semibold text-blue-700 hover:border-blue-300 hover:bg-blue-100"
            >
              {s.epic_key} · {s.epic_title} <span className="font-normal text-blue-500">{Math.round(s.confidence * 100)}%</span>
            </button>
          ))}
        </div>
      )}
      {showNoMatch && (
        <div className="anim-in flex flex-wrap items-center gap-2 rounded-lg bg-amber-50 px-3 py-2 text-[12px] text-amber-800 ring-1 ring-amber-200">
          Ninguna épica existente coincide con este título.
          <button type="button" onClick={() => setCreating(true)} className="font-bold underline">Crear una nueva</button>
        </div>
      )}
    </div>
  );
}
