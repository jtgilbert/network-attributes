import rasterio
import geopandas as gpd
from shapely.geometry import Point
from rasterstats import zonal_stats


def network_topology(in_network, first_feature, dem):

    features = {}
    topochains = {}

    with rasterio.open(dem) as src:
        if not src.crs.is_projected:
            raise Exception('DEM does not have a projected coordinate system')
        resolution = abs(src.transform[0])

    dn = gpd.read_file(in_network)
    count = 1
    for i in dn.index:
        print(f'Adding feature {count} of {len(dn)} to dictionary')
        geom = dn.loc[i].geometry
        s_coords = [geom.coords.xy[0][0], geom.coords.xy[1][0]]
        e_coords = [geom.coords.xy[0][-1], geom.coords.xy[1][-1]]
        spt = Point(s_coords[0], s_coords[1]).buffer(resolution*4)
        ept = Point(e_coords[0], e_coords[1]).buffer(resolution*4)
        s_elev = zonal_stats(spt, dem)[0].get('min')
        e_elev = zonal_stats(ept, dem)[0].get('min')

        features[i] = {
            'start_coords': s_coords,
            'end_coords': e_coords,
            'start_elev': s_elev,
            'end_elev': e_elev
        }
        count += 1

    chain = 1
    links = [first_feature]
    seg = features[first_feature]
    while seg:
        dsseg = None
        for segid, attrs in features.items():
            if attrs['start_coords'] == seg['end_coords']:
                if segid not in links:
                    links.append(segid)
                    print(f'Adding segment {segid} to chain')
                    seg = features[segid]
                    dsseg = seg
            if attrs['end_coords'] == seg['end_coords']:
                if attrs['end_elev']+(.01*dn.loc[segid].geometry.length) > attrs['start_elev']:  # janky fix to flatter reaches
                    if segid not in links:
                        links.append(segid)
                        print(f'Adding segment {segid} to chain')
                        tmp_st = attrs['end_coords']
                        tmp_end = attrs['start_coords']
                        features[segid]['start_coords'] = tmp_st
                        features[segid]['end_coords'] = tmp_end
                        seg = features[segid]
                        dsseg = seg
        if dsseg is None:
            seg = None
            topochains[chain] = links
            


    s_feat = dn.loc[first_feature]


network = '/media/jordan/Elements/Geoscience/Bitterroot/lidar/blodgett/Blodgett_network_split200.shp'
ff = 207
indem = '/media/jordan/Elements/Geoscience/Bitterroot/lidar/blodgett/Blodgett_DEM_2m.tif'

network_topology(network, ff, indem)
