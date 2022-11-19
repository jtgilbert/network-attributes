import geopandas as gpd
from shapely.geometry import Point
from rasterstats import zonal_stats


def add_slope(network, dem, crs_epsg, search_dist):

    # convert epsg number into crs dict
    sref = {'init': 'epsg:{}'.format(crs_epsg)}

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
        seg_geom = flowlines.loc[i, 'geometry']
        length = seg_geom.length

        x_coord1 = seg_geom.boundary[0].xy[0][0]
        y_coord1 = seg_geom.boundary[0].xy[1][0]
        x_coord2 = seg_geom.boundary[1].xy[0][0]
        y_coord2 = seg_geom.boundary[1].xy[1][0]

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
        slope_value = elev1-elev2/length

        slope.append(slope_value)

    # add slope values to network attribute table
    flowlines['Slope'] = slope

    flowlines.to_file(network)
