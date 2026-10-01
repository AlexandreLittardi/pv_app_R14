# R14 — 30 September 2026

Implemented the requested semantic icons, complete engineering questionnaire, common Undo/Redo in every tab, frozen roof-image preservation for report export, grouped single-line diagrams and English application output. Existing project names, notes, equipment keys and saved formulas are preserved.

Engineering reports now include full-year shading studies and heatmaps, complete spreadsheets with formula values, technical input schedules, per-string cable sizing, plan/layout/string/cable plates and energy/BESS chart/table comparisons. Current report snapshots recalculate energy when inputs are sufficient. Incomplete inverter ratings in the supplied projects are identified without invented power factors.

JPG settings are retained. String colours are shared bright cyan/magenta. BESS charts retain the vivid shared palette. Annual geometry sampling caches static module shapes and rejects disjoint bounding boxes; equivalence with original clipping is regression-tested, including overlapping translucent obstacles.

History retains source images and zoom, branches correctly, avoids rewriting in-progress input widgets, and shares unchanged hourly profiles across snapshots. Background calculation disables Undo/Redo until completion.

Validation: 82 regression/calculation tests, actual application-class frozen PDF exports, all attached-project questionnaire round trips and visual PDF/JPG/chart inspection. Interactive Tk desktop validation remains pending because no display is available.
