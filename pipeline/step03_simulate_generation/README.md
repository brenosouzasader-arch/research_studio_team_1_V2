# Step 03: Simulate generation

**Roadmap:** input = panel layout, LiDAR shadow horizon, PVGIS hourly weather → output = timestamped hourly PV generation G[h], annual kWh, shading losses.

Carried over from V1's steps 3 and 4. Step 3 places panel rows on the usable roof that step 02 found. Step 4 works out, hour by hour for a typical year, how much electricity each panel makes after shade from neighbours, trees and rooftop structures.

| | What it uses | What it gives |
|---|---|---|
| Layout, `../step02_pv_capacity/layout.py` | Step 2 usable area, building footprint | Panel rows: 1.76 × 1.13 m panels, 420 W, 10° tilt, facing the building side closest to south, rows spaced for no row-to-row shade at winter noon |
| Shade and yield, this folder | ICGC LiDAR within 150 m (roofs, ground, trees, rooftop structures), PVGIS typical year | kWh per panel per hour, shade loss per panel, yearly and monthly totals, kWh per kWp |

## Setup (once)

Download the sunshine data (free, no key). `--site` centres it on a test site in `../../sites`:

```
python -m step03_simulate_generation.weather --site upc_campus_nord
```

This writes `data\weather\barcelona_tmy.json` (8760 hours from PVGIS).

## One roof

```
python -m step03_simulate_generation.shade_yield "Carrer de Roger de Llúria 56, Barcelona" --laz-dir data\lidar --out lluria56
```

To use a step 2 reading you already have , add `--usable lluria56_usable.geojson`.

Panels that lose more than 40% of their sun to shade are left out (for example on a lower terrace under the building's own top floors). They show in grey in the picture and are counted as `panels_left_out`. Change the limit with `--max-shade 0.3`, or keep every panel with `--max-shade 1`.

Outputs:
- `lluria56_yield.json`: panels, kWp, yearly kWh, kWh per kWp, mean shade loss, monthly kWh, and every panel with its kWh and shade loss
- `lluria56_hourly.csv`: 8760 hours of kWh for the whole roof (input for step 5 and energy sharing)
- `lluria56_panels.geojson`: panel outlines (EPSG:25831), opens in QGIS
- `lluria56_panels.png`: the layout, dark blue = most shade, orange = best panels
- `lluria56_usable.geojson`: the usable roof it used (only when you leave out `--usable`)

## All roofs, ranked

```
python -m step03_simulate_generation.batch roofs.csv --laz-dir data\lidar --out data\yield
```

To rank several candidate hosts: make `roofs.csv` with a column `address` (optional `block` = any label, `lat`, `lon`) and run `python -m step03_simulate_generation.batch roofs.csv --laz-dir data\lidar --out data\yield_hosts`. `ranking.csv` lists them from most to least yearly kWh; a roof that fails is listed with its error. `--block upc` runs only the rows labelled `upc`.


## How the calculation works

1. **Sun path:** sun position for every hour of the year (`step4/sun.py`, same formulas as the 3D map).
2. **Horizon:** a 1 m height grid from all LiDAR points within 150 m. From each panel, 36 directions are walked outwards and the steepest angle to anything taller is kept.
3. **Shade:** the sun is blocked when it is lower than the horizon in its direction. Diffuse sky light is scaled by the share of open sky.
4. **Sun on the panel:** direct + diffuse + light reflected by the roof (albedo 0.2), on the tilted panel.
5. **Electricity:** 420 W per panel, minus heat losses (−0.35% per °C above 25 °C) and 14% system losses (PVGIS default).

## Checks to do (step 6)

- Compare yearly kWh with PVGIS for the same kWp, tilt and direction on 10 open roofs (target ±10%).
- Compare shade loss with Ladybug or Google Solar on a few shaded roofs.
- Numbers to tune: `step3/layout.py` (panel size, tilt, row spacing) and `step4/energy.py` (losses).

## Known limits

- Trees are solid in winter too (LiDAR is captured with leaves on).
- Panels on a roof the LiDAR misses (new buildings since 2023) are not shaded correctly.
- No snow, no soiling seasons, no inverter clipping.
