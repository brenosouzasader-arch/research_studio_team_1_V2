"""Every cadastral plot in a square around a point, from Catastro's INSPIRE parcels service.

Taken from V1's roof_test_set.py (which then grouped the plots into the 9 Eixample blocks).
Here it is kept general so any test site works. Used by step 06 to find nearby buildings.
"""
import xml.etree.ElementTree as ET

import requests
from shapely.geometry import Point
from shapely.ops import unary_union

from .catastro import CatastroError, _first_text, _local, _polygons

WFS_CP_URL = "https://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx"
TILE_M = 550
TIMEOUT = 60


def parse_parcels(gml_text):
    """Parse a CadastralParcel WFS reply into [{refcat, area_m2, point, geometry}]."""
    root = ET.fromstring(gml_text)
    out = []
    for p in root.iter():
        if _local(p.tag) != "CadastralParcel":
            continue
        ref = _first_text(p, "nationalCadastralReference") or _first_text(p, "localId")
        geom_elem = next((e for e in p.iter() if _local(e.tag) == "geometry"), p)
        polys = _polygons(geom_elem)
        if not ref or not polys:
            continue
        geom = unary_union(polys)
        point = None
        for e in p.iter():
            if _local(e.tag) == "referencePoint":
                pos = _first_text(e, "pos")
                if pos:
                    x, y = (float(v) for v in pos.split()[:2])
                    point = Point(x, y)
        if point is None or not geom.contains(point):
            point = geom.representative_point()
        area = _first_text(p, "areaValue")
        out.append({"refcat": ref[:14], "area_m2": float(area) if area else round(geom.area, 1),
                    "point": point, "geometry": geom})
    return out


def download_parcels(cx, cy, half=TILE_M):
    """All plots in a square around (cx, cy), fetched as 4 tiles to stay under Catastro's limits."""
    found = {}
    for x0 in (cx - half, cx):
        for y0 in (cy - half, cy):
            params = {"service": "wfs", "version": "2.0.0", "request": "GetFeature",
                      "typeNames": "CP:CadastralParcel", "srsName": "EPSG::25831",
                      "bbox": f"{x0:.0f},{y0:.0f},{x0 + half:.0f},{y0 + half:.0f}"}
            r = requests.get(WFS_CP_URL, params=params, timeout=TIMEOUT)
            r.raise_for_status()
            if "ExceptionReport" in r.text[:2000]:
                raise CatastroError(f"Catastro parcels WFS error: {r.text[:300]}")
            for p in parse_parcels(r.text):
                found.setdefault(p["refcat"], p)
    return list(found.values())
