# Going live: what has to happen outside this session

This repo is provider-ready and, as of the Finnhub integration
(`wealth_lab/providers/finnhub.py`), the code side of "live" is built. What's
left is entirely account/infrastructure setup on your end - none of it can
be done from inside a Claude Code session, since this sandbox has no
outbound network access and nothing here persists once the session ends.

This is a checklist, in the order to actually do it. Each step says what it
costs and what happens if you skip it.

**Where to actually view the live site once it's deployed:** `https://<your-app>.fly.dev/dashboard`
- **not** the Claude Artifact link. Confirmed directly: a published Claude
Artifact can't fetch an external site's data - the platform sandboxes
outbound requests from published pages, so `console.html` published as an
Artifact always falls back to its static snapshot, no matter how well the
live API works. `wealth_lab/api.py`'s `/dashboard` route serves that exact
same HTML file from the API itself, so its same-origin `fetch('/snapshot')`
actually resolves to real data - that's the real live product; the Artifact
link is a preview of the same UI on stale/static data, nothing more.

## 1. Get a Finnhub API key

Free. https://finnhub.io/register - takes a couple minutes. Free tier is
60 calls/minute, which the implementation here is built against.

Skip this and the API keeps returning 503 for `/research/{symbol}` and the
lookup tool stays exactly as complete as whatever's been manually
researched - not broken, just not live.

## 2. Verify the provider actually works, for real

This has never made a live HTTP call (see `providers/README.md`) - it's
built directly from Finnhub's documented API shapes, tested against mocked
responses, not the real thing. Before trusting it in front of real
visitors, run this somewhere with real network access (your own machine is
fine):

```bash
pip install -r requirements-live.txt
export FINNHUB_API_KEY=<your key>
python3 -c "
from wealth_lab.providers.finnhub import FinnhubProvider
p = FinnhubProvider()
print('price:', p.get_price('AAPL'))
print('fundamentals:', p.get_fundamentals('AAPL'))
print('news:', p.get_news('AAPL')[:2])
"
```

If `price` isn't a real float or `fundamentals` is `None`, something's off
in the request shape or your key - fix it here before deploying, not after.

## 3. Pick where the database actually lives

The tracker is one SQLite file. Most hosts (including the free tiers of
Render, Railway, and most PaaS providers) wipe the filesystem on every
redeploy - if `data/tracker.db` lives inside the repo checkout like it does
by default, every push destroys the research history.

Fix: set `WEALTH_LAB_DB_PATH` to a path on a *persistent* volume, separate
from the code checkout. `db.py` reads this env var at import time (added
specifically for this - see its top).

```
WEALTH_LAB_DB_PATH=/data/tracker.db   # wherever your host's persistent volume mounts
```

**Recommended host for this reason: Fly.io.** Its free/hobby tier includes
a small persistent volume (unlike Render/Railway's free tiers, which don't),
which is exactly what a single-SQLite-file app like this needs without
paying for a managed Postgres you don't otherwise need.

The repo root already has `Dockerfile`, `fly.toml`, and `.dockerignore` set
up for this - written and confirmed to boot correctly (dependencies
install clean, `uvicorn` serves real responses on `/` and `/universe`) by
running it directly in this session, though the actual `docker build`
itself has never run here (no Docker daemon in this sandbox - build it for
real the first time you deploy). You need a [Fly.io account](https://fly.io)
and their CLI (`fly` / `flyctl`) installed - that's the part only you can
do.

```bash
fly launch --copy-config --name <your-app-name>   # from the repo root - uses the existing fly.toml, don't let it generate a new one
fly volumes create wealth_lab_data --size 1 --region iad   # matches fly.toml's [mounts] source and primary_region
fly secrets set FINNHUB_API_KEY=<your key>   # a secret, not a plain env var - WEALTH_LAB_PROVIDER is already set in fly.toml
fly deploy
```

If you outgrow a single SQLite file (concurrent writes from real multi-user
traffic, not just reads), that's a real migration to Postgres - not
supported by `db.py` today, and not needed until you're actually seeing
that kind of load.

## 3b. Seed the deployed database with the research already done

The volume you just created starts **empty**. Everything researched in
this Claude Code session so far - 40+ S&P 500 theses, each with sourced
signals - lives in this sandbox's local `data/tracker.db`, which is
`.gitignore`'d (never pushed) and not guaranteed to survive this container
being reclaimed. That research isn't lost even if the file is: every
thesis is also mirrored into `report/data.json`, which **is** committed to
git. But `data.json` is a read-only export, not the live database the
deployed API reads and writes - the deployed instance won't show any of
this research until you copy the real file over once:

```bash
fly ssh sftp shell   # opens an SFTP session against the running machine
# put <local path to data/tracker.db> /data/tracker.db
```

Do this once, before pointing real traffic at the deployment - after that,
the CLI's `wealth_lab` commands and this session's daily Routine keep
writing to the *local* `data/tracker.db` (not the deployed one), so you'd
repeat this copy step periodically, or switch the Routine to write
directly against the deployed API instead, to keep the two in sync. Which
of those you want is a workflow decision worth making deliberately, not a
default to pick silently.

## 4. Lock down CORS

`wealth_lab/api.py` ships with `allow_origins=["*"]` - fine for local
development, wrong for anything public. Before deploying, change it to
your actual frontend's origin:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-actual-frontend.example.com"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

## 5. Think about who can call `/research/{symbol}`

The API has no authentication. Once live, anyone can `POST
/research/{symbol}` for an arbitrary ticker, which spends a Finnhub API
call (free tier, but rate-limited) and writes a new thesis to your
database every time. That's fine for a personal tool behind an obscure
URL; it's a real cost/abuse surface if the URL gets shared or indexed.
Before that happens, add either:
- a simple shared-secret header check (a few lines in `api.py`), or
- a reverse-proxy-level rate limit (most hosts, including Fly.io, support
  this without app code changes).

Neither is built here - this is a decision about who should be able to
trigger writes to your database, not a default I should pick for you.

## 6. What's still NOT automatic even once all of this is live

`POST /research/{symbol}` creates a thesis skeleton (name, sector, entry
price) and logs recent headlines as *unclassified* signals - it
deliberately does not decide bullish/bearish on its own (see
`providers/README.md`'s last section for why, and what building that
classification step for real would take). A newly auto-researched ticker
shows up in the lookup tool with a real price and real headlines, but its
score stays at 0 (unclassified signals don't move it) until those
headlines get reviewed and reclassified - by you, or by the daily Routine,
same as any other name today.
