"""Offline tests: parsing, geometry and LiDAR logic.

These do NOT call Catastro, ICGC or Nominatim. The sample replies below follow
the documented shape of those services but were written by hand, so the live
check is `smoke_test.py`, run from a laptop with internet access.
"""
import json

import laspy
import numpy as np
from shapely.geometry import Point, box

from step01_select_host import catastro, find_building, heritage, lidar

RCCOOR_SAMPLE = {
    "Consulta_RCCOORResult": {
        "control": {"cucoor": 1},
        "coordenadas": {"coord": [{
            "pc": {"pc1": "0123456", "pc2": "DF3802C"},
            "geo": {"xcen": "2.1689", "ycen": "41.3935", "srs": "EPSG:4326"},
            "ldt": "CL GIRONA 81 BARCELONA (BARCELONA)",
        }]},
    }
}

# Building footprint: a 20 x 15 m rectangle in EPSG:25831
X0, Y0 = 430100.0, 4582300.0
RING = f"{X0} {Y0} {X0+20} {Y0} {X0+20} {Y0+15} {X0} {Y0+15} {X0} {Y0}"

BU_SAMPLE = f"""<?xml version="1.0" encoding="UTF-8"?>
<gml:FeatureCollection xmlns:gml="http://www.opengis.net/gml/3.2"
  xmlns:bu-core2d="http://inspire.jrc.ec.europa.eu/schemas/bu-core2d/2.0"
  xmlns:bu-ext2d="http://inspire.jrc.ec.europa.eu/schemas/bu-ext2d/2.0"
  xmlns:base="urn:x-inspire:specification:gmlas:BaseTypes:3.2">
 <gml:featureMember>
  <bu-ext2d:Building gml:id="ES.SDGC.BU.0123456DF3802C">
   <bu-core2d:inspireId><base:Identifier><base:localId>0123456DF3802C</base:localId></base:Identifier></bu-core2d:inspireId>
   <bu-core2d:conditionOfConstruction>functional</bu-core2d:conditionOfConstruction>
   <bu-core2d:dateOfConstruction><bu-core2d:DateOfEvent>
     <bu-core2d:beginning>1902-01-01T00:00:00</bu-core2d:beginning>
     <bu-core2d:end>1902-01-01T00:00:00</bu-core2d:end>
   </bu-core2d:DateOfEvent></bu-core2d:dateOfConstruction>
   <bu-ext2d:geometry><bu-core2d:BuildingGeometry><bu-core2d:geometry>
     <gml:Surface><gml:patches><gml:PolygonPatch>
      <gml:exterior><gml:LinearRing><gml:posList>{RING}</gml:posList></gml:LinearRing></gml:exterior>
     </gml:PolygonPatch></gml:patches></gml:Surface>
   </bu-core2d:geometry></bu-core2d:BuildingGeometry></bu-ext2d:geometry>
   <bu-ext2d:currentUse>1_residential</bu-ext2d:currentUse>
   <bu-ext2d:numberOfBuildingUnits>14</bu-ext2d:numberOfBuildingUnits>
   <bu-ext2d:numberOfDwellings>12</bu-ext2d:numberOfDwellings>
  </bu-ext2d:Building>
 </gml:featureMember>
</gml:FeatureCollection>"""

PARTS_SAMPLE = f"""<?xml version="1.0" encoding="UTF-8"?>
<gml:FeatureCollection xmlns:gml="http://www.opengis.net/gml/3.2"
  xmlns:bu-ext2d="http://inspire.jrc.ec.europa.eu/schemas/bu-ext2d/2.0"
  xmlns:base="urn:x-inspire:specification:gmlas:BaseTypes:3.2">
 <gml:featureMember><bu-ext2d:BuildingPart>
  <base:localId>0123456DF3802C_part1</base:localId>
  <gml:Polygon><gml:exterior><gml:LinearRing><gml:posList>{RING}</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon>
  <bu-ext2d:numberOfFloorsAboveGround>6</bu-ext2d:numberOfFloorsAboveGround>
 </bu-ext2d:BuildingPart></gml:featureMember>
 <gml:featureMember><bu-ext2d:BuildingPart>
  <base:localId>0123456DF3802C_part2</base:localId>
  <gml:Polygon><gml:exterior><gml:LinearRing><gml:posList>{RING}</gml:posList></gml:LinearRing></gml:exterior></gml:Polygon>
  <bu-ext2d:numberOfFloorsAboveGround>7</bu-ext2d:numberOfFloorsAboveGround>
 </bu-ext2d:BuildingPart></gml:featureMember>
</gml:FeatureCollection>"""


def test_parse_rccoor():
    out = catastro.parse_rccoor(RCCOOR_SAMPLE)
    assert out["refcat"] == "0123456DF3802C" and len(out["refcat"]) == 14
    assert "GIRONA" in out["address"]


def test_parse_rccoor_error():
    bad = {"Consulta_RCCOORResult": {"control": {"cuerr": 1}, "lerr": [{"err": {"des": "No existe"}}]}}
    try:
        catastro.parse_rccoor(bad)
        assert False, "should raise"
    except catastro.CatastroError as e:
        assert "No existe" in str(e)


def test_parse_buildings_and_parts():
    [b] = catastro.parse_buildings(BU_SAMPLE)
    assert b["year_built"] == 1902 and b["dwellings"] == 12
    assert b["current_use"] == "1_residential"
    assert abs(b["footprint"].area - 300) < 1e-6
    parts = catastro.parse_building_parts(PARTS_SAMPLE)
    assert find_building.max_floors(parts, b["footprint"]) == 7


def _write_las(path, x, y, z, cls):
    header = laspy.LasHeader(point_format=3, version="1.4")
    header.offsets = [x.min(), y.min(), z.min()]
    header.scales = [0.01, 0.01, 0.01]
    las = laspy.LasData(header)
    las.x, las.y, las.z = x, y, z
    las.classification = np.full(len(x), cls, dtype=np.uint8)
    las.write(path)


def _roof_grid(step=0.25):
    xs, ys = np.meshgrid(np.arange(X0 + 0.1, X0 + 20, step), np.arange(Y0 + 0.1, Y0 + 15, step))
    return xs.ravel(), ys.ravel()


def test_flat_roof_with_stair_housing(tmp_path):
    x, y = _roof_grid()
    z = np.full_like(x, 25.0)  # flat roof at 25 m
    housing = (x > X0 + 2) & (x < X0 + 5) & (y > Y0 + 2) & (y < Y0 + 5)
    z[housing] = 27.8  # 3 x 3 m stair housing
    _write_las(tmp_path / "flat.laz", x, y, z, lidar.BUILDING_CLASS)
    fp = box(X0, Y0, X0 + 20, Y0 + 15)
    tiles = lidar.find_tiles(fp, tmp_path)
    assert [t.name for t in tiles] == ["flat.laz"]
    roof = lidar.roof_flatness(lidar.roof_points(fp, tiles))
    assert roof["is_flat"] is True and roof["flat_share"] > 0.85
    assert roof["roof_height_max"] == 27.8


def test_pitched_roof_is_not_flat(tmp_path):
    x, y = _roof_grid()
    z = 20 + 0.6 * np.abs(y - (Y0 + 7.5))  # ~31 degree gable
    _write_las(tmp_path / "pitched.las", x, y, z, lidar.BUILDING_CLASS)
    fp = box(X0, Y0, X0 + 20, Y0 + 15)
    roof = lidar.roof_flatness(lidar.roof_points(fp, lidar.find_tiles(fp, tmp_path)))
    assert roof["is_flat"] is False


def test_tile_outside_building_is_ignored(tmp_path):
    x, y = _roof_grid()
    _write_las(tmp_path / "far.laz", x + 5000, y, np.full_like(x, 10.0), 6)
    assert lidar.find_tiles(box(X0, Y0, X0 + 20, Y0 + 15), tmp_path) == []


def test_ground_points_are_not_roof(tmp_path):
    x, y = _roof_grid()
    _write_las(tmp_path / "ground.laz", x, y, np.full_like(x, 5.0), 2)  # class 2 = ground
    fp = box(X0, Y0, X0 + 20, Y0 + 15)
    roof = lidar.roof_flatness(lidar.roof_points(fp, lidar.find_tiles(fp, tmp_path)))
    assert roof["is_flat"] is None and roof["note"] == "too few building points"


def test_heritage_flag(tmp_path):
    fp = box(X0, Y0, X0 + 20, Y0 + 15)
    assert heritage.heritage_flag(fp, None) == (None, None)
    layer = {"type": "FeatureCollection", "features": [{
        "type": "Feature", "properties": {"name": "Casa test", "level": "B"},
        "geometry": {"type": "Polygon", "coordinates": [[
            [X0 - 1, Y0 - 1], [X0 + 21, Y0 - 1], [X0 + 21, Y0 + 16], [X0 - 1, Y0 + 16], [X0 - 1, Y0 - 1]]]},
    }]}
    path = tmp_path / "heritage.geojson"
    path.write_text(json.dumps(layer))
    protected = heritage.load_protected(path, source_crs="EPSG:25831")
    flag, props = heritage.heritage_flag(fp, protected)
    assert flag is True and props["level"] == "B"


def test_find_building_end_to_end_offline(tmp_path, monkeypatch):
    x, y = _roof_grid()
    _write_las(tmp_path / "flat.laz", x, y, np.full_like(x, 25.0), 6)
    monkeypatch.setattr(catastro, "refcat_from_point",
                        lambda lat, lon: catastro.parse_rccoor(RCCOOR_SAMPLE))
    monkeypatch.setattr(catastro, "buildings_for_refcat",
                        lambda ref: (catastro.parse_buildings(BU_SAMPLE),
                                     catastro.parse_building_parts(PARTS_SAMPLE)))
    record, fp = find_building.find_building(lat=41.39, lon=2.17, laz_dir=tmp_path)
    assert record.refcat == "0123456DF3802C"
    assert record.dwellings == 12 and record.building_height_m == 21.0
    assert record.flat_roof is True and record.lidar_tiles == ["flat.laz"]
    assert record.heritage_protected is None
    find_building.save_geojson(record, fp, tmp_path / "b.geojson")
    assert json.loads((tmp_path / "b.geojson").read_text())["features"][0]["properties"]["refcat"]


def test_sheet_without_building_class_uses_unclassified(tmp_path):
    """A roof split over two sheets, one of which (like ICGC 433584) has no class 6."""
    x, y = _roof_grid()
    z = np.full_like(x, 25.0)
    south = y < Y0 + 7.5
    _write_las(tmp_path / "a_classified.laz", x[south], y[south], z[south], lidar.BUILDING_CLASS)
    _write_las(tmp_path / "b_unclassified.laz", x[~south], y[~south], z[~south], lidar.UNCLASSIFIED)
    fp = box(X0, Y0, X0 + 20, Y0 + 15)
    pts = lidar.roof_points(fp, lidar.find_tiles(fp, tmp_path))
    assert len(pts) == len(x)  # both halves of the roof are read


def test_unclassified_points_ignored_when_sheet_has_buildings(tmp_path):
    x, y = _roof_grid()
    z = np.full_like(x, 25.0)
    cls = np.where(y < Y0 + 7.5, lidar.BUILDING_CLASS, lidar.UNCLASSIFIED).astype(np.uint8)
    header = laspy.LasHeader(point_format=3, version="1.4")
    header.offsets = [x.min(), y.min(), z.min()]
    header.scales = [0.01, 0.01, 0.01]
    las = laspy.LasData(header)
    las.x, las.y, las.z = x, y, z
    las.classification = cls
    las.write(tmp_path / "mixed.laz")
    fp = box(X0, Y0, X0 + 20, Y0 + 15)
    pts = lidar.roof_points(fp, lidar.find_tiles(fp, tmp_path))
    assert len(pts) == int((cls == lidar.BUILDING_CLASS).sum())


def _plot_with_building(tmp_path):
    """A 60 x 50 m plot: ground at 4 m everywhere, a 20 x 15 m block 12 m above it, a 2 m wall."""
    xs, ys = np.meshgrid(np.arange(X0 - 20, X0 + 40, 0.5), np.arange(Y0 - 20, Y0 + 30, 0.5))
    x, y = xs.ravel(), ys.ravel()
    in_block = (x >= X0) & (x < X0 + 20) & (y >= Y0) & (y < Y0 + 15)
    wall = (x >= X0 - 15) & (x < X0 - 14) & ~in_block
    z = np.where(in_block, 16.0, np.where(wall, 6.0, 4.0))
    _write_las(tmp_path / "ground.laz", x[~in_block & ~wall], y[~in_block & ~wall], z[~in_block & ~wall], 2)
    _write_las(tmp_path / "blocks.laz", x[in_block | wall], y[in_block | wall], z[in_block | wall], lidar.BUILDING_CLASS)
    return box(X0 - 20, Y0 - 20, X0 + 40, Y0 + 30)


def test_footprint_from_lidar_finds_the_block(tmp_path):
    plot = _plot_with_building(tmp_path)
    tiles = lidar.find_tiles(plot, tmp_path)
    fp, ground = lidar.footprint_from_lidar(plot, Point(X0 + 5, Y0 + 5), tiles)
    assert ground == 4.0
    assert abs(fp.area - 300) < 30  # 20 x 15 m; the low wall is left out
    assert fp.contains(Point(X0 + 10, Y0 + 7))


def test_find_building_falls_back_to_lidar(tmp_path, monkeypatch):
    plot = _plot_with_building(tmp_path)

    def no_building(ref):
        raise catastro.CatastroError("No building with a footprint found")

    monkeypatch.setattr(catastro, "refcat_from_point", lambda lat, lon: catastro.parse_rccoor(RCCOOR_SAMPLE))
    monkeypatch.setattr(catastro, "buildings_for_refcat", no_building)
    monkeypatch.setattr(find_building.parcels, "download_parcels",
                        lambda cx, cy, half: [{"refcat": "0123456DF3802C", "geometry": plot}])
    monkeypatch.setattr(find_building, "to_utm", lambda lon, lat: (X0 + 5, Y0 + 5))
    record, fp = find_building.find_building(lat=41.39, lon=2.17, laz_dir=tmp_path)
    assert record.footprint_source == "lidar"
    assert abs(record.footprint_area_m2 - 300) < 30
    assert record.year_built is None and any("LiDAR" in w for w in record.warnings)
