import { ReactNode } from "react";
import { X, Loader2 } from "lucide-react";
import { initials } from "../lib/format";

export function cx(...c: (string | false | null | undefined)[]) {
  return c.filter(Boolean).join(" ");
}

export function Card({ children, className = "", ...rest }: { children: ReactNode; className?: string; [k: string]: any }) {
  return (
    <div className={cx("rounded-2xl border border-slate-200/80 bg-white shadow-[0_1px_2px_rgba(15,23,42,.04),0_4px_16px_rgba(15,23,42,.04)]", className)} {...rest}>
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, icon, right }: { title: ReactNode; subtitle?: ReactNode; icon?: ReactNode; right?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
      <div className="flex items-start gap-3">
        {icon && <div className="mt-0.5 grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-slate-100 text-navy-800">{icon}</div>}
        <div>
          <h3 className="text-[15px] font-semibold text-slate-900">{title}</h3>
          {subtitle && <p className="mt-0.5 text-[13px] text-slate-500">{subtitle}</p>}
        </div>
      </div>
      {right}
    </div>
  );
}

type BtnProps = {
  children: ReactNode;
  variant?: "primary" | "secondary" | "ghost" | "danger" | "success" | "teams";
  size?: "sm" | "md" | "lg";
  loading?: boolean;
  className?: string;
  [k: string]: any;
};

export function Button({ children, variant = "primary", size = "md", loading, className = "", disabled, ...rest }: BtnProps) {
  const v = {
    primary: "bg-navy-900 text-white hover:bg-navy-800 shadow-sm",
    secondary: "bg-white text-slate-800 border border-slate-200 hover:bg-slate-50",
    ghost: "text-slate-600 hover:bg-slate-100",
    danger: "bg-red-600 text-white hover:bg-red-700",
    success: "bg-emerald-600 text-white hover:bg-emerald-700 shadow-sm",
    teams: "bg-teams text-white hover:bg-teams-dark",
  }[variant];
  const s = { sm: "h-8 px-3 text-xs", md: "h-10 px-4 text-sm", lg: "h-12 px-6 text-[15px]" }[size];
  return (
    <button
      className={cx("inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-50 active:scale-[.98]", v, s, className)}
      disabled={disabled || loading}
      {...rest}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

const TONES: Record<string, string> = {
  slate: "bg-slate-100 text-slate-700 ring-slate-200",
  red: "bg-red-50 text-red-700 ring-red-200",
  amber: "bg-amber-50 text-amber-800 ring-amber-200",
  green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  blue: "bg-blue-50 text-blue-700 ring-blue-200",
  violet: "bg-violet-50 text-violet-700 ring-violet-200",
  teams: "bg-indigo-50 text-teams ring-indigo-200",
  navy: "bg-navy-900 text-white ring-navy-900",
};

export function Badge({ children, tone = "slate", className = "" }: { children: ReactNode; tone?: string; className?: string }) {
  return (
    <span className={cx("inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[11px] font-semibold ring-1 ring-inset", TONES[tone] || TONES.slate, className)}>
      {children}
    </span>
  );
}

export const LIGHT = {
  red: { dot: "bg-red-500", text: "text-red-700", bg: "bg-red-50", ring: "ring-red-200", label: "Bloqueada", emoji: "🔴" },
  yellow: { dot: "bg-amber-400", text: "text-amber-800", bg: "bg-amber-50", ring: "ring-amber-200", label: "En refinamiento", emoji: "🟡" },
  green: { dot: "bg-emerald-500", text: "text-emerald-700", bg: "bg-emerald-50", ring: "ring-emerald-200", label: "Ready", emoji: "🟢" },
} as const;

export function LightDot({ light, pulse, size = 10 }: { light: "red" | "yellow" | "green"; pulse?: boolean; size?: number }) {
  return <span className={cx("inline-block shrink-0 rounded-full", LIGHT[light].dot, pulse && light === "red" && "pulse-red")} style={{ width: size, height: size }} />;
}

const AVATAR_COLORS = ["bg-blue-600", "bg-violet-600", "bg-emerald-600", "bg-amber-600", "bg-rose-600", "bg-cyan-600", "bg-indigo-600"];

export function Avatar({ name, size = 28, className = "" }: { name?: string | null; size?: number; className?: string }) {
  if (!name) return <span className={cx("grid place-items-center rounded-full bg-slate-200 text-[10px] font-bold text-slate-500", className)} style={{ width: size, height: size }}>?</span>;
  const idx = [...name].reduce((a, c) => a + c.charCodeAt(0), 0) % AVATAR_COLORS.length;
  return (
    <span title={name} className={cx("grid shrink-0 place-items-center rounded-full font-bold text-white", AVATAR_COLORS[idx], className)} style={{ width: size, height: size, fontSize: size * 0.38 }}>
      {initials(name)}
    </span>
  );
}

export function Tip({ children, text, className = "" }: { children: ReactNode; text: ReactNode; className?: string }) {
  return (
    <span className={cx("group relative inline-flex", className)}>
      {children}
      <span className="pointer-events-none absolute left-1/2 top-full z-50 mt-2 w-72 -translate-x-1/2 rounded-xl bg-navy-950 px-3 py-2 text-left text-xs font-normal leading-relaxed text-slate-100 opacity-0 shadow-xl transition-opacity group-hover:opacity-100">
        {text}
      </span>
    </span>
  );
}

export function Drawer({ open, onClose, children, width = 720, title }: { open: boolean; onClose: () => void; children: ReactNode; width?: number; title?: ReactNode }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex justify-end">
      <div className="absolute inset-0 bg-navy-950/40 backdrop-blur-[2px]" onClick={onClose} />
      <div className="anim-slide relative flex h-full flex-col bg-canvas shadow-2xl" style={{ width: `min(${width}px, 100vw)` }}>
        <div className="flex items-center justify-between border-b border-slate-200 bg-white px-5 py-3">
          <div className="min-w-0 flex-1">{title}</div>
          <button onClick={onClose} className="rounded-lg p-2 text-slate-500 hover:bg-slate-100">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">{children}</div>
      </div>
    </div>
  );
}

export function Empty({ icon, title, text }: { icon?: ReactNode; title: string; text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-10 text-center">
      {icon && <div className="mb-3 text-slate-300">{icon}</div>}
      <p className="text-sm font-semibold text-slate-600">{title}</p>
      {text && <p className="mt-1 max-w-sm text-xs text-slate-400">{text}</p>}
    </div>
  );
}

export function Spinner({ className = "" }: { className?: string }) {
  return <Loader2 className={cx("h-5 w-5 animate-spin text-slate-400", className)} />;
}

export function Loading() {
  return (
    <div className="grid h-64 place-items-center">
      <Spinner className="h-7 w-7" />
    </div>
  );
}
