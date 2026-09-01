"use client";

import { useEffect, useState } from "react";
import { LocationCard, type CardFreshness } from "@/components/LocationCard";
import { distanceMiles } from "@/lib/geo";
import { computeBestBetScore } from "@/lib/bestbet";
import type { Quality } from "@/lib/quality";

export interface BestBetLocation {
  id: string;
  name: string;
  city: string;
  state: string;
  lat: number;
  lng: number;
  freshness: CardFreshness;
  quality: Quality;
}

type GeoStatus = "loading" | "granted" | "unavailable";

export function BestBetList({ locations }: { locations: BestBetLocation[] }) {
  const [geoStatus, setGeoStatus] = useState<GeoStatus>("loading");
  const [userCoords, setUserCoords] = useState<{ lat: number; lng: number } | null>(null);

  useEffect(() => {
    requestLocation();
  }, []);

  function requestLocation() {
    if (!("geolocation" in navigator)) {
      setGeoStatus("unavailable");
      return;
    }
    setGeoStatus("loading");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setUserCoords({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setGeoStatus("granted");
      },
      () => setGeoStatus("unavailable"),
      { timeout: 8000, maximumAge: 5 * 60 * 1000 }
    );
  }

  const ranked = locations
    .map((loc) => {
      const distance = userCoords ? distanceMiles(userCoords, loc) : null;
      const score = computeBestBetScore({
        freshnessLevel: loc.freshness.level,
        quality: loc.quality,
        distanceMiles: distance,
      });
      return { ...loc, distance, score };
    })
    .sort((a, b) => b.score - a.score);

  const [top, ...rest] = ranked;

  return (
    <div className="flex flex-col gap-3">
      {geoStatus === "unavailable" && (
        <div className="flex items-center justify-between rounded-lg border border-dashed border-gray-300 bg-white p-3 text-sm text-gray-500">
          <span>Enable location to rank by distance too — right now it's freshness + quality only.</span>
          <button onClick={requestLocation} className="font-medium text-gray-900 hover:underline">
            Try again
          </button>
        </div>
      )}

      {top && (
        <div>
          <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-gray-500">
            Best bet right now
          </p>
          <LocationCard
            id={top.id}
            name={top.name}
            city={top.city}
            state={top.state}
            freshness={top.freshness}
            quality={top.quality}
            distanceMiles={top.distance}
            highlight
          />
        </div>
      )}

      {rest.length > 0 && (
        <div className="flex flex-col gap-2">
          {rest.map((loc) => (
            <LocationCard
              key={loc.id}
              id={loc.id}
              name={loc.name}
              city={loc.city}
              state={loc.state}
              freshness={loc.freshness}
              quality={loc.quality}
              distanceMiles={loc.distance}
            />
          ))}
        </div>
      )}
    </div>
  );
}
