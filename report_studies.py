"""Annual shadow study and complete spreadsheet plates for engineering reports."""
import csv
import datetime as dt
from zoneinfo import ZoneInfo


def annual_shadow(app, progress=None):
    """Integrate every real hour of the study year using the existing solar model."""
    from shadow_engine import calculate
    settings=getattr(app,'model_settings',{}) or {}
    year=int(settings.get('report_shadow_year',dt.date.today().year))
    if not 1900<=year<=2100:raise ValueError('Report shadow year must be between 1900 and 2100.')
    required=('solar_latitude','solar_longitude','panel_noct_c','panel_temp_coeff_pct','panel_pmax_w')
    missing=[key for key in required if getattr(app,key,None) is None]
    if not app.panels:missing.append('modules')
    obstacles=settings.get('shadow_obstacles',[]) or getattr(app,'pylon_img_pos',None) is not None
    if obstacles and not getattr(app,'px_per_mm',0):missing.append('calibrated image scale')
    if missing:return {'year':year,'missing':missing}
    zone=ZoneInfo(settings.get('timezone','Europe/Rome'))
    start=dt.datetime(year,1,1,tzinfo=zone).astimezone(dt.timezone.utc)
    end=dt.datetime(year+1,1,1,tzinfo=zone).astimezone(dt.timezone.utc)
    intervals=[];time=start
    while time<end:
        nxt=min(time+dt.timedelta(hours=1),end)
        intervals.append((time.astimezone(zone),nxt.astimezone(zone)));time=nxt
    # UTC intervals avoid omitting/duplicating elapsed hours at daylight saving.
    utc_intervals=[(a.astimezone(dt.timezone.utc),b.astimezone(dt.timezone.utc)) for a,b in intervals]
    # shadow_engine expects local clock dates and derives the UTC offset itself.
    # Its midpoint arithmetic is safe for one hour except at DST transitions;
    # use UTC integration and convert only the solar sampling midpoint.
    lost,potential,produced,timeline,log=calculate(app,utc_intervals,progress or (lambda *args:None),timezone=settings.get('timezone','Europe/Rome'))
    rows=[{'coord':coord,'panel':app.panels[coord],'potential_wh':potential[coord],
           'produced_wh':produced[coord],'lost_wh':lost[coord],
           'loss_pct':100*lost[coord]/potential[coord] if potential[coord] else 0.}
          for coord in app.panels]
    months={f'{year}-{m:02d}':{'potential_wh':0.,'produced_wh':0.,'lost_wh':0.} for m in range(1,13)}
    for time,energy,loss in timeline:
        bucket=months[time.strftime('%Y-%m')]
        bucket['produced_wh']+=energy;bucket['lost_wh']+=loss;bucket['potential_wh']+=energy+loss
    return {'year':year,'rows':rows,'months':months,'timeline':timeline,'hours':len(intervals)}


def shadow_blocks(app, assets, progress=None):
    from matplotlib.figure import Figure
    from matplotlib.collections import PolyCollection
    import numpy as np
    result=annual_shadow(app,progress)
    blocks=[('heading','Annual influence of shading')]
    if 'missing' in result:
        return blocks+[('text','Annual shadow study unavailable: enter '+', '.join(result['missing'])+'.')],result
    year=result['year'];rows=result['rows'];months=result['months']
    pot=sum(row['potential_wh'] for row in rows);lost=sum(row['lost_wh'] for row in rows)
    blocks += [('text',f'Full calendar year {year}: {result["hours"]} elapsed hourly intervals, local time zone {getattr(app,"model_settings",{}).get("timezone","Europe/Rome")}. Clear-sky geometric/selected bypass estimate using current geometry, orientations and thermal inputs. This study is separate from the imported-weather BESS comparison.'),
               ('table',['Unshaded potential (kWh)','Produced (kWh)','Lost (kWh)','Annual loss (%)'],[[pot/1000,(pot-lost)/1000,lost/1000,100*lost/pot if pot else 0]]),
               ('table',['Month','Unshaded (kWh)','Produced (kWh)','Lost (kWh)','Loss (%)'],[[month,r['potential_wh']/1000,r['produced_wh']/1000,r['lost_wh']/1000,100*r['lost_wh']/r['potential_wh'] if r['potential_wh'] else 0] for month,r in months.items()])]
    by_coord={tuple(row['coord']):row for row in rows}
    string_rows=[]
    from project_validation import natural
    for sid,coords in sorted(app.strings.items(),key=lambda item:natural(item[0])):
        members=[by_coord[tuple(c)] for c in coords if tuple(c) in by_coord]
        p=sum(r['potential_wh'] for r in members);l=sum(r['lost_wh'] for r in members)
        string_rows.append([sid,len(members),p/1000,(p-l)/1000,l/1000,100*l/p if p else 0])
    blocks.append(('table',['String','Modules','Unshaded (kWh)','Produced (kWh)','Lost (kWh)','Loss (%)'],string_rows))
    polygons=[];values=[]
    for row in rows:
        polygon=app._panel_rect(tuple(row['coord']))
        if polygon:polygons.append(polygon);values.append(row['loss_pct'])
    if polygons:
        fig=Figure(figsize=(9,7),dpi=180);ax=fig.subplots()
        collection=PolyCollection(polygons,array=np.asarray(values),cmap='YlOrRd',edgecolors='#475569',linewidths=.25)
        collection.set_clim(0,max(1,max(values)));ax.add_collection(collection);ax.autoscale_view();ax.invert_yaxis();ax.set_aspect('equal')
        ax.set_title(f'Annual shading loss by module — {year}');ax.set_xlabel('Image x (pixels)');ax.set_ylabel('Image y (pixels)')
        fig.colorbar(collection,ax=ax,label='Annual energy loss (%)');fig.tight_layout();fig.savefig(assets/'annual_shadow_roof.png')
        blocks.append(('image',assets/'annual_shadow_roof.png','Annual spatial heatmap. Each module is coloured by its energy-weighted shading loss; scale and geometry match the layout.'))
    days=(dt.date(year+1,1,1)-dt.date(year,1,1)).days
    energy=np.zeros((24,days));loss=np.zeros_like(energy)
    for time,produced,lost in result['timeline']:
        day=(time.date()-dt.date(year,1,1)).days
        if 0<=day<days:energy[time.hour,day]+=produced+lost;loss[time.hour,day]+=lost
    matrix=np.divide(100*loss,energy,out=np.zeros_like(loss),where=energy>0)
    matrix=np.ma.masked_where(energy==0,matrix)
    fig=Figure(figsize=(10,4),dpi=180);ax=fig.subplots();image=ax.imshow(matrix,origin='lower',aspect='auto',extent=(.5,days+.5,-.5,23.5),cmap='YlOrRd',vmin=0,vmax=max(1,float(matrix.max()) if matrix.count() else 1))
    ax.set_xlabel('Day of year');ax.set_ylabel('Local hour');ax.set_title(f'Shading influence over the year — {year}')
    fig.colorbar(image,ax=ax,label='Energy loss (%)');fig.tight_layout();fig.savefig(assets/'annual_shadow_calendar.png')
    blocks.append(('image',assets/'annual_shadow_calendar.png','Daily/hourly heatmap. Blank cells have no unshaded generation. Repeated daylight-saving hours are combined by energy.'))
    with (assets/'annual_shadow_modules.csv').open('w',newline='',encoding='utf-8-sig') as file:
        writer=csv.writer(file);writer.writerow(['Module','Coordinate','Unshaded kWh','Produced kWh','Lost kWh','Loss %'])
        for row in rows:writer.writerow([row['panel'],row['coord'],row['potential_wh']/1000,row['produced_wh']/1000,row['lost_wh']/1000,row['loss_pct']])
    return blocks,result


def spreadsheet_blocks(app, assets):
    from mixins.spreadsheet_tools import col_letter,cell_id
    sheet=getattr(app,'material_spreadsheet',{}) or {}
    blocks=[('heading','Complete spreadsheet')]
    if not sheet:return blocks+[('text','No spreadsheet supplied.')]
    rows=int(sheet.get('rows',20));cols=int(sheet.get('cols',8));cells=sheet.get('cells',{})
    computed=app._compute_spreadsheet_values()
    def value(row,col):
        raw=str(cells.get(cell_id(row,col),'') or '')
        result=computed.get((row,col),'')
        return raw+'\nValue: '+str(result) if raw.strip().startswith('=') else raw
    blocks.append(('text','All configured rows and columns are reproduced, including blank cells. Formula cells show both the entered formula and its calculated value. #ERR and #CIRC! remain visible for review.'))
    for first in range(0,cols,5):
        last=min(first+5,cols)
        blocks.append(('table',['Row']+[col_letter(c) for c in range(first,last)],[[str(r+1)]+[value(r,c) for c in range(first,last)] for r in range(rows)]))
    for name,evaluate in [('spreadsheet_inputs.csv',False),('spreadsheet_values.csv',True)]:
        with (assets/name).open('w',newline='',encoding='utf-8-sig') as file:
            writer=csv.writer(file);writer.writerow(['Row']+[col_letter(c) for c in range(cols)])
            for row in range(rows):writer.writerow([row+1]+[computed.get((row,c),'') if evaluate else cells.get(cell_id(row,c),'') for c in range(cols)])
    return blocks


def refresh_report_energy(app, progress=None):
    """Recalculate the frozen report snapshot when profiles/inputs are complete."""
    if app._energy_results_current():return
    profile=getattr(app,'hourly_consumption_profile',None)
    if not profile:
        app._report_energy_error='Consumption profile not supplied.';return
    from energy_engine import calculate
    from battery_dispatch import BatterySettings
    import math
    try:
        issues=app._layout_issues()
        if issues:raise ValueError('Layout checks: '+'; '.join(issues[:3]))
        settings=app.energy_input_settings
        numeric={key:float(str(value).replace(',','.')) for key,value in settings['bess'].items()}
        required={'nominal_kwh','charge_kw','discharge_kw','soc_min_pct','soc_max_pct','round_trip_efficiency'}
        if not required.issubset(numeric):raise ValueError('Complete all six BESS inputs in Configuration.')
        factor=float(str(settings['ac_factor']).replace(',','.'))
        if not math.isfinite(factor) or not 0<factor<=1:raise ValueError('Invalid AC conversion factor.')
        BatterySettings(**numeric,initial_soc_pct=numeric['soc_min_pct']).validate()
        payload=calculate(app,profile,factor,numeric,getattr(app,'hourly_weather_profile',None),progress or (lambda *args:None))
        for name,value in payload.items():setattr(app,name,value)
        app.energy_source_signature=app._energy_signature()
    except (ValueError,KeyError,AttributeError,TypeError) as exc:
        app._report_energy_error=str(exc)
