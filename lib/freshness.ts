import type { CheckIn } from "@prisma/client";
import type { CheckInStatus } from "@/lib/types";

export type FreshnessLevel = "fresh" | "picked_over" | "empty" | "stale";

export interface Freshness {
  level: FreshnessLevel;
  label: string;
  lastReport: CheckIn | null;
}

const FRESH_WINDOW_HOURS = 3;
const RECENT_WINDOW_HOURS = 24;

/**
 * Turns the latest check-in into a freshness signal. Falls back to
 * "stale" (no recent crowdsourced data) rather than hiding the location,
 * since the store's own schedule is still useful during cold-start.
 */
export function computeFreshness(checkIns: CheckIn[]): Freshness {
  const latest = checkIns[0] ?? null;

  if (!latest) {
    return { level: "stale", label: "No reports yet", lastReport: null };
  }

  const hoursAgo = (Date.now() - latest.createdAt.getTime()) / (1000 * 60 * 60);

  if (hoursAgo > RECENT_WINDOW_HOURS) {
    return { level: "stale", label: "No recent reports", lastReport: latest };
  }

  const status = latest.status as CheckInStatus;

  if (status === "FRESH") {
    return {
      level: "fresh",
      label: hoursAgo <= FRESH_WINDOW_HOURS ? "Fresh now" : "Fresh earlier today",
      lastReport: latest,
    };
  }

  if (status === "PICKED_OVER") {
    return { level: "picked_over", label: "Picked over", lastReport: latest };
  }

  return { level: "empty", label: "Reported empty", lastReport: latest };
}

export function timeAgo(date: Date): string {
  const minutes = Math.floor((Date.now() - date.getTime()) / (1000 * 60));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}
