"""Project setup, embedded BESS comparison and report entry point."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import math
from pathlib import Path

class ProjectWorkspaceMixin:
    def _build_tab_file_tools(self):
        super()._build_tab_file_tools()
        ttk.Button(self.tab_file,text='Configuration',command=self._show_project_configuration).pack(side='left',padx=5)
        ttk.Button(self.tab_file,text='Engineering report PDF',command=self._export_engineering_report).pack(side='left',padx=5)

    def _show_project_configuration(self):
        from mixins.configuration_questionnaire import show_questionnaire
        show_questionnaire(self)

    def _open_equipment_configuration(self):
        self._equipment_window.deiconify();self._fit_dialog(self._equipment_window,1000,550)

    def _show_grid_configuration(self):
        win=tk.Toplevel(self.root);win.title('Grid connection');entries={}
        for i,(key,label) in enumerate([('existing_contract_kw','Contract power (kW)'),('export_limit_kw','Export limit used in simulation (kW)')]):
            ttk.Label(win,text=label).grid(row=i,column=0,padx=12,pady=10)
            e=ttk.Entry(win);e.insert(0,str(self.grid_connection_settings.get(key,'')));e.grid(row=i,column=1,padx=12);entries[key]=e
        def save():
            try:
                values={k:float(e.get()) for k,e in entries.items()}
                if any(not math.isfinite(v) or v<0 for v in values.values()):raise ValueError
            except ValueError:messagebox.showerror('Invalid power','Enter nonnegative finite kW values.',parent=win);return
            self.grid_connection_settings.update(values);win.destroy();self._refresh_energy_workspace()
        ttk.Button(win,text='Apply',command=save).grid(row=2,column=1,pady=12)

    def _install_energy_workspace(self):
        self.energy_workspace=ttk.Frame(self.main_container,padding=14)
        ttk.Label(self.energy_workspace,text='Compare PV only, one battery cabinet and two cabinets',font=('Arial',14,'bold')).pack(anchor='w')
        self.energy_description=ttk.Label(self.energy_workspace,wraplength=1000,justify='left')
        self.energy_description.pack(fill='x',pady=8)
        ttk.Label(self.energy_workspace,text='1. Data: import hourly load and optional weather.  2. Settings: review equipment assumptions.  3. Calculate once in the toolbar.\nPV supplies the load first. Surplus charges the battery, then is exported or curtailed. Batteries cover later deficits; the grid supplies the rest.\nTwo cabinets increase capacity; the configured inverter power limits stay shared. No grid charging, market arbitrage or ancillary-service income is modelled.',wraplength=1000,justify='left').pack(fill='x',pady=4)
        frame=ttk.Frame(self.energy_workspace);frame.pack(fill='x',pady=6)
        columns=('scenario','pv','load','direct','battery','grid','export')
        self.energy_tree=ttk.Treeview(frame,columns=columns,show='headings',height=3)
        for key,title in zip(columns,('Configuration','PV kWh','Load kWh','Direct PV kWh','BESS to load kWh','Grid import kWh','Export kWh')):
            self.energy_tree.heading(key,text=title);self.energy_tree.column(key,width=135,minwidth=95)
        self.energy_tree.pack(fill='x')
        scroll=ttk.Scrollbar(frame,orient='horizontal',command=self.energy_tree.xview);scroll.pack(fill='x');self.energy_tree.configure(xscrollcommand=scroll.set)
        self.energy_chart_frame=ttk.Frame(self.energy_workspace);self.energy_chart_frame.pack(fill='both',expand=True)
        self._energy_chart=None;self._refresh_energy_workspace()

    def _refresh_energy_workspace(self):
        super()._refresh_energy_workspace()
        if not hasattr(self,'energy_chart_frame'):return
        for child in self.energy_chart_frame.winfo_children():child.destroy()
        self._energy_chart=None
        current=self._energy_results_current()
        if not current:
            for row in self.energy_tree.get_children():self.energy_tree.delete(row)
            self.energy_description.configure(text='No current comparison. Import data, review settings and calculate. Saved results are hidden if project inputs have changed.')
            return
        summaries=[self.self_consumption_summary,self.bess_summary,self.two_bess_summary]
        if not all(s.get('annual') for s in summaries):return
        from energy_charts import comparison_figure
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        fig=comparison_figure(summaries)
        self._energy_chart=FigureCanvasTkAgg(fig,master=self.energy_chart_frame)
        self._energy_chart.get_tk_widget().pack(fill='both',expand=True);self._energy_chart.draw()
        profile=self.hourly_consumption_profile or {}
        self.energy_description.configure(text=f"Energy over the imported period ({len(profile.get('hourly_kwh',[]))} hourly values); {len(profile.get('imputed_indices',[]))} load values filled by the importer. Source: {self.self_consumption_summary.get('method','Not supplied')}. All quantities are AC-side kWh; totals are not extrapolated to a year.")

    def _export_engineering_report(self):
        path=filedialog.asksaveasfilename(title='Engineering project report',defaultextension='.pdf',filetypes=[('PDF','*.pdf')])
        if not path:return
        try:
            from engineering_report import export_report
            export_report(self,Path(path))
            messagebox.showinfo('Report exported','PDF, editable LaTeX source, figure files and project input snapshot exported together.')
        except Exception as exc:messagebox.showerror('Report export failed',str(exc))

    def _calculate_self_consumption(self):
        issues=self._layout_issues()
        if issues:
            messagebox.showerror('Invalid layout', '\n'.join(issues[:12])+'\nRegenerate or correct the layout before calculating energy.')
            return
        return super()._calculate_self_consumption()

    def _install_home(self):
        super()._install_home()
