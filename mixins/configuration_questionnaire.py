"""All engineering inputs in one scrollable questionnaire; one atomic Apply."""
import copy
import json
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from pathlib import Path
from configuration_form import questionnaire_fields,questionnaire_required,prepare,get,put,parse,apply_values

DISPLAY_CHOICES={'previous_week':'Previous week average','reject':'Reject missing values','zero':'Fill with zero',
    'geometric':'Geometric optical loss','bypass_estimate':'Conservative bypass estimate'}

def show_questionnaire(app):
    if getattr(app,'_task_running',False):
        messagebox.showinfo('Configuration','Wait for or cancel the current calculation.',parent=app.root);return
    existing=getattr(app,'_configuration_questionnaire',None)
    if existing is not None and existing.winfo_exists():existing.lift();return
    win=tk.Toplevel(app.root);win.title('Project configuration — engineering questionnaire')
    app._configuration_questionnaire=win;app._fit_dialog(win,1000,780)
    win.transient(app.root);win.grab_set()
    header=ttk.Frame(win,padding=12);header.pack(fill='x')
    ttk.Label(header,text='Inputs required for engineering calculations',font=('Arial',14,'bold')).pack(anchor='w')
    ttk.Label(header,text='Engineering inputs used by project calculations are shown here. Canvas coordinates and geometry-only fields are hidden. Fields marked * are required.',wraplength=900).pack(anchor='w',pady=4)
    filters=ttk.Frame(header);filters.pack(fill='x',pady=(2,4))
    required_only=tk.BooleanVar(value=False)
    ttk.Checkbutton(filters,text='Required fields only',variable=required_only,command=lambda:rebuild()).pack(side='left')
    ttk.Label(filters,text='* Required field').pack(side='left',padx=(14,0))
    canvas=tk.Canvas(win,highlightthickness=0);bar=ttk.Scrollbar(win,orient='vertical',command=canvas.yview)
    footer=ttk.Frame(win,padding=10);footer.pack(side='bottom',fill='x')
    bar.pack(side='right',fill='y');canvas.pack(fill='both',expand=True);canvas.configure(yscrollcommand=bar.set)
    body=ttk.Frame(canvas,padding=12);window=canvas.create_window(0,0,window=body,anchor='nw')
    body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
    canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
    def wheel(event):canvas.yview_scroll(-1 if event.delta>0 else 1,'units');return 'break'
    win.bind('<MouseWheel>',wheel,add='+');win.bind('<Button-4>',lambda e:canvas.yview_scroll(-1,'units'));win.bind('<Button-5>',lambda e:canvas.yview_scroll(1,'units'))
    data=prepare(app._collect_project_data());entries=[];sections={};descriptors=[];all_descriptors=[]
    draft_values={}
    nav=tk.StringVar();picker=ttk.Combobox(header,textvariable=nav,state='readonly',width=55);picker.pack(anchor='w',pady=4)
    def go(event=None):
        frame=sections.get(nav.get())
        if frame:canvas.yview_moveto(frame.winfo_y()/max(1,body.winfo_height()))
    picker.bind('<<ComboboxSelected>>',go)
    def section(name):
        if name not in sections:
            frame=ttk.LabelFrame(body,text=name,padding=10);frame.pack(fill='x',pady=7);frame.columnconfigure(1,weight=1);sections[name]=frame
        return sections[name]
    def rebuild():
        nonlocal descriptors,all_descriptors
        # Preserve unsaved text when the required-only filter is toggled.
        for field,(variable,_widget) in zip(descriptors,entries):
            draft_values[tuple(field.path)]=variable.get()
        for child in body.winfo_children():child.destroy()
        entries.clear();sections.clear();all_descriptors=questionnaire_fields(data)
        descriptors=[f for f in all_descriptors if not required_only.get() or questionnaire_required(f)]
        previous={key:var.get() for key,var in getattr(win,'_source_files',{}).items()}
        files=section('Source files');file_vars={}
        for i,(key,label,types) in enumerate((('roof','Roof image',[('Images','*.png *.jpg *.jpeg *.bmp')]),('consumption','Consumption data',[('Consumption files','*.xlsx *.csv')]),('weather','Historical weather / PVGIS TMY',[('Weather JSON','*.json')]))):
            ttk.Label(files,text=label).grid(row=i,column=0,sticky='w',pady=4)
            var=tk.StringVar(value=previous.get(key,''));ttk.Entry(files,textvariable=var).grid(row=i,column=1,sticky='ew',padx=8);file_vars[key]=var
            def browse(v=var,ft=types):
                path=filedialog.askopenfilename(parent=win,filetypes=ft)
                if path:v.set(path)
            ttk.Button(files,text='Choose '+label.lower(),command=browse).grid(row=i,column=2)
        win._source_files=file_vars
        ttk.Label(files,text='Leave paths blank to retain loaded sources. Consumption CSV columns: timestamp, consumption_kwh; timestamps require UTC offsets.',wraplength=800).grid(row=3,columnspan=3,sticky='w',pady=6)
        row_counts={}
        removable_sections={}
        for field in descriptors:
            frame=section(field.section)
            row=row_counts.get(field.section,0);row_counts[field.section]=row+1
            title=field.label+(' *' if questionnaire_required(field) else '')
            ttk.Label(frame,text=title,wraplength=420).grid(row=row,column=0,sticky='w',pady=3,padx=(0,12))
            value=get(data,field.path)
            cached=draft_values.get(tuple(field.path),None)
            if field.kind=='boolean':
                variable=tk.BooleanVar(value=bool(value) if cached is None else str(cached).lower() in ('1','true','yes','on'));widget=ttk.Checkbutton(frame,text='Confirmed',variable=variable)
            else:
                if value is None:value=''
                elif field.kind=='row' and value!='':value=str(int(value)+1)
                elif field.kind=='point' and value!='':value=','.join(map(str,value))
                elif field.kind=='points':value=' ; '.join(','.join(map(str,p)) for p in value) if value else ''
                shown=DISPLAY_CHOICES.get(value,str(value)) if field.kind=='choice' else str(value)
                if cached is not None:shown=cached
                variable=tk.StringVar(value=shown)
                widget=ttk.Combobox(frame,textvariable=variable,values=[DISPLAY_CHOICES.get(v,v) for v in field.choices],state='readonly') if field.kind=='choice' else ttk.Entry(frame,textvariable=variable)
            widget.grid(row=row,column=1,sticky='ew',pady=3);entries.append((variable,widget))

            path=tuple(field.path)
            if len(path)>=5 and path[0]=='material_categories' and path[2]=='rows' and isinstance(path[3],int):
                removable_sections.setdefault(field.section,('material',path[1],path[3]))
            elif len(path)>=3 and path[0]=='cable_inventory' and isinstance(path[1],int):
                removable_sections.setdefault(field.section,('cable',None,path[1]))

        def remove_record(section_name,record):
            if not messagebox.askyesno(
                'Remove record',
                f'Remove "{section_name}" from the questionnaire?',
                parent=win
            ):
                return
            try:
                preserve_draft()
                kind,category,index=record
                if kind=='material':
                    rows=data.get('material_categories',{}).get(category,{}).get('rows',[])
                else:
                    rows=data.get('cable_inventory',[])
                if not 0 <= index < len(rows):
                    raise ValueError('This record no longer exists.')
                rows.pop(index)

                # Discard cached draft values for the removed row and rows after it;
                # their indexes may have shifted after deletion.
                if kind=='material':
                    prefix=('material_categories',category,'rows')
                else:
                    prefix=('cable_inventory',)
                for key in list(draft_values):
                    if key[:len(prefix)]==prefix:
                        draft_values.pop(key,None)

                rebuild()
                nav.set('Additional records')
                win.update_idletasks()
                frame=sections.get('Additional records')
                if frame:
                    canvas.yview_moveto(max(0,frame.winfo_y()-12)/max(1,body.winfo_height()))
            except Exception as exc:
                messagebox.showerror('Configuration',str(exc),parent=win)

        for section_name,record in removable_sections.items():
            frame=sections.get(section_name)
            if frame:
                ttk.Button(
                    frame,text='Remove',
                    command=lambda s=section_name,r=record:remove_record(s,r)
                ).grid(row=0,column=2,sticky='ne',padx=(12,0),pady=2)

        picker['values']=list(sections)
        add_frame=section('Additional records')
        ttk.Label(
            add_frame,
            text='Add a new engineering record. The new editable section appears immediately on this same page.',
            wraplength=820
        ).grid(row=0,column=0,columnspan=3,sticky='w',pady=(0,6))

        def preserve_draft():
            # Save what is currently typed without running whole-project validation.
            current={tuple(f.path):read(f,v) for f,(v,w) in zip(descriptors,entries)}
            for field in all_descriptors:
                key=tuple(field.path)
                if key in current:
                    raw=current[key]
                elif key in draft_values:
                    raw=draft_values[key]
                    if field.kind=='choice':
                        raw=next((k for k,v in DISPLAY_CHOICES.items() if v==raw),raw)
                else:
                    continue
                put(data,field.path,parse(field,raw))

        def add_record(kind):
            try:
                preserve_draft()
                if kind=='cable':
                    rows=data.setdefault('cable_inventory',[])
                    rows.append({'name':'New cable','length_m':0,'linear_mass_kg_m':None,'quantity':1})
                    target_prefix=('cable_inventory',len(rows)-1)
                else:
                    rows=data.setdefault('material_categories',{}).setdefault(kind,{'rows':[]})['rows']
                    rows.append({})
                    target_prefix=('material_categories',kind,'rows',len(rows)-1)

                rebuild()

                # Find the actual section generated for the new record, then scroll to it.
                target_section=None
                for field in all_descriptors:
                    path=tuple(field.path)
                    if path[:len(target_prefix)]==target_prefix:
                        target_section=field.section
                        break
                if target_section and target_section in sections:
                    nav.set(target_section)
                    win.update_idletasks()
                    frame=sections[target_section]
                    canvas.yview_moveto(max(0,frame.winfo_y()-12)/max(1,body.winfo_height()))
                    # Put the cursor in the first editable field of the new section.
                    for field,(variable,widget) in zip(descriptors,entries):
                        if field.section==target_section:
                            try:
                                widget.focus_set()
                            except tk.TclError:
                                pass
                            break
            except Exception as exc:
                messagebox.showerror('Configuration',str(exc),parent=win)

        buttons=(
            ('modules','Add module'),
            ('inverters','Add inverter equipment'),
            ('cables','Add cable equipment'),
            ('custom','Add custom field'),
            ('cable','Add cable inventory'),
        )
        for i,(kind,title) in enumerate(buttons):
            ttk.Button(add_frame,text=title,command=lambda k=kind:add_record(k)).grid(
                row=1+i//3,column=i%3,padx=5,pady=4,sticky='w')
    def read(field,var):
        raw=var.get()
        if field.kind=='choice':return next((key for key,value in DISPLAY_CHOICES.items() if value==raw),raw)
        return raw

    def questionnaire_values():
        current={tuple(f.path):read(f,v) for f,(v,w) in zip(descriptors,entries)}
        values=[]
        for field in all_descriptors:
            key=tuple(field.path)
            if key in current:
                values.append(current[key])
            elif key in draft_values:
                raw=draft_values[key]
                if field.kind=='choice':raw=next((k for k,v in DISPLAY_CHOICES.items() if v==raw),raw)
                values.append(raw)
            else:
                value=get(data,field.path)
                if field.kind=='row' and value not in (None,''):value=str(int(value)+1)
                elif field.kind=='point' and value not in (None,''):value=','.join(map(str,value))
                elif field.kind=='points':value=' ; '.join(','.join(map(str,p)) for p in value) if value else ''
                elif field.kind=='choice':value=DISPLAY_CHOICES.get(value,value)
                values.append(value)
        return values
    def apply():
        try:
            result=apply_values(data,all_descriptors,questionnaire_values())
            files={key:var.get().strip() for key,var in win._source_files.items()}
            image=app.roof_pil_img
            if files['roof']:
                from PIL import Image
                with Image.open(files['roof']) as source:image=source.copy()
                result['roof_image_path']=str(Path(files['roof']).resolve())
            if files['consumption']:
                from self_consumption import read_hourly_csv,read_daily_excel
                path=files['consumption'];settings=result['model_settings']
                result['hourly_consumption_profile']=read_hourly_csv(path,settings['timezone']) if path.lower().endswith('.csv') else read_daily_excel(path,settings['imputation'])
                result['hourly_weather_profile']={}
            if files['weather']:
                from self_consumption import (read_open_meteo_json,read_pvgis_tmy_json,
                                              is_pvgis_tmy_json,orientation_key)
                profile=result.get('hourly_consumption_profile')
                if not profile:raise ValueError('Import consumption before weather.')
                raw=json.loads(Path(files['weather']).read_text(encoding='utf-8'))
                if is_pvgis_tmy_json(raw):
                    orientations=sorted({
                        (result.get('panel_orientations',{}).get(c,{}).get('tilt_deg',result.get('panel_tilt_deg',0)),
                         result.get('panel_orientations',{}).get(c,{}).get('azimuth_deg',result.get('panel_azimuth_deg',180)))
                        for c in getattr(app,'panels',{})
                    })
                    if not orientations:
                        orientations=[(result.get('panel_tilt_deg',0),result.get('panel_azimuth_deg',180))]
                    result['hourly_weather_profile']=read_pvgis_tmy_json(
                        files['weather'],profile,orientations,app._compute_solar_position,
                        timezone=result['model_settings']['timezone'])
                else:
                    weather=read_open_meteo_json(files['weather'],profile,result['model_settings']['timezone'])
                    weather['query']=copy.deepcopy(result['model_settings']['weather_import_metadata'])
                    previous=result.get('hourly_weather_profile') or {}
                    profiles=copy.deepcopy(previous.get('orientations',{}))
                    if previous.get('query'):
                        q=previous['query'];profiles[orientation_key((q['tilt_deg'],(q['azimuth_deg_from_south']+180)%360))]=previous
                    q=weather['query'];profiles[orientation_key((q['tilt_deg'],(q['azimuth_deg_from_south']+180)%360))]=weather
                    result['hourly_weather_profile']={'orientations':profiles}
            old=app._collect_project_data();old_path=app.current_project_filepath;old_image=app.roof_pil_img
            app._record_history();app._restoring=True
            try:
                app._apply_document(result,old_path or str(Path(app.projects_dir)/'Untitled.json'))
                app.current_project_filepath=old_path;app.roof_pil_img=image;app.draw_grid();app._refresh_energy_workspace()
            except Exception:
                app._apply_document(old,old_path or str(Path(app.projects_dir)/'Untitled.json'));app.current_project_filepath=old_path;app.roof_pil_img=old_image;raise
            finally:app._restoring=False
            app._record_history();win.destroy()
        except Exception as exc:messagebox.showerror('Configuration',str(exc),parent=win)
    ttk.Button(footer,text='Apply all inputs',command=apply).pack(side='right',padx=5)
    ttk.Button(footer,text='Cancel',command=win.destroy).pack(side='right',padx=5)
    rebuild()
