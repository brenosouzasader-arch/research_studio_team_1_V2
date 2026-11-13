# Step 04: Read host demand

**Roadmap:** input = authorized 15/30/60-minute meter data OR proxy profiles; use; floor area → output = hourly demand D[host,h], quality flags. **Week 1 gate:** host PV + host load in one 8,760-hour table.

`host_table.py` (new in V2) reads step 03's hourly solar output and the host's demand, and lines them up hour by hour.

```
# with a meter export (best): any interval, a time column and a kWh column, UTC
python -m step04_read_host_demand.host_table --solar nexus2_hourly.csv --metered data\meters\nexus2.csv --building-id nexus2 --out data\host\nexus2

# without one: step 05's proxy profile from use type and floor area
python -m step04_read_host_demand.host_table --solar examples\bruc59_hourly.csv --host-kind office --host-floor-m2 1500 --building-id demo --out data\host\demo
```

Outputs in `--out`: `pv_hourly.csv`, `demand_hourly.csv`, `host_table.csv` (generation, host demand, self-consumed, surplus), `host_summary.json`, `surplus_map.png` (365 days × 24 hours).

Every demand row says where it came from: `metered` / `ok`, or `proxy_office` / `assumed`. Meter gaps are filled with the average of the same weekday hour.

**Try it now** (no internet): the second command above runs on the Bruc 59 example roof.

**A real result can be "no surplus".** If `surplus_share` in the summary is small, sharing does not pay for that host. That is a valid answer.
