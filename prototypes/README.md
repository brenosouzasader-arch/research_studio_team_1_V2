# Prototypes

Quick tests from the post-midterm research (11-12 Nov 2026), kept as reference. They use made-up profiles, not the pipeline. Each idea has since been built into a pipeline step.

| File | What it tried | Now in |
|---|---|---|
| `community_size_sim.py` | How many members a 15.5 kWp roof needs before ~90% is used on the spot | step 06 (shortlist size) |
| `matchmaker_test.py` | Greedy pick of flats that soak up an office roof's surplus, stopping when the next adds < 250 kWh/yr | step 06 (`fit_kwh`) |
| `fair_shares_test.py` | Three ways to set shares (fixed, hourly by need, fair paybacks) | step 07 |
| `two_roofs_test.py` | Adding a second (guest) roof to a community | not built |

They read each other by path, e.g. `python prototypes/matchmaker_test.py prototypes out.json`.
