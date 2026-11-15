"""Three panel layouts for one roof, from most panels to neatest and best.

Real installers build neat rectangular blocks of panels on the best part of a
roof. They leave out single panels in corners, ragged row ends and shaded spots.
On the CEP9 school, the real system is about 108 panels in tidy rows. Our "fill
the roof" layout also puts scattered panels on the cluttered south roof.

So step 03 gives the user three options to choose from:

    max   Fill the roof   every panel that fits (and loses at most 40% to shade)
    neat  Neat blocks     only rectangles of at least 12 m2 of panels (6 panels of 420 W,
                          5 of 540 W), at least 2 panels wide in both directions,
                          made of panels producing at least 85% of the roof's best
    best  Best blocks     only rectangles of at least 16 m2 of panels (8 panels of 420 W,
                          6 of 540 W), at least 2 panels wide in both directions,
                          made of panels producing at least 93% of the roof's best

A block is judged the same whichever way it runs: 2 x 3 and 3 x 2 panels are the same
block, and a single row (1 x 8) is never a block. Its size is an area, not a panel count,
so a bigger 540 W panel needs fewer panels to make the same block. "The roof's best" is the 90th-percentile panel (so one
lucky panel doesn't set the bar). The areas, side lengths and the 85% / 93% cut-offs are
ASSUMPTIONS, chosen to look like real rooftop systems. They are not from a standard.
Change them in OPTIONS below.

How the blocks are found: the panels sit on a grid (rows along the building).
The code repeatedly takes the biggest rectangle of grid cells that are all
good panels, keeps it as one block, and removes it. It stops when no
rectangle is big enough. `classify` also says why each other panel was left out:
"weak" (below the cut-off) or "loose" (good, but not inside a big enough block).
"""
import numpy as np

OPTIONS = [
    {"id": "max", "name": "Fill the roof", "min_share": None, "min_area_m2": 0, "min_short": 1, "min_long": 1,
     "rule": "every panel that fits and loses at most 40% of its sun to shade"},
    {"id": "neat", "name": "Neat blocks", "min_share": 0.85, "min_area_m2": 12, "min_short": 2, "min_long": 2,
     "rule": "rectangles of at least 12 m² of panels, at least 2 panels wide both ways, "
             "each panel at least 85% of the roof's best"},
    {"id": "best", "name": "Best blocks", "min_share": 0.93, "min_area_m2": 16, "min_short": 2, "min_long": 2,
     "rule": "rectangles of at least 16 m² of panels, at least 2 panels wide both ways, "
             "each panel at least 93% of the roof's best"},
]
REFERENCE_PERCENTILE = 90   # "the roof's best panel" = this percentile of yearly kWh per panel
DEFAULT_PANEL_M2 = 1.76 * 1.13


def min_cells(option, panel_m2=DEFAULT_PANEL_M2):
    """Fewest panels that make the option's minimum block area (never fewer than its two side lengths allow)."""
    return max(option["min_short"] * option["min_long"] if option["min_area_m2"] else 1,
               int(round(option["min_area_m2"] / panel_m2)))


def largest_block(grid, min_short, min_long, min_panels):
    """Biggest all-True rectangle in a 2-D bool array whose shorter side is at least min_short,
    longer side at least min_long and area at least min_panels cells, whichever way it runs.
    Returns (r0, r1, c0, c1) inclusive-exclusive, or None."""
    n_rows, n_cols = grid.shape
    best, best_area = None, 0
    for r0 in range(n_rows):
        full = np.ones(n_cols, bool)
        for r1 in range(r0, n_rows):
            full &= grid[r1]
            if not full.any():
                break
            run = 0
            for c in range(n_cols + 1):
                if c < n_cols and full[c]:
                    run += 1
                    continue
                if run:
                    h = r1 - r0 + 1
                    area = h * run
                    if (min(h, run) >= min_short and max(h, run) >= min_long
                            and area >= min_panels and area > best_area):
                        best, best_area = (r0, r1 + 1, c - run, c), area
                run = 0
    return best


def blocks(cells, good, min_short, min_long, min_panels):
    """Split the good panels into neat rectangular blocks.

    cells: (row, col) of every panel; good: bool per panel. Returns a list of
    blocks, each a list of panel indices."""
    if not len(cells):
        return []
    cells = np.asarray(cells)
    rows, cols = cells[:, 0] - cells[:, 0].min(), cells[:, 1] - cells[:, 1].min()
    index = -np.ones((rows.max() + 1, cols.max() + 1), int)
    index[rows, cols] = np.arange(len(cells))
    grid = np.zeros(index.shape, bool)
    grid[rows[good], cols[good]] = True
    found = []
    while True:
        b = largest_block(grid, min_short, min_long, min_panels)
        if b is None:
            return found
        r0, r1, c0, c1 = b
        found.append(sorted(int(i) for i in index[r0:r1, c0:c1].ravel()))
        grid[r0:r1, c0:c1] = False


def classify(cells, yearly_kwh, option, panel_m2=DEFAULT_PANEL_M2):
    """Which panels an option keeps and why the others go.
    Returns (keep mask, number of blocks or None, weak mask): weak = below the option's
    cut-off; a panel that is neither kept nor weak is 'loose' (good, but in no big block)."""
    yearly_kwh = np.asarray(yearly_kwh, float)
    n = len(yearly_kwh)
    if option["min_share"] is None or n == 0:
        return np.ones(n, bool), None, np.zeros(n, bool)
    ref = np.percentile(yearly_kwh, REFERENCE_PERCENTILE)
    good = yearly_kwh >= option["min_share"] * ref
    keep = np.zeros(n, bool)
    found = blocks(cells, good, option["min_short"], option["min_long"], min_cells(option, panel_m2))
    for b in found:
        keep[b] = True
    return keep, len(found), ~good


def choose(cells, yearly_kwh, option, panel_m2=DEFAULT_PANEL_M2):
    """Which panels an option keeps. Returns (bool array, number of blocks)."""
    keep, n, _ = classify(cells, yearly_kwh, option, panel_m2)
    return keep, n


def all_options(cells, yearly_kwh, panel_m2=DEFAULT_PANEL_M2):
    """{option id: (keep mask, number of blocks, weak mask)} for every option in OPTIONS."""
    return {o["id"]: classify(cells, yearly_kwh, o, panel_m2) for o in OPTIONS}
