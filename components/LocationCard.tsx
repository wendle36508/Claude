import Link from "next/link";
import { FreshnessBadge } from "@/components/FreshnessBadge";
import { timeAgo, type Freshness } from "@/lib/freshness";

export function LocationCard({
  id,
  name,
  city,
  state,
  freshness,
}: {
  id: string;
  name: string;
  city: string;
  state: string;
  freshness: Freshness;
}) {
  return (
    <Link
      href={`/locations/${id}`}
      className="flex items-center justify-between rounded-lg border bg-white p-4 hover:border-gray-400"
    >
      <div>
        <p className="font-medium">{name}</p>
        <p className="text-sm text-gray-500">
          {city}, {state}
        </p>
      </div>
      <div className="flex flex-col items-end gap-1">
        <FreshnessBadge level={freshness.level} label={freshness.label} />
        {freshness.lastReport && (
          <span className="text-xs text-gray-400">{timeAgo(freshness.lastReport.createdAt)}</span>
        )}
      </div>
    </Link>
  );
}
