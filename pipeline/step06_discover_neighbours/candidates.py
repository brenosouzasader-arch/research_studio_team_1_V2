"""Step 06: discover nearby buildings that could join, and shortlist the 3-5 that fit best.

    python -m step06_discover_neighbours.candidates --host-dir data\\host\\nexus2 ^
        --host "Carrer de Jordi Girona 29, Barcelona" --out data\\neighbours\\nexus2
    python -m step06_discover_neighbours.candidates --host-dir data\\host\\demo ^
        --candidates-csv my_candidates.csv --out data\\neighbours\\demo

Two ways to get the candidates:
- Catastro (default): every plot whose centre is within --max-distance of the host, minus a
  safety margin (the law measures between meters; we only know plot centres). For each plot:
  dwellings, floors, footprint and use from Catastro, then step 05's baseline profile.
- --candidates-csv: a list you made yourself (e.g. other UPC buildings with SIRENA data).
  Columns: building_id, lat, lon, use_type (home/office/school/shop), and either
  yearly_kwh, or floor_m2 (+ dwellings for homes), or metered (path to a meter CSV).

Each candidate gets a fit score: how many kWh of the host's surplus (step 04) its predicted
use could take up over the year, hour by hour. The --shortlist best are kept.

Outputs in --out:
- candidate_buildings.geojson  every candidate: building_id, use_type, geometry, distance_m,
                               eligible_status, dwellings, yearly_kwh, fit_kwh, demand_source
- demand_hourly.csv            the shortlisted buildings' hourly use (same columns as step 04)
- shortlist.csv                the shortlist, best fit first

eligible_status is always "tentative": distance is the only rule checked. Connection,
metering and the signed agreement need a professional check (see the roadmap's guardrails).
Participation: only a share of the flats in a building will sign up (--join-rate, ASSUMPTION 40%).
"""
import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np

from step04_read_host_demand.host_table import read_host_table, read_metered
from step05_forecast_demand import baseline_profiles as dm

MAX_DISTANCE_M = 500.0      # RD 244/2019 strictest rule (5 km now allowed for solar up to 5 MW, RDL 7/2026)
DISTANCE_MARGIN_M = 50.0
SHORTLIST = 5
JOIN_RATE = 0.4             # ASSUMPTION: share of a building's flats that sign up


def distance_m(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 2 * 6371000 * math.asin(math.sqrt(h))


def fit_kwh(surplus, demand):
    """kWh of the host's surplus this building could use, hour by hour, over the year."""
    return float(np.minimum(surplus, demand).sum())


def demand_for(row, times, shapes, join_rate=JOIN_RATE):
    """Hourly use of one candidate (dict with use_type and yearly_kwh / floor_m2 / dwellings / metered)."""
    kind = (row.get("use_type") or "home").lower()
    if row.get("metered"):
        return read_metered(row["metered"], times), "metered"
    if row.get("yearly_kwh"):
        yearly = float(row["yearly_kwh"])
    elif kind == "home":
        dwellings = int(float(row.get("dwellings") or 1))
        flat_m2 = float(row.get("floor_m2") or dm.FLAT_M2_DEFAULT * dwellings) / max(dwellings, 1)
        yearly = dwellings * (dm.FLAT_BASE_KWH + dm.FLAT_KWH_PER_M2 * flat_m2)
    else:
        yearly = float(row.get("floor_m2") or 0) * dm.KIND_PER_M2.get(kind, dm.COMMERCIAL_KWH_PER_M2)
    if kind == "home":
        yearly *= join_rate
    return yearly * shapes.get(kind, shapes["home"]), f"proxy_{kind}"


def from_catastro(host_lat, host_lon, max_distance, cache_path):
    """Plots around the host from Catastro -> candidate rows (needs internet)."""
    from pyproj import Transformer
    from step01_select_host.parcels import download_parcels
    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:25831", always_xy=True).transform
    to_wgs = Transformer.from_crs("EPSG:25831", "EPSG:4326", always_xy=True).transform
    cx, cy = to_utm(host_lon, host_lat)
    cache = dm.load_cache(cache_path)
    rows = []
    for p in download_parcels(cx, cy, half=max_distance + 50):
        lon, lat = to_wgs(p["point"].x, p["point"].y)
        d = distance_m((host_lat, host_lon), (lat, lon))
        if d > max_distance:
            continue
        try:
            info = dm.building_from_catastro(p["refcat"], cache)
        except Exception as e:     # one bad plot should not stop the search
            print(f"skip {p['refcat']}: {str(e)[:80]}")
            continue
        b = dm.predict_yearly(p["refcat"], info["dwellings"], info["floors"], info["footprint_m2"],
                              info["current_use"], info["year_built"])
        use_type = "home" if b.home_kwh >= b.shop_kwh else b.kind
        rows.append({"building_id": p["refcat"], "lat": lat, "lon": lon, "use_type": use_type,
                     "dwellings": b.dwellings, "yearly_kwh": b.home_kwh if use_type == "home" else b.shop_kwh,
                     "geometry": p["geometry"]})
    dm.save_cache(cache, cache_path)
    return rows


def shortlist(host, candidates, host_latlon, max_distance=MAX_DISTANCE_M, n=SHORTLIST, join_rate=JOIN_RATE,
              exclude=()):
    """Score every candidate within reach; return (all rows, shortlisted rows, {id: hourly demand})."""
    times, surplus = host["times"], host["surplus_kwh"]
    shapes = dm.profile_shapes(times)
    reach = max_distance - DISTANCE_MARGIN_M
    scored, demand = [], {}
    for row in candidates:
        if row["building_id"] in exclude:
            continue
        d = distance_m(host_latlon, (float(row["lat"]), float(row["lon"])))
        use, source = demand_for(row, times, shapes, join_rate)
        status = "tentative: within distance" if d <= reach else "out of reach"
        scored.append({**row, "distance_m": round(d), "eligible_status": status,
                       "yearly_kwh": round(float(use.sum())), "fit_kwh": round(fit_kwh(surplus, use)),
                       "demand_source": source})
        demand[row["building_id"]] = use
    scored.sort(key=lambda r: -r["fit_kwh"])
    best = [r for r in scored if r["eligible_status"].startswith("tentative") and r["fit_kwh"] > 0][:n]
    return scored, best, {r["building_id"]: demand[r["building_id"]] for r in best}


def write_outputs(out_dir, times, scored, best, demand):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    feats = []
    for r in scored:
        geom = r.get("geometry")
        props = {k: r.get(k) for k in ("building_id", "use_type", "distance_m", "eligible_status", "dwellings",
                                       "yearly_kwh", "fit_kwh", "demand_source")}
        if geom is not None:
            from shapely.geometry import mapping
            g = mapping(geom)          # EPSG:25831 from Catastro
        else:
            g = {"type": "Point", "coordinates": [float(r["lon"]), float(r["lat"])]}
        feats.append({"type": "Feature", "geometry": g, "properties": props})
    (out_dir / "candidate_buildings.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}),
                                                         encoding="utf-8")
    stamps = [str(t) + ":00Z" for t in times]
    with open(out_dir / "demand_hourly.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["building_id", "timestamp_utc", "consumed_kwh", "source_type", "quality_flag"])
        for r in best:
            flag = "ok" if r["demand_source"] == "metered" else "assumed"
            for s, v in zip(stamps, demand[r["building_id"]]):
                w.writerow([r["building_id"], s, round(float(v), 4), r["demand_source"], flag])
    cols = ["building_id", "use_type", "distance_m", "dwellings", "yearly_kwh", "fit_kwh", "demand_source", "eligible_status"]
    with open(out_dir / "shortlist.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(best)


def read_demand(path):
    """demand_hourly.csv (steps 04 and 06) -> {building_id: hourly kWh array}."""
    out = {}
    with open(path, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["building_id"], []).append(float(r["consumed_kwh"]))
    return {k: np.array(v) for k, v in out.items()}


def main():
    ap = argparse.ArgumentParser(description="Step 06: nearby candidate buildings, shortlisted by fit")
    ap.add_argument("--host-dir", required=True, help="step 04's output folder for the host")
    ap.add_argument("--host", help="host address (for its position and to leave it out)")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--candidates-csv", help="your own candidate list instead of Catastro")
    ap.add_argument("--max-distance", type=float, default=MAX_DISTANCE_M)
    ap.add_argument("--shortlist", type=int, default=SHORTLIST)
    ap.add_argument("--join-rate", type=float, default=JOIN_RATE)
    ap.add_argument("--out", default="data/neighbours")
    args = ap.parse_args()
    host_id = None
    if args.host:
        from step01_select_host.find_building import find_building
        record, _ = find_building(args.host)
        args.lat, args.lon, host_id = record.lat, record.lon, record.refcat
    if args.lat is None or args.lon is None:
        ap.error("give --host, or --lat and --lon")
    host = read_host_table(args.host_dir)
    if args.candidates_csv:
        with open(args.candidates_csv, newline="", encoding="utf-8-sig") as f:
            candidates = list(csv.DictReader(f))
    else:
        Path(args.out).mkdir(parents=True, exist_ok=True)
        candidates = from_catastro(args.lat, args.lon, args.max_distance, Path(args.out) / "catastro_cache.json")
    scored, best, demand = shortlist(host, candidates, (args.lat, args.lon), args.max_distance, args.shortlist,
                                     args.join_rate, exclude={host_id} if host_id else ())
    write_outputs(args.out, host["times"], scored, best, demand)
    print(f"{len(scored)} candidates, {len(best)} shortlisted -> {args.out}")
    for r in best:
        print(f"  {r['building_id']}: {r['use_type']}, {r['distance_m']} m, could take {r['fit_kwh']:,} kWh of surplus a year")


if __name__ == "__main__":
    main()
