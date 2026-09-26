// SQLite (Prisma) has no native enum support, so Chain/CheckInStatus are
// stored as plain strings and constrained by these TS unions at the
// application boundary instead.

export type Chain = "GOODWILL_OUTLET" | "SAVERS_OUTLET" | "INDEPENDENT_BIN_STORE" | "OTHER";

export const CHAINS: Chain[] = [
  "GOODWILL_OUTLET",
  "SAVERS_OUTLET",
  "INDEPENDENT_BIN_STORE",
  "OTHER",
];

export type CheckInStatus = "FRESH" | "PICKED_OVER" | "EMPTY";

export const CHECK_IN_STATUSES: CheckInStatus[] = ["FRESH", "PICKED_OVER", "EMPTY"];
