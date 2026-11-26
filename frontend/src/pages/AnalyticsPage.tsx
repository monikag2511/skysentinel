import { useEffect, useState } from "react";
import type { Drone } from "../types";

type Bucket = { label: string; count: number };

function BarChart({ title, items, color = "#14b8a6" }: { title: string; items: Bucket[]; color?: string }) {
  const max = Math.max(...items.map((i) => i.count), 1);
  return (
    <div className="card">
      <small>{title}</small>
      {items.length === 0 ? (
        <p style={{ color: "var(--muted)", marginTop: "0.6rem" }}>No data for selected filters.</p>
      ) : (
        <div style={{ display: "grid", gap: "0.55rem", marginTop: "0.75rem" }}>
          {items.map((item) => (
            <div key={item.label}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.84rem" }}>
                <span>{item.label}</span>
                <code>{item.count}</code>
              </div>
              <div style={{ height: "10px", background: "var(--bg)", borderRadius: "999px", overflow: "hidden", marginTop: "0.2rem" }}>
                <div
                  style={{
                    width: `${Math.max(4, (item.count / max) * 100)}%`,
                    height: "100%",
                    background: color,
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function TrendSvg({ items }: { items: Bucket[] }) {
  if (items.length === 0) return <p style={{ color: "var(--muted)" }}>No historical trend points yet.</p>;
  const w = 520;
  const h = 150;
  const pad = 24;
  const max = Math.max(...items.map((i) => i.count), 1);
  const pts = items.map((item, idx) => {
    const x = items.length === 1 ? w / 2 : pad + (idx / (items.length - 1)) * (w - pad * 2);
    const y = h - pad - (item.count / max) * (h - pad * 2);
    return { x, y, ...item };
  });
  const polyline = pts.map((p) => `${p.x},${p.y}`).join(" ");
  return (
    <svg viewBox={`0 0 ${w} ${h}`} style={{ width: "100%", height: "160px" }} role="img" aria-label="Historical attack trend chart">
      <line x1={pad} y1={h - pad} x2={w - pad} y2={h - pad} stroke="#334155" strokeWidth="1" />
      <polyline fill="none" stroke="#38bdf8" strokeWidth="3" points={polyline} />
      {pts.map((p) => (
        <g key={p.label}>
          <circle cx={p.x} cy={p.y} r="4.5" fill="#14b8a6" />
          <text x={p.x} y={h - 6} fontSize="10" fill="#94a3b8" textAnchor="middle">
            {p.label.slice(5)}
          </text>
        </g>
      ))}
    </svg>
  );
}

export function AnalyticsPage({
  fleet,
  requestApi,
}: {
  fleet: Drone[];
  requestApi: (path: string) => Promise<any>;
}) {
  const [data, setData] = useState<any | null>(null);
  const [droneId, setDroneId] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [period, setPeriod] = useState<"daily" | "weekly" | "monthly">("daily");

  useEffect(() => {
    const params = new URLSearchParams();
    if (droneId) params.set("drone_id", droneId);
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    requestApi("analytics?" + params.toString())
      .then(setData)
      .catch(() => {});
  }, [droneId, dateFrom, dateTo, fleet]);

  if (!data) return <p role="status">Computing security analytics…</p>;

  const totalTelemetry = data.gps_vs_normal.Normal + data.gps_vs_normal["GPS Spoofed"];
  const spoofPct = totalTelemetry ? Math.round((data.gps_vs_normal["GPS Spoofed"] / totalTelemetry) * 100) : 0;

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      <div className="card">
        <div className="sectionHead" style={{ padding: 0, flexWrap: "wrap" }}>
          <div>
            <small>SECURITY ANALYTICS &amp; VISUALIZATION</small>
            <h2>Threat Trends &amp; Telemetry Distribution</h2>
          </div>
          <div style={{ display: "flex", gap: "0.55rem", flexWrap: "wrap" }}>
            <select value={droneId} onChange={(e) => setDroneId(e.target.value)} aria-label="Filter analytics by drone">
              <option value="">All drones</option>
              {fleet.map((d) => (
                <option key={d.id} value={d.id}>{d.name}</option>
              ))}
            </select>
            <input type="date" aria-label="From date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
            <input type="date" aria-label="To date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
            <select value={period} onChange={(e) => setPeriod(e.target.value as any)} aria-label="Timeframe granularity">
              <option value="daily">Daily</option>
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
            </select>
          </div>
        </div>
      </div>

      <div className="kpi-grid">
        <div className="kpi-card ok">
          <small>NORMAL GPS ACTIVITY</small>
          <strong>{data.gps_vs_normal.Normal}</strong>
          <span>{100 - spoofPct}% of analyzed frames</span>
        </div>
        <div className={`kpi-card ${data.gps_vs_normal["GPS Spoofed"] > 0 ? "danger" : "ok"}`}>
          <small>GPS SPOOFED ACTIVITY</small>
          <strong>{data.gps_vs_normal["GPS Spoofed"]}</strong>
          <span>{spoofPct}% spoof rate</span>
        </div>
        <div className="kpi-card">
          <small>NETWORK TRAFFIC (IN / OUT)</small>
          <strong>{data.network_traffic.Inbound} / {data.network_traffic.Outbound}</strong>
          <span>{data.network_traffic.Threats} flagged threat packets</span>
        </div>
      </div>

      <div className="card">
        <small>HISTORICAL SECURITY TREND ({period.toUpperCase()})</small>
        <h2>Attack Frequency Over Time</h2>
        <TrendSvg items={data[period]} />
      </div>

      <div className="grid-2">
        <BarChart title="ATTACK TYPE DISTRIBUTION" items={data.attack_distribution} color="#f97316" />
        <BarChart title="SEVERITY DISTRIBUTION" items={data.severity_distribution} color="#ef4444" />
        <BarChart title="DRONE-WISE ATTACK STATISTICS" items={data.drone_attacks} color="#38bdf8" />
        <BarChart title="RECOVERY ACTION STATISTICS" items={data.recovery_actions} color="#14b8a6" />
      </div>
    </div>
  );
}
