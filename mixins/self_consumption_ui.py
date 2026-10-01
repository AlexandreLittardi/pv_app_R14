"""Onglet Volfrigo: bilancio orario produzione FV / consumo frigorifero."""
import os
import datetime as dt
import tempfile
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from self_consumption import balance, production_from_program, read_daily_excel, read_open_meteo_json
from battery_dispatch import BatterySettings, simulate_three_options, write_comparison_csv
from energy_economics import evaluate_options,validate_settings,write_economic_csv,storage_margin_per_charge_kwh


class SelfConsumptionMixin:
    def _build_self_consumption_tab(self):
        tab=ttk.Frame(self.ribbon_notebook,padding=5)
        self.tab_energy=tab
        self.ribbon_notebook.add(tab,text='Energy / BESS')
        self._energy_settings_window=tk.Toplevel(self.root)
        self._energy_settings_window.title('Energy / battery settings')
        self._energy_settings_window.withdraw()
        self._energy_settings_window.protocol('WM_DELETE_WINDOW',self._energy_settings_window.withdraw)
        frm=ttk.Frame(self._energy_settings_window,padding=10);frm.pack(fill=tk.BOTH,expand=True)
        ttk.Label(frm,text='AC factor (0–1)').grid(row=0,column=0,sticky='w',pady=3)
        self.self_ac_entry=ttk.Entry(frm,width=10);self.self_ac_entry.insert(0,'0.90');self.self_ac_entry.grid(row=0,column=1)
        self._bess_defaults={'nominal_kwh':522.496,'charge_kw':250,'discharge_kw':150,'soc_min_pct':10,'soc_max_pct':90,'round_trip_efficiency':.90}
        labels=['Capacity per cabinet (kWh)','Total charge power (kW)','Total discharge power (kW)','Minimum SOC (%)','Maximum SOC (%)','Round-trip efficiency']
        self.bess_entries={}
        for i,((key,value),label) in enumerate(zip(self._bess_defaults.items(),labels),1):
            ttk.Label(frm,text=label).grid(row=i,column=0,sticky='w',pady=3)
            e=ttk.Entry(frm,width=10);e.insert(0,str(value));e.grid(row=i,column=1,padx=6);self.bess_entries[key]=e
        ttk.Label(frm,text='Review grid limits under Home > Configuration.\nThese battery values are editable assumptions. Shared power limits apply to both 1 and 2 BESS.',wraplength=450).grid(row=7,column=0,columnspan=2,pady=10)
        ttk.Button(frm,text='Close',command=self._energy_settings_window.withdraw).grid(row=8,column=1,pady=5)
        mb=ttk.Menubutton(tab,text='Data');menu=tk.Menu(mb,tearoff=False)
        for label,cmd in [('Import consumption Excel',self._load_consumption_excel),('Download historical weather',self._download_historical_weather),('Import weather JSON',self._import_historical_weather)]:menu.add_command(label=label,command=cmd)
        mb.configure(menu=menu);mb.pack(side=tk.LEFT,padx=3)
        ttk.Button(tab,text='Calculate 3 options',command=self._calculate_self_consumption).pack(side=tk.LEFT,padx=3)
        result=ttk.Menubutton(tab,text='Results');menu=tk.Menu(result,tearoff=False)
        for label,cmd in [('Period / monthly comparison',self._show_self_consumption_result),('Monthly chart',self._open_annual_chart),('Hourly chart (24 h)',self._open_hourly_chart),('Economics / export / EMS',self._show_energy_economics),('Export hourly CSV',self._export_self_consumption)]:menu.add_command(label=label,command=cmd)
        result.configure(menu=menu);result.pack(side=tk.LEFT,padx=3)
        ttk.Button(tab,text='Settings',command=self._show_energy_settings).pack(side=tk.LEFT,padx=3)
        self.self_status=ttk.Label(tab,text='Import consumption to begin.');self.self_status.pack(side=tk.LEFT,padx=5)

    def _show_energy_settings(self):
        self._energy_settings_window.deiconify();self._fit_dialog(self._energy_settings_window,520,390)

    def _load_consumption_excel(self):
        path=filedialog.askopenfilename(title='Import hourly consumption (Excel or timestamp CSV)',
                                        filetypes=[('Hourly files','*.xlsx *.csv')])
        if not path:return
        try:
            from self_consumption import read_hourly_csv
            self.hourly_consumption_profile=(read_hourly_csv(path,self.model_settings['timezone']) if path.lower().endswith('.csv') else read_daily_excel(path,self.model_settings.get('imputation','previous_week')))
            self.hourly_pv_kwh=[]
            self.hourly_weather_profile={}
            self.self_consumption_summary={}
            self.bess_summary={}
            self.two_bess_summary={}
            profile=self.hourly_consumption_profile
            self.self_status.config(text=f"{len(profile['hourly_kwh'])} hours, "
                                    f"{len(profile['imputed_indices'])} estimated load values. Calculate PV.")
        except Exception as exc:
            messagebox.showerror('Invalid consumption data',str(exc))

    def _show_energy_economics(self):
        if not self._require_current_energy():return
        from energy_economics import covers_full_year
        if not covers_full_year(self.hourly_consumption_profile):
            messagebox.showwarning('Complete year required','Payback requires a full year of hourly consumption. The engineering report can still show monetary benefits over the imported period.')
            return
        summaries=[getattr(self,key,{}) for key in
                   ('self_consumption_summary','bess_summary','two_bess_summary')]
        if (not all(s.get('annual') for s in summaries) or
            self.self_consumption_summary.get('export_limit_kw') != self.grid_connection_settings['export_limit_kw']):
            messagebox.showwarning('Missing balance','Calculate the three options first.');return
        try:
            cfg=self.bess_summary['battery_settings']
            if any(abs(float(entry.get().replace(',','.'))-cfg[key])>1e-9
                   for key,entry in self.bess_entries.items()):
                messagebox.showwarning('BESS settings changed','Recalculate the three options before comparing costs.');return
        except (ValueError,KeyError):
            messagebox.showwarning('BESS','Invalid parameters: recalculate.');return
        win=tk.Toplevel(self.root);win.title(f'{self.project_name} — Energy economics')
        win.geometry('1080x600')
        pages=ttk.Notebook(win);pages.pack(fill=tk.BOTH,expand=True)
        comparison_page=ttk.Frame(pages);prices_page=ttk.Frame(pages);guide_page=ttk.Frame(pages)
        for page,label in [(comparison_page,'Comparison'),(prices_page,'Prices / investment'),(guide_page,'EMS / assumptions')]:pages.add(page,text=label)
        controls=ttk.Frame(prices_page,padding=8);controls.pack(fill=tk.X)
        labels=[('Grid purchase €/kWh','import_eur_kwh'),('Export low €/kWh','export_low_eur_kwh'),
                ('Export high €/kWh','export_high_eur_kwh'),('PV investment €','pv_capex_eur'),
                ('Cost per BESS €','bess_capex_each_eur')]
        entries={};settings=validate_settings(getattr(self,'economic_settings',{}))
        for i,(label,key) in enumerate(labels):
            row=ttk.Frame(controls);row.pack(fill=tk.X)
            ttk.Label(row,text=label,width=22).pack(side=tk.LEFT,padx=4)
            e=ttk.Combobox(row,values=('0.25','0.32'),width=8) if key=='import_eur_kwh' else ttk.Entry(row,width=8)
            e.insert(0,str(settings[key]));e.pack(side=tk.LEFT)
            entries[key]=e
        columns=[('case','BESS',50),('price','Export €/kWh',100),('saved','Avoided purchases €',140),
                 ('export','Export revenue €',120),('total','Total savings €',125),('net','Net cost €',115),
                 ('capital','Investment €',100),('years','Payback years',95),
                 ('delta','Extra BESS €/year',145),('pb_delta','Extra payback years',125),('npv','NPV €',120),('discounted','Discounted payback years',160)]
        table_frame=ttk.Frame(comparison_page);table_frame.pack(fill=tk.BOTH,expand=True,padx=10,pady=8)
        tree=ttk.Treeview(table_frame,columns=[c[0] for c in columns],show='headings',height=6)
        for key,title,width in columns:tree.heading(key,text=title);tree.column(key,width=width)
        sx=ttk.Scrollbar(table_frame,orient=tk.HORIZONTAL,command=tree.xview)
        tree.configure(xscrollcommand=sx.set);sx.pack(side=tk.BOTTOM,fill=tk.X)
        tree.pack(fill=tk.BOTH,expand=True)
        guidance=ttk.Label(guide_page,text='',wraplength=650,justify=tk.LEFT)
        guidance.pack(fill=tk.X,padx=12,pady=10)
        ttk.Label(guide_page,text='Net cost = residual grid purchases − export revenue. Savings = cost without PV − net cost. '
                  'The incremental BESS benefit deducts export revenue forgone. Maintenance, discount rate and degradation use Model settings; replacement uses the saved economic settings. Taxes and financing are excluded. PV source: '+summaries[0].get('method','unspecified')+'.',
                  wraplength=650,justify=tk.LEFT).pack(fill=tk.X,padx=12,pady=8)
        ttk.Label(guide_page,text='This window values the simulated self-consumption dispatch; it does not control the EMS '
                  'or optimize hourly tariffs. Recalculate the three scenarios after editing PV, consumption or storage. '
                  'Save the project JSON to keep the prices and investments.',
                  wraplength=650,justify=tk.LEFT).pack(fill=tk.X,padx=12,pady=8)
        guide_page.bind("<Configure>",lambda e:[w.configure(wraplength=max(200,e.width-30)) for w in guide_page.winfo_children() if isinstance(w,ttk.Label)])
        result_rows=[]
        def refresh():
            try:
                current=validate_settings({**self.economic_settings,**{k:e.get().replace(',','.') for k,e in entries.items()}})
                new=evaluate_options([s['annual'] for s in summaries],current)
                self.economic_settings=current
                result_rows[:]=new
                for item in tree.get_children():tree.delete(item)
                for r in new:
                    fmt=lambda value:'—' if value is None else f'{value:,.2f}'
                    tree.insert('',tk.END,values=(r['bess_count'],f"{r['export_eur_kwh']:.3f}",
                        *(fmt(r[k]) for k in ('avoided_purchases_eur','export_revenue_eur',
                        'total_benefit_eur','net_energy_outlay_eur','capex_eur','simple_payback_years','incremental_benefit_eur','incremental_payback_years','net_present_value_eur','discounted_payback_years'))))
                margins=storage_margin_per_charge_kwh(current,cfg['round_trip_efficiency'])
                lo=min(margins.values());hi=max(margins.values())
                guidance.config(text=f"EMS - gross value per PV kWh charged then used: {lo:.3f}–{hi:.3f} €/kWh. "
                    f"Break-even export price: efficiency × purchase price = "
                    f"{cfg['round_trip_efficiency']*current['import_eur_kwh']:.3f} €/kWh, before wear and auxiliaries. "
                    'Charging requires future load and available SOC/power; export the remainder. '
                    + ('Storage has positive gross margin at these prices.' if lo>0 else
                       'CAUTION: some prices do not justify charging; current dispatch is not optimized for hourly tariffs.'))
                return True
            except (ValueError,KeyError) as exc:
                messagebox.showerror('Economics',str(exc),parent=win);return False
        def export():
            if not refresh():return
            path=filedialog.asksaveasfilename(parent=win,defaultextension='.csv',
                initialfile=self.project_name+'_energy_economics.csv',filetypes=[('CSV','*.csv')])
            if path:write_economic_csv(path,result_rows)
        buttons=ttk.Frame(win,padding=10);buttons.pack(fill=tk.X)
        ttk.Button(buttons,text='Update economics',command=refresh).pack(side=tk.LEFT,padx=5)
        ttk.Button(buttons,text='Export economics CSV',
                   command=lambda:self._export_with_csv_preview(export,self.project_name+'_economics.csv')).pack(side=tk.LEFT,padx=5)
        refresh()

    def _import_historical_weather(self):
        path=filedialog.askopenfilename(title='Historical Open-Meteo JSON',
                                        filetypes=[('JSON','*.json')])
        if not path:return
        try:
            self.hourly_weather_profile=read_open_meteo_json(path,self.hourly_consumption_profile)
            self.hourly_pv_kwh=[];self.self_consumption_summary={};self.bess_summary={};self.two_bess_summary={}
            self.self_status.config(text='Historical weather imported: calculate PV.')
        except Exception as exc:
            messagebox.showerror('Invalid weather data',str(exc))

    def _download_historical_weather(self):
        profile=getattr(self,'hourly_consumption_profile',None)
        if not profile:
            messagebox.showwarning('Consumption missing','Import hourly consumption first.');return
        try:
            start=(dt.date.fromisoformat(profile['start_date'])-dt.timedelta(days=1)).isoformat()
            end=(dt.date.fromisoformat(profile['end_date'])+dt.timedelta(days=1)).isoformat()
            az=(float(self.panel_azimuth_deg)-180+180)%360-180
            params={'latitude':self.solar_latitude,'longitude':self.solar_longitude,
                    'start_date':start,'end_date':end,
                    'hourly':'global_tilted_irradiance,temperature_2m',
                    'tilt':self.panel_tilt_deg,'azimuth':az,'timezone':self.model_settings['timezone'],
                    'models':'best_match'}
            url='https://archive-api.open-meteo.com/v1/archive?'+urlencode(params)
            self.self_status.config(text='Downloading historical weather…')
            self.root.update_idletasks()
            request=Request(url,headers={'User-Agent':'PV-App-R13/1.0'})
            with urlopen(request,timeout=60) as response:
                payload=response.read(3_000_000)
            with tempfile.NamedTemporaryFile(suffix='.json',delete=False) as tmp:
                tmp.write(payload);temp_path=tmp.name
            try:
                weather=read_open_meteo_json(temp_path,profile)
            finally:
                os.unlink(temp_path)
            weather['source_filename']='Open-Meteo Historical API - Best Match'
            weather['query']={'latitude':self.solar_latitude,'longitude':self.solar_longitude,
                              'tilt_deg':self.panel_tilt_deg,'azimuth_deg_from_south':az,
                              'meteo_model':'best_match','download_period':[start,end]}
            self.hourly_weather_profile=weather
            self.hourly_pv_kwh=[];self.self_consumption_summary={};self.bess_summary={};self.two_bess_summary={}
            self.self_status.config(text='Historical weather available: calculate PV.')
        except Exception as exc:
            self.self_status.config(text='Historical weather download failed.')
            messagebox.showerror('Weather download',str(exc))

    def _calculate_self_consumption(self):
        self._sync_module_power()
        profile=getattr(self,'hourly_consumption_profile',None)
        if not profile:
            messagebox.showwarning('Consumption missing','Import the consumption Excel file.')
            return
        try:
            ac_factor=float(self.self_ac_entry.get().replace(',','.'))
            self.self_status.config(text='Calculating hourly PV…')
            def update(done,total):
                self.self_status.config(text=f'Calculating hourly PV: {done}/{total}')
                self.root.update_idletasks()
            weather=getattr(self,'hourly_weather_profile',None)
            pv=production_from_program(self,profile,ac_factor,update,weather=weather)
            result=balance(profile,pv,self.grid_connection_settings["export_limit_kw"])
            numeric={key:float(entry.get().replace(',','.'))
                     for key,entry in self.bess_entries.items()}
            battery=BatterySettings(nominal_kwh=numeric['nominal_kwh'],
                                    charge_kw=numeric['charge_kw'],
                                    discharge_kw=numeric['discharge_kw'],
                                    soc_min_pct=numeric['soc_min_pct'],
                                    soc_max_pct=numeric['soc_max_pct'],
                                    initial_soc_pct=numeric['soc_min_pct'],
                                    round_trip_efficiency=numeric['round_trip_efficiency'])
            options=simulate_three_options(profile,pv,battery,self.grid_connection_settings["export_limit_kw"])
            comparison={}
            if weather:
                sky=balance(profile,production_from_program(self,profile,ac_factor))
                comparison={'clear_sky_annual_kwh':sky['annual']['pv_kwh'],
                            'weather_to_clear_sky_pct':100*result['annual']['pv_kwh']/sky['annual']['pv_kwh'],
                            'monthly_correction_pct':{
                                m:(100*r['pv_kwh']/sky['monthly'][m]['pv_kwh']
                                   if sky['monthly'][m]['pv_kwh'] else 0)
                                for m,r in result['monthly'].items()}}
            self.hourly_pv_kwh=pv
            self.bess_summary={'annual':options['one_bess']['annual'],
                               'monthly':options['one_bess']['monthly'],
                               'battery_settings':options['one_bess']['settings']}
            self.two_bess_summary={'annual':options['two_bess']['annual'],
                                   'monthly':options['two_bess']['monthly'],
                                   'battery_settings':options['two_bess']['settings']}
            self.self_consumption_summary={'annual':result['annual'],'monthly':result['monthly'],
                                           'ac_factor':ac_factor,'export_limit_kw':self.grid_connection_settings['export_limit_kw'],
                                           'comparison':comparison,
                                           'method':('historical hourly weather + shading' if weather
                                                     else 'clear-sky estimate + shading')}
            self.energy_source_signature=self._energy_signature()
            self._refresh_energy_workspace()
        except Exception as exc:
            messagebox.showerror('Self-consumption calculation failed',str(exc))

    def _show_self_consumption_result(self):
        if not self._require_current_energy():return
        result=getattr(self,'self_consumption_summary',{})
        if not result:return
        a=result['annual']
        bess=getattr(self,'bess_summary',{})
        two=getattr(self,'two_bess_summary',{})
        if not bess or not two:
            messagebox.showwarning('BESS not calculated','Calculate all three options first.')
            return
        try:
            cfg=bess['battery_settings']
            if any(abs(float(entry.get().replace(',','.'))-cfg[key])>1e-9
                   for key,entry in self.bess_entries.items()):
                messagebox.showwarning('BESS settings changed',
                                       'Recalculate all three options with the new settings.')
                return
        except (KeyError,ValueError):
            messagebox.showwarning('Invalid BESS settings','Correct the settings and recalculate.')
            return
        b=bess.get('annual',{})
        c=two.get('annual',{})
        self.self_status.config(text=f"PV {a['pv_kwh']/1000:.1f} MWh; "
                                f"0 BESS {a['self_kwh']/1000:.1f} MWh; "
                                f"1 BESS {b['useful_self_kwh']/1000:.1f} MWh; "
                                f"2 BESS {c['useful_self_kwh']/1000:.1f} MWh of load served")
        win=tk.Toplevel(self.root)
        win.title(f'{self.project_name} — PV / 1 / 2 BESS')
        win.geometry('1000x590')
        pages=ttk.Notebook(win);pages.pack(fill=tk.BOTH,expand=True)
        annual_page=ttk.Frame(pages);monthly_page=ttk.Frame(pages);notes_page=ttk.Frame(pages)
        for page,label in [(annual_page,'Imported period'),(monthly_page,'Monthly'),(notes_page,'Assumptions')]:pages.add(page,text=label)
        summary=ttk.Treeview(annual_page,columns=('metric','without','one','two'),show='headings',height=11)
        for key,title,width in [('metric','Metric',320),('without','PV only',245),
                                ('one','1 BESS 522 kWh',245),('two','2 BESS 522 kWh',245)]:
            summary.heading(key,text=title);summary.column(key,width=width)
        metrics=[('PV production kWh',a['pv_kwh'],b['pv_kwh'],c['pv_kwh']),
                 ('Consumption kWh',a['load_kwh'],b['load_kwh'],c['load_kwh']),
                 ('Direct PV to load kWh',a['self_kwh'],b['direct_kwh'],c['direct_kwh']),
                 ('PV charged into BESS (AC) kWh',None,b['charge_ac_kwh'],c['charge_ac_kwh']),
                 ('BESS delivered to load kWh',None,b['discharge_ac_kwh'],c['discharge_ac_kwh']),
                 ('Load covered by PV kWh',a['self_kwh'],b['useful_self_kwh'],c['useful_self_kwh']),
                 ('Grid purchases kWh',a['grid_kwh'],b['grid_kwh'],c['grid_kwh']),
                 ('Grid export kWh',a['export_kwh'],b['export_kwh'],c['export_kwh']),
                 ('PV curtailed at grid point kWh',a.get('curtailed_kwh',0),b.get('curtailed_kwh',0),c.get('curtailed_kwh',0)),
                 ('Load self-sufficiency %',a['self_sufficiency_pct'],b['self_sufficiency_pct'],c['self_sufficiency_pct']),
                 ('PV kept on site %',a['autoconsumption_pct'],b['autoconsumption_pct'],c['autoconsumption_pct'])]
        for name,*values in metrics:
            summary.insert('',tk.END,values=(name,*(('—' if val is None else f'{val:,.1f}') for val in values)))
        sx=ttk.Scrollbar(annual_page,orient=tk.HORIZONTAL,command=summary.xview);summary.configure(xscrollcommand=sx.set);sx.pack(side=tk.BOTTOM,fill=tk.X)
        sy=ttk.Scrollbar(annual_page,orient=tk.VERTICAL,command=summary.yview);summary.configure(yscrollcommand=sy.set);sy.pack(side=tk.RIGHT,fill=tk.Y)
        summary.pack(fill=tk.BOTH,expand=True,padx=8,pady=8)
        if b:
            ttk.Label(notes_page,text=f"Storage losses: 1 BESS {b['battery_losses_kwh']:,.0f} kWh, "
                      f"2 BESS {c['battery_losses_kwh']:,.0f} kWh. "
                      f"Final SOC: 1 BESS {b['soc_final_pct']:.1f}%, "
                      f"2 BESS {c['soc_final_pct']:.1f}%. "
                      'BESS charges only from surplus PV, without grid charging.',
                      wraplength=1100).pack(anchor='w',padx=12)
        comparison=result.get('comparison',{})
        if comparison:
            ttk.Label(notes_page,text=f"PV relative to clear-sky case: "
                      f"{comparison['weather_to_clear_sky_pct']:.1f}% "
                      f"(base {comparison['clear_sky_annual_kwh']:,.0f} kWh)").pack(anchor='w',padx=12)
        ttk.Label(notes_page,text=f"PV: {result['method']}. Per BESS cabinet: "
                  f"{cfg['nominal_kwh']:,.3f} kWh nominal; only energy capacity doubles with two cabinets. "
                  f"Shared AC limits: charge {cfg['charge_kw']:,.0f} kW, "
                  f"discharge {cfg['discharge_kw']:,.0f} kW. "
                  'PV kept on site includes charging losses; it is different from useful load served.',
                  wraplength=1100).pack(anchor='w',padx=12,pady=8)
        months=ttk.Treeview(monthly_page,columns=('month','load','pv','self0','self1','self2','grid0','grid1','grid2'),show='headings',height=12)
        for key,title,width in [('month','Month',80),('load','Consumption',112),('pv','PV',112),
                                ('self0','Served 0',115),('self1','Served 1',115),('self2','Served 2',115),
                                ('grid0','Grid 0',115),('grid1','Grid 1',115),('grid2','Grid 2',115)]:
            months.heading(key,text=title);months.column(key,width=width)
        for month,r in result['monthly'].items():
            bm=bess.get('monthly',{}).get(month,{})
            cm=two.get('monthly',{}).get(month,{})
            months.insert('',tk.END,values=(month,*(f'{value:.1f}' for value in
                (r['load_kwh'],r['pv_kwh'],r['self_kwh'],bm['useful_self_kwh'],
                 cm['useful_self_kwh'],r['grid_kwh'],bm['grid_kwh'],cm['grid_kwh']))))
        sx=ttk.Scrollbar(monthly_page,orient=tk.HORIZONTAL,command=months.xview);months.configure(xscrollcommand=sx.set);sx.pack(side=tk.BOTTOM,fill=tk.X)
        sy=ttk.Scrollbar(monthly_page,orient=tk.VERTICAL,command=months.yview);months.configure(yscrollcommand=sy.set);sy.pack(side=tk.RIGHT,fill=tk.Y)
        notes_page.bind("<Configure>",lambda e:[w.configure(wraplength=max(200,e.width-30)) for w in notes_page.winfo_children() if isinstance(w,ttk.Label)])
        months.pack(fill=tk.BOTH,expand=True,padx=12,pady=8)

    def _export_self_consumption(self):
        if not self._require_current_energy():return
        if (not getattr(self,'hourly_pv_kwh',None) or not getattr(self,'bess_summary',None)
                or not getattr(self,'two_bess_summary',None)):
            messagebox.showwarning('Missing balance','Calculate the three hourly scenarios first.')
            return
        path=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV','*.csv')],
                                          initialfile=self.project_name+'_hourly_energy.csv')
        if path:
            settings=BatterySettings(**self.bess_summary['battery_settings'])
            data=simulate_three_options(self.hourly_consumption_profile,self.hourly_pv_kwh,settings,self.grid_connection_settings["export_limit_kw"])
            write_comparison_csv(path,data,self.hourly_consumption_profile['imputed_indices'])
            messagebox.showinfo('CSV exported',os.path.basename(path))
