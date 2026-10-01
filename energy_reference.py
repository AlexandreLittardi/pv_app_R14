"""Engineering documentation of the Energy / BESS implementation, in English."""
ENERGY_FORMULAS = [
 ('Energy / BESS: inputs',
  'Source: self_consumption.py, production_from_program(). Index h denotes a one-hour local-time slot (Delta t = 1 h); energies are kWh and powers kW. Consumption is imported as 24 columns per local day. Missing load values are estimated from up to seven preceding days at the same clock hour and flagged. PV is evaluated at the hour midpoint, using clear-sky irradiance or imported historical plane-of-array irradiance and ambient temperature. Historical weather currently supports one roof orientation. The 24-slot convention approximates daylight-saving transition days.', [
   (r'E_{PV,h}=\min\left(P_{AC,cap},f_{AC}\frac{\sum_iP_{i,h}}{1000}\right)\Delta t', 'P_i,h is the shaded module power in W, as defined in the module model. f_AC is the additional conversion/loss factor (default 0.90). P_AC,cap is the aggregate configured inverter cap. The code uses the numerical kVA ratings for this kW cap, assuming unity power factor; confirm active-power ratings before relying on clipping estimates.'),
   (r'\widehat E_{load,h}=\frac{1}{|D_h|}\sum_{d\in D_h}E_{load,h-24d}', 'D_h contains available preceding days d = 1,...,7. An error is raised if no prior value exists. Estimated entries must be reviewed separately from measured consumption.'),
 ]),
 ('Energy / BESS: dispatch',
  'Source: battery_dispatch.py, simulate_bess() and simulate_three_options(). The same PV and load inputs are used for PV only, one cabinet and two cabinets. Default cabinet capacity is 522.496 kWh. Two cabinets double capacity, while plant charge/discharge caps remain 250/150 kW. These are study settings. There is no grid charging, battery export or tariff-based scheduling. SOC starts at its configured minimum; the end SOC is not forced back to the start.', [
   (r'E_{direct,h}=\min(E_{PV,h},E_{load,h})', 'PV first supplies the load directly.'),
   (r'E_{surplus,h}=E_{PV,h}-E_{direct,h},\quad E_{deficit,h}=E_{load,h}-E_{direct,h}', 'Only surplus PV can charge storage; only the residual load can receive a discharge.'),
   (r'C_n=nC_1,\quad Q_{min}=C_n s_{min},\quad Q_{max}=C_n s_{max}', 'For n = 1 or 2 cabinets, Q is stored energy (kWh) and s is a fractional SOC. Default s_min = 0.10 and s_max = 0.90. PV-only has zero charge and discharge.'),
   (r'\eta_c=\eta_d=\sqrt{\eta_{rt}},\quad \eta_{rt}=0.90', 'Charge and discharge efficiencies are split equally; the round-trip efficiency is configurable.'),
   (r'E_{charge,h}=\min\left(E_{surplus,h},P_c\Delta t,\frac{Q_{max}-Q_h}{\eta_c}\right)', 'AC energy sent to the battery, constrained by surplus, charge power and available capacity.'),
   (r'Q_h^+=Q_h+\eta_cE_{charge,h}', 'Stored energy after the charge step.'),
   (r'E_{discharge,h}=\min\left(E_{deficit,h},P_d\Delta t,(Q_h^+-Q_{min})\eta_d\right)', 'AC energy delivered by the battery to the load. Surplus and deficit cannot both be positive in the same hourly slot.'),
   (r'Q_{h+1}=Q_h^+-\frac{E_{discharge,h}}{\eta_d},\quad SOC_{h+1}=100\frac{Q_{h+1}}{C_n}', 'SOC shown on the hourly chart is the end-of-hour state. The code clips numerical round-off to the SOC limits.'),
 ]),
 ('Energy / BESS: grid',
  'Source: self_consumption.py, balance(), and battery_dispatch.py. The requested export cap is 300 kW and is not recorded as approved. The existing 507 kW contract is stored separately; it does not replace the export cap or constrain grid imports in this dispatch model.', [
   (r'E_{grid,h}=E_{deficit,h}-E_{discharge,h}', 'Grid purchases cover the remaining load, including hours when PV output is zero.'),
   (r'E_{export,h}=\min(E_{surplus,h}-E_{charge,h},P_{export}\Delta t)', 'Remaining PV surplus is exported up to the configured export cap.'),
   (r'E_{curtailed,h}=E_{surplus,h}-E_{charge,h}-E_{export,h}', 'Surplus that cannot be consumed, stored or exported is counted as curtailed PV.'),
   (r'E_{load,h}=E_{direct,h}+E_{discharge,h}+E_{grid,h}', 'Load-side energy conservation, checked for annual totals.'),
   (r'E_{PV,h}=E_{direct,h}+E_{charge,h}+E_{export,h}+E_{curtailed,h}', 'PV-side energy conservation. PV before grid curtailment is the reported production quantity.'),
 ]),
 ('Energy / BESS: metrics',
  'Source: battery_dispatch.py annual aggregation; mixins/hourly_chart_ui.py displays the results. Monthly and annual values are sums of the hourly rows. The annual chart shows monthly totals in MWh. The hourly chart shows PV/load curves, stacked load sources and battery SOC. Grey bands mark zero PV production. Percentages use the totals below, not the average of hourly percentages.', [
   (r'E_{useful}=\sum_h(E_{direct,h}+E_{discharge,h})', 'Useful PV supplied to the load, directly or through storage.'),
   (r'E_{onsite}=\sum_h(E_{direct,h}+E_{charge,h})', 'PV retained on site includes energy entering storage; it is not the same quantity as useful load served.'),
   (r'L_{battery}=\sum_h(E_{charge,h}-E_{discharge,h})-(Q_{end}-Q_{start})', 'Battery losses deduct the change in stored energy, avoiding a false loss attribution to the final SOC.'),
   (r'SelfSufficiency=100\frac{E_{useful}}{\sum_h E_{load,h}}', 'Percentage of refrigerator consumption served by PV and BESS. The displayed value is zero if the load denominator is zero.'),
   (r'PVRetained=100\frac{E_{onsite}}{\sum_h E_{PV,h}},\quad UsefulPV=100\frac{E_{useful}}{\sum_h E_{PV,h}}', 'PV kept on site and useful self-consumption as shares of production. Zero production gives zero displayed ratios. Neither rate should be interpreted as storage efficiency.'),
 ]),
 ('Energy / BESS: costs',
  'Source: energy_economics.py, evaluate_options(). All energies below are annual totals. p_b and p_s are purchase and export prices in EUR/kWh. The defaults are p_b = 0.25 (0.32 can also be selected), and two export-price cases p_s = 0.07 and 0.08. PV investment is EUR 250,000; each cabinet adds EUR 50,000. Fixed charges, taxes, maintenance, financing, degradation and replacement are not included.', [
   (r'C_0=p_bE_{load},\quad C_{net,n}=p_bE_{grid,n}-p_sE_{export,n}', 'Baseline purchase cost without PV, and annual net electricity cost for scenario n.'),
   (r'B_n=C_0-C_{net,n}=p_bE_{useful,n}+p_sE_{export,n}', 'Annual benefit includes both avoided purchases and export revenue.'),
   (r'K_n=K_{PV}+nK_{BESS},\quad T_n=\frac{K_n}{B_n}', 'Simple whole-project payback in years, only when B_n > 0; otherwise no positive payback is displayed.'),
   (r'\Delta B_n=B_n-B_{n-1},\quad T_{extra,n}=\frac{K_{BESS}}{\Delta B_n}', 'Incremental payback compares one cabinet with PV-only, then two cabinets with one. It is displayed only if the incremental benefit is positive; foregone export revenue is already deducted.'),
 ]),
 ('Energy / BESS: EMS',
  'Source: energy_economics.py, storage_margin_per_charge_kwh(). This window evaluates the fixed self-consumption dispatch. It sends no control commands and does not optimize time-varying prices, grid arbitrage or future load forecasts. Recalculate energy after changing source profiles, layout or storage. Updating prices alone recalculates costs from the existing hourly energy results.', [
   (r'm_{charge}=\eta_{rt}p_b-p_s', 'Gross incremental value of one PV kWh charged and later delivered to the load instead of exported now. Assumes available future demand and SOC headroom; excludes ageing and auxiliary consumption.'),
   (r'p_{s,break}=\eta_{rt}p_b', 'Export price at which that simplified gross storage margin is zero. This indicator does not alter the current dispatch algorithm.'),
 ]),
]
