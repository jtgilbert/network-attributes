import rasterio
import geopandas as gpd
from rasterstats import zonal_stats
from shapely.geometry import Point


def network_topology(in_network, first_feature, dem):

    dn = gpd.read_file(in_network)
    with rasterio.open(dem) as src:
        if not src.crs.is_projected:
            raise Exception('DEM does not have a projected coordinate system')
        resolution = abs(src.transform[0])

    topo_dict = {}

    # first chain
    chain = 1
    links = [first_feature]
    chain_length = dn.loc[first_feature].geometry.length
    seg = dn.loc[first_feature].geometry
    rev = False
    while seg:
        start_pt = [seg.coords.xy[0][0], seg.coords.xy[1][0]]
        end_pt = [seg.coords.xy[0][-1], seg.coords.xy[1][-1]]
        if rev:
            # spt = Point(start_pt[0], start_pt[1])
            # ept = Point(end_pt[0], end_pt[1])
            # spt_buf = spt.buffer(resolution*4)
            # ept_buf = ept.buffer(resolution*4)
            # spt_zs = zonal_stats(spt_buf, dem)
            # ept_zs = zonal_stats(ept_buf, dem)
            # start_elev = spt_zs[0].get('min')
            # end_elev = ept_zs[0].get('min')
            # if end_elev > start_elev:
            #     print(f'segment {first_feature} appears to be reversed, flipping start and end coordinates')
            start_pt = [seg.coords.xy[0][-1], seg.coords.xy[1][-1]]
            end_pt = [seg.coords.xy[0][0], seg.coords.xy[1][0]]

        dsseg = None
        for i in dn.index:
            if i not in links:
                if seg == dn.loc[28].geometry:
                    if i == 48:
                        print('48')
                next_seg = dn.loc[i].geometry
                n_start_pt = [next_seg.coords.xy[0][0], next_seg.coords.xy[1][0]]
                n_end_pt = [next_seg.coords.xy[0][-1], next_seg.coords.xy[1][-1]]

                if n_start_pt == end_pt:
                    links.append(i)
                    print(f'adding segment {i} to chain')
                    chain_length += dn.loc[i].geometry.length
                    dsseg = next_seg
                    seg = next_seg
                    rev = False
                if n_end_pt == end_pt:
                    n_spt = Point(n_start_pt[0], n_start_pt[1])
                    n_ept = Point(n_end_pt[0], n_end_pt[1])
                    n_spt_zs = zonal_stats(n_spt, dem)
                    n_ept_zs = zonal_stats(n_ept, dem)
                    n_start_elev = n_spt_zs[0].get('min')
                    n_end_elev = n_ept_zs[0].get('min')
                    if n_end_elev > n_start_elev:
                        links.append(i)
                        print(f'adding segment {i} to chain')
                        chain_length += dn.loc[i].geometry.length
                        dsseg = next_seg
                        seg = next_seg
                        rev = True

        if dsseg is None:

            seg = None

    topo_dict[chain] = links

    dn.to_file()


network = '/media/jordan/Elements/Geoscience/Bitterroot/lidar/blodgett/Blodgett_network_split200.shp'
ff = 207
dem = '/media/jordan/Elements/Geoscience/Bitterroot/lidar/blodgett/Blodgett_DEM_2m.tif'

network_topology(network, ff, dem)
