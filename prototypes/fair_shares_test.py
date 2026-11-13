"""Step 5 test: what do different hourly share rules do to each member's payback?
Community: Bruc 59 roof + 1 office + 1 school + 6 flats (synthetic profiles from step 4 sim).
Usage: python fair_shares_test.py <step4_dir> <out_json>"""
import sys, json, importlib.util
import numpy as np
spec = importlib.util.spec_from_file_location("sim", sys.argv[1] + "/community_size_sim.py")
sys_argv = sys.argv; sys.argv = ["x", "/tmp"]; sim = importlib.util.module_from_spec(spec); spec.loader.exec_module(sim); sys.argv = sys_argv
solar, mon = sim.solar, sim.mon
members = sim.build(8, ("office", "school"), seed=3)
names = [m[0] for m in members]; D = np.array([m[1] for m in members])
N = len(D)

def evaluate(B):
    G = B * solar; used = np.minimum(G, D); sur = G - used; buy = D - used
    credit = np.zeros(N)
    for m in range(12):
        k = mon == m; credit += np.minimum(sur[:, k].sum(1) * sim.P_SUR, buy[:, k].sum(1) * sim.P_BUY)
    save = used.sum(1) * sim.P_BUY + credit
    invest = G.sum(1) / solar.sum() * sim.KWP * sim.COST_KWP
    return dict(selfcons=float(used.sum() / solar.sum() * 100), payback=(invest / save).tolist(),
                invest=invest.tolist(), save=save.tolist())

# A: fixed share, same every hour (proportional to daytime use)
day_use = (D * (solar > 0)).sum(1); A = np.repeat((day_use / day_use.sum())[:, None], 8760, 1)
# B: hourly, proportional to each member's use that hour
tot = D.sum(0); Bh = D / tot
# C: optimised hourly: in each hour first cover everyone's use (water-fill), then give the leftover
#    to whoever's payback is worst so far; iterate weights on the surplus split.
def waterfill(w):
    G = np.minimum(D, D / tot * np.minimum(solar, tot))          # cover use proportionally when sun < use
    left = solar - G.sum(0)                                       # surplus hours only
    G = G + np.outer(w / w.sum(), left)
    return G / np.where(solar > 0, solar, 1)
w = np.ones(N)
for it in range(400):
    r = evaluate(waterfill(w)); pb = np.array(r["payback"])
    w = np.clip(w * np.exp(-0.3 * (pb - pb.mean()) / pb.mean()), 1e-4, None)   # less surplus to the slow-payback members
C = waterfill(w)
out = dict(names=names, yearly_kwh=D.sum(1).tolist(), solar_kwh=float(solar.sum()))
for k, B in (("fixed", A), ("hourly_simple", Bh), ("hourly_optimised", C)):
    out[k] = evaluate(B)
    print(k, round(out[k]["selfcons"], 1), [round(p, 1) for p in out[k]["payback"]])
# typical June weekday and Saturday share tables for diagrams
def pick(m, sat):
    idx = np.where((mon == m) & ((sim.dow == 5) if sat else (sim.dow == 2)))[0][:24]
    return idx.tolist()
out["june_wed_idx"] = pick(5, False); out["june_sat_idx"] = pick(5, True)
for k, B in (("fixed", A), ("hourly_simple", Bh), ("hourly_optimised", C)):
    out[k]["june_wed"] = B[:, out["june_wed_idx"]].tolist(); out[k]["june_sat"] = B[:, out["june_sat_idx"]].tolist()
out["solar_june_wed"] = solar[out["june_wed_idx"]].tolist(); out["solar_june_sat"] = solar[out["june_sat_idx"]].tolist()
out["D_june_wed"] = D[:, out["june_wed_idx"]].tolist(); out["D_june_sat"] = D[:, out["june_sat_idx"]].tolist()
json.dump(out, open(sys.argv[2], "w"))
