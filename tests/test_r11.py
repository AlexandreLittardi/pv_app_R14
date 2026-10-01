import unittest
from types import SimpleNamespace
from diagram_layout import arrange
from bess_charts import daily_data,monthly_data,energy_figure
from battery_dispatch import BatterySettings,simulate_three_options
from report_plans import detail_tiles,clip_segment
from mixins.diagram_editor import DiagramEditorMixin
from mixins.installation_geometry import InstallationGeometryMixin
from toolbar_icons import raster,ICONS

class Canvas:
    def __init__(self):self.calls=[]
    def canvasx(self,x):return x+80
    def canvasy(self,y):return y+40
    def scan_mark(self,*args):self.calls.append(('mark',args))
    def scan_dragto(self,*args,**kw):self.calls.append(('pan',args))
    def configure(self,**kw):pass
    def delete(self,*args):pass
    def create_rectangle(self,*args,**kw):self.calls.append(('box',args))
    def create_line(self,*args,**kw):self.calls.append(('line',kw))

class Editor(DiagramEditorMixin):
    def __init__(self):
        self.canvas=Canvas();self.zoom_level=2;self.diagram_link_mode=None
        self.diagram_nodes={'a':{'x':70,'y':50},'b':{'x':140,'y':80}}
        self.diagram_selected_nodes=set();self.diagram_links=[]
    def _get_active_tab_index(self):return 7
    def _diagram_node_size(self,k):return (30,20)
    def _hit_test_diagram_node(self,x,y):
        for k,v in self.diagram_nodes.items():
            if abs(x/2-v['x'])<=15 and abs(y/2-v['y'])<=10:return k
        return None
    def draw_grid(self):pass

def event(x,y,state=0):return SimpleNamespace(x=x,y=y,state=state)

class R11Tests(unittest.TestCase):
    def test_left_drag_pans_and_never_moves_blocks(self):
        e=Editor();old={k:dict(v) for k,v in e.diagram_nodes.items()}
        e.on_left_press(event(60,60));e.on_left_drag(event(80,90));e.on_left_release(event(80,90))
        self.assertEqual(e.diagram_nodes,old);self.assertEqual(e.canvas.calls[-1],('pan',(80,90)))

    def test_right_marquee_then_group_drag_respects_zoom_and_scrolling(self):
        e=Editor();e.on_right_press(event(5,0));e.on_right_drag(event(240,155));e.on_right_release(event(240,155))
        self.assertEqual(e.diagram_selected_nodes,{'a','b'})
        e.on_right_press(event(60,60));e.on_right_drag(event(100,80));e.on_right_release(event(100,80))
        self.assertEqual(e.diagram_nodes['a'],{'x':90,'y':60});self.assertEqual(e.diagram_nodes['b'],{'x':160,'y':90})

    def test_large_electrical_blocks_and_distance_lanes_never_overlap(self):
        nodes={};links=[];sizes={}
        for b in range(3):
            inv=f'inv::{b}';nodes[inv]={};sizes[inv]=(380,160)
            for m in range(10):
                mp=f'mppt::{b}::{m}';nodes[mp]={};sizes[mp]=(410,150);links.append({'a':mp,'b':inv,'auto':True})
                for n in range(2):
                    s=f'str::{b}-{m}-{n}';nodes[s]={};sizes[s]=(450,150);links.append({'a':s,'b':mp,'auto':True})
        positions=arrange(nodes,links,sizes)
        for a,(ax,ay) in positions.items():
            aw,ah=sizes[a]
            for b,(bx,by) in positions.items():
                if a>=b:continue
                bw,bh=sizes[b]
                self.assertTrue(abs(ax-bx)>=(aw+bw)/2 or abs(ay-by)>=(ah+bh)/2)
        for link in links:
            a,b=link['a'],link['b']
            self.assertGreaterEqual(positions[b][0]-sizes[b][0]/2-(positions[a][0]+sizes[a][0]/2),260)

    def test_daily_balances_and_soc_boundaries(self):
        profile={'start_date':'2026-01-01','end_date':'2026-01-01','hourly_kwh':[2]*24,'imputed_indices':[]}
        out=simulate_three_options(profile,[0]*6+[5]*12+[0]*6,BatterySettings(nominal_kwh=10,charge_kw=3,discharge_kw=3),1)
        for case in range(3):
            data=daily_data(out['two_bess' if case==2 else 'one_bess']['rows'],case,1,10)
            for i in range(24):
                self.assertAlmostEqual(data['load_kwh'][i],data['direct_kwh'][i]+data['discharge_ac_kwh'][i]+data['grid_kwh'][i])
                self.assertAlmostEqual(data['pv_kwh'][i],sum(data[k][i] for k in ('direct_kwh','charge_ac_kwh','export_kwh','curtailed_kwh')))
            self.assertEqual(len(data['soc']),25 if case else 0)

    def test_detail_atlas_covers_every_module_with_readable_ids(self):
        panels=[((r,c),r*30+c+1,[(c*100,r*170),(c*100+100,r*170),(c*100+100,r*170+170),(c*100,r*170+170)]) for r in range(20) for c in range(30)]
        tiles=detail_tiles(panels)
        self.assertGreater(len(tiles),1)
        self.assertEqual({p[0] for _,_,members in tiles for p in members},{p[0] for p in panels})
        for _,bbox,members in tiles:
            scale=min(451/(bbox[2]-bbox[0]),515/(bbox[3]-bbox[1]))
            self.assertGreaterEqual(100*scale,27.99)

    def test_line_icons_are_images_not_unicode_glyphs(self):
        for key in ICONS:
            icon=raster(key);self.assertEqual(icon.size,(12,12));self.assertIsNotNone(icon.getbbox())

    def test_dimensions_are_black_double_arrows_without_dots_or_dashes(self):
        class Dim(InstallationGeometryMixin):
            def _draw_text_with_bg(self,*args,**kwargs):self.text=kwargs
        d=Dim();d.canvas=Canvas();d.px_per_mm=.1
        for axis in ('aligned','horizontal','vertical'):
            d._draw_dimension({'p1':(0,0),'p2':(100,80),'label':(50,110),'axis':axis},1)
            calls=d.canvas.calls;self.assertEqual(calls[-1][1]['arrow'],'both')
            self.assertTrue(all(c[1]['fill']=='#000000' and not c[1].get('dash') for c in calls))
            self.assertEqual(d.text['font'][0],'Times New Roman')

    def test_energy_axes_include_full_stacked_totals(self):
        data={k:[100.,200.] for k in ('load_kwh','pv_kwh','direct_kwh','charge_ac_kwh','discharge_ac_kwh','grid_kwh','export_kwh','curtailed_kwh')}
        data['soc']=[10,30,20]
        fig=energy_figure(data,['00:00','01:00'],'Daily')
        self.assertGreaterEqual(fig.axes[0].get_ylim()[1],600)
        self.assertGreaterEqual(fig.axes[1].get_ylim()[1],800)
        fig=energy_figure(data,['2026-01','2026-02'],'Monthly',True,[[2000,3000]]*3)
        self.assertGreaterEqual(fig.axes[2].get_ylim()[1],3)
