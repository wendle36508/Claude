"use client";

import dynamic from "next/dynamic";
import type { MapLocation } from "@/components/LocationMap";

// next/dynamic's ssr:false only takes effect inside a Client Component —
// used from a Server Component it silently still SSRs, and Leaflet
// touches `window` at import time, so this wrapper is required.
const LocationMap = dynamic(
  () => import("@/components/LocationMap").then((mod) => mod.LocationMap),
  {
    ssr: false,
    loading: () => <div className="h-80 w-full animate-pulse rounded-lg border bg-gray-100" />,
  }
);

export function MapLoader({ locations }: { locations: MapLocation[] }) {
  return <LocationMap locations={locations} />;
}
