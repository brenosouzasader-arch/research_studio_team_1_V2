"""Step 07: share the host's output among the host and the shortlisted buildings, hour by hour.

    python -m step07_optimize_allocation.allocation --host-dir data\\host\\nexus2 ^
        --neighbours-dir data\\neighbours\\nexus2 --out data\\allocation\\nexus2

For each hour h: G[h] = PV output, D[i,h] = use of participant i (the host is participant 0),
beta[i,h] = the agreed share. Assigned A[i,h] = beta[i,h] x G[h]; used S[i,h] = min(A[i,h], D[i,h]);
the rest of A is that participant's excess (exported, credited per the billing modality).

Three scenarios, as in the roadmap:
1. host_only     beta[host] = 1. No community. The baseline to beat.
2. fixed         one beta per participant for the whole year, proportional to its use in sunny
                 hours (sum over h of min(D[i,h], G[h])). V1's step 5c rule.
3. hourly        a beta for every hour of the year, agreed in advance (RD 244/2019 allows an
                 hourly coefficient file, changeable every 4 months). Set from PREDICTED use:
                 the host covers its own predicted use first, the rest of each hour is split in
                 proportion to the other participants' predicted use, and what nobody is
                 predicted to use goes back to the host. This is the best rule for both
                 self-consumption and the owner's money as long as a kWh used by the host is
                 worth more than one sold, and one sold more than one exported.

Checks on every scenario (also in tests): beta >= 0, betas add up to 1 in every hour with
output, and energy is conserved (used + excess = output).
Betas are computed from the predicted use and then tested against --actual use when
given (meter data), so prediction errors show up as lost self-consumption, not hidden.

Outputs in --out:
- allocation.csv            scenario, timestamp_utc, building_id, beta, allocated_kwh, used_kwh, excess_kwh
- allocation_summary.json   per scenario: generated, self-consumed, exported, ratio, per building
- betas_hourly.csv          the hourly scenario's coefficient table (rows = hours, columns = participants)
"""
import argparse
import csv
import json
from pathlib import Path

import numpy as np

from step04_read_host_demand.host_table import read_host_table
from step06_discover_neighbours.candidates import read_demand

TOL = 1e-6


def host_only(gen, demands):
    n = len(demands)
    beta = np.zeros((n, len(gen)))
    beta[0] = 1.0
    return beta


def fixed(gen, demands):
    w = np.array([np.minimum(d, gen).sum() for d in demands])
    w = w / w.sum() if w.sum() > 0 else np.eye(len(demands))[0]
    return np.repeat(w[:, None], len(gen), axis=1)


def hourly(gen, demands):
    """Host first, then the others in proportion to their predicted use, leftovers to the host."""
    d = np.array(demands)
    with np.errstate(invalid="ignore", divide="ignore"):
        host_part = np.where(gen > 0, np.minimum(d[0], gen) / gen, 0.0)
        rest = gen * (1 - host_part)
        others_need = d[1:].sum(0)
        given = np.minimum(rest, others_need)
        share = np.where(others_need > 0, given / others_need, 0.0)
        beta_others = np.where(gen > 0, d[1:] * share / gen, 0.0)
    beta_host = 1.0 - beta_others.sum(0)
    beta_host[gen <= 0] = 1.0
    return np.vstack([beta_host, beta_others])


SCENARIOS = {"host_only": host_only, "fixed": fixed, "hourly": hourly}


def check(beta, gen):
    """The roadmap's coefficient rules. Raises if one is broken."""
    if (beta < -TOL).any():
        raise ValueError("negative beta")
    sums = beta.sum(0)
    if not np.allclose(sums[gen > 0], 1.0, atol=1e-6):
        raise ValueError("betas do not add up to 1")


def account(beta, gen, actual):
    """Energy for each participant and hour, from agreed betas and actual use."""
    assigned = beta * gen
    used = np.minimum(assigned, np.array(actual))
    excess = assigned - used
    assert np.allclose(used.sum(0) + excess.sum(0), gen, atol=1e-6), "energy not conserved"
    return assigned, used, excess


def run(gen, ids, predicted, actual=None):
    """-> {scenario: {beta, assigned, used, excess}} with actual = predicted when not given."""
    actual = actual if actual is not None else predicted
    out = {}
    for name, rule in SCENARIOS.items():
        beta = rule(gen, predicted)
        check(beta, gen)
        a, u, e = account(beta, gen, actual)
        out[name] = {"beta": beta, "assigned": a, "used": u, "excess": e}
    return out


def summary(results, gen, ids):
    total = float(gen.sum())
    s = {}
    for name, r in results.items():
        used = r["used"].sum(1)
        s[name] = {"generated_kwh": round(total), "self_consumed_kwh": round(float(used.sum())),
                   "exported_kwh": round(float(r["excess"].sum())),
                   "self_consumption_ratio": round(float(used.sum() / total), 3) if total else 0.0,
                   "per_building": {i: {"beta_mean": round(float(r["beta"][k].mean()), 4),
                                        "allocated_kwh": round(float(r["assigned"][k].sum())),
                                        "used_kwh": round(float(used[k])),
                                        "excess_kwh": round(float(r["excess"][k].sum()))}
                                    for k, i in enumerate(ids)}}
    return s


def write(out_dir, times, ids, results):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamps = [str(t) + ":00Z" for t in times]
    with open(out_dir / "allocation.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scenario", "timestamp_utc", "building_id", "beta", "allocated_kwh", "used_kwh", "excess_kwh"])
        for name, r in results.items():
            for k, i in enumerate(ids):
                for h, s in enumerate(stamps):
                    w.writerow([name, s, i, round(float(r["beta"][k, h]), 6), round(float(r["assigned"][k, h]), 4),
                                round(float(r["used"][k, h]), 4), round(float(r["excess"][k, h]), 4)])
    with open(out_dir / "betas_hourly.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["timestamp_utc"] + ids)
        for h, s in enumerate(stamps):
            w.writerow([s] + [round(float(x), 6) for x in results["hourly"]["beta"][:, h]])


def main():
    ap = argparse.ArgumentParser(description="Step 07: host-only, fixed and hourly allocation")
    ap.add_argument("--host-dir", required=True, help="step 04's output folder")
    ap.add_argument("--neighbours-dir", required=True, help="step 06's output folder")
    ap.add_argument("--actual", help="optional demand_hourly.csv with ACTUAL use (meter data) to test the betas on")
    ap.add_argument("--out", default="data/allocation")
    args = ap.parse_args()
    host = read_host_table(args.host_dir)
    gen = host["generation_kwh"]
    others = read_demand(Path(args.neighbours_dir) / "demand_hourly.csv")
    ids = ["host"] + list(others)
    predicted = [host["host_demand_kwh"]] + [others[i] for i in others]
    actual = None
    if args.actual:
        real = read_demand(args.actual)
        actual = [real.get("host", predicted[0])] + [real.get(i, others[i]) for i in others]
    results = run(gen, ids, predicted, actual)
    write(args.out, host["times"], ids, results)
    s = summary(results, gen, ids)
    (Path(args.out) / "allocation_summary.json").write_text(json.dumps(s, indent=2), encoding="utf-8")
    for name, v in s.items():
        print(f"{name:10} used on site {v['self_consumption_ratio']:.0%}, exported {v['exported_kwh']:,} kWh")
    print(f"-> {args.out}")


if __name__ == "__main__":
    main()
