# MPA Data Explorer

A small prototype for the question "what OBIS data exist inside this marine protected area, and where are the gaps?" Pick an area, see the OBIS records on a map, see records per year and per phylum, and download the records as CSV with a citation line.

## How to run

```bash
git clone https://github.com/yeryani-tests/mpa-data-explorer.git
cd mpa-data-explorer
docker build -t mpa-explorer .
docker run --rm -p 8000:8000 mpa-explorer
```

Open http://localhost:8000. The browser needs internet access (OBIS data, and the map and chart libraries load from public CDNs). Optional environment variables: `PORT`, `GRID_PRECISION`, `CSV_MAX_RECORDS`, `CHECKLIST_MAX_ROWS`, `CACHE_TTL_SECONDS`, `OBIS_BASE_URL`.

## What it does

- **Areas:** Cabo Pulmo (Mexico), Tubbataha Reefs (Philippines), Lundy (UK). The outlines are **simplified rectangles I drew by hand, not official boundaries.**
- **Map:** OBIS grid cells (about 5 km) shaded by record count, instead of individual points, so the page stays fast even with 145,000 records (Tubbataha).
- **Records per year:** every year from the first record to today is shown; years with no records are red bars.
- **Records per phylum:** 14 major marine groups; groups with no records are red bars labelled "(none)".
- **CSV:** the first 1,000 records, with `#` lines at the top giving the source, retrieval date and a citation note.

## Container choices

- **Base image:** `python:3.12-slim`, an official image that is small and gets security updates; the dependencies are pure Python, so no compiler is needed.
- **Pinning:** exact versions in `requirements.txt`. The base image is pinned to a version tag, not a digest, which is easier to read but less strict.
- **Trade-offs:** dependencies install before the app code is copied, so code edits rebuild fast. Image size is about XXX MB. A multi-stage build would save little here.
- **Security and configuration:** the app runs as a non-root user, and all settings are environment variables. OBIS is open, so there are no secrets. In a real deployment, any key would come from the platform's secret store, never from the image or the repository.

## Deliberately not built

- The node and institution panel: OBIS records carry IDs only, so names need a second lookup.
- Official boundaries (Marine Regions or WDPA): licensing and file size were more than the 90 minutes allowed.
- A base map: public tile servers need keys or impose usage limits.
- Automated tests and a full CSV export.

## Known limitations

- Outlines are approximate; grid cells are coarse and extend past the outline.
- The year chart leaves out records with no date (Cabo Pulmo: 5,331 dated of 5,890).
- One year dominates Tubbataha, so small years are hard to see on a linear scale.
- Phylum counts come from the OBIS checklist, capped at 1,000 rows.
- The CSV is the first 1,000 records, not a representative sample (710 are iNaturalist for Cabo Pulmo). Read it with `comment="#"`.
- The cache is in memory and per process. I tested by hand and with a mocked API, not with automated tests.

## With two more days

Real boundaries from Marine Regions or WDPA; the node and institution panel with names; a paged full CSV export; a log scale and a per-dataset breakdown; automated tests; bundled map and chart libraries so it works offline; and a PostGIS-backed version (see Question 4).