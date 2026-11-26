import { useEffect, useState } from "react";
import type { AlertRow } from "../types";

export function AlertsPage({
  role,
  soundEnabled,
  onToggleSound,
  requestApi,
  onChanged,
}: {
  role: "viewer" | "operator";
  soundEnabled: boolean;
  onToggleSound: () => void;
  requestApi: (path: string, options?: RequestInit) => Promise<any>;
  onChanged: () => Promise<void>;
}) {
  const [items, setItems] = useState<AlertRow[]>([]);
  const [attackTypes, setAttackTypes] = useState<string[]>([]);
  const [q, setQ] = useState("");
  const [severity, setSeverity] = useState("");
  const [attackType, setAttackType] = useState("");
  const [selected, setSelected] = useState<AlertRow | null>(null);
  const [busyId, setBusyId] = useState<number | null>(null);

  async function load() {
    const params = new URLSearchParams();
    if (q.trim()) params.set("q", q.trim());
    if (severity) params.set("severity", severity);
    if (attackType) params.set("attack_type", attackType);
    const res = await requestApi("alerts?" + params.toString());
    setItems(res.items);
    setAttackTypes(res.attack_types);
  }

  useEffect(() => {
    load().catch(() => {});
    const t = setInterval(() => void load().catch(() => {}), 4500);
    return () => clearInterval(t);
  }, [q, severity, attackType]);

  async function act(id: number, action: "acknowledge" | "resolve") {
    setBusyId(id);
    try {
      await requestApi(`alerts/${id}/${action}`, {
        method: "POST",
        headers: { "X-Sky-Command": "1" },
      });
      await load();
      await onChanged();
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      <div className="card">
        <div className="sectionHead" style={{ padding: 0, marginBottom: "0.9rem", flexWrap: "wrap" }}>
          <div>
            <small>REAL-TIME SECURITY ALERT CENTRE</small>
            <h2>Live Alerts &amp; Notification History ({items.length})</h2>
          </div>
          <div style={{ display: "flex", gap: "0.55rem", flexWrap: "wrap", alignItems: "center" }}>
            <button onClick={onToggleSound}>
              {soundEnabled ? "🔊 Critical Sound: ON" : "🔇 Critical Sound: OFF"}
            </button>
            <input
              type="search"
              placeholder="Search alert ID, drone, type..."
              aria-label="Search alerts"
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
            <select value={severity} onChange={(e) => setSeverity(e.target.value)} aria-label="Filter alerts by severity">
              <option value="">All severities</option>
              <option value="Critical">Critical</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
            </select>
            <select value={attackType} onChange={(e) => setAttackType(e.target.value)} aria-label="Filter alerts by attack type">
              <option value="">All attack types</option>
              {attackTypes.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
        </div>

        {selected && (
          <div className="card" style={{ background: "var(--bg-elev)", marginBottom: "1rem" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <strong>{selected.alert_code} · {selected.attack_type}</strong>
              <button onClick={() => setSelected(null)}>Close</button>
            </div>
            <p style={{ margin: "0.4rem 0" }}>{selected.description}</p>
            <small>
              Drone: {selected.drone_name} ({selected.drone_code}) · Severity: {selected.severity} · Confidence:{" "}
              {selected.confidence != null ? `${selected.confidence}%` : "N/A"} · Time: {new Date(selected.created_at).toLocaleString()} · Status: {selected.status}
            </small>
          </div>
        )}

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Alert ID</th>
                <th>Drone</th>
                <th>Attack Type</th>
                <th>Severity</th>
                <th>Confidence</th>
                <th>Date &amp; Time</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((a) => (
                <tr key={a.id}>
                  <td><code>{a.alert_code}</code> {a.simulated && <span className="pill warn">SIM</span>}</td>
                  <td>{a.drone_name} ({a.drone_code})</td>
                  <td>{a.attack_type}</td>
                  <td><span className={"severity " + a.severity}>{a.severity}</span></td>
                  <td>{a.confidence != null ? `${a.confidence}%` : "—"}</td>
                  <td>{new Date(a.created_at).toLocaleString()}</td>
                  <td><span className={`pill ${a.status === "Active" ? "danger" : a.status === "Acknowledged" ? "warn" : ""}`}>{a.status}</span></td>
                  <td style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                    <button onClick={() => setSelected(a)}>Details</button>
                    {a.status === "Active" && (
                      <button disabled={busyId === a.id || role === "viewer"} onClick={() => void act(a.id, "acknowledge")}>
                        Ack
                      </button>
                    )}
                    {a.status !== "Resolved" && (
                      <button className="primary" disabled={busyId === a.id || role === "viewer"} onClick={() => void act(a.id, "resolve")}>
                        Resolve
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
