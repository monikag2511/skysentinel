import { useEffect, useState } from "react";

export function ReportsPage({
  requestApi,
}: {
  requestApi: (path: string) => Promise<any>;
}) {
  const [summary, setSummary] = useState<any | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    requestApi("reports/summary")
      .then(setSummary)
      .catch((e) => setError(e.message));
  }, []);

  async function downloadFile(format: "pdf" | "csv") {
    try {
      const response = await fetch(`/api/reports/export?format=${format}`);
      if (!response.ok) throw Error("Failed to generate report");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `skysentinel-security-report.${format}`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (error) return <p className="error" role="alert">{error}</p>;
  if (!summary) return <p role="status">Compiling security report preview…</p>;

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      <div className="card">
        <div className="sectionHead" style={{ padding: 0, flexWrap: "wrap" }}>
          <div>
            <small>REPORT GENERATION ENGINE</small>
            <h2>Executive Security &amp; Compliance Reports</h2>
          </div>
          <div style={{ display: "flex", gap: "0.6rem" }}>
            <button className="primary" onClick={() => void downloadFile("pdf")}>
              Download PDF Report
            </button>
            <button onClick={() => void downloadFile("csv")}>
              Download CSV Report
            </button>
          </div>
        </div>
        <p style={{ color: "var(--muted)", margin: "0.5rem 0 0" }}>
          Exports include drone activity summary, GPS spoofing detection results, network security incidents, attack statistics, alert history, recovery history, and Random Forest evaluation metrics.
        </p>
      </div>

      <div className="kpi-grid">
        <div className="kpi-card">
          <small>DRONE ACTIVITY</small>
          <strong>{summary.overview.total_drones} Drones</strong>
          <span>{summary.overview.active_drones} active · {summary.overview.spoofed_drones} spoofed</span>
        </div>
        <div className="kpi-card">
          <small>GPS DETECTION RESULTS</small>
          <strong>{summary.gps_detection.normal_count} / {summary.gps_detection.spoofed_count}</strong>
          <span>Normal / Spoofed ({summary.gps_detection.deviation_count} deviations)</span>
        </div>
        <div className="kpi-card">
          <small>NETWORK INCIDENTS</small>
          <strong>{summary.network.threat_packets} Threats</strong>
          <span>Of {summary.network.total_packets} packets · {summary.network.blocked_devices} blocked</span>
        </div>
        <div className="kpi-card ok">
          <small>ML PERFORMANCE</small>
          <strong>{(summary.ml_performance.accuracy * 100).toFixed(2)}%</strong>
          <span>F1 {summary.ml_performance.f1.toFixed(4)}</span>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <small>ATTACK BREAKDOWN</small>
          <h2>Attack Statistics</h2>
          {Object.keys(summary.attack_stats).length === 0 ? (
            <p style={{ color: "var(--muted)" }}>No attacks recorded yet.</p>
          ) : (
            <ul style={{ paddingLeft: "1.1rem" }}>
              {Object.entries(summary.attack_stats).map(([k, v]) => (
                <li key={k} style={{ display: "list-item", border: 0, padding: "0.2rem 0" }}>
                  <strong>{k}:</strong> {String(v)}
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="card">
          <small>RECENT RECOVERIES &amp; ALERTS</small>
          <h2>Latest Records Included</h2>
          <p style={{ color: "var(--muted)" }}>
            {summary.alerts.length} alerts and {summary.recoveries.length} recovery actions staged for export.
          </p>
        </div>
      </div>
    </div>
  );
}
