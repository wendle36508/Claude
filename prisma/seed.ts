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
    key: "denver-goodwill",
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
    key: "denver-savers",
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
    key: "aurora-savers",
    // Farther from central Denver than the other two, but consistently
    // rated higher — a real illustration of why "best bet" isn't just
    // "nearest": this one can out-rank closer options on the merits.
    name: "Savers Outlet (example) — Aurora",
    chain: Chain.SAVERS_OUTLET,
    address: "Address TBD — verify before launch",
    city: "Aurora",
    state: "CO",
    lat: 39.7294,
    lng: -104.8319,
    scheduleNote: "New bins reported ~9am daily (unverified)",
  },
  {
    key: "phoenix-goodwill",
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
    key: "phoenix-bin-co",
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
    key: "seattle-goodwill",
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

// Seed check-ins per location, keyed by the location's `key` above.
// Ratings are the 1-5 haul-quality star rating; status drives freshness.
const checkInsByLocation: Record<
  string,
  { status: CheckInStatus; rating: number | null; note: string; reporterName: string; hoursAgo: number }[]
> = {
  "denver-goodwill": [
    { status: CheckInStatus.FRESH, rating: 4, note: "Just rotated, tons of new stuff", reporterName: "seed-data", hoursAgo: 0.75 },
    { status: CheckInStatus.FRESH, rating: 3, note: "Decent but a lot of home goods", reporterName: "seed-data", hoursAgo: 20 },
  ],
  "denver-savers": [
    { status: CheckInStatus.FRESH, rating: 3, note: "Fresh but pretty average haul", reporterName: "seed-data", hoursAgo: 3 },
  ],
  "aurora-savers": [
    { status: CheckInStatus.FRESH, rating: 5, note: "Incredible find, worth the drive", reporterName: "seed-data", hoursAgo: 0.5 },
    { status: CheckInStatus.FRESH, rating: 5, note: "Consistently the best bins in the area", reporterName: "seed-data", hoursAgo: 30 },
  ],
  "phoenix-bin-co": [
    { status: CheckInStatus.PICKED_OVER, rating: 2, note: "Pretty picked through by early afternoon", reporterName: "seed-data", hoursAgo: 5 },
  ],
};

async function main() {
  await prisma.haul.deleteMany();
  await prisma.checkIn.deleteMany();
  await prisma.seller.deleteMany();
  await prisma.location.deleteMany();

  const locationByKey: Record<string, string> = {};

  for (const { key, ...location } of locations) {
    const created = await prisma.location.create({ data: location });
    locationByKey[key] = created.id;

    for (const checkIn of checkInsByLocation[key] ?? []) {
      await prisma.checkIn.create({
        data: {
          locationId: created.id,
          status: checkIn.status,
          rating: checkIn.rating,
          note: checkIn.note,
          reporterName: checkIn.reporterName,
          createdAt: new Date(Date.now() - checkIn.hoursAgo * 60 * 60 * 1000),
        },
      });
    }
  }

  // One demo storefront so /market has something to show without
  // needing to click through the claim flow first.
  const seller = await prisma.seller.create({
    data: {
      handle: "seed-reseller",
      displayName: "Seed Reseller (example)",
      bio: "Demo storefront created by the seed script — flip finds from the bins.",
      contactLink: "@seed-reseller on Poshmark (example)",
    },
  });

  await prisma.haul.create({
    data: {
      locationId: locationByKey["denver-goodwill"],
      // Inline placeholder pixel — kept self-contained rather than an
      // external URL so the seed doesn't depend on outbound network.
      imagePath:
        "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
      caption: "Leather jacket, barely worn — grabbed for $3 at the bins",
      posterName: "seed-data",
      forSale: true,
      price: 28,
      sellerId: seller.id,
    },
  });
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
