"""Persistence, recovery, undo and domain state at the application boundary."""
import copy
import datetime as dt
import json
import math
from pathlib import Path
import uuid
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from project_store import (EXTRA_STATE, MODEL_DEFAULTS, fingerprint, serial,
                           validate_project, write_project)

class SafeProjectMixin:
    def _install_project_guard(self):
        self.project_uid=uuid.uuid4().hex
        self._guard_ready=True;self._restoring=False;self._history=[];self._history_index=-1
        self._history_job=None;self._saved_signature=None
        from project_store import fingerprint
        self.layout_geometry={f'{c[0]},{c[1]}':fingerprint(self._panel_rect(c)) for c in self.panels}
        self._record_history();self._saved_signature=self._document_signature()
        self.root.protocol('WM_DELETE_WINDOW',self._close_project)
        self.root.bind('<Control-z>',self._undo_shortcut)
        self.root.bind('<Control-y>',self._redo_shortcut)
        self.root.bind('<Control-Shift-Z>',self._redo_shortcut)
        self.root.bind_all('<ButtonRelease-1>',self._queue_history,add='+')
        self.root.bind_all('<ButtonRelease-3>',self._queue_history,add='+')
        self.root.bind_all('<KeyRelease>',self._queue_history,add='+')
        self.root.bind_all('<FocusOut>',self._queue_history,add='+')
        self.root.after(600,self._poll_history)

    def _build_tab_file_tools(self):
        super()._build_tab_file_tools()
        ttk.Button(self.tab_file,text='Save as…',command=self.save_project_as).pack(side='left',padx=3)

    def _document_signature(self):
        return fingerprint(self._collect_project_data())

    def _confirm_unsaved(self):
        if not getattr(self,'_guard_ready',False) or self._document_signature()==self._saved_signature:return True
        answer=messagebox.askyesnocancel('Unsaved changes','Save changes before leaving this project?',parent=self.root)
        if answer is None:return False
        return self.save_project() if answer else True

    def _close_project(self):
        if getattr(self,'_task_running',False):
            self._cancel_task();messagebox.showinfo('Calculation','Cancellation requested. Close again once it finishes.');return
        if self._confirm_unsaved():self.root.destroy()

    def save_project_as(self):
        path=filedialog.asksaveasfilename(parent=self.root,title='Save project as',defaultextension='.json',filetypes=[('Project JSON','*.json')])
        if path:self.save_project(destination=path)

    def save_project(self,silent=False,destination=None):
        try:
            if hasattr(self,'txt_notes'):self.project_notes=self.txt_notes.get('1.0','end-1c')
            # Never block recovery of the whole project on an unfinished calculator field.
            self._capture_cable_inputs()
            data=self._collect_project_data()
            path=destination or self.current_project_filepath
            if silent:
                folder=Path(path).parent if path else Path(self.projects_dir)
                path=folder/'.recovery'/f'{self.project_uid}.json'
            elif not path:
                path=filedialog.asksaveasfilename(parent=self.root,initialdir=self.projects_dir,defaultextension='.json',filetypes=[('Project JSON','*.json')])
                if not path:return False
            data['project_name']=Path(path).stem if destination or not self.current_project_filepath and not silent else self.project_name
            saved=write_project(path,data,self.roof_pil_img,recovery=silent)
            if not silent:
                self.current_project_filepath=str(path);self.project_name=saved['project_name']
                self.roof_image_path=str(Path(path).parent/saved['roof_image_path']) if saved.get('roof_image_path') else None
                self._saved_signature=self._document_signature()
                self._remember_recent_project(str(path));self.lbl_project_info.configure(text=f'Active project: {self.project_name}')
                messagebox.showinfo('Saved','Project saved. Previous versions are retained in .backups.',parent=self.root)
            elif hasattr(self,'home_active_label'):self.home_active_label.configure(text=f'{self.project_name} — recovery copy saved')
            return True
        except Exception as exc:
            if not silent:messagebox.showerror('Save failed',str(exc),parent=self.root)
            elif hasattr(self,'home_active_label'):self.home_active_label.configure(text=f'Recovery save failed: {exc}')
            return False

    def _apply_document(self,data,filepath):
        data=validate_project(data)
        self.model_settings=copy.deepcopy(data['model_settings'])
        super()._load_project_file(filepath,data_override=data,quiet=True)
        for name in EXTRA_STATE:
            if name in data:setattr(self,name,copy.deepcopy(data[name]))
        result=data.get('shadow_result',{})
        self.shadow_result=copy.deepcopy(result) if result else {}
        if self.shadow_result:
            self.shadow_result['shadowed']={tuple(c) for c in result.get('shadowed',[])}
            self.shadow_result['shadow_pct']={tuple(map(int,c.split(','))):v for c,v in result.get('shadow_pct',{}).items()}
            for poly in self.shadow_result.get('shadow_polygons',[]):
                if isinstance(poly.get('coord'),list):poly['coord']=tuple(poly['coord'])
        self.panel_uids={tuple(map(int,c.split(','))):v for c,v in data.get('panel_uids',{}).items()}
        self.layout_geometry=data.get('layout_geometry') or {f'{c[0]},{c[1]}':fingerprint(self._panel_rect(c)) for c in self.panels}
        self.connection_review_required=list(data.get('connection_review_required',[]))
        # Old projects cannot retain the preceding project's shade calculation.
        self.shadow_simulation_results=copy.deepcopy(data.get('shadow_simulation_results',{}))
        self.shadow_source_signature=data.get('shadow_source_signature')
        for key in ('timeline','intervals'):
            if key in self.shadow_simulation_results:
                seq=self.shadow_simulation_results[key]
                count=2 if key=='intervals' else 1
                self.shadow_simulation_results[key]=[tuple(dt.datetime.fromisoformat(v) if i<count and isinstance(v,str) else v for i,v in enumerate(row)) for row in seq]
        for result in self.shadow_simulation_results.get('results',[]):
            if isinstance(result.get('coord'),list):result['coord']=tuple(result['coord'])
        self.cable_network_routes={};self.cable_routes_calculated=False
        self._refresh_notes();self.draw_grid()

    def _load_project_file(self,filepath,**kwargs):
        if getattr(self,'_task_running',False):messagebox.showinfo('Calculation','Cancel the calculation before opening another project.');return False
        try:
            data=validate_project(json.loads(Path(filepath).read_text(encoding='utf-8')))
        except Exception as exc:messagebox.showerror('Invalid project',str(exc),parent=self.root);return False
        if not self._confirm_unsaved():return False
        previous=copy.deepcopy(self._collect_project_data());old_path=self.current_project_filepath
        image=self.roof_pil_img;self._restoring=True
        try:
            self._apply_document(data,str(filepath))
            self._saved_signature=self._document_signature();self._history=[];self._history_index=-1
            self._record_history();super()._remember_recent_project(str(filepath));return True
        except Exception as exc:
            try:
                self._apply_document(previous,old_path or str(Path(self.projects_dir)/'Untitled.json'))
                self.current_project_filepath=old_path;self.roof_pil_img=image;self.draw_grid()
            except Exception as restore_exc:
                messagebox.showerror('Restore error',str(restore_exc),parent=self.root)
            messagebox.showerror('Import cancelled',str(exc),parent=self.root);return False
        finally:self._restoring=False

    def _remember_recent_project(self,path):
        if not getattr(self,'_restoring',False):super()._remember_recent_project(path)

    def _record_history(self):
        if not getattr(self,'_guard_ready',False):return
        self._history_job=None
        if hasattr(self,'txt_notes'):self.project_notes=self.txt_notes.get('1.0','end-1c')
        self._history_capturing=True
        try:
            self._capture_cable_inputs()
            data=copy.deepcopy(serial(self._collect_project_data()))
        finally:self._history_capturing=False
        if self._history_index>=0:
            previous=self._history[self._history_index][1]
            for key in ('hourly_consumption_profile','hourly_weather_profile','hourly_pv_kwh','self_consumption_summary','bess_summary','two_bess_summary','shadow_simulation_results'):
                if key in data and data[key]==previous.get(key):data[key]=previous[key]
        view={name:getattr(self,name,None) for name in ('zoom_level','cell_size_px','spreadsheet_zoom','diagram_show_electrical')}
        image=getattr(self,'roof_pil_img',None)
        sig=fingerprint((data,view,id(image)))
        if self._history_index>=0 and self._history[self._history_index][0]==sig:return
        self._history=self._history[:self._history_index+1]+[(sig,data,image,view)]
        self._history=self._history[-100:];self._history_index=len(self._history)-1
        self._update_history_buttons()

    def _restore_history(self,index):
        if getattr(self,'_task_running',False):return
        if not 0<=index<len(self._history):return
        path=self.current_project_filepath;image=self._history[index][2];view=self._history[index][3];self._restoring=True
        try:
            self._apply_document(copy.deepcopy(self._history[index][1]),path or str(Path(self.projects_dir)/'Untitled.json'))
            self.current_project_filepath=path;self.roof_pil_img=image;self._history_index=index
            for name,value in view.items():
                if value is not None:setattr(self,name,value)
            self._diagram_layout_applied=self._diagram_layout_signature() if self.diagram_nodes else None
            self._auto_fit=False;self._refresh_energy_workspace();self.draw_grid()
        finally:self._restoring=False

    def undo_project(self):
        self._record_history();self._restore_history(self._history_index-1)

    def redo_project(self):
        self._record_history();self._restore_history(self._history_index+1)

    def _undo_shortcut(self,event=None):
        self.undo_project();return 'break'

    def _redo_shortcut(self,event=None):
        self.redo_project();return 'break'

    def _queue_history(self,event=None):
        if not getattr(self,'_guard_ready',False) or getattr(self,'_restoring',False):return
        if self._history_job:self.root.after_cancel(self._history_job)
        self._history_job=self.root.after(300,self._record_history)

    def _poll_history(self):
        if not getattr(self,'_restoring',False) and not getattr(self,'_task_running',False):self._record_history()
        self.root.after(600,self._poll_history)

    def _install_responsive_ui(self):
        self._history_buttons=[]
        for ident in self.ribbon_notebook.tabs():
            tab=self.root.nametowidget(ident)
            for label,command in (('Undo',self.undo_project),('Redo',self.redo_project)):
                button=ttk.Button(tab,text=label,command=command);button.pack(side='left',padx=3)
                self._history_buttons.append((button,label))
        return super()._install_responsive_ui()

    def _shadow_signature(self):
        names=('roof_zones','panels','panel_width_mm','panel_height_mm','panel_tilt_deg','panel_azimuth_deg',
               'panel_orientations','px_per_mm','pylon_img_pos','pylon_ref_img_pos','pylon_height_mm',
               'pylon_width_mm','pylon_opacity','north_offset_deg','solar_latitude','solar_longitude',
               'solar_day','solar_month','solar_hour','solar_utc_offset','panel_pmax_w','panel_noct_c',
               'panel_temp_coeff_pct','strings','model_settings')
        return fingerprint({name:getattr(self,name,None) for name in names})

    def _shadow_current(self):return self.shadow_source_signature==self._shadow_signature()

    def draw_grid(self):
        if getattr(self,'_guard_ready',False):
            if self.shadow_result and self.shadow_result.get('source_signature')!=self._shadow_signature():self.shadow_result={}
            # Retain stable independent IDs for existing module coordinates.
            self.panel_uids={c:self.panel_uids.get(c,uuid.uuid4().hex) for c in self.panels}
            if not getattr(self,'_restoring',False):
                if self._history_job:self.root.after_cancel(self._history_job)
                self._history_job=self.root.after(300,self._record_history)
        result=super().draw_grid()
        self._update_history_buttons()
        return result

    def _update_history_buttons(self):
        for button,label in getattr(self,'_history_buttons',[]):
            available=(self._history_index>0 if label=='Undo' else self._history_index<len(self._history)-1) and not getattr(self,'_task_running',False)
            button.state(['!disabled' if available else 'disabled'])

    def _recompute_shadow(self):
        result=super()._recompute_shadow()
        result['source_signature']=self._shadow_signature()
        return result

    def _get_active_tab_index(self):
        # Keep callers compatible while decoupling the physical notebook order.
        names=('tab_file','tab_roof','tab_layout','tab_stringing','tab_equipment','tab_shadow',
               'tab_material','tab_diagram','tab_notes','tab_energy')
        selected=self.ribbon_notebook.select()
        for i,name in enumerate(names):
            if str(getattr(self,name,''))==selected:return i
        return super()._get_active_tab_index()

    def _show_model_settings(self):
        self._show_project_configuration()

    def _cancel_task(self):
        if getattr(self,'_active_job',None):self._active_job.cancel()

    def _energy_progress_start(self):
        if hasattr(self,'energy_progress'):
            self.energy_progress.stop()
            self.energy_progress.configure(mode='determinate',maximum=100,value=0)
        if hasattr(self,'self_status'):
            self.self_status.configure(text='Energy / BESS calculation in progress...')

    def _energy_progress_update(self,current,total):
        if not hasattr(self,'energy_progress'):
            return
        try:
            current=float(current);total=float(total)
        except (TypeError,ValueError):
            return
        if total>0:
            self.energy_progress.configure(mode='determinate',maximum=total)
            self.energy_progress['value']=max(0,min(current,total))
        else:
            self.energy_progress.configure(mode='indeterminate')
            self.energy_progress.start(12)

    def _energy_progress_finish(self,state='done'):
        if not hasattr(self,'energy_progress'):
            return
        self.energy_progress.stop()
        self.energy_progress.configure(mode='determinate')
        if state=='done':
            maximum=float(self.energy_progress.cget('maximum') or 100)
            self.energy_progress['value']=maximum
        else:
            self.energy_progress['value']=0

    def _start_job(self,work,complete,label,signature=None,on_progress=None,on_failure=None,home_progress=False):
        if getattr(self,'_task_running',False):
            messagebox.showinfo('Calculation','A task is already running. Cancel it before starting another.');return
        from async_jobs import Job,Cancelled
        import queue
        self._task_running=True;self._update_history_buttons();self._active_job=Job(work)
        is_energy_job=(label=='Energy calculation')
        if is_energy_job:self._energy_progress_start()
        if home_progress and hasattr(self,'_home_task_start'):self._home_task_start(label)
        def poll():
            try:
                while True:
                    kind,payload=self._active_job.messages.get_nowait()
                    if kind=='progress':
                        current=payload[0] if len(payload)>0 else 0
                        total=payload[1] if len(payload)>1 else 0
                        detail=payload[2] if len(payload)>2 else None
                        if is_energy_job:
                            self._energy_progress_update(current,total)
                        else:
                            self.self_status.configure(text=f'{label}: {current}/{total}')
                        if home_progress and hasattr(self,'_home_task_progress_update'):
                            self._home_task_progress_update(current,total,detail)
                        if on_progress:on_progress(*payload)
                    else:
                        self._task_running=False;self._update_history_buttons()
                        if kind=='done':
                            if signature is not None and signature!=self._energy_signature():
                                self.self_status.configure(text='Inputs changed during calculation. Calculate again.')
                                if is_energy_job:self._energy_progress_finish('failed')
                                if home_progress and hasattr(self,'_home_task_finish'):self._home_task_finish('Inputs changed - export again',True)
                                return
                            try:
                                complete(payload)
                                if is_energy_job:
                                    self._energy_progress_finish('done')
                                    self.self_status.configure(text='Energy / BESS calculation complete.')
                                if home_progress and hasattr(self,'_home_task_finish'):self._home_task_finish(label+' complete')
                            except Exception as exc:
                                self.self_status.configure(text='Result display failed.')
                                if is_energy_job:self._energy_progress_finish('failed')
                                if home_progress and hasattr(self,'_home_task_finish'):self._home_task_finish(label+' failed',True)
                                messagebox.showerror(label,str(exc),parent=self.root)
                        elif isinstance(payload,Cancelled):
                            if on_failure:on_failure()
                            self.self_status.configure(text='Calculation cancelled.')
                            if is_energy_job:self._energy_progress_finish('cancelled')
                            if home_progress and hasattr(self,'_home_task_finish'):self._home_task_finish(label+' cancelled',True)
                        else:
                            if on_failure:on_failure()
                            self.self_status.configure(text='Calculation failed.')
                            if is_energy_job:self._energy_progress_finish('failed')
                            if home_progress and hasattr(self,'_home_task_finish'):self._home_task_finish(label+' failed',True)
                            messagebox.showerror(label,str(payload),parent=self.root)
                        return
            except queue.Empty:pass
            self.root.after(80,poll)
        self.root.after(80,poll)

    def _build_self_consumption_tab(self):
        super()._build_self_consumption_tab()
        ttk.Button(self.tab_energy,text='Cancel calculation',command=self._cancel_task).pack(side='left',padx=4)
        self.energy_progress=ttk.Progressbar(
            self.tab_energy,orient='horizontal',mode='determinate',
            maximum=100,value=0,length=180
        )
        self.energy_progress.pack(side='left',padx=(8,4),pady=2)

    def _calculate_self_consumption(self):
        from energy_engine import freeze_app,calculate
        try:
            self._sync_module_power()
            issues=self._layout_issues()
            if issues:raise ValueError('Correct the panel layout before calculating: '+ '; '.join(issues[:3]))
            profile=self.hourly_consumption_profile
            if not profile:raise ValueError('Import consumption first.')
            numeric={key:float(entry.get().replace(',','.')) for key,entry in self.bess_entries.items()}
            factor=float(self.self_ac_entry.get().replace(',','.'))
            if not math.isfinite(factor) or not 0<factor<=1:raise ValueError('AC factor must be greater than zero and at most one.')
            from battery_dispatch import BatterySettings
            BatterySettings(**numeric,initial_soc_pct=numeric['soc_min_pct'],auxiliary_kw=self.model_settings.get('bess_auxiliary_kw',0),annual_degradation_pct=self.model_settings.get('bess_annual_degradation_pct',0)).validate()
            signature=self._energy_signature();frozen=freeze_app(self)
            weather=copy.deepcopy(self.hourly_weather_profile)
            def work(report):return calculate(frozen,copy.deepcopy(profile),factor,numeric,weather,report)
            def complete(result):
                for name,value in result.items():setattr(self,name,value)
                self.energy_source_signature=signature;self._refresh_energy_workspace();self.draw_grid()
            self._start_job(work,complete,'Energy calculation',signature)
        except Exception as exc:messagebox.showerror('Energy calculation',str(exc),parent=self.root)

    def _download_historical_weather(self):
        from urllib.parse import urlencode
        from urllib.request import Request,urlopen
        import tempfile,os
        from self_consumption import read_open_meteo_json,orientation_key
        try:
            profile=copy.deepcopy(self.hourly_consumption_profile)
            if not profile:raise ValueError('Import consumption first.')
            start=(dt.date.fromisoformat(profile['start_date'])-dt.timedelta(days=1)).isoformat()
            end=(dt.date.fromisoformat(profile['end_date'])+dt.timedelta(days=1)).isoformat()
            az=(self.panel_azimuth_deg-180+180)%360-180
            params={'latitude':self.solar_latitude,'longitude':self.solar_longitude,'start_date':start,'end_date':end,
                'hourly':'global_tilted_irradiance,temperature_2m','tilt':self.panel_tilt_deg,'azimuth':az,
                'timezone':self.model_settings['timezone'],'models':'best_match'}
            signature=self._energy_signature()
            orientations=sorted({(self.panel_orientations.get(c,{}).get('tilt_deg',self.panel_tilt_deg),
                self.panel_orientations.get(c,{}).get('azimuth_deg',self.panel_azimuth_deg)) for c in self.panels})
            if not orientations:orientations=[(self.panel_tilt_deg,self.panel_azimuth_deg)]
            def work(report):
                profiles={}
                for index,(tilt,orientation_az) in enumerate(orientations):
                    report(index,len(orientations))
                    query={**params,'tilt':tilt,'azimuth':(orientation_az-180+180)%360-180}
                    request=Request('https://archive-api.open-meteo.com/v1/archive?'+urlencode(query),headers={'User-Agent':'PV-App-R13/1.0'})
                    with urlopen(request,timeout=20) as response:payload=response.read(10_000_000)
                    with tempfile.NamedTemporaryFile(suffix='.json',delete=False) as tmp:tmp.write(payload);path=tmp.name
                    try:weather=read_open_meteo_json(path,profile,timezone=query['timezone'])
                    finally:os.unlink(path)
                    weather['query']={'latitude':query['latitude'],'longitude':query['longitude'],'tilt_deg':tilt,'azimuth_deg_from_south':query['azimuth']}
                    weather['source_filename']='Open-Meteo Historical API'
                    profiles[orientation_key((tilt,orientation_az))]=weather
                report(len(orientations),len(orientations));return {'orientations':profiles}
            def complete(weather):
                self.hourly_weather_profile=weather;self.hourly_pv_kwh=[];self.self_consumption_summary={};self.bess_summary={};self.two_bess_summary={}
                self.self_status.configure(text='Weather imported. Calculate energy.');self.draw_grid()
            self._start_job(work,complete,'Weather download',signature)
        except Exception as exc:messagebox.showerror('Weather',str(exc),parent=self.root)

    def _renumber_panels(self):
        self.panels={coord:i for i,coord in enumerate(sorted(self.panels,key=lambda c:self.panels[c]),1)}
        self._invalidate_cable_routes();self.draw_grid()

    def _build_tab_layout_tools(self):
        super()._build_tab_layout_tools()
        ttk.Button(self.tab_layout,text='Renumber panels',command=self._renumber_panels).pack(side='left',padx=4)

    def _import_historical_weather(self):
        from self_consumption import (read_open_meteo_json, read_pvgis_tmy_json,
                                      is_pvgis_tmy_json, orientation_key)
        from tkinter import simpledialog
        path=filedialog.askopenfilename(
            title='Import historical weather',
            filetypes=[('Weather JSON','*.json'),('All files','*.*')])
        if not path:return
        try:
            if not self.hourly_consumption_profile:raise ValueError('Import consumption first.')
            raw=json.loads(Path(path).read_text(encoding='utf-8'))
            if is_pvgis_tmy_json(raw):
                orientations=sorted({
                    (self.panel_orientations.get(c,{}).get('tilt_deg',self.panel_tilt_deg),
                     self.panel_orientations.get(c,{}).get('azimuth_deg',self.panel_azimuth_deg))
                    for c in self.panels
                })
                if not orientations:orientations=[(self.panel_tilt_deg,self.panel_azimuth_deg)]
                self.hourly_weather_profile=read_pvgis_tmy_json(
                    path,self.hourly_consumption_profile,orientations,
                    self._compute_solar_position,timezone=self.model_settings['timezone'])
            else:
                values={}
                for key,label,default in (
                    ('latitude','Source latitude',self.solar_latitude),
                    ('longitude','Source longitude',self.solar_longitude),
                    ('tilt_deg','Source panel tilt (degrees)',self.panel_tilt_deg),
                    ('azimuth_deg','Source azimuth from north (degrees)',self.panel_azimuth_deg)):
                    value=simpledialog.askfloat(
                        'Weather source metadata',label+' — verify against the source file',
                        initialvalue=default,parent=self.root)
                    if value is None:return
                    if not math.isfinite(value):raise ValueError('Metadata must be finite.')
                    values[key]=value
                item=read_open_meteo_json(
                    path,self.hourly_consumption_profile,
                    timezone=self.model_settings['timezone'])
                item['query']={k:v for k,v in values.items() if k!='azimuth_deg'}
                item['query']['azimuth_deg_from_south']=(values['azimuth_deg']-180+180)%360-180
                profiles=copy.deepcopy(self.hourly_weather_profile.get('orientations',{}))
                if self.hourly_weather_profile.get('query'):
                    old=self.hourly_weather_profile;q=old['query']
                    profiles[orientation_key((q['tilt_deg'],(q['azimuth_deg_from_south']+180)%360))]=old
                profiles[orientation_key((values['tilt_deg'],values['azimuth_deg']))]=item
                self.hourly_weather_profile={'orientations':profiles}
            self.hourly_pv_kwh=[];self.self_consumption_summary={};self.bess_summary={};self.two_bess_summary={}
            source='PVGIS TMY' if is_pvgis_tmy_json(raw) else 'historical weather'
            self.self_status.configure(text=f'{source} imported. Calculate energy.');self.draw_grid()
        except Exception as exc:messagebox.showerror('Weather import',str(exc),parent=self.root)

    def _export_engineering_report(self):
        import tempfile,shutil
        from energy_engine import freeze_app
        from engineering_report import export_report
        path=filedialog.asksaveasfilename(title='Engineering project report',defaultextension='.pdf',filetypes=[('PDF','*.pdf')])
        if not path:return
        if getattr(self,'_task_running',False):
            messagebox.showinfo('Export','Wait for or cancel the current calculation.');return
        # Keep progress in the main Home workspace; never grow the ribbon/toolbar.
        try:
            self.ribbon_notebook.select(self.tab_file)
            if hasattr(self,'_show_home'):self._show_home()
        except (tk.TclError,AttributeError):
            pass
        target=Path(path);frozen=freeze_app(self);source_signature=self._energy_signature()
        temporary=Path(tempfile.mkdtemp(prefix='.pv_report_',dir=target.parent))
        def work(report):
            try:
                report(0,1);export_report(frozen,temporary/target.name,progress=report);report(1,1)
                return temporary
            except Exception:
                shutil.rmtree(temporary,ignore_errors=True);raise
        def complete(folder):
            entries=list(folder.iterdir());installed=[];previous=[]
            backup=target.parent/'.backups'/('report_'+dt.datetime.now().strftime('%Y%m%dT%H%M%S%f'))
            try:
                if source_signature!=self._energy_signature():raise ValueError('Project inputs changed during export. Export again.')
                backup.mkdir(parents=True,exist_ok=False)
                for file in entries:
                    destination=target.parent/file.name
                    if destination.exists():
                        destination.replace(backup/file.name);previous.append((backup/file.name,destination))
                for file in entries:
                    destination=target.parent/file.name;file.replace(destination);installed.append(destination)
                messagebox.showinfo('Report exported','PDF, LaTeX source, figures and input snapshot exported together.')
            except Exception:
                for file in installed:
                    if file.is_dir():shutil.rmtree(file)
                    elif file.exists():file.unlink()
                for saved,destination in previous:saved.replace(destination)
                raise
            finally:shutil.rmtree(folder,ignore_errors=True)
        self._start_job(work,complete,'Generating engineering report',on_failure=lambda:shutil.rmtree(temporary,ignore_errors=True),home_progress=True)
