"""Scrollable project model settings, with explicit equipment and inventory inputs."""
import copy
import json
import math
import tkinter as tk
from tkinter import ttk, messagebox
from zoneinfo import ZoneInfo
from project_store import MODEL_DEFAULTS, validate_project


def show_settings(app):
    win=tk.Toplevel(app.root);win.title('Project model settings');win.geometry('780x650')
    tabs=ttk.Notebook(win);tabs.pack(fill='both',expand=True,padx=10,pady=10)
    general=ttk.Frame(tabs);equipment=ttk.Frame(tabs);advanced=ttk.Frame(tabs)
    for page,label in ((general,'Models'),(equipment,'Inverters'),(advanced,'Inventory / obstacles / exclusions')):tabs.add(page,text=label)
    canvas=tk.Canvas(general,highlightthickness=0);scroll=ttk.Scrollbar(general,command=canvas.yview)
    scroll.pack(side='right',fill='y');canvas.pack(fill='both',expand=True);canvas.configure(yscrollcommand=scroll.set)
    body=ttk.Frame(canvas);item=canvas.create_window(0,0,window=body,anchor='nw')
    body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width))
    saved={**MODEL_DEFAULTS,**app.model_settings};entries={}
    choices={'imputation':('previous_week','reject','zero'),'shadow_model':('geometric','bypass_estimate')}
    labels={'timezone':'IANA time zone','imputation':'Missing daily consumption','shadow_model':'Shading estimate',
        'bypass_groups':'Bypass groups per module','module_gap_x_mm':'Horizontal module gap (mm)',
        'module_gap_y_mm':'Vertical module gap (mm)','edge_clearance_mm':'Zone edge clearance (mm)',
        'bess_auxiliary_kw':'Auxiliary demand per BESS (kW)','bess_annual_degradation_pct':'BESS capacity loss (% / year)',
        'bess_lifetime_years':'Economic horizon (years)','annual_maintenance_eur':'Maintenance per BESS (€ / year)',
        'discount_rate_pct':'Discount rate (%)'}
    for i,(key,label) in enumerate(labels.items()):
        ttk.Label(body,text=label).grid(row=i,column=0,sticky='w',padx=10,pady=6)
        entry=ttk.Combobox(body,values=choices[key],state='readonly') if key in choices else ttk.Entry(body)
        entry.set(str(saved[key])) if key in choices else entry.insert(0,str(saved[key]))
        entry.grid(row=i,column=1,sticky='ew',padx=10,pady=6);entries[key]=entry
    body.columnconfigure(1,weight=1)
    ttk.Label(body,text='Zero gaps preserve the existing layout. Regenerate panels after changing gaps or exclusions; altered modules require string reconnection. Bypass mode is a conservative estimate, not an I–V simulation.',wraplength=620).grid(row=len(labels),columnspan=2,padx=10,pady=10,sticky='w')
    ttk.Label(equipment,text='Link each inverter to its equipment-sheet row. Row numbers start at 1. Blank retains the saved equipment record. Terminal height is above ground (m).',wraplength=680).pack(anchor='w',padx=10,pady=10)
    rows=app.material_categories.get('inverters',{}).get('rows',[]);links={};heights={}
    ef=ttk.Frame(equipment);ef.pack(fill='both',expand=True)
    for i,block in enumerate(app.blocks):
        ttk.Label(ef,text=block).grid(row=i,column=0,padx=10,pady=4)
        value=app.equipment_links.get(block)
        e=ttk.Combobox(ef,values=['']+[str(n+1) for n in range(len(rows))],width=10,state='readonly');e.set('' if value is None else str(value+1));e.grid(row=i,column=1);links[block]=e
        h=ttk.Entry(ef,width=12);h.insert(0,str(app.inverter_positions.get(block,{}).get('terminal_height_m','')));h.grid(row=i,column=2,padx=10);heights[block]=h
    texts={}
    examples={'cable_inventory':'[{"name":"AC feeder", "length_m":20, "linear_mass_kg_m":0.6, "quantity":1}]',
        'shadow_obstacles':'[{"footprint_px":[[0,0],[10,0],[10,10],[0,10]], "height_mm":6000, "opacity":1}]',
        'layout_exclusions':'[[[0,0],[10,0],[10,10],[0,10]]]'}
    for key,label in (('cable_inventory','Additional cables (DC inter-module, AC, earth): length of one cable × quantity × kg/m'),('shadow_obstacles','Additional obstacles: image-pixel footprint, height in mm, opacity 0–1'),('layout_exclusions','Excluded installation polygons: vertices in image pixels')):
        ttk.Label(advanced,text=label,wraplength=680).pack(anchor='w',padx=8,pady=(8,2))
        text=tk.Text(advanced,height=4,wrap='word');text.pack(fill='both',expand=True,padx=8)
        text.insert('1.0',json.dumps(app.cable_inventory if key=='cable_inventory' else saved.get(key,[]),indent=2));texts[key]=text
        ttk.Label(advanced,text='Example: '+examples[key],wraplength=680).pack(anchor='w',padx=8)
    def apply():
        try:
            values=copy.deepcopy(saved)
            for key,e in entries.items():
                raw=e.get().strip();values[key]=raw if key in ('timezone','imputation','shadow_model') else float(raw.replace(',','.'))
            for key in ('bypass_groups','bess_lifetime_years'):
                if values[key]!=int(values[key]):raise ValueError(f'{key}: enter a whole number.')
                values[key]=int(values[key])
            inventory=json.loads(texts['cable_inventory'].get('1.0','end'))
            for key in ('shadow_obstacles','layout_exclusions'):values[key]=json.loads(texts[key].get('1.0','end'))
            data=app._collect_project_data();data['model_settings']=values;data['cable_inventory']=inventory;validate_project(data)
            newlinks={block:int(e.get())-1 for block,e in links.items() if e.get()}
            newheights={block:float(e.get().replace(',','.')) for block,e in heights.items() if e.get().strip()}
            if any(not math.isfinite(v) or v<0 for v in newheights.values()):raise ValueError('Terminal heights must be finite and nonnegative.')
            app.model_settings=values;app.cable_inventory=inventory;app.equipment_links=newlinks
            for block in heights:
                if block in app.inverter_positions:
                    app.inverter_positions[block].pop('terminal_height_m',None)
                    if block in newheights:app.inverter_positions[block]['terminal_height_m']=newheights[block]
            app.economic_settings.update(annual_maintenance_eur=values['annual_maintenance_eur'],discount_rate_pct=values['discount_rate_pct'],annual_degradation_pct=values['bess_annual_degradation_pct'],lifetime_years=values['bess_lifetime_years'])
            app._invalidate_cable_routes();app.draw_grid();win.destroy()
        except (ValueError,TypeError,KeyError) as exc:messagebox.showerror('Settings',str(exc),parent=win)
    ttk.Button(win,text='Apply settings',command=apply).pack(pady=8)
