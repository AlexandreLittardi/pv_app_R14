import unittest
from types import SimpleNamespace
from geometry_layout import route_elevation,grid_spec,polygons_overlap
from mixins.installation_geometry import InstallationGeometryMixin
from mixins.shadow_geometry import ShadowGeometryMixin
from single_line_516 import route_is_current

class Geometry(InstallationGeometryMixin,ShadowGeometryMixin):
    pass

def surface(x1,x2,h):
    return {'points':[(x1,-1000),(x2,-1000),(x2,1000),(x1,1000)],'height_m':h}

class InstallationTests(unittest.TestCase):
    def test_bridge_keeps_upstream_height_and_counts_single_step(self):
        areas=[surface(0,4000,8),surface(4500,9000,11)]
        r=route_elevation([(0,0),(9000,0)],areas,1,1,2,1)
        self.assertAlmostEqual(r['horizontal_m'],9)
        self.assertAlmostEqual(r['vertical_drop_m'],13) # 8->11->1
        self.assertAlmostEqual(r['length_m'],24)
        r=route_elevation([(0,0),(9000,0)],areas,1,1,2,.4)
        self.assertAlmostEqual(r['vertical_drop_m'],29) # 8->0->11->1

    def test_bridge_across_several_polyline_segments(self):
        areas=[surface(0,4000,8),surface(4500,9000,8)]
        r=route_elevation([(0,0),(4200,0),(4400,0),(9000,0)],areas,1,1,0,.5)
        self.assertEqual(r['vertical_drop_m'],7)

    def test_missing_and_conflicting_height_rejected(self):
        for areas in [[surface(0,9000,None)],[surface(0,9000,8),surface(2000,8000,11)]]:
            with self.assertRaises(ValueError):route_elevation([(0,0),(9000,0)],areas,1,0,0,0)

    def test_no_shadow_height_fallback(self):
        z=surface(0,9000,None);z['z_mm']=8000
        with self.assertRaises(ValueError):route_elevation([(0,0),(9000,0)],[z],1,0,0,0)

    def test_rotated_grid_containment_adjacency_and_area(self):
        g=Geometry();g.px_per_mm=.1;g.panel_width_mm=1000;g.panel_height_mm=1700
        for angle in (0,15,45,90,135,180,-30):
            z={'x1':20,'y1':30,'x2':1020,'y2':1030,'angle_deg':angle}
            g.roof_zones=[z];g._recalculate_zone_grids();polys=[]
            for r in range(z['rows']):
                for c in range(z['cols']):
                    if not g._valid_zone_cell(z,r,c):continue
                    poly=g._panel_rect((r,c));polys.append(poly)
                    self.assertAlmostEqual(g._polygon_area(poly),17000,places=5)
                    self.assertTrue(all(20-1e-6<=x<=1020+1e-6 and 30-1e-6<=y<=1030+1e-6 for x,y in poly))
            self.assertGreater(len(polys),25)
            for i,a in enumerate(polys):
                for b in polys[i+1:]:self.assertFalse(polygons_overlap(a,b))

    def test_panel_centre_matches_rotated_corners(self):
        g=Geometry();g.px_per_mm=.1;g.panel_width_mm=1000;g.panel_height_mm=1700
        g.roof_zones=[{'x1':0,'y1':0,'x2':1000,'y2':1000,'angle_deg':35}];g._recalculate_zone_grids()
        poly=g._panel_rect((2,3));centre=g._get_panel_physical_center((2,3))
        self.assertEqual(centre,tuple(sum(p[i] for p in poly)/4 for i in (0,1)))

    def test_legacy_cable_plan_is_not_current(self):
        self.assertFalse(route_is_current({'electrical_route_plan_3d':{'source_signature':{},'routes':{'S':{}}}},'S'))

class PeriodTests(unittest.TestCase):
    def test_payback_requires_complete_anniversary_period(self):
        from energy_economics import covers_full_year
        self.assertFalse(covers_full_year({'start_date':'2026-01-01','end_date':'2026-01-01','hourly_kwh':[1]*24}))
        self.assertTrue(covers_full_year({'start_date':'2024-01-01','end_date':'2024-12-31','hourly_kwh':[1]*(366*24)}))
        self.assertTrue(covers_full_year({'start_date':'2025-04-01','end_date':'2026-03-31','hourly_kwh':[1]*(365*24)}))

class TrayProjectionTests(unittest.TestCase):
    def test_two_projections_on_same_tray_use_direct_interval(self):
        from mixins.cable_network import CableNetworkMixin
        from mixins.paths_tools import PathsToolsMixin
        class Router(CableNetworkMixin,PathsToolsMixin):pass
        r=Router();r.cable_paths=[{'points':[(0,0),(100,0)]}]
        graph=r._build_cable_network_graph()
        a=r._snap_point_to_network(graph,(30,10));b=r._snap_point_to_network(graph,(70,10))
        length,points=r._dijkstra(graph,a,b)
        self.assertAlmostEqual(length,60) # 10 to tray + 40 along it + 10 to endpoint
