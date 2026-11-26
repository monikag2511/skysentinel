import { useEffect, useState } from "react";

export function NetworkSecurityPage({
  role,
  requestApi,
  onChanged,
}: {
  role: "viewer" | "operator";
  requestApi: (path: string, options?: RequestInit) => Promise<any>;
  onChanged: () => Promise<void>;
}) {
  const [data, setData] = useState<any | null>(null);
  const [direction, setDirection] = useState("");
  const [threatOnly, setThreatOnly] = useState(false);
  const [newUid, setNewUid] = useState("");
  const [newName, setNewName] = useState("");
  const [newIp, setNewIp] = useState("10.42.1.50");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  async function load() {
    const params = new URLSearchParams();
    if (direction) params.set("direction", direction);
    if (threatOnly) params.set("threat_only", "true");
    const res = await requestApi("network/overview?" + params.toString());
    setData(res);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [direction, threatOnly]);

  async function toggleDevice(uid: string, action: "block" | "trust") {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await requestApi(`network/devices/${encodeURIComponent(uid)}/${action}`, {
        method: "POST",
        headers: { "X-Sky-Command": "1" },
      });
      setNotice(`Device ${uid} marked as ${action === "block" ? "Blocked" : "Trusted"}.`);
      await load();
      await onChanged();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function addDevice(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await requestApi("network/devices", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Sky-Command": "1" },
        body: JSON.stringify({ device_uid: newUid, name: newName, ip_address: newIp }),
      });
      setNewUid("");
      setNewName("");
      setNotice("Trusted device added.");
      await load();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  if (!data) return <p role="status">Loading network telemetry &amp; cipher state…</p>;
  const s = data.summary;

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      {error && <p className="error" role="alert">{error}</p>}
      {notice && <p className="notice" role="status">{notice}</p>}

      <div className="kpi-grid">
        <div className="kpi-card ok">
          <small>AES-256-GCM ENCRYPTION</small>
          <strong>{s.encrypted_pct}%</strong>
          <span>{s.total_packets} captured packets</span>
        </div>
        <div className="kpi-card ok">
          <small>AUTH INTEGRITY RATE</small>
          <strong>{s.auth_integrity_pct}%</strong>
          <span>AAD &amp; nonce verified</span>
        </div>
        <div className="kpi-card">
          <small>TRUSTED / BLOCKED NODES</small>
          <strong>{s.trusted_count} / {s.blocked_count}</strong>
          <span>Access control registry</span>
        </div>
        <div className={`kpi-card ${s.threat_counts.packet_injection + s.threat_counts.mitm_suspected > 0 ? "danger" : "ok"}`}>
          <small>INJECTION / MITM FLAGS</small>
          <strong>{s.threat_counts.packet_injection} / {s.threat_counts.mitm_suspected}</strong>
          <span>Replay: {s.threat_counts.replay_attack} · Unauth: {s.threat_counts.unauthorized}</span>
        </div>
      </div>

      <div className="grid-2">
        <div className="card">
          <small>ACCESS CONTROL REGISTRY</small>
          <h2>Trusted &amp; Blocked Devices</h2>
          <div className="table-wrap" style={{ marginTop: "0.75rem" }}>
            <table>
              <thead>
                <tr>
                  <th>Device UID</th>
                  <th>Name / IP</th>
                  <th>Status</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {data.devices.map((dv: any) => (
                  <tr key={dv.id}>
                    <td><code>{dv.device_uid}</code></td>
                    <td>{dv.name}<br /><span style={{ color: "var(--muted)", fontSize: "0.78rem" }}>{dv.ip_address} · {dv.mac_address}</span></td>
                    <td><span className={`pill ${dv.status === "Blocked" ? "danger" : ""}`}>{dv.status}</span></td>
                    <td>
                      {dv.status === "Trusted" ? (
                        <button className="danger-btn" disabled={busy || role === "viewer"} onClick={() => void toggleDevice(dv.device_uid, "block")}>
                          Block
                        </button>
                      ) : (
                        <button className="primary" disabled={busy || role === "viewer"} onClick={() => void toggleDevice(dv.device_uid, "trust")}>
                          Trust
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="card">
          <small>WHITELIST PROVISIONING</small>
          <h2>Register Trusted Device</h2>
          <form onSubmit={addDevice} style={{ display: "grid", gap: "0.65rem", marginTop: "0.75rem" }}>
            <label>
              Device UID
              <input required placeholder="e.g. RELAY-NODE-04" value={newUid} onChange={(e) => setNewUid(e.target.value)} style={{ width: "100%", marginTop: "0.25rem" }} />
            </label>
            <label>
              Device Label
              <input required placeholder="e.g. Field Relay Station" value={newName} onChange={(e) => setNewName(e.target.value)} style={{ width: "100%", marginTop: "0.25rem" }} />
            </label>
            <label>
              IP Address
              <input required value={newIp} onChange={(e) => setNewIp(e.target.value)} style={{ width: "100%", marginTop: "0.25rem" }} />
            </label>
            <button className="primary" type="submit" disabled={busy || role === "viewer"}>
              Add Trusted Device
            </button>
          </form>
        </div>
      </div>

      <div className="card">
        <div className="sectionHead" style={{ padding: 0, marginBottom: "0.85rem", flexWrap: "wrap" }}>
          <div>
            <small>SECURE COMMUNICATION &amp; PACKET INSPECTOR</small>
            <h2>Inbound &amp; Outbound Traffic Stream ({data.packets.length})</h2>
          </div>
          <div style={{ display: "flex", gap: "0.6rem", alignItems: "center" }}>
            <label style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
              <input type="checkbox" checked={threatOnly} onChange={(e) => setThreatOnly(e.target.checked)} />
              Threats only
            </label>
            <select value={direction} onChange={(e) => setDirection(e.target.value)} aria-label="Filter traffic direction">
              <option value="">All traffic</option>
              <option value="Inbound">Inbound</option>
              <option value="Outbound">Outbound</option>
            </select>
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Time (UTC)</th>
                <th>Dir</th>
                <th>Source → Destination</th>
                <th>Device</th>
                <th>Size / Proto</th>
                <th>Auth Status</th>
                <th>Detail</th>
                <th>Block</th>
              </tr>
            </thead>
            <tbody>
              {data.packets.map((p: any) => (
                <tr key={p.id}>
                  <td>{new Date(p.time).toLocaleTimeString("en-GB", { timeZone: "UTC" })}</td>
                  <td>{p.direction}</td>
                  <td><code>{p.src_addr} → {p.dst_addr}</code></td>
                  <td><code>{p.device_uid}</code></td>
                  <td>{p.packet_size} B · {p.protocol}</td>
                  <td>
                    <span className={`pill ${p.auth_status === "Authenticated" ? "" : "danger"}`}>
                      {p.auth_status}
                    </span>
                  </td>
                  <td>{p.detail} {p.simulated && <span className="pill warn">SIM</span>}</td>
                  <td>
                    {p.threat_type && p.device_uid !== "GCS-CTRL-01" && (
                      <button
                        className="danger-btn"
                        disabled={busy || role === "viewer"}
                        onClick={() => void toggleDevice(p.device_uid, "block")}
                      >
                        Block
                      </button>
                    )}
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
