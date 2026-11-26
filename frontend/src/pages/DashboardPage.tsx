import type { DashboardData, NavSection } from "../types";

export function DashboardOverview({
  dashboard,
  onNavigate,
}: {
  dashboard: DashboardData | null;
  onNavigate: (s: NavSection) => void;
}) {
  if (!dashboard) return null;
  const s = dashboard.stats;
  const netCls =
    s.network_security_status === "Compromised"
      ? "danger"
      : s.network_security_status === "Warning"
        ? "warn"
        : "ok";
  const gpsCls =
    s.gps_security_status === "Under Attack"
      ? "danger"
      : s.gps_security_status === "Alert"
        ? "warn"
        : "ok";

  return (
    <section aria-label="Security dashboard summary" style={{ marginBottom: "1.25rem" }}>
      <div className="kpi-grid">
        <button className="kpi-card" onClick={() => onNavigate("drones")}>
          <small>REGISTERED DRONES</small>
          <strong>{s.total_registered}</strong>
          <span>Manage fleet registry</span>
        </button>
        <button className="kpi-card ok" onClick={() => onNavigate("health")}>
          <small>CURRENTLY ACTIVE</small>
          <strong>{s.active_drones}</strong>
          <span>{s.normal_drones} operating normally</span>
        </button>
        <button
          className={`kpi-card ${s.spoofed_drones > 0 ? "danger" : "ok"}`}
          onClick={() => onNavigate("ml")}
        >
          <small>GPS SPOOFED DRONES</small>
          <strong>{s.spoofed_drones}</strong>
          <span>{s.spoofed_drones > 0 ? "Hold / recovery active" : "All corridors clean"}</span>
        </button>
        <button
          className={`kpi-card ${s.total_cyberattacks > 0 ? "warn" : "ok"}`}
          onClick={() => onNavigate("logs")}
        >
          <small>DETECTED CYBERATTACKS</small>
          <strong>{s.total_cyberattacks}</strong>
          <span>Across GPS &amp; network links</span>
        </button>
        <button
          className={`kpi-card ${s.critical_alerts > 0 ? "danger" : "ok"}`}
          onClick={() => onNavigate("alerts")}
        >
          <small>CRITICAL / HIGH ALERTS</small>
          <strong>{s.critical_alerts}</strong>
          <span>{s.active_alerts} total active alerts</span>
        </button>
        <button className={`kpi-card ${netCls}`} onClick={() => onNavigate("network")}>
          <small>NETWORK SECURITY</small>
          <strong>{s.network_security_status}</strong>
          <span>AES-256-GCM link status</span>
        </button>
        <button className={`kpi-card ${gpsCls}`} onClick={() => onNavigate("tracking")}>
          <small>GPS SECURITY STATUS</small>
          <strong>{s.gps_security_status}</strong>
          <span>ML + corridor verification</span>
        </button>
      </div>

      <div className="grid-2">
        <div className="card">
          <div className="sectionHead" style={{ padding: 0, marginBottom: "0.75rem" }}>
            <div>
              <small>THREAT FEED</small>
              <h2>Recent attack history</h2>
            </div>
            <button onClick={() => onNavigate("alerts")}>Alert Centre</button>
          </div>
          {dashboard.recent_attacks.length === 0 ? (
            <p style={{ color: "var(--muted)", margin: 0 }}>
              No cyberattacks detected yet. Use Attack Simulation or Flight Watch scenarios to test defenses.
            </p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Alert</th>
                    <th>Drone</th>
                    <th>Attack Type</th>
                    <th>Severity</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {dashboard.recent_attacks.slice(0, 6).map((a) => (
                    <tr key={a.id}>
                      <td>
                        <code>{a.alert_code}</code> {a.simulated && <span className="pill warn">SIM</span>}
                      </td>
                      <td>{a.drone_name}</td>
                      <td>{a.attack_type}</td>
                      <td>
                        <span className={"severity " + a.severity}>{a.severity}</span>
                      </td>
                      <td>{a.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="card">
          <div className="sectionHead" style={{ padding: 0, marginBottom: "0.75rem" }}>
            <div>
              <small>TELEMETRY STREAM</small>
              <h2>Latest drone activity</h2>
            </div>
            <button onClick={() => onNavigate("logs")}>All Logs</button>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Time (UTC)</th>
                  <th>Drone</th>
                  <th>Event</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {dashboard.latest_activity.slice(0, 6).map((e) => (
                  <tr key={e.id}>
                    <td>{new Date(e.time).toLocaleTimeString("en-GB", { timeZone: "UTC" })}</td>
                    <td>{e.drone_name}</td>
                    <td>{e.kind}</td>
                    <td>{e.status}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
  );
}
