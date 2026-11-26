import { useEffect, useRef } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import type { Drone, Point } from "./types";

export function Chart({
  fleet,
  selected,
  showAllDrones = false,
  onSelectDrone,
}: {
  fleet: Drone[];
  selected: Drone;
  showAllDrones?: boolean;
  onSelectDrone?: (id: number) => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);
  const vehicle = useRef<L.Marker | null>(null);

  useEffect(() => {
    const m = L.map(host.current!, {
      attributionControl: false,
      scrollWheelZoom: false,
      minZoom: 12,
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
    if (selected.route.length > 0) {
      map.current!.fitBounds(L.latLngBounds(selected.route).pad(0.45), {
        animate: false,
      });
    }
  }, [selected.id]);

  useEffect(() => {
    const g = layer.current!;
    g.clearLayers();
    fleet.forEach((d) =>
      L.polyline(d.route, {
        color: d.id === selected.id ? "#14b8a6" : "#475569",
        weight: d.id === selected.id ? 3 : 1.5,
        dashArray: "6 7",
      }).addTo(g),
    );

    const activeDrones = showAllDrones ? fleet : [selected];
    activeDrones.forEach((d) => {
      const reported: Point[] = d.track.map((s) => [
        s.reading.latitude,
        s.reading.longitude,
      ]);
      if (reported.length > 0) {
        const isSpoofed =
          d.gps_status === "Spoofed" ||
          d.mode === "Attitude hold" ||
          d.track.at(-1)?.classification === "GPS Spoofed";
        L.polyline(reported, {
          color: d.id === selected.id ? "#f97316" : "#64748b",
          weight: d.id === selected.id ? 3 : 2,
        }).addTo(g);

        d.track.forEach((s) => {
          if (s.classification === "GPS Spoofed" || (s.deviation_m ?? 0) > 150) {
            L.circleMarker([s.reading.latitude, s.reading.longitude], {
              radius: 6,
              color: "#ef4444",
              fillColor: "#ef4444",
              fillOpacity: 0.75,
            })
              .bindTooltip(
                `${d.name} · Suspicious fix (${Math.round(s.deviation_m ?? 0)}m)`,
              )
              .addTo(g);
          }
        });

        const latest = reported[reported.length - 1];
        const marker = L.circleMarker(latest, {
          radius: d.id === selected.id ? 6 : 5,
          color: isSpoofed ? "#ef4444" : "#f97316",
          fillColor: isSpoofed ? "#ef4444" : "#f97316",
          fillOpacity: 1,
        })
          .bindTooltip(
            `${d.id === selected.id ? "Reported GPS" : d.name} · ${latest[0].toFixed(4)}, ${latest[1].toFixed(4)}`,
          )
          .addTo(g);
        if (onSelectDrone) {
          marker.on("click", () => onSelectDrone(d.id));
        }
      }
    });

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
  }, [fleet, selected, showAllDrones, onSelectDrone]);

  return (
    <div
      className="chart"
      ref={host}
      role="region"
      aria-label="Interactive flight trajectory chart"
    />
  );
}
