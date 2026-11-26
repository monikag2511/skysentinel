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
