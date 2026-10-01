"""Preliminary AC/DC single-line drawing derived from the active PV project.

SVG export uses only Python's standard library. Equipment protections are
functional placeholders: no interrupting rating, cable ampacity or CEI 0-16
certificate is asserted by this drawing.
"""

from collections import Counter, defaultdict
import json
from html import escape
from pathlib import Path
import xml.etree.ElementTree as ET

INVERTER = 'DEYE SUN-125K-SG02HP3-EU-GM10'
BATTERY = 'DEYE MC-L522-2H3'


def route_is_current(data, sid):
    plan = data.get('electrical_route_plan_3d') or {}
    sig = plan.get('source_signature') or {}
    rec = (plan.get('routes') or {}).get(sid)
    if sig.get('routing_model') != 'installation_surfaces_v1':return False
    if json.dumps(sig.get('roof_polygons'),sort_keys=True) != json.dumps(data.get('roof_polygons',[]),sort_keys=True):return False
    if sig.get('routing_settings') != data.get('routing_settings',sig.get('routing_settings')):return False
    if not rec or not sig:
        return False
    if sig.get('strings', {}).get(sid) != data.get('strings', {}).get(sid):
        return False
    if sig.get('assignments', {}).get(sid) != data.get('string_mppt_assignment', {}).get(sid):
        return False
    inv=rec.get('inverter')
    p=data.get('inverter_positions', {}).get(inv, {})
    if sig.get('inverter_positions', {}).get(inv) != [p.get('x'),p.get('y'),p.get('terminal_height_m')]:
        return False
    for key in ('px_per_mm','panel_width_mm','panel_height_mm'):
        if sig.get(key) != data.get(key):
            return False
    old=[{'id':p.get('id'),'points':[list(q) for q in p.get('points',[])]} for p in data.get('cable_paths',[])]
    if sig.get('cable_paths') != old:
        return False
    old_zones=sig.get('roof_zones',[])
    new_zones=data.get('roof_zones',[])
    if len(old_zones)!=len(new_zones):
        return False
    for old,now in zip(old_zones,new_zones):
        for key,value in old.items():
            current=now.get(key)
            if isinstance(value,(int,float)) and not isinstance(value,bool) and isinstance(current,(int,float)):
                if abs(current-value)>1e-6:return False
            elif current!=value:return False
    return True


def build_model(data, batteries):
    if batteries not in (0,1,2):
        raise ValueError('Allowed BESS counts: 0, 1 or 2')
    strings=data.get('strings') or {}
    assignments=data.get('string_mppt_assignment') or {}
    if not strings or set(assignments)!=set(strings):
        raise ValueError('String or MPPT assignments are missing or inconsistent')
    per_inv=defaultdict(list)
    slots=defaultdict(list)
    issues=[]
    all_modules=[str(q) for parts in strings.values() for q in parts]
    if len(all_modules)!=len(set(all_modules)):
        issues.append('The same module appears in multiple strings.')
    if len(all_modules)!=len(data.get('panels',{})):
        issues.append('The number of modules assigned to strings differs from the layout.')
    routes=(data.get('electrical_route_plan_3d') or {}).get('routes',{})
    lines=[]
    for sid in sorted(strings,key=lambda s:int(s.split()[-1])):
        a=assignments[sid]
        inv=a.get('block');mppt=int(a.get('mppt',0))
        if inv not in data.get('blocks',{}) or not 1<=mppt<=int(data['blocks'][inv].get('mppt_count',0)):
            raise ValueError(f'{sid}: invalid inverter or MPPT')
        slots[(inv,mppt)].append(sid)
        per_inv[inv].append(sid)
        rec=routes.get(sid) if route_is_current(data,sid) else None
        if rec and (rec.get('inverter')!=inv or rec.get('mppt')!=mppt or rec.get('modules')!=len(strings[sid])):
            rec=None
        lines.append({'id':sid,'inv':inv,'mppt':mppt,'count':len(strings[sid]),
                      'route':rec})
    for (inv,mppt),sids in slots.items():
        if len(sids)>int(data['blocks'][inv].get('max_strings_per_mppt',2)):
            issues.append(f'{inv} MPPT {mppt}: {len(sids)} strings; maximum two inputs.')
        if len(sids)==2 and len(strings[sids[0]])!=len(strings[sids[1]]):
            issues.append(f'{inv} MPPT {mppt}: Parallel strings have different lengths.')
    for inv,sids in per_inv.items():
        p_kw=sum(len(strings[s])*float(data.get('panel_pmax_w',720))/1000 for s in sids)
        from project_validation import number
        dc_limit=number(data.get('electrical_checks',{}).get('inverter_max_pv_kw'))
        if dc_limit is not None and p_kw>dc_limit:
            issues.append(f'{inv}: PV power {p_kw:.1f} kWp exceeds the configured DC limit.')
    if batteries and data.get('bess_summary'):
        cfg=data['bess_summary'].get('battery_settings',{})
        ch=float(cfg.get('charge_kw',250));dis=float(cfg.get('discharge_kw',150))
        if ch>250 or dis>250:
            issues.append('EMS limit exceeds 250 kW nominal per cabinet; check the control settings.')
    else:ch,dis=250,150
    stale=[item['id'] for item in lines if item['route'] is None]
    if stale:issues.append(f'{len(stale)}/{len(lines)} two-pole routes missing or stale: recalculate lengths and sections.')
    equipment={inv:__import__('engineering_inputs').inverter_row(data,inv) for inv in per_inv}
    return {'equipment':equipment,'blocks':data.get('blocks',{}),'batteries':batteries,'strings':lines,'per_inv':per_inv,'slots':slots,
            'modules':len(all_modules),'power_kwp':sum(len(v) for v in strings.values())*float(data.get('panel_pmax_w',720))/1000,
            'charge_kw':ch,'discharge_kw':dis,'issues':issues,'stale':stale,
            'name':str(data.get('project_name','PV project'))}


def write_svg(model,path,language='en'):
    """One drawing with site one-line and exact string-to-MPPT schedule."""
    if len(model['per_inv'])>3:
        raise ValueError('Use the detailed electrical export for more than three inverters.')
    out=[]
    def add(s):out.append(s)
    def txt(x,y,s,size=18,color='#203047',weight='normal',anchor='start'):
        add(f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" font-family="DejaVu Sans,Arial,sans-serif">{escape(str(s))}</text>')
    def rect(x,y,w,h,fill='#ffffff',stroke='#7d90a1',rx=9):
        add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
    def line(x1,y1,x2,y2,color='#314d68',width=4,dash=''):
        add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}" {f"stroke-dasharray={chr(34)+dash+chr(34)}" if dash else ""}/>')
    def box(x,y,w,h,title,description,fill='#f3f7fa'):
        rect(x,y,w,h,fill);txt(x+12,y+27,title,17,weight='bold');txt(x+12,y+52,description,14)
    rows=model['strings'];height=1450+len(rows)*27+160
    add(f'<svg xmlns="http://www.w3.org/2000/svg" width="1560" height="{height}" viewBox="0 0 1560 {height}">')
    rect(0,0,1560,height,'#ffffff','#ffffff',0)
    rect(35,26,1490,108,'#eaf1f7','#eaf1f7')
    txt(55,68,f"VOLFRIGO - SCHÉMA UNIFILAIRE PRÉLIMINAIRE | {model['modules']} MODULES",27,weight='bold')
    txt(55,104,f"{model['power_kwp']:.2f} kWp DC | {len(model['per_inv'])} inverters | {model['batteries']} BESS AC",18)
    txt(55,166,'TOITURE / DC',19,weight='bold');txt(580,166,'CONVERSION / AC',19,weight='bold');txt(1100,166,'TGBT / POINT DE CONNEXION',19,weight='bold')
    bus_x=1120
    line(bus_x,242,bus_x,955,'#264567',8);txt(1137,273,'BARRE AC TGBT',17,weight='bold')
    for i,inv in enumerate(model['per_inv']):
        y=225+i*177
        sids=model['per_inv'].get(inv,[])
        count=sum(q['count'] for q in rows if q['inv']==inv)
        mppts=len({q['mppt'] for q in rows if q['inv']==inv})
        kw=count*model['power_kwp']/model['modules'] if model['modules'] else 0
        box(55,y,234,78,f'{inv} - {len(sids)} strings',f'{count} modules / {kw:.2f} kWp')
        line(289,y+40,313,y+40,'#24744b')
        box(313,y,210,78,f'QDC-{i+1} / SPD DC',f'{mppts} MPPT utilisés',fill='#eaf6ef')
        line(523,y+40,548,y+40,'#24744b')
        box(548,y,237,78,inv+' / '+str(model['equipment'][inv].get('Modèle') or 'MODEL MISSING'),str(model['blocks'][inv].get('mppt_count','?'))+' MPPT / ratings: equipment sheet',fill='#e7f0fa')
        line(785,y+40,809,y+40)
        box(809,y,223,78,f'QAC-{i+1} / SPD AC','coupure + protection à étudier')
        line(1032,y+40,bus_x,y+40)
        txt(548,y+104,'Port batterie de cet inverter: non câblé au MC-L522',12,'#697888')
    if not model['batteries']:
        rect(55,793,970,84,'#f3f6fa','#d6dfe7')
        txt(76,826,'OPTION SANS BESS',21,weight='bold')
        txt(76,855,'Branches batterie et protections dédiées absentes; espace préservé pour extension.',16)
    for i in range(model['batteries']):
        y=748+i*118
        box(314,y,445,80,f'BAT-{i+1} / {BATTERY}','522,496 kWh / PCS AC 250 kW nominal',fill='#fff1e7')
        line(759,y+40,784,y+40,'#b36b29')
        box(784,y,252,80,f'QB-{i+1} / SPD AC','sectionnement + protection à étudier',fill='#fff8f1')
        line(1036,y+40,bus_x,y+40,'#b36b29')
    rect(1164,301,339,128,'#fff7e9','#d8aa5b')
    txt(1180,336,'CHARGES FRIGORIFIQUES',18,weight='bold')
    txt(1180,364,'Tableau de distribution existant',15)
    txt(1180,390,'Circuit de secours non défini',14,'#844818')
    line(bus_x,360,1164,360)
    line(bus_x,584,1184,584)
    box(1184,549,320,86,'M / QPCC / SPI / CCI','mesure, interface, anti-export')
    line(1343,635,1343,673)
    box(1184,673,320,90,'TR MT/BT EXISTANTS','2 x 375 kVA (topologie à relever)')
    line(1343,763,1343,794)
    box(1184,794,320,87,'POD / RÉSEAU MT','export demandé 300 kW (à autoriser)' )
    rect(55,1004,1450,145,'#fff8ec','#e7c789')
    txt(74,1040,'LIMITES ET ISOLATION D’URGENCE',20,weight='bold')
    txt(74,1071,f"EMS: charge {model['charge_kw']:.0f} kW et décharge {model['discharge_kw']:.0f} kW TOTALES pour 1 ou 2 BESS; PCS installé: {250*model['batteries']} kW nominal.",16)
    txt(74,1101,'Commande incendie identifiée: réseau + 3 AC inverseurs + DC FV + chaque BESS; logique et implantation à valider.',15)
    txt(74,1128,'La coupure AC/DC ne supprime pas la tension des modules éclairés. Aucun départ « secours » n’est défini ici.',14,'#744917')
    txt(55,1194,f'RÉPARTITION DES {len(rows)} STRINGS / ENTRÉES MPPT / 2 PÔLES',21,weight='bold')
    txt(55,1221,'A et B sont les extrémités; polarité +/- à contrôler. Plan 3D cohérent avec le fichier, tracé terrain à valider.',14)
    rect(54,1244,1451,37,'#24425f','#24425f',0)
    cols=[(72,'STRING'),(256,'ONDULEUR'),(425,'MPPT / ENTRÉE'),(636,'MODULES'),(796,'A (m)'),(958,'B (m)'),(1120,'A+B (m)'),(1320,'Cu / ΔV')]
    for x,s in cols:txt(x,1270,s,14,'#ffffff','bold')
    for i,r in enumerate(rows):
        y=1281+i*27
        rect(54,y,1451,27,'#eef3f8' if i%2 else '#ffffff','#e1e7ec',0)
        rec=r['route'];seq=sum(1 for p in rows[:i] if p['inv']==r['inv'] and p['mppt']==r['mppt'])+1
        vals=[r['id'],r['inv'],f"{r['mppt']} / {seq}",str(r['count'])]
        if rec:
            vals += [f"{rec['terminal_A']['length_m']:.2f}",f"{rec['terminal_B']['length_m']:.2f}",
                     f"{rec['loop_length_m']:.2f}",(f"{rec['working_section_mm2']} mm² / {rec['drop_at_working_section_pct']:.2f}%" if rec.get('drop_at_working_section_pct') is not None else 'TO SIZE')]
        else: vals += ['RECALCUL','RECALCUL','RECALCUL','À VÉRIFIER']
        for (x,_),value in zip(cols,vals):txt(x,y+19,value,13)
    y=1281+len(rows)*27+34
    txt(55,y,'VÉRIFICATIONS AVANT EXÉCUTION',19,weight='bold');y+=32
    checks=[
        'Sections, fusibles et protections AC/BESS: courant de défaut, sélectivité, pose, longueur, température et norme locale non fournis.',
        'Conformité CEI 0-16 des convertisseurs et SPI/CCI: documentation et acceptation du distributeur à obtenir.',
        'POD, 2 transformateurs, limites injection et commande anti-export: relevé du schéma existant puis étude de flux.',
        'En toiture: coordination foudre/SPD, dispositifs de coupure, cheminements, traversées et consignes pompiers.',
        'Modèle et caractéristiques certifiées du module 720 W, tension froide, Isc et bifacialité: contrôler avant câblage.',
    ]
    for c in checks:txt(72,y,'• '+c,14);y+=26
    for i,c in enumerate(model['issues'][:3]):txt(72,y+i*25,'ATTENTION: '+c,14,'#9c312e')
    add('</svg>')
    dest=Path(path);dest.parent.mkdir(parents=True,exist_ok=True)
    svg='\n'.join(out)
    if True:  # Every application export uses English.
        translations={
            'SCHÉMA UNIFILAIRE PRÉLIMINAIRE':'PRELIMINARY SINGLE-LINE DIAGRAM',
            'hybrides':'hybrid inverters','révision du':'revised',
            'TOITURE / DC':'ROOF / DC','CONVERSION / AC':'CONVERSION / AC',
            'TGBT / POINT DE CONNEXION':'MAIN AC BOARD / GRID CONNECTION',
            'MPPT utilisés':'MPPTs in use','strings':'strings','modules /':'modules /',
            'HYBRIDE':'HYBRID','Port batterie de cet inverter: non câblé au MC-L522':
                'Inverter battery ports: not connected to MC-L522',
            'coupure + protection à étudier':'isolation + protection TBD',
            'sectionnement + protection à étudier':'isolation + protection TBD',
            'BARRE AC TGBT':'MAIN AC BUS',
            'CHARGES FRIGORIFIQUES':'COLD-STORE LOADS',
            'Tableau de distribution existant':'Existing distribution board',
            'Circuit de secours non défini':'Backup circuit not defined',
            'mesure, interface, anti-export':'meter, interface, export control',
            'TR MT/BT EXISTANTS':'MV/LV TRANSFORMERS',
            'topologie à relever':'topology to survey',
            'POD / RÉSEAU MT':'GRID CONNECTION / MV',
            'export demandé 300 kW (à autoriser)' :'requested export 300 kW (pending approval)',
            'OPTION SANS BESS':'NO BESS OPTION',
            'Branches batterie et protections dédiées absentes; espace préservé pour extension.':
                'No battery feeders or dedicated protection; future space reserved.',
            'LIMITES ET ISOLATION D’URGENCE':'LIMITS AND EMERGENCY ISOLATION',
            'charge':'charge','décharge':'discharge','TOTALES':'SHARED',
            'pour 1 ou 2 BESS':'with 1 or 2 BESS',
            'PCS installé':'installed PCS',
            'Commande incendie identifiée: réseau + 3 AC inverseurs + DC FV + chaque BESS; logique et implantation à valider.':
                'Emergency isolation: grid + 3 inverter AC branches + PV DC + each BESS; logic and positions to confirm.',
            'La coupure AC/DC ne supprime pas la tension des modules éclairés. Aucun départ « secours » n’est défini ici.':
                'AC/DC isolation does not de-energise lit PV modules. No backup-load feeder is designed.',
            'RÉPARTITION DES':'SCHEDULE OF','STRINGS / ENTRÉES MPPT / 2 PÔLES':'STRINGS / MPPT INPUTS / BOTH POLES',
            'A et B sont les extrémités; polarité +/- à contrôler. Plan 3D cohérent avec le fichier, tracé terrain à valider.':
                'A and B are string endpoints; actual +/- polarity to verify. 3D routes match this file; survey on site.',
            'ONDULEUR':'INVERTER','MPPT / ENTRÉE':'MPPT / INPUT',
            'MODULES':'MODULES',
            'RECALCUL':'RECALCULATE','À VÉRIFIER':'TO CHECK',
            'VÉRIFICATIONS AVANT EXÉCUTION':'CHECKS BEFORE FINAL DESIGN',
            'Sections, fusibles et protections AC/BESS: courant de défaut, sélectivité, pose, longueur, température et norme locale non fournis.':
                'AC/BESS conductors, fuses and protection: fault level, selectivity, routing, lengths and ambient conditions pending.',
            'Conformité CEI 0-16 des convertisseurs et SPI/CCI: documentation et acceptation du distributeur à obtenir.':
                'Obtain CEI 0-16 evidence for converters and confirm interface/controller requirements with the grid operator.',
            'POD, 2 transformateurs, limites injection et commande anti-export: relevé du schéma existant puis étude de flux.':
                'Survey grid point, both transformers, permitted export and control; then perform a site power-flow study.',
            'En toiture: coordination foudre/SPD, dispositifs de coupure, cheminements, traversées et consignes pompiers.':
                'On roof: verify lightning/SPD coordination, isolation, routes, penetrations and firefighter access.',
            'Modèle et caractéristiques certifiées du module 720 W, tension froide, Isc et bifacialité: contrôler avant câblage.':
                'Confirm exact 720 W module, cold open-circuit voltage, short-circuit current and bifacial gain.',
            'ATTENTION:':'WARNING:',
            'two-pole routes missing or stale: recalculate lengths and sections.':
                'two-pole routes missing or stale: recalculate lengths and sections.',
        }
        root=ET.fromstring(svg)
        for el in root.iter():
            if el.tag.endswith('}text') and el.text:
                value=el.text
                for before,after in translations.items():value=value.replace(before,after)
                value=value.replace(' et ',' and ')
                el.text=value
        svg=ET.tostring(root,encoding='unicode')
    dest.write_text(svg,encoding='utf-8')
    return dest
