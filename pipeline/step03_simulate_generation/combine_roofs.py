"""Add several roofs of ONE host together (for example CEP9's red and yellow buildings).

Step 03 reads one building at a time. A host that owns panels on two or more buildings is
run once per roof, and this tool adds the results into one yield file with the same layout
as step 03's own, so steps 04 to 09 and the website treat it as a single roof.

    python -m step03_simulate_generation.combine_roofs --roof Escola=data\\pv\\cep9_red_yield.json ^
        --roof Institut=data\\pv\\cep9_yellow_yield.json --out data\\pv\\cep9

What is added: panels, kWp, yearly and monthly kWh, and the hourly solar of every layout variant
(a variant is matched across roofs by panel wattage and layout option, for example 420 W neat).
Hourly files are read from the folder of each roof's yield json. Every panel keeps a 'roof' label.
Tilt and azimuth differ between roofs, so they are listed per roof under 'roofs' and the headline
values are those of the first roof. The roofs must be run with the same weather file.
"""
import argparse
import json
from pathlib import Path

import numpy as np


def _hourly(path):
    rows = Path(path).read_text().strip().splitlines()[1:]
    t = [r.split(",")[0] for r in rows]
    return t, np.array([float(r.split(",")[1]) for r in rows])


def _write(path, times, kwh):
    Path(path).write_text("time_utc,kwh\n" + "".join(f"{t},{round(float(v), 4)}\n" for t, v in zip(times, kwh)))


def _find(yield_json, hourly_file):
    """Step 03 stores the hourly file as it was given on the command line (e.g. data\\pv\\x.csv), so
    try that path first, then the file name next to the yield json."""
    for c in (Path(hourly_file), Path(yield_json).parent / Path(str(hourly_file).replace("\\", "/")).name):
        if c.exists():
            return c
    raise SystemExit(f"Hourly file {hourly_file} not found next to {yield_json}")


def _sum_hourly(files, out):
    times, total = None, None
    for f in files:
        t, v = _hourly(f)
        if times is None:
            times, total = t, v.copy()
        elif t != times or len(v) != len(total):
            raise SystemExit(f"{f}: its hours differ from the first roof's. Run both roofs with the same weather file.")
        else:
            total += v
    _write(out, times, total)
    return total


def combine(roofs, out):
    """roofs = [(name, path to <name>_yield.json)]. Returns the combined result dict."""
    loaded = [(n, Path(p), json.loads(Path(p).read_text())) for n, p in roofs]
    out = Path(out)
    first = loaded[0][2]
    variants = []
    for v0 in first["variants"]:
        key = (v0["panel_wp"], v0["option"])
        parts = []
        for n, p, y in loaded:
            m = [v for v in y["variants"] if (v["panel_wp"], v["option"]) == key]
            if m:
                parts.append((n, p, m[0]))
        if len(parts) != len(loaded):
            continue   # a layout that one of the roofs does not have cannot be added
        hourly = _sum_hourly([_find(p, v["hourly_file"]) for n, p, v in parts],
                             out.parent / f"{out.name}_hourly_{key[0]}_{key[1]}.csv")
        panels = sum(v["panels"] for *_, v in parts)
        kwp = round(sum(v["kwp"] for *_, v in parts), 2)
        yearly = sum(v["yearly_kwh"] for *_, v in parts)
        merged = {k: v0[k] for k in ("panel_wp", "panel", "option", "name", "rule")}
        merged.update({
            "blocks": sum((v.get("blocks") or 0) for *_, v in parts), "panels": panels, "kwp": kwp,
            "tilt_deg": v0["tilt_deg"], "azimuth_deg": v0["azimuth_deg"], "yearly_kwh": yearly,
            "kwh_per_kwp": round(yearly / kwp) if kwp else 0,
            "mean_shade_loss": round(sum((v["mean_shade_loss"] or 0) * v["panels"] for *_, v in parts) / max(panels, 1), 3),
            "monthly_kwh": [sum(v["monthly_kwh"][i] for *_, v in parts) for i in range(12)],
            "peak_hour_kw": round(float(hourly.max()), 2),
            "hourly_file": f"{out.name}_hourly_{key[0]}_{key[1]}.csv",
            "roofs": [{"roof": n, "panels": v["panels"], "kwp": v["kwp"], "yearly_kwh": v["yearly_kwh"],
                       "tilt_deg": v["tilt_deg"], "azimuth_deg": v["azimuth_deg"]} for n, _, v in parts],
            "panel_list": [{**q, "roof": n} for n, _, v in parts for q in v["panel_list"]]})
        funnels = [v.get("funnel") for *_, v in parts]
        if all(isinstance(f, dict) for f in funnels):   # how many panels each rule removed, added over the roofs
            merged["funnel"] = {k: sum(f.get(k, 0) or 0 for f in funnels) for k in funnels[0]}
        lefts = [v.get("left_out") for *_, v in parts]
        if all(isinstance(x, list) for x in lefts):
            merged["left_out"] = [q for x in lefts for q in x]
        variants.append(merged)
    main = next((v for v in variants if v["panel_wp"] == first["yield"]["panel_wp"]
                 and v["option"] == first["yield"]["layout"]), variants[0])
    result = {
        "building": {"refcat": "+".join(y["building"]["refcat"] for _, _, y in loaded),
                     "address": " + ".join(f"{n}: {y['building']['address']}" for n, _, y in loaded),
                     "query": " + ".join(n for n, _, _ in loaded)},
        "yield": {**{k: main[k] for k in ("panels", "kwp", "tilt_deg", "azimuth_deg", "yearly_kwh", "kwh_per_kwp",
                                           "mean_shade_loss", "monthly_kwh", "peak_hour_kw", "panel_wp")},
                  "layout": main["option"], "panels_left_out": sum(y["yield"]["panels_left_out"] for _, _, y in loaded),
                  "max_shade_loss": first["yield"]["max_shade_loss"]},
        "usable_area_m2": round(sum(y["usable_area_m2"] for _, _, y in loaded), 1),
        "usable_file": [y["usable_file"] for _, _, y in loaded],
        "roof": {"roofs": {n: y["roof"] for n, _, y in loaded}},
        "lidar": {"roofs": {n: y["lidar"] for n, _, y in loaded}},
        "panels": [{**q, "roof": n} for n, _, y in loaded for q in y["panels"]],
        "variants": variants,
        "roofs": [n for n, _, _ in loaded],
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    Path(f"{out}_yield.json").write_text(json.dumps(result, indent=2, default=str))
    _sum_hourly([_find(p, next(v for v in y["variants"] if (v["panel_wp"], v["option"]) ==
                               (main["panel_wp"], main["option"]))["hourly_file"]) for n, p, y in loaded],
                f"{out}_hourly.csv")
    return result


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--roof", action="append", required=True, metavar="NAME=YIELD_JSON")
    ap.add_argument("--out", required=True, help="output name without extension, e.g. data/pv/cep9")
    a = ap.parse_args()
    r = combine([tuple(x.split("=", 1)) for x in a.roof], a.out)
    print(f"{r['yield']['panels']} panels, {r['yield']['kwp']} kWp, {r['yield']['yearly_kwh']:,} kWh a year on {len(r['roofs'])} roofs")
