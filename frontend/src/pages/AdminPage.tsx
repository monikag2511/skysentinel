import { useEffect, useState } from "react";
import type { NavSection } from "../types";

export function AdminPage({
  role,
  requestApi,
  onChanged,
  onNavigate,
}: {
  role: "viewer" | "operator";
  requestApi: (path: string, options?: RequestInit) => Promise<any>;
  onChanged: () => Promise<void>;
  onNavigate: (s: NavSection) => void;
}) {
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [thresholds, setThresholds] = useState<any | null>(null);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  async function load() {
    const [settingsRes, auditRes] = await Promise.all([
      requestApi("admin/settings"),
      requestApi("admin/audit-logs"),
    ]);
    setThresholds(settingsRes.thresholds);
    setAuditLogs(auditRes.items);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [role]);

  async function login(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const res = await requestApi("auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      });
      setPassword("");
      setNotice(`Signed in as ${res.username} (${res.role}).`);
      await onChanged();
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await requestApi("auth/logout", { method: "POST" });
      setNotice("Signed out. Sensitive operations are now restricted (viewer mode).");
      await onChanged();
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function saveThresholds(e: React.FormEvent) {
    e.preventDefault();
    if (!thresholds) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      const res = await requestApi("admin/settings", {
        method: "PUT",
        headers: { "Content-Type": "application/json", "X-Sky-Command": "1" },
        body: JSON.stringify(thresholds),
      });
      setThresholds(res.thresholds);
      setNotice("Detection thresholds updated across all monitoring modules.");
      await onChanged();
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      {error && <p className="error" role="alert">{error}</p>}
      {notice && <p className="notice" role="status">{notice}</p>}

      <div className="grid-2">
        <div className="card">
          <small>ADMIN AUTHENTICATION &amp; ACCESS CONTROL</small>
          <h2>Session Control ({role === "operator" ? "Administrator Unlocked" : "Read-Only Viewer"})</h2>
          <p style={{ color: "var(--muted)", fontSize: "0.88rem" }}>
            Sensitive operations (drone CRUD, threshold changes, device blocking, attack simulation, recovery, alert resolution) require Administrator/Operator privileges. Use your configured <code>SKY_OPERATOR_PASSWORD</code> (or <code>skysentinel-admin</code> if unset in dev).
          </p>
          <form onSubmit={login} style={{ display: "grid", gap: "0.65rem" }}>
            <label>
              Username
              <select value={username} onChange={(e) => setUsername(e.target.value)} style={{ width: "100%", marginTop: "0.25rem" }}>
                <option value="admin">admin (Full Control)</option>
                <option value="operator">operator (Full Control)</option>
                <option value="viewer">viewer (Read-Only)</option>
              </select>
            </label>
            <label>
              Password
              <input
                type="password"
                required
                placeholder="Enter role password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                style={{ width: "100%", marginTop: "0.25rem" }}
              />
            </label>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button className="primary" type="submit" disabled={busy}>Admin Login</button>
              <button className="danger-btn" type="button" disabled={busy} onClick={() => void logout()}>
                Logout (Lock Controls)
              </button>
            </div>
          </form>
        </div>

        <div className="card">
          <small>DETECTION THRESHOLD CONFIGURATION</small>
          <h2>Security &amp; ML Thresholds</h2>
          {thresholds && (
            <form onSubmit={saveThresholds} style={{ display: "grid", gap: "0.6rem", marginTop: "0.5rem" }}>
              <div className="grid-2">
                <label>
                  Route Deviation (m)
                  <input
                    type="number"
                    value={thresholds.deviation_threshold_m}
                    onChange={(e) => setThresholds({ ...thresholds, deviation_threshold_m: Number(e.target.value) })}
                    style={{ width: "100%" }}
                  />
                </label>
                <label>
                  ML Spoof Score (0-1)
                  <input
                    type="number"
                    step="0.05"
                    min="0.1"
                    max="0.99"
                    value={thresholds.spoof_score_threshold}
                    onChange={(e) => setThresholds({ ...thresholds, spoof_score_threshold: Number(e.target.value) })}
                    style={{ width: "100%" }}
                  />
                </label>
                <label>
                  Max Speed (km/h)
                  <input
                    type="number"
                    value={thresholds.speed_threshold_kmh}
                    onChange={(e) => setThresholds({ ...thresholds, speed_threshold_kmh: Number(e.target.value) })}
                    style={{ width: "100%" }}
                  />
                </label>
                <label>
                  Max Accel (m/s²)
                  <input
                    type="number"
                    step="0.1"
                    value={thresholds.accel_threshold_ms2}
                    onChange={(e) => setThresholds({ ...thresholds, accel_threshold_ms2: Number(e.target.value) })}
                    style={{ width: "100%" }}
                  />
                </label>
                <label>
                  Packet Rate Limit (/s)
                  <input
                    type="number"
                    value={thresholds.rate_limit_per_sec}
                    onChange={(e) => setThresholds({ ...thresholds, rate_limit_per_sec: Number(e.target.value) })}
                    style={{ width: "100%" }}
                  />
                </label>
                <label>
                  Low Battery Warning (%)
                  <input
                    type="number"
                    value={thresholds.low_battery_pct}
                    onChange={(e) => setThresholds({ ...thresholds, low_battery_pct: Number(e.target.value) })}
                    style={{ width: "100%" }}
                  />
                </label>
              </div>
              <button className="primary" type="submit" disabled={busy || role === "viewer"}>
                Save Thresholds
              </button>
            </form>
          )}
        </div>
      </div>

      <div className="card">
        <small>ADMINISTRATIVE QUICK LINKS</small>
        <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap", marginTop: "0.5rem" }}>
          <button onClick={() => onNavigate("drones")}>Manage Registered Drones</button>
          <button onClick={() => onNavigate("network")}>Manage Trusted Devices</button>
          <button onClick={() => onNavigate("alerts")}>Manage Security Alerts</button>
          <button onClick={() => onNavigate("logs")}>View Security Events</button>
        </div>
      </div>

      <div className="card">
        <small>SYSTEM ACTIVITY AUDIT</small>
        <h2>Administrator &amp; System Activity ({auditLogs.length})</h2>
        <div className="table-wrap" style={{ marginTop: "0.75rem" }}>
          <table>
            <thead>
              <tr>
                <th>Time (UTC)</th>
                <th>Actor</th>
                <th>Action</th>
                <th>Target</th>
                <th>Detail</th>
              </tr>
            </thead>
            <tbody>
              {auditLogs.map((a) => (
                <tr key={a.id}>
                  <td>{new Date(a.time).toLocaleString()}</td>
                  <td>{a.actor}</td>
                  <td><code>{a.action}</code></td>
                  <td>{a.target}</td>
                  <td>{a.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
