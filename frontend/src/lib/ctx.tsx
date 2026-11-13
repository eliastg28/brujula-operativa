import { createContext, useContext } from "react";

export type Toast = { id: number; title: string; body?: string; tone?: "ok" | "error" | "info" | "teams" | "warn" };

export type AppCtx = {
  squad: string;
  squads: any[];
  setSquad: (id: string) => void;
  health: any;
  toast: (t: Omit<Toast, "id">) => void;
  openStory: (key: string) => void;
  openInbox: () => void;
  bump: () => void;
  tick: number; // cambia cuando algo se modifica → las páginas recargan
};

export const Ctx = createContext<AppCtx>(null as any);
export const useApp = () => useContext(Ctx);
