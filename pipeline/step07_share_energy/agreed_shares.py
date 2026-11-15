"""Step 07, second way of sharing: fixed shares agreed in advance, as real communities do.

    python -m step07_share_energy.agreed_shares --host-dir data\\host\\cep9 ^
        --neighbours-dir data\\neighbours\\cep9 --shares host=0.30,homes_30=0.232 ^
        --guest-price 0 --out data\\agreed\\cep9

The battery agent (battery_agent.py) decides every hour who gets the solar, and guests
pay the grid price minus a discount. Real Spanish communities such as CEP9 work
differently: each member gets a FIXED share of the output every hour (the "beta" in the
sharing contract), and a public owner may give it away for free. A member's share in an
hour when it doesn't need it goes to the grid.

--shares   building_id=share pairs; members not listed split what is left equally.
           "host" is the roof's own building.
--guest-price  what guests pay, as a share of the grid price (0 = free, 0.9 = 10% off).

Values use the typical-year PVPC (step 06), without taxes, like the rest of the tool.
The output says what a kWh is worth with Spanish electricity taxes too (electricity tax
5.11% and VAT 21%: ASSUMPTION, rates change over time), because real bills include them.

Writes agreed_shares_summary.json in --out.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from step04_read_host_demand.host_table import read_host_table
from step06_prices_and_battery.prices import read_solar_year_prices
from step07_share_energy.candidates import read_demand

from .allocation import account, check

TAX_FACTOR = 1.0511 * 1.21   # ASSUMPTION: electricity tax 5.11%, then VAT 21%


def parse_shares(text, ids):
    """'host=0.3,homes_30=0.2' -> array of shares in the order of ids (the rest split equally)."""
    given = {}
    for part in filter(None, (p.strip() for p in (text or "").split(","))):
        k, v = part.split("=")
        if k not in ids:
            raise SystemExit(f"--shares: unknown building {k}; known: {ids}")
        given[k] = float(v)
    left = 1.0 - sum(given.values())
    rest = [i for i in ids if i not in given]
    if left < -1e-9 or (left > 1e-9 and not rest):
        raise SystemExit(f"--shares add up to {1 - left:.3f}; they must add up to 1 (or leave members to share the rest)")
    return np.array([given.get(i, left / len(rest) if rest else 0.0) for i in ids])


def run(gen, ids, demands, shares, pvpc, guest_price=0.0, dwellings=None):
    beta = np.repeat(shares[:, None], len(gen), axis=1)
    beta[:, gen <= 0] = shares[:, None]
    check(beta, gen)
    assigned, used, excess = account(beta, gen, demands)
    out = {"generated_kwh": round(float(gen.sum())), "used_kwh": round(float(used.sum())),
           "to_grid_kwh": round(float(excess.sum())),
           "used_share": round(float(used.sum() / gen.sum()), 3) if gen.sum() else 0.0,
           "guest_price_share_of_grid": guest_price, "tax_factor": round(TAX_FACTOR, 4), "per_building": {}}
    for k, i in enumerate(ids):
        value = float((used[k] * pvpc).sum())
        paid = 0.0 if i == "host" else value * guest_price
        row = {"share": round(float(shares[k]), 4), "use_kwh": round(float(demands[k].sum())),
               "allocated_kwh": round(float(assigned[k].sum())), "used_kwh": round(float(used[k].sum())),
               "to_grid_kwh": round(float(excess[k].sum())),
               "saving_eur": round(value - paid), "saving_with_taxes_eur": round((value - paid) * TAX_FACTOR)}
        n = (dwellings or {}).get(i)
        if n:
            row.update({"dwellings": n, "per_dwelling_used_kwh": round(row["used_kwh"] / n),
                        "per_dwelling_saving_eur": round(row["saving_eur"] / n),
                        "per_dwelling_saving_with_taxes_eur": round(row["saving_with_taxes_eur"] / n)})
        out["per_building"][i] = row
    return out


def main():
    ap = argparse.ArgumentParser(description="Step 07: fixed agreed shares (as in CEP9)")
    ap.add_argument("--host-dir", required=True)
    ap.add_argument("--neighbours-dir", required=True)
    ap.add_argument("--prices-dir", default="data/prices")
    ap.add_argument("--shares", default="", help="building_id=share pairs; the rest split equally")
    ap.add_argument("--guest-price", type=float, default=0.0, help="share of the grid price guests pay (0 = free)")
    ap.add_argument("--out", default="data/agreed")
    args = ap.parse_args()
    host = read_host_table(args.host_dir)
    others = read_demand(Path(args.neighbours_dir) / "demand_hourly.csv")
    ids = ["host"] + list(others)
    demands = np.vstack([host["host_demand_kwh"]] + [others[i] for i in others])
    shares = parse_shares(args.shares, ids)
    pvpc = read_solar_year_prices(Path(args.prices_dir) / "prices_hourly_solar_year.csv")["pvpc"]["typical"]
    cands = json.loads((Path(args.neighbours_dir) / "candidate_buildings.geojson").read_text(encoding="utf-8"))
    dwellings = {f["properties"]["building_id"]: f["properties"].get("dwellings") for f in cands["features"]}
    dwellings = {k: int(float(v)) for k, v in dwellings.items() if v not in (None, "", 0)}
    res = run(host["generation_kwh"], ids, demands, shares, pvpc, args.guest_price, dwellings)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "agreed_shares_summary.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(f"{res['used_share']:.0%} of the solar used, {res['to_grid_kwh']:,} kWh to the grid")
    for i, r in res["per_building"].items():
        extra = f", {r['per_dwelling_used_kwh']} kWh and EUR {r['per_dwelling_saving_eur']} " \
                f"(EUR {r['per_dwelling_saving_with_taxes_eur']} with taxes) per home" if "dwellings" in r else ""
        print(f"  {i:16s} share {r['share']:.3f}: gets {r['allocated_kwh']:>7,} kWh, uses {r['used_kwh']:>7,}, "
              f"saves EUR {r['saving_eur']:>6,}{extra}")
    print(f"-> {out}")


if __name__ == "__main__":
    main()
