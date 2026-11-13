"""Step 08: is the community worth it for the owner? Money per scenario, with low/high cases.

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

CASES = {   # ASSUMPTIONS, Spain 2026
    "central": {"capex_eur_per_kwp": 1400, "grid_price": 0.16, "sale_price": 0.10, "export_price": 0.05},
    "low":     {"capex_eur_per_kwp": 1600, "grid_price": 0.13, "sale_price": 0.08, "export_price": 0.04},
    "high":    {"capex_eur_per_kwp": 1200, "grid_price": 0.20, "sale_price": 0.12, "export_price": 0.06},
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


def main():
    ap = argparse.ArgumentParser(description="Step 08: owner and participant money per scenario")
    ap.add_argument("--allocation-dir", required=True, help="step 07's output folder")
    ap.add_argument("--kwp", type=float, required=True, help="installed kWp (step 03's <name>_yield.json)")
    ap.add_argument("--out", default="data/investment")
    args = ap.parse_args()
    summary = json.loads((Path(args.allocation_dir) / "allocation_summary.json").read_text(encoding="utf-8"))
    rows = evaluate(summary, args.kwp)
    Path(args.out).mkdir(parents=True, exist_ok=True)
    (Path(args.out) / "investment_summary.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    for r in rows:
        if r["case"] == "central":
            print(f"{r['scenario']:10} net {r['annual_net_value_eur']:>7,} EUR/yr, payback {r['simple_payback_y']} y, "
                  f"+{r['incremental_vs_host_only_eur']:,} vs host only")
    print(f"-> {args.out}/investment_summary.json")


if __name__ == "__main__":
    main()
