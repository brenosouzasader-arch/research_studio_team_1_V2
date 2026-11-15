"""Step 07 (neighbours and sharing in one tool): find the best group of neighbours to share the roof with.

    python -m step07_share_energy.optimise --host-dir data\\host\\cep9 --lat 41.40458605 --lon 2.20067448 ^
        --candidates-csv examples\\cep9_members.csv --mode wired --out data\\match\\cep9

Step 07 used to pick the closest buildings and step 07 then shared the power. This tool does both
in one go. It takes EVERY building within reach of the host and tries many combinations of them,
hour by hour for the whole year, looking for the combination that

    1. wastes the least solar (the most kWh used by the host and the guests together; waste = sent
       to the grid), then
    2. earns the owner the most money.

Each building must pay its way: a building only counts as part of the answer if it adds at least
--min-gain-kwh (default 250 kWh a year) of used solar on top of the others (ASSUMPTION; it is the
stopping rule of the team's matchmaker diagram, and avoids wiring up a building for nothing).
No guest ever pays more than the grid: guests pay (1 - --guest-discount) x the PVPC of each hour.

TWO WAYS OF SHARING (--mode):
  wired   (default) guests are wired straight to the host's panels; the solar goes hour by hour to
          whoever needs it: host first, then the guests. Reach: 100 m. Works in any city.
  legal   the Spanish collective self-consumption rules, RD 244/2019: no new cable, each member gets
          a FIXED share (beta) of every hour's output for the whole year, set in advance from use in
          sunny hours. Reach: 500 m between meters (we use 450 m, because we only know plot centres).
          A member's share in an hour it doesn't need goes to the grid, so less solar is used.
          This is the option for central Barcelona. Up to 5 km is allowed for solar up to 5 MW
          (RDL 7/2026): use --max-distance 5000.

How the search works. With few candidates every combination is tried (exhaustive). With many, it
starts from the best single building, adds, removes and swaps buildings until nothing improves, and
repeats from random starting groups; "tried" says how many different groups were worked out.
At most --max-guests buildings are in a group (default 6: more cables and contracts are hard to run).

The chosen group is written in step 07's format (shortlist.csv, candidate_buildings.geojson,
demand_hourly.csv), so the battery agent (battery_agent.py) and steps 08-10 run on it unchanged.

Outputs in --out: match_summary.json (every number below), plus step 07's three files.
"""
import argparse
import csv
import itertools
import json
import math
from pathlib import Path

import numpy as np

from step04_read_host_demand.host_table import read_host_table
from step06_prices_and_battery.prices import read_solar_year_prices
from step07_share_energy import candidates as nb

MAX_GUESTS = 6              # ASSUMPTION: more guests than this is hard to wire and to contract
MIN_GAIN_KWH = 250.0        # ASSUMPTION: a building must add this much used solar a year to be worth joining
EXHAUSTIVE_LIMIT = 60000    # try every group when there are at most this many
RANDOM_STARTS = 300
DISCOUNT = 0.10             # team choice 15 Nov 2026: guests pay the grid price minus 10%
MODES = {
    "wired": {"reach_m": nb.MAX_DISTANCE_M, "margin_m": nb.DISTANCE_MARGIN_M, "rank": "distance",
              "what": "guests wired directly to the host, solar sent hour by hour to whoever needs it"},
    "legal": {"reach_m": nb.LEGAL_MAX_DISTANCE_M, "margin_m": nb.LEGAL_MARGIN_M, "rank": "fit",
              "what": "Spanish collective self-consumption (RD 244/2019): no new cable, one fixed share per member for the year"},
}


class Case:
    """Everything one search needs: solar, host use, guests' use, prices."""

    def __init__(self, gen, host_demand, ids, demands, pvpc, spot, mode="wired", discount=DISCOUNT):
        self.g, self.h = np.asarray(gen, float), np.asarray(host_demand, float)
        self.ids, self.D = list(ids), np.asarray(demands, float).reshape(len(ids), -1)
        self.pvpc, self.spot, self.mode, self.discount = pvpc, spot, mode, discount
        self.host_used = np.minimum(self.g, self.h)
        self.sunny = np.minimum(self.D, self.g[None, :]).sum(1)      # each guest's use in sunny hours
        self.host_sunny = float(self.host_used.sum())

    def evaluate(self, idx):
        """-> dict for the group idx (indices into ids): used, exported, owner money, guests' savings."""
        g = self.g
        if not len(idx):
            used_h, used_g, export = self.host_used, np.zeros_like(g), g - self.host_used
            per = {}
        elif self.mode == "wired":
            surplus = g - self.host_used
            need = self.D[list(idx)].sum(0)
            used_g = np.minimum(surplus, need)
            used_h, export = self.host_used, surplus - used_g
            with np.errstate(invalid="ignore", divide="ignore"):
                share = np.where(need > 0, used_g / need, 0.0)
            per = {self.ids[i]: self.D[i] * share for i in idx}
        else:                                                         # fixed betas, one per member for the year
            w = np.array([self.host_sunny] + [self.sunny[i] for i in idx])
            beta = w / w.sum() if w.sum() > 0 else np.eye(len(w))[0]
            used_h = np.minimum(beta[0] * g, self.h)
            per = {self.ids[i]: np.minimum(beta[k + 1] * g, self.D[i]) for k, i in enumerate(idx)}
            used_g = sum(per.values())
            export = g - used_h - used_g
        gu_eur = sum(float((u * self.pvpc).sum()) for u in per.values()) if per else float((used_g * self.pvpc).sum())
        owner = (float((used_h * self.pvpc).sum()) + (1 - self.discount) * gu_eur
                 + float((export * self.spot).sum()))
        return {"used_kwh": float(used_h.sum() + used_g.sum()), "export_kwh": float(export.sum()),
                "owner_eur": owner, "guests_save_eur": self.discount * gu_eur,
                "guest_used_kwh": float(np.sum(used_g)), "host_used_kwh": float(used_h.sum())}


def search(case, dist=None, max_guests=MAX_GUESTS, min_gain=MIN_GAIN_KWH, seed=1, exhaustive_limit=EXHAUSTIVE_LIMIT,
           random_starts=RANDOM_STARTS):
    """Try groups of guests; return (results dict {tuple of indices: metrics}, was it exhaustive)."""
    n = len(case.ids)
    dist = np.zeros(n) if dist is None else np.asarray(dist, float)
    k_max = min(max_guests, n)
    total = sum(math.comb(n, k) for k in range(k_max + 1))
    seen = {}

    def score(idx):
        key = tuple(sorted(idx))
        if key not in seen:
            m = case.evaluate(key)
            m["score"] = m["used_kwh"] - min_gain * len(key) - 1e-6 * float(dist[list(key)].sum())
            seen[key] = m
        return seen[key]["score"]

    if total <= exhaustive_limit:
        for k in range(k_max + 1):
            for c in itertools.combinations(range(n), k):
                score(c)
        return seen, True
    rng = np.random.default_rng(seed)

    def climb(start):
        cur = set(start)
        best = score(cur)
        improved = True
        while improved:
            improved = False
            moves = [cur | {i} for i in range(n) if i not in cur and len(cur) < k_max]
            moves += [cur - {i} for i in cur]
            moves += [(cur - {i}) | {j} for i in cur for j in range(n) if j not in cur]
            for m in moves:
                s = score(m)
                if s > best + 1e-9:
                    best, cur, improved = s, set(m), True
        return cur

    climb(set())
    for _ in range(random_starts):
        k = int(rng.integers(1, k_max + 1))
        climb(set(rng.choice(n, size=k, replace=False).tolist()))
    return seen, False


def summarise(case, seen, exhaustive, ids_meta, top=10):
    """The answer, in the form the website and the READMEs show."""
    alone = case.evaluate(())
    ranked = sorted(seen.items(), key=lambda kv: (-kv[1]["score"], kv[1]["owner_eur"] * -1))
    best_key, best = ranked[0]
    gen = float(case.g.sum())

    def row(key, m):
        return {"buildings": [case.ids[i] for i in key], "n": len(key),
                "used_share": round(m["used_kwh"] / gen, 4) if gen else 0.0, "used_kwh": round(m["used_kwh"]),
                "to_grid_kwh": round(m["export_kwh"]), "owner_eur": round(m["owner_eur"]),
                "guests_save_eur": round(m["guests_save_eur"])}

    marginal = []
    for i in best_key:
        without = tuple(j for j in best_key if j != i)
        marginal.append({"building": case.ids[i], "adds_kwh": round(best["used_kwh"] - seen[without]["used_kwh"])
                         if without in seen else round(best["used_kwh"] - case.evaluate(without)["used_kwh"])})
    everyone = tuple(range(len(case.ids)))
    return {"mode": case.mode, "what": MODES[case.mode]["what"], "tried": len(seen), "exhaustive": exhaustive,
            "candidates": ids_meta, "generated_kwh": round(gen),
            "host_alone": {"used_share": round(alone["used_kwh"] / gen, 4) if gen else 0.0,
                           "used_kwh": round(alone["used_kwh"]), "to_grid_kwh": round(alone["export_kwh"]),
                           "owner_eur": round(alone["owner_eur"])},
            "everyone": row(everyone, case.evaluate(everyone)) if len(everyone) <= 12 else None,
            "best": {**row(best_key, best), "marginal": marginal},
            "top": [row(k, m) for k, m in ranked[:top]]}


def run(host, candidates, host_latlon, prices_dir, mode="wired", max_distance=None, max_guests=MAX_GUESTS,
        min_gain=MIN_GAIN_KWH, discount=DISCOUNT, join_rate=nb.JOIN_RATE, exclude=()):
    cfg = MODES[mode]
    reach = max_distance or cfg["reach_m"]
    scored, inside, demand = nb.shortlist(host, candidates, host_latlon, reach, n=10 ** 6, join_rate=join_rate,
                                          exclude=exclude, margin=cfg["margin_m"], rank=cfg["rank"])
    sy = read_solar_year_prices(Path(prices_dir) / "prices_hourly_solar_year.csv")
    ids = [r["building_id"] for r in inside]
    if not ids:
        return scored, inside, demand, {"mode": mode, "tried": 0, "best": {"buildings": []}, "candidates": []}
    case = Case(host["generation_kwh"], host["host_demand_kwh"], ids, [demand[i] for i in ids],
                sy["pvpc"]["typical"], sy["spot"]["typical"], mode, discount)
    seen, exhaustive = search(case, [r["distance_m"] for r in inside], max_guests, min_gain)
    meta = [{k: r.get(k) for k in ("building_id", "name", "use_type", "distance_m", "yearly_kwh", "fit_kwh")}
            for r in inside]
    result = summarise(case, seen, exhaustive, meta)
    result.update({"reach_m": reach - cfg["margin_m"], "max_guests": max_guests, "min_gain_kwh": min_gain,
                   "guest_discount": discount})
    return scored, inside, demand, result


def main():
    ap = argparse.ArgumentParser(description="Step 07: find the best group of neighbours and share the solar")
    ap.add_argument("--host-dir", required=True, help="step 04's output folder for the host")
    ap.add_argument("--host", help="host address (for its position and to leave it out)")
    ap.add_argument("--lat", type=float)
    ap.add_argument("--lon", type=float)
    ap.add_argument("--candidates-csv", help="your own candidate list instead of Catastro (see step 07)")
    ap.add_argument("--mode", choices=sorted(MODES), default="wired",
                    help="wired = direct cable, 100 m (default); legal = RD 244/2019 fixed shares, 500 m, no cable")
    ap.add_argument("--max-distance", type=float, help="metres; default 100 (wired) or 500 (legal)")
    ap.add_argument("--max-guests", type=int, default=MAX_GUESTS)
    ap.add_argument("--min-gain-kwh", type=float, default=MIN_GAIN_KWH)
    ap.add_argument("--guest-discount", type=float, default=DISCOUNT)
    ap.add_argument("--join-rate", type=float, default=nb.JOIN_RATE)
    ap.add_argument("--prices-dir", default="data/prices")
    ap.add_argument("--out", default="data/match")
    args = ap.parse_args()
    host_id = None
    if args.host:
        from step01_select_host.find_building import find_building
        record, _ = find_building(args.host)
        args.lat, args.lon, host_id = record.lat, record.lon, record.refcat
    if args.lat is None or args.lon is None:
        ap.error("give --host, or --lat and --lon")
    host = read_host_table(args.host_dir)
    reach = args.max_distance or MODES[args.mode]["reach_m"]
    if args.candidates_csv:
        with open(args.candidates_csv, newline="", encoding="utf-8-sig") as f:
            cands = list(csv.DictReader(f))
    else:
        Path(args.out).mkdir(parents=True, exist_ok=True)
        cands = nb.from_catastro(args.lat, args.lon, reach, Path(args.out) / "catastro_cache.json")
    scored, inside, demand, res = run(host, cands, (args.lat, args.lon), args.prices_dir, args.mode, args.max_distance,
                                      args.max_guests, args.min_gain_kwh, args.guest_discount, args.join_rate,
                                      {host_id} if host_id else ())
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    chosen = [r for r in inside if r["building_id"] in set(res["best"]["buildings"])]
    nb.write_outputs(out, host["times"], scored, chosen, {r["building_id"]: demand[r["building_id"]] for r in chosen})
    (out / "match_summary.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    b, a = res["best"], res.get("host_alone")
    print(f"mode {args.mode}: {len(res['candidates'])} buildings within reach, {res['tried']:,} groups tried"
          f"{' (every one)' if res.get('exhaustive') else ''}")
    if a:
        print(f"  host alone:   {a['used_share']:.0%} of the solar used, {a['to_grid_kwh']:,} kWh to the grid, owner EUR {a['owner_eur']:,}/yr")
        print(f"  best group:   {b['used_share']:.0%} used, {b['to_grid_kwh']:,} kWh to the grid, owner EUR {b['owner_eur']:,}/yr, "
              f"guests save EUR {b['guests_save_eur']:,}/yr: {', '.join(b['buildings']) or 'nobody'}")
        for m in b.get("marginal", []):
            print(f"      {m['building']}: adds {m['adds_kwh']:,} kWh used a year")
    nxt = ("battery_agent --host-dir ... --neighbours-dir " + str(out)) if args.mode == "wired" else \
          "allocation or agreed_shares with --neighbours-dir " + str(out)
    print(f"-> {out}   next: python -m step07_share_energy.{nxt}")


if __name__ == "__main__":
    main()
