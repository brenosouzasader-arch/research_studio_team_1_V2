"""Test cases for step 01: host, participants, addresses, cadastral references,
the data we have and what is still unknown. One JSON file per case in cases/.

    python -m step01_select_host.cases            # list the cases
    python -m step01_select_host.cases cep9       # print one case
    python -m step01_select_host.cases --map      # rebuild cases/<case>_map.geojson (needs internet)
    python -m step01_select_host.cases --site     # copy the cases into ../website/data/site_data.json

Footprints for the map: the Catastro building first; when Catastro has no
building on the plot, the LiDAR trace saved by find_building in data/host/<id>.json.
"""
import json
import sys
from pathlib import Path

CASES_DIR = Path(__file__).resolve().parent / "cases"
PIPELINE_DIR = Path(__file__).resolve().parent.parent


def case_names():
    return sorted(p.stem for p in CASES_DIR.glob("*.json"))


def load_case(name):
    path = CASES_DIR / f"{name}.json"
    if not path.exists():
        raise SystemExit(f"No case called {name!r}. Cases: {', '.join(case_names())}")
    return json.loads(path.read_text(encoding="utf-8"))


def missing_files(case):
    """Local files the case lists that are not on disk (paths are relative to pipeline/)."""
    files = [r["step01_output"] for r in case["host"]["roofs"]]
    files += [d["file"] for d in case["available_data"] if d.get("file")]
    return [f for f in files if not (PIPELINE_DIR / f).exists()]


def summary(case):
    lines = [f"{case['name']}  [{case['role']}]", "", "Host roofs:"]
    for r in case["host"]["roofs"]:
        lines.append(f"  {r['roof']:<7} {r['refcat']}  {r['catastro_address']}  ({r['footprint_m2']} m², {r['current_use']})")
    lines += ["", "Participants:"]
    for p in case["participants"]:
        dist = f"{p['distance_m']} m" if p.get("distance_m") is not None else "? m"
        lines.append(f"  {p['name']:<52} {str(p.get('refcat') or 'UNKNOWN'):<16} {dist:>6}  {p.get('address') or 'address UNKNOWN'}")
    lines += ["", "Data:"]
    for d in case["available_data"]:
        lines.append(f"  [{d['status']}] {d['item']}")
    lines += ["", "Unknowns:"]
    for u in case["unknowns"]:
        lines.append(f"  - {u['item']}: {u['next']}")
    gone = missing_files(case)
    if gone:
        lines += ["", "Not on this computer (data/ is local, not in git): " + ", ".join(gone)]
    return "\n".join(lines)


def map_path(name):
    return CASES_DIR / f"{name}_map.geojson"


def _places(case):
    """(id, name, role, refcat, lat, lon) for every host roof and located participant."""
    out = [(f"roof_{r['roof']}", r.get("school") or case["host"]["name"], "host", r["refcat"], r["lat"], r["lon"])
           for r in case["host"]["roofs"]]
    host_refs = {r["refcat"] for r in case["host"]["roofs"]}
    for p in case["participants"]:
        if p.get("refcat") in host_refs or p.get("lat") is None:
            continue
        out.append((p["id"], p["name"], p["role"], p.get("refcat"), p["lat"], p["lon"]))
    return out


def build_map(name):
    """Write cases/<name>_map.geojson: one footprint (WGS84) per host roof and participant."""
    import numpy as np
    import shapely
    from pyproj import Transformer
    from shapely import wkt
    from shapely.geometry import Point, mapping

    from . import catastro
    from .find_building import pick_building

    to_utm = Transformer.from_crs("EPSG:4326", "EPSG:25831", always_xy=True).transform
    to_wgs = Transformer.from_crs("EPSG:25831", "EPSG:4326", always_xy=True).transform
    case = load_case(name)
    feats = []
    for pid, label, role, refcat, lat, lon in _places(case):
        pt = Point(to_utm(lon, lat))
        source, fp = "catastro", None
        try:
            fp = pick_building(catastro.buildings_for_refcat(refcat)[0], pt)["footprint"]
        except catastro.CatastroError:
            local = PIPELINE_DIR / "data" / "host" / f"{pid}.json"
            if local.exists():
                fp, source = wkt.loads(json.loads(local.read_text(encoding="utf-8"))["footprint_wkt"]), "lidar"
        if fp is None:
            source, fp = "point only", pt
        geom = shapely.transform(fp.simplify(0.3), lambda c: np.column_stack(to_wgs(c[:, 0], c[:, 1])).round(6))
        feats.append({"type": "Feature", "geometry": mapping(geom),
                      "properties": {"id": pid, "name": label, "role": role, "refcat": refcat,
                                     "footprint_source": source, "lat": lat, "lon": lon}})
        print(f"{name}: {label}: {source}")
    fc = {"type": "FeatureCollection", "features": feats}
    map_path(name).write_text(json.dumps(fc, ensure_ascii=False, indent=1), encoding="utf-8")


def site_cases():
    """What the website's step 01 map needs, for every case that has a map file."""
    out = []
    for name in case_names():
        if not map_path(name).exists():
            continue
        case = load_case(name)
        roof = case["host"]["roofs"][0]
        out.append({
            "case": name, "name": case["name"], "role": case["role"],
            "host": {"lat": roof["lat"], "lon": roof["lon"]},
            "map": json.loads(map_path(name).read_text(encoding="utf-8")),
            "unlocated": [p["name"] for p in case["participants"] if p.get("lat") is None and p.get("refcat") is None],
            "participants": [{k: p.get(k) for k in ("id", "name", "role", "address", "refcat", "distance_m", "footprint_m2")}
                             for p in case["participants"]],
        })
    return out


def update_site(path=PIPELINE_DIR.parent / "website" / "data" / "site_data.json"):
    """Put the cases (and the current known gaps) into an existing site_data.json, leaving the rest alone."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    data.setdefault("step01", {})["cases"] = site_cases()
    gaps = Path(__file__).resolve().parent / "known_gaps.json"
    data["step01"]["gaps"] = json.loads(gaps.read_text(encoding="utf-8"))
    Path(path).write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"updated step01 in {path}")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    if "--map" in args:
        for n in [a for a in args if not a.startswith("--")] or case_names():
            build_map(n)
        return
    if "--site" in args:
        update_site()
        return
    names = args or case_names()
    print("\n\n".join(summary(load_case(n)) for n in names))


if __name__ == "__main__":
    main()
