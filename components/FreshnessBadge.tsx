import type { FreshnessLevel } from "@/lib/freshness";

const STYLES: Record<FreshnessLevel, string> = {
  fresh: "bg-fresh/10 text-fresh border-fresh/30",
  picked_over: "bg-pickedover/10 text-pickedover border-pickedover/30",
  empty: "bg-empty/10 text-empty border-empty/30",
  stale: "bg-stale/10 text-stale border-stale/30",
};

export function FreshnessBadge({ level, label }: { level: FreshnessLevel; label: string }) {
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${STYLES[level]}`}
    >
      {label}
    </span>
  );
}
