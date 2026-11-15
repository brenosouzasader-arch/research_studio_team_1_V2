"""Step 09: collect the results of steps 03-09 into one file for the website.

    python -m step09_publish_report.export_site_data --name cep9 --yield data\\pv\\cep9_yield.json --label "..." --lat .. --lon ..

It reads the output folders that the earlier steps wrote (data\\host\\<name>,
data\\prices, data\\battery\\<name>, data\\neighbours\\<name>, data\\sharing\\<name>,
data\\investment\\<name>) and docs\\SOURCES.md, and writes ..\\website\\data\\site_data.json.

The website only reads that file: it does no modelling of its own, except the
guest-price slider, which uses the same formula as step 08 (owner_total_at_discount).

Every headline number goes into "facts" with:
- kind: "measured" (from a meter or a real price), "modelled" (computed by the pipeline)
        or "assumption" (a value we chose, listed at the end of SOURCES.md)
- src:  the short name of its row in SOURCES.md, or the pipeline file that computed it
so the website can show where each number comes from.
"""
import argparse
import csv
import html
import json
import re
from datetime import date
from pathlib import Path

import numpy as np

from step04_read_host_demand.host_table import read_host_table
from step06_prices_and_battery import battery_types as bt
from step06_prices_and_battery import dispatch
from step06_prices_and_battery.prices import local_hour, read_solar_year_prices
from step07_share_energy.candidates import read_demand

SHOWCASE_KWH = 10.0        # battery size used only to illustrate a day when the agent picks none


def fact(v, kind, src, unit="", note=""):
    return {"v": v, "kind": kind, "src": src, "unit": unit, "note": note}


def profiles(times, series):
    """Mean weekday and weekend day (local hours 0-23) of an hourly array."""
    hour, wday = local_hour(times)
    out = {}
    for label, mask in (("weekday", wday < 5), ("weekend", wday >= 5)):
        out[label] = [round(float(series[mask & (hour == h)].mean()), 3) for h in range(24)]
    return out


def layout_variants(y):
    """The step 03 layout options (fill the roof / neat blocks / best blocks, for each panel
    wattage), for the website's layout switch. Older yield files have none: then the one
    layout they hold is shown as "Fill the roof" with 420 W panels."""
    keys = ("panel_wp", "panel", "option", "name", "rule", "blocks", "panels", "kwp", "yearly_kwh",
            "kwh_per_kwp", "mean_shade_loss", "monthly_kwh", "funnel", "left_out", "roofs")
    if y.get("variants"):
        return [{**{k: v.get(k) for k in keys},
                 "panel_list": [{"c": p["corners"], "k": p["kwh_year"]} for p in v["panel_list"]]}
                for v in y["variants"]]
    yl = y["yield"]
    return [{"panel_wp": 420, "panel": "420 W, 1.76 x 1.13 m (default)", "option": "max",
             "name": "Fill the roof", "rule": "every panel that fits and loses at most 40% of its sun to shade",
             "blocks": None, **{k: yl.get(k) for k in ("panels", "kwp", "yearly_kwh", "kwh_per_kwp",
                                                        "mean_shade_loss", "monthly_kwh")},
             "panel_list": [{"x": p["x"], "y": p["y"], "k": p["kwh_year"]} for p in y["panels"]]}]


def actual_variant(a, variants):
    """The real system as one more layout, from a JSON like examples/cep9_actual.json:
    reported totals plus panel blocks traced from the photo. Our model's kWh per kWp on the
    traced blocks (step 03 panels of the same wattage whose centre is inside a block) shows
    how close the model gets on the real spots. The real monthly split isn't published, so
    the months follow our model's shape, scaled to the reported yearly total."""
    from shapely.geometry import Point, Polygon
    blocks = [Polygon(b["corners"]) for b in a["blocks"]]
    same = next((v for v in variants if v["option"] == "max" and v["panel_wp"] == a["panel_wp"]), None)
    inside = []
    if same:
        for p in same["panel_list"]:
            c = np.mean(p["c"][:4], axis=0) if p.get("c") else (p["x"], p["y"])
            if any(b.contains(Point(*c)) for b in blocks):
                inside.append(p["k"])
    model_per_kwp = float(np.mean(inside)) / (a["panel_wp"] / 1000) if inside else None
    shape = np.array(same["monthly_kwh"], float) if same else None
    return {"option": "actual", "name": "Actual", "panel_wp": a["panel_wp"], "panel": f"{a['panel_wp']} W",
            "rule": f"the real system: {a['panels']} panels of {a['panel_wp']} W [{a['source']}]",
            "blocks": len(blocks), "panels": a["panels"], "kwp": a["kwp"], "yearly_kwh": a["yearly_kwh"],
            "kwh_per_kwp": round(a["yearly_kwh"] / a["kwp"]), "mean_shade_loss": None,
            "monthly_kwh": [round(x) for x in shape / shape.sum() * a["yearly_kwh"]] if shape is not None else None,
            "panel_list": [], "actual": True, "source": a["source"], "source_url": a.get("source_url"),
            "panel_wp_note": a.get("panel_wp_note"), "traced_by": a.get("traced_by"),
            "traced": [{"name": b["name"], "c": b["corners"], "area_m2": round(Polygon(b["corners"]).area, 1)}
                       for b in a["blocks"]],
            "model_panels_on_blocks": len(inside),
            "model_kwh_per_kwp": round(model_per_kwp) if model_per_kwp else None,
            "model_yearly_kwh": round(model_per_kwp * a["kwp"]) if model_per_kwp else None,
            "photo": a.get("photo"), "by_roof": a.get("by_roof"), "by_roof_source": a.get("by_roof_source")}


def monthly_solar_days(times, gen):
    hour, _ = local_hour(times)
    month = times.astype("datetime64[M]").astype(int) % 12
    return [[round(float(gen[(month == m) & (hour == h)].mean()), 3) for h in range(24)] for m in range(12)]


def pick_days(times, gen, demand):
    """Example days: a sunny summer weekday, a summer Sunday + Monday, a winter weekday (local dates).
    Hours are in local order (the list of indices is already in time order)."""
    hour, _ = local_hour(times)
    utc_hour = (times - times.astype("datetime64[D]")).astype("timedelta64[h]").astype(int)
    local = times + ((hour - utc_hour) % 24).astype("timedelta64[h]")
    days = local.astype("datetime64[D]")
    wday = (days.astype(int) + 3) % 7
    month = local.astype("datetime64[M]").astype(int) % 12 + 1
    daily = {}
    for k, d in enumerate(days):
        daily.setdefault(d, []).append(k)
    def best(cond):
        cands = [d for d, ks in daily.items() if cond(wday[ks[0]], month[ks[0]]) and len(ks) == 24]
        return max(cands, key=lambda d: gen[daily[d]].sum())
    chosen = {"summer_weekday": best(lambda w, m: w < 5 and m in (6, 7)),
              "summer_sunday": best(lambda w, m: w == 6 and m in (6, 7)),
              "winter_weekday": best(lambda w, m: w < 5 and m in (1, 12))}
    out = {k: (str(d), daily[d]) for k, d in chosen.items()}
    sun = chosen["summer_sunday"]          # show Sunday and Monday: the battery keeps Sunday's solar for Monday
    out["summer_sunday"] = (str(sun), daily[sun] + daily.get(sun + np.timedelta64(1, "D"), []))
    return out


# ---- SOURCES.md -> structured list ------------------------------------------------------
_link = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_bold = re.compile(r"\*\*(.+?)\*\*")
_code = re.compile(r"`([^`]+)`")


def md_inline(text):
    t = html.escape(text, quote=False)
    t = _link.sub(lambda m: f'<a href="{m.group(2)}" target="_blank" rel="noopener">{m.group(1)}</a>', t)
    t = _bold.sub(r"<strong>\1</strong>", t)
    return _code.sub(r"<code>\1</code>", t)


def read_sources(path):
    """docs/SOURCES.md -> [{"title", "intro": [html], "header": [..], "rows": [[html, ...]]}]."""
    sections, cur = [], None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            cur = {"title": line[3:].strip(), "intro": [], "header": [], "rows": []}
            sections.append(cur)
        elif cur is None or not line.strip():
            continue
        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if set("".join(cells)) <= set("-: "):
                continue
            if not cur["header"]:
                cur["header"] = cells
            else:
                cur["rows"].append([md_inline(c) for c in cells])
        elif line.startswith("- "):
            cur["intro"].append(md_inline(line[2:]))
        else:
            cur["intro"].append(md_inline(line))
    return sections


def main():
    ap = argparse.ArgumentParser(description="Step 09: one data file for the website")
    ap.add_argument("--name", required=True, help="the folder name used in data\\<step>\\<name>")
    ap.add_argument("--yield", dest="yield_json", required=True, help="step 03's <name>_yield.json")
    ap.add_argument("--label", required=True, help="what the website calls this case")
    ap.add_argument("--host-label", default="Host", help="the host's name on the site, e.g. 'Institut Quatre Cantons'")
    ap.add_argument("--host-kind", default="office", help="office, school or shop (as given to step 04)")
    ap.add_argument("--host-use-note", default="step 05 profile from floor area and use type; replace with meter data",
                    help="where the host's yearly use comes from (shown with the number)")
    ap.add_argument("--note", default="", help="a sentence for the banner at the top (e.g. what is assumed)")
    ap.add_argument("--max-distance", type=float, default=100, help="the reach used in step 07, metres")
    ap.add_argument("--compare-note", default="", help="a sentence comparing the fixed-shares result with reality")
    ap.add_argument("--reach-note", default="", help="a sentence explaining the reach, shown in the neighbours section")
    ap.add_argument("--lat", type=float, required=True, help="host latitude (as given to step 07)")
    ap.add_argument("--lon", type=float, required=True, help="host longitude (as given to step 07)")
    ap.add_argument("--roof-yield", help="a different step 03 yield file for the roof section only "
                    "(e.g. a real roof whose later steps haven't run yet); default: --yield")
    ap.add_argument("--warning", action="append", default=[],
                    help="a warning for the top of the page, as 'what is wrong | what we need to look at or change'; repeat it")
    ap.add_argument("--property", action="append", default=[],
                    help="a step 01 building.json to list on the page's search (e.g. examples\\a160_building.json); repeat it. "
                         "The case's own property is added by itself")
    ap.add_argument("--match-dir", help="folder with match_summary.json files (default data\\match), named <name>_wired and <name>_legal")
    ap.add_argument("--compare-image", help="a picture of another tool's panel plan (e.g. Google Solar), in website\\data\\")
    ap.add_argument("--compare-caption", default="", help="what the comparison picture shows and where it is from")
    ap.add_argument("--actual", help="a JSON describing the real system on this roof (e.g. examples\\cep9_actual.json); "
                    "adds an 'Actual' tab to the roof section")
    ap.add_argument("--sources", default="../docs/SOURCES.md")
    ap.add_argument("--out", default="../website/data/site_data.json")
    args = ap.parse_args()
    n = args.name
    d = Path("data")
    y = json.loads(Path(args.yield_json).read_text(encoding="utf-8"))
    ry = json.loads(Path(args.roof_yield).read_text(encoding="utf-8")) if args.roof_yield else y
    host = read_host_table(d / "host" / n)
    hs = json.loads((d / "host" / n / "host_summary.json").read_text(encoding="utf-8"))
    sy = read_solar_year_prices(d / "prices" / "prices_hourly_solar_year.csv")
    psum = json.loads((d / "prices" / "prices_summary.json").read_text(encoding="utf-8"))
    pmodel = json.loads((d / "prices" / "price_model_report.json").read_text(encoding="utf-8"))
    bsize = json.loads((d / "battery" / n / "battery_sizing.json").read_text(encoding="utf-8"))
    share = json.loads((d / "sharing" / n / "battery_agent_summary.json").read_text(encoding="utf-8"))
    inv = json.loads((d / "investment" / n / "investment_battery.json").read_text(encoding="utf-8"))
    others = read_demand(d / "neighbours" / n / "demand_hourly.csv")
    cands = json.loads((d / "neighbours" / n / "candidate_buildings.geojson").read_text(encoding="utf-8"))

    agreed_path = d / "agreed" / n / "agreed_shares_summary.json"
    agreed = json.loads(agreed_path.read_text(encoding="utf-8")) if agreed_path.exists() else None
    times, gen = host["times"], host["generation_kwh"]
    ids = ["host"] + list(others)
    demand = np.vstack([host["host_demand_kwh"]] + [others[i] for i in others])
    yl = y["yield"]
    variants = layout_variants(ry)
    if args.actual:
        variants.append(actual_variant(json.loads(Path(args.actual).read_text(encoding="utf-8")), variants))
    typ = share["price_years"]["typical"]

    # buildings
    buildings = [{"id": "host", "label": f"{args.host_label} (host)", "kind": args.host_kind, "distance_m": 0,
                  "yearly_kwh": hs["host_demand_kwh"], "source": hs["demand_source"],
                  "profile": profiles(times, host["host_demand_kwh"])}]
    for f in cands["features"]:
        p = f["properties"]
        if p["building_id"] in others:
            buildings.append({"id": p["building_id"], "label": p.get("name") or p["building_id"].replace("_", " "),
                              "kind": p["use_type"], "distance_m": p["distance_m"], "yearly_kwh": p["yearly_kwh"],
                              "fit_kwh": p["fit_kwh"], "source": p["demand_source"],
                              "profile": profiles(times, others[p["building_id"]])})
    candidates = [{**f["properties"], "lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1],
                   "joined": f["properties"]["building_id"] in others}
                  for f in cands["features"] if f["geometry"]["type"] == "Point"]

    # example days, with the chosen battery or (if none) an illustrative one
    shown_kwh = share["battery_kwh"] if share["battery_kwh"] > 0 else SHOWCASE_KWH
    battery = {**bt.get(share["battery_type"]), "kwh": float(shown_kwh)}
    flows = dispatch.simulate_year(gen, demand, sy["pvpc"]["typical"], sy["spot"]["typical"], battery,
                                   share["guest_discount"])
    hour, _ = local_hour(times)
    days = {}
    for key, (day, ks) in pick_days(times, gen, demand).items():
        r = lambda a: [round(float(a[k]), 3) for k in ks]
        days[key] = {"date": day, "solar": r(gen), "price": r(sy["pvpc"]["typical"]),
                     "to_host": r(flows["pv_to"][0]), "to_guests": r(flows["pv_to"][1:].sum(0)),
                     "battery_out": r(flows["bat_to"].sum(0)), "charge": r(flows["charge"]),
                     "export": r(flows["export"] + flows["curtail"]), "level": r(flows["soc"]),
                     "use_host": r(demand[0]), "use_guests": r(demand[1:].sum(0))}

    # surplus map: 365 days x 24 local hours
    surplus = host["surplus_kwh"]
    smap = [[0.0] * 24 for _ in range(365)]
    day_idx = (times.astype("datetime64[D]") - times[0].astype("datetime64[D]")).astype(int)
    for k in range(len(times)):
        if day_idx[k] < 365:
            smap[day_idx[k]][hour[k]] = round(float(surplus[k]), 2)

    # money slider bases per price year (owner_total_at_discount in step 08)
    slider = {}
    for yname, r in share["price_years"].items():
        for label in ("with_battery", "without_battery"):
            res = r[label]
            guests_value = sum(v["roof_kwh_at_grid_price_eur"] for k, v in res["per_building"].items() if k != "host")
            slider.setdefault(yname, {})[label] = {"host_saving": res["owner_host_saving_eur"],
                                                   "guests_value": round(guests_value, 2),
                                                   "export": res["owner_export_income_eur"]}
    central = [r for r in inv if r["case"] == "central"]
    capex = {r["scenario"]: r["capex_eur"] for r in central if r["price_year"] == "typical"}
    om = {r["scenario"]: r["om_eur"] for r in central if r["price_year"] == "typical"}

    types = [{"id": k, "label": v["label"], "capex_eur_per_kwh": round(v["capex_eur_per_kwh"]),
              "round_trip": v["round_trip"], "cycle_life": v["cycle_life"], "calendar_years": v["calendar_years"],
              "usable_share": v["usable_share"], "notes": v["notes"]} for k, v in bt.TYPES.items()]

    best_host = {t: b for t, b in bsize["recommended"].items()}
    lfp5 = next((r for r in bsize["rows"] if r["battery_type"] == "lfp" and r["battery_kwh"] == 5), None)
    m2 = pmodel["horizons"]["2_days"]
    facts = {
        "panels": fact(yl["panels"], "modelled", "step 03", note="ICGC LiDAR + PVGIS typical year"),
        "kwp": fact(yl["kwp"], "modelled", "step 03", "kWp", "ICGC LiDAR + PVGIS typical year"),
        "solar_kwh": fact(yl["yearly_kwh"], "modelled", "step 03", "kWh/yr", "PVGIS typical year"),
        "kwh_per_kwp": fact(yl["kwh_per_kwp"], "modelled", "step 03", "kWh/kWp"),
        "usable_m2": fact(y.get("usable_area_m2"), "modelled", "step 02", "m²", "ICGC LiDAR"),
        "host_use_kwh": fact(hs["host_demand_kwh"], "assumption", "step 05", "kWh/yr",
                             args.host_use_note),
        "host_self_share": fact(hs["self_consumption_ratio"], "modelled", "step 04"),
        "surplus_kwh": fact(hs["surplus_kwh"], "modelled", "step 04", "kWh/yr"),
        "surplus_weekend_kwh": fact(hs["surplus_weekend_kwh"], "modelled", "step 04", "kWh/yr"),
        "shared_used_share": fact(typ["without_battery"]["used_share"], "modelled", "step 07"),
        "shared_wasted_kwh": fact(typ["without_battery"]["wasted_kwh"], "modelled", "step 07", "kWh/yr"),
        "owner_eur": fact(typ["without_battery"]["owner_total_eur"], "modelled",
                          "step 07", "€/yr", "typical-year PVPC [REE]"),
        "guests_saving_eur": fact(typ["without_battery"]["guests_saving_eur"], "modelled",
                                  "step 07", "€/yr", "guest price PVPC − 10%"),
        "battery_chosen_kwh": fact(share["battery_kwh"], "modelled", "step 07", "kWh", "size re-checked with the guests"),
        "lfp_price": fact(round(bt.LFP_CAPEX_EUR_PER_KWH), "assumption", "battery_types.py", "€/kWh",
                          "no checkable European building-battery price found"),
        "lfp5_break_even": fact(lfp5["break_even_eur_per_kwh"] if lfp5 else None, "modelled", "step 06", "€/kWh"),
        "pvpc_mean": fact(psum["typical"]["pvpc_mean_eur_kwh"], "measured", "REE", "€/kWh",
                          "mean of 2023, 2024 and 2025"),
        "evening_days": fact(psum["2025"]["days_evening_dearer_than_midday"], "measured", "REE", "days",
                             "2025: evening (19-22 h) dearer than midday (12-15 h)"),
        "model_mae": fact(m2["model"]["mae"], "modelled", "step 06", "€/kWh"),
        "baseline_mae": fact(min(m2["same_hour_last_week"]["mae"], m2["typical_year"]["mae"]), "modelled",
                             "step 06", "€/kWh"),
        "forecast_worth_eur": fact(share["forecast_test_2025"]["most_a_better_forecast_could_add_eur"], "modelled",
                                   "step 07", "€/yr", "2025, perfect vs typical-year forecast"),
        "pv_capex": fact(capex.get("direct_no_battery"), "assumption", "step 08", "€", "€1,061 per kWp (Marblanc Solar average of 10 quotes, homes under 20 kW)"),
    }

    warnings = []
    for w in ([args.note] if args.note else []) + args.warning:
        text, _, nxt = w.partition("|")
        warnings.append({"text": text.strip(), "next": nxt.strip()})
    props = []
    for pth in args.property:
        props.append(json.loads(Path(pth).read_text(encoding="utf-8")))
    main_rec = dict(y["building"])
    main_rec.setdefault("refcat", y["building"]["refcat"])
    here = next((r for r in props if r.get("refcat") == main_rec["refcat"]), None)
    gaps_path = Path(__file__).resolve().parent.parent / "step01_select_host" / "known_gaps.json"
    match = {}
    for mode in ("wired", "legal"):
        mp = Path(args.match_dir or d / "match") / f"{n}_{mode}" / "match_summary.json"
        if mp.exists():
            match[mode] = json.loads(mp.read_text(encoding="utf-8"))
    step01 = {"properties": [{**{k: v for k, v in r.items() if k != "_about"}, "analysed": r.get("refcat") == main_rec["refcat"],
                              "about": r.get("_about", "")} for r in props],
              "gaps": json.loads(gaps_path.read_text(encoding="utf-8")) if gaps_path.exists() else [],
              "run_command": 'python -m step01_select_host.find_building "<address>, Barcelona" --laz-dir data\\lidar'}
    data = {
        "step01": step01, "match": match, "warnings": warnings,
        "compare": {"file": args.compare_image, "caption": args.compare_caption} if args.compare_image else None,
        "meta": {"case": args.label, "address": y["building"]["query"], "refcat": y["building"]["refcat"],
                 "generated": str(date.today()), "demo": bool(args.note), "note": args.note,
                 "host_label": args.host_label, "host_kind": args.host_kind,
                 "reach_note": args.reach_note},
        "facts": facts,
        "roof": {"address": ry["building"]["query"], "refcat": ry["building"]["refcat"],
                 "usable_m2": ry.get("usable_area_m2"), "separate": bool(args.roof_yield),
                 "monthly_kwh": yl["monthly_kwh"], "tilt_deg": yl["tilt_deg"], "azimuth_deg": yl["azimuth_deg"],
                 "mean_shade_loss": yl["mean_shade_loss"], "panels_left_out": yl["panels_left_out"],
                 "solar_day_by_month": monthly_solar_days(times, gen),
                 "panels": [{"x": p["x"], "y": p["y"], "kwh": p["kwh_year"]} for p in y["panels"]],
                 "variants": variants,
                 "chosen": {"panel_wp": ry["yield"].get("panel_wp", 420), "option": ry["yield"].get("layout", "max")}},
        "host": {"surplus_by_month_kwh": hs["surplus_by_month_kwh"], "surplus_map": smap,
                 "first_day": str(times[0].astype("datetime64[D]"))},
        "buildings": buildings,
        "candidates": candidates,
        "max_distance_m": args.max_distance,
        "host_latlon": [args.lat, args.lon],
        "prices": {"by_local_hour": {k: v["pvpc_by_local_hour"] for k, v in psum.items()},
                   "summary": {k: {kk: vv for kk, vv in v.items() if kk != "pvpc_by_local_hour"} for k, v in psum.items()},
                   "model": pmodel},
        "battery": {"types": types, "sizing_host": bsize["rows"], "screen": bsize["screen"],
                    "recommended_host": best_host, "chosen_with_guests": share["battery_kwh"],
                    "sizing_with_guests": share["sizing_with_guests"], "shown_kwh": shown_kwh,
                    "shown_is_illustration": share["battery_kwh"] == 0},
        "days": days,
        "sharing": {k: {"with": v["with_battery"], "without": v["without_battery"], "gain": v["battery_gain_eur"]}
                    for k, v in share["price_years"].items()},
        "forecast_test": share["forecast_test_2025"],
        "money": {"slider": slider, "capex": capex, "om": om, "default_discount": share["guest_discount"],
                  "rows": inv},
        "sources": read_sources(args.sources),
        "agreed": agreed,
        "compare_note": args.compare_note,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"-> {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
