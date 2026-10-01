"""Rebuildable site wiring schedule and editable, documented single-line SVG.

No device rating or cable ampacity is inferred from the layout. An unfilled
field remains conspicuously open on the drawing rather than being approved.
"""
import hashlib
import json
import math
from collections import defaultdict
from html import escape
from pathlib import Path

from project_validation import natural, number
from single_line_516 import route_is_current

HYBRID_MODEL = 'DEYE SUN-125K-SG02HP3-EU-GM10'
BESS_MODEL = 'DEYE MC-L522-BC-2/3'


def source_fingerprint(project):
    """Engineering design must be checked again after connections or geometry change."""
    fields=('panels','strings','string_mppt_assignment','blocks','inverter_positions',
            'panel_pmax_w','material_categories','roof_zones','cable_paths','roof_polygons',
            'px_per_mm','panel_width_mm','panel_height_mm','routing_settings',
            'cable_calc_params','cable_string_params','cable_mass_by_section','model_settings','equipment_links',
            'electrical_route_plan_3d','grid_connection_settings')
    relevant={key:project.get(key) for key in fields}
    return hashlib.sha256(json.dumps(relevant,ensure_ascii=False,sort_keys=True,
                                     default=str).encode('utf-8')).hexdigest()


def default_design():
    return {
        'bess_count':0,
        'ac_voltage_v':'', 'power_factor':'',
        'dc':{}, 'ac':{},
        'battery':{
            '1':{'cluster_1_to':'INV1','cluster_2_to':'INV2'},
            '2':{'cluster_1_to':'','cluster_2_to':''},
        },
        'grid':{'main_breaker_a':'','meter_id':'','interface_protection':'',
                'export_control':'','transformer_connection':'','emergency_shutdown':''},
        'source_fingerprint':'',
    }


def normalise_design(saved):
    design=default_design()
    if not isinstance(saved,dict):return design
    for key in ('bess_count','ac_voltage_v','power_factor','source_fingerprint'):
        if key in saved:design[key]=saved[key]
    for key in ('dc','ac','battery','grid'):
        if isinstance(saved.get(key),dict):
            if key in ('dc','ac'):
                design[key]={str(k):dict(v) for k,v in saved[key].items() if isinstance(v,dict)}
            else:
                design[key].update({str(k):dict(v) if isinstance(v,dict) else v for k,v in saved[key].items()})
    try:design['bess_count']=int(design['bess_count'])
    except (ValueError,TypeError):design['bess_count']=0
    if design['bess_count'] not in (0,1,2):design['bess_count']=0
    return design


def _rating(value,label,issues,required=True):
    if value in ('',None):
        if required:issues.append(f'{label}: missing.')
        return None
    val=number(value)
    if val is None or val<=0:
        issues.append(f'{label}: a positive value is required.')
        return None
    return val


def build_detailed_model(project,saved_design):
    design=normalise_design(saved_design)
    issues=[]
    strings=project.get('strings') or {}
    assignment=project.get('string_mppt_assignment') or {}
    blocks=project.get('blocks') or {}
    panels=project.get('panels') or {}
    if not strings or not blocks:raise ValueError('Create strings and inverter blocks before generating the electrical drawing.')
    if set(strings)!=set(assignment):issues.append('Strings lack MPPT assignments or orphan assignments remain.')
    if design.get('source_fingerprint') and design['source_fingerprint']!=source_fingerprint(project):
        issues.append('Layout or electrical data changed after the settings were saved: review the design again.')
    elif not design.get('source_fingerprint'):
        issues.append('Wiring settings are not saved or rechecked against this project.')

    module=(project.get('material_categories',{}).get('modules',{}).get('rows') or [{}])[0]
    pmax=_rating(project.get('panel_pmax_w'),'Module STC power',issues)
    voc=_rating(module.get('Voc (V)'),'Module STC Voc',issues,False)
    vmp=_rating(module.get('Vmp (V)'),'Module STC Vmp',issues,False)
    isc=_rating(module.get('Isc (A)'),'Module STC Isc',issues,False)
    imp=_rating(module.get('Imp (A)'),'Module STC Imp',issues,False)
    if not all((voc,vmp,isc,imp)):
        issues.append('Confirm module STC Voc/Vmp/Isc/Imp against the final datasheet.')
    cold=project.get('electrical_checks') or {}
    if any(number(cold.get(key)) is None for key in ('voc_temp_coeff_pct','min_temperature_c','inverter_max_dc_v','mppt_max_current_a','mppt_max_isc_a')):
        issues.append('Cold Voc / MPPT current check incomplete: enter limits and design temperature in Electrical data.')

    per_inv=defaultdict(list);per_mppt=defaultdict(list);lines=[];used=[]
    for sid in sorted(strings,key=natural):
        members=strings[sid]
        used.extend(members)
        alloc=assignment.get(sid,{})
        inv=alloc.get('block');mppt=alloc.get('mppt')
        max_mppt=number(blocks.get(inv,{}).get('mppt_count'))
        if inv not in blocks or not isinstance(mppt,int) or not max_mppt or not 1<=mppt<=max_mppt:
            issues.append(f'{sid}: invalid inverter / MPPT assignment.');inv=inv or 'UNASSIGNED';mppt=None
        slot=(inv,mppt)
        per_mppt[slot].append(sid)
        per_inv[inv].append(sid)
        protection=design['dc'].get(sid,{})
        overrides=project.get('cable_string_params',{}).get(sid,{})
        section=_rating(overrides.get('section_mm2',protection.get('section_mm2')),f'{sid} DC section (mm²)',issues)
        fuse=_rating(protection.get('fuse_a'),f'{sid} DC fuse (A)',issues)
        isolator=_rating(protection.get('isolator_a'),f'{sid} DC isolator (A)',issues)
        if not protection.get('spd'):issues.append(f'{sid} DC surge protection: specify type and location.')
        plan=project.get('electrical_route_plan_3d') or {}
        route=(plan.get('routes') or {}).get(sid) if route_is_current(project,sid) else None
        if route and (route.get('inverter')!=inv or route.get('mppt')!=mppt or route.get('modules')!=len(members)):
            route=None
        if not route:issues.append(f'{sid}: A+B route is absent or stale.')
        from engineering_inputs import operating_values
        operating=operating_values(project,sid)
        from engineering_inputs import module_for_string
        module=module_for_string(project,sid)
        voc=number(module.get('Voc (V)'));vmp=number(module.get('Vmp (V)'))
        pmax=number(module.get('Pmax (W)'))
        if not pmax:issues.append(f'{sid}: selected module power is missing.')
        if route and section and operating['current_a'] and operating['voltage_v']:
            rho=number(project.get('cable_calc_params',{}).get('resistivity'))
            voltage_drop=100*operating['current_a']*rho*route['loop_length_m']/section/operating['voltage_v'] if rho else None
        else:voltage_drop=None
        lines.append({'id':sid,'inv':inv,'mppt':mppt,'count':len(members),
                      'panel_numbers':[panels.get(k,'?') for k in members],
                      'kwp':len(members)*(pmax or 0)/1000,
                      'voc_stc_v':len(members)*voc if voc else None,
                      'vmp_stc_v':len(members)*vmp if vmp else None,
                      'imp_a':operating['current_a'],'isc_a':operating['isc_a'],'route':route,'section_mm2':section,
                      'fuse_a':fuse,'isolator_a':isolator,'spd':protection.get('spd',''),
                      'drop_pct':voltage_drop})

    if len(used)!=len(panels) or len(set(used))!=len(used):
        issues.append('Module assignment to strings is incomplete or duplicated.')
    for (inv,mppt),sids in per_mppt.items():
        if mppt is None:continue
        max_inputs=number(blocks[inv].get('max_strings_per_mppt')) or 2
        if len(sids)>max_inputs:issues.append(f'{inv} MPPT {mppt}: {len(sids)} strings exceed {int(max_inputs)} declared inputs.')
        if len({len(strings[s]) for s in sids})>1:issues.append(f'{inv} MPPT {mppt}: parallel strings have unequal lengths.')
        from engineering_inputs import inverter_row
        current_max=number(inverter_row(project,inv).get('MPPT Imp max (A)',cold.get('mppt_max_current_a')))
        current_sum=sum(x['imp_a'] or 0 for x in lines if x['id'] in sids)
        if current_max and current_sum>current_max:issues.append(f'{inv} MPPT {mppt}: summed Imp exceeds the entered MPPT limit.')

    from electrical_checks import check
    issues.extend(check(project))
    ac=[]
    ac_voltage=_rating(design.get('ac_voltage_v'),'AC line-to-line voltage (V)',issues)
    pf=_rating(design.get('power_factor'),'AC power factor',issues)
    if pf and pf>1:issues.append('AC power factor must be ≤ 1.');pf=None
    for inv in sorted(blocks,key=natural):
        info=design['ac'].get(inv,{})
        placement=project.get('inverter_positions',{}).get(inv,{})
        material=__import__('engineering_inputs').inverter_row(project,inv)
        kva=number(material.get('Puissance (kVA)'))
        if not kva:issues.append(f'{inv}: confirm nominal apparent power.')
        model=material.get('Modèle') or 'MODEL NOT SUPPLIED'
        if inv not in project.get('inverter_positions',{}):issues.append(f'{inv}: inverter has no planned position.')
        length=_rating(info.get('length_m'),f'{inv} AC feeder length (m)',issues)
        section=_rating(info.get('section_mm2'),f'{inv} AC section (mm²)',issues)
        breaker=_rating(info.get('breaker_a'),f'{inv} AC breaker (A)',issues)
        if not info.get('spd'):issues.append(f'{inv}: define AC surge protection type and location.')
        if not info.get('isolator'):issues.append(f'{inv}: define AC isolator.')
        nominal_a=(kva*1000/(math.sqrt(3)*ac_voltage) if kva and ac_voltage else None)
        if breaker and nominal_a and breaker<nominal_a:
            issues.append(f'{inv}: breaker rating {breaker:g} A is below nominal apparent current {nominal_a:.1f} A.')
        ac.append({'id':inv,'model':model,'kva':kva,'strings':per_inv.get(inv,[]),
                   'dc_kwp':sum(x['kwp'] for x in lines if x['inv']==inv),
                   'protection':info,'length_m':length,'section_mm2':section,
                   'breaker_a':breaker,'nominal_a':nominal_a})

    count=design['bess_count'];battery=[];occupied=set()
    dispatch=project.get('bess_summary',{}).get('battery_settings',{})
    charge_kw=number(dispatch.get('charge_kw')) or 250
    discharge_kw=number(dispatch.get('discharge_kw')) or 150
    for i in range(1,count+1):
        cfg=design['battery'].get(str(i),{})
        links=[]
        for cluster in ('cluster_1_to','cluster_2_to'):
            to=cfg.get(cluster,'')
            if to and to not in blocks:issues.append(f'BESS {i} {cluster}: inverter {to} does not exist.')
            if i==1 and not to:issues.append(f'BESS 1 {cluster}: assign a BAT port.')
            if i==2 and not to:issues.append(f'BESS 2 {cluster}: obtain the supplementary DEYE connection diagram.')
            if to in occupied:issues.append(f'{to} BAT port is proposed for multiple clusters or cabinets: manufacturer approval required.')
            if to=='INV3':issues.append('INV3 is PV-only: connecting a battery would change the selected topology.')
            if to:occupied.add(to)
            links.append(to)
        for field,title in [('fuse_a','fuse'),('isolator_a','isolator'),
                            ('section_mm2','cable section'),('length_m','cable run')]:
            _rating(cfg.get(field),f'BESS {i} {title}',issues)
        if not cfg.get('spd'):issues.append(f'BESS {i}: specify DC surge protection.')
        battery.append({'id':i,'config':cfg,'links':links})
    if count==2:issues.append('The supplied DEYE drawing does not confirm two MC-L522 cabinets; obtain the manufacturer extension and parallel BAT-port drawing.')

    grid=design['grid']
    for key,label in [('main_breaker_a','main breaker'),('meter_id','meter'),
                      ('interface_protection','interface protection'),('export_control','export limiter control'),
                      ('transformer_connection','two-transformer topology'),
                      ('emergency_shutdown','emergency shutdown circuit')]:
        if key=='main_breaker_a':_rating(grid.get(key),label,issues)
        elif not grid.get(key):issues.append(f'Grid: document {label}.')
    grid_settings=project.get('grid_connection_settings') or {}
    export_kw=number(grid_settings.get('export_limit_kw'))
    contract_kw=number(grid_settings.get('existing_contract_kw'))
    if export_kw is None:issues.append('Requested export capacity is missing.')
    if grid_settings.get('export_limit_status') != 'approved':
        issues.append('Grid operator approval for the requested export capacity is not documented.')
    issues.append('Verify cable sections and protections through fault, installation, selectivity and datasheet studies; this drawing does not certify CEI 0-16 compliance.')
    return {'name':project.get('project_name','PV project'), 'modules':len(panels),
            'power_kwp':sum(x['kwp'] for x in lines),'inverters':ac,'lines':lines,
            'battery':battery,'battery_count':count,'grid':grid,'export_kw':export_kw,
            'contract_kw':contract_kw,'export_status':grid_settings.get('export_limit_status',''),
            'ac_voltage_v':ac_voltage,'power_factor':pf,'issues':issues,'design':design,
            'charge_kw':charge_kw,'discharge_kw':discharge_kw}


def write_detailed_svg(model,path):
    """Produce a readable vector drawing and wiring schedule with per-field open items."""
    lines=model['lines'];issues=model['issues']
    width=1700;height=1290+len(lines)*32+len(issues)*22
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">']
    def rect(x,y,w,h,fill='#fff',stroke='#c5d1db',r=7):
        out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}" stroke="{stroke}"/>')
    def text(x,y,value,size=15,color='#18334a',weight='normal'):
        out.append(f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-weight="{weight}" font-family="DejaVu Sans,Arial,sans-serif">{escape(str(value))}</text>')
    def wire(x1,y1,x2,y2,color='#274964',dash=False):
        out.append(f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{color}" stroke-width="3"'+(' stroke-dasharray="7 5"' if dash else '')+'/>')
    def field(value,unit=''):
        return f'{value:g}{unit}' if isinstance(value,(int,float)) else str(value or 'TO DEFINE')
    rect(0,0,width,height,'#fff','#fff',0)
    rect(30,22,1640,100,'#eaf2f9','#d3e3ee')
    text(51,61,f"{model['name']} — WORKING ELECTRICAL DRAWING",27,weight='bold')
    text(52,92,f"{model['modules']} modules / {model['power_kwp']:.2f} kWp • {len(model['inverters'])} inverters • {model['battery_count']} BESS • {len(issues)} open checks",16)
    text(42,153,'PV FIELD / DC',19,weight='bold')
    text(575,153,'INVERTERS AND AC FEEDERS',19,weight='bold')
    text(1290,153,'MAIN BOARD / GRID',19,weight='bold')
    bus_x=1253
    wire(bus_x,194,bus_x,780)
    inverters=model['inverters']
    for i,inv in enumerate(inverters):
        y=190+i*154
        mppts=sorted({x['mppt'] for x in lines if x['inv']==inv['id'] and x['mppt'] is not None})
        rect(42,y,227,90,'#eaf7ee');text(52,y+31,f"{inv['id']} • {len(inv['strings'])} strings",17,weight='bold')
        text(52,y+57,f"{inv['dc_kwp']:.2f} kWp / {len(mppts)} MPPT")
        rect(296,y,240,90,'#f0f7fa');text(308,y+31,'DC: isolation / SPD',16,weight='bold')
        text(308,y+58,'Per string: see schedule',13)
        wire(269,y+45,296,y+45,'#2f7a64')
        rect(566,y,280,90,'#e7effc');text(578,y+27,inv['id']+'  '+inv['model'],13,weight='bold')
        text(578,y+55,f"{field(inv['kva'],' kVA')} / {len(mppts)} MPPT used",14)
        wire(536,y+45,566,y+45,'#2f7a64')
        rect(876,y,293,90,'#f8f3e9');text(888,y+28,f"QAC {inv['id']}  {field(inv['breaker_a'],' A')}",16,weight='bold')
        text(888,y+53,f"Cu {field(inv['section_mm2'],' mm²')} / L {field(inv['length_m'],' m')}",14)
        text(888,y+74,f"SPD : {field(inv['protection'].get('spd'))}",12)
        wire(846,y+45,876,y+45);wire(1169,y+45,bus_x,y+45)
        text(680,y+105,'BAT PORT',12,'#8b459d')
    rect(1285,189,365,123,'#edf4f9')
    text(1298,215,'MAIN BOARD / COLD STORE LOAD',17,weight='bold')
    text(1298,244,f"Main breaker {field(number(model['grid'].get('main_breaker_a')),' A')}",14)
    text(1298,269,f"Interface protection: {field(model['grid'].get('interface_protection'))}",12)
    wire(bus_x,253,1285,253)
    rect(1285,345,365,154,'#fff5e8')
    text(1298,373,'METER / EXPORT CONTROL',16,weight='bold')
    text(1298,398,f"Contract {field(model['contract_kw'],' kW')}",14)
    text(1298,422,f"Requested export {field(model['export_kw'],' kW')}",14)
    text(1298,448,'Status: '+str(model['export_status'] or 'to define'),13)
    text(1298,472,'Control: '+field(model['grid'].get('export_control')),12)
    wire(bus_x,418,1285,418)
    rect(1285,525,365,115,'#f2f4f7')
    text(1298,555,'TRANSFORMERS / GRID',16,weight='bold')
    text(1298,583,'2 × 375 kVA reported; wiring to survey',13)
    text(1298,612,'Topology: '+field(model['grid'].get('transformer_connection')),12)
    wire(bus_x,579,1285,579)
    rect(42,671,1127,129,'#f6f0fb')
    text(57,697,f"DEYE BATTERIES {BESS_MODEL} — DC BAT PORTS",17,weight='bold')
    if not model['battery']:
        text(59,739,'No battery connected in this option; third hybrid reserved for PV.',16)
    for i,b in enumerate(model['battery']):
        y=717+i*40;cfg=b['config']
        text(59,y,f"BESS {b['id']}  522.496 kWh: cluster 1 → {field(b['links'][0])} BAT, cluster 2 → {field(b['links'][1])} BAT",14)
        text(820,y,f"Fuse {field(number(cfg.get('fuse_a')),' A')} / Cu {field(number(cfg.get('section_mm2')),' mm²')}",12)
        text(820,y+15,f"Isolator {field(number(cfg.get('isolator_a')),' A')} / SPD {field(cfg.get('spd'))}",11)
        text(820,y+29,f"Route {field(number(cfg.get('length_m')),' m')}",11)
        for cluster_idx,inv_id in enumerate(b['links']):
            pos=next((n for n,item in enumerate(inverters) if item['id']==inv_id),None)
            if pos is not None:
                start_x=165+cluster_idx*155
                lane_x=10+(i*2+cluster_idx)*8
                src_y=y+21+cluster_idx*14
                dest_y=314+pos*154
                dashed=' stroke-dasharray="7 5"' if b['id']==2 else ''
                out.append(f'<path d="M{start_x},{src_y} L{lane_x},{src_y} L{lane_x},{dest_y} '
                           f'L680,{dest_y} L680,{280+pos*154}" fill="none" stroke="#8b459d" '
                           f'stroke-width="2.5"{dashed}/>')
                text(start_x-17,src_y+17,f'C{cluster_idx+1}',11,'#8b459d')
    if model['battery']:
        text(50,821,f"EMS: shared charge {model['charge_kw']:.0f} kW, discharge {model['discharge_kw']:.0f} kW with 1 or 2 cabinets.",12,'#6c4682')
    text(42,840,'ACTUAL STRING / MPPT INPUT ASSIGNMENTS',20,weight='bold')
    text(42,865,'Voltages at STC; cold conditions, bifacial current, protections and cable ratings require certified data.',13)
    table_y=890
    rect(40,table_y,1620,34,'#25445e','#25445e',0)
    cols=[(49,'String'),(170,'Inv.'),(240,'MPPT / input'),(391,'Modules'),(470,'kWp'),(543,'Voc / Vmp (V)'),
          (735,'Imp / Isc (A)'),(887,'A / B / loop (m)'),(1112,'DC cable'),(1230,'Fuse'),(1340,'Isolator'),(1480,'DC SPD')]
    for x,label in cols:text(x,table_y+23,label,12,'#fff','bold')
    for idx,line in enumerate(lines):
        y=table_y+34+idx*32
        rect(40,y,1620,32,'#f0f5f9' if idx%2 else '#fff','#e5e9ee',0)
        seq=sum(1 for previous in lines[:idx] if previous['inv']==line['inv'] and previous['mppt']==line['mppt'])+1
        route=line['route']
        lengths=(f"{route['terminal_A']['length_m']:.1f}/{route['terminal_B']['length_m']:.1f}/{route['loop_length_m']:.1f}" if route else 'TO SURVEY')
        pairs=[line['id'],line['inv'],f"{field(line['mppt'])} / {seq}",line['count'],f"{line['kwp']:.2f}",
               f"{field(line['voc_stc_v'])}/{field(line['vmp_stc_v'])}",
               f"{field(line['imp_a'])}/{field(line['isc_a'])}",lengths,
               field(line['section_mm2'],' mm²'),field(line['fuse_a'],' A'),field(line['isolator_a'],' A'),field(line['spd'])]
        for (x,_),value in zip(cols,pairs):text(x,y+22,value,12)
    y=table_y+34+len(lines)*32+44
    rect(40,y-31,1620,len(issues)*22+110,'#fff7ed','#e8d0a8')
    text(56,y,'OPEN ITEMS / DESIGN CHECKS',20,weight='bold')
    for i,issue in enumerate(issues):
        note=issue if len(issue)<205 else issue[:201]+'…'
        text(60,y+27+i*22,'• '+note,12,'#7d4232')
    text(56,y+len(issues)*22+57,'Working drawing; no unstated protection, cable rating or grid compliance is implied.',13,'#694936')
    out.append('</svg>')
    dest=Path(path);dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text('\n'.join(out),encoding='utf-8')
    return dest
