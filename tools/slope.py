import argparse
import geopandas as gpd
from shapely.geometry import Point
from rasterstats import zonal_stats


def add_slope(network: str, dem: str, crs_epsg: int, search_dist: float):
    """

    :param network: path to a segmented drainage network layer
    :param dem: path to a dem
    :param crs_epsg: epsg of the input datasets or one to project them into
    :param search_dist: a buffer distance in stream network input units to search for elevation values (accounts for
    positional error between the network and the dem
    :return:
    """

    # convert epsg number into crs dict
    sref = 'epsg:{}'.format(crs_epsg)

    # read in network and check for projection
    flowlines = gpd.read_file(network)
    if flowlines['geometry'].crs == sref:
        pass
    else:
        flowlines = flowlines.to_crs(sref)

    # create a list to store slope values
    slope = []

    # iterate through each network segment, calculate slope and add to list
    for i in flowlines.index:
        # obtain the coordinates of the end points of each line segment
        seg_geom = flowlines.loc[i].geometry
        length = seg_geom.length

        x_coord1 = seg_geom.coords.xy[0][0]
        y_coord1 = seg_geom.coords.xy[1][0]
        x_coord2 = seg_geom.coords.xy[0][-1]
        y_coord2 = seg_geom.coords.xy[1][-1]

        # create points at the line end points
        pt1 = Point(x_coord1, y_coord1)
        pt2 = Point(x_coord2, y_coord2)

        # buffer the points to account for positional discrepancy between DEM and network
        buf1 = pt1.buffer(search_dist)
        buf2 = pt2.buffer(search_dist)

        # obtain elevation values within the buffers
        zs1 = zonal_stats(buf1, dem, stats='min')
        zs2 = zonal_stats(buf2, dem, stats='min')
        elev1 = zs1[0].get('min')
        elev2 = zs2[0].get('min')

        # calculate the slope of each reach and append it to the list
        slope_value = abs(elev1-elev2)/length

        slope.append(slope_value)

    # add slope values to network attribute table
    flowlines['Slope'] = slope

    flowlines.to_file(network)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('network', help='Path to a segmented drainage network layer.', type=str)
    parser.add_argument('dem', help='Path to a DEM.', type=str)
    parser.add_argument('epsg', help='The EPSG number of the projection of the input datasets, or one to project'
                                     'the datasets into', type=int)
    parser.add_argument('search_dist', help='A buffer distance from the network to search for elevation values (to'
                                            'account for positional error between the network and the dem.', type=float)
    args = parser.parse_args()

    add_slope(args.network, args.dem, args.epsg, args.search_dist)


if __name__ == '__main__':
    main()
