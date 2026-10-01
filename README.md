# PV Layout and Stringing — R14

Python/Tkinter desktop application. Python 3.12 with Tkinter is recommended.

## Start

```text
python -m pip install -r requirements.txt
python main.py
```

Windows: double-click `LANCER_WINDOWS.bat`. Exact validation-environment versions are recorded in `requirements-tested.txt`.

## Configuration and history

Home → **Configuration** opens one scrollable engineering questionnaire. Review geometry, site/solar parameters, equipment, inverter connections, each string's cable-sizing inputs, manufacturer linear masses, protection design, weather-source metadata, BESS and economics directly on this page. Choose the annual shadow-study year here. Optional blank values remain unknown. New equipment rows, additional cables, obstacles and exclusions can be added. Apply commits the validated questionnaire as one project edit; Cancel discards the draft.

Undo and Redo are available in every tab, with Ctrl+Z, Ctrl+Y and Ctrl+Shift+Z. One common history keeps layout, equipment, strings, diagram, cabling, spreadsheet and energy inputs consistent. Up to 100 states retain source images and drawing zoom. Drawing/typing changes are grouped using a short delay. A new edit after Undo clears the redo branch. History is held in memory and starts anew when a project is loaded. Undo/Redo is disabled during a background calculation.

Icons represent each tool's function and button labels remain visible. There are no button hover tooltips. Tool help remains under each tab's How it works. No additional zone-rotation control has been reintroduced; existing saved zone angles remain supported.

The editable single-line diagram groups naturally ordered strings and MPPT inputs by inverter, retains unassigned/custom devices, and offers Reflow and Fit diagram controls. Moving diagram elements remains supported.

## Engineering report

Home → **Engineering report PDF** exports the PDF, editable LaTeX source and a companion assets folder containing:

- Source roof plan, installation layout, two-colour string plates and readable numbered detail atlas; PDF/SVG vector plans.
- Exact string/module/MPPT schedule and installation-zone dimensions.
- Entered technical inputs, equipment schedule and protection settings; missing inputs remain explicit.
- Full calendar-year shading influence: energy-weighted module heatmap, daily/hourly heatmap, monthly energy/loss table, string table and module CSV.
- Complete spreadsheet, including blank configured rows/columns, formulas and evaluated values; separate input/value CSVs.
- Cable drawing, both conductor routes, length breakdown and current/voltage/section/voltage-drop/check/mass records for each calculable string.
- PV-only / one-BESS / two-BESS comparison charts, monthly charts, complete annual/monthly metric tables and economic comparison when the required inputs are complete.

Report export recalculates stale energy/BESS results on its frozen snapshot when possible. It leaves the live project unchanged. Missing consumption, incomplete inverter ratings, invalid connections or incompatible weather metadata are reported explicitly; stale numerical results are not presented as current. Enter active inverter power, or apparent power together with power factor, to enable energy calculations. Partial imported periods are identified and are not used for annual payback.

The annual shadow study integrates every real hour of the selected calendar year in the site time zone, including leap years and daylight-saving transitions. It uses the existing clear-sky and selected shading/thermal model, independently of the imported-weather energy comparison. It is an estimate, not a full I–V/bypass-diode or structural/electrical certification study. Missing scale/geometry inputs prevent the applicable calculation.

## Export colours and project compatibility

Strings alternate bright cyan and magenta consistently across the application, JPG and vector report exports. JPG resolution, JPEG quality 95, colour subsampling 0 and 300 dpi metadata are retained. BESS charts use the shared vivid palette: solar yellow, battery green, grid blue, export cyan, curtailment red and SOC purple.

The supplied projects and roof image remain unchanged in `exemples_joints/`. Legacy equipment keys and formula aliases remain readable; application-generated labels, help and exports use English. User-entered names, notes and spreadsheet text retain their original wording. The project named 517 contains 537 actual modules.

Atomic project/image saves, backups, separate recovery saves, per-string conductor sizing and the `TOTAL_CABLE_WEIGHT_KG` global variable remain supported. Total cable weight requires complete declared string routes and additional-inventory linear masses; undeclared cables are outside its scope.

## Verification

```text
python -m unittest discover -s tests -v
python tools/test_r11_gui.py
```

82 regression/calculation tests cover attached-project round trips, questionnaire validation, every-tab history, frozen-image PDF export, annual shading/DST, spreadsheet formulas, diagram spacing, icon distinctions, energy balances and earlier functionality. PDF generation using the actual application class, supplied project data and raster source has been checked; generated PDF/JPG/heatmap/chart pages have been visually inspected.

The interactive desktop test requires a Tk display. It has not been executed in this headless environment; perform the Windows smoke test before operational use. Historical release and audit documents are retained under `docs/historical/`.
