import { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Chart } from "./Chart";
import { Archive } from "./Archive";
import { DashboardOverview } from "./pages/DashboardPage";
import { FleetHealthPage } from "./pages/FleetHealthPage";
import type { DashboardData, Drone, NavSection, Reading, Snapshot } from "./types";
import "./style.css";

const instruments: [keyof Reading, string, string][] = [
  ["speed", "Speed", "km/h"],
  ["signal", "GPS signal", "%"],
  ["acceleration", "Acceleration", "m/s²"],
  ["gyroscope", "Gyroscope", "rad/s"],
  ["latitude", "Latitude", "° N"],
  ["longitude", "Longitude", "° E"],
];

const scenarios = [
  ["normal", "Normal flight"],
  ["gps", "GPS deviation"],
  ["unknown", "Unknown sender"],
  ["duplicate", "Duplicate sequence"],
  ["integrity", "Integrity failure"],
  ["rate", "Traffic burst"],
];

const navItems: [NavSection, string][] = [
  ["dashboard", "Security Dashboard"],
  ["tracking", "Live GPS Tracking"],
  ["drones", "Drone Management"],
  ["ml", "ML & Spoofing Analysis"],
  ["deviations", "Flight Deviations"],
  ["network", "Network & Comms"],
  ["simulation", "Attack Simulation"],
  ["recovery", "Autonomous Recovery"],
  ["alerts", "Security Alerts"],
  ["health", "Multi-Drone Health"],
  ["analytics", "Security Analytics"],
  ["logs", "Security Logs"],
  ["reports", "Report Generation"],
  ["admin", "Admin Management"],
];

const clock = (iso: string) =>
  new Date(iso).toLocaleTimeString("en-GB", { timeZone: "UTC" });

async function request(path: string, options?: RequestInit) {
  const response = await fetch("/api/" + path, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw Error(body.detail || "Flight service unavailable");
  }
  return response.json();
}

function App() {
  const [section, setSection] = useState<NavSection>("dashboard");
  const [navOpen, setNavOpen] = useState(false);
  const [snapshot, setSnapshot] = useState<Snapshot>();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [id, select] = useState(0);
  const [scenario, choose] = useState("normal");
  const [error, fail] = useState("");
  const [busy, working] = useState(false);
  const [live, play] = useState(false);
  const [filter, setFilter] = useState("All aircraft");
  const [notice, tell] = useState("");
  const [evaluation, report] = useState<{
    train: number;
    test: number;
    metrics: Record<
      string,
      { precision: number; recall: number; "f1-score": number }
    >;
  } | null>(null);
  const pending = useRef(false);
  const version = useRef(0);

  async function refresh() {
    const ticket = ++version.current;
    const [watchData, dashData] = await Promise.all([
      request("watch"),
      request("dashboard").catch(() => null),
    ]);
    if (ticket === version.current) {
      setSnapshot(watchData);
      if (dashData) setDashboard(dashData);
      fail("");
    }
  }

  useEffect(() => {
    refresh().catch((e) => fail(e.message));
    const t = setInterval(() => {
      if (!pending.current) refresh().catch((e) => fail(e.message));
    }, 6000);
    return () => clearInterval(t);
  }, []);

  async function run(action: string, incident?: number, device = id) {
    if (pending.current) return;
    pending.current = true;
    working(true);
    tell("");
    try {
      await request("drones/" + device + "/commands", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-Sky-Command": "1" },
        body: JSON.stringify({ action, incident }),
      });
      await refresh();
      tell("Flight record updated.");
    } catch (e) {
      fail((e as Error).message);
      play(false);
    } finally {
      pending.current = false;
      working(false);
    }
  }

  const d =
    snapshot?.fleet.find((aircraft: Drone) => aircraft.id === id) ||
    snapshot?.fleet[0];

  useEffect(() => {
    if (!live || d?.mode !== "Patrol") return;
    const t = setInterval(() => void run("normal", undefined, id), 3500);
    return () => clearInterval(t);
  }, [live, id, d?.mode]);

  const events =
    snapshot?.history.filter(
      (e) => filter === "All aircraft" || e.drone === id,
    ) || [];

  const activeAlertsCount =
    dashboard?.stats.active_alerts ??
    snapshot?.history.filter((e) => e.status === "Open").length ??
    0;

  return (
    <div className="app-shell">
      <aside className={"sidebar" + (navOpen ? " open" : "")}>
        <a
          href="#flight"
          className="brand"
          onClick={(e) => {
            e.preventDefault();
            setSection("dashboard");
            setNavOpen(false);
          }}
        >
          <i>✈</i> SkySentinel
        </a>
        {navItems.map(([key, label]) => (
          <button
            key={key}
            className="nav-item"
            aria-current={section === key ? "page" : undefined}
            onClick={() => {
              setSection(key);
              setNavOpen(false);
            }}
          >
            <span>{label}</span>
            {key === "alerts" && activeAlertsCount > 0 && (
              <span className="nav-badge">{activeAlertsCount}</span>
            )}
          </button>
        ))}
        <div className="sidebar-foot">
          <span>AES-256-GCM Telemetry</span>
          <span>Role: {snapshot?.role ?? "connecting"}</span>
        </div>
      </aside>

      <div className="content-col">
        <header className="topbar">
          <div className="topbar-left">
            <button
              className="menu-toggle"
              aria-label="Toggle navigation"
              onClick={() => setNavOpen(!navOpen)}
            >
              ☰ Menu
            </button>
            <span className="stamp">
              {navItems.find(([k]) => k === section)?.[1]}
            </span>
          </div>
          <div className="topbar-right">
            {dashboard && (
              <>
                <span
                  className={
                    "pill " +
                    (dashboard.stats.gps_security_status === "Under Attack"
                      ? "danger"
                      : dashboard.stats.gps_security_status === "Alert"
                        ? "warn"
                        : "")
                  }
                >
                  GPS: {dashboard.stats.gps_security_status}
                </span>
                <span
                  className={
                    "pill " +
                    (dashboard.stats.network_security_status === "Compromised"
                      ? "danger"
                      : dashboard.stats.network_security_status === "Warning"
                        ? "warn"
                        : "")
                  }
                >
                  NET: {dashboard.stats.network_security_status}
                </span>
              </>
            )}
            <span className="session">Simulation</span>
          </div>
        </header>

        <main>
          <section className="intro" id="flight">
            <div>
              <small>GROUND CONTROL &nbsp; / &nbsp; CHENNAI</small>
              <h1>
                Flight watch<span>.</span>
              </h1>
            </div>
            <p>
              Fleet operations
              <br />
              <strong>
                {snapshot?.fleet.length ?? "…"} aircraft on station
              </strong>
            </p>
          </section>

          {error && (
            <p role="alert" className="error">
              {error}{" "}
              <button onClick={() => refresh().catch((e) => fail(e.message))}>
                Retry
              </button>
            </p>
          )}

          {snapshot && d ? (
            section === "health" ? (
              <FleetHealthPage
                dashboard={dashboard}
                requestApi={request}
                onSelectDrone={(droneId) => {
                  select(droneId);
                  setSection("dashboard");
                }}
              />
            ) : (
              <>
                {section === "dashboard" && (
                  <DashboardOverview
                    dashboard={dashboard}
                    onNavigate={(s) => setSection(s)}
                  />
                )}
                <div className="fleet" aria-label="Select aircraft">
                  {snapshot.fleet.map((a) => (
                    <button
                      aria-pressed={a.id === d.id}
                      key={a.id}
                      onClick={() => {
                        select(a.id);
                        play(false);
                        tell("");
                      }}
                    >
                      <small>{a.code ?? `DRN / 00${a.id + 1}`}</small>
                      <strong>{a.name}</strong>
                      <span>{a.mode}</span>
                    </button>
                  ))}
                </div>
                <div className="workspace">
                  <section className="plot">
                    <div className="sectionHead">
                      <div>
                        <small>TRAJECTORY</small>
                        <h2>Flight chart</h2>
                      </div>
                      <span className="stamp">13° N · 80° E</span>
                    </div>
                    <Chart selected={d} fleet={snapshot.fleet} />
                    <div className="legend">
                      <span>┄ Expected route</span>
                      <span>━ Reported GPS</span>
                      <span>✈ Trusted fix</span>
                    </div>
                  </section>
                  <aside>
                    <small>FLIGHT STRIP &nbsp; / &nbsp; 00{d.id + 1}</small>
                    <h2>{d.name}</h2>
                    <dl>
                      {instruments.map(([key, label, unit]) => (
                        <div key={key}>
                          <dt>{label}</dt>
                          <dd>
                            {d.track.at(-1)
                              ? d.track
                                  .at(-1)!
                                  .reading[key].toFixed(
                                    key === "latitude" || key === "longitude"
                                      ? 4
                                      : 1,
                                  )
                              : "0.0"}{" "}
                            <em>{unit}</em>
                          </dd>
                        </div>
                      ))}
                    </dl>
                    {snapshot.role === "viewer" && (
                      <p>Viewer access · flight controls locked</p>
                    )}
                    <fieldset
                      className="controls"
                      disabled={snapshot.role === "viewer"}
                    >
                      <label htmlFor="scenario">Demo scenario</label>
                      <select
                        id="scenario"
                        value={scenario}
                        onChange={(e) => choose(e.target.value)}
                      >
                        {scenarios.map(([key, label]) => (
                          <option key={key} value={key}>
                            {label}
                          </option>
                        ))}
                      </select>
                      <button
                        className="primary"
                        disabled={busy || d.mode !== "Patrol"}
                        onClick={() => {
                          play(false);
                          void run(scenario);
                        }}
                      >
                        Run scenario
                      </button>
                      {d.mode === "Patrol" ? (
                        <button disabled={busy} onClick={() => play(!live)}>
                          {live ? "Pause patrol" : "Start continuous patrol"}
                        </button>
                      ) : (
                        <button
                          disabled={busy}
                          onClick={() => {
                            play(false);
                            void run(d.mode === "At base" ? "resume" : "home");
                          }}
                        >
                          {d.mode === "At base"
                            ? "Resume patrol"
                            : "Return to base"}
                        </button>
                      )}
                      <div className="notice" role="status">
                        {busy ? "Updating flight record…" : notice || d.mode}
                      </div>
                    </fieldset>
                  </aside>
                </div>
                <section id="ledger">
                  <div className="sectionHead">
                    <div>
                      <small>SECURITY HISTORY</small>
                      <h2>Incident ledger</h2>
                    </div>
                    <select
                      aria-label="Filter ledger"
                      value={filter}
                      onChange={(e) => setFilter(e.target.value)}
                    >
                      <option>All aircraft</option>
                      <option>Selected aircraft</option>
                    </select>
                  </div>
                  <ol>
                    {events.map((e) => (
                      <li key={e.id}>
                        <time>{clock(e.time)} UTC</time>
                        <div>
                          <strong>{e.kind}</strong>
                          <p>
                            {snapshot.fleet.find((a) => a.id === e.drone)?.name}{" "}
                            · {e.detail}{" "}
                            {e.score !== null &&
                              "Model score " + Math.round(e.score * 100) + "%"}
                          </p>
                        </div>
                        <span className={"severity " + e.severity}>
                          {e.severity}
                        </span>
                        {e.status === "Open" && snapshot.role !== "viewer" ? (
                          <button
                            disabled={busy}
                            onClick={() => run("ack", e.id, e.drone)}
                          >
                            Acknowledge
                          </button>
                        ) : (
                          <span>{e.status}</span>
                        )}
                      </li>
                    ))}
                  </ol>
                  <Archive />
                </section>
                <section className="evaluation">
                  <h2>Detector evaluation</h2>
                  <button
                    onClick={async () => {
                      try {
                        report(evaluation ? null : await request("evaluation"));
                      } catch (e) {
                        fail((e as Error).message);
                      }
                    }}
                  >
                    {evaluation ? "Hide results" : "View test results"}
                  </button>
                  {evaluation && (
                    <p>
                      {evaluation.train} training samples · {evaluation.test}{" "}
                      held-out samples · Precision{" "}
                      {(evaluation.metrics["1"].precision * 100).toFixed(1)}% ·
                      Recall {(evaluation.metrics["1"].recall * 100).toFixed(1)}%
                      · F1 {evaluation.metrics["1"]["f1-score"].toFixed(3)}
                    </p>
                  )}
                </section>
              </>
            )
          ) : (
            !error && <p role="status">Connecting to flight control…</p>
          )}
        </main>
      </div>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
