# Step 02: Evaluate PV capacity

**Roadmap:** input = ICGC LiDAR + imagery, obstacle masks, panel specification, exclusion rules → output = usable m², panel count, installed kWp, layout and confidence.

| File | What it does | From V1 |
|---|---|---|
| `lidar_roof.py` | Groups 0.5 m LiDAR cells into flat surfaces; anything sticking out is an obstacle; marks lower roofs (>7 m below the main roof) and roofs on the exclusion list | step2, unchanged |
| `grid.py` | The 0.5 m grid helper | step2, unchanged |
| `ortho.py` | Downloads the ICGC orthophoto (only for the preview picture) | step2, unchanged |
| `read_roof.py` | Address → usable area, obstacles, pictures. **LiDAR only** | step2, AI model removed |
| `layout.py` | Panel rows on the usable area: 1.76 × 1.13 m, 420 W, 10° tilt, facing the side closest to south | step3, unchanged |

Usable area = free surface minus 1 m along the edge and 0.5 m around obstacles, keeping pieces where at least one panel fits.

```
python -m step02_pv_capacity.read_roof "Carrer de Jordi Girona 29, Barcelona" --laz-dir data\lidar --out nexus2
```

Outputs: `nexus2.json` (numbers), `nexus2_usable.geojson` (QGIS), `nexus2_preview.png`, `nexus2_photo.png`, `nexus2_height.png`.

Panel count and kWp come out of step 03 (`shade_yield` lays the panels and drops shaded ones).

**Roofs already in use** (sports courts, gardens): list them in `data\roof_exclusions.csv` (`refcat,reason`) and they get 0 usable m².

**Left out from V1:** the U-Net photo model (`model.py`, `train.py`, `dataset.py`). Midterm reviewers said this step does not need AI. It is still in the V1 repository if we want it back.

**Test site:** you need the ICGC LiDAR tiles that cover your site in `data\lidar` (we only have the Eixample sheets 430582 and 430583 so far).
