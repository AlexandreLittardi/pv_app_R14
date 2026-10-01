"""Dispatch orario AC del BESS: solo surplus FV, senza ricarica da rete."""
from __future__ import annotations

import csv
from dataclasses import dataclass, asdict, replace
from math import isfinite, sqrt

from self_consumption import balance, timestamps


@dataclass
class BatterySettings:
    model: str = 'Deye MC-L522-2H3 (provisional model)'
    nominal_kwh: float = 522.496
    charge_kw: float = 250.0
    discharge_kw: float = 150.0
    soc_min_pct: float = 10.0
    soc_max_pct: float = 90.0
    initial_soc_pct: float = 10.0
    round_trip_efficiency: float = 0.90
    auxiliary_kw: float = 0.0
    annual_degradation_pct: float = 0.0

    def validate(self):
        nums=(self.nominal_kwh,self.charge_kw,self.discharge_kw,self.soc_min_pct,
              self.soc_max_pct,self.initial_soc_pct,self.round_trip_efficiency,self.auxiliary_kw,self.annual_degradation_pct)
        if not all(isfinite(v) for v in nums):
            raise ValueError('BESS settings must be finite numbers')
        if self.auxiliary_kw<0 or not 0<=self.annual_degradation_pct<100:raise ValueError('Invalid auxiliaries or degradation.')
        if self.nominal_kwh<=0 or self.charge_kw<=0 or self.discharge_kw<=0:
            raise ValueError('BESS capacity and power limits must be positive')
        if not (0<=self.soc_min_pct<self.soc_max_pct<=100):
            raise ValueError('Invalid SOC limits')
        if not self.soc_min_pct<=self.initial_soc_pct<=self.soc_max_pct:
            raise ValueError('Initial SOC is outside the configured limits')
        if not 0<self.round_trip_efficiency<=1:
            raise ValueError('Round-trip efficiency must be greater than zero and at most one')


def simulate_bess(profile, pv_kwh, settings: BatterySettings, export_limit_kw=None):
    """Restituisce i due scenari con bilanci energetici coerenti.

    Autoconsumo utile = FV diretto ai carichi + energia scaricata ai carichi.
    FV trattenuto nel sito = FV diretto + energia AC inviata al BESS.
    La differenza contiene perdite e variazione di SOC; non sommarli.
    """
    settings.validate()
    base=balance(profile,pv_kwh,export_limit_kw)
    stamps=timestamps(profile)
    low=settings.nominal_kwh*settings.soc_min_pct/100
    high=settings.nominal_kwh*settings.soc_max_pct/100
    stored=settings.nominal_kwh*settings.initial_soc_pct/100
    initial_stored=stored
    initial_credit=stored-low
    initial_storage_load=0.
    eta=sqrt(settings.round_trip_efficiency)
    monthly={}
    rows=[]
    for i,(stamp,load,pv) in enumerate(zip(stamps,profile['hourly_kwh'],pv_kwh)):
        load+=settings.auxiliary_kw
        capacity=settings.nominal_kwh*(1-settings.annual_degradation_pct/100)**(i/8766.)
        low=capacity*settings.soc_min_pct/100;high=capacity*settings.soc_max_pct/100
        stored=min(stored,high)
        direct=min(load,pv)
        surplus=max(0,pv-direct)
        deficit=max(0,load-direct)
        charge=min(surplus,settings.charge_kw,(high-stored)/eta)
        charge=max(0,charge)
        stored+=charge*eta
        discharge=min(deficit,settings.discharge_kw,(stored-low)*eta)
        discharge=max(0,discharge)
        from_initial=min(initial_credit,discharge/eta)
        initial_storage_load+=from_initial*eta;initial_credit-=from_initial
        stored-=discharge/eta
        stored=max(low,min(high,stored))
        grid=deficit-discharge
        available_export=surplus-charge
        exported=available_export if export_limit_kw is None else min(available_export,export_limit_kw)
        curtailed=available_export-exported
        bucket=monthly.setdefault(stamp.strftime('%Y-%m'),dict.fromkeys(
            ('load_kwh','pv_kwh','direct_kwh','charge_ac_kwh','discharge_ac_kwh',
             'useful_self_kwh','onsite_pv_kwh','grid_kwh','export_kwh','curtailed_kwh'),0.0))
        for key,value in (('load_kwh',load),('pv_kwh',pv),('direct_kwh',direct),
                          ('charge_ac_kwh',charge),('discharge_ac_kwh',discharge),
                          ('useful_self_kwh',direct+discharge),('onsite_pv_kwh',direct+charge),
                          ('grid_kwh',grid),('export_kwh',exported),('curtailed_kwh',curtailed)):
            bucket[key]+=value
        rows.append((stamp.isoformat(' '),load,pv,direct,charge,discharge,
                     direct+discharge,grid,exported,stored/settings.nominal_kwh*100,
                     stored,profile['hourly_kwh'][i]))
    annual={key:sum(m[key] for m in monthly.values()) for key in next(iter(monthly.values()))}
    annual['initial_storage_load_kwh']=initial_storage_load
    annual['auxiliary_kwh']=settings.auxiliary_kw*len(stamps)
    annual['battery_losses_kwh']=annual['charge_ac_kwh']-annual['discharge_ac_kwh']-(stored-initial_stored)
    annual['soc_initial_pct']=settings.initial_soc_pct
    annual['soc_final_pct']=stored/settings.nominal_kwh*100
    annual['autoconsumption_pct']=100*annual['onsite_pv_kwh']/annual['pv_kwh'] if annual['pv_kwh'] else 0.0
    annual['useful_self_pct']=100*annual['useful_self_kwh']/annual['pv_kwh'] if annual['pv_kwh'] else 0.0
    annual['self_sufficiency_pct']=100*annual['useful_self_kwh']/annual['load_kwh'] if annual['load_kwh'] else 0.0
    annual['extra_useful_kwh']=annual['useful_self_kwh']-base['annual']['self_kwh']
    annual['grid_saved_kwh']=base['annual']['grid_kwh']-annual['grid_kwh']
    # Meter balances at AC point of coupling, for every simulation.
    assert abs(annual['load_kwh']-annual['useful_self_kwh']-annual['grid_kwh'])<1e-5
    assert abs(annual['pv_kwh']-annual['onsite_pv_kwh']-annual['export_kwh']-annual['curtailed_kwh'])<1e-5
    return {'without_bess':{'annual':base['annual'],'monthly':base['monthly']},
            'with_bess':{'annual':annual,'monthly':monthly},
            'battery_settings':asdict(settings),'rows':rows}


def simulate_three_options(profile, pv_kwh, one_cabinet: BatterySettings, export_limit_kw=None):
    """Un solo FV e carico per le tre configurazioni simultanee.

    Due armadi identici con SOC iniziale identico condividono il limite AC
    di impianto impostato: si raddoppia solo la capacita' energetica.
    La ripartizione fra i due armadi e' simmetrica tramite EMS.
    """
    one=simulate_bess(profile,pv_kwh,one_cabinet,export_limit_kw)
    two_settings=replace(one_cabinet,
                         model=f'2 × {one_cabinet.model}',
                         nominal_kwh=2*one_cabinet.nominal_kwh,
                         charge_kw=one_cabinet.charge_kw,
                         discharge_kw=one_cabinet.discharge_kw,
                         auxiliary_kw=2*one_cabinet.auxiliary_kw)
    two=simulate_bess(profile,pv_kwh,two_settings,export_limit_kw)
    return {'export_limit_kw':export_limit_kw,'without_bess':one['without_bess'],
            'one_bess':{'annual':one['with_bess']['annual'],
                        'monthly':one['with_bess']['monthly'],
                        'settings':one['battery_settings'],'rows':one['rows']},
            'two_bess':{'annual':two['with_bess']['annual'],
                        'monthly':two['with_bess']['monthly'],
                        'settings':two['battery_settings'],'rows':two['rows']}}


def write_comparison_csv(path, comparison, imputed_indices=()):
    """Confronto a 3 opzioni sullo stesso timestamp (una riga per ora)."""
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        writer=csv.writer(f)
        writer.writerow(['local_datetime','load_kwh','pv_ac_kwh','direct_pv_kwh',
                         'grid_import_0_bess_kwh','grid_export_0_bess_kwh',
                         'charge_1_bess_ac_kwh','discharge_1_bess_ac_kwh',
                         'load_served_1_bess_kwh','grid_import_1_bess_kwh',
                         'grid_export_1_bess_kwh','soc_1_bess_pct',
                         'charge_2_bess_ac_kwh','discharge_2_bess_ac_kwh',
                         'load_served_2_bess_kwh','grid_import_2_bess_kwh',
                         'grid_export_2_bess_kwh','soc_2_bess_pct','estimated_load',
                         'curtailed_pv_0_bess_kwh','curtailed_pv_1_bess_kwh','curtailed_pv_2_bess_kwh','load_with_1_bess_aux_kwh','load_with_2_bess_aux_kwh'])
        imputed=set(imputed_indices)
        one=comparison['one_bess']['rows']
        two=comparison['two_bess']['rows']
        if len(one)!=len(two):
            raise ValueError('The two BESS profiles have different durations')
        for i,(r1,r2) in enumerate(zip(one,two)):
            stamp,_,pv,_,*_=r1
            load=r1[11] if len(r1)>11 else r1[1]
            direct=min(load,pv)
            if r2[0]!=stamp or abs((r2[11] if len(r2)>11 else r2[1])-load)>1e-8 or abs(r2[2]-pv)>1e-8:
                raise ValueError('BESS hourly profiles do not match')
            limit=comparison.get("export_limit_kw")
            export0=pv-direct if limit is None else min(pv-direct,limit)
            writer.writerow((stamp,load,pv,direct,load-direct,export0,
                             r1[4],r1[5],r1[6],r1[7],r1[8],r1[9],
                             r2[4],r2[5],r2[6],r2[7],r2[8],r2[9],i in imputed,
                             pv-direct-export0,pv-r1[3]-r1[4]-r1[8],pv-r2[3]-r2[4]-r2[8],r1[1],r2[1]))
