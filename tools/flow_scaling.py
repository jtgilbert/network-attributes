import argparse
import os
import rasterio
from rasterio.features import shapes
from rasterio.mask import mask
from rasterio.warp import reproject, Resampling, calculate_default_transform
import numpy as np
import geopandas as gpd
from pysheds.grid import Grid


def get_flow_scaling_factor(network: str, meas_id: int, dem: str, precip_raster: str, reproject: bool=False):
    """

    :param network: path to a segment stream network layer
    :param meas_id: the reach id (e.g. fid) where this discharge record applies
    :param dem: path to a 10m DEM. This should not be LiDAR if available
    :param precip_raster: path to a precipitation raster (e.g., PRISM)
    :param reproject: if True, rasters are reprojected to match the drainage network crs if needed
    :return: adds a field 'flow_scale' to the drainage network for scaling discharge measurements across the network
    """

    dn = gpd.read_file(network)

    # check for projection consistency
    if dn.crs.is_projected is False:
        raise Exception('Input drainage network should have a projected CRS')

    # check that precip raster resolution and segment length work together...

    # set the measurement segment value as 1
    dn.loc[meas_id, 'flow_scale'] = 1.

    # get the coords of the midpoint of the measurement segment
    seg_geom = dn.loc[meas_id].geometry
    pos = int(len(seg_geom.coords.xy[0]) / 2)
    mid_pt_x = seg_geom.coords.xy[0][pos]
    mid_pt_y = seg_geom.coords.xy[1][pos]

    # open and check projection of dem
    with rasterio.open(dem) as demsrc:
        if demsrc.crs != dn.crs:
            if reproject is False:
                raise Exception('DEM must have same projection as drainage network')
            else:
                print('reprojecting DEM')
                reproject_raster(dem, dn.crs, os.path.join(os.path.dirname(dem), 'DEM_reprojected.tif'))
                demsrc = rasterio.open(os.path.join(os.path.dirname(dem), 'DEM_reprojected.tif'))
                transform = demsrc.transform
                dem = os.path.join(os.path.dirname(dem), 'DEM_reprojected.tif')
        else:
            transform = demsrc.transform

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
        if src.crs != dn.crs:
            if reproject is False:
                raise Exception('Precip raster must have same projection as drainage network')
            else:
                print('reprojecting precip raster')
                reproject_raster(precip_raster, dn.crs, os.path.join(os.path.dirname(precip_raster), 'precip_reprojected.tif'))
                precip_raster = os.path.join(os.path.dirname(precip_raster), 'precip_reprojected.tif')
                src = rasterio.open(precip_raster)
                out_image, out_transform = mask(src, shps, crop=True)
        else:
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


def reproject_raster(in_raster, dst_crs, out_raster):

    with rasterio.open(in_raster) as src:
        src_transform = src.transform

        # calculate the transform matrix for the output
        dst_transform, width, height = calculate_default_transform(
            src.crs,
            dst_crs,
            src.width,
            src.height,
            *src.bounds,  # unpacks outer boundaries (left, bottom, right, top)
        )

        # set properties for output
        dst_kwargs = src.meta.copy()
        dst_kwargs.update(
            {
                "crs": dst_crs,
                "transform": dst_transform,
                "width": width,
                "height": height,
                "nodata": src.nodata,  # replace 0 with np.nan
            }
        )

        with rasterio.open(out_raster, "w", **dst_kwargs) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=dst_transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.cubic,
                )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('network', help='Path to a segmented stream network layer.', type=str)
    parser.add_argument('measurement_reach', help='The reach ID (e.g., fid) of the reach for which a discharge record'
                                                  'applies.', type=int)
    parser.add_argument('dem', help='Path to a 10m DEM. This should be coarse, not LiDAR.', type=str)
    parser.add_argument('precipitation', help='Path to a precipitation raster (e.g., PRISM).', type=str)
    parser.add_argument('--reproject', help='if True, rasters are reprojected to match the drainage network crs '
                                            'if needed', type=bool, default=False)
    args = parser.parse_args()

    get_flow_scaling_factor(args.network, args.measurement_reach, args.dem, args.precipitation, args.reproject)


if __name__ == '__main__':
    main()
