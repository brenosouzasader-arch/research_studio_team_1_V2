# Step 02: Evaluate PV capacity

**Roadmap:** input = ICGC LiDAR + imagery, obstacle masks, panel specification, exclusion rules → output = usable m², panel count, installed kWp, layout and confidence.

| File | What it does | From V1 |
|---|---|---|
| `lidar_roof.py` | Groups 0.5 m LiDAR cells into flat surfaces; anything sticking out is an obstacle; marks lower roofs (>7 m below the main roof) and roofs on the exclusion list | step2, unchanged |
| `grid.py` | The 0.5 m grid helper | step2, unchanged |
| `ortho.py` | Downloads the ICGC orthophoto (only for the preview picture) | step2, unchanged |
| `read_roof.py` | Address → usable area, obstacles, pictures. **LiDAR only** | step2, AI model removed |
| `layout.py` | Panel rows on the usable area: 420 W (1.76 × 1.13 m) or 540 W (2.28 × 1.13 m), 10° tilt. Row direction: `--orient building` (default), `south` or `search`, see below | step3, extended |

Usable area = free surface minus 1 m along the edge and 0.5 m around obstacles, keeping pieces where at least one panel fits.

```
python -m step02_pv_capacity.read_roof "Carrer de Jordi Girona 29, Barcelona" --laz-dir data\lidar --out nexus2
```

Outputs: `nexus2.json` (numbers), `nexus2_usable.geojson` (QGIS), `nexus2_preview.png`, `nexus2_photo.png`, `nexus2_height.png`.

Panel count and kWp come out of step 03 (`shade_yield` lays the panels and drops shaded ones).

**Roofs already in use** (sports courts, gardens): list them in `data\roof_exclusions.csv` (`refcat,reason`) and they get 0 usable m².

**Left out from V1:** the U-Net photo model (`model.py`, `train.py`, `dataset.py`). Midterm reviewers said this step does not need AI. It is still in the V1 repository if we want it back.

## Which way the panel rows point (`--orient` in step 03)

A flat roof is a free choice: rows can follow the building's walls, face due south, or sit at any angle in between. Rows square to the walls waste the least roof, but turned a few degrees they sometimes fit more panels. Panels turned away from south make a little less (at 10° tilt, 45° off south costs about 2.5%: an ASSUMPTION, `yield_factor` in `layout.py`).

| `--orient` | What it does |
|---|---|
| `building` (default, as in V1) | rows along the building edge nearest south |
| `south` | rows facing due south |
| `search` | lays the panels out every 5° from -45° to +45° around the building's axis (and at due south), scores each by panels × sun factor, keeps the best, and prints the table |

**Test on the CEP9 roof (15 Nov 2026, usable area from step 02, building axis 136°):** the panel count moves between 194 and 207 (420 W) and between 136 and 152 (540 W) as the rows turn. The best is due south (+45° from the building axis) with 207 panels of 420 W, against 201 along the building axis. So on this roof turning the rows gains about 3%, not the large gain expected; other roofs may differ. Run `--orient search` on the A160 roof to compare. To be checked against another tool: see the Google Solar slot below.

## Checking our layout against another tool

The website can show a second tool's panel plan next to ours (`export_site_data --compare-image <file> --compare-caption "..."`). The best candidate is Google's Solar API / Project Sunroof view of the same roof. We have not got one yet: it needs a screenshot or an API key from a team member (do not paste the key in the repository).

**Test sites and LiDAR tiles.** Poblenou: sheets **433583 and 433584** (CEP9 school) and **432583** (A160 office), as named in `sites/*.json`. Sheet 433584 has no building class, so the code treats its class-1 points as building. The old Eixample sheets 430582 and 430583 belong to V1 and are not used by the website. UPC Campus Nord needs its sheets listed in `sites/upc_campus_nord.json` (still marked CHECK).
