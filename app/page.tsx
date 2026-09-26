import { prisma } from "@/lib/db";
import { computeFreshness } from "@/lib/freshness";
import { computeQuality } from "@/lib/quality";
import { BestBetList, type BestBetLocation } from "@/components/BestBetList";
import { MapLoader } from "@/components/MapLoader";
import type { MapLocation } from "@/components/LocationMap";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const locations = await prisma.location.findMany({
    include: { checkIns: { orderBy: { createdAt: "desc" } } },
    orderBy: { city: "asc" },
  });

  const bestBetLocations: BestBetLocation[] = locations.map((location) => {
    const freshness = computeFreshness(location.checkIns);
    return {
      id: location.id,
      name: location.name,
      city: location.city,
      state: location.state,
      lat: location.lat,
      lng: location.lng,
      freshness: {
        level: freshness.level,
        label: freshness.label,
        lastReportAt: freshness.lastReport?.createdAt ?? null,
      },
      quality: computeQuality(location.checkIns),
    };
  });

  const mapLocations: MapLocation[] = bestBetLocations.map((loc) => ({
    id: loc.id,
    name: loc.name,
    lat: loc.lat,
    lng: loc.lng,
    freshnessLevel: loc.freshness.level,
    freshnessLabel: loc.freshness.label,
  }));

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Best bets near you</h1>
        <p className="text-sm text-gray-500">
          Ranked by freshness, haul quality, and distance — not just a flat list.
        </p>
      </div>

      <MapLoader locations={mapLocations} />

      {locations.length === 0 ? (
        <p className="text-sm text-gray-500">
          No locations yet. Run <code className="rounded bg-gray-100 px-1">npm run db:seed</code> to
          load example data.
        </p>
      ) : (
        <BestBetList locations={bestBetLocations} />
      )}
    </div>
  );
}
