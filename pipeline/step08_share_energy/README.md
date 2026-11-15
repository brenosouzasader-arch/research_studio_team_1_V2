# Step 08: Share energy (and run the battery)

**Question this step answers:** hour by hour, who gets the host's solar and battery power, and what does everyone gain?

**Roadmap:** input = G[h], all D[i,h], coefficient and contract constraints → output = allocation per hour, allocated kWh, export.

There are two scripts. Use the first for the default tool, and the second to compare with the Spanish sharing law.

## 1. `battery_agent.py`: direct wiring with the battery (the default)

The agent that runs the battery for the host and its guests. How it decides is explained in [step 06's README](../step06_prices_and_battery/README.md#how-the-battery-controller-decides). In short: every day it plans 48 hours ahead, carries out 24, and plans again. Its goals, in order: 1) waste no solar, 2) most money for the owner, 3) no guest pays more than the grid.

```
python -m step08_share_energy.battery_agent --host-dir data\host\demo --neighbours-dir data\neighbours\demo --prices-dir data\prices --out data\sharing\demo
```

What it does:

1. **Checks the battery size again with the guests.** Step 06 sized it for the host alone. Guests use solar the host can't, so the best size can change. It tries `--sizes` (default 0, 10, 20, 50, 100, 200 kWh) and picks the one with the highest net value per year. `--battery-kwh 20` fixes the size instead.
2. **Runs the chosen size with real prices** from 2023, 2024, 2025 and the typical year, so you see a range, not one number.
3. **Tests the price forecast by money:** it runs 2025 with perfect knowledge of the second day's prices and again with the typical-year price, and reports the difference.

Options: `--type nmc` (any type in `battery_types.py`), `--guest-discount 0.10` (guests pay 10% less than the grid, the team's default), `--no-export`.

Outputs:
- `battery_agent_summary.json`: the sizing table with guests, the chosen size, and for each price year with and without the battery: kWh used, wasted, exported, battery cycles, the owner's money (host savings + sales to guests + export), and each building's bill with and without the roof.
- `decisions_hourly.csv`: every hour of the typical year: solar, price, battery charge and level, export, and for each building what came from the panels, the battery and the grid. This is the training data for a future learned controller.

**Demo result** (made-up office under the Bruc 59 example roof, guests: homes at 50 m and a shop at 93 m):

| | Solar used | Wasted | Owner €/yr | Guests save €/yr |
|---|---|---|---|---|
| Host alone, no battery | 77% | 4,561 kWh | (see step 06) | 0 |
| With 2 guests, no battery | 97% | 577 kWh | 2,248 | 32 |
| With 2 guests + 10 kWh LFP | 98% | 359 kWh | 2,297 (+49) | 32 |

With guests, a 10 kWh battery gains only €49 a year against a yearly cost of about €458, so the agent picks **no battery**: the guests already use almost all the solar. A perfect price forecast would add €2 a year. Prices: typical year. Battery price: **ASSUMPTION** €500/kWh.

**Limitation:** the plan uses each building's *predicted* use and is carried out as planned. With real meters, a real controller would correct itself every hour. That isn't modelled yet.

## 2. `allocation.py`: the Spanish sharing-law options (no battery)

Under Spain's collective self-consumption rules [RD 244/2019], power isn't wired directly. Each participant gets an agreed share (beta) of the output. This script compares three ways to set the shares:

| Scenario | Betas | Notes |
|---|---|---|
| `host_only` | host = 1 | The baseline to beat |
| `fixed` | one beta per participant for the year, by use in sunny hours | V1 step 5c's rule |
| `hourly` | one beta per participant **per hour**, agreed in advance from predicted use: host first, then the others by predicted need, leftovers back to the host | Allowed under RD 244/2019 (hourly coefficient file) |

```
python -m step08_share_energy.allocation --host-dir data\host\demo --neighbours-dir data\neighbours\demo --out data\allocation\demo
```

Add `--actual real_demand.csv` to test betas made from predictions against real meter data. Prediction errors then show up as lost self-consumption.

Outputs: `allocation.csv` (scenario, timestamp, building, beta, allocated, used, excess), `allocation_summary.json`, `betas_hourly.csv`.

**Checks** (in the code and in the tests): beta ≥ 0, betas add up to 1 in every hour with output, and used + excess = output. In both scripts nobody gets more than it uses, and energy is conserved.
