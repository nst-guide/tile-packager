import json
from subprocess import run
from typing import List, Tuple

import geopandas as gpd
import pint
from shapely.geometry import Polygon, mapping
from shapely.ops import transform

ureg = pint.UnitRegistry()

def get_tile_indices(gdf, min_zoom, max_zoom, scheme, buffer_dist=None):
    """Generate tile indices

    Note that supermercado only currently supports polygon types,

    """
    if buffer_dist is not None:
        polygon = buffer(gdf, distance=buffer_dist, unit='mile').unary_union
    else:
        polygon = gdf.unary_union

    zooms = range(min_zoom, max_zoom + 1)
    return tiles_for_geometry(polygon, zoom_levels=zooms, scheme=scheme)


def tiles_for_geometry(polygon: Polygon, zoom_levels,
                       scheme='xyz') -> List[Tuple[int]]:
    """Generate x,y,z tile tuples for polygon

    Args:
        - polygon: polygon to generate tiles for
        - zoom_levels: iterable with integers for zoom levels
        - scheme: scheme of output tuples, either "xyz" or "tms"
    """
    if scheme not in ['xyz', 'tms']:
        raise ValueError('scheme must be "xyz" or "tms"')

    # Coerce to 2D GeoJSON; supermercado gets upset with 3D coordinates
    stdin = json.dumps(mapping(to_2d(polygon)))

    tile_tuples = []
    for zoom_level in zoom_levels:
        cmd = ['supermercado', 'burn', str(zoom_level)]
        r = run(
            cmd, capture_output=True, input=stdin, check=True, encoding='utf-8')
        tile_tuples.extend([
            json.loads(line) for line in r.stdout.strip().split('\n')])

    if scheme == 'tms':
        tile_tuples = [xyz_to_tms(x, y, z) for x, y, z in tile_tuples]

    return tile_tuples


def switch_xyz_tms(x, y, z):
    """Switch between xyz and tms coordinates

    https://gist.github.com/tmcw/4954720
    """
    y = (2 ** z) - y - 1
    return x, y, z


def xyz_to_tms(x, y, z):
    return switch_xyz_tms(x, y, z)


def tms_to_xyz(x, y, z):
    return switch_xyz_tms(x, y, z)


def to_2d(obj):
    """Convert geometric object from 3D to 2D"""
    if isinstance(obj, gpd.GeoDataFrame):
        return _to_2d_gdf(obj)

    try:
        return transform(_to_2d_transform, obj)
    except TypeError:
        # Means already 2D
        return obj


def _to_2d_gdf(obj):
    # Get geometry column
    geometry = obj.geometry

    # Replace geometry column with 2D coords
    geometry_name = obj.geometry.name
    try:
        obj[geometry_name] = geometry.apply(
            lambda g: transform(_to_2d_transform, g))
    except TypeError:
        # Means geometry is already 2D
        pass

    return obj


def _to_2d_transform(x, y, z):
    return tuple(filter(None, [x, y]))


def buffer(gdf: gpd.GeoDataFrame, distance: float, unit: str) -> gpd.GeoSeries:
    """Create buffer around GeoDataFrame

    Args:
        gdf: dataframe with geometry to take buffer around
        distance: distance for buffer
        unit: units for buffer distance, either ['mile', 'meter', 'kilometer']

    Returns:
        GeoDataFrame with buffer polygon
    """

    # Reproject to EPSG 3488 (meter accuracy)
    # https://epsg.io/3488
    gdf = gdf.to_crs(epsg=3488)

    # Find buffer distance in meters
    unit_dict = {
        'mile': ureg.mile,
        'meter': ureg.meter,
        'kilometer': ureg.kilometer, }
    pint_unit = unit_dict.get(unit)
    if pint_unit is None:
        raise ValueError(f'unit must be one of {list(unit_dict.keys())}')

    distance_m = (distance * pint_unit).to(ureg.meters).magnitude
    buffer = gdf.buffer(distance_m)

    # Reproject back to EPSG 4326 for saving
    buffer = buffer.to_crs(epsg=4326)

    return buffer
