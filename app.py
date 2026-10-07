import csv
import io
import json
import os
import time
from datetime import date
from pathlib import Path

import requests
from flask import Flask, Response, abort, jsonify, render_template

app = Flask(__name__)

# Configuration comes from environment variables (no secrets are needed: OBIS is open).
OBIS_BASE = os.environ.get("OBIS_BASE_URL", "https://api.obis.org/v3")
GRID_PRECISION = int(os.environ.get("GRID_PRECISION", "5"))
CACHE_TTL = int(os.environ.get("CACHE_TTL_SECONDS", "3600"))
TIMEOUT = int(os.environ.get("OBIS_TIMEOUT_SECONDS", "60"))
CSV_MAX = int(os.environ.get("CSV_MAX_RECORDS", "1000"))

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


CSV_COLUMNS = ["id", "occurrenceID", "scientificName", "aphiaID", "taxonRank", "phylum", "class",
               "order", "family", "eventDate", "date_year", "decimalLatitude", "decimalLongitude",
               "basisOfRecord", "datasetName", "dataset_id", "institutionCode"]


@app.route("/api/areas/<area_id>/records.csv")
def records_csv(area_id):
    """A capped sample of the underlying records (presence only), with a citation header."""
    feature = get_feature(area_id)
    data = obis_get("occurrence", geometry=to_wkt(feature), size=CSV_MAX, absence="false")
    results = data.get("results", [])
    total = data.get("total", len(results))
    name = feature["properties"]["name"]

    out = io.StringIO()
    out.write("# Source: OBIS (Ocean Biodiversity Information System), Intergovernmental "
              "Oceanographic Commission of UNESCO, https://obis.org\n")
    out.write(f"# Retrieved {date.today().isoformat()} via {OBIS_BASE}/occurrence for the "
              f"approximate outline of {name}.\n")
    out.write(f"# This file holds {len(results)} of {total} matching records (capped sample). "
              "Cite OBIS and the individual datasets (dataset_id) when you reuse the data.\n")
    writer = csv.writer(out)
    writer.writerow(CSV_COLUMNS)
    for rec in results:
        writer.writerow([rec.get(c, "") for c in CSV_COLUMNS])

    filename = f"obis_{area_id}_{date.today().isoformat()}.csv"
    return Response(out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment; filename={filename}"})