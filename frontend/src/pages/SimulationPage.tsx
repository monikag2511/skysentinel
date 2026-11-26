import { useState } from "react";
import type { Drone } from "../types";

const ATTACK_OPTIONS = [
  {
    key: "gps_spoofing",
    label: "GPS Spoofing Attack",
    severity: "Critical",
    desc: "Injects spoofed coordinates, high speed, and low signal strength across consecutive frames to trigger ML detection and Attitude Hold.",
  },
  {
    key: "unauthorized_device",
    label: "Unauthorized Device Access",
    severity: "High",
    desc: "Transmits telemetry from an unknown node UID (UNKNOWN-NODE-FF) without cryptographic trust.",
  },
  {
    key: "packet_injection",
    label: "Packet Injection Attempt",
    severity: "High",
    desc: "Modifies encrypted telemetry ciphertext in transit to fail AES-256-GCM authentication tag checks.",
  },
  {
    key: "replay_attack",
    label: "Replay Attack",
    severity: "Medium",
    desc: "Re-submits a previously accepted sequence number to test anti-replay protection.",
  },
  {
    key: "suspicious_traffic",
    label: "Suspicious Network Traffic",
    severity: "Critical",
    desc: "Triggers a packet flood exceeding rate limits alongside a simulated MITM probe.",
  },
  {
    key: "abnormal_location",
    label: "Abnormal Drone Location Changes",
    severity: "Critical",
    desc: "Generates a sudden 500m+ coordinate jump outside the planned corridor and flags route deviation.",
  },
  {
    key: "comm_interruption",
    label: "Communication Interruption",
    severity: "Critical",
    desc: "Simulates control-link RF heartbeat loss and engages fail-safe Attitude Hold with Return to Home recommendation.",
  },
];

export function SimulationPage({
  fleet,
  role,
  requestApi,
  onChanged,
  onNavigateRecovery,
}: {
  fleet: Drone[];
  role: "viewer" | "operator";
  requestApi: (path: string, options?: RequestInit) => Promise<any>;
  onChanged: () => Promise<void>;
  onNavigateRecovery: () => void;
}) {
  const [droneId, setDroneId] = useState(fleet[0]?.id ?? 0);
  const [busyKey, setBusyKey] = useState("");
  const [lastResult, setLastResult] = useState<any | null>(null);
  const [error, setError] = useState("");

  async function trigger(attackKey: string) {
    setBusyKey(attackKey);
    setError("");
    try {
      const res = await requestApi("simulations/run", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Sky-Command": "1" },
        body: JSON.stringify({ drone_id: droneId, attack_type: attackKey }),
      });
      setLastResult(res);
      await onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusyKey("");
    }
  }

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      <div className="card">
        <div className="sectionHead" style={{ padding: 0, marginBottom: "0.75rem", flexWrap: "wrap" }}>
          <div>
            <small>CONTROLLED CYBER RANGE · [SIMULATED EVENTS ONLY]</small>
            <h2>Attack Simulation Centre</h2>
          </div>
          <div style={{ display: "flex", gap: "0.6rem", alignItems: "center" }}>
            <label>
              Target Drone{" "}
              <select
                value={droneId}
                onChange={(e) => setDroneId(Number(e.target.value))}
                aria-label="Simulation target drone"
              >
                {fleet.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.code ?? `DRN-00${d.id + 1}`} · {d.name} ({d.mode})
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>
        <p style={{ color: "var(--muted)", margin: 0 }}>
          All actions here are clearly tagged <strong>[SIMULATED]</strong>. Each simulation executes the full end-to-end pipeline: activity generation, ML/crypto/network analysis, threat classification, security alert creation, dashboard update, log persistence, and recovery recommendation.
        </p>
      </div>

      {error && <p className="error" role="alert">{error}</p>}

      {lastResult && (
        <div className="card" style={{ borderColor: "rgba(245,158,11,0.5)" }}>
          <div className="sectionHead" style={{ padding: 0, marginBottom: "0.5rem" }}>
            <div>
              <small>[SIMULATED] EXECUTION TRACE</small>
              <h2>Completed: {ATTACK_OPTIONS.find((a) => a.key === lastResult.attack_type)?.label}</h2>
            </div>
            <button className="primary" onClick={onNavigateRecovery}>
              Open Recovery Console
            </button>
          </div>
          <ul style={{ margin: "0.5rem 0 0", paddingLeft: "1.2rem", display: "grid", gap: "0.3rem" }}>
            {lastResult.steps.map((s: string, idx: number) => (
              <li key={idx} style={{ display: "list-item", border: 0, padding: "0.15rem 0" }}>{s}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="grid-3">
        {ATTACK_OPTIONS.map((opt) => (
          <div key={opt.key} className="card" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", gap: "0.8rem" }}>
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "0.4rem" }}>
                <span className="pill warn">SIMULATED</span>
                <span className={"severity " + opt.severity}>{opt.severity}</span>
              </div>
              <h3>{opt.label}</h3>
              <p style={{ color: "var(--muted)", fontSize: "0.88rem", margin: "0.35rem 0 0" }}>
                {opt.desc}
              </p>
            </div>
            <button
              className="danger-btn"
              disabled={Boolean(busyKey) || role === "viewer"}
              onClick={() => void trigger(opt.key)}
            >
              {busyKey === opt.key ? "Simulating…" : `Simulate ${opt.label}`}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
