"""User-facing, code-audited guide. Equations are Matplotlib mathtext strings."""

from user_guide import WORKFLOWS

# Each group contains a concise explanation and display math. All variables are
# named in the accompanying prose; no formula is presented as a compliance check.
FORMULAS = [
    ('Symbols and scope', 'Angles are in degrees unless specified. Latitude phi is north-positive, longitude lambda east-positive, local hour h uses the supplied UTC offset u. G is W/m², P is W, E is Wh. Calculations are estimates, not equipment certification.', [
        (r'\gamma=\frac{2\pi}{N_y}\left(n-1+\frac{h-12}{24}\right)', 'Fractional year: Ny is 365 or 366 for the calculation year; n is the day number. The undated preview uses 2024.'),
    ]),
    ('Solar position', 'Solar elevation is corrected for refraction, while azimuth uses geometric elevation. Shadow preview uses representative year 2024 because its controls give only day/month; dated simulations and annual Energy/BESS use the real year. The annual routine derives the UTC offset for each hourly Europe/Rome timestamp.', [
        (r'E_t=229.18(0.000075+0.001868\cos\gamma-0.032077\sin\gamma-0.014615\cos2\gamma-0.040849\sin2\gamma)', 'Equation of time in minutes (Spencer/NOAA approximation).'),
        (r'\delta=0.006918-0.399912\cos\gamma+0.070257\sin\gamma-0.006758\cos2\gamma+0.000907\sin2\gamma-0.002697\cos3\gamma+0.001480\sin3\gamma', 'Solar declination in radians.'),
        (r'\omega=\frac{60h+E_t+4\lambda-60u}{4}-180', 'Hour angle: negative in the morning, positive in the afternoon.'),
        (r'\alpha_{geo}=\arcsin(\sin\phi\sin\delta+\cos\phi\cos\delta\cos\omega)', 'Geometric solar elevation; trigonometric arguments are converted to radians.'),
        (r'\alpha=\alpha_{geo}+\frac{1.02}{60\tan(\alpha_{geo}+10.3/(\alpha_{geo}+5.11))}', 'Sæmundsson refraction for geometric elevation greater than -0.85°. The tangent argument is converted to radians.'),
        (r'\cos A=\frac{\sin\delta-\sin\alpha_{geo}\sin\phi}{\cos\alpha_{geo}\cos\phi}', 'Solar azimuth from north: arccos in the morning, 360° minus arccos in the afternoon.'),
    ]),
    ('Irradiance and module power', 'A simplified clear-sky scenario is used for the shadow study. The Energy/BESS annual simulation can instead use imported historical plane-of-array irradiance AND hourly ambient temperature for a single module orientation. The 20°C ambient assumption and constant 0.20 albedo apply to the clear-sky model only.', [
        (r'm_a=\frac{1}{\sin\alpha},\quad G_{DNI}=1367(0.7)^{m_a^{0.675}}', 'Clear-sky direct normal irradiance; set to zero at solar elevation at or below 0.5°.'),
        (r'c_i=\max(0,\min(1,\sin\alpha\cos\beta+\cos\alpha\sin\beta\cos(A-\gamma_p)))', 'Incidence factor for module tilt beta and module azimuth gamma_p.'),
        (r'G_{POA}=G_{DNI}c_i+0.12G_{DNI}\sin\alpha\frac{1+\cos\beta}{2}+1.12G_{DNI}\sin\alpha\,0.20\frac{1-\cos\beta}{2}', 'Direct + simplified sky diffuse + ground reflection, with nonnegative sine of solar elevation.'),
        (r'G_{eff}=G_{POA}(1-f_s),\quad T_c=T_{ambient}+(T_{NOCT}-20)\frac{G_{eff}}{800}', 'Effective irradiance after fractional shading. T_ambient is 20°C for the clear-sky calculation; it comes from the hourly weather profile when supplied.'),
        (r'P=P_{STC}\frac{G_{eff}}{1000}\max\left(0,1+\frac{\mu_P}{100}(T_c-25)\right)', 'Linear power estimate (muP in %/°C), not an I-V or bypass-diode calculation.'),
    ]),
    ('Time, shading and layout', 'A shadow footprint is a square at the configured obstacle position. Its projection and polygon intersection are computed separately for each roof height. Real roof clearances and structural constraints are outside the grid model.', [
        (r'E=\sum_{k=1}^{M}P(t_{k,mid})\,\Delta t_k,\quad E_{loss}=\max(0,E_{unshaded}-E_{shaded})', 'Midpoint integration; E is Wh for P in watts and time in hours.'),
        (r'E_{string}=\sum_jE_j,\quad r_{loss}=100\frac{\sum_jE_{loss,j}}{\sum_jE_{unshaded,j}}', 'Aggregated module energies and relative estimated string losses. This is not an electrical current-limited string model.'),
        (r'Spread=\max_j(r_{loss,j})-\min_j(r_{loss,j})', 'Difference between the most and least affected modules of one string; a mismatch indicator only.'),
        (r'A=\frac{1}{2}\left|\sum_{i=1}^{p}(x_i y_{i+1}-x_{i+1}y_i)\right|', 'Shoelace area for a simple polygon; its intersection with a panel is obtained through polygon clipping.'),
        (r'd=\frac{H_{obstacle}-H_{roof}}{\tan\alpha},\quad f_s=\min\left(1,\frac{A_{intersection}}{A_{panel}}o\right)', 'Shadow length at positive elevation and positive height difference; o is obstacle opacity in [0,1].'),
        (r'n_{col}=\left\lfloor\frac{W}{w}\right\rfloor,\quad n_{row}=\left\lfloor\frac{H}{h}\right\rfloor', 'Grid in local coordinates of the inverse-rotated zone bounds; alignment uses residual width/height. The lattice rotates rigidly about the zone centre; incomplete boundary cells are discarded.'),
        (r'o_x\in\{0,(W-n_{col}w)/2,W-n_{col}w\},\quad o_y\in\{0,(H-n_{row}h)/2,H-n_{row}h\}', 'Left/centre/right and top/centre/bottom alignment of the residual clearance.'),
        (r'x\prime=c_x+(x-c_x)\cos\theta-(y-c_y)\sin\theta', 'Rotation of x around the installation zone centre.'),
        (r'y\prime=c_y+(x-c_x)\sin\theta+(y-c_y)\cos\theta', 'Rotation of y. The convex hull and polygon clipping use Andrew and Sutherland–Hodgman algorithms.'),
    ]),
    ('Strings, routing and voltage drop', 'N modules in series multiply voltage but retain module current. Parallel MPPT strings add currents; unlike a loose voltage interval, differing string voltages need an explicit mismatch check. Routes A and B are separate physical conductor paths.', [
        (r'P_{string}=\frac{NP_{STC}}{1000},\quad V_{oc,string}=NV_{oc},\quad V_{mpp,string}=NV_{mpp}', 'kWp and voltages at STC; Isc and Imp each equal the module current for a series string.'),
        (r'I_{MPPT}=\sum_{j=1}^{k}I_{string,j},\quad P_{inv,DC}=\sum_{s\in inv}P_{string,s}', 'Parallel current and assigned DC peak power. Check maximum voltage at cold temperature separately.'),
        (r'L_{loop}=L_A+L_B,\quad \Delta V=\frac{I\rho L_{loop}}{S}', 'Two conductor lengths including modeled vertical drop and reserves; rho is Ω·mm²/m, S is mm².'),
        (r'L_{orthogonal}=|x_2-x_1|+|y_2-y_1|', 'Fallback Manhattan route between two points without a drawn path; the drawn cable network uses Dijkstra shortest-path search.'),
        (r'V_{oc,cold}=NV_{oc,STC}\left[1+\frac{\mu_{Voc}}{100}(T_{min}-25)\right]', 'Cold-voltage estimate where the module voltage temperature coefficient and site design temperature are supplied; otherwise the check remains open.'),
        (r'S_{min}=\frac{I\rho(L_A+L_B)}{U\epsilon_{target}/100},\quad\epsilon_{actual}=100\frac{I\rho(L_A+L_B)}{SU}', 'Equivalent to 2L only if LA=LB=L. Sizing is voltage-drop-only; no ampacity or fault study.'),
        (r'I_{AC,nom}=\frac{1000S_{AC,kVA}}{\sqrt{3}U_{LL}}', 'Estimated three-phase line current from apparent inverter rating and entered line voltage; this is not a breaker selection.'),
    ]),
]

from energy_reference import ENERGY_FORMULAS
FORMULAS.extend(ENERGY_FORMULAS)

FORMULAS.append(('Installation routing', 'Installation elevations are independent of Shadow. Orthogonal height steps are evaluated at every crossed surface boundary.', [
    (r'L_{pole}=\sum_i\sqrt{\Delta x_i^2+\Delta y_i^2}+\sum_j|\Delta z_j|+L_{reserve}', 'Distances are in metres. Gaps up to the configured bridge threshold retain the upstream elevation; longer unsupported spans use ground level.'),
    (r'L_{loop}=L_A+L_B', 'A and B start at opposite ends of the string. Inter-module wiring and AC wiring are excluded.'),
]))
