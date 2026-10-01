"""Generate synthetic QA artefacts. NOT a real site study."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from mixins.installation_geometry import InstallationGeometryMixin
from mixins.shadow_geometry import ShadowGeometryMixin
from engineering_report import export_report
from battery_dispatch import BatterySettings,simulate_three_options
from energy_economics import DEFAULTS
from bess_charts import daily_data,monthly_data,energy_figure
from toolbar_icons import raster,ICONS
from PIL import Image,ImageDraw

class Sample(InstallationGeometryMixin,ShadowGeometryMixin):
    def _project_snapshot(self):
        return {'project_name':self.project_name,'panels':{f'{r},{c}':v for (r,c),v in self.panels.items()},
                'strings':{sid:[f'{r},{c}' for r,c in coords] for sid,coords in self.strings.items()},
                'blocks':self.blocks,'string_mppt_assignment':self.string_mppt_assignment,
                'material_categories':self.material_categories,'panel_pmax_w':self.panel_pmax_w}
    def _prepare_project_save(self):return {}
    def _energy_results_current(self):return True
    def _calculate_two_pole_route(self,sid):return None

def sample():
    s=Sample();s.project_name='SYNTHETIC QA FIXTURE - NOT A SITE STUDY'
    s.px_per_mm=.1;s.panel_width_mm=1000;s.panel_height_mm=1700;s.panel_pmax_w=400
    s.roof_zones=[{'id':1,'x1':0,'y1':0,'x2':3000,'y2':3060,'angle_deg':0,'installation_height_m':8,'z_mm':8000}]
    s._recalculate_zone_grids();s.panels={(r,c):r*30+c+1 for r in range(18) for c in range(30)}
    s.roof_polygons=[];s.measures=[];s.panel_orientations={};s.roof_pil_img=None
    s.inverter_positions={'INV1':{'x':3200,'y':1500}};s.cable_paths=[{'id':1,'points':[(100,0),(100,3150),(3200,3150),(3200,1500)]}]
    s.material_categories={'modules':{'rows':[{'Pmax (W)':400,'Voc (V)':45,'Modèle':'Synthetic fixture'}]}}
    s.blocks={'INV1':{'mppt_count':18}};s.strings={f'S{r+1}':[(r,c) for c in range(30)] for r in range(18)}
    s.string_mppt_assignment={f'S{r+1}':{'block':'INV1','mppt':r+1} for r in range(18)}
    s.routing_settings={'inverter_height_m':1,'reserve_per_pole_m':2,'bridge_gap_m':1};s.cable_calc_params={'resistivity':.017,'target_drop_pct':1}
    s.energy_input_settings={'ac_factor':.9};s.grid_connection_settings={'export_limit_kw':40};s.economic_settings=dict(DEFAULTS)
    s.hourly_consumption_profile={'start_date':'2026-01-01','end_date':'2026-01-01','hourly_kwh':[20]*24,'imputed_indices':[]}
    s.hourly_pv_kwh=[0]*6+[15,30,40,60,70,85,80,70,50,40,25,10]+[0]*6
    r=simulate_three_options(s.hourly_consumption_profile,s.hourly_pv_kwh,BatterySettings(nominal_kwh=150,charge_kw=50,discharge_kw=30),40)
    s.self_consumption_summary=r['without_bess'];s.bess_summary=r['one_bess'];s.two_bess_summary=r['two_bess']
    s.project_notes='All data in this file are synthetic, used only to inspect document rendering.'
    return s,r

if __name__=='__main__':
    out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True);s,r=sample()
    export_report(s,out/'report.pdf')
    data=daily_data(r['one_bess']['rows'],1,40,10)
    energy_figure(data,[f'{h:02d}:00' for h in range(24)],'Synthetic day | 1 BESS').savefig(out/'daily.png',dpi=150)
    # Explicit synthetic month variations, for chart readability only.
    summaries=[s.self_consumption_summary,s.bess_summary,s.two_bess_summary]
    months=[f'2026-{m:02d}' for m in range(1,13)]
    for summary in summaries:
        row=summary['monthly']['2026-01']
        summary['monthly']={m:{k:v*(20+i) for k,v in row.items()} for i,m in enumerate(months)}
    labels,data=monthly_data(summaries,1)
    energy_figure(data,labels,'Synthetic months | 1 BESS',True,[[s['monthly'][m]['grid_kwh'] for m in labels] for s in summaries]).savefig(out/'monthly.png',dpi=150)
    image=Image.new('RGB',(600,((len(ICONS)+5)//6)*85),'white');draw=ImageDraw.Draw(image)
    for i,key in enumerate(ICONS):
        icon=raster(key,32);x=(i%6)*100+30;y=(i//6)*85+5;image.paste(icon,(x,y),icon);draw.text((x-20,y+38),key,fill='black')
    image.save(out/'icons.png')
    print(out)
