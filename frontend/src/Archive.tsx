import { useState } from "react";
import type { EventRow } from "./types";

type Result = { items: (EventRow & { aircraft: string })[]; next: number | null };

export function Archive() {
  const [query, setQuery] = useState("");
  const [severity, setSeverity] = useState("");
  const [applied, setApplied] = useState("");
  const [result, setResult] = useState<Result | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function search(more = false) {
    setBusy(true);
    setError("");
    const params = more ? new URLSearchParams(applied) : new URLSearchParams({ q: query });
    if (!more && severity) params.set("severity", severity);
    if (more && result?.next) params.set("before", String(result.next));
    try {
      const response = await fetch("/api/archive?" + params);
      if (!response.ok) throw Error("Archive unavailable. Try the search again.");
      const page: Result = await response.json();
      if (!more) setApplied(params.toString());
      setResult({items: more ? [...(result?.items ?? []), ...page.items] : page.items, next: page.next});
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function download() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(result?.items, null, 2)], {type:"application/json"}));
    const link = document.createElement("a");
    link.href = url;
    link.download = "skysentinel-incidents.json";
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <details className="archive"><summary>Investigate past incidents</summary>
    <form onSubmit={e => { e.preventDefault(); void search(); }}>
      <label>Search history<input type="search" value={query} maxLength={100}
        onChange={e=>setQuery(e.target.value)} placeholder="Aircraft, event or status" /></label>
      <label>Severity<select value={severity} onChange={e=>setSeverity(e.target.value)}>
        <option value="">All severities</option>{["Info","Medium","High"].map(s=><option key={s}>{s}</option>)}
      </select></label>
      <button disabled={busy}>Search archive</button>
    </form>
    {error && <p role="alert">{error}</p>}
    <div role="status">{busy ? "Searching…" : result && (result.items.length ? result.items.length+" records loaded" : "No matching incidents")}</div>
    {result && result.items.length>0 && <><ol>{result.items.map(e=><li key={e.id}>
      <time dateTime={e.time}>{new Date(e.time).toLocaleString()}</time><div><strong>{e.kind}</strong><p>{e.aircraft} · {e.detail}</p></div>
      <span>{e.severity}</span><span>{e.status}</span></li>)}</ol>
      {result.next && <button disabled={busy} onClick={()=>search(true)}>Load older records</button>}
      <button onClick={download}>Export loaded records</button></>}
  </details>;
}
