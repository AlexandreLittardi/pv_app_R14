"""Regression tests for persistence, geometry, energy boundaries and new palette."""
import copy
import datetime as dt
import json
from pathlib import Path
import queue
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from PIL import Image
from project_store import validate_project,write_project,valid_polygon,fingerprint,MODEL_DEFAULTS
from zone_registry import allocate_ranges
from shading_models import optical_area,attenuation
from engineering_inputs import ac_limit_kw,panel_connections,inverter_row
from self_consumption import production_from_program,timestamps
from battery_dispatch import BatterySettings,simulate_three_options,simulate_bess,write_comparison_csv
from energy_economics import evaluate_options
from mixins.installation_geometry import InstallationGeometryMixin
from mixins.shadow_geometry import ShadowGeometryMixin
from mixins.string_sizing import StringSizingMixin,size_string
from detailed_electrical import source_fingerprint

ROOT=Path(__file__).resolve().parents[1]
class Geometry(InstallationGeometryMixin,ShadowGeometryMixin):
    def _invalidate_cable_routes(self):self.invalidated=True
    def _update_string_listbox(self):pass
    def _update_zone_combo(self):pass
    def _update_zone_entries_from_active(self):pass
    def draw_grid(self):pass
    def _clean_deleted_panels_from_strings(self):pass

def geometry():
    g=Geometry();g.px_per_mm=.1;g.panel_width_mm=1000;g.panel_height_mm=1700;g.model_settings=dict(MODEL_DEFAULTS)
    g.roof_zones=[{'x1':0,'x2':500,'y1':0,'y2':510},{'x1':1000,'x2':1500,'y1':0,'y2':510}]
    g._recalculate_zone_grids();g.panels={(0,0):7,(100,0):99};g.panel_blocks={};g.panel_orientations={};g.panel_uids={(0,0):'A',(100,0):'B'}
    g.strings={'S1':[(0,0)],'S2':[(100,0)]};g.string_mppt_assignment={'S1':{'block':'I','mppt':1},'S2':{'block':'I','mppt':2}};g.cable_string_params={}
    g.selected_panel_coords=set();g.selected_zone_indices={0};g.active_zone_idx=0
    g.layout_geometry={f'{r},{c}':fingerprint(g._panel_rect((r,c))) for r,c in g.panels}
    return g

def energy_app():
    panels={(0,0):1,(1,0):2};strings={'S1':[(0,0)],'S2':[(1,0)]}
    project={'panels':{'0,0':1,'1,0':2},'strings':{'S1':['0,0'],'S2':['1,0']},'material_categories':{'modules':{'rows':[{'Pmax (W)':10000}]}},
        'inverter_positions':{'I1':{'material_row':{'Puissance active (kW)':1}},'I2':{'material_row':{'Puissance active (kW)':100}}}}
    return SimpleNamespace(panels=panels,strings=strings,string_mppt_assignment={'S1':{'block':'I1','mppt':1},'S2':{'block':'I2','mppt':1}},
        blocks={'I1':{'mppt_count':1},'I2':{'mppt_count':1}},panel_blocks={},panel_pmax_w=10000,panel_noct_c=45,panel_temp_coeff_pct=0,
        panel_orientations={},panel_tilt_deg=0,panel_azimuth_deg=180,pylon_img_pos=None,solar_latitude=45,solar_longitude=9,
        model_settings=dict(MODEL_DEFAULTS),_project_snapshot=lambda:project,_compute_solar_position=lambda *a,**k:(45,180),
        _get_clear_sky_poa_irradiance=lambda *a:1000,_estimate_panel_power_w=lambda irr,shade=0:10000*(1-shade))

class PersistenceTests(unittest.TestCase):
    def test_legacy_projects_keep_panel_ids_and_all_memberships(self):
        for file in (ROOT/'exemples_joints').glob('*.json'):
            source=json.loads(file.read_text());data=validate_project(source)
            self.assertEqual(source['panels'],data['panels'])
            self.assertEqual(source['strings'],data['strings'])
            self.assertEqual(data,validate_project(data));self.assertEqual(data['schema_version'],2)
    def test_atomic_failure_keeps_previous_project_and_image(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'project.json';data={'panels':{'0,0':77}}
            first=write_project(path,data,Image.new('RGB',(10,10),'red'));original=path.read_bytes()
            with patch('project_store.os.replace',side_effect=OSError('disk failure')):
                with self.assertRaises(OSError):write_project(path,{'panels':{'0,0':88}},Image.new('RGB',(10,10),'blue'))
            self.assertEqual(path.read_bytes(),original);self.assertTrue((path.parent/first['roof_image_path']).exists())
    def test_backups_and_content_named_image(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'project.json';first=write_project(path,{},Image.new('RGB',(10,10),'red'))
            second=write_project(path,{},Image.new('RGB',(10,10),'blue'))
            self.assertNotEqual(first['roof_image_path'],second['roof_image_path'])
            self.assertEqual(len(list((path.parent/'.backups').glob('*.bak'))),1)
    def test_schema_and_nonfinite_inputs_rejected(self):
        for source in ({'schema_version':99},{'solar_hour':'NaN'},{'panel_width_mm':0},{'panels':{'0,0':1,'0,1':1}},
            {'cable_string_params':{'S':{'voltage_v':float('inf')}}},{'equipment_links':{'I':9}},
            {'model_settings':{'bypass_groups':0}},{'model_settings':{'timezone':'not/a/timezone'}},
            {'cable_inventory':[{'length_m':-1}]}):
            with self.subTest(source=source),self.assertRaises((ValueError,KeyError)):validate_project(source)
    def test_invalid_polygon_rejected(self):
        for points in ([[0,0],[1,1],[0,1],[1,0]],[[0,0],[0,0],[1,0]],[[0,0],[1,0],[2,0]]):
            self.assertFalse(valid_polygon(points))
            with self.assertRaises(ValueError):validate_project({'roof_polygons':[{'points':points}]})
    def test_equipment_link_reads_current_sheet(self):
        p=validate_project({'material_categories':{'inverters':{'rows':[{'Marque':'X','Modèle':'M','Puissance active (kW)':50}]}},'inverter_positions':{'I':{'x':0,'y':0,'material_row':{'Marque':'X','Modèle':'M','Puissance active (kW)':40}}}})
        self.assertEqual(p['equipment_links'],{'I':0});self.assertEqual(ac_limit_kw(p,'I'),50)
        p['material_categories']['inverters']['rows'][0]['Puissance active (kW)']=60;self.assertEqual(ac_limit_kw(p,'I'),60)

class GeometryTests(unittest.TestCase):
    def test_deleting_first_zone_preserves_second_geometry_and_string(self):
        g=geometry();before=g._panel_rect((100,0));g.delete_active_zone()
        self.assertEqual(g._panel_rect((100,0)),before);self.assertEqual(g.panels,{(100,0):99})
        self.assertEqual(g.strings['S2'],[(100,0)]);self.assertNotIn('S1',g.string_mppt_assignment)
    def test_moved_zone_detaches_only_affected_string(self):
        g=geometry();g.roof_zones[0]['x1']+=100;g.roof_zones[0]['x2']+=100;g.generate_panels_from_zones()
        self.assertEqual(g.strings['S1'],[]);self.assertNotIn('S1',g.string_mppt_assignment)
        self.assertEqual(g.strings['S2'],[(100,0)]);self.assertEqual(g.panels[(100,0)],99)
        self.assertNotEqual(g.panels[(0,0)],7);self.assertNotIn((0,0),g.panel_uids)
    def test_range_expands_above_100_without_collision(self):
        zones=[{'row_base':0,'row_capacity':100},{'row_base':100,'row_capacity':100}];calls=[]
        allocate_ranges(zones,[(150,1,0,0),(3,1,0,0)],lambda *a:calls.append(a))
        self.assertGreaterEqual(zones[0]['row_base'],200);self.assertEqual(zones[1]['row_base'],100);self.assertEqual(calls[0],(0,100,200))
    def test_gap_reduces_grid_and_preserves_module_area(self):
        g=geometry();original=g.roof_zones[0]['cols'];g.model_settings['module_gap_x_mm']=500;g._recalculate_zone_grids()
        self.assertLess(g.roof_zones[0]['cols'],original);self.assertAlmostEqual(g._polygon_area(g._panel_rect((0,0))),17000)
    def test_exclusions_reject_intersecting_panels(self):
        g=geometry();g.model_settings['layout_exclusions']=[[(0,0),(150,0),(150,200),(0,200)]]
        self.assertFalse(g._valid_zone_cell(g.roof_zones[0],0,0))

class EnergyTests(unittest.TestCase):
    def test_clipping_is_per_inverter(self):
        p={'start_date':'2026-01-01','end_date':'2026-01-01','hourly_kwh':[0]*24}
        self.assertEqual(production_from_program(energy_app(),p,1),[11]*24)
    def test_no_assumed_125_kw_limit(self):
        with self.assertRaises(ValueError):ac_limit_kw({'inverter_positions':{}},'I')
        p={'inverter_positions':{'I':{'material_row':{'Puissance (kVA)':125,'Cos phi':.8}}}}
        self.assertEqual(ac_limit_kw(p,'I'),100)
    def test_unconnected_modules_are_blocked(self):
        app=energy_app();app.strings.pop('S1')
        with self.assertRaises(ValueError):panel_connections(app)
    def test_stale_weather_is_blocked(self):
        p={'start_date':'2026-01-01','end_date':'2026-01-01','hourly_kwh':[0]*24}
        weather={'query':{'latitude':1,'longitude':9,'tilt_deg':0,'azimuth_deg_from_south':0},'hourly_poa_w_m2':[1000]*24,'hourly_ambient_c':[20]*24,'period_start':p['start_date'],'period_end':p['end_date']}
        with self.assertRaises(ValueError):production_from_program(energy_app(),p,1,weather=weather)
    def test_explicit_timestamp_dst_has_23_or_25_hours(self):
        from zoneinfo import ZoneInfo
        for date,count in ((dt.date(2026,3,29),23),(dt.date(2026,10,25),25)):
            zone=ZoneInfo('Europe/Paris');start=dt.datetime.combine(date,dt.time(),zone).astimezone(dt.timezone.utc)
            profile={'hourly_kwh':[1]*count,'timestamps':[(start+dt.timedelta(hours=i)).astimezone(zone).isoformat() for i in range(count)]}
            self.assertEqual(len(timestamps(profile)),count)
    def test_auxiliary_balance_and_hourly_export(self):
        p={'start_date':'2026-01-01','end_date':'2026-01-01','hourly_kwh':[10]*24}
        cfg=BatterySettings(nominal_kwh=100,charge_kw=10,discharge_kw=10,auxiliary_kw=1)
        r=simulate_three_options(p,[0]*24,cfg)
        self.assertEqual(r['one_bess']['annual']['grid_kwh'],264);self.assertEqual(r['two_bess']['annual']['grid_kwh'],288)
        annuals=[r[k]['annual'] for k in ('without_bess','one_bess','two_bess')]
        valued=evaluate_options(annuals,{'import_eur_kwh':1,'annual_maintenance_eur':0})
        self.assertEqual(valued[1]['incremental_benefit_eur'],-24)
        with tempfile.TemporaryDirectory() as directory:write_comparison_csv(Path(directory)/'out.csv',r)
    def test_initial_stored_energy_is_not_credited_as_pv(self):
        p={'start_date':'2026-01-01','end_date':'2026-01-01','hourly_kwh':[10]*24}
        cfg=BatterySettings(nominal_kwh=100,charge_kw=10,discharge_kw=10,initial_soc_pct=90)
        r=simulate_three_options(p,[0]*24,cfg)
        valued=evaluate_options([r[k]['annual'] for k in ('without_bess','one_bess','two_bess')])
        self.assertAlmostEqual(valued[1]['avoided_purchases_eur'],0)
    def test_design_fingerprint_covers_geometry_routing_and_override(self):
        base={'px_per_mm':.1,'cable_string_params':{},'routing_settings':{}}
        for key,value in (('px_per_mm',.2),('cable_string_params',{'S':{'voltage_v':400}}),('routing_settings',{'reserve_per_pole_m':8})):
            changed={**base,key:value};self.assertNotEqual(source_fingerprint(base),source_fingerprint(changed))

class ModelTests(unittest.TestCase):
    def test_overlap_is_not_double_counted(self):
        square=[(0,0),(1,0),(1,1),(0,1)]
        self.assertAlmostEqual(optical_area([(square,1),(square,1)]),1)
        self.assertAlmostEqual(optical_area([(square,.5),(square,.5)]),.75)
        other=[(.5,0),(1.5,0),(1.5,1),(.5,1)]
        self.assertAlmostEqual(optical_area([(square,1),(other,1)]),1.5)
    def test_bypass_model_is_explicit(self):
        self.assertEqual(attenuation(.1,{'shadow_model':'geometric'}),.1)
        self.assertAlmostEqual(attenuation(.1,{'shadow_model':'bypass_estimate','bypass_groups':3}),1/3)
    def test_additional_cable_inventory_is_counted(self):
        class Mass(StringSizingMixin):
            strings={};cable_inventory=[{'length_m':10,'linear_mass_kg_m':.5,'quantity':2}]
        self.assertEqual(Mass()._cable_mass_summary()['total_kg'],10)
        Mass.cable_inventory.append({'length_m':5});self.assertIsNone(Mass()._cable_mass_summary()['total_kg'])
    def test_chosen_section_and_ampacity_are_checked(self):
        rec=size_string({'loop_length_m':100},10,{'Imp (A)':12,'Vmp (V)':40},{'section_mm2':1,'ampacity_a':5},{'resistivity':.017,'target_drop_pct':1},{})
        self.assertIn('FAIL',rec['ampacity_status']);self.assertEqual(rec['working_section_mm2'],1)
    def test_worker_cancellation_does_not_return_success(self):
        from async_jobs import Job,Cancelled
        import threading
        gate=threading.Event()
        job=Job(lambda report:(gate.wait(2),report(1,1)))
        job.cancel();gate.set();kind,payload=job.messages.get(timeout=3)
        self.assertEqual(kind,'error');self.assertIsInstance(payload,Cancelled)
    def test_palette_is_vivid_and_categories_distinguishable(self):
        from bess_charts import COLORS,CASE_COLORS
        self.assertEqual(len(set(COLORS[k] for k in ('direct','battery','grid','export','curtail','soc'))),6)
        self.assertEqual(len(set(CASE_COLORS)),3)
    def test_full_plan_export_contains_offscreen_extent(self):
        from plan_renderer import render_plan
        g=geometry();g.roof_pil_img=Image.new('RGB',(20,20),'white');g.roof_polygons=[];g.cable_paths=[];g.inverter_positions={};g.measures=[]
        with tempfile.TemporaryDirectory() as directory:
            size=render_plan(g,Path(directory)/'plan.jpg',1);self.assertGreater(size[0],1000)

if __name__=='__main__':unittest.main()
