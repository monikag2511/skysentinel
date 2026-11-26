import { useState } from "react";
import type { DashboardData, DroneHealth } from "../types";

export function FleetHealthPage({
  dashboard,
  onSelectDrone,
  requestApi,
}: {
  dashboard: DashboardData | null;
  onSelectDrone: (id: number) => void;
  requestApi: (path: string) => Promise<any>;
}) {
  const [selectedReport, setSelectedReport] = useState<any | null>(null);
  const [loadingId, setLoadingId] = useState<number | null>(null);

  async function openReport(drone: DroneHealth) {
    setLoadingId(drone.id);
    try {
      const data = await requestApi(`drones/${drone.id}/report`);
      setSelectedReport(data);
    } finally {
      setLoadingId(null);
    }
  }

  function downloadDroneReport() {
    if (!selectedReport) return;
    const blob = new Blob([JSON.stringify(selectedReport, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${selectedReport.drone.code.toLowerCase()}-security-report.json`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  if (!dashboard) return <p role="status">Loading fleet health telemetry…</p>;

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      <div className="card">
        <div className="sectionHead" style={{ padding: 0, marginBottom: "1rem" }}>
          <div>
            <small>MULTI-DRONE &amp; HEALTH MONITORING</small>
            <h2>Fleet Health &amp; Security Matrix</h2>
          </div>
          <span className="pill">{dashboard.drone_health.length} Drones Monitored</span>
        </div>

        <div className="grid-3">
          {dashboard.drone_health.map((d) => {
            const isDanger = d.security_status === "GPS Spoofed";
            const isWarn = d.warnings.length > 0 || d.security_status === "Network Warning";
            return (
              <div
                key={d.id}
                className="card"
                style={{
                  borderColor: isDanger ? "rgba(239,68,68,0.6)" : isWarn ? "rgba(245,158,11,0.5)" : "var(--border)",
                }}
              >
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                  <div>
                    <small>{d.code}</small>
                    <h3 style={{ margin: 0 }}>{d.name}</h3>
                    <span style={{ fontSize: "0.8rem", color: "var(--muted)" }}>{d.model_type}</span>
                  </div>
                  <span className={`pill ${isDanger ? "danger" : isWarn ? "warn" : ""}`}>
                    {d.security_status}
                  </span>
                </div>

                <dl style={{ margin: "0.85rem 0" }}>
                  <div>
                    <dt>Battery</dt>
                    <dd style={{ color: d.battery < 25 ? "#f87171" : undefined }}>{d.battery}%</dd>
                  </div>
                  <div>
                    <dt>Altitude</dt>
                    <dd>{d.altitude} m</dd>
                  </div>
                  <div>
                    <dt>Speed</dt>
                    <dd>{d.speed} km/h</dd>
                  </div>
                  <div>
                    <dt>GPS Signal</dt>
                    <dd>{d.signal}%</dd>
                  </div>
                  <div>
                    <dt>GPS Status</dt>
                    <dd>{d.gps_status}</dd>
                  </div>
                  <div>
                    <dt>Network / Comm</dt>
                    <dd>{d.comm_status}</dd>
                  </div>
                  <div>
                    <dt>Sensor Status</dt>
                    <dd>{d.sensor_status}</dd>
                  </div>
                  <div>
                    <dt>Flight Status</dt>
                    <dd>{d.flight_status}</dd>
                  </div>
                </dl>

                {d.warnings.length > 0 && (
                  <div className="error" style={{ marginBottom: "0.75rem", padding: "0.55rem 0.75rem" }}>
                    {d.warnings.map((w, idx) => (
                      <div key={idx} style={{ fontSize: "0.82rem" }}>
                        ⚠ {w}
                      </div>
                    ))}
                  </div>
                )}

                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
                  <button
                    className="primary"
                    disabled={loadingId === d.id}
                    onClick={() => void openReport(d)}
                  >
                    {loadingId === d.id ? "Loading…" : "Security Report & Activity"}
                  </button>
                  <button onClick={() => onSelectDrone(d.id)}>Focus on Map</button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {selectedReport && (
        <div className="card">
          <div className="sectionHead" style={{ padding: 0, marginBottom: "0.75rem" }}>
            <div>
              <small>INDIVIDUAL DRONE REPORT · {selectedReport.drone.code}</small>
              <h2>{selectedReport.drone.name} Activity &amp; Security Report</h2>
            </div>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button className="primary" onClick={downloadDroneReport}>
                Export JSON Report
              </button>
              <button onClick={() => setSelectedReport(null)}>Close</button>
            </div>
          </div>

          <div className="grid-2">
            <div>
              <h3>Recent Alerts ({selectedReport.alerts.length})</h3>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Code</th>
                      <th>Attack</th>
                      <th>Severity</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedReport.alerts.slice(0, 8).map((a: any) => (
                      <tr key={a.id}>
                        <td>{a.alert_code}</td>
                        <td>{a.attack_type}</td>
                        <td className={"severity " + a.severity}>{a.severity}</td>
                        <td>{a.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            <div>
              <h3>Activity History ({selectedReport.events.length})</h3>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Time</th>
                      <th>Kind</th>
                      <th>Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {selectedReport.events.slice(0, 8).map((e: any) => (
                      <tr key={e.id}>
                        <td>{new Date(e.time).toLocaleTimeString("en-GB", { timeZone: "UTC" })}</td>
                        <td>{e.kind}</td>
                        <td>{e.detail}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
