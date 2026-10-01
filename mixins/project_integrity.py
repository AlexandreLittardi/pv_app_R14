"""Keep equipment, diagrams and saved simulation provenance consistent."""
import hashlib
import json
import tkinter as tk
from tkinter import ttk, messagebox
from project_validation import normalize_project, sync_diagram, audit_project, number
from energy_economics import DEFAULTS, validate_settings
from detailed_electrical import default_design, normalise_design

EXTRA_FIELDS = ('model_settings','cable_inventory','equipment_links','shadow_source_signature','hourly_consumption_profile','hourly_pv_kwh','hourly_weather_profile',
                'self_consumption_summary','bess_summary','two_bess_summary',
                'economic_settings','grid_connection_settings','electrical_route_plan_3d',
                'electrical_checks','routing_settings','energy_source_signature','electrical_design','energy_input_settings')

class ProjectIntegrityMixin:
    def _init_energy_state(self):
        self.hourly_consumption_profile=None;self.hourly_weather_profile=None
        self.hourly_pv_kwh=[]
        self.self_consumption_summary={};self.bess_summary={};self.two_bess_summary={}
        self.economic_settings=dict(DEFAULTS)
        self.grid_connection_settings={'existing_contract_kw':507.,'export_limit_kw':300.,'export_limit_status':'requested_not_approved'}
        self.electrical_route_plan_3d={};self.electrical_checks={}
        self.electrical_design=default_design()
        self.routing_settings={'inverter_height_m':0.,'reserve_per_pole_m':2.}
        self.energy_input_settings={}
        self.energy_source_signature=None
        self._diagram_signature=None

    def _project_snapshot(self):
        data={name:getattr(self,name) for name in (
            'project_name','roof_polygons','routing_settings','blocks','string_mppt_assignment','inverter_positions','roof_zones','cable_paths',
            'panel_width_mm','panel_height_mm','panel_pmax_w','panel_efficiency_pct','px_per_mm',
            'material_categories','diagram_nodes','diagram_links','electrical_checks','model_settings','cable_calc_params','cable_string_params','cable_mass_by_section','cable_inventory','equipment_links')}
        data.update(panels={f'{r},{c}':v for (r,c),v in self.panels.items()},
                    strings={sid:[f'{r},{c}' for r,c in coords] for sid,coords in self.strings.items()},
                    panel_blocks={f'{r},{c}':v for (r,c),v in self.panel_blocks.items()},
                    continuous_panel_numbers=self.var_continuous_numbers.get())
        return data

    def _sync_module_power(self):
        rows=self.material_categories.get('modules',{}).get('rows',[])
        if len(rows)==1:
            p=number(rows[0].get('Pmax (W)'))
            if p is not None and p>0:self.panel_pmax_w=p
        area=self.panel_width_mm*self.panel_height_mm/1e6
        if area>0:self.panel_efficiency_pct=self.panel_pmax_w/area/10
        if hasattr(self,'diagram_electrical_specs'):
            self.diagram_electrical_specs['pmax_w']=self.panel_pmax_w
            if len(rows)==1:
                for field,column in [('voc_v','Voc (V)'),('vmp_v','Vmp (V)'),('imp_a','Imp (A)'),('isc_a','Isc (A)')]:
                    v=number(rows[0].get(column))
                    if v is not None and v>0:self.diagram_electrical_specs[field]=v
                    else:self.diagram_electrical_specs.pop(field,None)
            else:
                for field in ('voc_v','vmp_v','imp_a','isc_a'):self.diagram_electrical_specs.pop(field,None)
        for attr,value in [('entry_panel_pmax',self.panel_pmax_w),('entry_panel_efficiency',self.panel_efficiency_pct)]:
            entry=getattr(self,attr,None)
            if entry is not None and not getattr(self,'_history_capturing',False):
                entry.delete(0,tk.END);entry.insert(0,str(value))

    def _read_shadow_params_from_entries(self,show_errors=False):
        result=super()._read_shadow_params_from_entries(show_errors=show_errors)
        if hasattr(self,'material_categories'):self._sync_module_power()
        return result

    def _prepare_project_save(self):
        self._sync_module_power()
        self.energy_input_settings={'ac_factor':self.self_ac_entry.get(), 'bess':{k:e.get() for k,e in self.bess_entries.items()}}
        return {k:getattr(self,k) for k in EXTRA_FIELDS}

    def _load_energy_state(self,data):
        self._init_energy_state()
        for key in EXTRA_FIELDS:
            if key in data:setattr(self,key,data[key])
        # Translate application-generated descriptors from older saved projects.
        methods={'cielo sereno + ombra':'clear-sky estimate + shading',
                 'meteo storico orario + ombra':'historical hourly weather + shading'}
        self.self_consumption_summary['method']=methods.get(
            self.self_consumption_summary.get('method'),
            self.self_consumption_summary.get('method','clear-sky estimate + shading'))
        for summary in (self.bess_summary,self.two_bess_summary):
            cfg=summary.get('battery_settings',{})
            if 'model' in cfg:cfg['model']=cfg['model'].replace('modello provvisorio','provisional model')
        if self.hourly_consumption_profile:
            convention=('explicit offset timestamps' if self.hourly_consumption_profile.get('timestamps') else 'legacy 24 slots/day; DST approximate')
            self.hourly_consumption_profile.setdefault('hour_convention',convention)
        self.electrical_design=normalise_design(self.electrical_design)
        self.economic_settings=validate_settings(self.economic_settings)
        limit=number(self.grid_connection_settings.get('export_limit_kw'))
        if limit is None or limit<0:raise ValueError('Invalid grid export limit')
        self.grid_connection_settings['export_limit_kw']=limit
        self._sync_module_power()
        for key,entry in self.bess_entries.items():
            entry.delete(0,tk.END);entry.insert(0,str(self.energy_input_settings.get('bess',{}).get(key,self.bess_summary.get('battery_settings',{}).get(key,self._bess_defaults[key]))))
        self.self_ac_entry.delete(0,tk.END);self.self_ac_entry.insert(0,str(self.energy_input_settings.get('ac_factor',self.self_consumption_summary.get('ac_factor',.9))))
        if self.hourly_pv_kwh and not self.energy_source_signature:
            # Legacy curves have no reliable geometry provenance. Never label them current.
            self.self_status.configure(text='Saved results: recalculate to validate against this layout.')
        else:self.self_status.configure(text='Energy profiles loaded.' if self.hourly_consumption_profile else 'Import hourly consumption.')

    def _energy_signature(self):
        self._sync_module_power()
        d=self._project_snapshot()
        keep={k:d[k] for k in ('panels','strings','string_mppt_assignment','blocks','inverter_positions',
                               'roof_zones','panel_width_mm','panel_height_mm','panel_pmax_w','px_per_mm')}
        for k in ('panel_tilt_deg','panel_azimuth_deg','panel_temp_coeff_pct','panel_noct_c','pylon_img_pos',
                  'pylon_ref_img_pos','pylon_height_mm','pylon_width_mm','pylon_opacity','north_offset_deg',
                  'solar_latitude','solar_longitude','hourly_consumption_profile','hourly_weather_profile',
                  'grid_connection_settings','model_settings','equipment_links','material_categories','cable_string_params'):
            keep[k]=getattr(self,k,None)
        keep['panel_orientations']={str(k):v for k,v in self.panel_orientations.items()}
        keep['ac_factor']=self.self_ac_entry.get()
        keep['bess_inputs']={k:e.get() for k,e in self.bess_entries.items()}
        return hashlib.sha256(json.dumps(keep,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

    def _require_current_energy(self):
        if self.energy_source_signature!=self._energy_signature():
            messagebox.showwarning('Results need recalculation','Layout, equipment, weather or inputs changed, or this legacy curve has no provenance. Calculate the three options first.',parent=self.root)
            return False
        return True

    def draw_grid(self):
        if hasattr(self,'diagram_nodes') and hasattr(self,'var_continuous_numbers'):
            signature=repr((self.strings,self.string_mppt_assignment,self.blocks))
            if signature!=self._diagram_signature:
                d=self._project_snapshot();sync_diagram(d)
                self.diagram_nodes=d['diagram_nodes'];self.diagram_links=d['diagram_links']
                self._diagram_signature=signature
                if hasattr(self,'diagram_list'):self._refresh_diagram_list()
        return super().draw_grid()

    def _show_electrical_audit(self):
        win=tk.Toplevel(self.root);win.title('Electrical checks — datasheet inputs')
        pages=ttk.Notebook(win);pages.pack(fill=tk.BOTH,expand=True)
        fields=[('Module Voc STC (V)','module_voc_v'),('Module Vmp STC (V)','module_vmp_v'),
                ('Module Imp STC (A)','module_imp_a'),('Module Isc STC (A)','module_isc_a'),
                ('Voc temperature coefficient (%/°C)','voc_temp_coeff_pct'),('Minimum design temperature (°C)','min_temperature_c'),
                ('Inverter maximum DC voltage (V)','inverter_max_dc_v'),('MPPT minimum voltage (V)','mppt_min_v'),
                ('MPPT maximum voltage (V)','mppt_max_v'),('MPPT maximum operating current (A)','mppt_max_current_a'),
                ('MPPT maximum short-circuit current (A)','mppt_max_isc_a'),('Maximum PV input per inverter (kW)','inverter_max_pv_kw')]
        entries={}
        for start,name in [(0,'Module'),(6,'Inverter')]:
            frame=ttk.Frame(pages,padding=10);pages.add(frame,text=name)
            for i,(label,key) in enumerate(fields[start:start+6]):
                ttk.Label(frame,text=label).grid(row=i,column=0,sticky='w',pady=4)
                e=ttk.Entry(frame,width=12);e.insert(0,str(self.electrical_checks.get(key,'')));e.grid(row=i,column=1,padx=6);entries[key]=e
        result=ttk.Frame(pages,padding=8);pages.add(result,text='Results')
        text=tk.Text(result,wrap='word',width=55,height=14);text.pack(fill=tk.BOTH,expand=True)
        confirmed=tk.BooleanVar(value=bool(self.electrical_checks.get('dimensions_confirmed')))
        ttk.Checkbutton(win,text='Module dimensions confirmed against final datasheet',variable=confirmed).pack(anchor='w',padx=8)
        def run():
            values={}
            for key,e in entries.items():
                raw=e.get().strip()
                if raw:
                    v=number(raw)
                    if v is None or (key not in ('voc_temp_coeff_pct','min_temperature_c') and v<=0):
                        messagebox.showerror('Invalid rating',key,parent=win);return
                    values[key]=v
            values['dimensions_confirmed']=confirmed.get();self.electrical_checks=values
            issues=audit_project(self._project_snapshot())
            text.configure(state='normal');text.delete('1.0','end');text.insert('1.0','\n\n'.join(issues));text.configure(state='disabled');pages.select(result)
        ttk.Button(win,text='Save inputs and check',command=run).pack(pady=6)
        run();self._fit_dialog(win,600,460)
