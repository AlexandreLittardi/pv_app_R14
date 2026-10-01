"""Validated, versioned project records and crash-safe local persistence."""
import copy
import datetime as dt
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile
import uuid

SCHEMA_VERSION=2
EXTRA_STATE=('schema_version','project_uid','panel_uids','layout_geometry','connection_review_required',
 'cable_string_params','cable_mass_by_section','cable_inventory','model_settings','equipment_links',
 'shadow_result','shadow_simulation_results','shadow_source_signature')
MODEL_DEFAULTS={'timezone':'Europe/Rome','imputation':'previous_week','shadow_model':'geometric',
 'bypass_groups':3,'module_gap_x_mm':0.,'module_gap_y_mm':0.,'edge_clearance_mm':0.,
 'bess_auxiliary_kw':0.,'bess_annual_degradation_pct':0.,'bess_lifetime_years':15,
 'annual_maintenance_eur':0.,'discount_rate_pct':0.}

def serial(value):
    if isinstance(value,dict):
        return {(','.join(map(str,k)) if isinstance(k,tuple) else str(k)):serial(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,set)):return [serial(v) for v in value]
    if isinstance(value,(dt.datetime,dt.date)):return value.isoformat()
    return value

def fingerprint(value):
    return hashlib.sha256(json.dumps(serial(value),sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def valid_polygon(points):
    if len(points)<3 or len(set(map(tuple,points)))!=len(points):return False
    if any(len(p)!=2 or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in p) for p in points):return False
    def orient(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def hits(a,b,c,d):
        eps=1e-9
        o=[orient(a,b,c),orient(a,b,d),orient(c,d,a),orient(c,d,b)]
        if o[0]*o[1]<-eps and o[2]*o[3]<-eps:return True
        def on(a,b,c):return abs(orient(a,b,c))<eps and min(a[0],b[0])-eps<=c[0]<=max(a[0],b[0])+eps and min(a[1],b[1])-eps<=c[1]<=max(a[1],b[1])+eps
        return on(a,b,c) or on(a,b,d) or on(c,d,a) or on(c,d,b)
    n=len(points)
    for i in range(n):
        for j in range(i+1,n):
            if j==i+1 or (i==0 and j==n-1):continue
            if hits(points[i],points[(i+1)%n],points[j],points[(j+1)%n]):return False
    area=abs(sum(points[i][0]*points[(i+1)%n][1]-points[(i+1)%n][0]*points[i][1] for i in range(n)))
    return area>1e-8

def validate_project(original):
    if not isinstance(original,dict):raise ValueError('Project JSON must be an object.')
    data=copy.deepcopy(original)
    version=data.get('schema_version',1)
    if not isinstance(version,int) or version>SCHEMA_VERSION or version<1:raise ValueError('Unsupported project schema version.')
    def finite(value,path):
        if isinstance(value,float) and not math.isfinite(value):raise ValueError(f'{path}: non-finite number.')
        if isinstance(value,dict):
            for k,v in value.items():finite(v,f'{path}.{k}')
        elif isinstance(value,list):
            for i,v in enumerate(value):finite(v,f'{path}[{i}]')
    finite(data,'project')
    object_fields=('panels','strings','panel_blocks','panel_orientations','blocks','inverter_positions',
     'string_mppt_assignment','material_categories','material_spreadsheet','diagram_nodes','diagram_electrical_specs',
     'cable_calc_params','cable_string_params','cable_mass_by_section','routing_settings','economic_settings',
     'grid_connection_settings','electrical_design','electrical_checks','model_settings')
    for key in object_fields:
        if key in data and not isinstance(data[key],dict):raise ValueError(f'{key}: expected an object.')
    for key in ('roof_zones','roof_polygons','cable_paths','measures','diagram_links','manual_strings'):
        if key in data and not isinstance(data[key],list):raise ValueError(f'{key}: expected a list.')
    for key in ('panel_width_mm','panel_height_mm'):
        v=float(data.get(key,1000 if key=='panel_width_mm' else 1700))
        if not math.isfinite(v) or v<=0:raise ValueError(f'{key}: positive finite dimensions required.')
    for key in ('px_per_mm','scale_length_mm'):
        if float(data.get(key,0))<0:raise ValueError(f'{key}: must be nonnegative.')
    numeric_fields=('panel_tilt_deg','panel_azimuth_deg','pylon_height_mm','pylon_width_mm','pylon_opacity',
        'north_offset_deg','solar_latitude','solar_longitude','solar_utc_offset','solar_day','solar_month','solar_hour',
        'panel_pmax_w','panel_efficiency_pct','panel_temp_coeff_pct','panel_noct_c','px_per_mm','scale_length_mm')
    for key in numeric_fields:
        if key in data:
            value=float(data[key])
            if not math.isfinite(value):raise ValueError(f'{key}: finite value required.')
            data[key]=int(value) if key in ('solar_day','solar_month') else value
    def point(value):return isinstance(value,(list,tuple)) and len(value)==2 and all(isinstance(x,(int,float)) and math.isfinite(x) for x in value)
    for key in ('scale_p1','scale_p2','pylon_img_pos','pylon_ref_img_pos'):
        if data.get(key) is not None and not point(data[key]):raise ValueError(f'{key}: invalid point.')
    for block,record in data.get('blocks',{}).items():
        if not isinstance(record,dict):raise ValueError(f'{block}: invalid inverter block.')
        for key in ('mppt_count','max_strings_per_mppt'):
            if key in record and (not isinstance(record[key],int) or not 1<=record[key]<=1000):raise ValueError(f'{block}: invalid {key}.')
    for orientation in data.get('panel_orientations',{}).values():
        if not isinstance(orientation,dict) or any(not math.isfinite(float(v)) for v in orientation.values()):raise ValueError('Invalid module orientation.')
    for route in data.get('cable_paths',[]):
        if not isinstance(route,dict) or any(not point(p) for p in route.get('points',[])):raise ValueError('Invalid cable path.')
    for measure in data.get('measures',[]):
        pts=[measure.get(k) for k in ('p1','p2','label')] if isinstance(measure,dict) else measure
        if any(not point(p) for p in pts):raise ValueError('Invalid dimension points.')
    for key in ('hourly_consumption_profile',):
        profile=data.get(key)
        if profile:
            if not isinstance(profile,dict) or not isinstance(profile.get('hourly_kwh'),list):raise ValueError('Invalid consumption profile.')
            if any(not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 for v in profile['hourly_kwh']):raise ValueError('Invalid consumption kWh.')
            from self_consumption import timestamps
            timestamps(profile)
    coords=set(data.get('panels',{}))
    for coord in coords|set(data.get('panel_orientations',{}))|set(data.get('panel_blocks',{})):
        if not re.fullmatch(r'\d+,\d+',coord):raise ValueError(f'Invalid panel coordinate: {coord}')
    for coord,num in data.get('panels',{}).items():
        if not isinstance(num,int) or isinstance(num,bool) or num<=0:raise ValueError(f'{coord}: invalid module ID.')
    if len(set(data.get('panels',{}).values()))!=len(coords):raise ValueError('Duplicate module IDs.')
    for sid,members in data.get('strings',{}).items():
        if not isinstance(members,list) or any(not isinstance(x,str) or not re.fullmatch(r'\d+,\d+',x) for x in members):raise ValueError(f'{sid}: invalid panel list.')
    for sid,a in data.get('string_mppt_assignment',{}).items():
        if not isinstance(a,dict) or not isinstance(a.get('mppt'),int):raise ValueError(f'{sid}: invalid MPPT assignment.')
    for z in data.get('roof_zones',[]):
        for key in ('x1','x2','y1','y2'):
            if not isinstance(z,dict) or not math.isfinite(float(z.get(key,float('nan')))):raise ValueError('Invalid zone dimensions.')
        for key in ('x1','x2','y1','y2'):z[key]=float(z[key])
        if z['x1']==z['x2'] or z['y1']==z['y2']:raise ValueError('A zone must have positive area.')
        for key in ('angle_deg','installation_height_m','z_mm'):
            if z.get(key) is not None and not math.isfinite(float(z[key])):raise ValueError(f'Invalid zone {key}.')
    for p in data.get('roof_polygons',[]):
        if not isinstance(p,dict) or not valid_polygon(p.get('points',[])):raise ValueError('Routing area must be a simple polygon with nonzero area.')
    for key in ('hourly_consumption_profile','hourly_weather_profile'):
        if data.get(key) is not None and not isinstance(data[key],dict):raise ValueError(f'{key}: expected profile object.')
    for cat in data.get('material_categories',{}).values():
        if not isinstance(cat,dict) or not isinstance(cat.get('rows',[]),list) or any(not isinstance(row,dict) for row in cat.get('rows',[])):raise ValueError('Invalid equipment sheet.')
    if 'solar_day' in data and 'solar_month' in data:dt.date(2024,data['solar_month'],data['solar_day'])
    if not -90<=data.get('solar_latitude',0)<=90 or not -180<=data.get('solar_longitude',0)<=180:raise ValueError('Invalid site latitude / longitude.')
    data['schema_version']=SCHEMA_VERSION
    data.setdefault('project_uid',uuid.uuid4().hex)
    data['model_settings']={**MODEL_DEFAULTS,**data.get('model_settings',{})}
    from zoneinfo import ZoneInfo
    ZoneInfo(data['model_settings']['timezone'])
    for key in ('module_gap_x_mm','module_gap_y_mm','edge_clearance_mm','bess_auxiliary_kw','bess_annual_degradation_pct','annual_maintenance_eur','discount_rate_pct'):
        v=float(data['model_settings'][key])
        if not math.isfinite(v) or v<0:raise ValueError(f'{key}: finite nonnegative value required.')
    if data['model_settings']['bess_annual_degradation_pct']>=100:raise ValueError('Degradation must be less than 100%.')
    if data['model_settings']['shadow_model'] not in ('geometric','bypass_estimate'):raise ValueError('Unknown shadow model.')
    settings=data['model_settings']
    for key in ('bypass_groups','bess_lifetime_years'):
        value=settings[key]
        if int(value)!=value or not 1<=value<=100:raise ValueError(f'{key}: whole number between 1 and 100 required.')
    if settings['imputation'] not in ('previous_week','reject','zero'):raise ValueError('Unknown imputation method.')
    for poly in settings.get('layout_exclusions',[]):
        if not valid_polygon(poly):raise ValueError('Invalid exclusion polygon.')
    for obstacle in settings.get('shadow_obstacles',[]):
        if not isinstance(obstacle,dict) or not valid_polygon(obstacle.get('footprint_px',[])):raise ValueError('Invalid obstacle footprint.')
        if not math.isfinite(obstacle.get('height_mm',float('nan'))) or obstacle['height_mm']<=0:raise ValueError('Invalid obstacle height.')
        if not 0<=obstacle.get('opacity',1)<=1:raise ValueError('Obstacle opacity must be between zero and one.')
    if not isinstance(data.get('cable_inventory',[]),list):raise ValueError('Cable inventory must be a list.')
    for cable in data.get('cable_inventory',[]):
        if not isinstance(cable,dict):raise ValueError('Invalid inventory entry.')
        for key in ('length_m','linear_mass_kg_m','quantity'):
            value=cable.get(key,1 if key=='quantity' else None)
            if value is not None and (not isinstance(value,(int,float)) or not math.isfinite(value) or value<0):raise ValueError(f'Cable inventory: invalid {key}.')
    for sid,overrides in data.get('cable_string_params',{}).items():
        if not isinstance(overrides,dict):raise ValueError(f'{sid}: expected string parameters.')
        for key,value in overrides.items():
            if not isinstance(value,(int,float)) or not math.isfinite(value) or value<0:raise ValueError(f'{sid}: invalid {key}.')
            if key=='module_row' and int(value)!=value:raise ValueError('Module equipment row must be an integer.')
    for block,placement in data.get('inverter_positions',{}).items():
        for key in ('x','y','terminal_height_m'):
            if key in placement and (not isinstance(placement[key],(int,float)) or not math.isfinite(placement[key]) or key=='terminal_height_m' and placement[key]<0):raise ValueError(f'{block}: invalid {key}.')
    links=data.setdefault('equipment_links',{})
    rows=data.get('material_categories',{}).get('inverters',{}).get('rows',[])
    for block,placement in data.get('inverter_positions',{}).items():
        if block not in links:
            saved=placement.get('material_row',{})
            matching=[i for i,row in enumerate(rows) if saved and row.get('Modèle')==saved.get('Modèle') and row.get('Marque')==saved.get('Marque')]
            if len(matching)==1:links[block]=matching[0]
    for block,index in links.items():
        if not isinstance(index,int) or not 0<=index<len(rows):raise ValueError(f'{block}: equipment link points to a missing row.')
    from project_validation import normalize_project
    data=normalize_project(data)
    uids=data.get('panel_uids',{})
    data['panel_uids']={c:uids.get(c,uuid.uuid4().hex) for c in data.get('panels',{})}
    return data

def atomic_bytes(path,payload,backup=False):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix='.'+path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:stream.write(payload);stream.flush();os.fsync(stream.fileno())
        if backup and path.exists():
            folder=path.parent/'.backups';folder.mkdir(exist_ok=True)
            dest=folder/(path.name+'.'+dt.datetime.now().strftime('%Y%m%dT%H%M%S%f')+'.bak')
            shutil.copy2(path,dest)
            for old in sorted(folder.glob(path.name+'.*.bak'))[:-10]:old.unlink()
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)

def write_project(path,data,image=None,recovery=False):
    data=validate_project(serial(data));path=Path(path)
    if image is not None:
        output=io.BytesIO();image.save(output,format='PNG');blob=output.getvalue()
        name=path.stem+'_roof_'+hashlib.sha256(blob).hexdigest()[:12]+'.png'
        dest=path.parent/name
        if not dest.exists():atomic_bytes(dest,blob)
        data['roof_image_path']=name
    payload=json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False).encode('utf-8')
    atomic_bytes(path,payload,backup=not recovery)
    return data
