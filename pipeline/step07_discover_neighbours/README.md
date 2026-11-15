# Step 07: Discover neighbours

**Question this step answers:** which nearby buildings could use the host's spare solar?

**Roadmap:** input = candidate coordinates, building types, eligibility evidence → output = shortlist of 3-5 candidates with eligibility flags.

`candidates.py` finds the buildings near the host, predicts each one's hourly use (step 05), and keeps the **closest** ones that can actually use some of the host's surplus.

## Distance: direct wiring by default

Team decision (15 Nov 2026): the default tool **ignores the Spanish sharing law** so it also works in other cities. Guests are wired directly to the host's panels and battery, so they must be close:

- **Default:** within **100 m**, **closest first** (shorter cables, less loss, easier to agree).
- **`--legal-mode`:** the Spanish collective self-consumption rule instead, with 500 m between meters [RD 244/2019], minus a 50 m safety margin because we only know plot centres, ranked by best fit. Up to 5 km is now allowed for solar up to 5 MW (RDL 7/2026), so you can use `--max-distance 5000` with it.

```
# from Catastro: every plot within 100 m of the host
python -m step07_discover_neighbours.candidates --host-dir data\host\nexus2 --host "Carrer de Jordi Girona 29, Barcelona" --out data\neighbours\nexus2

# or your own list (e.g. other UPC buildings with SIRENA data)
python -m step07_discover_neighbours.candidates --host-dir data\host\demo --lat 41.3935 --lon 2.1689 --candidates-csv examples\demo_candidates.csv --out data\neighbours\demo
```

Your own list needs `building_id, lat, lon, use_type` and one of `yearly_kwh`, `floor_m2` (+ `dwellings` for homes) or `metered` (path to a meter CSV).

Outputs: `candidate_buildings.geojson`, `shortlist.csv`, `demand_hourly.csv` (the shortlist's hourly use).

- **fit_kwh** = how much of the host's surplus that building could use over the year. Buildings with 0 are dropped.
- **eligible_status** is always *tentative*. Only distance is checked. A direct cable, metering and the agreement need a professional check.
- Only a share of the flats sign up: `--join-rate` (**ASSUMPTION** 0.4).

Demo (examples\demo_candidates.csv): of 5 made-up buildings, 2 are within 100 m (homes at 50 m and a shop at 93 m). The school at 161 m and the homes at 144 m would join only in legal mode.

Reworked from V1: the greedy "who takes the most surplus" idea from step 5b (`sharing.py`).
