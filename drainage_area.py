import geopandas as gpd
from shapely.geometry import Point
from rasterstats import zonal_stats


def add_da(network, da, crs_epsg, search_dist):

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
