import { prisma } from "@/lib/db";
import { computeFreshness } from "@/lib/freshness";
import { LocationCard } from "@/components/LocationCard";
import { MapLoader } from "@/components/MapLoader";
import type { MapLocation } from "@/components/LocationMap";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  const locations = await prisma.location.findMany({
    include: { checkIns: { orderBy: { createdAt: "desc" }, take: 1 } },
    orderBy: { city: "asc" },
  });

  const withFreshness = locations.map((location) => ({
    location,
    freshness: computeFreshness(location.checkIns),
  }));

  const mapLocations: MapLocation[] = withFreshness.map(({ location, freshness }) => ({
    id: location.id,
    name: location.name,
    lat: location.lat,
    lng: location.lng,
    freshnessLevel: freshness.level,
    freshnessLabel: freshness.label,
  }));

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Bin locations</h1>
        <p className="text-sm text-gray-500">
          Crowdsourced freshness reports for outlet bin stores. Green = reported fresh recently.
        </p>
      </div>

      <MapLoader locations={mapLocations} />

      {locations.length === 0 ? (
        <p className="text-sm text-gray-500">
          No locations yet. Run <code className="rounded bg-gray-100 px-1">npm run db:seed</code> to
          load example data.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          {withFreshness.map(({ location, freshness }) => (
            <LocationCard
              key={location.id}
              id={location.id}
              name={location.name}
              city={location.city}
              state={location.state}
              freshness={freshness}
            />
          ))}
        </div>
      )}
    </div>
  );
}
