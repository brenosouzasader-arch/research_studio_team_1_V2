# Step 10: Publish report

**Roadmap:** input = all previous results, sources, assumptions, validation → output = 3D host/community view + exportable feasibility report.

Not built yet (roadmap Week 3-4). Plan:

- Reuse V1's 3D map (`website/` in the V1 repository: ArcGIS, the city's 3D model, roof files per building). It was built for the Eixample co-investment communities, so it needs a new view: one host, its guests within 100 m, and the scenarios side by side.
- A report page that reads `host_summary.json` (step 04), `battery_sizing.json` (step 06), `shortlist.csv` (step 07), `battery_agent_summary.json` (step 08) and `investment_battery.json` (step 09), and marks every number as measured, modelled or **ASSUMPTION**, with its source from `docs/SOURCES.md`.
- **Guest-price slider** (team decision, 15 Nov 2026): default 10% below the grid price. Use `owner_total_at_discount()` in `step09_compare_investment/investment.py`; see that step's README.
- A battery-type picker, reading the rows of `battery_sizing.json` (run step 06 with `--compare-types`).
- A "fewer panels" button that explains how to re-run from step 03 with `--max-panels`.

V1's map code was left out of this repository on purpose, so the pipeline stays small. Copy it in when this step starts.
