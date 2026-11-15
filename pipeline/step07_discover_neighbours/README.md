# Step 07: Discover neighbours (now part of the combined step 07 + 08)

**Question this step answers:** which nearby buildings could use the host's spare solar?

**Steps 07 and 08 now run as one tool:** `python -m step08_share_energy.optimise`, see [step 08's README](../step08_share_energy/README.md). It takes everything this step finds and tries many combinations of buildings, instead of only taking the closest few. This folder still holds the building search (`candidates.py`) that the combined tool uses.

`candidates.py` finds the buildings near the host, predicts each one's hourly use (step 05), and scores each by how much of the host's surplus it could use.

## Distance

Team decision (15 Nov 2026): the default tool **ignores the Spanish sharing law** so it also works in other cities. Guests are wired directly to the host's panels and battery, so they must be close:

- **Wired (default):** within **100 m**.
- **Legal (`--legal-mode`, or `--mode legal` in the combined tool):** the Spanish collective self-consumption rule with no new cable, 500 m between meters [RD 244/2019], minus a 50 m safety margin because we only know plot centres. Up to 5 km is allowed for solar up to 5 MW (RDL 7/2026): use `--max-distance 5000`.

```
# from Catastro: every plot within 100 m of the host
python -m step07_discover_neighbours.candidates --host-dir data\host\cep9 --lat 41.40458605 --lon 2.20067448 --out data\neighbours\cep9

# or your own list (e.g. the real CEP9 members)
python -m step07_discover_neighbours.candidates --host-dir data\host\cep9 --lat 41.40458605 --lon 2.20067448 --candidates-csv examples\cep9_members.csv --max-distance 2000 --join-rate 1 --out data\neighbours\cep9
```

Your own list needs `building_id, lat, lon, use_type` and one of `yearly_kwh`, `floor_m2` (+ `dwellings` for homes) or `metered` (path to a meter CSV). `examples\cep9_members.csv` is a complete example.

Outputs: `candidate_buildings.geojson`, `shortlist.csv`, `demand_hourly.csv`.

- **fit_kwh** = how much of the host's surplus that building could use over the year. Buildings with 0 are dropped.
- **eligible_status** is always *tentative*. Only distance is checked. A direct cable, metering and the agreement need a professional check.
- Only a share of the flats sign up: `--join-rate` (**ASSUMPTION** 0.4).

`examples\demo_candidates.csv` is a small made-up list used only by the offline tests.

Reworked from V1: the greedy "who takes the most surplus" idea from step 5b (`sharing.py`).
