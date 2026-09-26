import type { FreshnessLevel } from "@/lib/freshness";
import type { Quality } from "@/lib/quality";

// A location with no ratings yet isn't "bad" — it's unknown. Scoring it
// as 0 would bury every new/cold-start location under anything with even
// one mediocre rating, which fights the app's own cold-start problem.
// Treat "no ratings" as cautiously average instead.
const UNRATED_QUALITY_SCORE = 0.7;

// Freshness gates the score rather than just adding to it: a picked-over
// or empty location shouldn't out-rank a fresh one just because it's
// closer and better-rated historically — that's the one thing this app
// exists to prevent. "Stale" (no recent report at all) sits in between,
// since it's genuinely unknown rather than known-bad.
const FRESHNESS_MULTIPLIER: Record<FreshnessLevel, number> = {
  fresh: 1,
  picked_over: 0.65,
  empty: 0.35,
  stale: 0.5,
};

/** 1 at 0 miles, 0.5 at 5 miles, 0.33 at 10 miles — smooth falloff, no hard cutoff. */
function closenessScore(distanceMiles: number | null): number {
  if (distanceMiles == null) return 0.5; // no user location available — stay neutral
  return 1 / (1 + distanceMiles / 5);
}

function qualityScore(quality: Quality): number {
  return quality.count > 0 ? quality.average / 5 : UNRATED_QUALITY_SCORE;
}

export interface BestBetInput {
  freshnessLevel: FreshnessLevel;
  quality: Quality;
  distanceMiles: number | null;
}

/**
 * Ranks "worth the drive right now": closeness and quality weighted
 * equally, then scaled by how fresh the bins currently are.
 */
export function computeBestBetScore({ freshnessLevel, quality, distanceMiles }: BestBetInput): number {
  const blended = 0.5 * qualityScore(quality) + 0.5 * closenessScore(distanceMiles);
  return blended * FRESHNESS_MULTIPLIER[freshnessLevel];
}
