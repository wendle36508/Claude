"use client";

import { MapContainer, TileLayer, Marker, Popup } from "react-leaflet";
import L from "leaflet";
import Link from "next/link";
import type { FreshnessLevel } from "@/lib/freshness";

const MARKER_COLORS: Record<FreshnessLevel, string> = {
  fresh: "#16a34a",
  picked_over: "#d97706",
  empty: "#dc2626",
  stale: "#6b7280",
};

function markerIcon(level: FreshnessLevel) {
  const color = MARKER_COLORS[level];
  return L.divIcon({
    className: "",
    html: `<span style="display:block;width:14px;height:14px;border-radius:50%;background:${color};border:2px solid white;box-shadow:0 0 0 1px rgba(0,0,0,0.3)"></span>`,
    iconSize: [14, 14],
    iconAnchor: [7, 7],
  });
}

export interface MapLocation {
  id: string;
  name: string;
  lat: number;
  lng: number;
  freshnessLevel: FreshnessLevel;
  freshnessLabel: string;
}

export function LocationMap({ locations }: { locations: MapLocation[] }) {
  const center: [number, number] =
    locations.length > 0
      ? [locations[0].lat, locations[0].lng]
      : [39.8283, -98.5795]; // continental US fallback

  return (
    <MapContainer
      center={center}
      zoom={locations.length > 0 ? 5 : 4}
      scrollWheelZoom
      className="h-80 w-full rounded-lg border"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {locations.map((loc) => (
        <Marker key={loc.id} position={[loc.lat, loc.lng]} icon={markerIcon(loc.freshnessLevel)}>
          <Popup>
            <div className="text-sm">
              <p className="font-medium">{loc.name}</p>
              <p>{loc.freshnessLabel}</p>
              <Link href={`/locations/${loc.id}`} className="text-blue-600 underline">
                View details
              </Link>
            </div>
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
