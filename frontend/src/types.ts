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
};
export type Drone = {
  id: number;
  name: string;
  mode: string;
  trusted: Point;
  seq: number;
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
};
export type Snapshot = { fleet: Drone[]; history: EventRow[]; role: "viewer" | "operator" };
