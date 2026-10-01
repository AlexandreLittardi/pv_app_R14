"""R14 regression: questionnaire, every-tab history and actual frozen PDF class."""
import copy
import csv
import datetime as dt
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from PIL import Image
from energy_engine import freeze_app
from configuration_form import prepare,fields,get,apply_values,parse,Field
from constants import STRING_COLORS
from report_plans import PALETTE
from report_studies import annual_shadow,shadow_blocks,spreadsheet_blocks
from tools.report_fixture import load
from mixins.safe_project import SafeProjectMixin
from diagram_layout import arrange
from toolbar_icons import icon_key,raster

ROOT=Path(__file__).resolve().parents[1]
PROJECT=ROOT/'exemples_joints'/'Usine_Frimo_517.json'


def questionnaire_values(data,descriptors):
    values=[]
    for field in descriptors:
        value=get(data,field.path)
        if value is None:value=''
        if field.kind=='row' and value!='':value=int(value)+1
        if field.kind=='point' and value!='':value=','.join(map(str,value))
        if field.kind=='points':value=';'.join(','.join(map(str,p)) for p in value) if value else ''
        values.append(value)
    return values

class History(SafeProjectMixin):
    def __init__(self):
        self._guard_ready=True;self._restoring=False;self._history=[];self._history_index=-1
        self._task_running=False;self.current_project_filepath=None;self.projects_dir='.'
        self.document={'panels':{},'strings':{},'material_spreadsheet':{},'diagram_nodes':{},'cable_string_params':{},'energy_input_settings':{}}
        self.roof_pil_img=None;self.diagram_nodes={};self.zoom_level=1;self._history_buttons=[]
    def _capture_cable_inputs(self):pass
    def _collect_project_data(self):return copy.deepcopy(self.document)
    def _apply_document(self,data,path):self.document=copy.deepcopy(data)
    def _refresh_energy_workspace(self):pass
    def draw_grid(self):self._update_history_buttons()

class QuestionnaireTests(unittest.TestCase):
    def test_all_attached_projects_questionnaire_roundtrip(self):
        for path in (ROOT/'exemples_joints').glob('*.json'):
            app=load(path);data=prepare(app._collect_project_data());before=copy.deepcopy(data)
            descriptors=fields(data)
            result=apply_values(data,descriptors,questionnaire_values(data,descriptors))
            self.assertEqual(data['panels'],result['panels']);self.assertEqual(data['strings'],result['strings'])
            self.assertEqual(data['material_spreadsheet'],result['material_spreadsheet'])
            self.assertEqual(data['string_direction'],result['string_direction'])
            paths={f.path for f in descriptors}
            for sid in data['strings']:
                if data['strings'][sid]:self.assertIn(('cable_string_params',sid,'section_mm2'),paths)
            for key in ('nominal_kwh','soc_min_pct','charge_kw'):self.assertIn(('energy_input_settings','bess',key),paths)
            self.assertIn(('model_settings','report_shadow_year'),paths)
            self.assertIn(('electrical_design','grid','main_breaker_a'),paths)
            self.assertEqual(before['panels'],data['panels'])
    def test_invalid_questionnaire_is_atomic(self):
        data=prepare(load(PROJECT,small=True)._collect_project_data());descriptors=fields(data)
        values=questionnaire_values(data,descriptors);before=copy.deepcopy(data)
        index=next(i for i,f in enumerate(descriptors) if f.path==('panel_width_mm',));values[index]='-1'
        with self.assertRaises(ValueError):apply_values(data,descriptors,values)
        self.assertEqual(data,before)
    def test_choice_and_nonfinite_point_validation(self):
        with self.assertRaises(ValueError):parse(Field('x',('x',),'Direction','choice',('Horizontal','Vertical')),'garbage')
        with self.assertRaises(ValueError):parse(Field('x',('x',),'Point','point'),'NaN,1')
        self.assertEqual(parse(Field('x',('x',),'Row','row'),'2'),1)

class HistoryTests(unittest.TestCase):
    def test_undo_redo_for_each_tab_and_each_document_domain(self):
        for tab in range(10):
            h=History();h.active_tab=tab;h._record_history();baseline=copy.deepcopy(h.document)
            for key in h.document:h.document[key]={'changed_in_tab':tab}
            h.undo_project();self.assertEqual(h.document,baseline)
            h.redo_project();self.assertEqual(h.document['strings'],{'changed_in_tab':tab})
    def test_history_capture_keeps_uncommitted_widget_text(self):
        from energy_engine import Value
        app=load(PROJECT,small=True);app.entry_panel_pmax=Value('typing a draft')
        app.cable_entries={key:Value(str(value)) for key,value in app.cable_calc_params.items()}
        app._history=[];app._history_index=-1;app._guard_ready=True
        app._record_history();self.assertEqual(app.entry_panel_pmax.get(),'typing a draft')

    def test_unchanged_hourly_profiles_shared_between_history_states(self):
        h=History();h.document['hourly_consumption_profile']={'hourly_kwh':[10]*8760}
        h._record_history();h.document['panels']={'a':1};h._record_history()
        self.assertIs(h._history[0][1]['hourly_consumption_profile'],h._history[1][1]['hourly_consumption_profile'])
        h.undo_project();h.document['hourly_consumption_profile']['hourly_kwh'][0]=99
        self.assertEqual(h._history[0][1]['hourly_consumption_profile']['hourly_kwh'][0],10)

    def test_undo_preserves_source_image_and_view(self):
        h=History();first=Image.new('RGB',(4,4),'red');second=Image.new('RGB',(4,4),'blue')
        h.roof_pil_img=first;h._record_history();h.roof_pil_img=second;h.zoom_level=2
        h.undo_project();self.assertIs(h.roof_pil_img,first);self.assertEqual(h.zoom_level,1)
        h.redo_project();self.assertIs(h.roof_pil_img,second);self.assertEqual(h.zoom_level,2)
    def test_redo_invalidated_after_branch_edit(self):
        h=History();h._record_history();h.document['panels']={'a':1};h._record_history();h.document['panels']={'a':2}
        h.undo_project();self.assertEqual(h.document['panels'],{'a':1})
        h.document['panels']={'a':3};h.redo_project();self.assertEqual(h.document['panels'],{'a':3});self.assertEqual(h._history_index,len(h._history)-1)
    def test_buttons_available_for_all_ten_tabs(self):
        class Button:
            def __init__(self,parent,text,command):self.parent=parent;self.text=text;self.command=command
            def pack(self,**kwargs):pass
            def state(self,values):self.disabled=values==['disabled']
        class Base:
            def _install_responsive_ui(self):return True
        class Tabs(History,Base):pass
        app=Tabs();app.root=SimpleNamespace(nametowidget=lambda ident:ident)
        app.ribbon_notebook=SimpleNamespace(tabs=lambda:list(range(10)))
        with patch('mixins.safe_project.ttk.Button',Button):app._install_responsive_ui()
        self.assertEqual(len(app._history_buttons),20)
        app._record_history();app.document['panels']={'a':1};app._record_history()
        for button,label in app._history_buttons:self.assertEqual(button.disabled,label=='Redo')

class ReportTests(unittest.TestCase):
    def test_real_app_frozen_image_export_and_all_requested_sections(self):
        from engineering_report import export_report
        import fitz
        app=load(PROJECT,small=True)
        # Explicit synthetic fixture rating, never applied to the supplied project.
        app.material_categories['inverters']['rows'][0]['Puissance active (kW)']=125.
        app.roof_pil_img=Image.new('RGB',(600,300),'white')
        app.material_spreadsheet={'rows':3,'cols':7,'cells':{'A1':'2','B1':'=A1*3','G3':'Last cell'}}
        frozen=freeze_app(app)
        self.assertEqual(type(frozen),type(app));self.assertIsNot(frozen.roof_pil_img,app.roof_pil_img)
        frozen.roof_pil_img.putpixel((0,0),(255,0,0));self.assertEqual(app.roof_pil_img.getpixel((0,0)),(255,255,255))
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'report.pdf';export_report(frozen,path)
            with fitz.open(path) as pdf:text='\n'.join(page.get_text() for page in pdf)
            for title in ('Plan, installation areas','Equipment and electrical schedule','Annual influence of shading','Complete spreadsheet','Energy and BESS comparison','DC cable routes','String connections','Last cell'):
                self.assertIn(title,text)
            self.assertIn('Energy results current',text);self.assertIn('Monthly PV/load balance',text)
            assets=Path(directory)/'report_assets'
            for name in ('annual_shadow_roof.png','annual_shadow_calendar.png','energy_comparison.png','energy_monthly.png','spreadsheet_inputs.csv','spreadsheet_values.csv','strings_overview.svg','cables_overview.svg','roof_source.png'):
                self.assertTrue((assets/name).exists(),name)
            with (assets/'spreadsheet_values.csv').open(encoding='utf-8-sig') as file:rows=list(csv.reader(file))
            self.assertEqual(float(rows[1][2]),6);self.assertEqual(rows[3][-1],'Last cell')
            self.assertFalse(app.self_consumption_summary==frozen.self_consumption_summary)
    def test_full_year_uses_real_hours_and_energy_weighted_loss(self):
        app=SimpleNamespace(panels={(0,0):1},strings={'S1':[(0,0)]},model_settings={'timezone':'Europe/Paris','report_shadow_year':2024,'shadow_obstacles':[{}]},
            pylon_img_pos=None,px_per_mm=1,solar_latitude=45,solar_longitude=9,panel_noct_c=45,panel_temp_coeff_pct=-.3,panel_pmax_w=400)
        solar=[]
        def sun(*args,**kwargs):solar.append((args,kwargs));return 45,180
        app._compute_solar_position=sun;app._calculate_shadow_percentages=lambda *a:({(0,0):25},[])
        app._get_clear_sky_poa_irradiance=lambda *a:1000
        app._panel_energy_step=lambda irradiance,shade,hours:(400*hours,400*(1-shade)*hours,400*shade*hours)
        result=annual_shadow(app)
        self.assertEqual(result['hours'],8784);self.assertAlmostEqual(result['rows'][0]['loss_pct'],25)
        self.assertAlmostEqual(sum(m['potential_wh'] for m in result['months'].values()),8784*400)
        self.assertEqual(len({t.astimezone(dt.timezone.utc) for t,p,l in result['timeline']}),8784)
        self.assertEqual({args[5] for args,kw in solar},{1.,2.})
    def test_cached_shadow_geometry_matches_original_with_overlapping_obstacles(self):
        from shadow_engine import make_shadow_sampler
        app=load(PROJECT);coord=next(iter(app.panels));poly=app._panel_rect(coord)
        app.model_settings['shadow_obstacles']=[{'footprint_px':poly,'height_mm':60000,'opacity':.5}]*2
        sample=make_shadow_sampler(app)
        for elevation,azimuth in ((10,90),(35,180),(65,270)):
            original=app._calculate_shadow_percentages(elevation,azimuth)[0];cached=sample(elevation,azimuth)
            self.assertEqual(set(original),set(cached))
            for key in original:self.assertAlmostEqual(original[key],cached[key],places=8)

    def test_annual_study_cancellation_propagates(self):
        from async_jobs import Cancelled
        app=load(PROJECT,small=True)
        def cancel(*args):raise Cancelled('cancelled')
        with self.assertRaises(Cancelled):annual_shadow(app,cancel)
    def test_string_palette_shared_and_bicolour(self):
        self.assertEqual(PALETTE,STRING_COLORS);self.assertEqual(len(PALETTE),2)
        self.assertNotEqual(PALETTE[0],PALETTE[1])
    def test_distinct_primary_actions_have_distinct_icon_rasters(self):
        actions=['Undo','Redo','Configuration','Display settings','Engineering report PDF','Export screenshot','Renumber panels','Zones','Panel…','Layout','MPPT actions','String actions','Block actions','Cable paths','Gathering points','String routes','Calculate cross-section','Shadow settings','Obstacle','Charts']
        keys=[icon_key(action) for action in actions];self.assertEqual(len(keys),len(set(keys)))
        images=[raster(key).tobytes() for key in keys];self.assertEqual(len(images),len(set(images)))
    def test_natural_order_and_grouped_inverters(self):
        nodes={'inv::I1':{},'mppt::I1::1':{},'str::S10':{},'str::S2':{}}
        links=[{'a':a,'b':b,'auto':True} for a,b in [('str::S10','mppt::I1::1'),('str::S2','mppt::I1::1'),('mppt::I1::1','inv::I1')]]
        positions=arrange(nodes,links,{k:(300,100) for k in nodes})
        self.assertLess(positions['str::S2'][1],positions['str::S10'][1])
