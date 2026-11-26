export type Point = [number, number];

export type Reading = {
  latitude: number;
  longitude: number;
  speed: number;
  acceleration: number;
  gyroscope: number;
  signal: number;
};

export type Sample = {
  seq: number;
  time: string;
  reading: Reading;
  expected: Point;
  score: number;
  altitude?: number;
  battery?: number;
  classification?: string;
  confidence?: number;
  severity?: string;
  reason?: string;
  deviation_m?: number;
  simulated?: boolean;
};

export type Drone = {
  id: number;
  name: string;
  mode: string;
  trusted: Point;
  seq: number;
  code?: string;
  model_type?: string;
  battery?: number;
  altitude?: number;
  gps_status?: string;
  comm_status?: string;
  sensor_status?: string;
  is_active?: boolean;
  base_lat?: number;
  base_lon?: number;
  route_config?: Point[] | null;
  created_at?: string;
  route: Point[];
  track: Sample[];
};

export type EventRow = {
  id: number;
  drone: number;
  drone_name?: string;
  time: string;
  kind: string;
  severity: string;
  detail: string;
  status: string;
  score: number | null;
  incident: number | null;
  category?: string;
  simulated?: boolean;
};

export type AlertRow = {
  id: number;
  alert_code: string;
  drone_id: number | null;
  drone_name?: string;
  drone_code?: string;
  attack_type: string;
  severity: string;
  confidence: number | null;
  created_at: string;
  description: string;
  status: string;
  simulated: boolean;
  source_event_id: number | null;
  details?: Record<string, unknown> | null;
};

export type DroneHealth = {
  id: number;
  code: string;
  name: string;
  model_type: string;
  mode: string;
  is_active: boolean;
  battery: number;
  altitude: number;
  speed: number;
  signal: number;
  latitude: number;
  longitude: number;
  gps_status: string;
  comm_status: string;
  sensor_status: string;
  flight_status: string;
  security_status: string;
  warnings: string[];
  last_seen: string;
};

export type DashboardData = {
  stats: {
    total_registered: number;
    active_drones: number;
    normal_drones: number;
    spoofed_drones: number;
    total_cyberattacks: number;
    critical_alerts: number;
    active_alerts: number;
    network_security_status: string;
    gps_security_status: string;
  };
  recent_attacks: AlertRow[];
  latest_activity: EventRow[];
  drone_health: DroneHealth[];
  thresholds: Record<string, number>;
};

export type Snapshot = {
  fleet: Drone[];
  history: EventRow[];
  role: "viewer" | "operator";
};

export type NavSection =
  | "dashboard"
  | "tracking"
  | "drones"
  | "ml"
  | "deviations"
  | "network"
  | "simulation"
  | "recovery"
  | "alerts"
  | "health"
  | "analytics"
  | "logs"
  | "reports"
  | "admin";
