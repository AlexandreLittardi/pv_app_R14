"""Declarative questionnaire fields and transactional input parsing."""
import copy
from dataclasses import dataclass
import math
from project_store import MODEL_DEFAULTS,validate_project
from detailed_electrical import normalise_design
from energy_economics import DEFAULTS as ECONOMIC_DEFAULTS

@dataclass
class Field:
    section:str
    path:tuple
    label:str
    kind:str='number'
    choices:tuple=()
    optional:bool=False

LABELS={
 'panel_width_mm':'Module width (mm)','panel_height_mm':'Module height (mm)','panel_tilt_deg':'Module tilt (°)',
 'panel_azimuth_deg':'Module azimuth from north (°)','panel_pmax_w':'Module STC power (W)','px_per_mm':'Image scale (pixels/mm)',
 'scale_length_mm':'Calibration reference length (mm)','solar_latitude':'Site latitude (°)','solar_longitude':'Site longitude (°)',
 'north_offset_deg':'Image north offset (°)','solar_utc_offset':'Instantaneous solar UTC offset (hours)',
 'solar_day':'Solar study day','solar_month':'Solar study month','solar_hour':'Solar study hour (decimal)',
 'panel_noct_c':'Module NOCT (°C)','panel_temp_coeff_pct':'Power temperature coefficient (%/°C)',
 'pylon_height_mm':'Primary obstacle height (mm)','pylon_width_mm':'Primary obstacle width (mm)',
 'pylon_opacity':'Primary obstacle opacity (0–1)','timezone':'Site time zone (IANA)',
 'imputation':'Missing consumption method','shadow_model':'Shading model','bypass_groups':'Bypass groups per module',
 'module_gap_x_mm':'Horizontal module gap (mm)','module_gap_y_mm':'Vertical module gap (mm)',
 'edge_clearance_mm':'Zone edge clearance (mm)','bess_auxiliary_kw':'Auxiliary demand per cabinet (kW)',
 'bess_annual_degradation_pct':'BESS capacity degradation (%/year)','bess_lifetime_years':'Economic horizon (years)',
 'annual_maintenance_eur':'Annual maintenance per cabinet (€)','discount_rate_pct':'Discount rate (%)',
 'inverter_height_m':'Default inverter terminal height (m)','reserve_per_pole_m':'Reserve per conductor (m)',
 'bridge_gap_m':'Maximum bridged cable gap (m)','current_a':'String operating current (A)',
 'voltage_v':'String operating voltage (V)','isc_a':'String short-circuit current (A)',
 'section_mm2':'Chosen conductor section (mm²)','ampacity_a':'Corrected cable ampacity (A)',
 'protection_a':'Protection rating (A)','linear_mass_kg_m':'Cable linear mass (kg/m)',
 'module_row':'Module sheet row (0-based)','installation_height_m':'Cable installation elevation (m)',
 'z_mm':'Shadow receiver elevation (mm)','terminal_height_m':'Inverter terminal height (m)',
 'nominal_kwh':'Capacity per cabinet (kWh)','charge_kw':'Shared charging limit (kW)',
 'discharge_kw':'Shared discharge limit (kW)','soc_min_pct':'Minimum SOC (%)','soc_max_pct':'Maximum SOC (%)',
 'round_trip_efficiency':'Round-trip efficiency (0–1)','ac_factor':'Additional AC conversion factor (0–1)',
 'existing_contract_kw':'Existing contract power (kW)','export_limit_kw':'Export limit (kW)',
 'export_limit_status':'Export authorization status','model':'Equipment model',
 'module_voc_v':'Default module Voc at STC (V)','module_vmp_v':'Default module Vmp at STC (V)',
 'module_imp_a':'Default module Imp (A)','module_isc_a':'Default module Isc (A)',
 'voc_temp_coeff_pct':'Default Voc temperature coefficient (%/°C)','vmp_temp_coeff_pct':'Default Vmp temperature coefficient (%/°C)',
 'min_temperature_c':'Minimum design temperature (°C)','max_cell_temperature_c':'Maximum cell temperature (°C)',
 'bifacial_current_gain_pct':'Bifacial current gain (%)','inverter_max_dc_v':'Default maximum inverter DC voltage (V)',
 'mppt_min_v':'Default MPPT minimum voltage (V)','mppt_max_v':'Default MPPT maximum voltage (V)',
 'mppt_max_current_a':'Default MPPT operating-current limit (A)','mppt_max_isc_a':'Default MPPT short-circuit limit (A)',
 'inverter_max_pv_kw':'Default maximum inverter PV power (kW)','dimensions_confirmed':'Module dimensions verified against datasheet',
 'import_eur_kwh':'Grid purchase price (€/kWh)','export_low_eur_kwh':'Low export tariff (€/kWh)',
 'export_high_eur_kwh':'High export tariff (€/kWh)','pv_capex_eur':'PV investment (€)',
 'bess_capex_each_eur':'Investment per BESS cabinet (€)','annual_degradation_pct':'Economic degradation assumption (%/year)',
 'lifetime_years':'Economic projection horizon (years)','replacement_year':'Replacement year (0 = none)',
 'replacement_cost_eur':'Replacement cost per cabinet (€)','ac_voltage_v':'AC line-to-line voltage (V)',
 'power_factor':'AC power factor (0–1)','fuse_a':'DC fuse rating (A)','isolator_a':'Isolator rating (A)',
 'spd':'Surge protection model/type','breaker_a':'Breaker rating (A)','length_m':'Cable length (m)',
 'mppt_count':'MPPT count','max_strings_per_mppt':'Maximum strings per MPPT',
 'cluster_1_to':'Battery cluster 1 inverter connection','cluster_2_to':'Battery cluster 2 inverter connection',
 'meter_id':'Meter reference','main_breaker_a':'Main breaker rating (A)',
 'interface_protection':'Grid interface protection','export_control':'Export-limiter control',
 'transformer_connection':'Transformer connection arrangement','emergency_shutdown':'Emergency shutdown arrangement',
 'latitude':'Weather source latitude (°)','longitude':'Weather source longitude (°)',
 'tilt_deg':'Weather source tilt (°)','azimuth_deg_from_south':'Weather source azimuth from south (°)',
}
TEXT_KEYS={'model','spd','export_limit_status','meter_id','interface_protection','export_control',
 'transformer_connection','emergency_shutdown','cluster_1_to','cluster_2_to','isolator','name'}
INTEGER_KEYS={'solar_day','solar_month','bypass_groups','bess_lifetime_years','lifetime_years','replacement_year','mppt_count','max_strings_per_mppt','bess_count'}
OPTION_KEYS={'module_voc_v','module_vmp_v','module_imp_a','module_isc_a','voc_temp_coeff_pct','min_temperature_c',
 'vmp_temp_coeff_pct','max_cell_temperature_c','bifacial_current_gain_pct','inverter_max_dc_v','mppt_min_v',
 'mppt_max_v','mppt_max_current_a','mppt_max_isc_a','inverter_max_pv_kw'}

def label(key):return LABELS.get(key,str(key).replace('_',' ').capitalize())
def get(data,path,default=''):
    try:
        for key in path:data=data[key]
        return data
    except (KeyError,IndexError,TypeError):return default

def put(data,path,value):
    current=data
    for i,key in enumerate(path[:-1]):
        if isinstance(current,dict):current=current.setdefault(key,[] if isinstance(path[i+1],int) else {})
        else:current=current[key]
    if value is None and isinstance(current,dict):current.pop(path[-1],None)
    else:current[path[-1]]=value

def prepare(data):
    data=copy.deepcopy(data)
    data['model_settings']={**MODEL_DEFAULTS,**data.get('model_settings',{})}
    data['economic_settings']={**ECONOMIC_DEFAULTS,**data.get('economic_settings',{})}
    data['electrical_design']=normalise_design(data.get('electrical_design',{}))
    data.setdefault('electrical_checks',{})
    for key,value in {'bridge_gap_m':0.,'inverter_height_m':1.,'reserve_per_pole_m':2.}.items():data.setdefault('routing_settings',{}).setdefault(key,value)
    from datetime import date
    data['model_settings'].setdefault('report_shadow_year',date.today().year)
    data['model_settings'].setdefault('weather_import_metadata',{'latitude':data.get('solar_latitude',0.),'longitude':data.get('solar_longitude',0.),'tilt_deg':data.get('panel_tilt_deg',0.),'azimuth_deg_from_south':(data.get('panel_azimuth_deg') if data.get('panel_azimuth_deg') is not None else 180.)%360-180.})
    from battery_dispatch import BatterySettings
    from dataclasses import asdict
    energy=data.setdefault('energy_input_settings',{})
    energy.setdefault('ac_factor',.9)
    defaults=asdict(BatterySettings());energy.setdefault('bess',{})
    for key in ('nominal_kwh','charge_kw','discharge_kw','soc_min_pct','soc_max_pct','round_trip_efficiency'):energy['bess'].setdefault(key,defaults[key])
    data.setdefault('cable_calc_params',{'current_a':12.,'voltage_v':400.,'length_m':0.,'resistivity':.017,'target_drop_pct':1.})
    for key,value in {'existing_contract_kw':0.,'export_limit_kw':0.,'export_limit_status':'Not confirmed'}.items():data.setdefault('grid_connection_settings',{}).setdefault(key,value)
    return data

def fields(data):
    from mixins.material_tools import MATERIAL_CATEGORY_DEFS,MATERIAL_COLUMNS_EN,MATERIAL_TITLES_EN
    from mixins.notes_tools import STANDARD_DC_SECTIONS
    result=[]
    def add(section,path,title=None,kind=None,choices=(),optional=False):
        key=path[-1]
        result.append(Field(section,tuple(path),title or label(key),kind or ('integer' if key in INTEGER_KEYS else 'text' if key in TEXT_KEYS else 'number'),tuple(choices),optional))
    add('Project',('project_name',),'Project name','text')
    add('Annual shadow study',('model_settings','report_shadow_year'),'Report study year','integer')
    for key in ('string_min_panels','string_max_panels'):add('String generation',(key,),kind='integer',optional=True)
    add('String generation',('string_direction',),'String generation direction','choice',choices=('Auto (layout)','Horizontal','Vertical'),optional=True)
    for key in ('px_per_mm','scale_length_mm','panel_width_mm','panel_height_mm','panel_tilt_deg','panel_azimuth_deg','panel_pmax_w'):add('Roof and modules',(key,))
    for key in ('solar_latitude','solar_longitude','north_offset_deg','solar_day','solar_month','solar_hour','solar_utc_offset','panel_noct_c','panel_temp_coeff_pct','pylon_height_mm','pylon_width_mm','pylon_opacity'):add('Solar and thermal model',(key,))
    for key in ('scale_p1','scale_p2','pylon_img_pos','pylon_ref_img_pos'):add('Roof and modules' if key.startswith('scale') else 'Solar and thermal model',(key,),key.replace('_',' ').capitalize()+' (image pixels)','point',optional=True)
    choices={'imputation':('previous_week','reject','zero'),'shadow_model':('geometric','bypass_estimate')}
    for key in ('latitude','longitude','tilt_deg','azimuth_deg_from_south'):add('New weather file — verify actual source metadata',('model_settings','weather_import_metadata',key))
    for key in MODEL_DEFAULTS:add('Model assumptions',('model_settings',key),kind='choice' if key in choices else 'text' if key=='timezone' else None,choices=choices.get(key,()))
    for category,(title,columns) in MATERIAL_CATEGORY_DEFS.items():
        for i,row in enumerate(data.get('material_categories',{}).get(category,{}).get('rows',[])):
            for column in dict.fromkeys(columns+list(row)):
                add('Equipment — '+MATERIAL_TITLES_EN[category]+f' / row {i+1}',('material_categories',category,'rows',i,column),MATERIAL_COLUMNS_EN.get(column,column),'equipment',optional=True)
    for key in sorted(OPTION_KEYS):add('Electrical verification',('electrical_checks',key),optional=True)
    add('Electrical verification',('electrical_checks','dimensions_confirmed'),kind='boolean')
    for i,z in enumerate(data.get('roof_zones',[])):
        for key in ('x1','y1','x2','y2','installation_height_m','z_mm'):add(f'Installation zone {i+1}',('roof_zones',i,key),label(key)+(' (image pixels)' if key in ('x1','y1','x2','y2') else ''),optional=key in ('installation_height_m','z_mm'))
    for i,p in enumerate(data.get('roof_polygons',[])):
        add(f'Routing area {i+1}',('roof_polygons',i,'points'),'Boundary points (image pixels)','points')
        add(f'Routing area {i+1}',('roof_polygons',i,'installation_height_m'),optional=True)
    for key in ('inverter_height_m','reserve_per_pole_m','bridge_gap_m'):add('Cable routing',('routing_settings',key))
    for key in data.get('cable_calc_params',{}):add('Cable sizing defaults',('cable_calc_params',key))
    for block in data.get('blocks',{}):
        for key in ('mppt_count','max_strings_per_mppt'):add('Inverter '+block,('blocks',block,key))
        add('Inverter '+block,('equipment_links',block),'Inverter equipment row (1-based)','row',optional=True)
        for key in ('x','y','terminal_height_m'):
            if block in data.get('inverter_positions',{}):add('Inverter '+block,('inverter_positions',block,key),label(key)+(' (image pixels)' if key in ('x','y') else ''),optional=key=='terminal_height_m')
    for sid,members in data.get('strings',{}).items():
        if not members:continue
        for key in ('current_a','voltage_v','isc_a','section_mm2','ampacity_a','protection_a','linear_mass_kg_m','reserve_per_pole_m'):add('String '+sid,('cable_string_params',sid,key),optional=True)
        add('String '+sid,('cable_string_params',sid,'module_row'),'Module equipment row (1-based)','row',optional=True)
        add('String '+sid,('string_mppt_assignment',sid,'block'),'Connected inverter','text')
        add('String '+sid,('string_mppt_assignment',sid,'mppt'),'Connected MPPT','integer',optional=True)
        dc=data['electrical_design']['dc'].setdefault(sid,{})
        for key in ('section_mm2','fuse_a','isolator_a','spd'):add('String '+sid,('electrical_design','dc',sid,key),optional=True)
    for section in STANDARD_DC_SECTIONS:add('Cable linear masses',('cable_mass_by_section',f'{section:g}'),f'{section:g} mm² conductor (kg/m)',optional=True)
    for i,cable in enumerate(data.get('cable_inventory',[])):
        for key in ('name','length_m','linear_mass_kg_m','quantity'):add(f'Additional cable {i+1}',('cable_inventory',i,key),optional=key!='name')
    for i,obstacle in enumerate(data['model_settings'].get('shadow_obstacles',[])):
        add(f'Additional obstacle {i+1}',('model_settings','shadow_obstacles',i,'footprint_px'),'Footprint vertices (image pixels)','points')
        for key in ('height_mm','opacity'):add(f'Additional obstacle {i+1}',('model_settings','shadow_obstacles',i,key))
    for i,poly in enumerate(data['model_settings'].get('layout_exclusions',[])):add(f'Layout exclusion {i+1}',('model_settings','layout_exclusions',i),'Excluded vertices (image pixels)','points')
    add('Energy and storage',('energy_input_settings','ac_factor'))
    for key in ('nominal_kwh','charge_kw','discharge_kw','soc_min_pct','soc_max_pct','round_trip_efficiency'):add('Energy and storage',('energy_input_settings','bess',key))
    for key in ('existing_contract_kw','export_limit_kw','export_limit_status'):add('Grid connection',('grid_connection_settings',key),optional=key=='existing_contract_kw')
    for key in ECONOMIC_DEFAULTS:add('Economic evaluation',('economic_settings',key))
    for key in ('bess_count','ac_voltage_v','power_factor'):add('Electrical single-line — site',('electrical_design',key),optional=key!='bess_count')
    for block in data.get('blocks',{}):
        for key in ('length_m','section_mm2','breaker_a','spd','isolator'):add('AC feeder '+block,('electrical_design','ac',block,key),optional=True)
    for cabinet in ('1','2'):
        for key in ('cluster_1_to','cluster_2_to','section_mm2','fuse_a','isolator_a','length_m','spd'):add('Battery cabinet '+cabinet,('electrical_design','battery',cabinet,key),optional=True)
    for key in data['electrical_design']['grid']:add('Electrical single-line — grid',('electrical_design','grid',key),optional=True)
    weather=data.get('hourly_weather_profile') or {}
    profiles=weather.get('orientations',{}) if 'orientations' in weather else {'current':weather} if weather else {}
    for name,profile in profiles.items():
        prefix=('hourly_weather_profile','orientations',name,'query') if 'orientations' in weather else ('hourly_weather_profile','query')
        for key in ('latitude','longitude','tilt_deg','azimuth_deg_from_south'):add('Weather source '+name,prefix+(key,),optional=True)
    return result


# Home questionnaire policy:
# show engineering source inputs and assumptions; hide canvas state, duplicated editor
# controls and values that can be derived from module/inverter/equipment records.
_HOME_EXCLUDED_KEYS = {
    # Canvas/image-space internals
    'px_per_mm','scale_p1','scale_p2','pylon_img_pos','pylon_ref_img_pos',
    'x','y','x1','y1','x2','y2','points','footprint_px',

    # Shadow preview controls / obstacle editor values
    'solar_day','solar_month','solar_hour','solar_utc_offset',
    'pylon_height_mm','pylon_width_mm','pylon_opacity','height_mm','opacity',

    # Internal links / row selectors
    'module_row',
}

_HOME_EXCLUDED_PATH_PREFIXES = (
    ('model_settings','layout_exclusions'),
    ('model_settings','shadow_obstacles'),
    ('model_settings','weather_import_metadata'),
)

# These values are derivable from the selected module/inverter/equipment datasheets.
# Keep the actual Equipment sections; remove duplicate "default verification" inputs.
_HOME_DERIVED_ELECTRICAL_KEYS = {
    'module_voc_v','module_vmp_v','module_imp_a','module_isc_a',
    'voc_temp_coeff_pct','vmp_temp_coeff_pct',
    'inverter_max_dc_v','mppt_min_v','mppt_max_v',
    'mppt_max_current_a','mppt_max_isc_a','inverter_max_pv_kw',
    'mppt_count','max_strings_per_mppt',
}

# Per-string values are calculated from module/inverter data, string membership and
# routing, or are maintained by the dedicated string/electrical workflows.
_HOME_STRING_DERIVED_KEYS = {
    'current_a','voltage_v','isc_a','section_mm2','ampacity_a',
    'protection_a','linear_mass_kg_m','reserve_per_pole_m',
    'module_row','block','mppt','fuse_a','isolator_a','spd',
}

_HOME_REQUIRED_PATHS = {
    ('project_name',),
    ('model_settings','report_shadow_year'),
    ('model_settings','timezone'),
    ('model_settings','imputation'),
    ('model_settings','shadow_model'),
}

def questionnaire_required(field):
    return tuple(field.path) in _HOME_REQUIRED_PATHS

def questionnaire_fields(data):
    """Return useful engineering inputs for the Home questionnaire.

    The form intentionally keeps source data and calculation assumptions (equipment
    datasheets, BESS/grid/economic settings, routing assumptions, etc.) while hiding
    image coordinates, preview controls, per-string derived values and duplicated
    electrical defaults that can be obtained from the equipment records.
    """
    result=[]
    for field in fields(data):
        path=tuple(field.path)
        key=path[-1] if path else None

        if key in _HOME_EXCLUDED_KEYS:
            continue
        if any(path[:len(prefix)] == prefix for prefix in _HOME_EXCLUDED_PATH_PREFIXES):
            continue

        # Keep only the useful physical values from installation/routing geometry.
        if field.section.startswith('Installation zone '):
            if key not in ('installation_height_m','z_mm'):
                continue
        if field.section.startswith('Routing area '):
            if key != 'installation_height_m':
                continue
        if field.section.startswith(('Additional obstacle ','Layout exclusion ')):
            continue

        # Keep String generation inputs, but no per-string derived/editing values.
        if field.section.startswith('String ') and field.section != 'String generation':
            continue

        # Equipment rows are the source of truth. Hide duplicate verification defaults.
        if field.section == 'Electrical verification' and key in _HOME_DERIVED_ELECTRICAL_KEYS:
            continue

        # Inverter MPPT counts are already part of inverter equipment data.
        if field.section.startswith('Inverter ') and key in ('mppt_count','max_strings_per_mppt'):
            continue

        # Weather source metadata is read from the imported file / project orientation.
        if field.section.startswith('Weather source '):
            continue
        if field.section.startswith('New weather file'):
            continue

        result.append(field)
    return result


def parse(field,raw):
    if field.kind=='boolean':return bool(raw)
    raw=str(raw).strip()
    if not raw:return None if field.optional else '' if field.kind in ('text','equipment') else (_ for _ in ()).throw(ValueError('a value is required'))
    if field.kind=='choice':
        if raw not in field.choices:raise ValueError('choose one of '+', '.join(field.choices))
        return raw
    if field.kind=='text':return raw
    if field.kind=='equipment':
        try:return float(raw.replace(',','.'))
        except ValueError:return raw
    if field.kind in ('point','points'):
        points=[]
        for part in raw.split(';'):
            pair=[float(x.strip()) for x in part.split(',')]
            if len(pair)!=2 or not all(math.isfinite(v) for v in pair):raise ValueError('use x,y ; x,y with finite coordinates')
            points.append(pair)
        if field.kind=='point' and len(points)!=1:raise ValueError('one x,y point is required')
        return points[0] if field.kind=='point' else points
    value=float(raw.replace(',','.'))
    if not math.isfinite(value):raise ValueError('a finite value is required')
    if field.kind in ('integer','row'):
        if value!=int(value):raise ValueError('a whole number is required')
        return int(value)-1 if field.kind=='row' else int(value)
    return value

def apply_values(data,descriptors,values):
    result=copy.deepcopy(data)
    for field,raw in zip(descriptors,values):
        try:put(result,field.path,parse(field,raw))
        except (ValueError,TypeError) as exc:raise ValueError(field.section+' — '+field.label+': '+str(exc)) from exc
    # Incomplete assignment remains explicitly unassigned, never a partial record.
    result['string_mppt_assignment']={sid:a for sid,a in result.get('string_mppt_assignment',{}).items() if a.get('block') and a.get('mppt')}
    result=validate_project(result)
    if not 1900<=result['model_settings'].get('report_shadow_year',2026)<=2100:raise ValueError('Report study year must be between 1900 and 2100.')
    from battery_dispatch import BatterySettings
    energy=result.get('energy_input_settings',{})
    BatterySettings(**energy['bess'],initial_soc_pct=energy['bess']['soc_min_pct']).validate()
    if not 0<float(energy['ac_factor'])<=1:raise ValueError('AC conversion factor must be greater than zero and at most one.')
    return result
