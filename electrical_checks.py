"""Per-string and per-inverter datasheet checks; missing limits stay unknown."""
from collections import defaultdict
from engineering_inputs import module_for_string,inverter_row,operating_values
from project_validation import number


def check(project):
    issues=[];global_spec=project.get('electrical_checks',{});strings=project.get('strings',{})
    module_rows=project.get('material_categories',{}).get('modules',{}).get('rows',[])
    inverters={b:inverter_row(project,b) for b in project.get('blocks',{})}
    distinct={str(sorted(row.items())) for row in inverters.values() if row}
    def limit(block,column,key):
        return number(inverters.get(block,{}).get(column,global_spec.get(key) if len(distinct)<=1 else None))
    slots=defaultdict(list);pv=defaultdict(float)
    for sid,members in strings.items():
        if not members:continue
        a=project.get('string_mppt_assignment',{}).get(sid,{})
        block=a.get('block');row=module_for_string(project,sid);op=operating_values(project,sid)
        fallback=global_spec if len(module_rows)<=1 else {}
        voc=op['voc_v'] or number(fallback.get('module_voc_v'))
        vmp=number(row.get('Vmp (V)',fallback.get('module_vmp_v')))
        imp=op['current_a'] or number(fallback.get('module_imp_a'));isc=op['isc_a'] or number(fallback.get('module_isc_a'))
        coeff=number(row.get('Voc temp coefficient (%/°C)',global_spec.get('voc_temp_coeff_pct')))
        tmin=number(global_spec.get('min_temperature_c'))
        vmax=limit(block,'Tension max (V)','inverter_max_dc_v')
        vmin=limit(block,'MPPT min (V)','mppt_min_v');mpptmax=limit(block,'MPPT max (V)','mppt_max_v')
        if any(x is None for x in (voc,vmp,imp,isc,coeff,tmin,vmax,vmin,mpptmax)):
            issues.append(f'{sid}: electrical validation incomplete for selected module / inverter.')
        if all(x is not None for x in (voc,coeff,tmin,vmax)):
            cold=len(members)*voc*(1+coeff/100*(tmin-25))
            if cold>vmax:issues.append(f'{sid}: cold Voc {cold:.1f} V exceeds inverter DC limit {vmax:g} V.')
        if all(x is not None for x in (vmp,vmin,mpptmax)) and not vmin<=len(members)*vmp<=mpptmax:
            issues.append(f'{sid}: STC Vmp outside selected inverter MPPT range.')
        hot_coeff=number(row.get('Vmp temp coefficient (%/°C)',global_spec.get('vmp_temp_coeff_pct')))
        tmax=number(global_spec.get('max_cell_temperature_c'))
        if hot_coeff is not None and tmax is not None and vmp and vmin:
            hot=len(members)*vmp*(1+hot_coeff/100*(tmax-25))
            if hot<vmin:issues.append(f'{sid}: hot Vmp {hot:.1f} V below MPPT minimum.')
        else:issues.append(f'{sid}: hot Vmp check missing coefficient / maximum cell temperature.')
        gain=number(row.get('Bifacial current gain (%)',global_spec.get('bifacial_current_gain_pct',0)))
        gain=0 if gain is None else gain
        slots[(block,a.get('mppt'))].append((sid,imp,isc,gain))
        rating=number(row.get('Pmax (W)',project.get('panel_pmax_w') if len(module_rows)<=1 else None))
        if rating:pv[block]+=len(members)*rating/1000
    for (block,mppt),records in slots.items():
        for index,column,key in ((1,'MPPT Imp max (A)','mppt_max_current_a'),(2,'MPPT Isc max (A)','mppt_max_isc_a')):
            maximum=limit(block,column,key)
            if maximum is None or any(r[index] is None for r in records):issues.append(f'{block} MPPT {mppt}: current check incomplete.')
            elif sum(r[index]*(1+r[3]/100) for r in records)>maximum:issues.append(f'{block} MPPT {mppt}: summed current exceeds {maximum:g} A.')
        per_input=number(inverters.get(block,{}).get('Input Isc max (A)'))
        if per_input is not None:
            for sid,_,isc,gain in records:
                if isc and isc*(1+gain/100)>per_input:issues.append(f'{sid}: short-circuit current exceeds per-input rating.')
        else:issues.append(f'{block} MPPT {mppt}: per-input short-circuit limit not supplied.')
    for block,kw in pv.items():
        maximum=limit(block,'PV max (kW)','inverter_max_pv_kw')
        if maximum is None:issues.append(f'{block}: maximum PV input power not supplied.')
        elif kw>maximum:issues.append(f'{block}: {kw:.2f} kWp exceeds configured PV input limit {maximum:g} kW.')
    return issues
