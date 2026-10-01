"""Editable engineering schedule for the active PV project; compact toolbar entry."""
import copy
import csv
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import webbrowser

from detailed_electrical import (build_detailed_model, normalise_design,
                                 source_fingerprint, write_detailed_svg)
from project_validation import natural


class DetailedElectricalUIMixin:
    def _detailed_project_snapshot(self):
        data=self._project_snapshot()
        data.update(grid_connection_settings=self.grid_connection_settings,
                    electrical_route_plan_3d=self.electrical_route_plan_3d,
                    cable_calc_params=self.cable_calc_params,
                    electrical_checks=self.electrical_checks,
                    bess_summary=self.bess_summary)
        return data

    def _export_detailed_electrical_svg(self):
        try:
            model=build_detailed_model(self._detailed_project_snapshot(),self.electrical_design)
            path=filedialog.asksaveasfilename(parent=self.root,defaultextension='.svg',
                    initialfile=f'{self.project_name}_wiring_{len(self.panels)}_panels.svg',
                    filetypes=[('Vector diagram SVG','*.svg')],title='Export detailed single-line')
            if not path:return
            write_detailed_svg(model,path)
            messagebox.showinfo('Site wiring',f'Saved {path}\n\n{len(model["issues"])} open points are shown in the drawing.',parent=self.root)
        except (OSError,ValueError,TypeError,KeyError) as exc:
            messagebox.showerror('Site wiring',str(exc),parent=self.root)

    def _show_detailed_electrical_editor(self):
        existing=getattr(self,'_detailed_editor_window',None)
        if existing is not None and existing.winfo_exists():
            existing.lift();existing.focus_set();return
        project=self._detailed_project_snapshot()
        design=normalise_design(copy.deepcopy(self.electrical_design))
        win=tk.Toplevel(self.root)
        win.title(f'Electrical wiring • {self.project_name}')
        self._detailed_editor_window=win
        pages=ttk.Notebook(win)
        pages.pack(fill=tk.BOTH,expand=True,padx=8,pady=6)
        tab_top=ttk.Frame(pages,padding=9);tab_dc=ttk.Frame(pages,padding=9)
        tab_ac=ttk.Frame(pages,padding=9);tab_bat=ttk.Frame(pages,padding=9)
        tab_checks=ttk.Frame(pages,padding=9)
        for frame,label in [(tab_top,'Site'),(tab_dc,'PV strings'),(tab_ac,'Inverters AC'),
                            (tab_bat,'BESS / grid'),(tab_checks,'Open checks')]:
            pages.add(frame,text=label)

        overview=[]
        label=ttk.Label(tab_top,text='Topology is derived from the current inverter blocks and string assignments.',
                  wraplength=550,justify=tk.LEFT)
        label.pack(anchor='w',pady=4);overview.append(label)
        label=ttk.Label(tab_top,text='With one MC-L522, cluster 1 → BAT of INV1 and cluster 2 → BAT of INV2. '
                  'INV3 remains PV-only. The second cabinet needs its own DEYE-approved connection diagram.',
                  wraplength=550,justify=tk.LEFT)
        label.pack(anchor='w',pady=4);overview.append(label)
        label=ttk.Label(tab_top,text='Reference: DEYE MC-L522-BC + 125k H-INV drawing; the 136 kW string inverter '
                  'shown there is replaced here by the third hybrid specified for this project.',
                  wraplength=550,justify=tk.LEFT)
        label.pack(anchor='w',pady=4);overview.append(label)
        settings=ttk.Frame(tab_top);settings.pack(anchor='w',pady=10)
        ttk.Label(settings,text='Installed BESS cabinets:').grid(row=0,column=0,sticky='w',pady=6)
        count=tk.StringVar(value=str(design['bess_count']))
        ttk.Combobox(settings,textvariable=count,state='readonly',values=['0','1','2'],width=6).grid(row=0,column=1,sticky='w',padx=9)
        top_vars={}
        for idx,(field,label) in enumerate([('ac_voltage_v','AC line-line voltage (V)'),
                                              ('power_factor','AC power factor')],1):
            ttk.Label(settings,text=label).grid(row=idx,column=0,sticky='w',pady=6)
            var=tk.StringVar(value=str(design.get(field,'')))
            ttk.Entry(settings,textvariable=var,width=12).grid(row=idx,column=1,sticky='w',padx=9)
            top_vars[field]=var
        grid_settings=self.grid_connection_settings
        label=ttk.Label(tab_top,text=f"Contract {grid_settings.get('existing_contract_kw','?')} kW | "
                  f"requested export {grid_settings.get('export_limit_kw','?')} kW | "
                  f"status: {grid_settings.get('export_limit_status','not specified')}. "
                  'Change actual contract and authorization in the project grid settings before final design.',
                  wraplength=550,justify=tk.LEFT)
        label.pack(anchor='w',pady=10);overview.append(label)
        tab_top.bind('<Configure>',lambda event:[widget.configure(wraplength=max(220,event.width-34))
                     for widget in overview])

        def table(parent,columns):
            shell=ttk.Frame(parent);shell.pack(fill=tk.BOTH,expand=True)
            tree=ttk.Treeview(shell,columns=[c[0] for c in columns],show='headings',height=9,selectmode='browse')
            for key,label,width in columns:
                tree.heading(key,text=label);tree.column(key,width=width,minwidth=58)
            tree.grid(row=0,column=0,sticky='nsew')
            shell.rowconfigure(0,weight=1);shell.columnconfigure(0,weight=1)
            ttk.Scrollbar(shell,orient=tk.VERTICAL,command=tree.yview).grid(row=0,column=1,sticky='ns')
            bar=ttk.Scrollbar(shell,orient=tk.HORIZONTAL,command=tree.xview)
            bar.grid(row=1,column=0,sticky='ew')
            tree.configure(xscrollcommand=bar.set)
            return tree

        dc_cols=[('string','String',100),('inv','Inverter',90),('mppt','MPPT',64),
                 ('modules','Modules',75),('route','A+B route (m)',115),
                 ('section','DC mm²',83),('fuse','Fuse A',78),('isolator','Isolator A',95)]
        dc_tree=table(tab_dc,dc_cols)
        dc_fields=[('section_mm2','DC copper (mm²)'),('fuse_a','DC fuse (A)'),
                   ('isolator_a','DC isolator (A)'),('spd','SPD model / type')]
        dc_entries={};dc_form=ttk.Frame(tab_dc);dc_form.pack(fill=tk.X,pady=6)
        for n,(key,label) in enumerate(dc_fields):
            ttk.Label(dc_form,text=label).grid(row=n//2,column=2*(n%2),sticky='w',pady=3)
            entry=ttk.Entry(dc_form,width=16);entry.grid(row=n//2,column=2*(n%2)+1,padx=5,sticky='ew')
            dc_entries[key]=entry
        dc_form.columnconfigure(1,weight=1);dc_form.columnconfigure(3,weight=1)
        dc_current=[None]
        def dc_flush():
            sid=dc_current[0]
            if sid:design['dc'][sid]={k:e.get().strip() for k,e in dc_entries.items()}
        def dc_select(_event=None):
            sid=dc_tree.selection()
            if not sid:return
            dc_flush();dc_current[0]=sid[0]
            stored=design['dc'].get(sid[0],{})
            for key,e in dc_entries.items():e.delete(0,tk.END);e.insert(0,str(stored.get(key,'')))
        dc_tree.bind('<<TreeviewSelect>>',dc_select)
        for sid in sorted(project['strings'],key=natural):
            alloc=project['string_mppt_assignment'].get(sid,{})
            rec=self.get_two_pole_route(sid) if hasattr(self,'get_two_pole_route') else None
            vals=design['dc'].get(sid,{})
            dc_tree.insert('',tk.END,iid=sid,values=(sid,alloc.get('block',''),alloc.get('mppt',''),
                len(project['strings'][sid]),f"{rec['loop_length_m']:.1f}" if rec else 'recalculate',
                vals.get('section_mm2',''),vals.get('fuse_a',''),vals.get('isolator_a','')))
        ttk.Label(tab_dc,text='Lengths A/B are pulled from current routes only. A voltage-drop recommendation is not an approved cable section.',
                  wraplength=750).pack(anchor='w')
        if dc_tree.get_children():dc_tree.selection_set(dc_tree.get_children()[0])

        ac_cols=[('inv','Inverter',110),('model','Model',310),('strings','Strings',75),
                 ('kwp','PV kWp',95),('length','AC route (m)',115),('section','AC mm²',85),('breaker','Breaker A',90)]
        ac_tree=table(tab_ac,ac_cols)
        ac_fields=[('length_m','Cable run (m)'),('section_mm2','AC copper (mm²)'),
                   ('breaker_a','Breaker (A)'),('spd','SPD model / type'),('isolator','AC isolator / switch')]
        ac_entries={};ac_form=ttk.Frame(tab_ac);ac_form.pack(fill=tk.X,pady=6)
        for n,(key,label) in enumerate(ac_fields):
            ttk.Label(ac_form,text=label).grid(row=n//2,column=2*(n%2),sticky='w',pady=3)
            e=ttk.Entry(ac_form,width=16);e.grid(row=n//2,column=2*(n%2)+1,padx=5,sticky='ew');ac_entries[key]=e
        ac_form.columnconfigure(1,weight=1);ac_form.columnconfigure(3,weight=1)
        ac_current=[None]
        def ac_flush():
            inv=ac_current[0]
            if inv:design['ac'][inv]={k:e.get().strip() for k,e in ac_entries.items()}
        def ac_select(_event=None):
            selection=ac_tree.selection()
            if not selection:return
            ac_flush();ac_current[0]=selection[0]
            stored=design['ac'].get(selection[0],{})
            for key,e in ac_entries.items():e.delete(0,tk.END);e.insert(0,str(stored.get(key,'')))
        ac_tree.bind('<<TreeviewSelect>>',ac_select)
        for inv in sorted(project['blocks'],key=natural):
            placement=project['inverter_positions'].get(inv,{})
            mat=placement.get('material_row',{})
            assigned=[s for s,a in project['string_mppt_assignment'].items() if a.get('block')==inv]
            dc_kwp=sum(len(project['strings'].get(s,[])) for s in assigned)*self.panel_pmax_w/1000
            vals=design['ac'].get(inv,{})
            ac_tree.insert('',tk.END,iid=inv,values=(inv,mat.get('Modèle',''),len(assigned),
                         f'{dc_kwp:.2f}',vals.get('length_m',''),vals.get('section_mm2',''),vals.get('breaker_a','')))
        ttk.Label(tab_ac,text='Nominal AC current is calculated only after the actual line voltage is entered. Cable ampacity / fault level need external checks.',
                  wraplength=750).pack(anchor='w')
        if ac_tree.get_children():ac_tree.selection_set(ac_tree.get_children()[0])

        bat_pages=ttk.Notebook(tab_bat);bat_pages.pack(fill=tk.BOTH,expand=True)
        bat_vars={}
        for n in (1,2):
            page=ttk.Frame(bat_pages,padding=12);bat_pages.add(page,text=f'BESS {n}')
            old=design['battery'].get(str(n),{})
            vars_for_cab={}
            for row,(key,label) in enumerate([
                ('cluster_1_to','Cluster 1 → BAT of'),('cluster_2_to','Cluster 2 → BAT of'),
                ('fuse_a','DC fuse (A)'),('isolator_a','DC isolator (A)'),
                ('section_mm2','DC cable (mm²)'),('length_m','Cable run (m)'),('spd','SPD model / type')]):
                ttk.Label(page,text=label).grid(row=row,column=0,sticky='w',pady=4)
                var=tk.StringVar(value=str(old.get(key,'')))
                if key.startswith('cluster_'):
                    w=ttk.Combobox(page,textvariable=var,state='readonly',
                                   values=['']+sorted(project['blocks'],key=natural),width=19)
                else:w=ttk.Entry(page,textvariable=var,width=21)
                w.grid(row=row,column=1,sticky='w',padx=7);vars_for_cab[key]=var
            if n==2:
                ttk.Label(page,text='The supplied DEYE drawing shows one cabinet with two clusters. '
                          'A second cabinet / parallel BAT wiring must be confirmed by DEYE.',
                          wraplength=490,justify=tk.LEFT).grid(row=7,column=0,columnspan=2,pady=10)
            bat_vars[str(n)]=vars_for_cab
        grid_page=ttk.Frame(bat_pages,padding=12);bat_pages.add(grid_page,text='TGBT / grid')
        grid_vars={}
        for row,(key,label) in enumerate([
            ('main_breaker_a','Main breaker (A)'),('meter_id','Meter reference'),
            ('interface_protection','Interface protection model / settings'),
            ('export_control','Export limiter / sensor'),
            ('transformer_connection','Connection of existing transformers'),
            ('emergency_shutdown','Emergency shutdown circuit')]):
            ttk.Label(grid_page,text=label,wraplength=225).grid(row=row,column=0,sticky='w',pady=5)
            var=tk.StringVar(value=str(design['grid'].get(key,'')))
            ttk.Entry(grid_page,textvariable=var,width=35).grid(row=row,column=1,padx=5,sticky='ew')
            grid_vars[key]=var
        grid_page.columnconfigure(1,weight=1)

        checks_text=tk.Text(tab_checks,wrap='word',state='disabled')
        checks_text.pack(side=tk.LEFT,fill=tk.BOTH,expand=True)
        scroll=ttk.Scrollbar(tab_checks,command=checks_text.yview)
        scroll.pack(side=tk.RIGHT,fill=tk.Y);checks_text.configure(yscrollcommand=scroll.set)

        def capture():
            dc_flush();ac_flush()
            design['bess_count']=int(count.get())
            for key,var in top_vars.items():design[key]=var.get().strip()
            for cab,values in bat_vars.items():
                design['battery'][cab]={key:var.get().strip() for key,var in values.items()}
            design['grid']={key:var.get().strip() for key,var in grid_vars.items()}
            design['source_fingerprint']=source_fingerprint(self._detailed_project_snapshot())
            return build_detailed_model(self._detailed_project_snapshot(),design)

        def refresh():
            try:model=capture()
            except (ValueError,TypeError,KeyError) as exc:
                messagebox.showerror('Electrical design',str(exc),parent=win);return None
            checks_text.configure(state='normal');checks_text.delete('1.0',tk.END)
            checks_text.insert(tk.END,f"{len(model['issues'])} open point(s) for {len(model['lines'])} strings.\n\n")
            for line in model['issues']:checks_text.insert(tk.END,'• '+line+'\n')
            checks_text.configure(state='disabled')
            return model

        def save():
            if refresh() is None:return
            self.electrical_design=copy.deepcopy(design)
            self.save_project(silent=True)
            messagebox.showinfo('Electrical design','Site wiring settings saved to the current project. Open checks remain visible.',parent=win)

        def export_svg(preview=False):
            model=refresh()
            if model is None:return
            if preview:
                path=Path(tempfile.gettempdir())/'pv_site_wiring_preview.svg'
            else:
                path=filedialog.asksaveasfilename(parent=win,defaultextension='.svg',
                    initialfile=f'{self.project_name}_wiring_{len(self.panels)}_panels.svg',
                    filetypes=[('SVG vector diagram','*.svg')])
                if not path:return
            try:write_detailed_svg(model,path)
            except OSError as exc:messagebox.showerror('Export SVG',str(exc),parent=win);return
            if preview:webbrowser.open_new_tab(Path(path).resolve().as_uri())
            else:messagebox.showinfo('SVG',f'Saved {path}',parent=win)

        def export_csv():
            model=refresh()
            if model is None:return
            def writer():
                path=filedialog.asksaveasfilename(parent=win,defaultextension='.csv',
                    initialfile='electrical_wiring_schedule.csv',filetypes=[('CSV','*.csv')])
                if not path:return
                with open(path,'w',newline='',encoding='utf-8-sig') as output:
                    csvwriter=csv.writer(output,delimiter=';')
                    csvwriter.writerow(['String','Inverter','MPPT','Module count','Panels','kWp',
                        'Voc STC (V)','Vmp STC (V)','Imp (A)','Isc (A)','Pole A (m)','Pole B (m)',
                        'Loop (m)','DC section (mm2)','DC fuse (A)','DC isolator (A)','DC SPD',
                        'Estimated drop (%)'])
                    for line in model['lines']:
                        route=line['route'];term_a=route['terminal_A']['length_m'] if route else ''
                        term_b=route['terminal_B']['length_m'] if route else ''
                        csvwriter.writerow([line['id'],line['inv'],line['mppt'],line['count'],
                            ','.join(map(str,line['panel_numbers'])),line['kwp'],line['voc_stc_v'] or '',
                            line['vmp_stc_v'] or '',line['imp_a'] or '',line['isc_a'] or '',
                            term_a,term_b,route['loop_length_m'] if route else '',
                            line['section_mm2'] or '',line['fuse_a'] or '',line['isolator_a'] or '',
                            line['spd'],line['drop_pct'] if line['drop_pct'] is not None else ''])
                    csvwriter.writerow([]);csvwriter.writerow(['OPEN CHECKS'])
                    for issue in model['issues']:csvwriter.writerow([issue])
                messagebox.showinfo('CSV',f'Saved {path}',parent=win)
            self._export_with_csv_preview(writer,'electrical_wiring_schedule.csv')

        actions=ttk.Frame(win,padding=6);actions.pack(fill=tk.X)
        ttk.Button(actions,text='Refresh checks',command=lambda:(pages.select(tab_checks),refresh())).pack(side=tk.LEFT)
        menu_button=ttk.Menubutton(actions,text='Drawing / exports')
        menu=tk.Menu(menu_button,tearoff=False)
        menu.add_command(label='Preview current SVG',command=lambda:export_svg(True))
        menu.add_command(label='Export current SVG…',command=export_svg)
        menu.add_command(label='Preview / export wiring CSV…',command=export_csv)
        menu_button.configure(menu=menu);menu_button.pack(side=tk.LEFT,padx=5)
        ttk.Button(actions,text='Save settings and project',command=save).pack(side=tk.RIGHT,padx=4)
        ttk.Button(actions,text='Close',command=win.destroy).pack(side=tk.RIGHT)
        refresh();self._fit_dialog(win,1020,670)
