import { PrismaClient } from "@prisma/client";
import type { Chain, CheckInStatus } from "../lib/types";

const prisma = new PrismaClient();

const Chain = {
  GOODWILL_OUTLET: "GOODWILL_OUTLET" as Chain,
  SAVERS_OUTLET: "SAVERS_OUTLET" as Chain,
  INDEPENDENT_BIN_STORE: "INDEPENDENT_BIN_STORE" as Chain,
};

const CheckInStatus = {
  FRESH: "FRESH" as CheckInStatus,
  PICKED_OVER: "PICKED_OVER" as CheckInStatus,
};

/**
 * PLACEHOLDER seed data. Coordinates are approximate city centers, not
 * verified store addresses — this is here so the app has something to
 * render locally. Cold-start step 1 (see README) is replacing this with
 * a real, verified directory for the pilot metro(s) before launch.
 */
const locations = [
  {
    name: "Goodwill Outlet (example) — Denver",
    chain: Chain.GOODWILL_OUTLET,
    address: "Address TBD — verify before launch",
    city: "Denver",
    state: "CO",
    lat: 39.7392,
    lng: -104.9903,
    scheduleNote: "New bins reported ~10am Tue/Thu/Sat (unverified)",
  },
  {
    name: "Savers Outlet (example) — Denver",
    chain: Chain.SAVERS_OUTLET,
    address: "Address TBD — verify before launch",
    city: "Denver",
    state: "CO",
    lat: 39.7047,
    lng: -105.0814,
    scheduleNote: null,
  },
  {
    name: "Goodwill Outlet (example) — Phoenix",
    chain: Chain.GOODWILL_OUTLET,
    address: "Address TBD — verify before launch",
    city: "Phoenix",
    state: "AZ",
    lat: 33.4484,
    lng: -112.074,
    scheduleNote: "New bins reported daily ~9am (unverified)",
  },
  {
    name: "Independent Bin Store (example) — Phoenix",
    chain: Chain.INDEPENDENT_BIN_STORE,
    address: "Address TBD — verify before launch",
    city: "Phoenix",
    state: "AZ",
    lat: 33.5722,
    lng: -112.0891,
    scheduleNote: null,
  },
  {
    name: "Goodwill Outlet (example) — Seattle",
    chain: Chain.GOODWILL_OUTLET,
    address: "Address TBD — verify before launch",
    city: "Seattle",
    state: "WA",
    lat: 47.6062,
    lng: -122.3321,
    scheduleNote: "New bins reported ~11am Mon/Wed/Fri (unverified)",
  },
];

async function main() {
  await prisma.checkIn.deleteMany();
  await prisma.location.deleteMany();

  for (const location of locations) {
    const created = await prisma.location.create({ data: location });

    // Give a couple of locations seed check-ins so the freshness UI has
    // something real to render (fresh, picked-over, and stale examples).
    if (location.city === "Denver" && location.chain === Chain.GOODWILL_OUTLET) {
      await prisma.checkIn.create({
        data: {
          locationId: created.id,
          status: CheckInStatus.FRESH,
          note: "Just rotated, tons of new stuff",
          reporterName: "seed-data",
          createdAt: new Date(Date.now() - 45 * 60 * 1000),
        },
      });
    }

    if (location.chain === Chain.INDEPENDENT_BIN_STORE) {
      await prisma.checkIn.create({
        data: {
          locationId: created.id,
          status: CheckInStatus.PICKED_OVER,
          note: "Pretty picked through by early afternoon",
          reporterName: "seed-data",
          createdAt: new Date(Date.now() - 5 * 60 * 60 * 1000),
        },
      });
    }
  }
}

main()
  .then(async () => {
    await prisma.$disconnect();
  })
  .catch(async (e) => {
    console.error(e);
    await prisma.$disconnect();
    process.exit(1);
  });
