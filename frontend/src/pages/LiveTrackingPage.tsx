import { useState } from "react";
import { Chart } from "../Chart";
import type { Drone } from "../types";

export function LiveTrackingPage({
  fleet,
  selected,
  onSelect,
}: {
  fleet: Drone[];
  selected: Drone;
  onSelect: (id: number) => void;
}) {
  const [showAll, setShowAll] = useState(true);
  const latest = selected.track.at(-1);

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      <div className="card">
        <div className="sectionHead" style={{ padding: 0, marginBottom: "0.85rem", flexWrap: "wrap" }}>
          <div>
            <small>LIVE GPS TRACKING &amp; CORRIDOR COMPARISON</small>
            <h2>Multi-Drone Tactical Map</h2>
          </div>
          <div style={{ display: "flex", gap: "0.6rem", alignItems: "center" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "0.4rem", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={showAll}
                onChange={(e) => setShowAll(e.target.checked)}
              />
              Show all drones simultaneously
            </label>
            <select
              aria-label="Focus aircraft"
              value={selected.id}
              onChange={(e) => onSelect(Number(e.target.value))}
            >
              {fleet.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.code ?? `DRN-00${d.id + 1}`} · {d.name}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div style={{ height: "440px", display: "flex", flexDirection: "column" }}>
          <Chart
            fleet={fleet}
            selected={selected}
            showAllDrones={showAll}
            onSelectDrone={onSelect}
          />
        </div>
        <div className="legend" style={{ paddingBottom: 0 }}>
          <span>┄ Planned flight route</span>
          <span>━ Actual reported GPS path</span>
          <span style={{ color: "#ef4444" }}>● Suspicious / deviated position</span>
          <span>✈ Trusted inertial fix</span>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <small>SELECTED MARKER TELEMETRY · {selected.code ?? `DRN-00${selected.id + 1}`}</small>
          <h2>{selected.name} Live Fix</h2>
          {latest ? (
            <dl>
              <div><dt>Reported Lat / Lon</dt><dd>{latest.reading.latitude.toFixed(5)}, {latest.reading.longitude.toFixed(5)}</dd></div>
              <div><dt>Expected Lat / Lon</dt><dd>{latest.expected[0].toFixed(5)}, {latest.expected[1].toFixed(5)}</dd></div>
              <div><dt>Corridor Deviation</dt><dd>{(latest.deviation_m ?? 0).toFixed(1)} m</dd></div>
              <div><dt>Classification</dt><dd>{latest.classification ?? "Normal"}</dd></div>
              <div><dt>Speed / Signal</dt><dd>{latest.reading.speed.toFixed(1)} km/h · {latest.reading.signal.toFixed(1)}%</dd></div>
              <div><dt>GPS / Mode</dt><dd>{selected.gps_status ?? "Connected"} · {selected.mode}</dd></div>
            </dl>
          ) : (
            <p style={{ color: "var(--muted)" }}>No telemetry history recorded yet.</p>
          )}
        </div>

        <div className="card">
          <small>MOVEMENT &amp; LOCATION HISTORY</small>
          <h2>Recent Waypoints ({selected.track.length})</h2>
          <div className="table-wrap" style={{ maxHeight: "260px", overflowY: "auto" }}>
            <table>
              <thead>
                <tr>
                  <th>Seq</th>
                  <th>Reported GPS</th>
                  <th>Deviation</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {[...selected.track].reverse().slice(0, 12).map((s) => (
                  <tr key={s.seq}>
                    <td>#{s.seq}</td>
                    <td>{s.reading.latitude.toFixed(4)}, {s.reading.longitude.toFixed(4)}</td>
                    <td>{(s.deviation_m ?? 0).toFixed(1)} m</td>
                    <td>
                      <span className={`pill ${s.classification === "GPS Spoofed" ? "danger" : ""}`}>
                        {s.classification ?? "Normal"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}
