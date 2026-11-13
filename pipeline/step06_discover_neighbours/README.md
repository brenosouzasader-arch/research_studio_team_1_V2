# Step 06: Discover neighbours

**Roadmap:** input = candidate coordinates, building types, eligibility evidence → output = shortlist of 3-5 candidates with eligibility flags.

`candidates.py` (new in V2) finds the buildings near the host and keeps the ones whose predicted use best fits the host's surplus hour by hour.

```
# from Catastro: every plot within 500 m (minus a 50 m margin) of the host
python -m step06_discover_neighbours.candidates --host-dir data\host\nexus2 --host "Carrer de Jordi Girona 29, Barcelona" --out data\neighbours\nexus2

# or your own list (e.g. other UPC buildings with SIRENA data)
python -m step06_discover_neighbours.candidates --host-dir data\host\demo --lat 41.3935 --lon 2.1689 --candidates-csv my_candidates.csv --out data\neighbours\demo
```

Your own list needs `building_id, lat, lon, use_type` and one of `yearly_kwh`, `floor_m2` (+ `dwellings` for homes) or `metered` (path to a meter CSV).

Outputs: `candidate_buildings.geojson`, `shortlist.csv`, `demand_hourly.csv` (the shortlist's hourly use).

- **fit_kwh** = how much of the host's surplus that building could use over the year.
- **eligible_status** is always *tentative*. Only distance is checked. Connection, metering and the agreement need a professional check.
- Only a share of the flats sign up: `--join-rate` (ASSUMPTION 0.4).
- The 500 m rule is the strictest in RD 244/2019; up to 5 km is allowed now for solar up to 5 MW (`--max-distance 5000`).

Reworked from V1: the greedy "who takes the most surplus" idea from step 5b (`sharing.py`) and the prototype matchmaker (`../../prototypes/matchmaker_test.py`).
