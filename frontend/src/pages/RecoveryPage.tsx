import { useEffect, useState } from "react";
import type { Drone } from "../types";

const ACTIONS = [
  {
    name: "Return to Home",
    desc: "Simulated autonomous navigation back to home coordinates along trusted corridor.",
  },
  {
    name: "Attitude Hold",
    desc: "Simulated inertial hover holding the last verified trusted GPS fix.",
  },
  {
    name: "Manual Override",
    desc: "Transfers simulated control authority to an authorized ground operator.",
  },
  {
    name: "Emergency Motor Disarm",
    desc: "Simulated emergency motor cut-off (simulation-only safety safeguard).",
  },
  {
    name: "Resume Patrol",
    desc: "Releases aircraft back into simulated normal patrol after threat clearance.",
  },
];

export function RecoveryPage({
  fleet,
  role,
  requestApi,
  onChanged,
}: {
  fleet: Drone[];
  role: "viewer" | "operator";
  requestApi: (path: string, options?: RequestInit) => Promise<any>;
  onChanged: () => Promise<void>;
}) {
  const [history, setHistory] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  async function load() {
    const res = await requestApi("recoveries");
    setHistory(res.items);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [fleet]);

  async function executeAction(droneId: number, action: string, recoveryId?: number, reason?: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const res = await requestApi(`drones/${droneId}/recover`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Sky-Command": "1" },
        body: JSON.stringify({ action, recovery_id: recoveryId, reason }),
      });
      setNotice(`Simulated recovery '${res.action}' completed (${res.status}). Aircraft mode: ${res.mode}.`);
      await load();
      await onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const pendingRecommendations = history.filter((h) => h.status === "Recommended");

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      <div className="card">
        <small>AUTONOMOUS RECOVERY SYSTEM · [SIMULATED FAIL-SAFE]</small>
        <h2>Incident Recovery &amp; Operator Override</h2>
        <p style={{ color: "var(--muted)", margin: "0.35rem 0 0" }}>
          All recovery actions are simulated safely in software unless integrated with verified hardware interlocks. Initiating recovery logs an alert and records the outcome.
        </p>
      </div>

      {error && <p className="error" role="alert">{error}</p>}
      {notice && <p className="notice" role="status">{notice}</p>}

      {pendingRecommendations.length > 0 && (
        <div className="card" style={{ borderColor: "rgba(239,68,68,0.5)" }}>
          <small>RECOMMENDED ACTIONS</small>
          <h2>Active Recovery Recommendations ({pendingRecommendations.length})</h2>
          <div style={{ display: "grid", gap: "0.85rem", marginTop: "0.75rem" }}>
            {pendingRecommendations.map((rec) => (
              <div key={rec.id} className="card" style={{ background: "var(--bg-elev)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: "0.5rem" }}>
                  <div>
                    <strong>{rec.drone_name} ({rec.drone_code})</strong> · Recommended:{" "}
                    <span className="pill warn">{rec.recommended_action}</span>
                    <p style={{ margin: "0.3rem 0", color: "var(--muted)" }}>{rec.recommendation_reason}</p>
                  </div>
                </div>
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", marginTop: "0.5rem" }}>
                  {ACTIONS.slice(0, 4).map((act) => (
                    <button
                      key={act.name}
                      className={act.name === rec.recommended_action ? "primary" : act.name === "Emergency Motor Disarm" ? "danger-btn" : ""}
                      disabled={busy || role === "viewer"}
                      onClick={() => void executeAction(rec.drone_id, act.name, rec.id, rec.recommendation_reason)}
                    >
                      {act.name}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="card">
        <small>FLEET RECOVERY CONTROLS</small>
        <h2>Per-Drone Recovery Controls</h2>
        <div className="grid-3" style={{ marginTop: "0.75rem" }}>
          {fleet.map((d) => (
            <div key={d.id} className="card" style={{ background: "var(--bg-elev)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <strong>{d.name}</strong>
                <span className={`pill ${d.mode === "Patrol" ? "" : "warn"}`}>{d.mode}</span>
              </div>
              <p style={{ fontSize: "0.82rem", color: "var(--muted)", margin: "0.4rem 0 0.75rem" }}>
                GPS: {d.gps_status ?? "Connected"} · Comms: {d.comm_status ?? "Encrypted"}
              </p>
              <div style={{ display: "grid", gap: "0.4rem" }}>
                {ACTIONS.map((act) => (
                  <button
                    key={act.name}
                    className={act.name === "Emergency Motor Disarm" ? "danger-btn" : act.name === "Return to Home" ? "primary" : ""}
                    disabled={busy || role === "viewer"}
                    title={act.desc}
                    onClick={() => void executeAction(d.id, act.name)}
                  >
                    {act.name}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <small>RECOVERY AUDIT TRAIL</small>
        <h2>Recovery History ({history.length})</h2>
        <div className="table-wrap" style={{ marginTop: "0.75rem" }}>
          <table>
            <thead>
              <tr>
                <th>Time (UTC)</th>
                <th>Drone</th>
                <th>Recommended</th>
                <th>Selected Action</th>
                <th>Status</th>
                <th>Reason / Outcome</th>
              </tr>
            </thead>
            <tbody>
              {history.map((r) => (
                <tr key={r.id}>
                  <td>{new Date(r.created_at).toLocaleTimeString("en-GB", { timeZone: "UTC" })}</td>
                  <td>{r.drone_name} {r.simulated && <span className="pill warn">SIM</span>}</td>
                  <td>{r.recommended_action}</td>
                  <td>{r.selected_action ?? "Pending"}</td>
                  <td><span className={`pill ${r.status === "Successful" ? "" : r.status === "Failed" ? "danger" : "warn"}`}>{r.status}</span></td>
                  <td>{r.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
