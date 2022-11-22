import geopandas as gpd
from shapely.geometry import Point, LineString, MultiPoint
from shapely.ops import split


def split_network(network, seg_length, out_file, epsg_out=None): # , out_file, retain_atts):

    dn = gpd.read_file(network)

    # check for projected crs
    if not dn.crs.is_projected:
        dn.to_crs(epsg=epsg_out)

    # check that vertex density is reasonable for splitting to the segment length
    tot_len = 0
    verts = 0
    for i in dn.index:
        tot_len += dn.loc[i].geometry.length
        verts += len(dn.loc[i].geometry.coords.xy[0])
    if tot_len - verts < 0.2 * seg_length:
        raise Exception('Few line vertices relative to the input segmentation length: densify network vertices')

    out_features = []

    for i in dn.index:
        print(f'segmenting feature {i+1} of {len(dn.index)}')
        if dn.loc[i].geometry.length <= seg_length:
            out_features.append(dn.loc[i].geometry)
        else:
            feature = dn.loc[i].geometry
            vertices = feature.coords
            dist = 0
            pts = []
            for x in range(len(vertices.xy[0])-1):
                l = LineString([(vertices.xy[0][x], vertices.xy[1][x]), (vertices.xy[0][x+1], vertices.xy[1][x+1])])
                dist += l.length
                if dist >= seg_length:
                    pts.append([vertices.xy[0][x], vertices.xy[1][x]])
                    dist = 0
            if len(pts) > 1:
                pt = MultiPoint(pts)
            else:
                pt = Point(pts)
            ls = split(feature, pt)
            for f in ls:
                out_features.append(f)
            print(f'split feature into {len(ls)} features')

    d = {'length': [ftr.length for ftr in out_features], 'geometry': out_features}
    out_dn = gpd.GeoDataFrame(d, crs=dn.crs)
    out_dn.to_file(out_file)


in_network = '/media/jordan/Elements/Geoscience/Bitterroot/lidar/blodgett/Blodgett_network_1km.shp'
out_network = '/media/jordan/Elements/Geoscience/Bitterroot/lidar/blodgett/Blodgett_network_split200.shp'

split_network(in_network, 200, out_network)
