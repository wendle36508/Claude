import type { Chain } from "../lib/types";

export interface DirectoryLocation {
  slug: string;
  name: string;
  chain: Chain;
  address: string;
  city: string;
  state: string;
  lat: number;
  lng: number;
  hours: string | null;
  scheduleNote: string | null;
}

/**
 * The real, verified bin store directory. Synced into the database on
 * every deploy by prisma/sync-directory.ts (upsert by slug — never
 * deletes, so removing an entry here won't wipe its check-ins/hauls).
 *
 * Only list stores confirmed as true pay-by-the-pound thrift bins.
 * Pilot region: MA, RI, CT. As of Sept 2026 research, MA has no
 * confirmed Goodwill bins — sources claiming otherwise didn't hold up.
 */
export const DIRECTORY: DirectoryLocation[] = [
  {
    slug: "goodwill-outlet-hamden-ct",
    name: "Goodwill Outlet — Hamden",
    chain: "GOODWILL_OUTLET",
    address: "2901 State St",
    city: "Hamden",
    state: "CT",
    // Approximate — no geocoder reachable when this was added. Verify on a map.
    lat: 41.3618,
    lng: -72.8852,
    hours: "Mon–Sat 8am–7pm, Sun 9am–7pm",
    scheduleNote: null,
  },
  {
    slug: "goodwill-outlet-providence-ri",
    name: "Goodwill Outlet — Providence",
    chain: "GOODWILL_OUTLET",
    address: "100 Houghton St",
    city: "Providence",
    state: "RI",
    lat: 41.856598,
    lng: -71.435864,
    hours: "Mon–Sat 9am–6pm, closed Sun",
    scheduleNote: null,
  },
];
