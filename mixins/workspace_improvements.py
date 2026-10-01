"""Home, recent projects, compact layout controls and universal CSV preview."""
import csv
import datetime as dt
import io
import json
import math
import os
import shutil
import tempfile
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from home_reference import WORKFLOWS, FORMULAS


class WorkspaceImprovementsMixin:
    def _build_tab_file_tools(self):
        project=ttk.Menubutton(self.tab_file,text='Project')
        menu=tk.Menu(project,tearoff=False)
        menu.add_command(label='Open JSON project…',command=self.import_project)
        menu.add_command(label='Save project',command=self.save_project)
        menu.add_command(label='Load roof image…',command=self.load_roof_image)
        menu.add_command(label='Fit roof to window',command=self._fit_roof_to_window)
        menu.add_separator()
        menu.add_command(label='Export final JPG',command=self.export_jpg_final)
        project.configure(menu=menu)
        project.pack(side=tk.LEFT,padx=5)
        self.lbl_project_info=ttk.Label(self.tab_file,text=f'Active project: {self.project_name}')

    def _build_tab_layout_tools(self):
        tab = self.tab_layout
        self.entry_width = ttk.Entry(tab, width=7)
        self.entry_width.insert(0, str(int(self.panel_width_mm)))
        self.entry_height = ttk.Entry(tab, width=7)
        self.entry_height.insert(0, str(int(self.panel_height_mm)))
        self.entry_layout_tilt = ttk.Entry(tab, width=7)
        self.entry_layout_tilt.insert(0, str(self.panel_tilt_deg))
        self.entry_layout_azimuth = ttk.Entry(tab, width=7)
        self.entry_layout_azimuth.insert(0, str(self.panel_azimuth_deg))
        self._panel_field_vars=[]
        for entry in (self.entry_width,self.entry_height,self.entry_layout_tilt,self.entry_layout_azimuth):
            variable=tk.StringVar(value=entry.get())
            entry.configure(textvariable=variable)
            self._panel_field_vars.append(variable)
        self.var_continuous_numbers = tk.BooleanVar(value=True)
        self.var_block_paint_only = tk.BooleanVar(value=False)

        def group(label, commands):
            button = ttk.Menubutton(tab, text=label)
            menu = tk.Menu(button, tearoff=False)
            commands(menu)
            button.configure(menu=menu)
            button.pack(side=tk.LEFT, padx=5)
            return menu

        ttk.Button(tab,text='Panel…',command=self._show_panel_configuration).pack(side=tk.LEFT,padx=5)
        ttk.Separator(tab, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)
        def layout(menu):
            menu.add_command(label='Generate layout', command=self.generate_panels_from_zones)
            menu.add_checkbutton(label='Consecutive panel numbers', variable=self.var_continuous_numbers)
        group('Layout', layout)
        ttk.Separator(tab, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)
        self.combo_blocks = ttk.Combobox(tab, values=['No Block'], width=12, state='readonly')
        self.combo_blocks.set('No Block')
        self.combo_blocks.bind('<<ComboboxSelected>>', self._on_block_selected)
        self.combo_blocks.pack(side=tk.LEFT, padx=4)
        self._fix_combobox_popdown_position(self.combo_blocks)
        def blocks(menu):
            menu.add_command(label='New block', command=self.create_new_block)
            menu.add_command(label='Delete active block', command=self.delete_active_block)
            menu.add_checkbutton(label='Paint block only', variable=self.var_block_paint_only)
        group('Block', blocks)
        ttk.Separator(tab, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=4)
        def inverter(menu):
            menu.add_command(label='Place inverter for active block', command=self.open_inverter_selection_dialog)
            menu.add_command(label='Remove placement', command=self.remove_inverter_placement)
        group('Inverter', inverter)

    def _show_panel_configuration(self):
        win = tk.Toplevel(self.root)
        win.title('Panel configuration')
        body = ttk.Frame(win, padding=14)
        body.pack(fill=tk.BOTH, expand=True)
        pairs = [('Width (mm)', self.entry_width), ('Height (mm)', self.entry_height),
                 ('Tilt (°)', self.entry_layout_tilt), ('Azimuth (°)', self.entry_layout_azimuth)]
        for row, ((label, original), variable) in enumerate(zip(pairs,self._panel_field_vars)):
            ttk.Label(body, text=label).grid(row=row, column=0, sticky='w', pady=6)
            ttk.Entry(body, width=15, textvariable=variable).grid(row=row, column=1, sticky='w', padx=8)
        ttk.Label(body, text='Orientation applies to selected panels; if none are selected, it sets the default.',
                  wraplength=350).grid(row=4, column=0, columnspan=2, pady=10)
        def apply():
            try:
                width=float(self.entry_width.get());height=float(self.entry_height.get())
                tilt=float(self.entry_layout_tilt.get());azimuth=float(self.entry_layout_azimuth.get())
                if not all(math.isfinite(x) for x in (width,height,tilt,azimuth)) or \
                        width<=0 or height<=0 or not 0<=tilt<=90 or not 0<=azimuth<360:
                    raise ValueError
            except ValueError:
                messagebox.showerror('Panel configuration','Check dimensions (>0), tilt (0–90°) and azimuth (0–<360°).',parent=win)
                return
            self.update_dimensions()
            self.apply_panel_orientation()
            win.destroy()
        ttk.Button(body, text='Apply', command=apply).grid(row=5, column=1, sticky='e')
        self._fit_dialog(win,420,300)

    def _install_home(self):
        self.home_frame = ttk.Frame(self.main_container, padding=16)
        self.lbl_project_info.pack_forget()
        tab,items,more,menu=self._toolbars[str(self.tab_file)]
        self._toolbars[str(self.tab_file)]=(tab,[item for item in items if item[0] is not self.lbl_project_info],more,menu)
        heading = ttk.Frame(self.home_frame)
        heading.pack(fill=tk.X)
        ttk.Label(heading, text='Recent projects', font=('Arial', 15, 'bold')).pack(anchor='w')
        self.home_active_label=ttk.Label(heading,text='')
        self.home_active_label.pack(anchor='w',pady=3)
        buttons=ttk.Frame(heading)
        buttons.pack(anchor='w',pady=3)
        ttk.Button(buttons, text='Open selected', command=self._open_recent_selection).pack(side=tk.LEFT)
        ttk.Button(buttons, text='Open another project…', command=self.import_project).pack(side=tk.LEFT,padx=8)
        history = ttk.Frame(self.home_frame)
        history.pack(fill=tk.X, pady=(4, 8))
        self.recent_tree = ttk.Treeview(history, columns=('name','date','location'), show='headings', height=3)
        for key, label, size in [('name','Project',190),('date','Last opened',175),('location','Location',430)]:
            self.recent_tree.heading(key, text=label)
            self.recent_tree.column(key, width=size, minwidth=80)
        self.recent_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.recent_tree.bind('<Double-1>', lambda event:self._open_recent_selection())
        scroll=ttk.Scrollbar(history,orient=tk.VERTICAL,command=self.recent_tree.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.recent_tree.configure(yscrollcommand=scroll.set)

        # Task progress lives in the main Home workspace, never in the ribbon.
        # It is packed only while a long-running task is active, so the toolbar
        # height can never be changed by progress/status text.
        self.home_task_frame=ttk.Frame(self.home_frame,padding=(9,6))
        self.home_task_label=ttk.Label(self.home_task_frame,text='',font=('Arial',10,'bold'))
        self.home_task_label.pack(side=tk.LEFT,padx=(0,10))
        self.home_task_progress=ttk.Progressbar(self.home_task_frame,mode='determinate',maximum=100,length=360)
        self.home_task_progress.pack(side=tk.LEFT,fill=tk.X,expand=True)
        self.home_task_percent=ttk.Label(self.home_task_frame,text='',width=5,anchor='e')
        self.home_task_percent.pack(side=tk.LEFT,padx=(8,4))
        self.home_task_cancel=ttk.Button(self.home_task_frame,text='Cancel',command=self._cancel_task)
        self.home_task_cancel.pack(side=tk.LEFT,padx=(6,0))
        self._home_task_hide_job=None

        self.home_guide_heading=ttk.Frame(self.home_frame);self.home_guide_heading.pack(fill=tk.X)
        ttk.Label(self.home_guide_heading,text='Guide',font=('Arial',15,'bold')).pack(side=tk.LEFT)
        notebook=ttk.Notebook(self.home_frame);notebook.pack(fill=tk.BOTH,expand=True,pady=(4,0))
        self.home_guide_notebook=notebook
        for title,data in [('How it works',WORKFLOWS),('Formulas',FORMULAS)]:
            page=ttk.Frame(notebook,padding=5);notebook.add(page,text=title)
            sections=tk.Listbox(page,exportselection=False,width=23)
            sections.pack(side=tk.LEFT,fill=tk.Y)
            for section in data:sections.insert(tk.END,section[0])
            body=ttk.Frame(page);body.pack(side=tk.LEFT,fill=tk.BOTH,expand=True,padx=(7,0))
            reader=tk.Text(body,wrap='word',font=('Arial',10),padx=11,pady=8,relief='flat')
            reader.pack(side=tk.LEFT,fill=tk.BOTH,expand=True)
            scrollbar=ttk.Scrollbar(body,orient=tk.VERTICAL,command=reader.yview)
            scrollbar.pack(side=tk.RIGHT,fill=tk.Y);reader.configure(yscrollcommand=scrollbar.set)
            reader.tag_configure('heading',font=('Arial',13,'bold'),spacing3=10)
            reader.tag_configure('detail',spacing1=3,spacing3=12)
            def select(_event=None,box=sections,target=reader,items=data,formulas=title=='Formulas'):
                if not box.curselection():return
                item=items[box.curselection()[0]]
                target.configure(state='normal');target.delete('1.0',tk.END)
                target.insert(tk.END,item[0]+'\n','heading')
                target.insert(tk.END,item[1]+'\n\n','detail')
                if not formulas:
                    from toolbar_icons import DESCRIPTIONS
                    idx=next((i for i,title in enumerate(self._full_tab_titles) if title==item[0]),None)
                    if idx is not None:
                        target.insert(tk.END,'Toolbar commands\n','heading')
                        tab=self.ribbon_notebook.tabs()[idx]
                        for key,label,commands in self._toolbar_icon_catalog.get(str(tab),[]):
                            target.image_create(tk.END,image=self._toolbar_icon_images[key])
                            target.insert(tk.END,'  '+label+'\n','heading')
                            target.insert(tk.END,DESCRIPTIONS[key]+'\n','detail')
                            if commands:target.insert(tk.END,'Commands: '+ '; '.join(commands)+'\n\n','detail')
                target._formula_images=[]
                if formulas:
                    for expression,explanation in item[2]:
                        try:
                            from matplotlib.mathtext import math_to_image
                            from PIL import Image,ImageTk
                            output=io.BytesIO()
                            math_to_image('$'+expression+'$',output,dpi=125,format='png',color='#18334a')
                            output.seek(0);raster=Image.open(output)
                            limit=max(220,target.winfo_width()-35)
                            if raster.width>limit:
                                raster=raster.resize((limit,max(12,round(raster.height*limit/raster.width))),
                                                     getattr(Image,'Resampling',Image).LANCZOS)
                            photo=ImageTk.PhotoImage(raster,master=self.root)
                            target.image_create(tk.END,image=photo);target._formula_images.append(photo)
                        except (ImportError,ValueError,RuntimeError):
                            target.insert(tk.END,expression)
                        target.insert(tk.END,'\n'+explanation+'\n\n','detail')
                target.configure(state='disabled');target.yview_moveto(0)
            sections.bind('<<ListboxSelect>>',select)
            if title=='Formulas':
                def rescale(_event,box=sections,target=reader,callback=select):
                    job=getattr(target,'_formula_resize_job',None)
                    if job is not None:self.root.after_cancel(job)
                    target._formula_resize_job=self.root.after(180,callback)
                reader.bind('<Configure>',rescale)
            sections.selection_set(0)
            self.root.after_idle(select)
        self._refresh_recent_projects()
        self._install_energy_workspace()
        if self._get_active_tab_index()==0:
            self._show_home()

    def _home_task_start(self,label):
        if not hasattr(self,'home_task_frame'):return
        if self._home_task_hide_job is not None:
            try:self.root.after_cancel(self._home_task_hide_job)
            except tk.TclError:pass
            self._home_task_hide_job=None
        self.home_task_label.configure(text=label)
        self.home_task_percent.configure(text='')
        self.home_task_progress.stop()
        self.home_task_progress.configure(mode='indeterminate',maximum=100,value=0)
        self.home_task_progress.start(12)
        self.home_task_cancel.state(['!disabled'])
        if not self.home_task_frame.winfo_manager():
            self.home_task_frame.pack(fill=tk.X,pady=(0,8),before=self.home_guide_heading)

    def _home_task_progress_update(self,current,total,message=None):
        if not hasattr(self,'home_task_frame'):return
        if not self.home_task_frame.winfo_manager():self._home_task_start('Working...')
        try:
            current=float(current);total=float(total)
            if total>0:
                self.home_task_progress.stop()
                self.home_task_progress.configure(mode='determinate',maximum=total,value=max(0,min(current,total)))
                pct=max(0,min(100,round(100*current/total)))
                self.home_task_percent.configure(text=f'{pct}%')
        except (TypeError,ValueError,ZeroDivisionError):
            pass
        if message:self.home_task_label.configure(text=str(message))

    def _home_task_finish(self,message='Ready',failed=False):
        if not hasattr(self,'home_task_frame'):return
        self.home_task_progress.stop()
        self.home_task_progress.configure(mode='determinate',maximum=100,value=0 if failed else 100)
        self.home_task_percent.configure(text='' if failed else '100%')
        self.home_task_label.configure(text=message)
        self.home_task_cancel.state(['disabled'])
        if self._home_task_hide_job is not None:
            try:self.root.after_cancel(self._home_task_hide_job)
            except tk.TclError:pass
        def hide():
            self._home_task_hide_job=None
            if self.home_task_frame.winfo_manager():self.home_task_frame.pack_forget()
        self._home_task_hide_job=self.root.after(2200 if not failed else 3500,hide)

    def _install_energy_workspace(self):
        self.energy_workspace=ttk.Frame(self.main_container,padding=15)
        ttk.Label(self.energy_workspace,text='Hourly energy and storage',font=('Arial',16,'bold')).pack(anchor='w')
        self.energy_description=ttk.Label(self.energy_workspace,text='',wraplength=680,justify=tk.LEFT)
        self.energy_description.pack(anchor='w',fill=tk.X,pady=(5,12))
        self.energy_description.bind('<Configure>',lambda e:self.energy_description.configure(wraplength=max(200,e.width-20)))
        actions=ttk.Frame(self.energy_workspace);actions.pack(fill=tk.X,pady=4)
        for label,command in [('Import consumption',self._load_consumption_excel),
                              ('Calculate 3 options',self._calculate_self_consumption),
                              ('Annual chart',self._open_annual_chart),
                              ('24-hour chart',self._open_hourly_chart),
                              ('Economics',self._show_energy_economics)]:
            ttk.Button(actions,text=label,command=command).pack(side=tk.LEFT,padx=(0,5))
        columns=('scenario','pv','load','direct','battery','grid','export')
        frame=ttk.Frame(self.energy_workspace);frame.pack(fill=tk.BOTH,expand=True,pady=10)
        self.energy_tree=ttk.Treeview(frame,columns=columns,show='headings',height=4)
        for name,title,width in [('scenario','Configuration',145),('pv','PV kWh',110),('load','Load kWh',110),
                                 ('direct','Direct kWh',110),('battery','BESS kWh',110),
                                 ('grid','Grid kWh',110),('export','Export kWh',110)]:
            self.energy_tree.heading(name,text=title);self.energy_tree.column(name,width=width,minwidth=80)
        self.energy_tree.pack(side=tk.TOP,fill=tk.BOTH,expand=True)
        xs=ttk.Scrollbar(frame,orient=tk.HORIZONTAL,command=self.energy_tree.xview)
        xs.pack(fill=tk.X);self.energy_tree.configure(xscrollcommand=xs.set)
        self._refresh_energy_workspace()

    def _refresh_energy_workspace(self):
        if not hasattr(self,'energy_tree'):return
        for row in self.energy_tree.get_children():self.energy_tree.delete(row)
        for label,summary in [('PV only',self.self_consumption_summary),('1 BESS',self.bess_summary),('2 BESS',self.two_bess_summary)]:
            annual=(summary or {}).get('annual') or {}
            if not annual:continue
            fmt=lambda key:f"{annual.get(key,0):,.0f}"
            self.energy_tree.insert('',tk.END,values=(label,fmt('pv_kwh'),fmt('load_kwh'),
                f"{annual.get('direct_kwh',annual.get('self_kwh',0)):,.0f}",fmt('discharge_ac_kwh'),
                fmt('grid_kwh'),fmt('export_kwh')))
        source=(self.self_consumption_summary or {}).get('method','Clear-sky estimate')
        source={'cielo sereno + ombra':'clear-sky estimate + shading',
                'meteo storico orario + ombra':'historical hourly weather + shading'}.get(source,source)
        status='Saved results require recalculation after source or layout changes.' if getattr(self,'hourly_pv_kwh',None) and not self._energy_results_current() else ''
        self.energy_description.configure(text=f'Annual AC energy, in kWh. Source: {source}. '
            'PV serves the cold-store load first; batteries use surplus PV and the remainder is exported up to the requested limit. '
            +status if self.energy_tree.get_children() else 'Import an hourly consumption file, then calculate PV only / one BESS / two BESS. '
            'Optional historical weather is available under Data. No roof canvas is shown here.')

    def _energy_results_current(self):
        try:return self.energy_source_signature==self._energy_signature()
        except (ValueError,KeyError,TypeError,AttributeError):return False

    def _calculate_self_consumption(self):
        result=super()._calculate_self_consumption()
        self._refresh_energy_workspace()
        return result

    def _on_ribbon_tab_changed(self,event):
        result=super()._on_ribbon_tab_changed(event)
        if hasattr(self,'home_frame'):
            if self._get_active_tab_index()==0:self._show_home()
            else:self.home_frame.pack_forget()
        if hasattr(self,'energy_workspace'):
            if self._get_active_tab_index()==9:
                self.canvas_frame.pack_forget();self._refresh_energy_workspace()
                self.energy_workspace.pack(fill=tk.BOTH,expand=True)
            else:self.energy_workspace.pack_forget()
        return result

    def _show_home(self):
        self._refresh_recent_projects()
        self.canvas_frame.pack_forget()
        if not self.home_frame.winfo_manager():self.home_frame.pack(fill=tk.BOTH,expand=True)

    def _show_help(self,page='quick'):
        self.ribbon_notebook.select(0)
        if hasattr(self,'home_guide_notebook'):
            self.home_guide_notebook.select(1 if page in ('formulas','technical') else 0)

    def _recent_path(self):
        return Path(os.environ.get('PV_APP_RECENTS_FILE', str(Path.home()/'.pv_layout_app'/'recent.json')))

    def _read_recent_projects(self):
        try:
            data=json.loads(self._recent_path().read_text(encoding='utf-8'))
            return [x for x in data if isinstance(x,dict) and isinstance(x.get('path'),str)][:15]
        except (OSError,ValueError,TypeError):
            return []

    def _remember_recent_project(self,path):
        path=str(Path(path).resolve())
        records=[r for r in self._read_recent_projects() if r['path']!=path]
        records.insert(0,{'path':path,'last_opened':dt.datetime.now().astimezone().isoformat(timespec='seconds')})
        dest=self._recent_path()
        try:
            dest.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.NamedTemporaryFile('w',encoding='utf-8',dir=dest.parent,
                                             delete=False) as output:
                json.dump(records[:15],output,ensure_ascii=False,indent=2)
                temporary=output.name
            os.replace(temporary,dest)
        except OSError:
            return  # Recent history must never prevent opening a project.
        self._refresh_recent_projects()

    def _refresh_recent_projects(self):
        if not hasattr(self,'recent_tree'):return
        self.home_active_label.configure(text=f'Active project: {self.project_name}')
        tree=self.recent_tree
        for item in tree.get_children():tree.delete(item)
        for record in self._read_recent_projects():
            path=Path(record['path'])
            date=record.get('last_opened','')
            tree.insert('',tk.END,iid=str(path),values=(path.stem,date.replace('T',' ')[:19],str(path)))

    def _open_recent_selection(self):
        selection=self.recent_tree.selection()
        if not selection:return
        path=selection[0]
        if not Path(path).is_file():
            messagebox.showwarning('Recent projects',f'Project no longer found:\n{path}')
            return
        self._load_project_file(path)

    def on_left_press(self,event):
        idx=self._get_active_tab_index()
        plain=not bool(event.state & 0x0005)
        special=(idx==1 and (self.path_mode!='select' or self.roof_mode!='select')) or \
                (idx==2 and self.layout_mode!='select') or \
                (idx==5 and self.shadow_mode!='select') or \
                (idx==7 and self._hit_test_diagram_node(self.canvas.canvasx(event.x),self.canvas.canvasy(event.y)) is not None) or \
                (idx==8 and self.path_mode!='select')
        if plain and not special:
            self._canvas_pan_start=(event.x,event.y)
            self._canvas_panning=False
            self.canvas.scan_mark(event.x,event.y)
            return
        self._canvas_pan_start=None
        return super().on_left_press(event)

    def on_left_drag(self,event):
        start=getattr(self,'_canvas_pan_start',None)
        if start is not None:
            if self._canvas_panning or abs(event.x-start[0])+abs(event.y-start[1])>5:
                self._canvas_panning=True
                self._auto_fit=False
                self.canvas.scan_dragto(event.x,event.y,gain=1)
            return
        return super().on_left_drag(event)

    def on_left_release(self,event):
        start=getattr(self,'_canvas_pan_start',None)
        if start is not None:
            panning=self._canvas_panning
            self._canvas_pan_start=None
            self._canvas_panning=False
            self.canvas.configure(cursor='')
            if panning:return
            result=super().on_left_press(event)
            super().on_left_release(event)
            return result
        return super().on_left_release(event)

    def _export_with_csv_preview(self,callback,initialfile='export.csv'):
        """Run the existing CSV writer against a private temporary path, then preview and save."""
        with tempfile.TemporaryDirectory(prefix='pv-csv-') as folder:
            staged=str(Path(folder)/'preview.csv')
            original_dialog=filedialog.asksaveasfilename
            original_info=messagebox.showinfo
            filedialog.asksaveasfilename=lambda **kwargs:staged
            messagebox.showinfo=lambda *args,**kwargs:None
            try:
                callback()
            finally:
                filedialog.asksaveasfilename=original_dialog
                messagebox.showinfo=original_info
            if not Path(staged).is_file():return
            self._preview_csv_file(staged,initialfile)

    def _preview_csv_file(self,staged,initialfile):
        win=tk.Toplevel(self.root)
        win.title('CSV preview — review before saving')
        body=ttk.Frame(win,padding=10)
        body.pack(fill=tk.BOTH,expand=True)
        with open(staged,newline='',encoding='utf-8-sig') as source:
            lines=list(csv.reader(source,delimiter=';'))
        ttk.Label(body,text=f'{len(lines)} rows · CSV separated by semicolons').pack(anchor='w')
        box=ttk.Frame(body)
        box.pack(fill=tk.BOTH,expand=True,pady=8)
        box.rowconfigure(0,weight=1)
        box.columnconfigure(0,weight=1)
        preview=tk.Text(box,wrap='none',font=('Courier New',10),state='normal')
        preview.grid(row=0,column=0,sticky='nsew')
        yscroll=ttk.Scrollbar(box,orient=tk.VERTICAL,command=preview.yview)
        yscroll.grid(row=0,column=1,sticky='ns')
        xscroll=ttk.Scrollbar(box,orient=tk.HORIZONTAL,command=preview.xview)
        xscroll.grid(row=1,column=0,sticky='ew')
        preview.configure(yscrollcommand=yscroll.set,xscrollcommand=xscroll.set)
        for row in lines[:500]:preview.insert(tk.END,'  |  '.join(row)+'\n')
        if len(lines)>500:preview.insert(tk.END,f'… {len(lines)-500} more rows in the export\n')
        preview.configure(state='disabled')
        controls=ttk.Frame(body)
        controls.pack(fill=tk.X)
        def save():
            dest=filedialog.asksaveasfilename(parent=win,title='Save CSV',
                                              defaultextension='.csv',initialfile=initialfile,
                                              filetypes=[('CSV files','*.csv')])
            if not dest:return
            try:shutil.copyfile(staged,dest)
            except OSError as exc:messagebox.showerror('CSV export',str(exc),parent=win);return
            win.destroy()
            messagebox.showinfo('CSV export',f'Saved:\n{dest}',parent=self.root)
        ttk.Button(controls,text='Cancel',command=win.destroy).pack(side=tk.RIGHT)
        ttk.Button(controls,text='Save CSV…',command=save).pack(side=tk.RIGHT,padx=8)
        self._fit_dialog(win,860,550)
        win.transient(self.root)
        win.grab_set()
        self.root.wait_window(win)

    def export_csv(self):return self._export_with_csv_preview(lambda:super(WorkspaceImprovementsMixin,self).export_csv(),'stringing.csv')
    def export_mppt_csv(self):return self._export_with_csv_preview(lambda:super(WorkspaceImprovementsMixin,self).export_mppt_csv(),'mppt_assignments.csv')
    def _export_cable_routes_csv(self):return self._export_with_csv_preview(lambda:super(WorkspaceImprovementsMixin,self)._export_cable_routes_csv(),'cable_routes.csv')
    def _export_spreadsheet_csv(self):return self._export_with_csv_preview(lambda:super(WorkspaceImprovementsMixin,self)._export_spreadsheet_csv(),'spreadsheet.csv')
    def _export_self_consumption(self):return self._export_with_csv_preview(lambda:super(WorkspaceImprovementsMixin,self)._export_self_consumption(),'hourly_energy.csv')
