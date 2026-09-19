# Runs the wealth_lab API (wealth_lab/api.py) for real deployment - see
# DEPLOYMENT.md for the full checklist this fits into (Finnhub signup,
# WEALTH_LAB_DB_PATH pointed at a persistent volume, CORS lockdown).
# Not used anywhere in this sandboxed session - there's no network access
# here to build/run a container against a live provider. Written for you
# to build wherever you actually deploy.
FROM python:3.12-slim

WORKDIR /app

COPY requirements-live.txt requirements.txt ./
RUN pip install --no-cache-dir -r requirements-live.txt

COPY wealth_lab ./wealth_lab
COPY report/console.html ./report/console.html

# The database file itself is NOT copied in - it's created fresh (empty)
# on first run at WEALTH_LAB_DB_PATH, which should point at a mounted
# persistent volume (see fly.toml), never at a path inside the image -
# anything written inside the image's own filesystem is lost on redeploy.
ENV WEALTH_LAB_DB_PATH=/data/tracker.db

EXPOSE 8080
CMD ["uvicorn", "wealth_lab.api:app", "--host", "0.0.0.0", "--port", "8080"]
