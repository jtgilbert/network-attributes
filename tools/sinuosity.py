import argparse
import geopandas as gpd


def add_sinuosity(network: str, crs_epsg: int):
    """

    :param network: path to a segmented drainage network layer
    :param crs_epsg: the epsg number of the network projection, or one to reproject the network to
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

    # create a list to store sinuosity values
    sin = []

    # iterate through each network segment, calculate slope and add to list
    for i in flowlines.index:
        # obtain the coordinates of the end points of each line segment
        seg_geom = flowlines.loc[i].geometry
        length = seg_geom.length

        x_coord1 = seg_geom.coords.xy[0][0]
        y_coord1 = seg_geom.coords.xy[1][0]
        x_coord2 = seg_geom.coords.xy[0][-1]
        y_coord2 = seg_geom.coords.xy[1][-1]

        dist = ((x_coord1-x_coord2)**2+(y_coord1-y_coord2)**2)**0.5
        sin_val = length/dist
        sin.append(sin_val)

    # add sinuosity values to network attribute table
    flowlines['Sinuosity'] = sin
    flowlines.to_file(network)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('network', help='path to a segmented drainage network layer', type=str)
    parser.add_argument('epsg', help='the epsg number of the network projection, or one to reproject the network to', type=int)
    args = parser.parse_args()

    add_sinuosity(args.network, args.epsg)


if __name__ == '__main__':
    main()
