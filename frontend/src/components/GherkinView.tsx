const KW = /^(\s*)(Escenario|Esquema del escenario|Scenario|Dado|Dada|Dados|Dadas|Cuando|Entonces|Y|E|Pero|Given|When|Then|And|But)(:?)(\s.*)?$/i;

function renderRest(rest = "") {
  const parts = rest.split(/("[^"]*")/g);
  return parts.map((p, i) => (p.startsWith('"') ? <span key={i} className="gherkin-str">{p}</span> : <span key={i}>{p}</span>));
}

export default function GherkinView({ text }: { text: string }) {
  if (!text?.trim()) {
    return <div className="rounded-xl border border-dashed border-red-300 bg-red-50/50 px-4 py-6 text-center text-sm text-red-600">Sin criterios de aceptación — la Brújula bloquea esta historia.</div>;
  }
  return (
    <pre className="overflow-x-auto rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 font-mono text-[12.5px] leading-[1.7] text-slate-700">
      {text.split("\n").map((line, i) => {
        const m = line.match(KW);
        if (!m) return <div key={i}>{line || " "}</div>;
        const isSc = /^(escenario|esquema|scenario)/i.test(m[2]);
        return (
          <div key={i} className={isSc ? "mt-2 first:mt-0" : ""}>
            {m[1]}
            <span className={isSc ? "gherkin-sc" : "gherkin-kw"}>{m[2]}{m[3]}</span>
            {isSc ? <span className="gherkin-sc">{m[4]}</span> : renderRest(m[4])}
          </div>
        );
      })}
    </pre>
  );
}
