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
    sminel = 1000000
    sminseg = None
    for seg in s_ff_segs:
        if features[seg]['start_elev'] < sminel:
            sminel = features[seg]['start_elev']
            sminseg = seg
    if features[minseg]['end_elev'] < features[sminseg]['start_elev']:
        e_ff_segs.remove(minseg)
    else:
        s_ff_segs.remove(sminseg)
    starting_segs = s_ff_segs+e_ff_segs
    starting_segs.remove(first_feature)

    ff = first_feature
    tot_links = [ff]

    # find links in each chain
    chain = 1
    while chain:
        chain_len = features[ff]['length']
        links = [ff]
        seg = features[ff]
        while seg:
            dsseg = None
            candidates = []
            for segid, attrs in features.items():
                if attrs['start_coords'] == seg['end_coords']:
                    # put list of possible segs then preferentially choose the one that end elev < start elev.
                    if segid not in tot_links:
                        candidates.append([segid, 0])

                if attrs['end_coords'] == seg['end_coords']:
                    # if attrs['end_elev']+(.01*dn.loc[segid].geometry.length) > attrs['start_elev']:  # janky fix to flatter reaches
                    if segid not in tot_links:
                        candidates.append([segid, 1])

            if len(candidates) == 1:  # if there's only one option for downstream segments
                if candidates[0][0] not in tot_links:
                    links.append(candidates[0][0])
                    chain_len += features[candidates[0][0]]['length']
                    tot_links.append(candidates[0][0])
                    print(f'Adding segment {candidates[0][0]} to chain')
                    if candidates[0][1] == 1:
                        tmp_st = features[candidates[0][0]]['end_coords']
                        tmp_end = features[candidates[0][0]]['start_coords']
                        features[candidates[0][0]]['start_coords'] = tmp_st
                        features[candidates[0][0]]['end_coords'] = tmp_end
                    seg = features[candidates[0][0]]
                    dsseg = seg
            if len(candidates) > 1:  # if there's more than one option for downstream segments
                minel = 100000
                candid = None
                for id, status in candidates:
                    if min(features[id]['start_elev'], features[id]['end_elev']) < minel:
                        minel = min(features[id]['start_elev'], features[id]['end_elev'])
                        candid = id
                        stat = status
                if candid:
                    if stat == 1:
                        tmp_st = features[candid]['end_coords']
                        tmp_end = features[candid]['start_coords']
                        features[candid]['start_coords'] = tmp_st
                        features[candid]['end_coords'] = tmp_end
                    links.append(candid)
                    tot_links.append(candid)
                    seg = features[candid]
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
                    tot_links.append(ff)
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
