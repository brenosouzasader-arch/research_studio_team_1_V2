# What came from V1

Source: V1 repository, `main` as of 6 Nov 2026 (the pipeline is the same in Breno's fork and in iaac-maai).

## Kept

| V1 file | V2 place | Changes |
|---|---|---|
| `step1/*` (catastro, find_building, geocode, height, heritage, lidar) | `step01_select_host/` | none |
| `step2/lidar_roof.py`, `grid.py`, `ortho.py` | `step02_pv_capacity/` | none |
| `step2/read_roof.py` | `step02_pv_capacity/read_roof.py` | LiDAR only; AI model and `--web` removed |
| `step3/layout.py` | `step02_pv_capacity/layout.py` | none (the roadmap puts the layout in step 02) |
| `step4/` sun, horizon, energy, shade_yield, weather, check_months, batch | `step03_simulate_generation/` | `--web` removed; `weather` takes `--site`; `batch --block` takes any label |
| `step5/demand.py` | `step05_forecast_demand/baseline_profiles.py` | none (it is now the rule-based baseline the AI must beat) |
| `step5/bcn_data.py` | `step05_forecast_demand/bcn_data.py` | takes `--site` |
| `step4/roof_test_set.py` (parcel download only) | `step01_select_host/parcels.py` | the general part only, without the Eixample block numbering |
| `smoke_test.py`, tests for steps 1, 2 (LiDAR), 4, weather | `pipeline/`, `pipeline/tests/` | renamed by step; the 3D-map export test removed |
| examples: Bruc 59, Diputació 311, Llúria 56 | `pipeline/examples/` | none |

## Reworked into new steps

| V1 idea | V2 place |
|---|---|
| `step5/sharing.py`: own use first, then share the surplus; greedy "who takes the most" | `step04_read_host_demand/host_table.py` and `step06_discover_neighbours/candidates.py` |
| `step5/communities.py`: fixed beta by sunny-hour use; prices and costs | `step07_optimize_allocation/allocation.py` (`fixed`) and `step08_compare_investment/investment.py` |
| Research prototypes (matchmaker, fair shares, community size) | `prototypes/` as reference |

## Left out (still in V1)

| V1 file | Why |
|---|---|
| `step2/model.py`, `train.py`, `dataset.py`, `requirements-ai.txt` | Roof AI not needed (midterm feedback); the AI effort goes to demand in step 05 |
| `step4/roof_test_set.py` (Eixample 9-block numbering) | Tied to the old study area |
| `step4/energy_map.py`, EPW notes | City energy map benchmark; Eixample-only, optional |
| `step5/communities.py` (co-investment) | The business model changed: the owner now keeps the panels |
| `web/` and `website/` (3D map) | Comes back in step 09 when we build the new view |
| `website_matchsol/` | Hourly-matching web prototype; its logic is now in steps 06-07 |
