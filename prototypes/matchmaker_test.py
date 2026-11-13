"""Prototype AI matchmaker: host office roof + pool of candidate flats.
Greedy: keep adding the flat that soaks up the most of the remaining surplus (hour by hour, whole year),
stop when the next flat would add too little. Usage: python matchmaker_test.py <step4_dir> <out_json>"""
import sys, json, importlib.util, io, contextlib
import numpy as np
spec = importlib.util.spec_from_file_location("sim", sys.argv[1] + "/community_size_sim.py")
argv = sys.argv; sys.argv = ["x", "/tmp"]
with contextlib.redirect_stdout(io.StringIO()):
    sim = importlib.util.module_from_spec(spec); spec.loader.exec_module(sim)
sys.argv = argv
r = np.random.default_rng(11)
solar = sim.solar                                   # 15.5 kWp roof, kW per hour
host = sim.office(r)                                # host building use (meter data in real tool)
surplus = np.maximum(solar - host, 0)               # what the host can't use itself
host_used = np.minimum(solar, host).sum()
# candidate pool: 80 flats within 500 m, three usage types
pool = []
for i in range(80):
    f = sim.flat(r); day = (f.reshape(365, 24)[:, 9:17].sum() / f.sum())
    pool.append(f)
pool = np.array(pool)
daytime = np.array([p.reshape(365, 24)[:, 9:17].sum() / p.sum() for p in pool])
wkend = np.array([p[sim.weekend].sum() / p.sum() for p in pool])
VALUE = sim.P_BUY - sim.P_SUR                       # extra value of a kWh used by a flat instead of credited
chosen, absorbed, curve = [], np.zeros(8760), []
remaining = list(range(len(pool)))
while remaining and len(chosen) < 45:
    gains = [np.minimum(surplus, absorbed + pool[j]).sum() - np.minimum(surplus, absorbed).sum() for j in remaining]
    k = int(np.argmax(gains)); g = gains[k]
    j = remaining.pop(k)
    total_used = host_used + np.minimum(surplus, absorbed + pool[j]).sum()
    curve.append(dict(n=len(chosen) + 1, gain_kwh=float(g), used_pct=float(total_used / solar.sum() * 100), flat=int(j)))
    chosen.append(j); absorbed = absorbed + pool[j]
STOP_KWH = 250                                      # stop when next flat soaks up < 250 kWh/yr (~€25/yr extra value)
n_best = next(c["n"] for c in curve if c["gain_kwh"] < STOP_KWH) - 1
best = chosen[:n_best]
absorbed_best = pool[best].sum(0)
left = np.maximum(surplus - absorbed_best, 0)
# random group of the same size for comparison
rand = r.choice(len(pool), n_best, replace=False)
rand_used = (host_used + np.minimum(surplus, pool[rand].sum(0)).sum()) / solar.sum() * 100
out = dict(n_best=n_best, used_host_only=float(host_used / solar.sum() * 100), used_best=curve[n_best - 1]["used_pct"],
           used_random_same_n=float(rand_used), curve=curve[:40], surplus_kwh=float(surplus.sum()),
           surplus_map=surplus.reshape(365, 24).T.tolist(), left_map=left.reshape(365, 24).T.tolist(),
           pool_daytime=daytime.tolist(), pool_weekend=wkend.tolist(), best=best,
           weekend_share_of_surplus=float(surplus[sim.weekend].sum() / surplus.sum()),
           august_share_of_surplus=float(surplus[sim.mon == 7].sum() / surplus.sum()))
json.dump(out, open(argv[2], "w"))
print({k: (round(v, 2) if isinstance(v, float) else v) for k, v in out.items() if k in ("n_best", "used_host_only", "used_best", "used_random_same_n", "surplus_kwh", "weekend_share_of_surplus", "august_share_of_surplus")})
print("picked daytime share mean", np.mean(daytime[best]).round(3), "pool", daytime.mean().round(3))
print([ (c['n'], round(c['gain_kwh']), round(c['used_pct'],1)) for c in curve[:30]])
