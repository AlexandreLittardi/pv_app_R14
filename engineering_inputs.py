"""One source of electrical operating data for routes, schedules and energy."""
import copy
from project_validation import number

def module_for_string(project,sid):
    rows=project.get('material_categories',{}).get('modules',{}).get('rows',[])
    override=project.get('cable_string_params',{}).get(sid,{})
    idx=override.get('module_row')
    if idx is not None and isinstance(idx,int) and 0<=idx<len(rows):return rows[idx]
    return rows[0] if len(rows)==1 else {}

def operating_values(project,sid):
    row=module_for_string(project,sid);override=project.get('cable_string_params',{}).get(sid,{})
    count=len(project.get('strings',{}).get(sid,[]))
    vmp=number(row.get('Vmp (V)'));imp=number(row.get('Imp (A)'))
    return {'current_a':number(override.get('current_a',imp)),
            'voltage_v':number(override.get('voltage_v',vmp*count if vmp else None)),
            'isc_a':number(override.get('isc_a',row.get('Isc (A)'))),
            'voc_v':number(row.get('Voc (V)'))}

def inverter_row(project,block):
    placement=project.get('inverter_positions',{}).get(block,{})
    link=project.get('equipment_links',{}).get(block)
    rows=project.get('material_categories',{}).get('inverters',{}).get('rows',[])
    if isinstance(link,int) and 0<=link<len(rows):return copy.deepcopy(rows[link])
    return placement.get('material_row',{})

def ac_limit_kw(project,block):
    row=inverter_row(project,block)
    kw=number(row.get('Puissance active (kW)'))
    if kw is not None and kw>0:return kw
    kva=number(row.get('Puissance (kVA)'))
    pf=number(row.get('Cos phi',project.get('electrical_design',{}).get('power_factor')))
    if kva is None or kva<=0 or pf is None or not 0<pf<=1:
        raise ValueError(f'{block}: enter active power (kW), or apparent power (kVA) and power factor in Equipment / Electrical design.')
    return kva*pf

def panel_connections(app):
    connected={};seen=set()
    for sid,members in app.strings.items():
        if not members:continue
        a=app.string_mppt_assignment.get(sid,{})
        block=a.get('block');slot=a.get('mppt')
        spec=app.blocks.get(block,{})
        if not spec or not isinstance(slot,int) or not 1<=slot<=int(spec.get('mppt_count',0)):
            raise ValueError(f'{sid}: assign a valid inverter / MPPT before energy calculation.')
        for c in members:
            if c not in app.panels or c in seen:raise ValueError(f'{sid}: missing or duplicate module membership.')
            declared=app.panel_blocks.get(c)
            if declared and declared!=block:raise ValueError(f'{sid}: module block differs from its inverter assignment.')
            seen.add(c);connected[c]=block
    if seen!=set(app.panels):raise ValueError('Connect every module to exactly one string before calculating energy.')
    return connected
