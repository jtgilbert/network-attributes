import argparse
import os
import rasterio
from rasterio.features import shapes
from rasterio.mask import mask
import numpy as np
import geopandas as gpd
from pysheds.grid import Grid


def get_flow_scaling_factor(network: str, meas_id: int, dem: str, precip_raster: str):
    """

    :param network: path to a segment stream network layer
    :param meas_id: the reach id (e.g. fid) where this discharge record applies
    :param dem: path to a DEM
    :param precip_raster: path to a precipitation raster (e.g., PRISM)
    :return: adds a field 'flow_scale' to the drainage network for scaling discharge measurements across the network
    """

    # check for projection consistency

    # check that precip raster resolution and segment length work together...

    # create scratch work folder to store temp files
    scratch = os.path.join(os.path.dirname(network), 'scratch')
    if not os.path.exists(scratch):
        os.mkdir(scratch)

    # open the stream network and set the measurement segment value as 1
    dn = gpd.read_file(network)
    dn.loc[meas_id, 'flow_scale'] = 1.

    # get the coords of the midpoint of the measurement segment
    seg_geom = dn.loc[meas_id].geometry
    pos = int(len(seg_geom.coords.xy[0]) / 2)
    mid_pt_x = seg_geom.coords.xy[0][pos]
    mid_pt_y = seg_geom.coords.xy[1][pos]

    # first delineate the watershed upstream of the measurement reach
    print('performing flow analysis on DEM')
    grid = Grid.from_raster(dem)
    griddem = grid.read_raster(dem)
    pit_filled_dem = grid.fill_pits(griddem)
    flooded_dem = grid.fill_depressions(pit_filled_dem)
    inflated_dem = grid.resolve_flats(flooded_dem)

    dirmap = (64, 128, 1, 2, 4, 8, 16, 32)
    fdir = grid.flowdir(inflated_dem, dirmap=dirmap)
    acc = grid.accumulation(fdir, dirmap=dirmap)

    print('delineating catchment upstream of measurement reach')
    x_snap, y_snap = grid.snap_to_mask(acc > 1000, (mid_pt_x, mid_pt_y))
    catch = grid.catchment(x=x_snap, y=y_snap, fdir=fdir, xytype='coordinate')

    catch_arr = np.where(catch, 1, np.nan).astype(np.int16)

    with rasterio.open(dem) as demsrc:
        transform = demsrc.transform
        crs = demsrc.crs

    results = (
        {'properties': {'raster_val': v}, 'geometry': s}
        for i, (s, v)
        in enumerate(
        shapes(catch_arr, mask=catch_arr == 1., transform=transform)))

    geoms = list(results)
    if len(geoms) == 0:
        raise Exception('no geoms')
    shps = [g['geometry'] for g in geoms]

    print('finding reference precip value')
    with rasterio.open(precip_raster) as src:
        out_image, out_transform = mask(src, shps, crop=True)

    precip_ref = 0
    for i in np.nditer(out_image):
        if i != src.nodata:
            precip_ref += i / (src.res[0]*src.res[1])

    print(f'reference precip: {precip_ref}')

    for i in dn.index:
        print(f'assessing reach {i}')
        grid = Grid.from_raster(dem)
        geom = dn.loc[i].geometry
        pos = int(len(geom.coords.xy[0]) / 2)
        x = geom.coords.xy[0][pos]
        y = geom.coords.xy[1][pos]
        x_snap, y_snap = grid.snap_to_mask(acc > 1000, (x, y))
        catch = grid.catchment(x=x_snap, y=y_snap, fdir=fdir, xytype='coordinate')

        catch_arr = np.where(catch, 1, np.nan).astype(np.int16)
        results = (
            {'properties': {'raster_val': v}, 'geometry': s}
            for i, (s, v)
            in enumerate(
            shapes(catch_arr, mask=catch_arr == 1., transform=transform)))

        geoms = list(results)
        if len(geoms) == 0:
            raise Exception('no geoms')
        shps = [g['geometry'] for g in geoms]

        with rasterio.open(precip_raster) as src:
            out_image, out_transform = mask(src, shps, crop=True)

        precip = 0
        for j in np.nditer(out_image):
            if j != src.nodata:
                precip += j / (src.res[0]*src.res[1])

        print(f'precip = {precip}')
        print(f'ratio = {precip/precip_ref}')
        dn.loc[i, 'flow_scale'] = precip/precip_ref

    dn.to_file(network)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('network', help='Path to a segmented stream network layer.', type=str)
    parser.add_argument('measurement_reach', help='The reach ID (e.g., fid) of the reach for which a discharge record'
                                                  'applies.', type=int)
    parser.add_argument('dem', help='Path to a DEM.', type=str)
    parser.add_argument('precipitation', help='Path to a precipitation raster (e.g., PRISM).', type=str)
    args = parser.parse_args()

    get_flow_scaling_factor(args.network, args.measurement_reach, args.dem, args.precipitation)


if __name__ == '__main__':
    main()


# in_network = '/media/jordan/Elements/Geoscience/Bitterroot/Blodgett/GIS/Blodgett_network.shp'
# in_reach = 6
# in_dem = '/media/jordan/Elements/Geoscience/Bitterroot/Blodgett/GIS/Blodgett_DEM_10m.tif'
# in_precip = '/media/jordan/Elements/Geoscience/Bitterroot/Blodgett/GIS/precip_100m.tif'

# get_flow_scaling_factor(in_network, in_reach, in_dem, in_precip)


