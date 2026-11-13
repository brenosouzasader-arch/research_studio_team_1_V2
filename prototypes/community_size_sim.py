"""Step 4 test: is there an ideal community size and mix for one host roof?
Illustrative only: synthetic hourly sun and demand profiles (replace with Daria's data later).
Host roof = Bruc 59 (about 15.5 kWp, 19,463 kWh/yr from our step 4 run).
Usage: python community_size_sim.py <out_dir>"""
import sys, json
import numpy as np

OUT = sys.argv[1] if len(sys.argv) > 1 else "."
P_BUY, P_SUR, COST_KWP = 0.16, 0.06, 1400          # EUR/kWh bought, EUR/kWh surplus credit, EUR/kWp
KWP, YIELD_TOTAL = 15.5, 19463                     # host roof
H = np.arange(8760); day = H // 24; hr = H % 24 + 0.5
mon = np.minimum((day / 30.42).astype(int), 11)
dow = (day + 3) % 7                                 # 2025-ish: day 0 = Thursday -> 0=Mon
weekend = dow >= 5
rng = np.random.default_rng(7)

# ---- solar (same shape as the sizing chart) ----
daylen = 12.2 + 2.6 * np.sin(2 * np.pi * (day - 80) / 365); rise = 12.5 - daylen / 2
x = (hr - rise) / daylen
s = np.where((x > 0) & (x < 1), np.sin(np.pi * x), 0) ** 1.3
solar = s * (0.75 + 0.25 * np.sin(2 * np.pi * (day - 80) / 365)) * np.repeat(np.clip(rng.beta(5, 1.6, 365), .15, 1), 24)
solar *= YIELD_TOTAL / solar.sum()


def bump(c, w):
    return np.exp(-((hr - c) / w) ** 2)


def flat(r):
    kwh = r.uniform(1600, 3400); shift = r.uniform(-1, 1); home = r.random() < 0.3   # 30% have someone home by day
    d = 0.17 + 0.25 * bump(8 + shift, 1.0) + 0.75 * bump(21 + shift, 1.8)
    d = d + (0.35 if home else 0.08) * bump(14, 2.5) + weekend * 0.25 * bump(13, 3)
    d *= (1 + 0.15 * np.cos(2 * np.pi * (day - 15) / 365))
    return d * kwh / d.sum()


def office(r):
    kwh = 20000
    open_ = (~weekend) & ~((mon == 7) & (day % 30 < 21))          # closed weekends + 3 weeks in August
    d = 0.15 + open_ * (np.clip(np.sin((hr - 7.5) / 11 * np.pi), 0, None) ** 0.6) * ((hr > 7.5) & (hr < 18.5)) * 1.0
    d *= (1 + 0.25 * np.cos(2 * np.pi * (day - 200) / 365))       # more cooling in summer
    return d * kwh / d.sum()


def school(r):
    kwh = 25000
    holiday = (mon == 6) | (mon == 7) | ((mon == 11) & (day % 30 > 20)) | ((mon == 3) & (day % 30 < 7))
    open_ = (~weekend) & ~holiday
    d = 0.08 + open_ * (np.clip(np.sin((hr - 8) / 9 * np.pi), 0, None) ** 0.7) * ((hr > 8) & (hr < 17))
    d *= (1 + 0.3 * np.cos(2 * np.pi * (day - 15) / 365))         # heating/lighting in winter
    return d * kwh / d.sum()


def build(n, mix, seed):
    r = np.random.default_rng(seed); members = []
    if "office" in mix: members.append(("office", office(r)))
    if "school" in mix: members.append(("school", school(r)))
    while len(members) < n: members.append(("flat", flat(r)))
    return members[:n]


def evaluate(members, hourly):
    D = np.array([m[1] for m in members])                 # members x 8760
    sunny = solar > 0
    if hourly:
        tot = D.sum(0); B = np.where(tot > 0, D / np.where(tot > 0, tot, 1), 1 / len(D))
    else:
        day_use = (D * sunny).sum(1); B = np.repeat((day_use / day_use.sum())[:, None], 8760, 1)
    G = B * solar; used = np.minimum(G, D); sur = G - used; buy = D - used
    credit = np.zeros(len(D)); lost = 0.0
    for m in range(12):
        k = mon == m; c = sur[:, k].sum(1) * P_SUR; cap = buy[:, k].sum(1) * P_BUY
        credit += np.minimum(c, cap); lost += np.maximum(c - cap, 0).sum() / P_SUR
    save = used.sum(1) * P_BUY + credit
    invest = (B * solar).sum(1) / solar.sum() * KWP * COST_KWP   # pay in proportion to share of output
    pb = invest / np.maximum(save, 1e-9)
    kinds = [m[0] for m in members]
    flat_pb = [p for p, k in zip(pb, kinds) if k == "flat"]
    return dict(selfcons=used.sum() / solar.sum() * 100, selfsuff=used.sum() / D.sum() * 100,
                surplus=sur.sum(), lost=lost, payback=KWP * COST_KWP / save.sum(),
                flat_payback_median=float(np.median(flat_pb)) if flat_pb else None,
                flat_payback_worst=float(np.max(flat_pb)) if flat_pb else None)


sizes = [2, 4, 8, 16, 32, 64]
mixes = {"flats only": ("flat",), "flats + office": ("office",), "flats + school": ("school",),
         "flats + office + school": ("office", "school")}
res = {}
for name, mix in mixes.items():
    for hourly in (False, True):
        rows = []
        for n in sizes:
            if n < len(mix) + 1: rows.append(None); continue
            vals = [evaluate(build(n, mix, seed), hourly) for seed in range(5)]
            rows.append({k: float(np.mean([v[k] for v in vals if v[k] is not None])) if any(v[k] is not None for v in vals) else None for k in vals[0]})
        res[f"{name}|{'hourly' if hourly else 'fixed'}"] = rows
json.dump(dict(sizes=sizes, res=res, solar_kwh=float(solar.sum())), open(f"{OUT}/results.json", "w"), indent=1)
for k, rows in res.items():
    print(k)
    for n, r in zip(sizes, rows):
        if r: print(f"  n={n:3d} selfcons={r['selfcons']:5.1f}% selfsuff={r['selfsuff']:5.1f}% payback={r['payback']:5.1f}y flatpb={r['flat_payback_median']} worst={r['flat_payback_worst']}")
