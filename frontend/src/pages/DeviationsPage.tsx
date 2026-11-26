import { useEffect, useState } from "react";
import type { Drone } from "../types";

export function DeviationsPage({
  fleet,
  requestApi,
  onFocusMap,
}: {
  fleet: Drone[];
  requestApi: (path: string) => Promise<any>;
  onFocusMap: (droneId: number) => void;
}) {
  const [items, setItems] = useState<any[]>([]);
  const [droneId, setDroneId] = useState("");
  const [severity, setSeverity] = useState("");

  useEffect(() => {
    const params = new URLSearchParams();
    if (droneId) params.set("drone_id", droneId);
    if (severity) params.set("severity", severity);
    requestApi("deviations?" + params.toString())
      .then((d) => setItems(d.items))
      .catch(() => {});
  }, [droneId, severity]);

  return (
    <div className="card">
      <div className="sectionHead" style={{ padding: 0, marginBottom: "1rem", flexWrap: "wrap" }}>
        <div>
          <small>FLIGHT PATH DEVIATION DETECTION</small>
          <h2>Route Deviation &amp; GPS Jump History ({items.length})</h2>
        </div>
        <div style={{ display: "flex", gap: "0.6rem" }}>
          <select value={droneId} onChange={(e) => setDroneId(e.target.value)} aria-label="Filter deviations by drone">
            <option value="">All drones</option>
            {fleet.map((d) => (
              <option key={d.id} value={d.id}>{d.name}</option>
            ))}
          </select>
          <select value={severity} onChange={(e) => setSeverity(e.target.value)} aria-label="Filter deviations by severity">
            <option value="">All severities</option>
            <option value="Critical">Critical</option>
            <option value="High">High</option>
            <option value="Medium">Medium</option>
          </select>
        </div>
      </div>

      {items.length === 0 ? (
        <p style={{ color: "var(--muted)" }}>
          No route deviations exceeding threshold recorded yet. Run a GPS deviation or Abnormal location simulation to inspect path warnings.
        </p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Time (UTC)</th>
                <th>Drone</th>
                <th>Expected</th>
                <th>Detected</th>
                <th>Offset / Jump</th>
                <th>Reason</th>
                <th>Map</th>
              </tr>
            </thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.id}>
                  <td>{new Date(r.time).toLocaleTimeString("en-GB", { timeZone: "UTC" })}</td>
                  <td>{r.drone_name} {r.simulated && <span className="pill warn">SIM</span>}</td>
                  <td>{r.expected_lat.toFixed(4)}, {r.expected_lon.toFixed(4)}</td>
                  <td>{r.detected_lat.toFixed(4)}, {r.detected_lon.toFixed(4)}</td>
                  <td>
                    <strong className={"severity " + r.severity}>{r.distance_m} m</strong>
                    <br />
                    <span style={{ color: "var(--muted)", fontSize: "0.78rem" }}>
                      Thresh {r.threshold_m}m · Jump {r.jump_m}m
                    </span>
                  </td>
                  <td>{r.reason}</td>
                  <td>
                    <button onClick={() => onFocusMap(r.drone_id)}>Highlight</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
