# BinBuddy

Find fresh bin drops at outlet thrift stores (Goodwill Outlet, Savers Outlet,
independent "bin stores") near you. Bin stores rotate their inventory on a
schedule and get picked clean within hours, so a static map of locations
isn't useful on its own — the core signal this app provides is *freshness*:
is a given location's bins currently worth a drive.

Two directory sites (thebinfinder.com, thriftbins.com) already list bin
locations with static, manager-verified schedules. BinBuddy's bet is the
thing a content site structurally can't do: live, crowdsourced "is it fresh
right now" reporting, a "which of my nearby bins is worth the drive"
ranking, and a haul feed where people post finds tagged to the location —
none of which exist in the current directories.

## Stack

- Next.js 14 (App Router) + TypeScript
- Prisma + Postgres (local dev points at a local Postgres — see below;
  production points at whatever `DATABASE_URL` a host injects)
- Tailwind CSS
- Leaflet / react-leaflet for the map (OpenStreetMap tiles, no API key)
- Haul photos: local disk in dev, Vercel Blob in production (automatic —
  see `app/api/hauls/route.ts`)
- No auth in the MVP — check-ins, hauls, and even seller storefronts
  (below) are all trust-based, no login. A claimed seller handle is the
  closest thing to an account this app has.

## Getting started

Needs a local Postgres. Copy `.env.example` to `.env` and point
`DATABASE_URL` at it.

```bash
npm install
npm run db:migrate   # applies the schema
npm run db:seed      # loads example locations, check-ins, and a demo storefront
npm run dev
```

Then open http://localhost:3000.

## Data model

- **Location** — a bin store: chain, address, coordinates, and an optional
  `scheduleNote` (the store's own rotation schedule, e.g. "new bins ~10am
  Mon/Wed/Fri"). This is the fallback signal when there's no recent
  crowdsourced data yet.
- **CheckIn** — a freshness report against a location: `FRESH` /
  `PICKED_OVER` / `EMPTY`, an optional note, an optional reporter name.
  The most recent check-in (within a rolling window) drives the badge
  shown on the map and location list.
- **Haul** — a photo post of what someone found, tagged to the location
  they got it from. Separate from `CheckIn`: a haul is about the find, a
  check-in is about the state of the bins. A haul can optionally be
  listed for resale (`forSale` + `price`, tied to a `Seller`) — the same
  post shows up both in the location's haul feed and on the seller's
  storefront, rather than being a second, duplicate listing.
- **Seller** — a reseller's public storefront at `/market/<handle>`. The
  handle is claimed once, no password — see "No auth" above for why
  that's an acceptable amount of trust for now and where it stops being
  one.

⚠️ **The seed data in `prisma/seed.ts` is placeholder** — approximate city
coordinates and `"Address TBD"` placeholders, not a verified directory. See
cold-start step 1 below before this goes anywhere near real users.

## The cold-start plan

The hard problem isn't the product, it's that freshness data is worthless
without active users in a city, and users won't show up to an app with no
data. Sequencing to get out of that hole:

1. **Seed the location directory manually, don't crowdsource it.** Outlet
   bin stores are a small, fixed set (~a few hundred in the US across
   Goodwill Outlet, Savers/Value Village Outlet, and independent bin
   stores). Compile real addresses/hours from store locators and public
   listings for the pilot metro(s) before launch — this alone makes the
   app useful (a verified directory + hours) even with zero check-ins.
2. **Capture each store's own rotation schedule where it's public.**
   Many outlets post or informally share a rotation schedule. Getting this
   into `scheduleNote` for each location means the app has a useful signal
   from day one, not just "no data yet."
3. **Launch in 1–2 pilot metros with existing bin communities**, not
   nationally. Look for cities with an active subreddit or Facebook group
   already coordinating bin runs informally — that's a lower liquidity bar
   to cross (dozens of engaged users, not thousands) and a place to
   recruit first users directly rather than cold organic growth.
4. **Seed the first check-ins yourself** (or via a couple of recruited
   power users) for the first few weeks, so the app never shows an empty
   feed to a new visitor. An empty "recent reports" list on a new user's
   first visit is the fastest way to lose them.
5. **Push alerts are the retention hook, but they need step 1–2 done
   first.** Once locations + schedules are seeded, "notify me when this
   location rotates" is valuable even before crowdsourced check-ins are
   flowing — it's next on the roadmap once the directory work above is
   real.

## Deploying (Vercel)

1. Push this repo to GitHub (already done if you're reading this from
   the repo) and go to vercel.com → **Add New Project** → import it.
2. In the project's **Storage** tab: **Create Database → Postgres**
   (Vercel's native Neon-backed Postgres — no separate signup, and it
   auto-injects `DATABASE_URL` into the project's env vars).
3. Same **Storage** tab: **Create → Blob** — auto-injects
   `BLOB_READ_WRITE_TOKEN`. Once that's set, haul photo uploads
   automatically switch from local disk to Blob storage (see
   `app/api/hauls/route.ts` — same code path, no config needed beyond
   the env var existing).
4. Deploy. The build script (`npm run build`) runs
   `prisma migrate deploy` before `next build`, so the schema applies
   itself on every deploy — no manual migration step.
5. Optional: run `npm run db:seed` once against the production
   `DATABASE_URL` (e.g. `vercel env pull` then run it locally) if you
   want the example data live — skip this for a real launch and seed a
   verified directory instead (see cold-start plan below).

## Roadmap (not yet built)

- Push notifications for followed locations
- Real accounts (check-ins/hauls are still fully anonymous; seller
  handles are the only claimed identity, and even those have no
  password — someone else could currently claim a name-collision handle
  first. Fine for a prototype, not fine once real transactions happen
  through a storefront)
- Verified location directory replacing the placeholder seed data
- Nearest / Highest-rated toggle on the best-bet list (currently shows
  only the blended ranking) — see the earlier design mockup
