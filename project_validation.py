"""Project migrations and electrical checks; never invent missing ratings."""
import copy
import math
import re
from pathlib import Path
from collections import Counter, defaultdict

INVERTER_MODEL = 'SUN-125K-SG02HP3-EU-GM10'

def string_label(identifier):
    """Compact visible label without changing saved string identifiers."""
    match=re.fullmatch(r'String\s+(\d+)',str(identifier).strip(),flags=re.IGNORECASE)
    return f'S{match.group(1)}' if match else str(identifier)

FORMULA_ALIASES = {
    'POIDS_TOTAL_CABLAGES_KG':'TOTAL_CABLE_WEIGHT_KG',
    'NB_MODULES':'PANEL_COUNT', 'NB_STRINGS':'STRING_COUNT',
    'NB_ONDULEURS':'INVERTER_COUNT', 'PUISSANCE_TOTALE_WC':'PV_CAPACITY_WP',
    'COURANT_A':'CURRENT_A', 'TENSION_V':'VOLTAGE_V',
    'LONGUEUR_M':'LENGTH_M', 'RESISTIVITE':'RESISTIVITY',
    'CHUTE_CIBLE_PCT':'TARGET_DROP_PCT', 'SOMME':'SUM',
}

def english_formula(value):
    if not isinstance(value,str) or not value.lstrip().startswith('='):
        return value
    def translate(match):
        name=match.group(0)
        dynamic=re.fullmatch(r'(ZONE\d+|STRING\d+)_(NB_PANNEAUX|LARGEUR_MM|HAUTEUR_MM|LIGNES|COLONNES)',name)
        if dynamic:
            suffix={'NB_PANNEAUX':'PANEL_COUNT','LARGEUR_MM':'WIDTH_MM',
                    'HAUTEUR_MM':'HEIGHT_MM','LIGNES':'ROWS','COLONNES':'COLUMNS'}
            return dynamic.group(1)+'_'+suffix[dynamic.group(2)]
        return FORMULA_ALIASES.get(name,name)
    return re.sub(r'\b[A-Za-z_][A-Za-z_0-9]*\b',translate,value)

def normalize_formula_storage(data):
    """Migrate formula identifiers in both saved sheets, preserving nonformula text."""
    cells=data.get('material_spreadsheet',{}).get('cells',{})
    for address,value in list(cells.items()):cells[address]=english_formula(value)
    for category in data.get('material_categories',{}).values():
        for row in category.get('rows',[]):
            for name,value in list(row.items()):row[name]=english_formula(value)
    return data

def number(value):
    try:
        n = float(str(value).replace(',', '.'))
        return n if math.isfinite(n) else None
    except (ValueError, TypeError):
        return None

def natural(value):
    return [int(p) if p.isdigit() else p for p in re.split(r'(\d+)', str(value))]

def sync_diagram(data):
    """Assignments own generated wiring. Preserve custom devices and positions."""
    nodes = data.setdefault('diagram_nodes', {})
    old = copy.deepcopy(nodes)
    desired = set()
    links = []
    y = 60
    for block, spec in sorted(data.get('blocks', {}).items(), key=lambda x: natural(x[0])):
        inv = 'inv::'+block
        top = y
        for m in range(1, int(spec.get('mppt_count', 1))+1):
            mppt = f'mppt::{block}::{m}'
            desired.add(mppt)
            nodes[mppt] = dict(old.get(mppt, {'x':520, 'y':y}), type='mppt', label=f'MPPT {m}')
            strings = [sid for sid, a in data.get('string_mppt_assignment', {}).items()
                       if a.get('block') == block and a.get('mppt') == m and data.get('strings', {}).get(sid)]
            for sid in sorted(strings, key=natural):
                ident = 'str::'+sid
                desired.add(ident)
                nodes[ident] = dict(old.get(ident, {'x':160, 'y':y}), type='string',
                                    label=f'{sid} ({len(data["strings"][sid])} panels)')
                links.append({'a':ident, 'b':mppt, 'auto':True})
                y += 155
            links.append({'a':mppt, 'b':inv, 'auto':True})
            y += 155
        desired.add(inv)
        nodes[inv] = dict(old.get(inv, {'x':880, 'y':(top+y)/2}), type='inverter', label=block)
        y += 100
    for sid, members in data.get('strings', {}).items():
        if members and 'str::'+sid not in desired:
            ident='str::'+sid;desired.add(ident)
            nodes[ident]=dict(old.get(ident,{'x':125,'y':y}),type='string',label=f'{sid} ({len(members)} panels) — unassigned')
            y+=65
    for ident in list(nodes):
        if ident.startswith(('str::','mppt::','inv::')) and ident not in desired:
            del nodes[ident]
    # Even manually marked links must not contradict authoritative MPPT wiring.
    manual = [dict(l) for l in data.get('diagram_links', []) if not l.get('auto')
              and l.get('a') in nodes and l.get('b') in nodes
              and not any(str(l.get(k,'')).startswith(('str::','mppt::')) for k in ('a','b'))]
    data['diagram_links'] = manual + links
    return data

def resolve_image(filepath, stored):
    if not stored:
        return None
    parent=Path(filepath).resolve().parent
    raw=Path(stored)
    candidates=[parent/raw.name, raw] if raw.is_absolute() else [parent/raw, parent/raw.name]
    for path in candidates:
        if path.is_file(): return str(path.resolve())
    def clean(s):
        return re.sub(r'\(\d+\)$','',Path(s).stem).replace('├⌐','é').casefold()
    matches=[p for p in parent.iterdir() if p.is_file() and p.suffix.lower()==raw.suffix.lower() and clean(p.name)==clean(raw.name)]
    return str(matches[0].resolve()) if len(matches)==1 else None

def normalize_project(original):
    data=copy.deepcopy(original)
    panels=data.get('panels',{})
    for key in ('panel_blocks','panel_orientations'):
        data[key]={k:v for k,v in data.get(key,{}).items() if k in panels}
    data['strings']={sid:[k for k in coords if k in panels] for sid,coords in data.get('strings',{}).items()}
    data['manual_strings']=[s for s in data.get('manual_strings',[]) if s in data['strings']]
    data['string_mppt_assignment']={sid:a for sid,a in data.get('string_mppt_assignment',{}).items() if data['strings'].get(sid)}
    for sid,record in data.get('electrical_route_plan_3d',{}).get('routes',{}).items():
        members=data['strings'].get(sid,[])
        if members:
            for key,index in [('terminal_A',0),('terminal_B',-1)]:
                if key in record:record[key]['module_id']=panels[members[index]]
    data['cable_string_params']={s:p for s,p in data.get('cable_string_params',{}).items() if s in data['strings']}
    materials=data.get('material_categories',{})
    rows=materials.get('modules',{}).get('rows',[])
    if len(rows)==1 and (number(rows[0].get('Pmax (W)')) or 0)>0:
        data['panel_pmax_w']=number(rows[0]['Pmax (W)'])
    area=(number(data.get('panel_width_mm')) or 0)*(number(data.get('panel_height_mm')) or 0)/1e6
    if area>0 and (number(data.get('panel_pmax_w')) or 0)>0:
        data['panel_efficiency_pct']=data['panel_pmax_w']/area/10
    params=data.get('cable_calc_params',{})
    if number(params.get('length_m')) == 0:
        lengths=[r.get('loop_length_m',0)/2 for r in data.get('electrical_route_plan_3d',{}).get('routes',{}).values()]
        if lengths:params['length_m']=max(lengths)
    normalize_formula_storage(data)
    sync_diagram(data)
    return data

def audit_project(data):
    """Return explicit failures and missing engineering inputs, without approval."""
    issues=[];panels=data.get('panels',{});strings=data.get('strings',{});assign=data.get('string_mppt_assignment',{})
    uses=Counter(k for coords in strings.values() for k in coords)
    for k in panels:
        if uses[k]!=1:issues.append(f'Panel {panels[k]} ({k}): assigned {uses[k]} times.')
    slots=defaultdict(list)
    for sid,coords in strings.items():
        if not coords:continue
        a=assign.get(sid,{})
        block=data.get('blocks',{}).get(a.get('block'),{})
        if not block or not 1<=int(a.get('mppt',0))<=int(block.get('mppt_count',0)):
            issues.append(f'{sid}: missing or invalid MPPT assignment.');continue
        slots[(a['block'],a['mppt'])].append(sid)
    for (b,m),ids in slots.items():
        if len({len(strings[s]) for s in ids})>1:issues.append(f'{b} MPPT {m}: unequal parallel string lengths.')
        if len(ids)>int(data['blocks'][b].get('max_strings_per_mppt',2)):issues.append(f'{b} MPPT {m}: too many parallel strings.')
    if not data.get('cable_paths'):issues.append('No surveyed cable path: route lengths are preliminary estimates.')
    spec=data.get('electrical_checks',{})
    from electrical_checks import check
    issues.extend(check(data))
    if not spec.get('dimensions_confirmed'):issues.append('Module dimensions retained from layout; confirm against the selected datasheet before changing geometry.')
    issues.append('Final checks required: hot Vmp, bifacial current gain, per-input limits, ampacity, AC/BESS protections and grid certification.')
    return issues
