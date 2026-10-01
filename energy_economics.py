"""Value useful PV and grid exports without double-counting battery charging.

This is an economic evaluation of the existing energy dispatch. It does not
send commands to site equipment or optimise against hourly market forecasts.
"""
import csv
from math import isfinite

DEFAULTS = {'import_eur_kwh':0.25,'export_low_eur_kwh':0.07,
            'export_high_eur_kwh':0.08,'pv_capex_eur':250000.,
            'bess_capex_each_eur':50000.,'annual_maintenance_eur':0.,'discount_rate_pct':0.,
            'annual_degradation_pct':0.,'lifetime_years':15.,'replacement_year':0.,'replacement_cost_eur':0.}

def validate_settings(settings=None):
    values=dict(DEFAULTS)
    values.update(settings or {})
    values={key:float(values[key]) for key in DEFAULTS}
    if not all(isfinite(v) for v in values.values()):
        raise ValueError('Economic values must be finite numbers')
    if values['import_eur_kwh']<=0 or min(values.values())<0:
        raise ValueError('Purchase price must be positive; other values must be non-negative')
    if values['annual_degradation_pct']>=100 or values['lifetime_years']<1:raise ValueError('Invalid lifetime or degradation.')
    if values['export_low_eur_kwh']>values['export_high_eur_kwh']:
        raise ValueError('Minimum export price exceeds the maximum')
    return values

def evaluate_options(annuals, settings=None):
    settings=validate_settings(settings)
    if len(annuals)!=3:raise ValueError('All three energy balances (0 / 1 / 2 BESS) are required')
    results=[]
    for tariff in (settings['export_low_eur_kwh'],settings['export_high_eur_kwh']):
        previous=None
        for n,a in enumerate(annuals):
            useful=a['self_kwh'] if n==0 else a['useful_self_kwh']
            grid=a['grid_kwh']; export=a['export_kwh'];load=a['load_kwh']
            if min(useful,grid,export,load)<0 or abs(load-useful-grid)>0.01:
                raise ValueError('The load energy balance is inconsistent')
            useful_pv=useful-a.get('initial_storage_load_kwh',0)-a.get('auxiliary_kwh',0)
            avoided=useful_pv*settings['import_eur_kwh']
            revenue=export*tariff
            purchases=grid*settings['import_eur_kwh']
            benefit=avoided+revenue-n*settings['annual_maintenance_eur']
            capex=settings['pv_capex_eur']+n*settings['bess_capex_each_eur']
            delta=None if previous is None else benefit-previous['total_benefit_eur']
            lost=None if previous is None else previous['export_revenue_eur']-revenue
            results.append({'bess_count':n,'export_eur_kwh':tariff,'useful_pv_kwh':useful_pv,
                'export_kwh':export,'grid_kwh':grid,'avoided_purchases_eur':avoided,
                'export_revenue_eur':revenue,'grid_purchases_eur':purchases,
                'net_energy_outlay_eur':purchases-revenue,'total_benefit_eur':benefit,
                'capex_eur':capex,'simple_payback_years':capex/benefit if benefit>0 else None,
                'incremental_benefit_eur':delta,'foregone_export_eur':lost,
                'incremental_payback_years':settings['bess_capex_each_eur']/delta if delta is not None and delta>0 else None})
            rate=settings['discount_rate_pct']/100
            degradation=settings['annual_degradation_pct']/100
            baseline_benefit=annuals[0]['self_kwh']*settings['import_eur_kwh']+annuals[0]['export_kwh']*tariff
            gross_benefit=avoided+revenue
            flows=[]
            for year in range(1,int(settings['lifetime_years'])+1):
                gross=(gross_benefit if n==0 else baseline_benefit+(gross_benefit-baseline_benefit)*(1-degradation)**(year-1))
                replacement=settings['replacement_cost_eur']*n if year==settings['replacement_year'] else 0
                flows.append(gross-n*settings['annual_maintenance_eur']-replacement)
            results[-1]['net_present_value_eur']=-capex+sum(flow/(1+rate)**year for year,flow in enumerate(flows,1))
            results[-1]['discounted_payback_years']=None
            cumulative=-capex
            for year,flow in enumerate(flows,1):
                previous_total=cumulative;cumulative+=flow/(1+rate)**year
                if cumulative>=0 and previous_total<0:results[-1]['discounted_payback_years']=year;break
            previous=results[-1]
    return results

def write_economic_csv(path, rows):
    if not rows:raise ValueError('No economic results available')
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]))
        writer.writeheader();writer.writerows(rows)

def storage_margin_per_charge_kwh(settings, round_trip_efficiency):
    """Gross incremental value per kWh charged and later used by the load."""
    s=validate_settings(settings)
    eta=float(round_trip_efficiency)
    if not 0<eta<=1:raise ValueError('Invalid round-trip efficiency')
    return {p:eta*s['import_eur_kwh']-p for p in
            (s['export_low_eur_kwh'],s['export_high_eur_kwh'])}


def covers_full_year(profile):
    """A complete anniversary-to-anniversary load period, including leap years."""
    import datetime as dt
    try:
        start=dt.date.fromisoformat(profile['start_date']);end=dt.date.fromisoformat(profile['end_date'])
        try:anniversary=start.replace(year=start.year+1)
        except ValueError:anniversary=start.replace(year=start.year+1,day=28)
        if profile.get('timestamps'):
            from self_consumption import timestamps
            stamps=timestamps(profile)
            return end+dt.timedelta(days=1)==anniversary and len(stamps) in (8760,8784)
        return end+dt.timedelta(days=1)==anniversary and len(profile['hourly_kwh'])==(anniversary-start).days*24
    except (KeyError,TypeError,ValueError):return False
