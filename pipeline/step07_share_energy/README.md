# Step 07: Match and share (one optimiser)

**Question this tool answers:** of all the buildings within reach of the roof, which group should share its solar, so that the most energy is used and the least is sent back to the grid?

**Roadmap:** input = G[h], all D[i,h], coefficient and contract constraints → output = allocation per hour, allocated kWh, export.

Steps 07 (find neighbours) and 08 (share energy) used to be separate: step 07 took the closest few buildings, step 07 shared the power among them. Now `optimise.py` does both in one go. It takes **every** building within reach and tries **many combinations** of them, hour by hour for the whole year, and keeps the combination that

1. **wastes the least solar** (the most kWh used by the host and the guests together; waste = sent to the grid), then
2. **earns the owner the most money**.

A building only counts if it adds at least 250 kWh a year of used solar on top of the others, and a group has at most 6 guests (both **ASSUMPTIONS**; the first is the stopping rule of the team's matchmaker diagram). No guest ever pays more than the grid: guests pay (1 − discount) × the PVPC of every hour.

```
python -m step07_share_energy.optimise --host-dir data\host\cep9 --lat 41.40458605 --lon 2.20067448 --candidates-csv examples\cep9_members.csv --mode wired --max-distance 2000 --join-rate 1 --out data\match\cep9_wired
python -m step07_share_energy.optimise --host-dir data\host\cep9 --lat 41.40458605 --lon 2.20067448 --candidates-csv examples\cep9_members.csv --mode legal --max-distance 2000 --join-rate 1 --out data\match\cep9_legal
```

Leave out `--candidates-csv` to search Catastro for every plot within reach (needs internet, from a laptop).

## Two ways of sharing (`--mode`)

| | `wired` (default) | `legal` (Spain, RD 244/2019) |
|---|---|---|
| Connection | guests wired directly to the host's panels | **no wires**: shared through the grid; each member's share is registered with the distributor |
| Reach | 100 m | 500 m between meters (we use 450 m; up to 5 km for solar up to 5 MW since RDL 7/2026) |
| Who gets the solar each hour | whoever needs it: host first, then guests | **a fixed share (beta)** per member for the whole year, set in advance from each one's use in sunny hours |
| Unused share | goes to the next building in need | goes to the grid |
| Works outside Spain | yes | no |
| Battery | yes (`battery_agent.py`) | no: compare with `allocation.py` and `agreed_shares.py` |

Use `legal` for central Barcelona, where buildings are close but cables across streets are not realistic.

## How the search works

With few buildings, every combination is tried (exhaustive). With many, it starts from the best single building, adds, removes and swaps buildings until nothing improves, and repeats from 300 random starting groups. The output says how many different groups were worked out (`tried`). Each group is scored by the kWh used minus 250 kWh for every building in it (so a building that adds little is not worth including).

## What it writes (in `--out`)

- `match_summary.json`: every candidate with distance and fit; the number of groups tried; the host alone, the best group and the top 10 groups with kWh used, kWh to the grid, owner money and guests' savings; what each building in the best group adds
- the chosen group in step 07's format (`shortlist.csv`, `candidate_buildings.geojson`, `demand_hourly.csv`), so the next tools run on it unchanged

## Result on the CEP9 school (modelled; building use is an estimate, not meters)

| | Solar used | To the grid | Owner €/yr | Guests save €/yr |
|---|---|---|---|---|
| Host alone | 59% | 28,891 kWh | 6,728 | 0 |
| Best group, wired | 99% | 985 kWh | 8,090 | 276 |
| Best group, legal (fixed shares) | 94% | 4,305 kWh | 7,530 | 658 |

In both modes the best group is all 4 members (fire station, Maria Espinalt, Can Felipa, 30 homes). Only 4 buildings were in the list, so every one of the 16 groups was tried: the search is built for dozens of candidates and has not yet been run on a full Catastro search around a roof. The fire station adds the most (about 6,300 kWh used a year). Note that the legal mode here is *our* simple fixed-share rule; CEP9's real shares are not published.

## After the group is chosen

1. **`battery_agent.py`**: runs the battery for the host and its guests (wired mode). How it decides is in [step 06's README](../step06_prices_and_battery/README.md#how-the-battery-controller-decides). Every day it plans 48 hours ahead, carries out 24 and plans again. Goals in order: waste no solar, most money for the owner, no guest pays more than the grid.

   ```
   python -m step07_share_energy.battery_agent --host-dir data\host\cep9 --neighbours-dir data\match\cep9_wired --prices-dir data\prices --out data\sharing\cep9
   ```

   It checks the battery size again with the guests, runs the chosen size on the real 2023, 2024 and 2025 prices and the typical year, and tests the price forecast by money. Options: `--type nmc`, `--guest-discount 0.10`, `--no-export`, `--battery-kwh 20`. Outputs: `battery_agent_summary.json` and `decisions_hourly.csv` (every hour: solar, price, battery, export and each building's sources; training data for a future learned controller). **Limitation:** the plan uses each building's *predicted* use and is carried out as planned; a real controller would correct itself every hour with meters.

2. **`allocation.py`**: the Spanish sharing-law options with betas (no battery): `host_only` (host = 1), `fixed` (one beta per participant for the year) and `hourly` (a beta per hour, agreed in advance from predicted use; allowed by RD 244/2019's hourly coefficient file). `--actual` tests betas made from predictions against real meter data. Outputs: `allocation.csv`, `allocation_summary.json`, `betas_hourly.csv`.

3. **`agreed_shares.py`**: CEP9's own terms, fixed shares agreed in advance and free power, for comparison with our tool.

**Checks** (in the code and the tests): beta ≥ 0, betas add up to 1 in every hour with output, used + excess = output, nobody gets more than it uses.

Sources for the rules: RD 244/2019, consolidated text (BOE); CEP9 presentation. See [docs/SOURCES.md](../../docs/SOURCES.md).
