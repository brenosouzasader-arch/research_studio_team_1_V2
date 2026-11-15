"""Step 06c: is a battery at the host worth it, and how big? (host alone, before any guests)

    python -m step06_prices_and_battery.battery_size --host-dir data\\host\\demo ^
        --prices-dir data\\prices --out data\\battery\\demo
    add --compare-types to try every battery type in battery_types.py, not only LFP

WHY HERE: the battery is sized for the host first (between step 05 and step 07), because the
owner pays for it. Step 07 checks the size again once the guests are known.

WHAT IT DOES:
1. A quick screen, with no battery model: day by day, how much midday surplus could have
   covered the host's own later use (min of the day's surplus and the day's grid purchases).
   This is the most any battery could ever move for the host. If it is near zero, stop here.
2. For each battery size (default 0 to 200 kWh) it runs the controller (dispatch.py) over the
   whole year with real prices and the host's hourly use, and compares with no battery:
   solar wasted, money for the owner, cycles per year.
3. Money per size:
      capex             = kWh x installed cost per kWh (battery_types.py)
      battery life      = min(calendar life, cycle life / cycles per year)
      yearly cost       = capex / life + upkeep (O&M)
      yearly gain       = owner's money with battery - owner's money without
      net per year      = yearly gain - yearly cost      (> 0 means the battery pays for itself)
      simple payback    = capex / (yearly gain - upkeep)
      break-even price  = the installed EUR per kWh at which net per year would be 0
                          (compare with capex_eur_per_kwh: how much cheaper batteries must get)
   The recommended size is the one with the highest net per year. If no size is above zero,
   the battery is not viable for the host alone (it may still be with guests: step 07).

Prices: real PVPC and wholesale prices from step 06a, "typical" year by default
(--price-year 2023, 2024 or 2025 to test one real year).

Outputs in --out:
- battery_sizing.csv    one row per type and size
- battery_sizing.json   the screen, the recommended size and the rows
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from step04_read_host_demand.host_table import read_host_table
from step06_prices_and_battery import battery_types as bt
from step06_prices_and_battery import dispatch
from step06_prices_and_battery.prices import read_solar_year_prices

SIZES_KWH = (0, 5, 10, 20, 30, 50, 75, 100, 150, 200)


def screen(gen, host_use):
    """Most energy any battery could move from midday surplus to the host's own later use, per year."""
    days = len(gen) // 24
    g = gen[: days * 24].reshape(days, 24)
    d = host_use[: days * 24].reshape(days, 24)
    surplus = np.maximum(g - d, 0).sum(1)
    deficit = np.maximum(d - g, 0).sum(1)
    shiftable = np.minimum(surplus, deficit)
    return {"surplus_kwh": round(float(surplus.sum())), "host_grid_purchases_kwh": round(float(deficit.sum())),
            "max_shiftable_kwh": round(float(shiftable.sum())),
            "days_with_shiftable_over_1kwh": int((shiftable > 1).sum()),
            "p90_daily_shiftable_kwh": round(float(np.percentile(shiftable, 90)), 1)}


def money(battery, gain_eur, cycles):
    capex = battery["kwh"] * battery["capex_eur_per_kwh"]
    om = capex * battery["om_share_per_year"]
    life = bt.life_years(battery, cycles) if battery["kwh"] > 0 else None
    yearly_cost = capex / life + om if life else 0.0
    net = gain_eur - yearly_cost
    payback = capex / (gain_eur - om) if gain_eur - om > 0 else None
    # installed price per kWh at which this size would just break even (net per year = 0)
    per_kwh_cost = battery["kwh"] * (1 / life + battery["om_share_per_year"]) if life else 0.0
    break_even = gain_eur / per_kwh_cost if per_kwh_cost > 0 else None
    return {"capex_eur": round(capex), "om_eur_per_year": round(om), "life_years": round(life, 1) if life else None,
            "break_even_eur_per_kwh": round(break_even) if break_even is not None else None,
            "yearly_cost_eur": round(yearly_cost), "yearly_gain_eur": round(gain_eur),
            "net_per_year_eur": round(net), "simple_payback_y": round(payback, 1) if payback else None}


def size_battery(gen, demand, pvpc, spot, ids=("host",), types=(bt.DEFAULT,), sizes=SIZES_KWH,
                 guest_discount=0.10, plan_price=None, export_limit=None):
    """Run the controller for every type and size. demand[n, H]. -> (rows, {type: best row or None})."""
    demand = np.atleast_2d(demand)
    rows, best = [], {}
    for name in types:
        base = None
        for kwh in sizes:
            b = {**bt.get(name), "kwh": float(kwh)}
            flows = dispatch.simulate_year(gen, demand, pvpc, spot, b, guest_discount, plan_price, export_limit)
            a = dispatch.account(flows, gen, demand, pvpc, spot, guest_discount, list(ids), b)
            if base is None:
                base = a if kwh == 0 else dispatch.account(
                    dispatch.simulate_year(gen, demand, pvpc, spot, {**b, "kwh": 0.0}, guest_discount, plan_price,
                                           export_limit), gen, demand, pvpc, spot, guest_discount, list(ids),
                    {**b, "kwh": 0.0})
            m = money(b, a["owner_total_eur"] - base["owner_total_eur"], a["battery_cycles_per_year"])
            rows.append({"battery_type": name, "battery_kwh": kwh, "used_share": a["used_share"],
                         "wasted_kwh": a["wasted_kwh"], "exported_kwh": a["exported_kwh"],
                         "battery_losses_kwh": a["battery_losses_kwh"],
                         "cycles_per_year": a["battery_cycles_per_year"], "owner_total_eur": a["owner_total_eur"],
                         "guests_saving_eur": a["guests_saving_eur"], **m})
        mine = [r for r in rows if r["battery_type"] == name and r["battery_kwh"] > 0]
        top = max(mine, key=lambda r: r["net_per_year_eur"]) if mine else None
        best[name] = top if top and top["net_per_year_eur"] > 0 else None
    return rows, best


def main():
    ap = argparse.ArgumentParser(description="Step 06c: battery at the host: viable? what size?")
    ap.add_argument("--host-dir", required=True, help="step 04's output folder")
    ap.add_argument("--prices-dir", default="data/prices", help="step 06a's output folder")
    ap.add_argument("--price-year", default="typical", help="typical, 2023, 2024 or 2025")
    ap.add_argument("--type", default=bt.DEFAULT, choices=list(bt.TYPES))
    ap.add_argument("--compare-types", action="store_true", help="try every battery type")
    ap.add_argument("--sizes", type=float, nargs="+", default=list(SIZES_KWH), help="battery sizes in kWh")
    ap.add_argument("--no-export", action="store_true", help="the host may not export: surplus is curtailed")
    ap.add_argument("--out", default="data/battery")
    args = ap.parse_args()
    host = read_host_table(args.host_dir)
    sy = read_solar_year_prices(Path(args.prices_dir) / "prices_hourly_solar_year.csv")
    year = int(args.price_year) if args.price_year.isdigit() else args.price_year
    gen, use = host["generation_kwh"], host["host_demand_kwh"]
    s = screen(gen, use)
    print(f"Screen: {s['surplus_kwh']:,} kWh surplus a year; at most {s['max_shiftable_kwh']:,} kWh could be "
          f"moved to the host's own later use ({s['days_with_shiftable_over_1kwh']} days with more than 1 kWh).")
    types = list(bt.TYPES) if args.compare_types else [args.type]
    rows, best = size_battery(gen, use[None, :], sy["pvpc"][year], sy["spot"][year], types=types,
                              sizes=args.sizes, export_limit=0.0 if args.no_export else None)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "battery_sizing.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    rec = best.get(args.type) if not args.compare_types else best.get(bt.DEFAULT)
    result = {"price_year": str(year), "screen": s,
              "recommended": {t: (b["battery_kwh"] if b else 0) for t, b in best.items()},
              "recommended_kwh": rec["battery_kwh"] if rec else 0,
              "viable_for_host_alone": rec is not None, "rows": rows}
    (out / "battery_sizing.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print("  type             kWh  used  wasted kWh  cycles/yr  gain EUR/yr  cost EUR/yr  net EUR/yr  payback  break-even EUR/kWh")
    for r in rows:
        print(f"  {r['battery_type']:15} {r['battery_kwh']:>4g}  {r['used_share']:.0%}  {r['wasted_kwh']:>10,}"
              f"  {r['cycles_per_year']:>9}  {r['yearly_gain_eur']:>11,}  {r['yearly_cost_eur']:>11,}"
              f"  {r['net_per_year_eur']:>10,}  {str(r['simple_payback_y'] or '-'):>7}  {r['break_even_eur_per_kwh'] or '-'}")
    for t, b in best.items():
        print(f"{t}: " + (f"best size {b['battery_kwh']:g} kWh, +{b['net_per_year_eur']:,} EUR/yr after paying for it"
                          if b else "no size pays for itself for the host alone (check again with guests in step 07)"))
    print(f"-> {out}")


if __name__ == "__main__":
    main()
