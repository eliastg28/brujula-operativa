import { useCallback, useEffect, useRef, useState } from "react";

/** Carga datos y los refresca cada `ms`. `reload()` fuerza un refresco inmediato. */
export function usePoll<T>(fetcher: () => Promise<T>, deps: any[], ms = 5000) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<any>(null);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const reload = useCallback(async () => {
    try {
      const d = await fetcherRef.current();
      setData(d);
      setError(null);
      return d;
    } catch (e) {
      setError(e);
      return null;
    }
  }, []);

  useEffect(() => {
    reload();
    if (!ms) return;
    const id = setInterval(reload, ms);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, reload, setData };
}

/** Re-render cada segundo (para contadores en vivo). */
export function useNow(ms = 1000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(id);
  }, [ms]);
  return now;
}

export function useHashRoute() {
  const [hash, setHash] = useState(() => window.location.hash || "#/ejecutiva");
  useEffect(() => {
    const on = () => setHash(window.location.hash || "#/ejecutiva");
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const parts = hash.replace(/^#\/?/, "").split("/");
  return { page: parts[0] || "ejecutiva", param: parts[1] };
}
