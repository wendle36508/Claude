export interface Quality {
  average: number;
  count: number;
}

/**
 * Average haul-quality rating (1-5 stars) from check-ins that included
 * one. Unrated check-ins (status-only reports) don't count toward this —
 * they still drive freshness, just not quality.
 */
export function computeQuality(checkIns: { rating: number | null }[]): Quality {
  const rated = checkIns.filter((c): c is { rating: number } => c.rating != null);
  if (rated.length === 0) return { average: 0, count: 0 };
  const sum = rated.reduce((total, c) => total + c.rating, 0);
  return { average: sum / rated.length, count: rated.length };
}
