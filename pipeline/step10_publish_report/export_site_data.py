"""Step 10: collect the results of steps 03-09 into one file for the website.

    python -m step10_publish_report.export_site_data --name demo --yield examples\\bruc59_yield.json

It reads the output folders that the earlier steps wrote (data\\host\\<name>,
data\\prices, data\\battery\\<name>, data\\neighbours\\<name>, data\\sharing\\<name>,
data\\investment\\<name>) and docs\\SOURCES.md, and writes ..\\website\\data\\site_data.json.

The website only reads that file: it does no modelling of its own, except the
guest-price slider, which uses the same formula as step 09 (owner_total_at_discount).

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
from step07_discover_neighbours.candidates import read_demand

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
            "kwh_per_kwp", "mean_shade_loss", "monthly_kwh")
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
    ap = argparse.ArgumentParser(description="Step 10: one data file for the website")
    ap.add_argument("--name", default="demo", help="the folder name used in data\\<step>\\<name>")
    ap.add_argument("--yield", dest="yield_json", default="examples/bruc59_yield.json",
                    help="step 03's <name>_yield.json")
    ap.add_argument("--label", default="Demo: made-up 300 m² office under the Bruc 59 example roof",
                    help="what the website calls this case")
    ap.add_argument("--lat", type=float, default=41.3935, help="host latitude (as given to step 07)")
    ap.add_argument("--lon", type=float, default=2.1689, help="host longitude (as given to step 07)")
    ap.add_argument("--sources", default="../docs/SOURCES.md")
    ap.add_argument("--out", default="../website/data/site_data.json")
    args = ap.parse_args()
    n = args.name
    d = Path("data")
    y = json.loads(Path(args.yield_json).read_text(encoding="utf-8"))
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

    times, gen = host["times"], host["generation_kwh"]
    ids = ["host"] + list(others)
    demand = np.vstack([host["host_demand_kwh"]] + [others[i] for i in others])
    yl = y["yield"]
    typ = share["price_years"]["typical"]

    # buildings
    buildings = [{"id": "host", "label": "Host (office)", "kind": "office", "distance_m": 0,
                  "yearly_kwh": hs["host_demand_kwh"], "source": hs["demand_source"],
                  "profile": profiles(times, host["host_demand_kwh"])}]
    for f in cands["features"]:
        p = f["properties"]
        if p["building_id"] in others:
            buildings.append({"id": p["building_id"], "label": p["building_id"].replace("_", " "),
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

    # money slider bases per price year (owner_total_at_discount in step 09)
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
                             "made-up 300 m² office at 120 kWh/m² a year; replace with meter data"),
        "host_self_share": fact(hs["self_consumption_ratio"], "modelled", "step 04"),
        "surplus_kwh": fact(hs["surplus_kwh"], "modelled", "step 04", "kWh/yr"),
        "surplus_weekend_kwh": fact(hs["surplus_weekend_kwh"], "modelled", "step 04", "kWh/yr"),
        "shared_used_share": fact(typ["without_battery"]["used_share"], "modelled", "step 08"),
        "shared_wasted_kwh": fact(typ["without_battery"]["wasted_kwh"], "modelled", "step 08", "kWh/yr"),
        "owner_eur": fact(typ["without_battery"]["owner_total_eur"], "modelled",
                          "step 08", "€/yr", "typical-year PVPC [REE]"),
        "guests_saving_eur": fact(typ["without_battery"]["guests_saving_eur"], "modelled",
                                  "step 08", "€/yr", "guest price PVPC − 10%"),
        "battery_chosen_kwh": fact(share["battery_kwh"], "modelled", "step 08", "kWh", "size re-checked with the guests"),
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
                                   "step 08", "€/yr", "2025, perfect vs typical-year forecast"),
        "pv_capex": fact(capex.get("direct_no_battery"), "assumption", "step 09", "€", "€1,400 per kWp"),
    }

    data = {
        "meta": {"case": args.label, "address": y["building"]["query"], "refcat": y["building"]["refcat"],
                 "generated": str(date.today()), "demo": True,
                 "note": "The roof is real (Carrer del Bruc 59, read from LiDAR). The office using it and the neighbours are made up, to test the tool until we have a real host with meter data."},
        "facts": facts,
        "roof": {"monthly_kwh": yl["monthly_kwh"], "tilt_deg": yl["tilt_deg"], "azimuth_deg": yl["azimuth_deg"],
                 "mean_shade_loss": yl["mean_shade_loss"], "panels_left_out": yl["panels_left_out"],
                 "solar_day_by_month": monthly_solar_days(times, gen),
                 "panels": [{"x": p["x"], "y": p["y"], "kwh": p["kwh_year"]} for p in y["panels"]],
                 "variants": layout_variants(y),
                 "chosen": {"panel_wp": yl.get("panel_wp", 420), "option": yl.get("layout", "max")}},
        "host": {"surplus_by_month_kwh": hs["surplus_by_month_kwh"], "surplus_map": smap,
                 "first_day": str(times[0].astype("datetime64[D]"))},
        "buildings": buildings,
        "candidates": candidates,
        "max_distance_m": 100,
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
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"-> {out} ({out.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
