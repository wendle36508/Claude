import Link from "next/link";
import { timeAgo } from "@/lib/freshness";

export interface HaulCardData {
  id: string;
  imagePath: string;
  caption: string | null;
  posterName: string | null;
  createdAt: Date;
  location: { id: string; name: string; city: string; state: string };
  forSale?: boolean;
  price?: number | null;
}

export function HaulCard({ haul, showLocation = true }: { haul: HaulCardData; showLocation?: boolean }) {
  return (
    <div className="overflow-hidden rounded-lg border bg-white">
      <div className="relative">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={haul.imagePath}
          alt={haul.caption ?? "Haul photo"}
          className="aspect-square w-full object-cover"
        />
        {haul.forSale && haul.price != null && (
          <span className="absolute right-2 top-2 rounded-full bg-gray-900 px-2 py-0.5 text-xs font-semibold text-white">
            ${haul.price.toFixed(2)}
          </span>
        )}
      </div>
      <div className="flex flex-col gap-1 p-3">
        {showLocation && (
          <Link href={`/locations/${haul.location.id}`} className="text-xs font-medium text-gray-700 hover:underline">
            📍 {haul.location.name}
          </Link>
        )}
        {haul.caption && <p className="text-sm text-gray-800">{haul.caption}</p>}
        <div className="flex items-center justify-between text-xs text-gray-400">
          <span>{haul.posterName ?? "Anonymous"}</span>
          <span>{timeAgo(haul.createdAt)}</span>
        </div>
      </div>
    </div>
  );
}
