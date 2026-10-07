import json
import os
import time
from datetime import date
from pathlib import Path

import requests
from flask import Flask, abort, jsonify, render_template

app = Flask(__name__)

# Configuration comes from environment variables (no secrets are needed: OBIS is open).
OBIS_BASE = os.environ.get("OBIS_BASE_URL", "https://api.obis.org/v3")
GRID_PRECISION = int(os.environ.get("GRID_PRECISION", "5"))
CACHE_TTL = int(os.environ.get("CACHE_TTL_SECONDS", "3600"))
TIMEOUT = int(os.environ.get("OBIS_TIMEOUT_SECONDS", "60"))

AREAS = json.loads((Path(__file__).parent / "mpa_areas.json").read_text(encoding="utf-8"))
FEATURES = {f["properties"]["id"]: f for f in AREAS["features"]}

_cache = {}  # in-memory, per process: (path, params) -> (timestamp, data)


def to_wkt(feature):
    ring = feature["geometry"]["coordinates"][0]
    return "POLYGON((" + ",".join(f"{x} {y}" for x, y in ring) + "))"


def obis_get(path, **params):
    key = (path, tuple(sorted(params.items())))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL:
        return hit[1]
    resp = requests.get(f"{OBIS_BASE}/{path}", params=params, timeout=TIMEOUT)
    resp.raise_for_status()
    data = resp.json()
    _cache[key] = (time.time(), data)
    return data


def get_feature(area_id):
    feature = FEATURES.get(area_id)
    if feature is None:
        abort(404)
    return feature


@app.errorhandler(requests.RequestException)
def obis_unavailable(err):
    return jsonify({"error": "OBIS could not be reached or returned an error",
                    "detail": str(err)[:200]}), 502


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/health")
def health():
    return {"status": "ok"}


@app.route("/api/areas")
def areas():
    return jsonify(AREAS)


@app.route("/api/areas/<area_id>/grid")
def grid(area_id):
    """OBIS records aggregated into grid cells (one polygon per cell, with a count n)."""
    data = obis_get(f"occurrence/grid/{GRID_PRECISION}", geometry=to_wkt(get_feature(area_id)))
    return jsonify(data)


@app.route("/api/areas/<area_id>/years")
def years(area_id):
    """Records per year, with every year from the first record to today filled in,
    so that years with no records appear as explicit zeros."""
    rows = obis_get("statistics/years", geometry=to_wkt(get_feature(area_id)))
    counts = {int(r["year"]): int(r["records"]) for r in rows if r.get("year") is not None}
    if not counts:
        return jsonify({"years": [], "records": [], "total": 0, "first_year": None,
                        "last_year": None, "empty_years": 0, "span_years": 0})
    first, last = min(counts), max(counts)
    all_years = list(range(first, max(last, date.today().year) + 1))
    records = [counts.get(y, 0) for y in all_years]
    return jsonify({
        "years": all_years,
        "records": records,
        "total": sum(records),
        "first_year": first,
        "last_year": last,
        "empty_years": sum(1 for n in records if n == 0),
        "span_years": len(all_years),
    })