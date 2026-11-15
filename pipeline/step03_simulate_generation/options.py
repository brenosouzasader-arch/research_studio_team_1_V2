"""Three panel layouts for one roof, from most panels to neatest and best.

Real installers build neat rectangular blocks of panels on the best part of a
roof. They leave out single panels in corners, ragged row ends and shaded spots.
On the CEP9 school, the real system is about 110 panels in tidy rows. Our "fill
the roof" layout also puts about 85 scattered panels on the cluttered south roof.

So step 03 gives the user three options to choose from:

    max   Fill the roof   every panel that fits (and loses at most 40% to shade)
    neat  Neat blocks     only rectangles of at least 6 panels, 3 or more per row,
                          made of panels producing at least 85% of the roof's best
    best  Best blocks     only rectangles of at least 8 panels, 4 or more per row,
                          made of panels producing at least 93% of the roof's best

"The roof's best" is the 90th-percentile panel (so one lucky panel doesn't set
the bar). The block sizes and the 85% / 93% cut-offs are ASSUMPTIONS, chosen
to look like real rooftop systems. They are not from a standard. On the CEP9
school (first test, 15 Nov 2026) they give about 200 / 130 / 50 panels of
420 W; the real system has 108 panels of 540 W. Change them in OPTIONS below.

How the blocks are found: the panels sit on a grid (rows along the building).
The code repeatedly takes the biggest rectangle of grid cells that are all
good panels, keeps it as one block, and removes it. It stops when no
rectangle is big enough.
"""
import numpy as np

OPTIONS = [
    {"id": "max", "name": "Fill the roof", "min_share": None, "min_panels": 1, "min_row": 1,
     "rule": "every panel that fits and loses at most 40% of its sun to shade"},
    {"id": "neat", "name": "Neat blocks", "min_share": 0.85, "min_panels": 6, "min_row": 3,
     "rule": "rectangles of 6+ panels (3+ per row), each panel at least 85% of the roof's best"},
    {"id": "best", "name": "Best blocks", "min_share": 0.93, "min_panels": 8, "min_row": 4,
     "rule": "rectangles of 8+ panels (4+ per row), each panel at least 93% of the roof's best"},
]
REFERENCE_PERCENTILE = 90   # "the roof's best panel" = this percentile of yearly kWh per panel


def largest_block(grid, min_row, min_panels):
    """Biggest all-True rectangle in a 2-D bool array with at least min_row columns and
    min_panels cells. Returns (r0, r1, c0, c1) inclusive-exclusive, or None."""
    n_rows, n_cols = grid.shape
    best, best_area = None, 0
    for r0 in range(n_rows):
        full = np.ones(n_cols, bool)
        for r1 in range(r0, n_rows):
            full &= grid[r1]
            if not full.any():
                break
            # longest run of True columns in `full`
            run, start = 0, 0
            for c in range(n_cols + 1):
                if c < n_cols and full[c]:
                    run += 1
                    continue
                if run:
                    h = r1 - r0 + 1
                    area = h * run
                    if run >= min_row and area >= min_panels and area > best_area:
                        best, best_area = (r0, r1 + 1, c - run, c), area
                run = 0
    return best


def blocks(cells, good, min_row, min_panels):
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
        b = largest_block(grid, min_row, min_panels)
        if b is None:
            return found
        r0, r1, c0, c1 = b
        found.append(sorted(int(i) for i in index[r0:r1, c0:c1].ravel()))
        grid[r0:r1, c0:c1] = False


def choose(cells, yearly_kwh, option):
    """Which panels an option keeps. Returns (bool array, number of blocks)."""
    yearly_kwh = np.asarray(yearly_kwh, float)
    n = len(yearly_kwh)
    if option["min_share"] is None or n == 0:
        return np.ones(n, bool), None
    ref = np.percentile(yearly_kwh, REFERENCE_PERCENTILE)
    good = yearly_kwh >= option["min_share"] * ref
    keep = np.zeros(n, bool)
    found = blocks(cells, good, option["min_row"], option["min_panels"])
    for b in found:
        keep[b] = True
    return keep, len(found)


def all_options(cells, yearly_kwh):
    """{option id: (keep mask, number of blocks)} for every option in OPTIONS."""
    return {o["id"]: choose(cells, yearly_kwh, o) for o in OPTIONS}
