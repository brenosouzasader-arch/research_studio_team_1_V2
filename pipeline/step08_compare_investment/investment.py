"""Step 08: is it worth it for the owner? Money per scenario, with low/high cases.

TWO INPUTS, two parts:
A) --allocation-dir (step 07a, allocation.py): the shared-solar scenarios without a battery,
   priced with flat ASSUMED prices (CASES below). Kept for comparison with the Spanish
   sharing-law options (fixed and hourly betas).
B) --sharing-dir (step 07b, battery_agent.py): direct wiring with and without the battery,
   priced with REAL hourly prices of 2023, 2024, 2025 and the typical year. Only the panel
   cost and upkeep come from CASES; the battery's cost comes from battery_types.py.

    python -m step08_compare_investment.investment --sharing-dir data\\sharing\\demo --kwp 15.5 ^
        --out data\\investment\\demo

Too few or too many panels? The tool starts with every panel that fits. To test a smaller
system, go back to step 03 with --max-panels N and run steps 04 to 09 again.

    python -m step08_compare_investment.investment --allocation-dir data\\allocation\\nexus2 ^
        --kwp 60 --out data\\investment\\nexus2

Our business model (team decision, 12 Nov 2026): the owner pays for the panels and keeps them.
The host uses what it can; the participants buy their share at a fixed agreed price
(SALE_PRICE), cheaper than the grid, so they save (GRID_PRICE - SALE_PRICE) per kWh used.
What nobody uses is exported and credited (EXPORT_PRICE). Whether the owner may charge
participants this way is still being checked against Spanish rules.

Every price below is an ASSUMPTION for a planning estimate, not a quote. Each scenario is
run with the central values and with a low and a high case, so no single payback is promised.

Output: investment_summary.json, one entry per scenario and case:
scenario, case, capex_eur, annual_savings_eur (host's own bill), sales_eur (paid by participants),
export_value_eur, om_eur, annual_net_value_eur, simple_payback_y, participant_savings_eur,
incremental_vs_host_only_eur.
"""
import argparse
import json
from pathlib import Path

from step06_prices_and_battery import battery_types as bt

CASES = {   # Spain 2026. Panel cost: central 1,061 EUR/kWp = Marblanc Solar's average of 10 quotes (<20 kW homes, no battery,
            # June-Aug 2025) [marblancsolar.com/itemised-costs-solar-panels-in-spain, Breno's choice 15 Nov 2026];
            # best case 730 = APPA 2024 (180 kW industrial, no VAT); worst case 1,400 = ASSUMPTION (old default, no source).
            # export_price central 0.06 = Endesa Solar Plus surplus price, excl. taxes [endesa.com Solar Plus Bateria Virtual,
            # 'last update 15 Oct 2026']. Grid and sale prices are still ASSUMPTIONS.
    "central": {"capex_eur_per_kwp": 1061, "grid_price": 0.16, "sale_price": 0.10, "export_price": 0.06},
    "low":     {"capex_eur_per_kwp": 1400, "grid_price": 0.13, "sale_price": 0.08, "export_price": 0.04},
    "high":    {"capex_eur_per_kwp": 730, "grid_price": 0.20, "sale_price": 0.12, "export_price": 0.06},
}
OM_EUR_PER_KWP_YEAR = 15.0    # ASSUMPTION: cleaning, inverter fund, insurance


def evaluate(summary, kwp, cases=CASES, om=OM_EUR_PER_KWP_YEAR):
    rows = []
    for case, p in cases.items():
        capex = kwp * p["capex_eur_per_kwp"]
        om_eur = kwp * om
        base = None
        for scenario, s in summary.items():
            per = s["per_building"]
            host_used = per["host"]["used_kwh"]
            sold = sum(v["used_kwh"] for k, v in per.items() if k != "host")
            exported = s["exported_kwh"]
            savings = host_used * p["grid_price"]
            sales = sold * p["sale_price"]
            export = exported * p["export_price"]
            net = savings + sales + export - om_eur
            row = {"scenario": scenario, "case": case, "capex_eur": round(capex),
                   "annual_savings_eur": round(savings), "sales_eur": round(sales),
                   "export_value_eur": round(export), "om_eur": round(om_eur),
                   "annual_net_value_eur": round(net),
                   "simple_payback_y": round(capex / net, 1) if net > 0 else None,
                   "participant_savings_eur": round(sold * (p["grid_price"] - p["sale_price"])),
                   "self_consumption_ratio": s["self_consumption_ratio"]}
            if scenario == "host_only":
                base = net
            rows.append(row)
        for r in rows:
            if r["case"] == case:
                r["incremental_vs_host_only_eur"] = round(r["annual_net_value_eur"] - base) if base is not None else None
    return rows


def owner_total_at_discount(result, discount):
    """Owner's EUR per year if guests paid (1 - discount) x grid price: what the report's slider shows.
    The controller's choices hardly change with the discount (it always prefers serving the host,
    then guests, then export), so the kWh are kept and only the price is changed."""
    per = result["per_building"]
    guests_value = sum(v["roof_kwh_at_grid_price_eur"] for k, v in per.items() if k != "host")
    return round(result["owner_host_saving_eur"] + (1 - discount) * guests_value + result["owner_export_income_eur"])


def evaluate_battery(sharing, kwp, cases=CASES, om=OM_EUR_PER_KWP_YEAR):
    """Rows for direct sharing without and with the battery, per price year and cost case."""
    battery = {**bt.get(sharing["battery_type"]), "kwh": sharing["battery_kwh"]}
    b_capex = battery["kwh"] * battery["capex_eur_per_kwh"]
    b_om = b_capex * battery["om_share_per_year"]
    rows = []
    for year, r in sharing["price_years"].items():
        cycles = r["with_battery"]["battery_cycles_per_year"]
        life = bt.life_years(battery, cycles) if battery["kwh"] > 0 else None
        for case, p in cases.items():
            pv_capex = kwp * p["capex_eur_per_kwp"]
            pv_om = kwp * om
            for scenario, res, capex, b_cost in (("direct_no_battery", r["without_battery"], pv_capex, 0.0),
                                                 ("direct_with_battery", r["with_battery"], pv_capex + b_capex, b_om)):
                net = res["owner_total_eur"] - pv_om - b_cost
                wear = b_capex / life if (scenario == "direct_with_battery" and life) else 0.0
                payback = capex / net if net > 0 else None
                rows.append({
                    "scenario": scenario, "price_year": year, "case": case, "capex_eur": round(capex),
                    "battery_kwh": battery["kwh"] if scenario == "direct_with_battery" else 0,
                    "battery_type": battery["name"],
                    "battery_life_years": round(life, 1) if (life and scenario == "direct_with_battery") else None,
                    "owner_host_saving_eur": res["owner_host_saving_eur"],
                    "owner_sales_to_guests_eur": res["owner_sales_to_guests_eur"],
                    "owner_export_income_eur": res["owner_export_income_eur"],
                    "om_eur": round(pv_om + b_cost), "annual_net_value_eur": round(net),
                    "net_after_battery_wear_eur": round(net - wear),
                    "simple_payback_y": round(payback, 1) if payback else None,
                    "battery_replaced_before_payback": bool(life and payback and life < payback),
                    "guests_saving_eur": res["guests_saving_eur"], "guest_discount": res["guest_discount"],
                    "used_share": res["used_share"], "wasted_kwh": res["wasted_kwh"]})
    return rows


def main():
    ap = argparse.ArgumentParser(description="Step 08: owner and participant money per scenario")
    ap.add_argument("--allocation-dir", help="step 07a's output folder (allocation.py)")
    ap.add_argument("--sharing-dir", help="step 07b's output folder (battery_agent.py)")
    ap.add_argument("--kwp", type=float, required=True, help="installed kWp (step 03's <name>_yield.json)")
    ap.add_argument("--out", default="data/investment")
    args = ap.parse_args()
    if not (args.allocation_dir or args.sharing_dir):
        ap.error("give --allocation-dir, --sharing-dir or both")
    Path(args.out).mkdir(parents=True, exist_ok=True)
    if args.allocation_dir:
        summary = json.loads((Path(args.allocation_dir) / "allocation_summary.json").read_text(encoding="utf-8"))
        rows = evaluate(summary, args.kwp)
        (Path(args.out) / "investment_summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print("Sharing-law scenarios, flat assumed prices (central case):")
        for r in rows:
            if r["case"] == "central":
                print(f"  {r['scenario']:10} net {r['annual_net_value_eur']:>7,} EUR/yr, payback {r['simple_payback_y']} y, "
                      f"{r['incremental_vs_host_only_eur']:+,} vs host only")
        print(f"-> {args.out}/investment_summary.json")
    if args.sharing_dir:
        sharing = json.loads((Path(args.sharing_dir) / "battery_agent_summary.json").read_text(encoding="utf-8"))
        rows = evaluate_battery(sharing, args.kwp)
        (Path(args.out) / "investment_battery.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
        print(f"Direct sharing with real prices, battery {sharing['battery_kwh']:g} kWh {sharing['battery_type']} "
              f"(central panel cost):")
        for r in rows:
            if r["case"] == "central":
                print(f"  {r['price_year']:>7} {r['scenario']:20} net {r['annual_net_value_eur']:>7,} EUR/yr, "
                      f"payback {r['simple_payback_y']} y, guests save {r['guests_saving_eur']:,} EUR/yr")
        print(f"-> {args.out}/investment_battery.json")


if __name__ == "__main__":
    main()
