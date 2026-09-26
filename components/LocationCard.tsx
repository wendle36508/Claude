import Link from "next/link";
import { FreshnessBadge } from "@/components/FreshnessBadge";
import { StarRating } from "@/components/StarRating";
import { timeAgo, type FreshnessLevel } from "@/lib/freshness";
import type { Quality } from "@/lib/quality";

export interface CardFreshness {
  level: FreshnessLevel;
  label: string;
  lastReportAt: Date | null;
}

export function LocationCard({
  id,
  name,
  city,
  state,
  freshness,
  quality,
  distanceMiles,
  highlight = false,
}: {
  id: string;
  name: string;
  city: string;
  state: string;
  freshness: CardFreshness;
  quality?: Quality;
  distanceMiles?: number | null;
  highlight?: boolean;
}) {
  const hasQuality = quality && quality.count > 0;
  const hasDistance = distanceMiles != null;

  return (
    <Link
      href={`/locations/${id}`}
      className={`flex items-center justify-between rounded-lg border bg-white p-4 hover:border-gray-400 ${
        highlight ? "border-2 border-gray-900" : ""
      }`}
    >
      <div>
        <p className="font-medium">{name}</p>
        <p className="text-sm text-gray-500">
          {city}, {state}
        </p>
        {(hasQuality || hasDistance) && (
          <div className="mt-1 flex items-center gap-2">
            {hasQuality && <StarRating value={quality!.average} size={12} showValue />}
            {hasDistance && (
              <span className="text-xs text-gray-400">{distanceMiles!.toFixed(1)} mi</span>
            )}
          </div>
        )}
      </div>
      <div className="flex flex-col items-end gap-1">
        <FreshnessBadge level={freshness.level} label={freshness.label} />
        {freshness.lastReportAt && (
          <span className="text-xs text-gray-400">{timeAgo(freshness.lastReportAt)}</span>
        )}
      </div>
    </Link>
  );
}
