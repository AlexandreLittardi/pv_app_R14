"""Freeze project inputs and compute energy without calling a Tk widget."""
import copy
from self_consumption import production_from_program,balance
from battery_dispatch import BatterySettings,simulate_three_options

class Value:
    def __init__(self,value):self.value=value
    def get(self):return self.value
    def delete(self,*args):self.value=''
    def insert(self,index,value):self.value=value

def freeze_app(app):
    def plain(value):
        if value is None or isinstance(value,(int,float,str,bool)):return True
        if isinstance(value,dict):return all(plain(k) and plain(v) for k,v in value.items())
        if isinstance(value,(list,tuple,set)):return all(plain(v) for v in value)
        import datetime
        return isinstance(value,(datetime.date,datetime.datetime))
    frozen=type(app).__new__(type(app))
    for name,value in vars(app).items():
        if name.startswith(('_history','_toolbar','_active_job')):continue
        if plain(value):
            try:setattr(frozen,name,copy.deepcopy(value))
            except (TypeError,ValueError):pass
    # Raster assets are part of a report snapshot, not Tk widgets.
    from PIL import Image
    frozen.roof_pil_img=app.roof_pil_img.copy() if getattr(app,'roof_pil_img',None) is not None else None
    import tkinter as tk
    from tkinter import ttk
    for name,value in vars(app).items():
        if isinstance(value,(Value,tk.Variable,tk.Entry,ttk.Entry,ttk.Combobox)):
            setattr(frozen,name,Value(value.get()))
    frozen.bess_entries={key:Value(entry.get()) for key,entry in getattr(app,'bess_entries',{}).items()}
    frozen.var_continuous_numbers=Value(app.var_continuous_numbers.get())
    return frozen

def calculate(app,profile,ac_factor,numeric,weather,progress):
    settings=app.model_settings
    pv=production_from_program(app,profile,ac_factor,progress,weather)
    limit=app.grid_connection_settings['export_limit_kw']
    base=balance(profile,pv,limit)
    battery=BatterySettings(**numeric,initial_soc_pct=numeric['soc_min_pct'],
                           auxiliary_kw=settings.get('bess_auxiliary_kw',0),
                           annual_degradation_pct=settings.get('bess_annual_degradation_pct',0))
    options=simulate_three_options(profile,pv,battery,limit)
    comparison={}
    if weather:
        sky=balance(profile,production_from_program(app,profile,ac_factor,progress),limit)
        comparison={'clear_sky_annual_kwh':sky['annual']['pv_kwh'],
            'weather_to_clear_sky_pct':100*base['annual']['pv_kwh']/sky['annual']['pv_kwh'] if sky['annual']['pv_kwh'] else 0,
            'monthly_correction_pct':{m:100*r['pv_kwh']/sky['monthly'][m]['pv_kwh'] if sky['monthly'][m]['pv_kwh'] else 0 for m,r in base['monthly'].items()}}
    return {'hourly_pv_kwh':pv,'self_consumption_summary':{'annual':base['annual'],'monthly':base['monthly'],
        'ac_factor':ac_factor,'export_limit_kw':limit,'comparison':comparison,
        'method':'historical hourly weather + shading' if weather else 'clear-sky estimate + shading'},
        'bess_summary':{'annual':options['one_bess']['annual'],'monthly':options['one_bess']['monthly'],'battery_settings':options['one_bess']['settings']},
        'two_bess_summary':{'annual':options['two_bess']['annual'],'monthly':options['two_bess']['monthly'],'battery_settings':options['two_bess']['settings']}}
