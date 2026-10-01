"""Per-string voltage drop and manufacturer-supplied cable mass."""
import copy
import math
import tkinter as tk
from tkinter import ttk, messagebox
from project_validation import number, string_label


def size_string(record, modules, module_spec, overrides, parameters, masses):
    from mixins.notes_tools import calculate_dc_cable_size
    result = copy.deepcopy(record)
    current = number(overrides.get('current_a', module_spec.get('Imp (A)')))
    vmp = number(module_spec.get('Vmp (V)'))
    voltage = number(overrides.get('voltage_v', vmp * modules if vmp else None))
    result.update(current_a=current, voltage_v=voltage, working_section_mm2=None,
                  drop_at_working_section_pct=None, mass_kg=None,
                  sizing_status='Missing module Imp/Vmp or string operating values')
    if current is None or voltage is None:
        return result
    try:
        sized = calculate_dc_cable_size(current, voltage, result['loop_length_m']/2,
                                       parameters['resistivity'], parameters['target_drop_pct'])
    except (ValueError, TypeError, KeyError):
        result['sizing_status'] = 'Invalid sizing inputs'
        return result
    section = number(overrides.get('section_mm2')) or sized['recommended_mm2']
    if section is not None:
        sized['actual_drop_pct']=100*parameters['resistivity']*current*result['loop_length_m']/section/voltage
    ampacity=number(overrides.get('ampacity_a'))
    protection=number(overrides.get('protection_a'))
    if ampacity is not None and (current>ampacity or protection is not None and protection>ampacity):
        result['ampacity_status']='FAIL — current/protection exceeds corrected cable ampacity'
    elif ampacity is None:result['ampacity_status']='Missing corrected cable ampacity'
    else:result['ampacity_status']='Entered ampacity checked; installation data still require review'
    if sized['actual_drop_pct'] is not None and sized['actual_drop_pct']>parameters['target_drop_pct']:
        result['ampacity_status']='FAIL — chosen section exceeds voltage-drop limit'

    result.update(working_section_mm2=section,
                  drop_at_working_section_pct=sized['actual_drop_pct'],
                  sizing_status='Voltage drop only' if section else 'Required section exceeds 240 mm²')
    linear_mass = number(overrides.get('linear_mass_kg_m',masses.get(f'{section:g}'))) if section is not None else None
    if linear_mass is not None and linear_mass > 0:
        result['mass_kg'] = result['loop_length_m'] * linear_mass
    return result


class StringSizingMixin:
    def _string_sizing_signature(self):
        return {'parameters': self.cable_calc_params,
                'strings': getattr(self, 'cable_string_params', {}),
                'mass_by_section': getattr(self, 'cable_mass_by_section', {}),
                'module_rows': self.material_categories.get('modules', {}).get('rows', [])}

    def _size_string_route(self, sid, record):
        from engineering_inputs import module_for_string
        spec=module_for_string(self._project_snapshot(),sid)
        return size_string(record, len(self.strings.get(sid, [])), spec,
                           getattr(self, 'cable_string_params', {}).get(sid, {}),
                           self.cable_calc_params, getattr(self, 'cable_mass_by_section', {}))

    def _cable_mass_summary(self):
        total = 0.; missing = 0
        for sid, coords in self.strings.items():
            if not coords:continue
            route = self.get_two_pole_route(sid)
            mass = route.get('mass_kg') if route else None
            if mass is None:missing += 1
            else:total += mass
        for cable in getattr(self,'cable_inventory',[]):
            length=cable.get('length_m');linear=cable.get('linear_mass_kg_m');quantity=cable.get('quantity',1)
            if length is None or linear is None:missing+=1
            else:total+=length*linear*quantity
        return {'total_kg': total if not missing else None, 'known_kg': total, 'missing': missing}

    def _build_string_sizing_page(self, notebook):
        page = ttk.Frame(notebook, padding=7)
        notebook.add(page, text='String sizing')
        ttk.Label(page, text='DC string cables: section and mass', font=('Arial',10,'bold')).pack(anchor='w')
        ttk.Label(page, text='Each string uses its own A+B length and module count. Imp/Vmp come from the module sheet; Edit string supplies explicit operating values.', wraplength=320).pack(anchor='w',pady=6)
        frame=ttk.Frame(page);frame.pack(fill='both',expand=True)
        table=ttk.Frame(frame);table.pack(fill='both',expand=True)
        columns=('length','section','drop','mass','status')
        self.string_sizing_tree=ttk.Treeview(table,columns=columns,show='tree headings',height=9,selectmode='browse')
        for key,label,width in [('#0','String',75),('length','A+B (m)',70),('section','mm²',55),('drop','Drop %',65),('mass','kg',65),('status','Status',260)]:
            self.string_sizing_tree.heading(key,text=label);self.string_sizing_tree.column(key,width=width,minwidth=45)
        self.string_sizing_tree.pack(side='left',fill='both',expand=True)
        xs=ttk.Scrollbar(frame,orient='horizontal',command=self.string_sizing_tree.xview);xs.pack(fill='x')
        ys=ttk.Scrollbar(table,orient='vertical',command=self.string_sizing_tree.yview);ys.pack(side='right',fill='y')
        self.string_sizing_tree.configure(xscrollcommand=xs.set,yscrollcommand=ys.set)
        self.string_sizing_tree.bind('<Double-1>',lambda e:self._edit_string_sizing())
        ttk.Button(page,text='Calculate all strings',command=self._calculate_and_show_cable_routes).pack(fill='x',pady=5)
        ttk.Button(page,text='Edit selected string…',command=self._edit_string_sizing).pack(fill='x')
        ttk.Button(page,text='Cable mass by section…',command=self._edit_cable_masses).pack(fill='x',pady=5)
        self.string_mass_label=ttk.Label(page,wraplength=320);self.string_mass_label.pack(anchor='w',pady=6)
        ttk.Label(page,text='Total includes DC string-to-inverter A+B and additional cables entered in Model settings. Enter manufacturer kg/m and corrected ampacity for the installed cable. Omitted cables are outside the declared inventory.',wraplength=320,foreground='#546E7A').pack(anchor='w')

    def _refresh_string_sizing_table(self):
        tree=self.string_sizing_tree;selected=tree.selection()
        tree.delete(*tree.get_children())
        for sid in self._get_sorted_string_keys():
            if not self.strings.get(sid):continue
            rec=self.get_two_pole_route(sid)
            values=[]
            for key in ('loop_length_m','working_section_mm2','drop_at_working_section_pct','mass_kg'):
                value=rec.get(key) if rec else None
                values.append(f'{value:.2f}' if value is not None else '—')
            status=rec.get('sizing_status','')+'; '+rec.get('ampacity_status','') if rec else 'Calculate route / check elevations'
            if rec and rec.get('working_section_mm2') and rec.get('mass_kg') is None:status+='; missing kg/m'
            tree.insert('', 'end',iid=sid,text=string_label(sid),values=(*values,status))
        if selected and tree.exists(selected[0]):tree.selection_set(selected[0])
        mass=self._cable_mass_summary()
        text=(f"TOTAL_CABLE_WEIGHT_KG: {mass['total_kg']:.2f} kg" if mass['total_kg'] is not None else
              f"Total mass unavailable: {mass['missing']} cable record(s) missing inputs. Known subtotal: {mass['known_kg']:.2f} kg.")
        self.string_mass_label.configure(text=text)

    def _edit_string_sizing(self):
        selection=self.string_sizing_tree.selection()
        if not selection:
            messagebox.showinfo('String sizing','Select a string in the table.');return
        sid=selection[0];saved=self.cable_string_params.get(sid,{})
        win=tk.Toplevel(self.root);win.title(f'Operating values — {string_label(sid)}');entries={}
        ttk.Label(win,text='Blank = use module equipment sheet. Voltage is the whole string Vmp.',wraplength=390).grid(row=0,column=0,columnspan=2,padx=12,pady=10)
        for row,(key,label) in enumerate([('current_a','String Imp (A)'),('voltage_v','String Vmp (V)'),('section_mm2','Chosen section (mm²)'),('ampacity_a','Corrected cable ampacity (A)'),('protection_a','Protection rating (A)'),('linear_mass_kg_m','Cable mass (kg/m)'),('reserve_per_pole_m','Reserve per conductor (m)')],1):
            ttk.Label(win,text=label).grid(row=row,column=0,padx=12,pady=6)
            entry=ttk.Entry(win);entry.insert(0,str(saved.get(key,'')));entry.grid(row=row,column=1,padx=12);entries[key]=entry
        module_rows=self.material_categories.get('modules',{}).get('rows',[])
        ttk.Label(win,text='Module equipment row (1-based)').grid(row=len(entries)+1,column=0,padx=12,pady=6)
        module=ttk.Combobox(win,values=['']+[str(i+1) for i in range(len(module_rows))],state='readonly')
        module.set(str(saved['module_row']+1) if 'module_row' in saved else '')
        module.grid(row=len(entries)+1,column=1)
        def apply():
            try:
                values={k:float(e.get().replace(',','.')) for k,e in entries.items() if e.get().strip()}
                if any(not math.isfinite(v) or v<0 or v==0 and k!='reserve_per_pole_m' for k,v in values.items()):raise ValueError
            except ValueError:messagebox.showerror('String sizing','Enter positive finite operating values.',parent=win);return
            if module.get():values['module_row']=int(module.get())-1
            if values:self.cable_string_params[sid]=values
            else:self.cable_string_params.pop(sid,None)
            win.destroy();self._calculate_and_show_cable_routes()
        ttk.Button(win,text='Apply and calculate',command=apply).grid(row=len(entries)+2,column=1,pady=12)

    def _edit_cable_masses(self):
        from mixins.notes_tools import STANDARD_DC_SECTIONS
        win=tk.Toplevel(self.root);win.title('Manufacturer cable mass');entries={}
        ttk.Label(win,text='Enter kg/m for one insulated conductor from the cable sheet. Blank = unknown.',wraplength=400).grid(row=0,column=0,columnspan=2,padx=12,pady=8)
        for row,section in enumerate(STANDARD_DC_SECTIONS,1):
            key=f'{section:g}'
            ttk.Label(win,text=f'{key} mm² — kg/m').grid(row=row,column=0,padx=12,pady=2)
            entry=ttk.Entry(win);entry.insert(0,str(self.cable_mass_by_section.get(key,'')));entry.grid(row=row,column=1,padx=12);entries[key]=entry
        def apply():
            try:
                values={k:float(e.get().replace(',','.')) for k,e in entries.items() if e.get().strip()}
                if any(not math.isfinite(v) or v<=0 for v in values.values()):raise ValueError
            except ValueError:messagebox.showerror('Cable mass','Enter positive finite kg/m values.',parent=win);return
            self.cable_mass_by_section=values;win.destroy();self._calculate_and_show_cable_routes()
        ttk.Button(win,text='Apply',command=apply).grid(row=len(entries)+1,column=1,pady=10)
