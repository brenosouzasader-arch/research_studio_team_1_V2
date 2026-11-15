"""Step 07b: share solar AND the host's battery with the guests, hour by hour, for a whole year.

    python -m step07_share_energy.battery_agent --host-dir data\\host\\demo ^
        --neighbours-dir data\\neighbours\\demo --prices-dir data\\prices --out data\\sharing\\demo

This is the "agent" that runs the battery. Default set-up (team decision, 15 Nov 2026):
guests are wired directly to the host's panels and battery, the battery belongs to the owner
and charges only from the panels. How it decides is explained in
step06_prices_and_battery/dispatch.py: once a day it plans 48 hours ahead with a linear
program, carries out 24 hours, and plans again. Goals in order: 1) waste no solar,
2) most money for the owner, 3) no guest pays more than the grid.

What this script does:
1. RE-CHECKS THE BATTERY SIZE with the guests (step 06 sized it for the host alone): runs the
   year for every size in --sizes and picks the one with the highest net value per year for
   the owner (gain minus the battery's yearly cost). --battery-kwh fixes the size instead.
2. RUNS THE CHOSEN SIZE with the prices of each real year (2023, 2024, 2025) and the typical
   year, so the result is a range, not one number.
3. TESTS THE PRICE FORECAST BY MONEY: runs 2025 twice, once planning with perfect knowledge
   of the next day's prices and once with the typical-year price as the forecast for day 2.
   The difference is the most a better forecast could ever be worth.

Guest price: (1 - --guest-discount) x the grid price of that hour, default 10% below PVPC
(team choice). Every guest's bill is checked to be at or below its grid-only bill.

Outputs in --out:
- battery_agent_summary.json   sizing table with guests, chosen size, results per price year,
                               forecast test, and per-building kWh and EUR
- decisions_hourly.csv         every hour of the typical year at the chosen size: solar,
                               price, battery charge and level, export, and for each building
                               solar received, battery received, bought from the grid.
                               This is the training data for a future learned controller.

Limitation: the plan uses PREDICTED use and is carried out as planned (actual = predicted).
With real meters, a real controller would correct each hour; that is not modelled yet.
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from step04_read_host_demand.host_table import read_host_table
from step06_prices_and_battery import battery_types as bt
from step06_prices_and_battery import dispatch
from step06_prices_and_battery.battery_size import size_battery
from step06_prices_and_battery.prices import read_solar_year_prices
from step07_share_energy.candidates import read_demand

SIZES_KWH = (0, 10, 20, 50, 100, 200)
GUEST_DISCOUNT = 0.10      # team choice (15 Nov 2026): guests pay PVPC - 10%; a slider on the report page
PRICE_YEARS = ("typical", 2023, 2024, 2025)


def run_year(gen, demand, ids, sy, year, battery, discount, plan_price=None, export_limit=None):
    pvpc, spot = sy["pvpc"][year], sy["spot"][year]
    flows = dispatch.simulate_year(gen, demand, pvpc, spot, battery, discount, plan_price, export_limit)
    return flows, dispatch.account(flows, gen, demand, pvpc, spot, discount, ids, battery)


def write_decisions(path, times, gen, pvpc, ids, demand, flows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        head = ["timestamp_utc", "generation_kwh", "pvpc_eur_kwh", "battery_charge_kwh", "battery_level_kwh",
                "export_kwh", "curtailed_kwh"]
        for i in ids:
            head += [f"{i}_use_kwh", f"{i}_from_solar_kwh", f"{i}_from_battery_kwh", f"{i}_from_grid_kwh"]
        w.writerow(head)
        for h, t in enumerate(times):
            row = [str(t) + ":00Z", round(float(gen[h]), 4), round(float(pvpc[h]), 5),
                   round(float(flows["charge"][h]), 4), round(float(flows["soc"][h]), 4),
                   round(float(flows["export"][h]), 4), round(float(flows["curtail"][h]), 4)]
            for k in range(len(ids)):
                got = flows["pv_to"][k, h] + flows["bat_to"][k, h]
                row += [round(float(demand[k, h]), 4), round(float(flows["pv_to"][k, h]), 4),
                        round(float(flows["bat_to"][k, h]), 4), round(float(demand[k, h] - got), 4)]
            w.writerow(row)


def main():
    ap = argparse.ArgumentParser(description="Step 07b: solar + battery shared with guests, hour by hour")
    ap.add_argument("--host-dir", required=True, help="step 04's output folder")
    ap.add_argument("--neighbours-dir", required=True, help="step 07's output folder")
    ap.add_argument("--prices-dir", default="data/prices", help="step 06a's output folder")
    ap.add_argument("--type", default=bt.DEFAULT, choices=list(bt.TYPES), help="battery type")
    ap.add_argument("--battery-kwh", type=float, help="fix the battery size instead of re-checking it")
    ap.add_argument("--sizes", type=float, nargs="+", default=list(SIZES_KWH))
    ap.add_argument("--guest-discount", type=float, default=GUEST_DISCOUNT)
    ap.add_argument("--no-export", action="store_true", help="the host may not export: surplus is curtailed")
    ap.add_argument("--out", default="data/sharing")
    args = ap.parse_args()
    if not 0 <= args.guest_discount <= 1:
        ap.error("--guest-discount must be between 0 and 1 (0.10 = guests pay 10% less than the grid)")
    host = read_host_table(args.host_dir)
    others = read_demand(Path(args.neighbours_dir) / "demand_hourly.csv")
    ids = ["host"] + list(others)
    demand = np.vstack([host["host_demand_kwh"]] + [others[i] for i in others])
    gen = host["generation_kwh"]
    sy = read_solar_year_prices(Path(args.prices_dir) / "prices_hourly_solar_year.csv")
    limit = 0.0 if args.no_export else None

    sizing_rows = []
    if args.battery_kwh is None:
        print(f"Re-checking the battery size with {len(ids) - 1} guests ...")
        sizing_rows, best = size_battery(gen, demand, sy["pvpc"]["typical"], sy["spot"]["typical"], ids,
                                         [args.type], args.sizes, args.guest_discount, export_limit=limit)
        kwh = best[args.type]["battery_kwh"] if best[args.type] else 0.0
    else:
        kwh = args.battery_kwh
    battery = {**bt.get(args.type), "kwh": float(kwh)}
    none = {**battery, "kwh": 0.0}

    years = {}
    for y in PRICE_YEARS:
        _, with_b = run_year(gen, demand, ids, sy, y, battery, args.guest_discount, export_limit=limit)
        _, without = run_year(gen, demand, ids, sy, y, none, args.guest_discount, export_limit=limit)
        years[str(y)] = {"with_battery": with_b, "without_battery": without,
                         "battery_gain_eur": with_b["owner_total_eur"] - without["owner_total_eur"]}

    # forecast test on 2025: perfect knowledge vs typical-year forecast for day 2.
    # With no battery the forecast cannot matter, so test the smallest size above 0 instead.
    test_kwh = kwh if kwh > 0 else min([x for x in args.sizes if x > 0] or [10.0])
    test_b = {**battery, "kwh": float(test_kwh)}
    _, perfect = run_year(gen, demand, ids, sy, 2025, test_b, args.guest_discount, export_limit=limit)
    _, typical_plan = run_year(gen, demand, ids, sy, 2025, test_b, args.guest_discount,
                               plan_price=sy["pvpc"]["typical"], export_limit=limit)
    forecast = {"tested_battery_kwh": test_kwh, "owner_eur_perfect_forecast": perfect["owner_total_eur"],
                "owner_eur_typical_year_forecast": typical_plan["owner_total_eur"],
                "most_a_better_forecast_could_add_eur": perfect["owner_total_eur"] - typical_plan["owner_total_eur"]}

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    flows, _ = run_year(gen, demand, ids, sy, "typical", battery, args.guest_discount, export_limit=limit)
    write_decisions(out / "decisions_hourly.csv", host["times"], gen, sy["pvpc"]["typical"], ids, demand, flows)
    summary = {"battery_type": args.type, "battery_kwh": kwh, "guest_discount": args.guest_discount,
               "buildings": ids, "sizing_with_guests": sizing_rows, "price_years": years,
               "forecast_test_2025": forecast}
    (out / "battery_agent_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    t = years["typical"]
    print(f"Battery: {kwh:g} kWh {args.type}. Typical-year prices:")
    for label, r in (("without battery", t["without_battery"]), ("with battery", t["with_battery"])):
        print(f"  {label:15}: {r['used_share']:.0%} of solar used, {r['wasted_kwh']:,} kWh wasted, "
              f"owner {r['owner_total_eur']:,} EUR/yr, guests save {r['guests_saving_eur']:,} EUR/yr")
    print("  battery gain per price year: " + ", ".join(f"{y} {v['battery_gain_eur']:+,} EUR" for y, v in years.items()))
    print(f"  with a {test_kwh:g} kWh battery, a perfect price forecast would add at most "
          f"{forecast['most_a_better_forecast_could_add_eur']:,} EUR in 2025 over the typical-year forecast")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
