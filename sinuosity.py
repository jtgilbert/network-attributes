import geopandas as gpd


def add_sinuosity(network, dem, crs_epsg):

    # convert epsg number into crs dict
    sref = {'init': 'epsg:{}'.format(crs_epsg)}

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
        seg_geom = flowlines.loc[i, 'geometry']
        length = seg_geom.length

        x_coord1 = seg_geom.boundary[0].xy[0][0]
        y_coord1 = seg_geom.boundary[0].xy[1][0]
        x_coord2 = seg_geom.boundary[1].xy[0][0]
        y_coord2 = seg_geom.boundary[1].xy[1][0]

        dist = ((x_coord1-x_coord2)**2+(y_coord1-y_coord2)**2)**0.5
        sin_val = length/dist
        sin.append(sin_val)

    # add sinuosity values to network attribute table
    flowlines['Sinuosity'] = sin
    flowlines.to_file(network)
