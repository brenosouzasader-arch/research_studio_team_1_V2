"""The battery controller: decides, hour by hour, where every kWh of solar goes.

Used by step 06 (host alone, to size the battery) and step 07 (host + guests).

THE SET-UP (team decision, 15 Nov 2026):
- The battery sits at the host and belongs to the roof owner.
- It charges ONLY from the panels, never from the grid.
- Guests are wired directly to the host's panels and battery (no sharing law in the default tool).
- Each hour, solar goes to: the host, a guest, the battery, or the grid (export). If export is
  not allowed (export_limit), the rest is curtailed (panels turned down).

THE GOALS, in this order:
1. Waste as little solar as possible. Waste = solar that no building uses: exported,
   curtailed, or lost inside the battery (charging and discharging lose energy).
2. Then make the owner as much money as possible: a kWh the host uses saves it the grid
   price; a kWh sold to a guest earns (1 - guest discount) x grid price; an exported kWh earns
   the wholesale price.
3. No guest ever pays more than the grid: guests pay (1 - discount) x the grid price of that
   same hour, and buy only what they use, so their bill can only go down.

HOW IT DECIDES: once a day it plans the next 48 hours with a linear program (scipy's HiGHS
solver), then carries out the first 24 hours and plans again the next day. The first 24 hours
use the real day-ahead prices (published the day before), the next 24 a forecast
(plan_price). The plan uses the buildings' PREDICTED use. This is a transparent optimiser,
not a trained AI: every hour's decision is written to a table that can later train a faster
supervised or reinforcement-learning controller.

The linear program for one window of T hours and n buildings (building 0 = host):
    variables   p[i,t] solar -> building i      b[i,t] battery -> building i
                c[t] solar -> battery           x[t] solar -> grid (export)
                k[t] curtailed                  s[t] battery charge at the end of hour t
    solar       sum_i p[i,t] + c[t] + x[t] + k[t] = G[t]
    battery     s[t] = s[t-1] + eta * c[t] - sum_i b[i,t] / eta      (eta = sqrt(round trip))
    needs       p[i,t] + b[i,t] <= D[i,t]                 (nobody gets more than it uses)
    limits      0 <= c[t] <= P,  sum_i b[i,t] <= P,  0 <= s[t] <= usable kWh,  x[t] <= export_limit
    maximise    sum (WASTE_WEIGHT + value[i,t]) * (p + b)  +  export_price[t] * x
Because every kWh delivered to a building earns WASTE_WEIGHT (far more than any price), the
solver first delivers as much solar as possible (goal 1) and only then uses prices (goal 2).
"""
import numpy as np
from scipy import sparse
from scipy.optimize import linprog

WASTE_WEIGHT = 10.0      # EUR per kWh: a ranking device, far above any real price (PVPC max 2023-25: 0.42)
EXPORT_TIE_BREAK = 1e-4  # EUR/kWh: when the wholesale price is 0, export rather than curtail
WINDOW_H = 48
STEP_H = 24

_cache = {}


def _matrices(n, T):
    """Constraint matrices for n buildings and T hours (built once, reused every day)."""
    key = (n, T)
    if key in _cache:
        return _cache[key]
    nv = 2 * n * T + 4 * T
    P = lambda i, t: i * T + t
    B = lambda i, t: n * T + i * T + t
    C = lambda t: 2 * n * T + t
    X = lambda t: 2 * n * T + T + t
    K = lambda t: 2 * n * T + 2 * T + t
    S = lambda t: 2 * n * T + 3 * T + t
    eq_r, eq_c, eq_v = [], [], []
    for t in range(T):                       # solar balance, rows 0..T-1
        for i in range(n):
            eq_r.append(t); eq_c.append(P(i, t)); eq_v.append(1.0)
        for col in (C(t), X(t), K(t)):
            eq_r.append(t); eq_c.append(col); eq_v.append(1.0)
    ub_r, ub_c, ub_v = [], [], []
    row = 0
    for i in range(n):                       # needs, rows 0..nT-1
        for t in range(T):
            ub_r += [row, row]; ub_c += [P(i, t), B(i, t)]; ub_v += [1.0, 1.0]
            row += 1
    for t in range(T):                       # discharge power
        for i in range(n):
            ub_r.append(row); ub_c.append(B(i, t)); ub_v.append(1.0)
        row += 1
    A_ub = sparse.csr_matrix((ub_v, (ub_r, ub_c)), shape=(row, nv))
    idx = {"P": P, "B": B, "C": C, "X": X, "K": K, "S": S}
    _cache[key] = (nv, eq_r, eq_c, eq_v, A_ub, idx)
    return _cache[key]


def plan_window(gen, demand, value, export_price, soc0, battery, export_limit=None):
    """Solve one window. gen[T], demand[n,T], value[n,T] EUR/kWh, export_price[T]. -> dict of flows."""
    demand = np.asarray(demand, dtype=float)
    n, T = demand.shape
    nv, eq_r, eq_c, eq_v, A_ub, ix = _matrices(n, T)
    usable = battery["kwh"] * battery["usable_share"]
    power = battery["kwh"] * battery["c_rate"]
    eta = np.sqrt(battery["round_trip"]) if battery["kwh"] > 0 else 1.0
    # battery balance rows T..2T-1:  s[t] - s[t-1] - eta c[t] + sum b / eta = (soc0 if t == 0)
    r, c_, v = list(eq_r), list(eq_c), list(eq_v)
    for t in range(T):
        rr = T + t
        r += [rr, rr]; c_ += [ix["S"](t), ix["C"](t)]; v += [1.0, -eta]
        if t > 0:
            r.append(rr); c_.append(ix["S"](t - 1)); v.append(-1.0)
        for i in range(n):
            r.append(rr); c_.append(ix["B"](i, t)); v.append(1.0 / eta)
    A_eq = sparse.csr_matrix((v, (r, c_)), shape=(2 * T, nv))
    b_eq = np.concatenate([gen, [soc0], np.zeros(T - 1)])
    b_ub = np.concatenate([demand.ravel(), np.full(T, power)])
    cost = np.zeros(nv)
    w = -(WASTE_WEIGHT + np.asarray(value, dtype=float)).ravel()
    cost[: n * T] = w
    cost[n * T: 2 * n * T] = w
    cost[2 * n * T + T: 2 * n * T + 2 * T] = -(np.asarray(export_price, dtype=float) + EXPORT_TIE_BREAK)
    xmax = np.inf if export_limit is None else export_limit
    bounds = ([(0, None)] * (2 * n * T) + [(0, power)] * T + [(0, xmax)] * T + [(0, None)] * T
              + [(0, usable)] * T)
    res = linprog(cost, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds, method="highs")
    if res.status != 0:
        raise RuntimeError(f"battery plan failed: {res.message}")
    z = np.maximum(res.x, 0.0)
    return {"pv_to": z[: n * T].reshape(n, T), "bat_to": z[n * T: 2 * n * T].reshape(n, T),
            "charge": z[2 * n * T: 2 * n * T + T], "export": z[2 * n * T + T: 2 * n * T + 2 * T],
            "curtail": z[2 * n * T + 2 * T: 2 * n * T + 3 * T], "soc": z[2 * n * T + 3 * T:]}


def simulate_year(gen, demand, pvpc, export_price, battery, guest_discount=0.10, plan_price=None,
                  export_limit=None, window=WINDOW_H, step=STEP_H):
    """Run the controller over the whole year. demand[n, H], building 0 = host.
    pvpc = real hourly grid price (EUR/kWh), known for the first `step` hours of each plan;
    plan_price = what the controller assumes for later hours (default: the real price, i.e. a perfect forecast).
    -> dict of hourly flows for the year (same keys as plan_window)."""
    demand = np.asarray(demand, dtype=float)
    n, H = demand.shape
    plan_price = pvpc if plan_price is None else plan_price
    share = np.ones((n, 1))
    share[1:] = 1.0 - guest_discount
    out = {k: np.zeros((n, H)) for k in ("pv_to", "bat_to")}
    out.update({k: np.zeros(H) for k in ("charge", "export", "curtail", "soc")})
    soc = 0.0
    for start in range(0, H, step):
        end = min(start + window, H)
        seen = np.array(plan_price[start:end], dtype=float)
        known = min(step, end - start)
        seen[:known] = pvpc[start:start + known]
        value = share * seen[None, :]
        plan = plan_window(gen[start:end], demand[:, start:end], value, export_price[start:end], soc, battery,
                           export_limit)
        keep = min(step, end - start)
        for k in ("pv_to", "bat_to"):
            out[k][:, start:start + keep] = plan[k][:, :keep]
        for k in ("charge", "export", "curtail", "soc"):
            out[k][start:start + keep] = plan[k][:keep]
        soc = float(plan["soc"][keep - 1])
    return out


def account(flows, gen, demand, pvpc, export_price, guest_discount, ids, battery):
    """kWh and EUR for the year from simulate_year()'s flows, at the REAL prices."""
    demand = np.asarray(demand, dtype=float)
    got = flows["pv_to"] + flows["bat_to"]                          # kWh each building gets from the roof
    grid = demand - got                                             # kWh each building still buys
    assert (grid > -1e-6).all(), "a building got more than it uses"
    losses = flows["charge"].sum() - flows["bat_to"].sum() - flows["soc"][-1]
    used = float(got.sum())
    total = float(gen.sum())
    conserved = used + flows["export"].sum() + flows["curtail"].sum() + losses + flows["soc"][-1]
    assert abs(conserved - total) < 1e-3 * max(total, 1.0), "energy not conserved"
    per = {}
    for k, i in enumerate(ids):
        grid_only = float((demand[k] * pvpc).sum())
        roof_value = float((got[k] * pvpc).sum())                  # those kWh at the grid price
        if k == 0:
            pays = 0.0
        else:
            pays = (1.0 - guest_discount) * roof_value
        bill = float((grid[k] * pvpc).sum()) + pays
        assert bill <= grid_only + 1e-6, f"{i} would pay more than grid only"
        per[i] = {"use_kwh": round(float(demand[k].sum())), "from_roof_kwh": round(float(got[k].sum())),
                  "from_battery_kwh": round(float(flows["bat_to"][k].sum())),
                  "bill_grid_only_eur": round(grid_only), "bill_with_roof_eur": round(bill),
                  "saving_eur": round(grid_only - bill),
                  "roof_kwh_at_grid_price_eur": round(roof_value, 2)}
    throughput = float(flows["bat_to"].sum())
    usable = battery["kwh"] * battery["usable_share"]
    host_saving = per[ids[0]]["saving_eur"]
    sales = sum((1.0 - guest_discount) * per[i]["roof_kwh_at_grid_price_eur"] for i in ids[1:])
    export_eur = float((flows["export"] * export_price).sum())
    return {
        "generated_kwh": round(total), "used_by_buildings_kwh": round(used),
        "exported_kwh": round(float(flows["export"].sum())), "curtailed_kwh": round(float(flows["curtail"].sum())),
        "battery_losses_kwh": round(float(losses)),
        "wasted_kwh": round(total - used), "used_share": round(used / total, 3) if total else 0.0,
        "battery_kwh": battery["kwh"], "battery_type": battery.get("name", "lfp"),
        "battery_discharged_kwh": round(throughput),
        "battery_cycles_per_year": round(throughput / usable, 1) if usable > 0 else 0.0,
        "owner_host_saving_eur": round(host_saving), "owner_sales_to_guests_eur": round(sales),
        "owner_export_income_eur": round(export_eur),
        "owner_total_eur": round(host_saving + sales + export_eur),
        "guest_discount": guest_discount,
        "guests_saving_eur": round(sum(per[i]["saving_eur"] for i in ids[1:])),
        "per_building": per,
    }
