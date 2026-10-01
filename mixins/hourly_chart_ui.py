"""Readable Matplotlib day and month views using identical energy-flow colours."""
import tkinter as tk
from tkinter import ttk, messagebox
from battery_dispatch import BatterySettings, simulate_three_options
from self_consumption import timestamps
from bess_charts import CASES,daily_data,monthly_data,energy_figure

class HourlyChartMixin:
    def _open_annual_chart(self):
        if not self._require_current_energy():return
        summaries=[self.self_consumption_summary,self.bess_summary,self.two_bess_summary]
        self._bess_chart_window('Monthly energy balance',summaries=summaries)

    def _open_hourly_chart(self):
        if not self._require_current_energy():return
        profile=self.hourly_consumption_profile
        if not profile or not self.hourly_pv_kwh or not self.bess_summary:
            messagebox.showwarning('Missing profile','Calculate all three options first.');return
        cfg=BatterySettings(**self.bess_summary['battery_settings'])
        comparison=simulate_three_options(profile,self.hourly_pv_kwh,cfg,self.grid_connection_settings['export_limit_kw'])
        dates=list(dict.fromkeys(s.date().isoformat() for s in timestamps(profile)))
        self._bess_chart_window('Daily energy balance',comparison=comparison,dates=dates,cfg=cfg)

    def _bess_chart_window(self,title,summaries=None,comparison=None,dates=None,cfg=None):
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        win=tk.Toplevel(self.root);win.title(title)
        controls=ttk.Frame(win,padding=8);controls.pack(fill='x')
        ttk.Label(controls,text='Configuration:').pack(side='left')
        case=tk.StringVar(value=CASES[1]);picker=ttk.Combobox(controls,textvariable=case,values=CASES,width=12,state='readonly');picker.pack(side='left',padx=6)
        day=tk.StringVar(value=dates[0] if dates else '')
        if dates:
            ttk.Label(controls,text='Day:').pack(side='left',padx=(10,0))
            selector=ttk.Combobox(controls,textvariable=day,values=dates,width=12,state='readonly');selector.pack(side='left',padx=5)
        totals=ttk.Label(win,padding=(10,2),wraplength=1000);totals.pack(fill='x')
        chart=ttk.Frame(win);chart.pack(fill='both',expand=True)
        detail=ttk.Label(win,text='Click a bar for the exact values.',padding=8,wraplength=1000);detail.pack(fill='x')
        state={}
        def draw(*_):
            if not self._energy_results_current():
                for child in chart.winfo_children():child.destroy()
                detail.configure(text='Project inputs changed. Close this window and calculate again.');return
            i=CASES.index(case.get())
            if dates:
                rows=comparison['two_bess' if i==2 else 'one_bess']['rows']
                stamps=timestamps(self.hourly_consumption_profile)
                indices=[j for j,stamp in enumerate(stamps) if stamp.date().isoformat()==day.get()]
                start=indices[0]
                initial=rows[start-1][9] if start else cfg.initial_soc_pct
                data=daily_data([rows[j] for j in indices],i,self.grid_connection_settings['export_limit_kw'],initial)
                labels=[stamps[j].strftime('%H:%M %z') for j in indices];name=f'{day.get()} | {case.get()}'
                imports=None
            else:
                labels,data=monthly_data(summaries,i);name=f'Monthly balances | {case.get()}'
                imports=[[s['monthly'][m]['grid_kwh'] for m in labels] for s in summaries]
            state.update(data=data,labels=labels)
            for child in chart.winfo_children():child.destroy()
            fig=energy_figure(data,labels,name,monthly=not dates,comparison=imports)
            canvas=FigureCanvasTkAgg(fig,master=chart);state['canvas']=canvas
            canvas.get_tk_widget().pack(fill='both',expand=True);canvas.draw()
            totals.configure(text=f"Selected {'day' if dates else 'period'}: Load {sum(data['load_kwh']):,.0f} kWh | PV {sum(data['pv_kwh']):,.0f} kWh | Grid import {sum(data['grid_kwh']):,.0f} kWh | Export {sum(data['export_kwh']):,.0f} kWh")
            detail.configure(text='Click a bar for exact values. Battery charging and useful discharge are shown separately; SOC is never overlaid on energy.')
            def clicked(event):
                if event.inaxes not in fig.axes or event.xdata is None:return
                index=round(event.xdata)
                if not 0<=index<len(labels):return
                d=state['data'];label=labels[index]
                text=f"{label}: load {d['load_kwh'][index]:.1f}; PV {d['pv_kwh'][index]:.1f}; direct PV {d['direct_kwh'][index]:.1f}; battery charge {d['charge_ac_kwh'][index]:.1f}; discharge {d['discharge_ac_kwh'][index]:.1f}; grid import {d['grid_kwh'][index]:.1f}; export {d['export_kwh'][index]:.1f}; curtailed {d['curtailed_kwh'][index]:.1f} kWh."
                if dates and d['soc']:text+=f" SOC {d['soc'][index]:.1f}% → {d['soc'][index+1]:.1f}%."
                detail.configure(text=text)
            canvas.mpl_connect('button_press_event',clicked)
        picker.bind('<<ComboboxSelected>>',draw)
        if dates:
            selector.bind('<<ComboboxSelected>>',draw)
            def move(delta):
                day.set(dates[max(0,min(len(dates)-1,dates.index(day.get())+delta))]);draw()
            ttk.Button(controls,text='Previous day',command=lambda:move(-1)).pack(side='left',padx=4)
            ttk.Button(controls,text='Next day',command=lambda:move(1)).pack(side='left',padx=4)
        win.bind('<Configure>',lambda e:[w.configure(wraplength=max(250,win.winfo_width()-30)) for w in (totals,detail)] if e.widget is win else None,add='+')
        self._fit_dialog(win,1200,920);win.after_idle(draw)
