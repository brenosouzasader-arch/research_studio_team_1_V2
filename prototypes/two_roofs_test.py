"""Step 5 test: a guest roof adds panels. How does the ideal group size change?
Roof 1 = Bruc 59 (15.5 kWp). Roof 2 = a middle roof like Roger de Lluria 56 (10.5 kWp), same hourly shape.
Usage: python two_roofs_test.py <step4_dir> <out_json>"""
import sys, json, importlib.util, io, contextlib
import numpy as np
spec = importlib.util.spec_from_file_location("sim", sys.argv[1] + "/community_size_sim.py")
argv = sys.argv; sys.argv = ["x", "/tmp"]
with contextlib.redirect_stdout(io.StringIO()):
    sim = importlib.util.module_from_spec(spec); spec.loader.exec_module(sim)
sys.argv = argv
base = sim.solar / sim.KWP                       # kWh per kWp per hour

def run(kwp, members):
    solar = base * kwp; D = np.array([m[1] for m in members]); tot = D.sum(0)
    B = D / np.where(tot > 0, tot, 1)
    G = B * solar; used = np.minimum(G, D); sur = G - used; buy = D - used
    credit = sum(np.minimum(sur[:, sim.mon == m].sum(1) * sim.P_SUR, buy[:, sim.mon == m].sum(1) * sim.P_BUY) for m in range(12))
    save = used.sum(1) * sim.P_BUY + credit
    return dict(selfcons=float(used.sum() / solar.sum() * 100), payback=float(kwp * sim.COST_KWP / save.sum()),
                selfsuff=float(used.sum() / D.sum() * 100))

sizes = [8, 12, 16, 20, 24, 32, 48, 64]
out = {"sizes": sizes}
for label, kwp in (("roof 1 only (15.5 kWp)", 15.5), ("roof 1 + roof 2 (26 kWp)", 26.0)):
    for mix_name, mix in (("office + flats", ("office",)), ("office + school + flats", ("office", "school"))):
        rows = []
        for n in sizes:
            v = [run(kwp, sim.build(n, mix, s)) for s in range(5)]
            rows.append({k: float(np.mean([x[k] for x in v])) for k in v[0]})
        out[f"{label}|{mix_name}"] = rows
        print(label, mix_name, [(n, round(r["selfcons"]), round(r["payback"], 1)) for n, r in zip(sizes, rows)])
json.dump(out, open(argv[2], "w"), indent=1)
