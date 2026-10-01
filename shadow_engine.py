"""Cancellable geometric shading integration; no Tk access from the worker."""
import datetime as dt
from zoneinfo import ZoneInfo

def calculate(app,intervals,report,timezone=None):
    coords=list(app.panels);lost={c:0. for c in coords};potential=lost.copy();produced=lost.copy()
    timeline=[];log=[];zone=ZoneInfo(timezone or app.model_settings['timezone'])
    has_obstacles=bool(app.model_settings.get('shadow_obstacles')) or getattr(app,'pylon_img_pos',None) is not None
    sampler=make_shadow_sampler(app) if has_obstacles else None
    for idx,(start,end) in enumerate(intervals,1):
        report(idx-1,len(intervals))
        mid=start+(end-start)/2
        if timezone is not None:mid=mid.astimezone(zone)
        offset=(mid.utcoffset() if mid.tzinfo is not None else mid.replace(tzinfo=zone).utcoffset()).total_seconds()/3600
        elev,az=app._compute_solar_position(app.solar_latitude,app.solar_longitude,mid.day,mid.month,
            mid.hour+mid.minute/60+mid.second/3600,offset,year=mid.year)
        percentages=(sampler(elev,az) if sampler else app._calculate_shadow_percentages(elev,az)[0]) if elev>.1 and has_obstacles else {}
        p_sum=l_sum=0.;irradiances={};energies={}
        for c in coords:
            orientation=getattr(app,'panel_orientations',{}).get(c,{})
            key=(orientation.get('tilt_deg',getattr(app,'panel_tilt_deg',None)),orientation.get('azimuth_deg',getattr(app,'panel_azimuth_deg',None)))
            if not hasattr(app,'panel_orientations'):key=c
            if key not in irradiances:irradiances[key]=app._get_clear_sky_poa_irradiance(elev,az,c) if elev>.1 else 0.
            irr=irradiances[key];shade=percentages.get(c,0)/100
            if (irr,shade) not in energies:energies[irr,shade]=app._panel_energy_step(irr,shade,(end-start).total_seconds()/3600)
            ep,es,el=energies[irr,shade]
            potential[c]+=ep;produced[c]+=es;lost[c]+=el;p_sum+=es;l_sum+=el
        timeline.append((mid,p_sum,l_sum));log.append((start,end,p_sum,l_sum))
    report(len(intervals),len(intervals))
    return lost,potential,produced,timeline,log


def make_shadow_sampler(app):
    """Cache static module geometry and reject disjoint shadow bounds exactly."""
    required=('_compute_shadow_geometry','_panel_rect','_polygon_clip','_polygon_area','_recalculate_zone_grids')
    if not all(hasattr(app,key) for key in required):return None
    from shading_models import optical_area
    app._recalculate_zone_grids()
    def bounds(poly):return (min(x for x,y in poly),min(y for x,y in poly),max(x for x,y in poly),max(y for x,y in poly))
    panels=[]
    for coord in app.panels:
        poly=app._panel_rect(coord)
        if not poly:continue
        zone=next((i for i,z in enumerate(app.roof_zones) if z['row_base']<=coord[0]<z['row_base']+z['rows']),None)
        panels.append((coord,poly,bounds(poly),app._polygon_area(poly),zone))
    def sample(elevation,azimuth):
        shadows={}
        for geometry in app._compute_shadow_geometry(elevation,azimuth):
            polygon=geometry['polygon']
            if polygon:shadows.setdefault(geometry['zone_idx'],[]).append((polygon,bounds(polygon),geometry.get('opacity',1)))
        result={}
        for coord,poly,box,area,zone in panels:
            layers=[]
            for polygon,shadow_box,opacity in shadows.get(zone,[]):
                if box[2]<=shadow_box[0] or shadow_box[2]<=box[0] or box[3]<=shadow_box[1] or shadow_box[3]<=box[1]:continue
                clipped=app._polygon_clip(polygon,poly)
                if len(clipped)>=3:layers.append((clipped,opacity))
            if layers and area>1e-12:
                percent=min(100,100*optical_area(layers)/area)
                if percent>0:result[coord]=percent
        return result
    return sample
