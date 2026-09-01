# Thrift Bins

Find fresh bin drops at outlet thrift stores (Goodwill Outlet, Savers Outlet,
independent "bin stores") near you. Bin stores rotate their inventory on a
schedule and get picked clean within hours, so a static map of locations
isn't useful on its own — the core signal this app provides is *freshness*:
is a given location's bins currently worth a drive.

## Stack

- Next.js 14 (App Router) + TypeScript
- Prisma + SQLite for local dev (swap the `DATABASE_URL` in `.env` for
  Postgres in production — schema is provider-agnostic)
- Tailwind CSS
- Leaflet / react-leaflet for the map (OpenStreetMap tiles, no API key)
- No auth in the MVP — check-ins take an optional free-text name

## Getting started

```bash
npm install
npm run db:migrate   # creates dev.db and applies the schema
npm run db:seed      # loads example locations (see note below)
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

## Roadmap (not yet built)

- Push notifications for followed locations
- User accounts (to build reporter trust/reputation over time)
- Verified location directory replacing the placeholder seed data
- Photo attachments on check-ins
