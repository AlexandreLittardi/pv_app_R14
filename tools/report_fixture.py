"""Load real project state into the real application class without constructing Tk."""
import copy
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import PVLayoutRibbonApp
from energy_engine import Value
from project_store import validate_project,MODEL_DEFAULTS
from battery_dispatch import BatterySettings
from dataclasses import asdict
from mixins.project_integrity import EXTRA_FIELDS


def load(path, image=None, small=False):
    data=validate_project(json.loads(Path(path).read_text(encoding='utf-8')))
    app=PVLayoutRibbonApp.__new__(PVLayoutRibbonApp)
    for name,value in data.items():setattr(app,name,copy.deepcopy(value))
    app.model_settings={**MODEL_DEFAULTS,**data.get('model_settings',{}),'report_shadow_year':2026}
    for name in EXTRA_FIELDS:
        if not hasattr(app,name):setattr(app,name,[] if name in ('cable_inventory','hourly_pv_kwh') else {})
    for name in ('cable_string_params','cable_mass_by_section','panel_uids','shadow_result','shadow_simulation_results'):
        if not hasattr(app,name):setattr(app,name,{})
    def coord(key):return tuple(map(int,key.split(',')))
    for name in ('panels','panel_blocks','panel_orientations'):
        setattr(app,name,{coord(key):value for key,value in getattr(app,name,{}).items()})
    app.strings={sid:[coord(key) for key in coords] for sid,coords in app.strings.items()}
    app.manual_strings=set(app.manual_strings)
    app.var_continuous_numbers=Value(data.get('continuous_panel_numbers',True))
    for key in ('min','max'):setattr(app,'string_'+key+'_var',Value(data.get('string_'+key+'_panels',12)))
    app.string_direction_var=Value(data.get('string_direction','Auto (layout)'))
    app.self_ac_entry=Value(data.get('energy_input_settings',{}).get('ac_factor','.9'))
    defaults=asdict(BatterySettings())
    keys=('nominal_kwh','charge_kw','discharge_kw','soc_min_pct','soc_max_pct','round_trip_efficiency')
    app.bess_entries={key:Value(str(data.get('energy_input_settings',{}).get('bess',{}).get(key,defaults[key]))) for key in keys}
    app.roof_pil_img=None
    if image:
        from PIL import Image
        with Image.open(image) as source:app.roof_pil_img=source.copy()
    app._cable_network_graph=None;app._cable_graph_signature=None
    app._recalculate_zone_grids()
    if small:
        sid=next(sid for sid,coords in app.strings.items() if coords)
        coords=app.strings[sid][:2]
        app.panels={key:app.panels[key] for key in coords}
        app.strings={sid:coords};app.panel_blocks={c:b for c,b in app.panel_blocks.items() if c in coords}
        app.panel_orientations={c:v for c,v in app.panel_orientations.items() if c in coords}
        app.string_mppt_assignment={sid:app.string_mppt_assignment[sid]}
        app.hourly_consumption_profile={'start_date':'2026-01-01','end_date':'2026-01-01','hourly_kwh':[20.]*24,'imputed_indices':[]}
        app.hourly_weather_profile={};app.self_consumption_summary={};app.bess_summary={};app.two_bess_summary={}
        app.energy_source_signature=None
    return app

if __name__=='__main__':
    from energy_engine import freeze_app
    from engineering_report import export_report
    app=load(sys.argv[1],sys.argv[2] if len(sys.argv)>2 else None)
    target=Path(sys.argv[3]) if len(sys.argv)>3 else Path('report_qa.pdf')
    last=[-1]
    def progress(done,total):
        percent=int(100*done/max(1,total))
        if percent//10!=last[0]:print(f'{done}/{total}',flush=True);last[0]=percent//10
    export_report(freeze_app(app),target,progress)
    print(target)
