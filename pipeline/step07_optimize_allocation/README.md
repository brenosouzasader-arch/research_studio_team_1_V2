# Step 07: Optimize allocation

**Roadmap:** input = G[h], all D[i,h], coefficient and contract constraints → output = fixed / predefined hourly beta[i,h], allocated kWh, export.

`allocation.py` (new in V2) compares three scenarios:

| Scenario | Betas | Notes |
|---|---|---|
| `host_only` | host = 1 | The baseline to beat |
| `fixed` | one beta per participant for the year, by use in sunny hours | V1 step 5c's rule |
| `hourly` | one beta per participant **per hour**, agreed in advance from predicted use: host first, then the others by predicted need, leftovers back to the host | Allowed under RD 244/2019 (hourly coefficient file) |

```
python -m step07_optimize_allocation.allocation --host-dir data\host\demo --neighbours-dir data\neighbours\demo --out data\allocation\demo
```

Add `--actual real_demand.csv` to test betas made from predictions against real meter data. Prediction errors then show up as lost self-consumption.

Outputs: `allocation.csv` (scenario, timestamp, building, beta, allocated, used, excess), `allocation_summary.json`, `betas_hourly.csv`.

**Checks** (in code and in the tests): beta ≥ 0, betas add up to 1 in every hour with output, and used + excess = output. No energy moves between hours (no batteries).
