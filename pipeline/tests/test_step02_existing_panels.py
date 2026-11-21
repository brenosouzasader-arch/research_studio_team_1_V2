"""Offline checks on step 02's existing-panel finder (photo colours + LiDAR)."""
import numpy as np

from step02_pv_capacity import existing_panels as ep
from step02_pv_capacity.grid import Grid
from step02_pv_capacity.lidar_roof import LidarRoof


def _roof_with_panels():
    """A 20 x 20 m flat roof (warm gravel) with an 8 x 5 m block of grey, striped panels."""
    grid = Grid(0.0, 20.0, 0.5, 40, 40)
    roof = np.ones((40, 40), bool)
    dsm = np.full((40, 40), 10.0)
    lroof = LidarRoof(grid, roof, dsm, np.zeros((40, 40), int), np.zeros((40, 40), bool),
                      roof.copy(), {"surfaces": [{"height_m": 10.0, "area_m2": 400}]}, np.zeros((40, 40), bool))
    rgb = np.zeros((200, 200, 3), np.uint8)
    rgb[...] = (210, 185, 155)                       # warm roof: red well above blue
    block = rgb[40:90, 60:140]                       # 5 m x 8 m at 0.1 m
    block[...] = (120, 125, 135)                     # grey-blue modules
    block[::6] = (200, 205, 210)                     # light frames every 0.6 m: texture
    return rgb, lroof


def test_panel_block_is_found_and_roof_is_not():
    rgb, lroof = _roof_with_panels()
    fine, coarse, blobs, other = ep.detect(rgb, lroof, 5)
    assert len(blobs) == 1
    assert 30 <= blobs[0]["area_m2"] <= 45            # 40 m2 block, edges trimmed by the cleaning
    assert not fine[150:, :].any()                    # plain gravel stays clear
    assert coarse.sum() * 0.25 > 25


def test_summary_estimates_panels():
    s = ep.summary([{"area_m2": 103.2}], 2.28 * 1.13)
    assert s["existing_panels_m2"] == 103.2
    assert s["existing_panels_estimate"] == round(103.2 * ep.PANEL_COVER / (2.28 * 1.13))


def test_listed_look_alike_is_not_a_panel():
    rgb, lroof = _roof_with_panels()
    fine, coarse, blobs, other = ep.detect(rgb, lroof, 5, not_panels=[(10.0, 13.5, 3.0, "solar water heater")])
    assert blobs == [] and not fine.any()
    assert other.sum() * 0.25 > 25                    # kept as an obstacle instead
