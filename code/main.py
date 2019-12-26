import json
import urllib.request
from pathlib import Path
from urllib.request import urlretrieve

import click
import geopandas as gpd
import requests

from geom import get_tile_indices, switch_xyz_tms

style_json = 'https://raw.githubusercontent.com/nst-guide/osm-liberty-topo/gh-pages/style.json'
style_json = '/Users/kyle/github/mapping/nst-guide/osm-liberty-topo/style.json'
geometry = '/Users/kyle/github/mapping/nst-guide/create-database/data/pct/line/halfmile/CA_Sec_A_tracks.geojson'
buffer_dist = 1
min_zoom = 0
max_zoom = 7
out = 'tiles'


@click.command()
@click.option(
    '-s'
    '--style-json',
    required=True,
    type=str,
    help='Path to style JSON. Can be local or remote file.')
# Maybe switch this to argument in the future
@click.option(
    '-g'
    '--geometry',
    required=True,
    type=click.Path(
        exists=True, file_okay=True, dir_okay=False, resolve_path=True),
    help='Path to vector geometry for finding tile intersections.')
@click.option(
    '-b'
    '--buffer-dist',
    required=True,
    type=float,
    help='Distance to use for buffer around provided geometries.')
@click.option(
    '-l'
    '--layer',
    required=False,
    multiple=True,
    type=str,
    help='Package only selected layers from style JSON')
@click.option(
    '-z'
    '--min-zoom', required=True, type=int, help='Minimum zoom to package.')
@click.option(
    '-Z'
    '--max-zoom', required=True, type=int, help='Maximum zoom to package')
@click.option(
    '--shave/--no-shave',
    default=False,
    help=
    'Whether to apply @mapbox/vtshaver on vector tiles. Must be available on PATH.'
)
@click.option(
    '-o'
    '--out',
    required=True,
    type=click.Path(exists=False, resolve_path=True),
    help='Output folder. Folder must not already exist.')
@click.option(
    '--modify-paths/--no-modify-paths',
    is_flag=True,
    default=True,
    help='Modify paths in style JSON to be relative to offline download.')
@click.option(
    '--rate-limit',
    type=float,
    default=None,
    help='Rate limit to use for downloading tiles.')
def main(
        style_json, geometry, buffer_dist, layer, min_zoom, max_zoom, shave,
        out, modify_paths, rate_limit):
    """Package tiles from Style JSON for offline use.
    """
    # Load style JSON
    if style_json.startswith('http'):
        r = requests.get(style_json)
        style = r.json()
    else:
        with Path(style_json).resolve().open() as f:
            style = json.load(f)

    # Make sure layers exist as source in style json
    sources = style['sources']
    msg = 'Not all layers exist as keys of sources in style JSON'
    assert all(l in sources.keys() for l in layer), msg

    # Load Geometry
    gdf = gpd.read_file(geometry)
    tile_indices = get_tile_indices(
        gdf,
        min_zoom=min_zoom,
        max_zoom=max_zoom,
        scheme='xyz',
        buffer_dist=buffer_dist)

    # Download map tiles for each tile_indices
    out_dir = Path(out).resolve()
    out_dir.mkdir(parents=True)
    for name, d in sources.items():
        # Parse source info
        info = parse_source(d)

        # Get minzoom and maxzoom for source and intersect with overall min/max
        # zoom
        _min_zoom = min_zoom
        if info.get('minzoom') > _min_zoom:
            _min_zoom = info.get('minzoom')

        _max_zoom = max_zoom
        if info.get('maxzoom') < _max_zoom:
            _max_zoom = info.get('maxzoom')

        # If zooms exist, create folder in out_dir and download tiles
        if not bool(range(_min_zoom, _max_zoom + 1)):
            continue

        # Create folder
        _out_dir = out_dir / info['name']
        _out_dir.mkdir()

        # If scheme is tms, switch tile_indices
        _tile_indices = tile_indices.copy()
        if info.get('scheme') == 'tms':
            _tile_indices = [switch_xyz_tms(*x) for x in _tile_indices]

        # Make necessary z/x folders
        new_dirs = {(x[2], x[0]) for x in _tile_indices}
        for z, x in new_dirs:
            (_out_dir / str(z) / str(x)).mkdir(parents=True, exist_ok=True)

        # Download to folders
        # Apparently S3 rejects the standard User-Agent sent by urlretrieve,
        # even though it works for wget, requests, and Chrome, so I set a custom
        # User-Agent for urlretrieve
        # This solution is from https://stackoverflow.com/a/36663971
        opener = urllib.request.build_opener()
        opener.addheaders = [(
            'User-Agent',
            'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/36.0.1941.0 Safari/537.36'
        )]
        urllib.request.install_opener(opener)
        for x, y, z in _tile_indices:
            url = info['tiles'][0].format(x=x, y=y, z=z)
            local_path = _out_dir / str(z) / str(x) / Path(url).name
            try:
                urlretrieve(url, local_path)
            except urllib.error.HTTPError:
                pass

        # If `url` key exists, download tile JSON file to folder


def parse_source(d):
    """Parse source from style JSON sources
    """
    if d.get('url') is not None:
        r = requests.get(d['url'])
        tile_json = r.json()
        d = {**d, **tile_json}

    return d


if __name__ == '__main__':
    main()
