import { useEffect, useState } from "react";
import { Archive } from "../Archive";
import type { Drone } from "../types";

export function LogsPage({
  fleet,
  requestApi,
}: {
  fleet: Drone[];
  requestApi: (path: string) => Promise<any>;
}) {
  const [items, setItems] = useState<any[]>([]);
  const [kinds, setKinds] = useState<string[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [q, setQ] = useState("");
  const [droneId, setDroneId] = useState("");
  const [kind, setKind] = useState("");
  const [category, setCategory] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [selected, setSelected] = useState<any | null>(null);

  useEffect(() => {
    const params = new URLSearchParams();
    if (q.trim()) params.set("q", q.trim());
    if (droneId) params.set("drone_id", droneId);
    if (kind) params.set("attack_type", kind);
    if (category) params.set("category", category);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    requestApi("logs?" + params.toString())
      .then((res) => {
        setItems(res.items);
        setKinds(res.kinds);
        setCategories(res.categories);
      })
      .catch(() => {});
  }, [q, droneId, kind, category, dateFrom, dateTo, fleet]);

  function exportJson() {
    const url = URL.createObjectURL(new Blob([JSON.stringify(items, null, 2)], { type: "application/json" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "skysentinel-security-logs.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      <div className="card">
        <div className="sectionHead" style={{ padding: 0, marginBottom: "0.85rem", flexWrap: "wrap" }}>
          <div>
            <small>SECURITY LOGS &amp; INCIDENT HISTORY</small>
            <h2>Complete Audit &amp; Security Log ({items.length})</h2>
          </div>
          <button className="primary" onClick={exportJson}>Export Security History (JSON)</button>
        </div>

        <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap", marginBottom: "0.9rem" }}>
          <input type="search" placeholder="Search logs..." aria-label="Search logs" value={q} onChange={(e) => setQ(e.target.value)} />
          <select value={droneId} onChange={(e) => setDroneId(e.target.value)} aria-label="Filter logs by drone">
            <option value="">All drones</option>
            {fleet.map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
          <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Filter logs by category">
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <select value={kind} onChange={(e) => setKind(e.target.value)} aria-label="Filter logs by event type">
            <option value="">All event types</option>
            {kinds.map((k) => (
              <option key={k} value={k}>{k}</option>
            ))}
          </select>
          <input type="date" aria-label="Log date from" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
          <input type="date" aria-label="Log date to" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </div>

        {selected && (
          <div className="card" style={{ background: "var(--bg-elev)", marginBottom: "0.85rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <strong>Incident #{selected.id} · {selected.kind}</strong>
              <button onClick={() => setSelected(null)}>Close</button>
            </div>
            <p style={{ margin: "0.35rem 0" }}>{selected.detail}</p>
            <small>
              Drone: {selected.drone_name} · Category: {selected.category} · Severity: {selected.severity} · Status: {selected.status} · Time: {new Date(selected.time).toLocaleString()}
            </small>
          </div>
        )}

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Drone</th>
                <th>Category</th>
                <th>Event / Attack</th>
                <th>Severity</th>
                <th>Status</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {items.map((e) => (
                <tr key={e.id}>
                  <td>{new Date(e.time).toLocaleString()}</td>
                  <td>{e.drone_name}</td>
                  <td>{e.category ?? "Telemetry"}</td>
                  <td><strong>{e.kind}</strong> {e.simulated && <span className="pill warn">SIM</span>}</td>
                  <td className={"severity " + e.severity}>{e.severity}</td>
                  <td>{e.status}</td>
                  <td>
                    <button onClick={() => setSelected(e)}>Inspect</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card" style={{ padding: 0 }}>
        <Archive />
      </div>
    </div>
  );
}
