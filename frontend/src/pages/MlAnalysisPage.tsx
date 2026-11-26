import { useEffect, useState } from "react";
import type { Drone } from "../types";

export function MlAnalysisPage({
  fleet,
  requestApi,
}: {
  fleet: Drone[];
  requestApi: (path: string) => Promise<any>;
}) {
  const [data, setData] = useState<any | null>(null);
  const [droneFilter, setDroneFilter] = useState("");
  const [clsFilter, setClsFilter] = useState("");
  const [selectedPred, setSelectedPred] = useState<any | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const params = new URLSearchParams();
    if (droneFilter) params.set("drone_id", droneFilter);
    if (clsFilter) params.set("classification", clsFilter);
    requestApi("ml/analysis?" + params.toString())
      .then((res) => {
        setData(res);
        setError("");
      })
      .catch((e) => setError(e.message));
  }, [droneFilter, clsFilter, fleet]);

  if (error) return <p className="error" role="alert">{error}</p>;
  if (!data) return <p role="status">Loading Random Forest evaluation and telemetry classifications…</p>;

  const ev = data.evaluation;
  const cm: number[][] = ev.confusion_matrix;
  const spoofMetrics = ev.metrics["1"];
  const importanceEntries = Object.entries(ev.importance as Record<string, number>).sort(
    (a, b) => b[1] - a[1],
  );
  const maxImp = Math.max(...importanceEntries.map(([, v]) => v), 0.01);

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      <div className="kpi-grid">
        <div className="kpi-card ok">
          <small>MODEL ACCURACY</small>
          <strong>{(ev.accuracy * 100).toFixed(2)}%</strong>
          <span>{ev.train} train / {ev.test} held-out</span>
        </div>
        <div className="kpi-card ok">
          <small>PRECISION (SPOOFED)</small>
          <strong>{(spoofMetrics.precision * 100).toFixed(2)}%</strong>
          <span>Random Forest (100 trees)</span>
        </div>
        <div className="kpi-card ok">
          <small>RECALL (SPOOFED)</small>
          <strong>{(spoofMetrics.recall * 100).toFixed(2)}%</strong>
          <span>Flight-level holdout</span>
        </div>
        <div className="kpi-card ok">
          <small>F1-SCORE</small>
          <strong>{spoofMetrics["f1-score"].toFixed(4)}</strong>
          <span>Seed {ev.seed}</span>
        </div>
        <div className="kpi-card">
          <small>LIVE NORMAL PREDICTIONS</small>
          <strong>{data.live_counts.normal}</strong>
          <span>Of {data.live_counts.total} telemetry fixes</span>
        </div>
        <div className={`kpi-card ${data.live_counts.spoofed > 0 ? "danger" : "ok"}`}>
          <small>LIVE SPOOFED PREDICTIONS</small>
          <strong>{data.live_counts.spoofed}</strong>
          <span>GPS Spoofing detections</span>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <small>HELD-OUT EVALUATION (N={ev.test})</small>
          <h2>Confusion Matrix</h2>
          <div className="table-wrap" style={{ marginTop: "0.75rem" }}>
            <table>
              <thead>
                <tr>
                  <th>Actual \ Predicted</th>
                  <th>Predicted Normal (0)</th>
                  <th>Predicted Spoofed (1)</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th>Actual Normal (0)</th>
                  <td style={{ background: "rgba(20,184,166,0.16)", fontWeight: 700 }}>{cm[0][0]} (TN)</td>
                  <td style={{ background: "rgba(245,158,11,0.14)" }}>{cm[0][1]} (FP)</td>
                </tr>
                <tr>
                  <th>Actual Spoofed (1)</th>
                  <td style={{ background: "rgba(245,158,11,0.14)" }}>{cm[1][0]} (FN)</td>
                  <td style={{ background: "rgba(20,184,166,0.16)", fontWeight: 700 }}>{cm[1][1]} (TP)</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <small>SENSOR ATTRIBUTE WEIGHTS</small>
          <h2>Feature Importance</h2>
          <div style={{ display: "grid", gap: "0.55rem", marginTop: "0.75rem" }}>
            {importanceEntries.map(([feat, val]) => (
              <div key={feat}>
                <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
                  <span style={{ textTransform: "capitalize" }}>{feat}</span>
                  <code>{(val * 100).toFixed(1)}%</code>
                </div>
                <div style={{ height: "8px", background: "var(--bg)", borderRadius: "999px", overflow: "hidden", marginTop: "0.2rem" }}>
                  <div
                    style={{
                      width: `${(val / maxImp) * 100}%`,
                      height: "100%",
                      background: "linear-gradient(90deg, #14b8a6, #38bdf8)",
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {selectedPred && (
        <div className="card">
          <div className="sectionHead" style={{ padding: 0, marginBottom: "0.65rem" }}>
            <div>
              <small>INDIVIDUAL PREDICTION INSPECTOR · SEQ #{selectedPred.seq}</small>
              <h2>{selectedPred.drone_name} · {selectedPred.classification}</h2>
            </div>
            <button onClick={() => setSelectedPred(null)}>Close</button>
          </div>
          <p style={{ margin: "0 0 0.75rem", color: selectedPred.classification === "GPS Spoofed" ? "#fca5a5" : "#5eead4" }}>
            <strong>Reason:</strong> {selectedPred.reason}
          </p>
          <dl>
            <div><dt>ML Spoof Probability</dt><dd>{(selectedPred.score * 100).toFixed(1)}%</dd></div>
            <div><dt>Prediction Confidence</dt><dd>{Number(selectedPred.confidence).toFixed(1)}%</dd></div>
            <div><dt>Threat Severity</dt><dd>{selectedPred.severity}</dd></div>
            <div><dt>Corridor Deviation</dt><dd>{Number(selectedPred.deviation_m).toFixed(1)} m</dd></div>
            <div><dt>Speed / Accel / Gyro</dt><dd>{selectedPred.reading.speed.toFixed(1)} km/h · {selectedPred.reading.acceleration.toFixed(2)} m/s² · {selectedPred.reading.gyroscope.toFixed(2)} rad/s</dd></div>
            <div><dt>GPS Signal Strength</dt><dd>{selectedPred.reading.signal.toFixed(1)}%</dd></div>
          </dl>
        </div>
      )}

      <div className="card">
        <div className="sectionHead" style={{ padding: 0, marginBottom: "0.85rem", flexWrap: "wrap" }}>
          <div>
            <small>GPS SPOOFING DETECTION HISTORY</small>
            <h2>Prediction History &amp; Sensor Comparison ({data.predictions.length})</h2>
          </div>
          <div style={{ display: "flex", gap: "0.6rem" }}>
            <select value={droneFilter} onChange={(e) => setDroneFilter(e.target.value)} aria-label="Filter predictions by drone">
              <option value="">All drones</option>
              {fleet.map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
            <select value={clsFilter} onChange={(e) => setClsFilter(e.target.value)} aria-label="Filter predictions by classification">
              <option value="">All classifications</option>
              <option value="Normal">Normal</option>
              <option value="GPS Spoofed">GPS Spoofed</option>
            </select>
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Time (UTC)</th>
                <th>Drone</th>
                <th>Classification</th>
                <th>Confidence</th>
                <th>Severity</th>
                <th>Offset</th>
                <th>Reason</th>
                <th>Inspect</th>
              </tr>
            </thead>
            <tbody>
              {data.predictions.map((p: any) => (
                <tr key={p.id}>
                  <td>{new Date(p.time).toLocaleTimeString("en-GB", { timeZone: "UTC" })}</td>
                  <td>{p.drone_name}</td>
                  <td>
                    <span className={`pill ${p.classification === "GPS Spoofed" ? "danger" : ""}`}>
                      {p.classification}
                    </span>
                  </td>
                  <td>{Number(p.confidence).toFixed(1)}% (ML {(p.score * 100).toFixed(0)}%)</td>
                  <td className={"severity " + p.severity}>{p.severity}</td>
                  <td>{Number(p.deviation_m).toFixed(1)} m</td>
                  <td style={{ maxWidth: "320px" }}>{p.reason}</td>
                  <td>
                    <button onClick={() => setSelectedPred(p)}>Details</button>
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
