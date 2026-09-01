import Link from "next/link";
import { notFound } from "next/navigation";
import { prisma } from "@/lib/db";
import { computeFreshness, timeAgo } from "@/lib/freshness";
import { computeQuality } from "@/lib/quality";
import { FreshnessBadge } from "@/components/FreshnessBadge";
import { StarRating } from "@/components/StarRating";
import { CheckInForm } from "@/components/CheckInForm";
import { HaulCard } from "@/components/HaulCard";
import type { CheckInStatus } from "@/lib/types";

export const dynamic = "force-dynamic";

const STATUS_LABEL: Record<CheckInStatus, string> = {
  FRESH: "Fresh bins",
  PICKED_OVER: "Picked over",
  EMPTY: "Empty",
};

export default async function LocationDetailPage({ params }: { params: { id: string } }) {
  const location = await prisma.location.findUnique({
    where: { id: params.id },
    include: {
      checkIns: { orderBy: { createdAt: "desc" } },
      hauls: { orderBy: { createdAt: "desc" }, take: 6 },
    },
  });

  if (!location) notFound();

  const freshness = computeFreshness(location.checkIns);
  const quality = computeQuality(location.checkIns);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">{location.name}</h1>
        <p className="text-sm text-gray-500">
          {location.address}, {location.city}, {location.state}
        </p>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <FreshnessBadge level={freshness.level} label={freshness.label} />
          {freshness.lastReport && (
            <span className="text-xs text-gray-400">{timeAgo(freshness.lastReport.createdAt)}</span>
          )}
          {quality.count > 0 && (
            <span className="flex items-center gap-1">
              <StarRating value={quality.average} size={13} />
              <span className="text-xs text-gray-500">
                {quality.average.toFixed(1)} ({quality.count})
              </span>
            </span>
          )}
        </div>
        {location.scheduleNote && (
          <p className="mt-2 text-sm text-gray-500">📅 {location.scheduleNote}</p>
        )}
      </div>

      <CheckInForm locationId={location.id} />

      <div>
        <h2 className="mb-2 font-medium">Recent reports</h2>
        {location.checkIns.length === 0 ? (
          <p className="text-sm text-gray-500">No reports yet — be the first.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {location.checkIns.map((checkIn) => (
              <li key={checkIn.id} className="rounded-lg border bg-white p-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2">
                    <span className="font-medium">
                      {STATUS_LABEL[checkIn.status as CheckInStatus]}
                    </span>
                    {checkIn.rating != null && <StarRating value={checkIn.rating} size={11} />}
                  </span>
                  <span className="text-xs text-gray-400">{timeAgo(checkIn.createdAt)}</span>
                </div>
                {checkIn.note && <p className="mt-1 text-gray-600">{checkIn.note}</p>}
                {checkIn.reporterName && (
                  <p className="mt-1 text-xs text-gray-400">— {checkIn.reporterName}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div>
        <div className="mb-2 flex items-center justify-between">
          <h2 className="font-medium">Recent hauls</h2>
          <Link
            href={`/hauls?location=${location.id}`}
            className="text-sm text-gray-500 hover:underline"
          >
            Post a haul →
          </Link>
        </div>
        {location.hauls.length === 0 ? (
          <p className="text-sm text-gray-500">No hauls posted from here yet.</p>
        ) : (
          <div className="grid grid-cols-3 gap-2">
            {location.hauls.map((haul) => (
              <HaulCard
                key={haul.id}
                showLocation={false}
                haul={{
                  ...haul,
                  location: {
                    id: location.id,
                    name: location.name,
                    city: location.city,
                    state: location.state,
                  },
                }}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
