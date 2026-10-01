"""AC energy figures with separate load, PV allocation and SOC axes."""
import numpy as np
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

COLORS={'direct':'#FFB000','battery':'#00A651','grid':'#2563EB',
        'charge':'#00A651','export':'#00BCD4','curtail':'#EF4444','soc':'#9333EA'}
CASE_COLORS=('#2563EB','#F97316','#00A651')
CASES=('PV only','1 BESS','2 BESS')

def monthly_data(summaries,case):
    months=sorted(summaries[0]['monthly'])
    rows=[summaries[case]['monthly'][m] for m in months]
    return months,{key:[r.get(key,r.get('self_kwh',0) if key=='direct_kwh' else 0) for r in rows]
                  for key in ('load_kwh','pv_kwh','direct_kwh','charge_ac_kwh','discharge_ac_kwh','grid_kwh','export_kwh','curtailed_kwh')}

def daily_data(rows,case,export_limit,initial_soc):
    data={k:[] for k in ('load_kwh','pv_kwh','direct_kwh','charge_ac_kwh','discharge_ac_kwh','grid_kwh','export_kwh','curtailed_kwh')}
    for r in rows:
        load,pv,direct=r[1:4]
        if case==0 and len(r)>11:load=r[11];direct=min(load,pv)
        charge,discharge=(r[4],r[5]) if case else (0.,0.)
        grid=load-direct-discharge
        export=r[8] if case else (pv-direct if export_limit is None else min(pv-direct,export_limit))
        for key,value in zip(data,(load,pv,direct,charge,discharge,grid,export,max(0,pv-direct-charge-export))):data[key].append(value)
    data['soc']=[initial_soc]+[r[9] for r in rows] if case else []
    return data

def _style(ax,title,unit):
    ax.set_title(title,loc='left',fontsize=11,pad=32)
    ax.set_ylabel(unit,fontsize=9)
    ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
    ax.spines[['top','right']].set_visible(False);ax.tick_params(labelsize=8)
    ax.yaxis.set_major_locator(MaxNLocator(nbins=4))

def _stacks(ax,x,data,keys,labels,colors,factor):
    bottom=np.zeros(len(x))
    for key,label,color in zip(keys,labels,colors):
        values=np.array(data[key])/factor
        ax.bar(x,values,bottom=bottom,width=.76,color=color,label=label)
        bottom+=values
    ax.legend(loc='lower left',bbox_to_anchor=(0,1.005),ncol=len(keys),frameon=False,fontsize=8,borderaxespad=0)

def energy_figure(data,labels,title,monthly=False,comparison=None):
    fig=Figure(figsize=(11.5,8.2),dpi=100,layout='constrained')
    fig.suptitle(title,fontsize=13,fontweight='bold')
    axes=fig.subplots(3,1)
    x=np.arange(len(labels));factor=1000 if monthly else 1
    unit='Energy (MWh / month)' if monthly else 'Energy (kWh / hour)'
    _style(axes[0],'1. How the load is supplied — bars sum to consumption',unit)
    _stacks(axes[0],x,data,['direct_kwh','discharge_ac_kwh','grid_kwh'],['Direct PV','Battery to load','Grid import'],[COLORS['direct'],COLORS['battery'],COLORS['grid']],factor)
    _style(axes[1],'2. Where PV production goes — bars sum to PV production',unit)
    _stacks(axes[1],x,data,['direct_kwh','charge_ac_kwh','export_kwh','curtailed_kwh'],['Direct PV','Battery charging','Grid export','Curtailed PV'],[COLORS['direct'],COLORS['charge'],COLORS['export'],COLORS['curtail']],factor)
    if monthly:
        _style(axes[2],'3. Grid purchases — compare the same months for all three cases','Grid import (MWh / month)')
        for i,(case,values) in enumerate(zip(CASES,comparison)):
            axes[2].bar(x+(i-1)*.25,np.array(values)/1000,width=.23,label=case,color=CASE_COLORS[i])
        axes[2].legend(loc='lower left',bbox_to_anchor=(0,1.005),ncol=3,frameon=False,fontsize=8,borderaxespad=0)
    elif data['soc']:
        _style(axes[2],'3. Battery state of charge — independent percentage axis','SOC (%)')
        axes[2].plot(np.arange(len(labels)+1),data['soc'],color=COLORS['soc'],linewidth=2,drawstyle='steps-post')
        axes[2].set_ylim(0,100);axes[2].set_yticks([0,25,50,75,100])
        positions=list(range(0,len(labels),2))+[len(labels)]
        axes[2].set_xticks(positions,[labels[j] if j<len(labels) else 'End' for j in positions])
        axes[2].set_xlim(-.5,len(labels)+.5)
        axes[2].set_xlabel('Local time; SOC at the beginning of each interval and at the end of the day',fontsize=9)
    else:
        axes[2].axis('off');axes[2].text(.02,.55,'PV only: no battery charging, discharge or SOC.',transform=axes[2].transAxes,fontsize=11)
    for ax in axes[:2] if not monthly else axes:
        stride=max(1,len(labels)//12)
        ax.set_xticks(x[::stride],labels[::stride],rotation=25 if monthly else 0,ha='right' if monthly else 'center')
        ax.set_xlim(-.6,max(.6,len(labels)-.4))
        ax.set_ylim(bottom=0)
    if monthly:axes[2].set_xlabel('Month (calendar year shown)',fontsize=9)
    return fig
