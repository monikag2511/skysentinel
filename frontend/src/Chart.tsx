import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Drone, Point } from "./types";

export function Chart({
  fleet,
  selected,
}: {
  fleet: Drone[];
  selected: Drone;
}) {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const vehicle = useRef<L.Marker | null>(null);
  useEffect(() => {
    const m = L.map(host.current!, {
      attributionControl: false,
      scrollWheelZoom: false,
      minZoom: 13,
      zoomSnap: 0.25,
      maxZoom: 19,
    });
    map.current = m;
    layer.current = L.layerGroup().addTo(m);
    L.control.scale({ imperial: false }).addTo(m);
    const resize = new ResizeObserver(() => m.invalidateSize());
    resize.observe(host.current!);
    return () => {
      resize.disconnect();
      m.remove();
      vehicle.current = null;
    };
  }, []);
  useEffect(() => {
    map.current!.fitBounds(L.latLngBounds(selected.route).pad(0.45), {
      animate: false,
    });
  }, [selected.id]);
  useEffect(() => {
    const g = layer.current!;
    g.clearLayers();
    fleet.forEach((d) =>
      L.polyline(d.route, {
        color: d.id === selected.id ? "#16756e" : "#829eaa",
        weight: d.id === selected.id ? 3 : 1.5,
        dashArray: "6 7",
      }).addTo(g),
    );
    const reported: Point[] = selected.track.map((s) => [
      s.reading.latitude,
      s.reading.longitude,
    ]);
    L.polyline(reported, { color: "#cc482b", weight: 3 }).addTo(g);
    L.circleMarker(reported[reported.length - 1], {
      radius: 5,
      color: "#a7361d",
      fillOpacity: 1,
    })
      .bindTooltip("Reported GPS")
      .addTo(g);
    const fix = selected.trusted;
    if (vehicle.current) vehicle.current.setLatLng(fix);
    else
      vehicle.current = L.marker(fix, {
        icon: L.divIcon({
          className: "aircraft",
          html: "<span>✈</span>",
          iconSize: [38, 38],
          iconAnchor: [19, 19],
        }),
      }).addTo(map.current!);
    vehicle.current.bindTooltip(selected.name + " · trusted fix", {
      permanent: true,
      direction: "bottom",
      offset: [0, 14],
    });
  }, [fleet, selected]);
  return (
    <div
      className="chart"
      ref={host}
      role="region"
      aria-label="Interactive flight trajectory chart"
    />
  );
}
