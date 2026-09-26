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
 * Pilot region: MA, RI, CT, plus Hudson NH as the nearest bins for
 * Boston-area shoppers. As of Sept 2026 research, MA itself has no
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
  {
    slug: "goodwill-outlet-hudson-nh",
    name: "Goodwill Buy the Pound Outlet — Hudson",
    chain: "GOODWILL_OUTLET",
    address: "9 Wason Rd",
    city: "Hudson",
    state: "NH",
    // Street-level coordinates for Wason Rd (short road), not the exact building.
    lat: 42.73187,
    lng: -71.424196,
    // Sources conflict: Apple Maps lists outlet 7am–4pm, Yelp lists the store 9am–6pm.
    hours: "Outlet daily 7am–4pm (unconfirmed; main store 9am–6pm)",
    scheduleNote: null,
  },
];
