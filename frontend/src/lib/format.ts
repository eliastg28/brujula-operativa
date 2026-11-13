export function elapsedParts(fromIso: string, toMs = Date.now()) {
  const ms = Math.max(0, toMs - new Date(fromIso).getTime());
  const s = Math.floor(ms / 1000);
  return {
    days: Math.floor(s / 86400),
    hours: Math.floor((s % 86400) / 3600),
    minutes: Math.floor((s % 3600) / 60),
    seconds: s % 60,
    totalDays: ms / 86400000,
  };
}

const pad = (n: number) => String(n).padStart(2, "0");

export function fmtCounter(fromIso: string, toMs = Date.now()) {
  const p = elapsedParts(fromIso, toMs);
  return `${p.days}d ${pad(p.hours)}:${pad(p.minutes)}:${pad(p.seconds)}`;
}

export function fmtAgo(iso: string) {
  const p = elapsedParts(iso);
  if (p.days > 0) return `hace ${p.days}d ${p.hours}h`;
  if (p.hours > 0) return `hace ${p.hours}h ${p.minutes}m`;
  if (p.minutes > 0) return `hace ${p.minutes} min`;
  return "ahora";
}

const MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
const DAYS = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];

export function fmtDate(iso: string, withDay = false) {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  return `${withDay ? DAYS[dt.getDay()] + " " : ""}${d} ${MONTHS[m - 1]}`;
}

export function dayName(iso: string) {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return DAYS[new Date(y, m - 1, d).getDay()];
}

export function initials(name = "") {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0])
    .join("")
    .toUpperCase();
}
