"""Offline tests for steps 3 and 4: panel layout, sun, LiDAR shade and yield.

Catastro is replaced by a stand-in and PVGIS by a clear-sky year, so no
internet is needed.
"""
import csv
import json

import laspy
import numpy as np
import pytest
from shapely import affinity
from shapely.geometry import box

from step02_pv_capacity.layout import PANEL_WP, facing_azimuth, lay_out, row_pitch
from step02_pv_capacity.grid import Grid
from step02_pv_capacity.lidar_roof import rasterise_max
from step03_simulate_generation import shade_yield
from step03_simulate_generation.horizon import horizons, is_lit, sky_view
from step03_simulate_generation.sun import sun_position
from step03_simulate_generation.weather import Weather

X0, Y0 = 430000.0, 4582000.0
LAT, LON = 41.39, 2.17
FP = box(X0, Y0, X0 + 20, Y0 + 15)


def _clear_sky_year():
    times = np.arange(np.datetime64("2023-01-01T00:30"), np.datetime64("2024-01-01T00:30"),
                      np.timedelta64(1, "h"))
    elev, _ = sun_position(times, LAT, LON)
    s = np.sin(np.deg2rad(elev.clip(0)))
    dni = np.where(elev > 2, 900 * s ** 0.3, 0.0)
    dhi = np.where(elev > 0, 100 * s, 0.0)
    return Weather(times, dni * s + dhi, dni, dhi, np.full(len(times), 18.0))


def _write_las(path, x, y, z, cls):
    header = laspy.LasHeader(point_format=6, version="1.4")
    header.offsets = [x.min(), y.min(), z.min()]
    header.scales = [0.01, 0.01, 0.01]
    las = laspy.LasData(header)
    las.x, las.y, las.z = x, y, z
    las.classification = np.asarray(cls, dtype=np.uint8)
    las.write(path)


def _scene(tower=True):
    """Our flat roof at 25 m, ground at 0 around it, and (optionally) a 60 m tower just south."""
    xs, ys = np.meshgrid(np.arange(X0 - 60, X0 + 80, 0.5), np.arange(Y0 - 60, Y0 + 75, 0.5))
    x, y = xs.ravel(), ys.ravel()
    z = np.zeros_like(x)
    cls = np.full(x.shape, 2)
    ours = (x >= X0) & (x < X0 + 20) & (y >= Y0) & (y < Y0 + 15)
    z[ours], cls[ours] = 25.0, 6
    if tower:
        t = (x >= X0) & (x < X0 + 20) & (y >= Y0 - 12) & (y < Y0 - 4)
        z[t], cls[t] = 60.0, 6
    return x, y, z, cls


class _Record:
    refcat, catastro_address, query, year_built, dwellings = "0123456DF3802C", "CL TEST 1", "test", 1900, 10
    lat, lon = LAT, LON


@pytest.fixture
def offline(tmp_path, monkeypatch):
    _write_las(tmp_path / "tile.laz", *_scene())
    monkeypatch.setattr(shade_yield, "find_building", lambda *a, **k: (_Record(), FP))
    monkeypatch.setattr(shade_yield, "load_tmy", lambda path: _clear_sky_year())
    (tmp_path / "tmy.json").write_text("{}")
    return tmp_path


def test_sun_at_barcelona_summer_noon():
    elev, az = sun_position(np.array(["2023-06-21T11:51"], dtype="datetime64[m]"), LAT, LON)
    assert abs(elev[0] - (90 - LAT + 23.44)) < 1.0 and abs(az[0] - 180) < 5


def test_layout_faces_closest_to_south_and_spaces_rows():
    eixample = box(0, 0, 30, 20)
    assert facing_azimuth(eixample) == pytest.approx(180, abs=1)
    turned = affinity.rotate(eixample, 45)   # Eixample grid: 45 degrees
    assert facing_azimuth(turned) % 90 == pytest.approx(45, abs=1)
    lay = lay_out(box(0, 0, 10, 10), eixample)
    assert 5 * 6 <= lay.count <= 6 * 7   # 5 panels a row, rows every ~1.53 m
    assert row_pitch() == pytest.approx(1.53, abs=0.02)
    assert lay.kwp == pytest.approx(lay.count * PANEL_WP / 1000)
    assert all(box(0, 0, 10, 10).contains(p) for p in lay.panels)


def test_tower_to_the_south_blocks_low_sun():
    x, y, z, cls = _scene()
    area = box(X0 - 60, Y0 - 60, X0 + 80, Y0 + 75)
    grid = Grid.around(area, 1.0, buffer=0)
    dsm = rasterise_max(np.column_stack([x, y, z]), grid)
    h = horizons(grid, dsm, [X0 + 10, X0 + 10], [Y0 + 2, Y0 + 13], [25.4, 25.4])
    south = h[:, 18]
    assert south[0] > 60 and south[0] > south[1] > 0   # nearer the tower = higher horizon
    assert h[:, 0].max() < 1          # nothing to the north
    assert sky_view(h)[0] < sky_view(h)[1] < 1
    lit = is_lit(h, np.array([30.0, 80.0]), np.array([180.0, 180.0]))
    assert not lit[1, 0] and lit[1, 1]   # north panel: winter sun blocked, summer sun clear


def test_full_run_writes_outputs_and_shade_costs_energy(offline):
    res = shade_yield.shade_yield(str(offline), "test", weather_path=str(offline / "tmy.json"),
                                  out=str(offline / "roof"), max_shade_loss=None)
    y = res["yield"]
    assert y["panels"] > 20 and y["yearly_kwh"] > 0
    assert 0.1 < y["mean_shade_loss"] < 0.9          # a 60 m tower right in front
    assert sum(y["monthly_kwh"]) == pytest.approx(y["yearly_kwh"], rel=0.01)
    losses = [p["shade_loss"] for p in res["panels"]]
    south_row = min(res["panels"], key=lambda p: p["y"])
    north_row = max(res["panels"], key=lambda p: p["y"])
    assert south_row["shade_loss"] > north_row["shade_loss"] and max(losses) > min(losses)
    rows = list(csv.reader(open(offline / "roof_hourly.csv")))
    assert len(rows) == 8761
    fc = json.loads((offline / "roof_panels.geojson").read_text())
    assert len(fc["features"]) == y["panels"]
    assert (offline / "roof_panels.png").exists()


def test_heavily_shaded_panels_are_left_out(offline):
    out = str(offline / "roof")
    every = shade_yield.shade_yield(str(offline), "test", weather_path=str(offline / "tmy.json"),
                                    out=out, max_shade_loss=None)["yield"]
    kept = shade_yield.shade_yield(str(offline), "test", weather_path=str(offline / "tmy.json"),
                                   out=out, max_shade_loss=0.4)
    y = kept["yield"]
    assert y["panels_left_out"] > 0 and y["panels"] + y["panels_left_out"] == every["panels"]
    assert all(p["shade_loss"] <= 0.4 for p in kept["panels"])
    assert y["kwh_per_kwp"] > every["kwh_per_kwp"]


def test_open_roof_yield_is_plausible(tmp_path, monkeypatch):
    _write_las(tmp_path / "tile.laz", *_scene(tower=False))
    monkeypatch.setattr(shade_yield, "find_building", lambda *a, **k: (_Record(), FP))
    monkeypatch.setattr(shade_yield, "load_tmy", lambda path: _clear_sky_year())
    (tmp_path / "tmy.json").write_text("{}")
    y = shade_yield.shade_yield(str(tmp_path), "test", weather_path=str(tmp_path / "tmy.json"),
                                out=str(tmp_path / "roof"))["yield"]
    assert y["mean_shade_loss"] < 0.05
    assert 1000 < y["kwh_per_kwp"] < 2200   # clear-sky year, so above Barcelona's real ~1,500


# ---- layout options (options.py) -----------------------------------------------
from step03_simulate_generation import options as layout_options


def test_blocks_are_rectangles_and_drop_stragglers():
    # a 3 x 6 block of good panels, plus one lonely panel and a 1 x 2 stub
    cells = [(r, c) for r in range(3) for c in range(6)] + [(5, 0), (5, 8), (5, 9)]
    good = np.ones(len(cells), bool)
    found = layout_options.blocks(cells, good, min_short=2, min_long=2, min_panels=6)
    assert len(found) == 1 and len(found[0]) == 18


def test_a_block_counts_the_same_whichever_way_it_runs():
    wide = [(r, c) for r in range(2) for c in range(3)]      # 2 rows x 3 columns
    tall = [(r, c) for r in range(3) for c in range(2)]      # 3 rows x 2 columns
    for cells in (wide, tall):
        assert len(layout_options.blocks(cells, np.ones(6, bool), 2, 2, 6)) == 1
    assert layout_options.blocks([(0, c) for c in range(6)], np.ones(6, bool), 2, 2, 6) == []   # 1 x 6 is a strip


def test_block_size_is_an_area_so_big_panels_need_fewer():
    neat = layout_options.OPTIONS[1]
    small = layout_options.min_cells(neat, 1.76 * 1.13)      # 420 W
    big = layout_options.min_cells(neat, 2.28 * 1.13)        # 540 W
    assert small == 6 and big == 5


def test_classify_says_why_a_panel_was_left_out():
    cells = [(r, c) for r in range(2) for c in range(6)] + [(5, 0)]
    kwh = np.full(len(cells), 600.0)
    kwh[-1] = 300.0                                          # a weak panel on its own
    kwh[:0] = 0
    keep, n, weak = layout_options.classify(cells, kwh, layout_options.OPTIONS[1])
    assert n == 1 and keep.sum() == 12 and weak[-1] and not weak[:12].any()


def test_weak_panels_are_left_out_of_best_blocks():
    cells = [(r, c) for r in range(2) for c in range(8)]
    kwh = np.full(len(cells), 600.0)
    kwh[[0, 8]] = 400.0                      # the first column is shaded
    keep, n = layout_options.choose(cells, kwh, layout_options.OPTIONS[2])
    assert n == 1 and keep.sum() == 14 and not keep[0] and not keep[8]
    every, _ = layout_options.choose(cells, kwh, layout_options.OPTIONS[0])
    assert every.all()


def test_540_w_panels_are_bigger_and_count_more_kwp():
    from step02_pv_capacity.layout import MODULES
    roof = box(0, 0, 20, 10)
    eixample = box(0, 0, 20, 10)
    small = lay_out(roof, eixample, module=MODULES[420])
    big = lay_out(roof, eixample, module=MODULES[540])
    assert big.count < small.count
    assert big.kwp == pytest.approx(big.count * 0.54)
    assert len(small.cells) == small.count


def test_shade_yield_writes_all_variants(offline, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    res = shade_yield.shade_yield(str(offline), "test", weather_path=str(offline / "tmy.json"),
                                  out=str(tmp_path / "r"), compare_wp=[540])
    ids = {(v["panel_wp"], v["option"]) for v in res["variants"]}
    assert ids == {(w, o) for w in (420, 540) for o in ("max", "neat", "best")}
    assert (tmp_path / "r_options.png").exists()
    maxv = next(v for v in res["variants"] if v["panel_wp"] == 420 and v["option"] == "max")
    assert maxv["panels"] == res["yield"]["panels"]
    for v in res["variants"]:
        assert v["panels"] <= maxv["panels"] or v["panel_wp"] == 540


def test_combine_roofs_adds_two_roofs(tmp_path):
    import json
    from step03_simulate_generation import combine_roofs as cr
    def roof(name, kwh):
        times = [f"2023-01-01T{h:02d}:30" for h in range(24)]
        (tmp_path / f"{name}_hourly_420_neat.csv").write_text("time_utc,kwh\n" + "".join(f"{t},{kwh}\n" for t in times))
        (tmp_path / f"{name}_hourly.csv").write_text((tmp_path / f"{name}_hourly_420_neat.csv").read_text())
        v = {"panel_wp": 420, "panel": "420 W", "option": "neat", "name": "Neat", "rule": "r", "blocks": 1, "panels": 10,
             "kwp": 4.2, "tilt_deg": 10, "azimuth_deg": 135, "yearly_kwh": 1000, "kwh_per_kwp": 238, "mean_shade_loss": 0.1,
             "monthly_kwh": [10] * 12, "peak_hour_kw": kwh, "hourly_file": f"data\\pv\\{name}_hourly_420_neat.csv",
             "panel_list": [{"x": 1, "y": 2, "kwh_year": 100, "corners": []}]}
        y = {"building": {"refcat": name, "address": name, "query": name},
             "yield": {"panels": 10, "kwp": 4.2, "tilt_deg": 10, "azimuth_deg": 135, "yearly_kwh": 1000, "kwh_per_kwp": 238,
                       "mean_shade_loss": 0.1, "monthly_kwh": [10] * 12, "peak_hour_kw": kwh, "panels_left_out": 1,
                       "max_shade_loss": 0.4, "panel_wp": 420, "layout": "neat"},
             "usable_area_m2": 50.0, "usable_file": "u.geojson", "roof": {}, "lidar": {}, "panels": [], "variants": [v]}
        (tmp_path / f"{name}_yield.json").write_text(json.dumps(y))
        return (name, tmp_path / f"{name}_yield.json")
    r = cr.combine([roof("red", 1.0), roof("yellow", 2.0)], tmp_path / "both")
    assert r["yield"]["panels"] == 20 and r["yield"]["yearly_kwh"] == 2000 and r["yield"]["peak_hour_kw"] == 3.0
    assert {q["roof"] for q in r["variants"][0]["panel_list"]} == {"red", "yellow"}
    assert (tmp_path / "both_hourly.csv").exists() and r["variants"][0]["monthly_kwh"] == [20] * 12


def test_custom_panel_size_changes_the_count(offline, monkeypatch):
    monkeypatch.setattr(shade_yield, "load_tmy", lambda path: _clear_sky_year())
    (offline / "tmy.json").write_text("{}")
    def run(**kw):
        return shade_yield.shade_yield(str(offline), "test", weather_path=str(offline / "tmy.json"),
                                       out=str(offline / "o" / "roof"), **kw)["yield"]
    base, big, small = run(panel_wp=540), run(panel_wp=540, panel_size=(2.6, 1.3)), run(panel_wp=540, panel_size=(1.7, 1.0))
    assert big["panels"] < base["panels"] < small["panels"]
