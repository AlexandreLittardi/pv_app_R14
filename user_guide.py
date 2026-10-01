"""Expanded desktop workflow adapted from the supplied earlier tutorial."""
WORKFLOWS = [
('Home', '''START A PROJECT
Open a JSON project from Project > Open JSON project, or load a roof image for a new project. Recent projects are local shortcuts; they do not replace saved files. Save the JSON alongside its roof image so it remains portable.

CONFIGURE BEFORE CALCULATING
The toolbar uses compact 12 px icons with labels. Each How it works section includes its toolbar icons and commands. There is no More menu or secondary toolbar-fields dialog. Home > Configuration groups equipment sheets, module dimensions and orientation, electrical checks, installation elevations, grid connection and energy settings. Enter manufacturer values from the actual equipment sheets. Review every prefilled value: it is an assumption, not a certification.

RECOMMENDED ORDER
Calibrate the plan; draw installation zones; set module dimensions; generate the layout; assign inverter blocks; build strings; assign MPPTs; place inverters; define cable routes and elevations; assess shading; import consumption and weather; compare storage scenarios.

DELIVERABLE
Engineering report PDF exports project inputs, missing data, plan figures, string/MPPT tables, cable lengths, energy results when current, formulas and limitations. Vector installation, string and cable-path overviews and a numbered detail atlas accompany it. Detail sheets retain 8 pt selectable module identifiers; overlapping pages repeat the same IDs. Matching SVG and PDF sheets, an editable LaTeX source and a machine-readable input snapshot are also exported. Review the report before issuing it.'''),
('Installation area', '''1. CALIBRATE
Load a plan with a known distance. Draw scale reference between its exact endpoints, then enter the distance in millimetres. Check a second known dimension; a photograph with perspective distortion cannot be treated as a survey.

2. DRAW ZONES
Use Zones > Draw rectangular zone and drag opposite corners. Choose the zone in the list. Drag its interior to move it or its corner handles to resize it. Settings accepts exact coordinates, dimensions and alignment. Existing project layout angles remain readable. Pan using the right mouse button when not finishing a drawing.

3. ROUTING POLYGONS
Cable routing area > Draw adds vertices by left-click. Right-click finishes; Escape cancels. Choose a polygon in the list, then Transform selected area: drag a vertex to reshape it or the interior to move it. This is a transformation tool; it does not select panels underneath.

4. ELEVATIONS
Installation heights accepts metres above a common datum for every rectangular zone and routing polygon. Enter the inverter terminal height too. These elevations are used by Cabling only. Shadow roof heights remain separate. Unknown elevations remain unknown and block affected cable calculations.

5. DIMENSIONS
Choose aligned, horizontal or vertical dimension. Drag the two endpoints. The dimension has extension lines and arrowheads. Drag its label to position the dimension line; Ctrl-right-click the label to delete it. Values are millimetres. Horizontal/vertical dimensions show the corresponding projection, not the diagonal.'''),
('Layout and blocks', '''MODULE CONFIGURATION
Panel sets width/height in millimetres and electrical tilt/azimuth in degrees. The zone rotation is an image-plane layout angle; it is different from module tilt or compass azimuth.

GENERATE
Generate layout builds an edge-to-edge lattice, rotated as one rigid grid about the zone centre. Only complete modules inside the rectangle are retained. Angled boundaries leave unavoidable triangular offcuts; internal panel spacing is not artificially enlarged. Configuration supplies module gaps, edge clearances and exclusion polygons for reserved corridors.

EDIT
Changing zone dimensions or rotation changes the grid. Generate layout again and review strings and MPPT assignments afterwards. Ctrl-click adds/assigns panels and Ctrl-right-click removes them in the layout editor. Panel identifiers remain stable; Renumber panels is an explicit action. Changed module geometry disconnects affected strings for review.

BLOCKS AND INVERTERS
Create one named block per inverter. Choose the active block and use Paint block only when assigning existing modules, to avoid creating stray modules. Enter inverter equipment in Home > Configuration, then select the block and place its inverter on the plan. A placed inverter stores a copy of the chosen equipment row; later sheet edits do not automatically replace that copy.'''),
('Stringing', '''CREATE ORDERED STRINGS
Create a string, choose it in the list and add the intended panels in electrical order. Automatic stringing uses the configured minimum/maximum lengths and the selected grouping. Inspect the result rather than assuming the geometric order is suitable for installation.

EDIT AND CHECK
The panel list shows the actual connection order. Move panels up/down or remove an incorrect entry. String start badges identify the first modules on the plan. Avoid duplicate membership, disconnected groups and strings spanning different inverter blocks.

ENGINEERING CHECKS
Verify string Voc at the minimum design temperature and operating Vmp against the selected inverter range, using manufacturer coefficients and site temperatures. The software's STC values alone do not establish cold-weather compliance. Shading totals do not model current-limited strings or bypass diodes.

AFTER LAYOUT CHANGES
Regenerate or review strings, MPPTs and cable routes. Both end modules matter: cable conductor A starts at the first module, conductor B at the last.'''),
('MPPT assignment', '''CONFIGURE EACH INVERTER
Set the number of MPPTs and allowed string inputs for each block from its datasheet. Do not infer input current or voltage limits solely from the inverter power rating.

ASSIGN
Select a string and assign it to the intended MPPT, or run automatic distribution and review the table. Every nonempty string should have exactly one assignment consistent with its block. Resolve capacity warnings before export.

VERIFY
Parallel strings should have compatible lengths and orientations. Check maximum input voltage, operating voltage window, current per MPPT and short-circuit current against documented ratings. Missing ratings are shown as missing, not accepted.

EXPORT
The CSV schedule includes string identifiers, module counts and MPPT assignments. Review it alongside the roof plan and the single-line diagram; recalculate after any string or block change.'''),
('Shadow', '''REFERENCE GEOMETRY
Set the site coordinates, north reference and obstacle position. Enter obstacle height, width and opacity and the roof heights used by the shadow model. Check all units and both roof levels on a multi-level site.

PREVIEW
Choose a day and time to inspect the projected footprint. Confirm the footprint direction against north and the image. Opacity represents the assumed obstructed fraction, not a measured optical property unless independently established.

SIMULATE
Run the required period with the configured step. Inspect module and string losses and the most affected periods. Geometry is evaluated per roof level, so a low-roof shadow must not automatically be applied to a higher roof.

LIMITATIONS
The clear-sky irradiance, NOCT cell temperature and linear temperature coefficient model are estimates. Geometric shading aggregation is not a detailed module I-V, mismatch, optimizer or bypass-diode model. For dated Energy/BESS calculations the actual imported dates are used. Record assumptions in the project report.'''),
('Spreadsheet', '''PROJECT VARIABLES
The sidebar is reserved for the variable explorer. Search a variable and double-click it, or use Insert, to place its identifier in the selected spreadsheet cell. Equipment sheets are now in Home > Configuration.

FORMULAS
Start a formula with =. Use cell references, arithmetic and the supported project variables. Select ranges and drag the fill handle to extend formulas; relative references move with the destination. Keep units explicit in adjacent labels.

REVIEW
A blank or failed formula is not a zero. Check error messages, inputs and dependencies. CSV export preserves the visible tabular result but cannot carry the complete interactive project; save the JSON as well.

CHARTS
Use charts only for comparable quantities with stated units. Derived spreadsheet calculations remain user-defined engineering assumptions and must be reviewed independently.'''),
('Electrical single-line diagram', '''GENERATE
Auto generate builds Strings > MPPT > Inverters from the active project assignments. Blocks and rows have increased separation for readable labels. Regenerating restores the automatic arrangement.

ARRANGE
Left drag pans the view. Right-click selects a block. Right drag from empty space draws a selection rectangle; Shift/Ctrl extends it. Right drag from an already selected block moves the whole selection. The side list also supports extended selection. Reflow restores a measured layout with dedicated lanes for distance labels. Showing electrical values automatically recalculates spacing, including for older saved projects. Delete removes selected elements and their links; automatic nodes may return when regenerated from the project.

CUSTOM ELEMENTS
Add protective devices, meters or switchboards as custom elements. Choose a custom link style, then click the two endpoints. These links document a design decision; they do not validate its protection coordination.

DATA
Site wiring and Electrical data menus have been removed. Equipment inputs and electrical checks are accessible in Home > Configuration. The drawing follows the project; it is not a manufacturer-approved wiring diagram.'''),
('Cabling', '''PER-STRING SIZING AND MASS
Calculate routes populates the String sizing table with each A+B length, proposed section, voltage drop and mass. Imp and Vmp come from the single module equipment sheet; string voltage is Vmp × module count. Edit a string to supply its current and total operating voltage when module data is missing or differs. No generic 10 A / 600 V fallback is used for string sizing. Set cable kg/m by section from manufacturer sheets. TOTAL_CABLE_WEIGHT_KG (alias POIDS_TOTAL_CABLAGES_KG) is available in spreadsheet formulas only when every active string has a current route, section and kg/m. Its scope is DC string-to-inverter A+B cables; inter-module and AC cables are excluded. Missing inputs are displayed rather than counted as zero.

ROUTE PRIORITY
Place an inverter for each block. Draw cable tray polylines and finish with right-click. Choose gather points for the zone exits. The router prefers the drawn network, then the available polygon area, then an estimated direct L-shaped route. A direct fallback requires site review.

TWO CONDUCTORS
A is the first module to the inverter, drawn solid in the block colour. B is the last module to the inverter, drawn purple dashed. The inventory is A+B, not a single route doubled. Inter-module connectors and AC cables are excluded.

HEIGHT MODEL
Installation area elevations supply all cable heights. Each planar segment is split at area boundaries; vertical changes are counted once. A gap no longer than the configured maximum bridge length stays at the upstream height, then changes to the next surface height. Longer gaps descend to ground and rise again. Set the threshold to the actual supported span; its default is zero. Conflicting or missing heights prevent the affected calculation. Shadow heights are never substituted.

LENGTH AND SECTION
Length equals planar path + vertical steps + terminal reserve for each conductor. Voltage-drop sizing uses the complete DC loop. Confirm ampacity, temperature derating, grouping, installation method, mechanical protection and protective devices separately.

CHANGES
Recalculate after changing panel geometry, endpoints, inverter positions, paths, areas, heights or reserves. Export only current routes.'''),
('Energy / BESS', '''PURPOSE
Compare the same PV system and load with no storage, one cabinet or two cabinets. The question is how much PV can serve the load, how much electricity must still be purchased and how much is exported or curtailed.

INPUTS
Import hourly consumption (date, day, hours 0-23). Review filled missing values. Add historical hourly weather if available; otherwise the result uses the clear-sky estimate. Set AC conversion factor, cabinet capacity, shared power limits, usable SOC window, round-trip efficiency and grid export limit.

ONE CALCULATION
Use Calculate 3 options once in the toolbar. Each hour, PV serves the load; surplus charges the battery subject to power and SOC limits; remaining PV is exported subject to the limit and then curtailed. The battery serves the remaining deficit, and the grid supplies the balance. Initial SOC equals minimum SOC. Two cabinets double capacity while sharing the same configured charge/discharge power.

READ THE CHARTS
The load-supply bars stack direct PV + BESS discharge + grid import: each total equals the same load. The second chart shows exports and curtailment. Do not add battery charging to useful self-consumption: it contains losses and changes in stored energy. The daily chart has three separate panels: sources supplying the load, uses of PV production and SOC on its own 0–100% axis. SOC is shown at hour boundaries. Use Previous day / Next day, choose a configuration and click a bar for exact hourly values. The monthly chart uses the same first two panels in MWh and compares grid purchases for all three configurations below. Month labels include the year.

ECONOMICS
Results > Economics applies configured purchase/export prices and investment assumptions to the energy balance. It is a simplified undiscounted comparison: review operating costs, degradation, replacement, taxes and financing separately. No grid charging, time-of-use dispatch, arbitrage revenue or ancillary services are simulated.

PROVENANCE
Totals cover the imported period and are not automatically an annual forecast. The comparison is hidden after a relevant input changes until recalculated. Check end SOC, losses, missing values, weather provenance and actual equipment power limits before using the result commercially.'''),
]
