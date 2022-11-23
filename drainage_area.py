import argparse
import geopandas as gpd
from shapely.geometry import Point
from rasterstats import zonal_stats


def add_da(network: str, da: str, crs_epsg: str, search_dist: str):
    """

    :param network: path to segmented stream network shapefile
    :param da: path to drainage area raster
    :param crs_epsg: the epsg number for the dataset projections
    :param search_dist: a buffer distance to search for drainage area values away from network segments to
    account for positional error between the raster and drainage network
    :return: adds the field 'Drain_Area' to the stream network
    """

    # convert epsg number into crs dict
    sref = {'init': 'epsg:{}'.format(crs_epsg)}

    # read in network and check for projection
    flowlines = gpd.read_file(network)
    if flowlines['geometry'].crs == sref:
        pass
    else:
        flowlines = flowlines.to_crs(sref)

    # list to store da values
    da_list = []

    # iterate through each network segment, obtain da value and add to list
    for i in flowlines.index:
        # find and buffer segment midpoint to account for positional inaccuracy between da raster and network
        seg_geom = flowlines.loc[i, 'geometry']
        pos = int(len(seg_geom.coords.xy[0])/2)
        mid_pt_x = seg_geom.coords.xy[0][pos]
        mid_pt_y = seg_geom.coords.xy[1][pos]

        pt = Point(mid_pt_x, mid_pt_y)
        buf = pt.buffer(search_dist)

        # get max drainage area value within buffered midpoint
        zs = zonal_stats(buf, da, stats='max')
        da_value = zs[0].get('max')

        da_list.append(da_value)

    # add da values to network attribute table
    flowlines['Drain_Area'] = da_list


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('network', help='Path to a segmented stream network layer.', type=str)
    parser.add_argument('drainage_area', help='Path to a drainage area raster.', type=str)
    parser.add_argument('EPSG', help='An epsg number for a coordinate reference system.', type=int)
    parser.add_argument('buffer_distance', help='A buffer distance to search away from the network segment for a max'
                                                'drainage area value (to account for positional error between the raster'
                                                'and the network.', type=float)
    args = parser.parse_args()

    add_da(args.network, args.drainage_area, args.EPSG, args.buffer_distance)


if __name__ == '__main__':
    main()
