import { useEffect, useState } from "react";
import type { DroneHealth } from "../types";

export function DroneManagementPage({
  role,
  requestApi,
  onChanged,
  onSelectMap,
}: {
  role: "viewer" | "operator";
  requestApi: (path: string, options?: RequestInit) => Promise<any>;
  onChanged: () => Promise<void>;
  onSelectMap: (id: number) => void;
}) {
  const [items, setItems] = useState<DroneHealth[]>([]);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [selected, setSelected] = useState<DroneHealth | null>(null);
  const [editing, setEditing] = useState<DroneHealth | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const [form, setForm] = useState({
    name: "",
    code: "",
    model_type: "Quad-Rotor UAV",
    battery: 98,
    altitude: 135,
    base_lat: 13.05,
    base_lon: 80.214,
  });

  async function load() {
    const params = new URLSearchParams();
    if (query.trim()) params.set("q", query.trim());
    if (statusFilter) params.set("status", statusFilter);
    const data = await requestApi("drones?" + params.toString());
    setItems(data.items);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [query, statusFilter]);

  async function registerDrone(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const created = await requestApi("drones", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Sky-Command": "1" },
        body: JSON.stringify({
          name: form.name,
          code: form.code || undefined,
          model_type: form.model_type,
          battery: Number(form.battery),
          altitude: Number(form.altitude),
          base_lat: Number(form.base_lat),
          base_lon: Number(form.base_lon),
        }),
      });
      setMessage(`Registered ${created.name} (${created.code}) with ID ${created.id}.`);
      setForm({ ...form, name: "", code: "" });
      await load();
      await onChanged();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function saveEdit(e: React.FormEvent) {
    e.preventDefault();
    if (!editing) return;
    setBusy(true);
    setError("");
    try {
      await requestApi(`drones/${editing.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json", "X-Sky-Command": "1" },
        body: JSON.stringify({
          name: editing.name,
          model_type: editing.model_type,
          battery: Number(editing.battery),
          altitude: Number(editing.altitude),
          is_active: editing.is_active,
        }),
      });
      setMessage(`Updated ${editing.name}.`);
      setEditing(null);
      await load();
      await onChanged();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function removeDrone(d: DroneHealth) {
    setBusy(true);
    setError("");
    try {
      await requestApi(`drones/${d.id}`, {
        method: "DELETE",
        headers: { "X-Sky-Command": "1" },
      });
      setMessage(`Deleted ${d.name} (${d.code}).`);
      if (selected?.id === d.id) setSelected(null);
      await load();
      await onChanged();
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: "grid", gap: "1rem" }}>
      {error && <p className="error" role="alert">{error}</p>}
      {message && <p className="notice" role="status">{message}</p>}

      <div className="grid-2">
        <div className="card">
          <small>FLEET PROVISIONING</small>
          <h2>Register New Drone</h2>
          <form onSubmit={registerDrone} style={{ display: "grid", gap: "0.65rem", marginTop: "0.75rem" }}>
            <label>
              Drone Name
              <input
                required
                placeholder="e.g. Delta-Hawk"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                style={{ width: "100%", marginTop: "0.25rem" }}
              />
            </label>
            <div className="grid-2">
              <label>
                Unique Code (optional)
                <input
                  placeholder="Auto (DRN-004)"
                  value={form.code}
                  onChange={(e) => setForm({ ...form, code: e.target.value })}
                  style={{ width: "100%", marginTop: "0.25rem" }}
                />
              </label>
              <label>
                Airframe Model
                <input
                  required
                  value={form.model_type}
                  onChange={(e) => setForm({ ...form, model_type: e.target.value })}
                  style={{ width: "100%", marginTop: "0.25rem" }}
                />
              </label>
            </div>
            <div className="grid-2">
              <label>
                Battery (%)
                <input
                  type="number"
                  min={0}
                  max={100}
                  step="0.5"
                  value={form.battery}
                  onChange={(e) => setForm({ ...form, battery: Number(e.target.value) })}
                  style={{ width: "100%", marginTop: "0.25rem" }}
                />
              </label>
              <label>
                Altitude (m)
                <input
                  type="number"
                  min={0}
                  max={5000}
                  value={form.altitude}
                  onChange={(e) => setForm({ ...form, altitude: Number(e.target.value) })}
                  style={{ width: "100%", marginTop: "0.25rem" }}
                />
              </label>
            </div>
            <div className="grid-2">
              <label>
                Base Latitude
                <input
                  type="number"
                  step="0.0001"
                  value={form.base_lat}
                  onChange={(e) => setForm({ ...form, base_lat: Number(e.target.value) })}
                  style={{ width: "100%", marginTop: "0.25rem" }}
                />
              </label>
              <label>
                Base Longitude
                <input
                  type="number"
                  step="0.0001"
                  value={form.base_lon}
                  onChange={(e) => setForm({ ...form, base_lon: Number(e.target.value) })}
                  style={{ width: "100%", marginTop: "0.25rem" }}
                />
              </label>
            </div>
            <button className="primary" disabled={busy || role === "viewer"} type="submit">
              {role === "viewer" ? "Operator Login Required" : "Register Drone"}
            </button>
          </form>
        </div>

        <div className="card">
          <small>DRONE DETAIL INSPECTOR</small>
          <h2>{selected ? `${selected.name} (${selected.code})` : "Select a Drone"}</h2>
          {selected ? (
            <>
              <dl>
                <div><dt>Unique ID</dt><dd>#{selected.id} / {selected.code}</dd></div>
                <div><dt>Security Status</dt><dd>{selected.security_status}</dd></div>
                <div><dt>Battery</dt><dd>{selected.battery}%</dd></div>
                <div><dt>Speed / Altitude</dt><dd>{selected.speed} km/h · {selected.altitude} m</dd></div>
                <div><dt>Latitude</dt><dd>{selected.latitude.toFixed(5)}°</dd></div>
                <div><dt>Longitude</dt><dd>{selected.longitude.toFixed(5)}°</dd></div>
                <div><dt>GPS Connectivity</dt><dd>{selected.gps_status}</dd></div>
                <div><dt>Comms Link</dt><dd>{selected.comm_status}</dd></div>
              </dl>
              <div style={{ display: "flex", gap: "0.5rem" }}>
                <button className="primary" onClick={() => onSelectMap(selected.id)}>
                  Track on Live Map
                </button>
                <button onClick={() => setEditing(selected)} disabled={role === "viewer"}>
                  Edit Details
                </button>
              </div>
            </>
          ) : (
            <p style={{ color: "var(--muted)" }}>
              Choose any registered aircraft from the table below to inspect live coordinates, battery, GPS link, and security status.
            </p>
          )}
        </div>
      </div>

      {editing && (
        <div className="card">
          <small>EDIT DRONE · {editing.code}</small>
          <h2>Update {editing.name}</h2>
          <form onSubmit={saveEdit} style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", alignItems: "end" }}>
            <label>
              Name
              <input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} />
            </label>
            <label>
              Model
              <input value={editing.model_type} onChange={(e) => setEditing({ ...editing, model_type: e.target.value })} />
            </label>
            <label>
              Battery %
              <input type="number" value={editing.battery} onChange={(e) => setEditing({ ...editing, battery: Number(e.target.value) })} />
            </label>
            <label>
              Altitude (m)
              <input type="number" value={editing.altitude} onChange={(e) => setEditing({ ...editing, altitude: Number(e.target.value) })} />
            </label>
            <label>
              Active
              <select
                value={editing.is_active ? "yes" : "no"}
                onChange={(e) => setEditing({ ...editing, is_active: e.target.value === "yes" })}
              >
                <option value="yes">Active</option>
                <option value="no">Standby</option>
              </select>
            </label>
            <button className="primary" type="submit" disabled={busy}>Save Changes</button>
            <button type="button" onClick={() => setEditing(null)}>Cancel</button>
          </form>
        </div>
      )}

      <div className="card">
        <div className="sectionHead" style={{ padding: 0, marginBottom: "0.85rem", flexWrap: "wrap" }}>
          <div>
            <small>REGISTERED FLEET</small>
            <h2>All Registered Drones ({items.length})</h2>
          </div>
          <div style={{ display: "flex", gap: "0.6rem", flexWrap: "wrap" }}>
            <input
              type="search"
              placeholder="Search name, code, model..."
              aria-label="Search drones"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <select aria-label="Filter drone status" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
              <option value="">All statuses</option>
              <option value="Normal">Normal</option>
              <option value="GPS Spoofed">GPS Spoofed</option>
              <option value="Network Warning">Network Warning</option>
              <option value="Patrol">Patrol</option>
              <option value="At base">At base</option>
            </select>
          </div>
        </div>

        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID / Code</th>
                <th>Name</th>
                <th>Status</th>
                <th>Battery</th>
                <th>Speed / Alt</th>
                <th>Coordinates</th>
                <th>GPS / Comms</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((d) => (
                <tr key={d.id}>
                  <td><code>#{d.id} · {d.code}</code></td>
                  <td><strong>{d.name}</strong><br /><span style={{ color: "var(--muted)", fontSize: "0.78rem" }}>{d.model_type}</span></td>
                  <td><span className={`pill ${d.security_status === "GPS Spoofed" ? "danger" : d.security_status === "Normal" ? "" : "warn"}`}>{d.security_status}</span></td>
                  <td>{d.battery}%</td>
                  <td>{d.speed} km/h · {d.altitude}m</td>
                  <td>{d.latitude.toFixed(4)}, {d.longitude.toFixed(4)}</td>
                  <td>{d.gps_status} / {d.comm_status}</td>
                  <td style={{ display: "flex", gap: "0.35rem", flexWrap: "wrap" }}>
                    <button onClick={() => setSelected(d)}>Details</button>
                    <button disabled={role === "viewer"} onClick={() => setEditing(d)}>Edit</button>
                    <button className="danger-btn" disabled={busy || role === "viewer" || items.length <= 1} onClick={() => void removeDrone(d)}>Delete</button>
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
