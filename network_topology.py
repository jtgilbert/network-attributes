import argparse
import math
import rasterio
import geopandas as gpd
from shapely.geometry import Point
from rasterstats import zonal_stats


def network_topology(in_network: str, first_feature: int, dem:str):
    """

    :param in_network: path to a segmented drainage network layer
    :param first_feature: the feature ID (e.g., fid) to start with (upstream-most feature)
    :param dem: path to a dem
    :return:
    """

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
            'end_elev': e_elev,
            'length': geom.length
        }
        count += 1

    # get a list of all network chain start segments
    startcoords = [attrs['start_coords'] for seg, attrs in features.items()]
    endcoords = [attrs['end_coords'] for seg, attrs in features.items()]
    allcoords = startcoords + endcoords
    ff_coords = [x for x in allcoords if allcoords.count(x) == 1]
    s_ff_segs = [seg for seg, attrs in features.items() if attrs['start_coords'] in ff_coords]
    e_ff_segs = [seg for seg, attrs in features.items() if attrs['end_coords'] in ff_coords]
    minel = 1000000
    minseg = None
    for seg in e_ff_segs:
        if features[seg]['end_elev'] < minel:
            minel = features[seg]['end_elev']
            minseg = seg
    e_ff_segs.remove(minseg)
    starting_segs = s_ff_segs+e_ff_segs
    starting_segs.remove(first_feature)

    tot_links = []
    ff = first_feature

    # find links in each chain
    chain = 1
    while chain:
        chain_len = features[ff]['length']
        links = [ff]
        seg = features[ff]
        while seg:
            dsseg = None
            for segid, attrs in features.items():
                if attrs['start_coords'] == seg['end_coords']:
                    if segid not in tot_links:
                        links.append(segid)
                        chain_len += attrs['length']
                        tot_links.append(segid)
                        print(f'Adding segment {segid} to chain')
                        seg = features[segid]
                        dsseg = seg
                if attrs['end_coords'] == seg['end_coords']:
                    if attrs['end_elev']+(.01*dn.loc[segid].geometry.length) > attrs['start_elev']:  # janky fix to flatter reaches
                        if segid not in tot_links:
                            links.append(segid)
                            chain_len += attrs['length']
                            tot_links.append(segid)
                            print(f'Adding segment {segid} to chain')
                            tmp_st = attrs['end_coords']
                            tmp_end = attrs['start_coords']
                            features[segid]['start_coords'] = tmp_st
                            features[segid]['end_coords'] = tmp_end
                            seg = features[segid]
                            dsseg = seg
            if dsseg is None:
                # check that the end point isn't actually the start
                for segid, attrs in features.items():
                    if attrs['end_coords'] == seg['start_coords']:
                        if segid not in tot_links:
                            links.append(segid)
                            chain_len += attrs['length']
                            tot_links.append(segid)
                            print(f'Adding segment {segid} to chain')
                            tmp_st = attrs['end_coords']
                            tmp_end = attrs['start_coords']
                            features[segid]['start_coords'] = tmp_st
                            features[segid]['end_coords'] = tmp_end
                            seg = features[segid]
                            dsseg = seg
            if dsseg is None:
                seg = None
                topochains[chain] = {'segids': links, 'length': chain_len}
                if len(starting_segs) > 0:
                    chain += 1
                    ff = starting_segs[0]
                    starting_segs.remove(ff)
                else:
                    chain = None

    # get the attributes for each network segment
    maxlen = 0
    chain_sel = None
    chain_lab = 1
    for chainid, att in topochains.items():
        if att['length'] > maxlen:
            maxlen = att['length']
            chain_sel = chainid
    while chain_sel:
        denom = 10**(magnitude_order(len(topochains[chain_sel]['segids']))+1)
        if len(topochains[chain_sel]['segids']) == 1:
            for i, id in enumerate(topochains[chain_sel]['segids']):
                features[id].update({
                    'rid': chain_lab + (1/denom),
                    'rid_ds': None,
                    'rid_us': None,
                    'rid_us2': None
                })
        elif len(topochains[chain_sel]['segids']) == 2:
            for i, id in enumerate(topochains[chain_sel]['segids']):
                if i == 0:
                    features[id].update({
                        'rid': chain_lab + (1 / denom),
                        'rid_ds': chain_lab + (2 / denom),
                        'rid_us': None,
                        'rid_us2': None
                    })
                else:
                    features[id].update({
                        'rid': chain_lab + (2 / denom),
                        'rid_ds': None,
                        'rid_us': chain_lab + (1 / denom),
                        'rid_us2': None
                    })
        else:
            for i, id in enumerate(topochains[chain_sel]['segids']):
                if i == 0:  # if it's the first link in the chain
                    features[id].update({
                        'rid': chain_lab + (1/denom),
                        'rid_ds': chain_lab + (2/denom),
                        'rid_us': None,
                        'rid_us2': None
                    })
                elif i == len(topochains[chain_sel]['segids'])-1:  # if it's the last link in the chain
                    features[id].update({
                        'rid': chain_lab + ((i + 1) / denom),
                        'rid_ds': None,
                        'rid_us': chain_lab + (i / denom),
                        'rid_us2': None
                    })
                else:  # if its any in between
                    features[id].update({
                        'rid': chain_lab + ((i+1)/denom),
                        'rid_ds': chain_lab + ((i+2)/denom),
                        'rid_us': chain_lab + (i/denom),
                        'rid_us2': None
                    })
        del topochains[chain_sel]
        if len(topochains) > 0:
            maxlen = 0
            chain_sel = None
            for chainid, att in topochains.items():
                if att['length'] > maxlen:
                    maxlen = att['length']
                    chain_sel = chainid
            chain_lab += 1
        else:
            chain_sel = None

    # now deal with confluences
    for segid, atts in features.items():
        if atts['rid_ds'] is None:
            ds_segs = []
            for s, a in features.items():
                if atts['end_coords'] == a['start_coords']:
                    ds_segs.append(s)
            if len(ds_segs) > 1:
                print(f'warning: there are two reaches downstream of segment {segid}')
            if len(ds_segs) != 0:  # if it's not the last segment
                features[segid]['rid_ds'] = features[ds_segs[0]]['rid']
        us_segs = []
        for s, a in features.items():
            if atts['start_coords'] == a['end_coords']:
                us_segs.append(s)
        if len(us_segs) > 2:
            print(f'warning: there are more than two reaches upstream of segment {segid}')
        if len(us_segs) == 2:
            if features[segid]['rid_us'] == features[us_segs[0]]['rid']:
                features[segid]['rid_us2'] = features[us_segs[1]]['rid']
            else:
                features[segid]['rid_us2'] = features[us_segs[0]]['rid']

    for i in dn.index:
        dn.loc[i, 'rid'] = features[i]['rid']
        dn.loc[i, 'rid_ds'] = features[i]['rid_ds']
        dn.loc[i, 'rid_us'] = features[i]['rid_us']
        dn.loc[i, 'rid_us2'] = features[i]['rid_us2']

    dn.to_file(in_network)


def magnitude_order(num):
    if num == 0:
        return 0

    absnum = abs(num)
    order = math.log10(absnum)
    res = math.floor(order)

    return res


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('network', help='Path to a segmented stream network layer.', type=str)
    parser.add_argument('first_feature', help='The feature ID of the reach topology should start with.', type=int)
    parser.add_argument('dem', help='Path to a DEM.', type=str)
    args = parser.parse_args()

    network_topology(args.network, args.first_feature, args.dem)


if __name__ == '__main__':
    main()


# network = '/media/jordan/Elements/Geoscience/Bitterroot/lidar/blodgett/Blodgett_network_split200.shp'
# ff = 207
# indem = '/media/jordan/Elements/Geoscience/Bitterroot/lidar/blodgett/Blodgett_DEM_2m.tif'

# network_topology(network, ff, indem)
