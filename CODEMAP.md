# CODEMAP (généré par tools/gen_codemap.py, ne pas éditer à la main)
Utilisation : lis cette carte AVANT d'explorer. Lis ensuite uniquement la plage de lignes utile.

### app.py (318 lignes)
Classe principale de l'application : assemble tous les mixins et contient
Imports internes : constants, mixins.cable_network, mixins.canvas_grid, mixins.detailed_electrical_ui, mixins.diagram_editor, mixins.diagram_tools, mixins.editor_interactions, mixins.equipment_tools, mixins.hourly_chart_ui, mixins.installation_geometry, mixins.inverter_tools, mixins.material_tools, mixins.notes_tools, mixins.paths_tools, mixins.project_integrity, mixins.project_io, mixins.project_workspace, mixins.responsive_ui, mixins.safe_project, mixins.self_consumption_ui, mixins.shadow_tools, mixins.spreadsheet_interactions, mixins.spreadsheet_tools, mixins.stringing_tools, mixins.two_pole_cables, mixins.ui_builders, mixins.workspace_improvements, mixins.zone_tools, project_store
- **class PVLayoutRibbonApp** L45-314
  - `__init__(root)` L74-314

### async_jobs.py (20 lignes)
A cancellable worker; queue messages keep all Tk access on its owner thread.
- **class Cancelled** L5-5
- **class Job** L7-20
  - `__init__(work)` L8-19
  - `cancel()` L20-20

### battery_dispatch.py (163 lignes)
Dispatch orario AC del BESS: solo surplus FV, senza ricarica da rete.
Imports internes : self_consumption
- **class BatterySettings** L12-37
  - `validate()` L24-37
- `simulate_bess(profile, pv_kwh, settings, export_limit_kw)` L40-107 — Restituisce i due scenari con bilanci energetici coerenti.
- `simulate_three_options(profile, pv_kwh, one_cabinet, export_limit_kw)` L110-131 — Un solo FV e carico per le tre configurazioni simultanee.
- `write_comparison_csv(path, comparison, imputed_indices)` L134-163 — Confronto a 3 opzioni sullo stesso timestamp (una riga per ora).

### bess_charts.py (75 lignes)
AC energy figures with separate load, PV allocation and SOC axes.
Constantes : COLORS, CASE_COLORS, CASES
- `monthly_data(summaries, case)` L11-15
- `daily_data(rows, case, export_limit, initial_soc)` L17-27
- `_style(ax, title, unit)` L29-34
- `_stacks(ax, x, data, keys, labels, colors, factor)` L36-42
- `energy_figure(data, labels, title, monthly, comparison)` L44-75

### configuration_form.py (215 lignes)
Declarative questionnaire fields and transactional input parsing.
Imports internes : battery_dispatch, detailed_electrical, energy_economics, mixins.material_tools, mixins.notes_tools, project_store
Constantes : LABELS, TEXT_KEYS, INTEGER_KEYS, OPTION_KEYS
- **class Field** L10-16
- `label(key)` L74-74
- `get(data, path, default)` L75-79
- `put(data, path, value)` L81-87
- `prepare(data)` L89-107
- `fields(data)` L109-174
- `parse(field, raw)` L176-200
- `apply_values(data, descriptors, values)` L202-215

### constants.py (14 lignes)
Couleurs utilisees pour les strings et les blocs.
Constantes : STRING_COLORS, BLOCK_COLORS

### detailed_electrical.py (336 lignes)
Rebuildable site wiring schedule and editable, documented single-line SVG.
Imports internes : electrical_checks, engineering_inputs, project_validation, single_line_516
Constantes : HYBRID_MODEL, BESS_MODEL
- `source_fingerprint(project)` L20-29 — Engineering design must be checked again after connections or geometry change.
- `default_design()` L32-44
- `normalise_design(saved)` L47-61
- `_rating(value, label, issues, required)` L64-72
- `build_detailed_model(project, saved_design)` L75-225
- `write_detailed_svg(model, path)` L228-336 — Produce a readable vector drawing and wiring schedule with per-field open items.

### diagram_layout.py (46 lignes)
Grouped, naturally ordered string → MPPT → inverter diagrams.
Imports internes : project_validation
- `arrange(nodes, links, sizes, gap_x, gap_y)` L4-37
- `group_bounds(nodes, sizes)` L39-46

### electrical_checks.py (59 lignes)
Per-string and per-inverter datasheet checks; missing limits stay unknown.
Imports internes : engineering_inputs, project_validation
- `check(project)` L7-59

### energy_charts.py (25 lignes)
Comparable AC energy charts. Never mix battery charging with useful load supply.
Imports internes : bess_charts
- `comparison_figure(summaries)` L6-25

### energy_economics.py (98 lignes)
Value useful PV and grid exports without double-counting battery charging.
Imports internes : self_consumption
Constantes : DEFAULTS
- `validate_settings(settings)` L14-25
- `evaluate_options(annuals, settings)` L27-69
- `write_economic_csv(path, rows)` L71-75
- `storage_margin_per_charge_kwh(settings, round_trip_efficiency)` L77-83 — Gross incremental value per kWh charged and later used by the load.
- `covers_full_year(profile)` L86-98 — A complete anniversary-to-anniversary load period, including leap years.

### energy_engine.py (56 lignes)
Freeze project inputs and compute energy without calling a Tk widget.
Imports internes : battery_dispatch, self_consumption
- **class Value** L6-10
  - `__init__(value)` L7-7
  - `get()` L8-8
  - `delete()` L9-9
  - `insert(index, value)` L10-10
- `freeze_app(app)` L12-35
- `calculate(app, profile, ac_factor, numeric, weather, progress)` L37-56

### energy_reference.py (47 lignes)
Engineering documentation of the Energy / BESS implementation, in English.
Constantes : ENERGY_FORMULAS

### engineering_inputs.py (53 lignes)
One source of electrical operating data for routes, schedules and energy.
Imports internes : project_validation
- `module_for_string(project, sid)` L5-10
- `operating_values(project, sid)` L12-19
- `inverter_row(project, block)` L21-26
- `ac_limit_kw(project, block)` L28-36
- `panel_connections(app)` L38-53

### engineering_report.py (408 lignes)
Desktop engineering report: current inputs, explicit omissions, PDF and LaTeX.
Imports internes : bess_charts, configuration_form, energy_charts, energy_economics, home_reference, mixins.material_tools, mixins.spreadsheet_tools, project_validation, report_plans, report_studies
Constantes : MISSING
- `scalar(value)` L19-23
- `report_content(app, assets, font, progress)` L26-233
- `report_title(app)` L236-240 — Use the saved project filename, independent of the PDF export name.
- `_ordered_blocks(blocks)` L243-268 — Keep the complete calculation record, while bringing drawings forward.
- `export_report(app, path, progress)` L271-380
- `write_latex(path, blocks, project)` L383-408

### geometry_layout.py (104 lignes)
Shared, unit-neutral rigid layout geometry and installation cable elevations.
- `rotate(point, centre, degrees)` L5-9
- `inside(point, polygon)` L12-22
- `grid_spec(zone, width, height, scale)` L25-36
- `route_elevation(points, surfaces, scale, inverter_height, reserve, bridge_gap)` L39-87 — Split each planar segment at surface edges. Orthogonal height steps.
- `polygons_overlap(a, b)` L90-97 — Strict overlap of convex panels; shared edges are allowed.
- `intersects_polygon(a, b)` L100-104

### home_reference.py (54 lignes)
User-facing, code-audited guide. Equations are Matplotlib mathtext strings.
Imports internes : energy_reference, user_guide
Constantes : FORMULAS

### main.py (16 lignes)
Point d'entree de l'application Aide au Layout et Stringing PV.
Imports internes : app, platform_setup

### mixins/__init__.py (0 lignes)

### mixins/cable_network.py (595 lignes) ⚠ GROS FICHIER : ne pas lire en entier, utiliser les plages de lignes
Réseau de chemins de câbles (self.cable_paths, tracé dans l'onglet "Chemins")
Constantes : _NET_ROUTE_COLORS, _GRID_NEIGHBORS, _MAX_GRID_DIM
- **class CableNetworkMixin** L59-595
  - `_build_cable_network_graph()` L64-109 — Construit un graphe {noeud: [(voisin, poids_px), ...]} à partir de
  - `_segment_intersection(seg1, seg2)` L112-127 — Retourne le point d'intersection de deux segments, ou None s'ils ne
  - `_snap_point_to_network(graph, pt)` L129-165 — Projette pt sur le segment le plus proche du réseau de chemins de
  - `_dijkstra(graph, start, end)` L168-202 — Plus court chemin entre deux nœuds du graphe de chemins tracés.
  - `_build_walkable_grid()` L208-229 — Rasterise la zone de passage (polygones de l'onglet Chemins moins
  - `_nearest_walkable_cell(grid, gw, gh, gx, gy)` L232-253 — Cellule de passage la plus proche de (gx, gy) (recherche en anneaux).
  - `_grid_dijkstra(grid, gw, gh, src)` L256-280
  - `_grid_smooth_path(cells)` L283-299 — Simplifie le chemin en grille en ne gardant que les points de
  - `_route_via_walkable_area(point_a, point_b)` L301-340 — Route point_a -> point_b en évitant les obstacles, via la zone de
  - `_orthogonal_points(p1, p2)` L343-357 — Chemin à un coude (deux segments perpendiculaires) entre p1 et
  - `compute_cable_route(string_id, terminal)` L363-431 — Retourne (longueur_totale_mm, route_kind, points) pour la string
  - `compute_cable_length_mm(string_id)` L433-439 — Compatibilité : retourne (longueur_mm, via_reseau_ou_zone) — utilisé
  - `compute_all_cable_routes()` L441-467
  - `_draw_cable_network_routes(zoom)` L469-499 — Dessine les câbles calculés par compute_all_cable_routes().
  - `_dist_point_to_zone_rect(px, py, z)` L506-511
  - `_get_panel_zone_idx(coord)` L513-523 — Retourne l'index (dans self.roof_zones) de la zone contenant ce
  - `_get_zone_gather_point(zone_idx, inverter_point)` L525-552 — Point où les câbles d'une même zone se rassemblent avant le tronc
  - `_place_gather_point_at(img_x, img_y)` L554-574 — Place/déplace manuellement le point de rassemblement de la zone la
  - `_activate_gather_point_mode()` L576-581
  - `_reset_gather_points()` L583-595 — Repasse toutes les zones en calcul automatique du point de

### mixins/canvas_grid.py (1339 lignes) ⚠ GROS FICHIER : ne pas lire en entier, utiliser les plages de lignes
Interactions souris sur le canvas et dessin de la grille de panneaux.
Imports internes : constants
- **class CanvasGridMixin** L22-1335
  - `on_left_press(event)` L23-249
  - `on_left_drag(event)` L251-357
  - `on_left_release(event)` L359-481
  - `on_right_press(event)` L483-518
  - `on_right_drag(event)` L520-525
  - `_handle_ctrl_click_add(cell)` L531-552
  - `_handle_ctrl_click_remove(cell)` L554-569
  - `_zoom_at_pointer(event, delta)` L575-598
  - `create_new_block()` L604-618
  - `delete_active_block()` L620-628
  - `_update_combo_blocks()` L630-640
  - `_on_block_selected(event)` L642-646
  - `_get_grid_bounds()` L652-659
  - `_get_string_display_color(string_id, color)` L661-705 — Retourne la couleur d'affichage d'une string selon le toggle de focus (Onglet St…
  - `_is_inactive_string_dimmed(string_id)` L707-713 — Indique si une string doit être visuellement grisée.
  - `draw_grid()` L715-1239
  - `_set_layout_orientation_entries(tilt, azimuth)` L1241-1244
  - `apply_panel_orientation()` L1246-1264
  - `_update_stats_display()` L1266-1285
  - `center_view_on_origin()` L1287-1293
  - `_get_cell_coords(event)` L1295-1332
  - `_get_active_tab_index()` L1334-1335

### mixins/configuration_questionnaire.py (126 lignes)
All engineering inputs in one scrollable questionnaire; one atomic Apply.
Imports internes : configuration_form, self_consumption
Constantes : DISPLAY_CHOICES
- `show_questionnaire(app)` L11-126

### mixins/detailed_electrical_ui.py (287 lignes)
Editable engineering schedule for the active PV project; compact toolbar entry.
Imports internes : detailed_electrical, project_validation
- **class DetailedElectricalUIMixin** L15-287
  - `_detailed_project_snapshot()` L16-23
  - `_export_detailed_electrical_svg()` L25-35
  - `_show_detailed_electrical_editor()` L37-287

### mixins/diagram_editor.py (134 lignes)
Left drag pans the diagram; right drag selects, or moves the selected group.
Imports internes : diagram_layout, project_validation
- **class DiagramEditorMixin** L6-134
  - `_build_tab_diagram_tools()` L7-11
  - `_build_main_area()` L13-15
  - `on_left_press(event)` L17-22
  - `on_left_drag(event)` L24-27
  - `on_left_release(event)` L29-31
  - `on_right_press(event)` L33-42
  - `on_right_drag(event)` L44-55
  - `on_right_release(event)` L57-75
  - `_diagram_node_size(key)` L77-84
  - `_diagram_layout_signature()` L86-88
  - `_reflow_diagram()` L90-94
  - `_draw_diagram()` L96-121
  - `generate_diagram_auto()` L123-125
  - `_fit_diagram()` L127-134

### mixins/diagram_tools.py (550 lignes) ⚠ GROS FICHIER : ne pas lire en entier, utiliser les plages de lignes
Onglet Schéma Unifilaire : génère automatiquement un schéma
Imports internes : single_line_516
Constantes : NODE_COLORS, NODE_W, NODE_H, LINK_STYLES
- **class DiagramToolsMixin** L28-550
  - `_build_tab_diagram_tools()` L33-71
  - `_build_side_panel_diagram()` L77-99
  - `_export_site_single_line(batteries, language)` L105-139 — Rebuild the site topology from the CURRENT project, not a saved image.
  - `generate_diagram_auto()` L141-228
  - `_add_custom_diagram_node()` L234-262
  - `_toggle_diagram_link_mode(style)` L264-273
  - `_cancel_diagram_link_mode()` L275-278
  - `_edit_diagram_electrical_specs()` L280-363 — Record STC module ratings and an optional nominal inverter AC rating.
  - `_toggle_diagram_electrical()` L365-372
  - `_diagram_node_metric_lines(node_id)` L374-406 — Calculate STC DC ratings using each string's actual number of modules.
  - `_delete_selected_diagram_node()` L408-419
  - `_hit_test_diagram_node(cx, cy)` L421-429
  - `_diagram_node_size(node_id)` L431-433
  - `_on_diagram_list_select(event)` L435-441
  - `_refresh_diagram_list()` L443-450
  - `_get_string_length_m(sid)` L452-463 — Longueur cumulée (en m) du câblage d'une string, panneau à panneau.
  - `_draw_diagram()` L469-550

### mixins/editor_interactions.py (92 lignes)
Explicit desktop editor gestures, without left-button canvas panning conflicts.
Imports internes : mixins.canvas_grid, project_store
- **class EditorInteractionsMixin** L4-92
  - `on_left_press(event)` L5-36
  - `on_left_drag(event)` L38-59
  - `on_left_release(event)` L61-70
  - `_on_diagram_list_select(event)` L72-74
  - `_delete_selected_diagram_node()` L76-80
  - `draw_grid()` L82-88
  - `_on_zone_combo_selected(event)` L90-92

### mixins/equipment_tools.py (457 lignes)
Gestion des equipements et repartition des strings dans les MPPT.
Imports internes : project_validation
- `natural_sort_key(s)` L21-23 — Clé de tri naturel pour ordonner correctement 'INV2' avant 'INV10' et 'String 2'…
- **class EquipmentToolsMixin** L26-453
  - `_on_block_selected_equip(event)` L27-31
  - `_update_equipment_panel_from_active()` L33-45
  - `_refresh_block_capacity_label()` L47-61
  - `_set_mppt_capacity_label(label, color)` L63-67
  - `_apply_block_equipment()` L69-86
  - `_on_mppt_current_string_changed(event)` L88-98
  - `export_mppt_csv()` L100-130 — Export every nonempty string, including unassigned strings, in a readable CSV.
  - `_get_block_string_count(block_name)` L132-142 — Nombre de strings connectées (au moins un panneau) à ce bloc/onduleur.
  - `_get_string_block(string_id)` L148-155 — Retourne le nom du bloc (onduleur) auquel appartient la string, ou None.
  - `_prune_mppt_assignments()` L157-172 — Nettoie les affectations MPPT devenues invalides (string supprimée, bloc supprim…
  - `_assign_string_to_mppt(string_id, block_name, mppt_idx, show_errors)` L174-213 — Tente d'affecter une string à un MPPT donné, en respectant la capacité et
  - `_unassign_string_from_mppt(string_id)` L215-216
  - `_clear_mppt_assignments()` L218-223
  - `_auto_distribute_strings_to_mppt()` L225-326 — Distribue les strings dans l'ordre naturel (String 1, 2, 3...) :
  - `_refresh_equipment_tree()` L328-411
  - `_format_cable_length_label(string_id)` L413-423 — Formate la longueur de câble string -> onduleur pour l'arbre équipement,
  - `_on_equip_tree_press(event)` L425-427
  - `_on_equip_tree_release(event)` L429-453

### mixins/hourly_chart_ui.py (79 lignes)
Readable Matplotlib day and month views using identical energy-flow colours.
Imports internes : battery_dispatch, bess_charts, self_consumption
- **class HourlyChartMixin** L8-79
  - `_open_annual_chart()` L9-12
  - `_open_hourly_chart()` L14-22
  - `_bess_chart_window(title, summaries, comparison, dates, cfg)` L24-79

### mixins/installation_geometry.py (180 lignes)
Installation transforms, common panel geometry, dimensions and elevations.
Imports internes : geometry_layout, project_store, zone_registry
- **class InstallationGeometryMixin** L7-180
  - `_recalculate_zone_grids()` L8-16
  - `_remap_zone_rows(base, capacity, new_base)` L18-28
  - `_panel_pitch_mm()` L30-32
  - `_mark_geometry_change()` L34-36
  - `delete_active_zone()` L38-48
  - `_detach_coords(coords)` L50-56
  - `_zone_rotate_rect(zone, x1, y1, x2, y2)` L58-62
  - `_valid_zone_cell(zone, r, c)` L64-73
  - `_get_panel_physical_center(coord)` L75-78
  - `_get_cell_coords(event)` L80-91
  - `generate_panels_from_zones()` L93-120
  - `_show_installation_heights()` L122-149
  - `_activate_dimension(mode)` L151-152
  - `_draw_dimension(measure, zoom)` L154-165
  - `_layout_issues()` L167-176
  - `_draw_clearance_dimension(marker, zoom)` L178-180

### mixins/inverter_tools.py (245 lignes)
Placement physique des onduleurs sur le plan (Onglet Layout & Blocs).
Imports internes : mixins.material_tools
- `natural_sort_key(s)` L18-20 — Clé de tri naturel pour ordonner correctement 'INV2' avant 'INV10' et 'String 2'…
- **class InverterToolsMixin** L23-245
  - `open_inverter_selection_dialog()` L28-104
  - `_start_inverter_placement(material_row)` L110-120
  - `_place_pending_inverter_at(img_x, img_y)` L122-138 — Appelé depuis on_left_press (canvas_grid.py) lorsque layout_mode == 'place_inver…
  - `remove_inverter_placement()` L140-153
  - `assign_strings_to_inverters()` L159-219 — Affecte séquentiellement les strings aux MPPT des onduleurs.
  - `_draw_inverters(zoom)` L225-245 — Dessine un marqueur pour chaque onduleur placé. Appelé depuis draw_grid()

### mixins/material_tools.py (704 lignes) ⚠ GROS FICHIER : ne pas lire en entier, utiliser les plages de lignes
Fiche matériel du projet : modules PV, onduleurs, câbles/protections et
Constantes : MATERIAL_CATEGORY_DEFS, MATERIAL_TITLES_EN, MATERIAL_COLUMNS_EN, SHEET_ALIASES, _CELL_REF_RE, _TOKEN_SPEC, _TOKEN_RE
- `default_material_categories()` L56-59 — Structure par défaut (utilisée à l'init de l'app et au chargement d'un
- `_resolve_sheet(name, default_key)` L74-80
- `_col_index_to_letters(idx)` L83-89
- `_col_letters_to_index(letters)` L92-96
- `_parse_cell_ref(token_str, sheet)` L102-108
- `_sanitize_ident(name)` L111-120 — Transforme un nom de champ personnalisé ('Marge %') en identifiant
- `_to_number(raw)` L123-134 — Convertit une valeur brute de cellule en float pour usage dans une
- `_tokenize(s)` L158-170
- **class _FormulaParser** L173-265 — Grammaire : expr := terme (('+'|'-') terme)* ; terme := unaire
  - `__init__(tokens)` L180-182
  - `_peek()` L184-185
  - `_advance()` L187-190
  - `_expect(kind)` L192-196
  - `parse()` L198-201
  - `_parse_expr()` L203-209
  - `_parse_term()` L211-217
  - `_parse_unary()` L219-224
  - `_parse_primary()` L226-238
  - `_parse_ident_expr()` L240-265
- **class MaterialToolsMixin** L268-704
  - `_build_side_panel_material()` L273-336
  - `_make_scrollable_grid(parent)` L338-379 — Zone avec ascenseurs vertical + horizontal contenant une grille de widgets.
  - `_build_material_grid_header(inner, columns)` L381-393
  - `_rebuild_material_grid_rows(key)` L399-427
  - `_rebuild_all_material_grids()` L429-432
  - `_select_material_row(key, row_idx)` L434-440
  - `_add_material_row(key)` L442-446
  - `_delete_material_row(key)` L448-457
  - `_on_material_cell_focus_in(key, row_idx, col_idx)` L463-471 — Au clic sur une cellule : affiche la formule brute (pas le résultat) pour éditio…
  - `_on_material_cell_commit(key, row_idx, col_idx)` L473-482
  - `_on_material_cell_return(key, row_idx, col_idx)` L484-492 — Entrée : valide la cellule et passe à la ligne suivante (comme un tableur).
  - `_get_material_global_vars()` L498-534 — Variables globales du projet utilisables dans une formule
  - `_compute_material_formulas()` L540-657 — Calcule toutes les cellules-formules de la fiche matériel.
  - `_format_computed_value(value)` L660-665
  - `_refresh_material_trees()` L667-704 — Point d'entrée public (nom conservé : appelé par project_io.py après

### mixins/model_settings.py (75 lignes)
Scrollable project model settings, with explicit equipment and inventory inputs.
Imports internes : project_store
- `show_settings(app)` L11-75

### mixins/notes_tools.py (367 lignes)
Cabling workspace: route inventory, DC voltage-drop estimate and project notes.
Imports internes : project_validation
Constantes : STANDARD_DC_SECTIONS
- `calculate_dc_cable_size(current_a, voltage_v, length_m, resistivity, target_drop_pct)` L13-29 — Estimate a two-conductor DC circuit from one-way cable length.
- **class NotesToolsMixin** L32-367
  - `_init_notes_state()` L33-45
  - `_build_tab_notes_tools()` L47-87
  - `_build_side_panel_notes()` L89-180
  - `_capture_cable_inputs()` L182-194 — Store valid edits so tab switches and project saves keep the current input.
  - `_compute_cable_size()` L196-209
  - `_on_notes_changed(event)` L211-215
  - `_refresh_notes()` L217-226
  - `_refresh_cabling_paths()` L228-241
  - `_invalidate_cable_routes()` L243-248
  - `_on_cable_path_tree_selected(event)` L250-259
  - `_refresh_cable_route_table(summary)` L261-295
  - `_on_cable_route_selected(event)` L297-300
  - `_calculate_and_show_cable_routes()` L302-312
  - `_hide_cable_routes()` L314-316
  - `_on_click_trace_cables()` L318-323 — Retained for old callbacks; the new toolbar uses the route inventory.
  - `_use_longest_cable_route()` L325-335
  - `_export_cable_routes_csv()` L337-367

### mixins/paths_tools.py (388 lignes)
Outils de tracage des chemins/polygones de cablage et mesures de distance.
Imports internes : project_store
- **class PathsToolsMixin** L20-388
  - `_activate_polygon_select_mode()` L21-24
  - `_activate_polygon_draw_mode()` L26-36
  - `_cancel_polygon_draw()` L38-41
  - `_finish_polygon_draw()` L43-60
  - `_update_polygon_combo()` L62-68
  - `_on_polygon_combo_selected(event)` L70-75
  - `_activate_cable_path_draw_mode()` L81-90
  - `_cancel_cable_path_draw()` L92-95
  - `_finish_cable_path_draw()` L97-115
  - `_update_cable_path_combo()` L117-127
  - `_on_cable_path_combo_selected(event)` L129-134
  - `delete_active_cable_path()` L136-148
  - `delete_active_polygon()` L150-159
  - `_point_in_polygon(px, py, points)` L162-172 — Test point-dans-polygone (ray casting).
  - `_hit_test_polygon(img_x, img_y)` L174-179 — img_x, img_y en coordonnées image d'origine. Retourne l'index du polygone conten…
  - `_toggle_distance_mode()` L185-196
  - `clear_distance_markers()` L198-200
  - `_get_all_borders()` L202-221 — Renvoie la liste de tous les bords : contour(s) du/des polygone(s) et contour de…
  - `_nearest_point_on_segment(px, py, x1, y1, x2, y2)` L224-231
  - `_nearest_point_on_borders(px, py, borders, exclude_source)` L233-244 — Retourne (x, y, distance, border) du point le plus proche de (px, py) parmi tous…
  - `_add_distance_marker_at(img_x, img_y)` L246-269 — Trouve le bord le plus proche du clic, puis le bord OPPOSÉ le plus proche de ce …
  - `_hit_test_distance_marker(cx, cy, threshold)` L271-284 — cx, cy en coordonnées canvas (déjà zoomées). Retourne l'index de la mesure la pl…
  - `_draw_text_with_bg(x, y, text, fill, font, anchor)` L286-297 — Dessine un texte sur le canvas avec un fond blanc opaque derrière, pour la lisib…
  - `_compute_polygon_overlay(zoom)` L303-326
  - `_on_canvas_motion(event)` L328-379
  - `_on_escape_key(event)` L381-388

### mixins/project_integrity.py (164 lignes)
Keep equipment, diagrams and saved simulation provenance consistent.
Imports internes : detailed_electrical, energy_economics, project_validation
Constantes : EXTRA_FIELDS
- **class ProjectIntegrityMixin** L15-164
  - `_init_energy_state()` L16-27
  - `_project_snapshot()` L29-38
  - `_sync_module_power()` L40-59
  - `_read_shadow_params_from_entries(show_errors)` L61-64
  - `_prepare_project_save()` L66-69
  - `_load_energy_state(data)` L71-99
  - `_energy_signature()` L101-114
  - `_require_current_energy()` L116-120
  - `draw_grid()` L122-130
  - `_show_electrical_audit()` L132-164

### mixins/project_io.py (448 lignes)
Sauvegarde/chargement du projet JSON et exports (CSV, JPG).
Imports internes : mixins.material_tools, mixins.spreadsheet_tools, plan_renderer, project_store, project_validation
- **class ProjectIOMixin** L24-448
  - `_collect_project_data()` L25-98
  - `_on_ctrl_s(event)` L100-102
  - `_auto_save()` L104-110
  - `_flash_autosave_notice()` L112-116 — Affiche brièvement une confirmation discrète de sauvegarde automatique.
  - `import_project()` L118-125
  - `_load_project_file(filepath, data_override, quiet)` L127-395
  - `export_csv()` L397-438
  - `export_jpg_final(scale)` L441-448

### mixins/project_workspace.py (86 lignes)
Project setup, embedded BESS comparison and report entry point.
Imports internes : energy_charts, engineering_report, mixins.configuration_questionnaire
- **class ProjectWorkspaceMixin** L7-86
  - `_build_tab_file_tools()` L8-11
  - `_show_project_configuration()` L13-15
  - `_open_equipment_configuration()` L17-18
  - `_show_grid_configuration()` L20-31
  - `_install_energy_workspace()` L33-47
  - `_refresh_energy_workspace()` L49-67
  - `_export_engineering_report()` L69-76
  - `_calculate_self_consumption()` L78-83
  - `_install_home()` L85-86

### mixins/responsive_ui.py (179 lignes)
Wrapping native icon toolbars, without overflow menus or duplicated fields.
Imports internes : toolbar_icons
- **class ResponsiveUIMixin** L7-179
  - `_on_ribbon_tab_changed(event)` L8-11
  - `_build_root_scroller()` L13-16
  - `_install_responsive_ui()` L18-37
  - `_paginate_shadow_panel()` L39-40
  - `_install_compact_zoom()` L42-57
  - `_responsive_tab_changed(event)` L59-60
  - `_fit_tab_labels()` L62-75
  - `_schedule_responsive(event)` L77-80
  - `_layout_responsive()` L82-119
  - `_fit_roof_to_window()` L121-123
  - `_apply_roof_fit()` L125-132
  - `_zoom_button_change(factor)` L134-136
  - `_zoom_at_pointer(event, delta)` L138-140
  - `_iconize_toolbar(tab)` L142-167
  - `_fit_dialog(window, width, height)` L169-173
  - `_cap_mapped_dialog(event)` L175-179

### mixins/safe_project.py (413 lignes)
Persistence, recovery, undo and domain state at the application boundary.
Imports internes : async_jobs, battery_dispatch, energy_engine, engineering_report, project_store, self_consumption
- **class SafeProjectMixin** L13-413
  - `_install_project_guard()` L14-29
  - `_build_tab_file_tools()` L31-33
  - `_document_signature()` L35-36
  - `_confirm_unsaved()` L38-42
  - `_close_project()` L44-47
  - `save_project_as()` L49-51
  - `save_project(silent, destination)` L53-79
  - `_apply_document(data, filepath)` L81-108
  - `_load_project_file(filepath)` L110-129
  - `_remember_recent_project(path)` L131-132
  - `_record_history()` L134-153
  - `_restore_history(index)` L155-166
  - `undo_project()` L168-169
  - `redo_project()` L171-172
  - `_undo_shortcut(event)` L174-175
  - `_redo_shortcut(event)` L177-178
  - `_queue_history(event)` L180-183
  - `_poll_history()` L185-187
  - `_install_responsive_ui()` L189-196
  - `_shadow_signature()` L198-204
  - `_shadow_current()` L206-206
  - `draw_grid()` L208-218
  - `_update_history_buttons()` L220-223
  - `_recompute_shadow()` L225-228
  - `_get_active_tab_index()` L230-237
  - `_show_model_settings()` L239-240
  - `_cancel_task()` L242-243
  - `_start_job(work, complete, label, signature, on_progress, on_failure)` L245-277
  - `_build_self_consumption_tab()` L279-281
  - `_calculate_self_consumption()` L283-303
  - `_download_historical_weather()` L305-341
  - `_renumber_panels()` L343-345
  - `_build_tab_layout_tools()` L347-349
  - `_import_historical_weather()` L351-375
  - `_export_engineering_report()` L377-413

### mixins/self_consumption_ui.py (351 lignes)
Onglet Volfrigo: bilancio orario produzione FV / consumo frigorifero.
Imports internes : battery_dispatch, energy_economics, self_consumption
- **class SelfConsumptionMixin** L15-351
  - `_build_self_consumption_tab()` L16-43
  - `_show_energy_settings()` L45-46
  - `_load_consumption_excel()` L48-64
  - `_show_energy_economics()` L66-153
  - `_import_historical_weather()` L155-164
  - `_download_historical_weather()` L166-200
  - `_calculate_self_consumption()` L202-251
  - `_show_self_consumption_result()` L253-337
  - `_export_self_consumption()` L339-351

### mixins/shadow_energy.py (232 lignes)
Position solaire, irradiance ciel clair, puissance/energie des panneaux, agregation par string.
Imports internes : shading_models
- **class ShadowEnergyMixin** L21-232
  - `_get_clear_sky_irradiance(elevation_deg)` L22-40 — Estime le DNI (irradiance normale directe) en W/m².
  - `_get_clear_sky_poa_irradiance(elevation_deg, solar_azimuth_deg, panel_coord)` L42-77 — Convertit le DNI simplifié en irradiance approximative sur le plan du module.
  - `_estimate_cell_temperature(poa_irradiance)` L79-81 — Température cellule estimée par NOCT, sans données météo réelles.
  - `_estimate_panel_power_w(poa_irradiance, shaded_fraction)` L83-105 — Puissance électrique estimée du panneau à partir de Pmax STC.
  - `_panel_energy_step(poa_irradiance, shaded_fraction, dt_hours)` L107-113 — Retourne (énergie idéale Wh, énergie ombrée Wh, perte Wh).
  - `_summarize_string_group(string_id, members)` L115-141 — Agrège les résultats panneau (dict issus de `results`) d'une string.
  - `_aggregate_shadow_results_by_string(results)` L143-172 — Regroupe les résultats de simulation par string électrique.
  - `_compute_solar_position(lat_deg, lon_deg, day, month, hour_decimal, utc_offset, year)` L174-232 — Calcule l'élévation et l'azimut solaire avec haute précision (Spencer/NOAA).

### mixins/shadow_geometry.py (234 lignes)
Geometrie de l'ombre : polygones, enveloppe convexe, projection, pourcentages d'ombrage.
Imports internes : shading_models
- **class ShadowGeometryMixin** L21-234
  - `_polygon_area(points)` L23-30
  - `_clip_polygon_against_edge(subject, edge_start, edge_end)` L33-62 — Clippe un polygone convexe par une arête orientée (Sutherland-Hodgman).
  - `_polygon_clip(subject, clip)` L65-75
  - `_panel_rect(coord)` L77-99 — Retourne le rectangle physique du panneau en coordonnées image.
  - `_convex_hull(points)` L102-124 — Retourne l'enveloppe convexe d'un nuage de points 2D.
  - `_legacy_shadow_geometry(elevation, azimuth)` L126-178 — Calcule les polygones d'ombre projetés par le pylône, par hauteur de zone.
  - `_compute_shadow_geometry(elevation, azimuth)` L180-197
  - `_calculate_shadow_percentages(elevation, azimuth)` L199-223 — Calcule le % d'ombre panneau par panneau, avec la hauteur de sa zone.
  - `_point_near_segment(px, py, x1, y1, x2, y2, max_dist)` L225-234

### mixins/shadow_simulation.py (1222 lignes) ⚠ GROS FICHIER : ne pas lire en entier, utiliser les plages de lignes
Fenetre de simulation temporelle d'ombrage (multi-jours, heatmap, export).
Imports internes : energy_engine, shadow_engine
Constantes : _HEAT_STOPS, _MONTH_ABBR, _STEP_UNITS, _UNIT_SECONDS, _CHART_MAX_PERIODS, _CHART_METRICS, _CHART_PALETTES
- `_heat_rgb(t)` L26-32 — Couleur (r, g, b) du dégradé pour t dans [0, 1].
- `_rgb_hex(rgb)` L35-36
- `_text_on(rgb)` L39-42 — Texte sombre ou blanc selon la luminance du fond.
- `_nice_ticks(vmax, n)` L45-57 — Graduations « rondes » (1, 2, 2.5, 5 × 10^k) couvrant [0, vmax].
- **class ShadowSimulationMixin** L86-1222
  - `_open_shadow_simulation()` L87-737 — Ouvre la simulation temporelle d'ombrage avec intégration par intervalles.
  - `_aggregate_shadow_series(results, unit, count)` L743-835 — Agrège l'énergie simulée par période.
  - `_chart_label(unit, start, prev_start, multi_year)` L838-852 — Étiquette de l'axe X : « jan. », « 15 jan. », « 14:05\n15 jan. »…
  - `_chart_range_text(unit, start, end)` L855-876 — Description complète d'une période (info-bulle).
  - `_show_simulation_chart()` L881-1222

### mixins/shadow_tools.py (518 lignes) ⚠ GROS FICHIER : ne pas lire en entier, utiliser les plages de lignes
Onglet/panneau lateral ombre du pylone et callbacks UI.
Imports internes : .shadow_energy, .shadow_geometry, .shadow_simulation
- **class ShadowToolsMixin** L25-515
  - `_build_tab_shadow_tools()` L26-60
  - `_build_side_panel_shadow()` L62-237 — Construit le panneau latéral de paramétrage de l'ombre du pylône.
  - `_toggle_shadow_params_panel()` L239-244
  - `_activate_place_pylon_mode()` L246-251
  - `_activate_place_ref_mode()` L253-258
  - `_clear_pylon()` L260-269
  - `_update_shadow_delta_entries()` L271-280
  - `_apply_pylon_delta_position()` L282-298
  - `_refresh_shadow_zone_list()` L300-306
  - `_on_shadow_zone_selected(event)` L308-317
  - `_apply_shadow_zone_height()` L319-332
  - `_decimal_hour_to_hhmm(hour)` L335-338
  - `_hhmm_to_decimal_hour(value)` L341-348
  - `_on_shadow_hour_slider(value)` L350-365 — Synchronise le curseur avec l'heure solaire locale et recalcule immédiatement.
  - `_schedule_shadow_recompute(event)` L367-373
  - `_auto_recompute_shadow()` L375-381
  - `_read_shadow_params_from_entries(show_errors)` L383-429 — Lit les entrées du panneau latéral et met à jour les paramètres. Renvoie True si…
  - `_update_shadow_status_label()` L431-465
  - `_recompute_shadow()` L471-515 — Recalcule la position solaire et le % d'ombre de chaque panneau.

### mixins/spreadsheet_interactions.py (183 lignes)
Cell-range selection, fill handle, formula references and clipboard actions.
Imports internes : mixins.spreadsheet_tools
Constantes : _REFERENCE
- `shift_formula(formula, dr, dc)` L9-16 — Shift relative references when a formula is dragged to another cell.
- **class SpreadsheetInteractionsMixin** L19-183
  - `_rebuild_spreadsheet_grid()` L20-25
  - `_init_spreadsheet_state()` L27-32
  - `_build_material_spreadsheet_area()` L34-40
  - `_spreadsheet_rect_coords(first, last)` L42-47
  - `_draw_spreadsheet_selection()` L49-62
  - `_insert_clicked_cell_reference(cell)` L64-72
  - `_on_spreadsheet_cell_click(event)` L74-98
  - `_spreadsheet_cell_drag(event)` L100-113
  - `_spreadsheet_cell_release(event)` L115-122
  - `_spreadsheet_fill_to(target)` L124-157
  - `_spreadsheet_copy(event)` L159-167
  - `_spreadsheet_paste(event)` L169-183

### mixins/spreadsheet_tools.py (1286 lignes) ⚠ GROS FICHIER : ne pas lire en entier, utiliser les plages de lignes
Feuille de calcul type tableur (façon Google Sheets simplifié) affichée
Imports internes : project_validation
Constantes : DEFAULT_ROWS, DEFAULT_COLS, MAX_ROWS, MAX_COLS, _CELL_REF_RE, _COLON_RANGE_RE, _RANGE_TOKEN_RE, _BINOPS, _UNARY
- `col_letter(index)` L71-78 — 0 -> 'A', 25 -> 'Z', 26 -> 'AA' ...
- `col_index(letters)` L81-86 — 'A' -> 0, 'Z' -> 25, 'AA' -> 26 ...
- `cell_id(row, col)` L89-91 — (0, 0) -> 'A1' (row/col 0-indexés).
- `parse_cell_id(ref)` L94-100 — 'C3' -> (2, 2) (row, col 0-indexés), ou None si ce n'est pas une
- `_to_number(raw)` L103-114 — Convertit une valeur brute de cellule en float si possible, sinon la
- `default_spreadsheet_state()` L117-121 — Structure par défaut (utilisée à l'init de l'app et au chargement
- **class _FormulaError** L128-129
- `_eval_formula_ast(expr, cell_lookup, variables)` L132-196 — Évalue en toute sécurité une formule : + - * / % ** parenthèses,
- **class SpreadsheetToolsMixin** L199-1286
  - `_init_spreadsheet_state()` L204-225
  - `_get_spreadsheet_variables()` L231-315 — Variables numériques disponibles dans les formules, en plus des
  - `_refresh_variable_explorer()` L317-348
  - `_insert_selected_variable()` L350-353
  - `_compute_spreadsheet_values()` L359-396 — Calcule toutes les cellules de la feuille de calcul. Retourne
  - `_format_spreadsheet_value(value)` L399-406
  - `_build_material_spreadsheet_area()` L412-507 — Construit la grille de calcul dessinée nativement sur un Canvas
  - `_on_spreadsheet_data_yscroll(first, last)` L509-511
  - `_on_spreadsheet_data_xscroll(first, last)` L513-515
  - `_on_spreadsheet_mousewheel(event)` L517-519
  - `_on_spreadsheet_mousewheel_shift(event)` L521-523
  - `_spreadsheet_col_w(c)` L533-537
  - `_spreadsheet_row_h(r)` L539-543
  - `_spreadsheet_col_x(c)` L545-546
  - `_spreadsheet_row_y(r)` L548-549
  - `_spreadsheet_set_col_w(c, width)` L551-556
  - `_spreadsheet_set_row_h(r, height)` L558-563
  - `_zoom_spreadsheet(factor)` L565-568
  - `_reset_spreadsheet_zoom()` L570-573
  - `_spreadsheet_col_border_at(cx)` L575-583 — Index de la colonne dont la bordure droite passe près de cx, ou None.
  - `_spreadsheet_row_border_at(cy)` L585-592
  - `_on_spreadsheet_colheader_motion(event)` L596-601
  - `_on_spreadsheet_colheader_press(event)` L603-610
  - `_on_spreadsheet_colheader_drag(event)` L612-618
  - `_on_spreadsheet_colheader_release(event)` L620-623
  - `_on_spreadsheet_rowheader_motion(event)` L627-632
  - `_on_spreadsheet_rowheader_press(event)` L634-641
  - `_on_spreadsheet_rowheader_drag(event)` L643-649
  - `_on_spreadsheet_rowheader_release(event)` L651-654
  - `_rebuild_spreadsheet_grid()` L659-727 — (Re)dessine entièrement la grille (après ajout/suppression de
  - `_refresh_spreadsheet()` L729-749 — Recalcule toutes les formules et met à jour l'affichage de
  - `_draw_spreadsheet_selection()` L755-778
  - `_spreadsheet_ensure_visible(row, col)` L780-806
  - `_spreadsheet_cell_at_event(event)` L808-832
  - `_on_spreadsheet_cell_click(event)` L834-842
  - `_on_spreadsheet_cell_double_click(event)` L844-850
  - `_spreadsheet_move_selection(dr, dc)` L852-867
  - `_spreadsheet_start_edit(initial_text)` L873-902
  - `_spreadsheet_finish_edit(move_down, move_right)` L904-924
  - `_spreadsheet_commit_edit()` L926-929 — Valide la cellule en cours d'édition sans déplacer la sélection
  - `_spreadsheet_cancel_edit()` L931-932
  - `_spreadsheet_destroy_edit_widget()` L934-947
  - `_on_spreadsheet_key_return(event)` L953-958
  - `_on_spreadsheet_key_delete(event)` L960-967
  - `_on_spreadsheet_key_type(event)` L969-980 — Taper directement un caractère sur une cellule sélectionnée
  - `_add_spreadsheet_row()` L986-991
  - `_add_spreadsheet_col()` L993-998
  - `_remove_spreadsheet_row()` L1000-1022
  - `_remove_spreadsheet_col()` L1024-1046
  - `_clear_spreadsheet()` L1048-1054
  - `_get_zone_string_insert_vars()` L1056-1077 — Variables numériques (catégorie A) générées dynamiquement à partir
  - `_insert_text_into_active_cell(text)` L1080-1098 — Insère `text` dans la cellule active, à la position du curseur si
  - `_insert_spreadsheet_variable(name)` L1100-1130
  - `_apply_spreadsheet_formula_bar(event)` L1132-1145
  - `_export_spreadsheet_csv()` L1147-1163
  - `_import_spreadsheet_csv()` L1165-1197
  - `_show_spreadsheet_chart()` L1199-1286

### mixins/string_sizing.py (156 lignes)
Per-string voltage drop and manufacturer-supplied cable mass.
Imports internes : engineering_inputs, mixins.notes_tools, project_validation
- `size_string(record, modules, module_spec, overrides, parameters, masses)` L9-44
- **class StringSizingMixin** L47-156
  - `_string_sizing_signature()` L48-52
  - `_size_string_route(sid, record)` L54-59
  - `_cable_mass_summary()` L61-73
  - `_build_string_sizing_page(notebook)` L75-95
  - `_refresh_string_sizing_table()` L97-114
  - `_edit_string_sizing()` L116-140
  - `_edit_cable_masses()` L142-156

### mixins/stringing_tools.py (455 lignes)
Gestion des strings (creation, edition, generation automatique).
Imports internes : project_validation
- `natural_sort_key(s)` L21-23 — Clé de tri naturel pour ordonner correctement 'INV2' avant 'INV10' et 'String 2'…
- **class StringingToolsMixin** L26-455
  - `add_panel_to_string(cell)` L27-43
  - `remove_panel_from_strings(cell)` L45-55
  - `_clean_deleted_panels_from_strings()` L57-65
  - `_update_string_listbox(selected_panel_index)` L67-94
  - `_on_string_tree_selected(event)` L96-107
  - `_selected_string_panel_index()` L109-116
  - `_move_panel_in_string(direction)` L118-129
  - `_add_panel_manual_dialog()` L131-144
  - `_remove_panel_from_string_list()` L146-155
  - `add_new_string()` L157-172
  - `delete_active_string()` L174-191
  - `clear_all_strings()` L193-202
  - `_get_sorted_string_keys()` L204-205
  - `_update_combo_strings()` L207-216
  - `_on_active_string_changed(event)` L218-223
  - `_get_panel_physical_center(coord)` L229-248
  - `generate_auto_strings()` L250-397
  - `_split_balanced(items, min_per_string, max_per_string)` L399-418
  - `_get_next_available_panel_number()` L424-429
  - `update_dimensions()` L431-442
  - `_find_zone_for_panel(coord)` L444-455

### mixins/two_pole_cables.py (116 lignes)
Both string terminals, using the supplied router and verified saved routes.
Imports internes : geometry_layout, mixins.string_sizing, project_validation, single_line_516
- **class TwoPoleCablesMixin** L8-116
  - `_route_signature()` L9-18
  - `get_two_pole_route(sid)` L20-28
  - `_calculate_two_pole_route(sid)` L30-63
  - `compute_cable_length_mm(sid)` L65-67
  - `compute_all_cable_routes()` L69-89
  - `_draw_cable_network_routes(zoom)` L91-116

### mixins/ui_builders.py (703 lignes) ⚠ GROS FICHIER : ne pas lire en entier, utiliser les plages de lignes
Construction de l'interface ruban (onglets, panneaux lateraux).
Constantes : QUICK_START_GUIDE, FORMULA_GUIDE, TECHNICAL_GUIDE
- **class UIBuildersMixin** L93-698
  - `_load_ui_preferences()` L94-111
  - `_show_ui_preferences()` L113-154
  - `_build_root_scroller()` L156-176 — One outer scrollbar pair for the complete toolbar and work area.
  - `_update_root_scrollregion(event)` L178-179
  - `_resize_root_scroll_content(event)` L181-189
  - `_show_help(page)` L191-218 — Affiche une aide intégrée sans dépendre d'un fichier externe.
  - `_center_window(window, width, height)` L220-226
  - `_fix_combobox_popdown_position(combo)` L228-242
  - `_zoom_button_change(factor)` L244-250
  - `_reset_zoom()` L252-255
  - `_get_image_resample_filter()` L258-263 — Retourne un filtre de redimensionnement compatible avec Pillow.
  - `_build_ribbon_ui()` L269-307
  - `_build_tab_file_tools()` L313-348
  - `_build_tab_roof_tools()` L354-426
  - `_build_tab_layout_tools()` L432-518
  - `_build_tab_stringing_tools()` L524-563
  - `_show_string_settings()` L565-582
  - `_build_tab_equipment_tools()` L588-634
  - `_show_mppt_settings()` L636-658
  - `_build_tab_material_tools()` L664-698

### mixins/workspace_improvements.py (419 lignes)
Home, recent projects, compact layout controls and universal CSV preview.
Imports internes : home_reference, toolbar_icons
- **class WorkspaceImprovementsMixin** L17-419
  - `_build_tab_file_tools()` L18-30
  - `_build_tab_layout_tools()` L32-79
  - `_show_panel_configuration()` L81-107
  - `_install_home()` L109-198
  - `_install_energy_workspace()` L200-223
  - `_refresh_energy_workspace()` L225-242
  - `_energy_results_current()` L244-246
  - `_calculate_self_consumption()` L248-251
  - `_on_ribbon_tab_changed(event)` L253-263
  - `_show_home()` L265-268
  - `_show_help(page)` L270-273
  - `_recent_path()` L275-276
  - `_read_recent_projects()` L278-283
  - `_remember_recent_project(path)` L285-299
  - `_refresh_recent_projects()` L301-309
  - `_open_recent_selection()` L311-318
  - `on_left_press(event)` L320-334
  - `on_left_drag(event)` L336-344
  - `on_left_release(event)` L346-357
  - `_export_with_csv_preview(callback, initialfile)` L359-373 — Run the existing CSV writer against a private temporary path, then preview and s…
  - `_preview_csv_file(staged, initialfile)` L375-413
  - `export_csv()` L415-415
  - `export_mppt_csv()` L416-416
  - `_export_cable_routes_csv()` L417-417
  - `_export_spreadsheet_csv()` L418-418
  - `_export_self_consumption()` L419-419

### mixins/zone_tools.py (675 lignes) ⚠ GROS FICHIER : ne pas lire en entier, utiliser les plages de lignes
Gestion des zones de toiture, de l'echelle et de la zone principale.
- **class ZoneToolsMixin** L20-671
  - `_build_main_area()` L21-239
  - `_toggle_zone_params_panel()` L243-249
  - `_on_string_tree_start_drag(event)` L255-256
  - `_on_string_tree_drop(event)` L258-276
  - `_on_ribbon_tab_changed(event)` L282-355
  - `load_roof_image()` L361-401
  - `_activate_scale_mode()` L403-409
  - `_activate_measure_mode()` L411-420
  - `clear_measures()` L422-426
  - `_activate_zone_mode()` L428-437
  - `_activate_zone_select_mode()` L439-442
  - `_update_zone_combo()` L444-450
  - `_on_zone_combo_selected(event)` L452-458
  - `delete_active_zone()` L460-479
  - `_update_zone_entries_from_active()` L481-509
  - `update_active_zone_params()` L511-546
  - `_recalculate_zone_grids()` L548-604 — Calcule le nombre de lignes/colonnes et l'offset exact au mm près pour chaque zo…
  - `_zone_panel_center(x1, y1, x2, y2)` L614-615
  - `_zone_rotate_point(zone, cx, cy, x, y)` L617-628 — Tourne un point (x, y) autour du centre donné (cx, cy), selon
  - `_zone_rotate_rect(zone, x1, y1, x2, y2)` L630-635 — 4 coins tournés (TL, TR, BR, BL) d'un panneau autour de SON PROPRE
  - `_update_zones_from_scale()` L637-641 — Recalcule les grilles de zones et rafraîchit l'affichage suite au calibrage.
  - `generate_panels_from_zones()` L643-671

### plan_renderer.py (42 lignes)
Render the complete project in source coordinates, independently of Tk/zoom.
Imports internes : report_plans
- `render_plan(app, path, scale)` L6-42

### platform_setup.py (16 lignes)
Reglages specifiques a la plateforme (DPI Windows).
- `configure_windows_dpi()` L5-16 — A appeler une seule fois au demarrage sur Windows pour un rendu net.

### project_store.py (205 lignes)
Validated, versioned project records and crash-safe local persistence.
Imports internes : project_validation, self_consumption
Constantes : SCHEMA_VERSION, EXTRA_STATE, MODEL_DEFAULTS
- `serial(value)` L24-29
- `fingerprint(value)` L31-32
- `valid_polygon(points)` L34-50
- `validate_project(original)` L52-179
- `atomic_bytes(path, payload, backup)` L181-193
- `write_project(path, data, image, recovery)` L195-205

### project_validation.py (164 lignes)
Project migrations and electrical checks; never invent missing ratings.
Imports internes : electrical_checks
Constantes : INVERTER_MODEL, FORMULA_ALIASES
- `string_label(identifier)` L10-13 — Compact visible label without changing saved string identifiers.
- `english_formula(value)` L24-35
- `normalize_formula_storage(data)` L37-44 — Migrate formula identifiers in both saved sheets, preserving nonformula text.
- `number(value)` L46-51
- `natural(value)` L53-54
- `sync_diagram(data)` L56-97 — Assignments own generated wiring. Preserve custom devices and positions.
- `resolve_image(filepath, stored)` L99-110
- `normalize_project(original)` L112-139
- `audit_project(data)` L141-164 — Return explicit failures and missing engineering inputs, without approval.

### report_plans.py (175 lignes)
Vector plans and complete, non-overlapping physical-block detail sheets.
Imports internes : constants, project_validation
Constantes : PALETTE
- `clip_segment(a, b, bounds)` L11-21
- `scene(app)` L23-32
- `detail_tiles(panels, width, height)` L34-64
- `physical_blocks(app, panels)` L66-88 — Partition modules by physical installation zone, with no repeated IDs.
- `plate(app, panels, bounds, layer, numbered, routes, font, title, zone)` L91-156
- `vector_blocks(app, assets, routes, font)` L159-175

### report_studies.py (137 lignes)
Annual shadow study and complete spreadsheet plates for engineering reports.
Imports internes : battery_dispatch, energy_engine, mixins.spreadsheet_tools, project_validation, shadow_engine
- `annual_shadow(app, progress)` L7-40 — Integrate every real hour of the study year using the existing solar model.
- `shadow_blocks(app, assets, progress)` L43-89
- `spreadsheet_blocks(app, assets)` L92-111
- `refresh_report_energy(app, progress)` L114-137 — Recalculate the frozen report snapshot when profiles/inputs are complete.

### self_consumption.py (285 lignes)
Profili orari e bilancio FV/utenza. Nessuna batteria nel calcolo.
Imports internes : engineering_inputs, shading_models
- `orientation_key(orientation)` L12-13
- `read_open_meteo_json(path, profile, timezone)` L16-69 — Allinea meteo storico Open-Meteo alle 24 colonne locali per giorno.
- `read_daily_excel(path, imputation)` L72-118 — Legge il formato Volfrigo: data, giorno, colonne 0..23 in kWh.
- `timestamps(profile)` L121-135
- `production_from_program(app, profile, ac_factor, progress, weather)` L138-228 — Usa gli stessi metodi di energia, sole e ombra del programma.
- `balance(profile, pv_kwh, export_limit_kw)` L231-257
- `write_hourly_csv(path, result)` L260-265
- `read_hourly_csv(path, timezone)` L268-285

### shading_models.py (48 lignes)
Geometric optical loss for overlapping obstacles; optional bypass approximation.
- `attenuation(fraction, settings)` L4-9
- `optical_area(layers)` L11-48 — Integrate 1-product(transmission) on polygon union, without double counting.

### shadow_engine.py (62 lignes)
Cancellable geometric shading integration; no Tk access from the worker.
Imports internes : shading_models
- `calculate(app, intervals, report, timezone)` L5-30
- `make_shadow_sampler(app)` L33-62 — Cache static module geometry and reject disjoint shadow bounds exactly.

### single_line_516.py (263 lignes)
Preliminary AC/DC single-line drawing derived from the active PV project.
Imports internes : project_validation
Constantes : INVERTER, BATTERY
- `route_is_current(data, sid)` L18-51
- `build_model(data, batteries)` L54-106
- `write_svg(model, path, language)` L109-263 — One drawing with site one-line and exact string-to-MPPT schedule.

### tests/test_detailed_electrical.py (63 lignes)
Ensure the exported physical connections follow the active project.
Imports internes : detailed_electrical
Constantes : PROJECT
- **class DetailedElectricalTests** L14-60
  - `setUp()` L15-16
  - `test_project_mppt_two_poles_and_dc_battery_ports()` L18-31
  - `test_two_cabinets_do_not_invent_parallel_connection()` L33-40
  - `test_stale_design_ratings_and_valid_vector_export()` L42-60

### tests/test_installation.py (77 lignes)
Imports internes : energy_economics, geometry_layout, mixins.cable_network, mixins.installation_geometry, mixins.paths_tools, mixins.shadow_geometry, single_line_516
- **class Geometry** L8-9
- `surface(x1, x2, h)` L11-12
- **class InstallationTests** L14-59
  - `test_bridge_keeps_upstream_height_and_counts_single_step()` L15-22
  - `test_bridge_across_several_polyline_segments()` L24-27
  - `test_missing_and_conflicting_height_rejected()` L29-31
  - `test_no_shadow_height_fallback()` L33-35
  - `test_rotated_grid_containment_adjacency_and_area()` L37-50
  - `test_panel_centre_matches_rotated_corners()` L52-56
  - `test_legacy_cable_plan_is_not_current()` L58-59
- **class PeriodTests** L61-66
  - `test_payback_requires_complete_anniversary_period()` L62-66
- **class TrayProjectionTests** L68-77
  - `test_two_projections_on_same_tray_use_direct_interval()` L69-77

### tests/test_r11.py (108 lignes)
Imports internes : battery_dispatch, bess_charts, diagram_layout, mixins.diagram_editor, mixins.installation_geometry, report_plans, toolbar_icons
- **class Canvas** L11-20
  - `__init__()` L12-12
  - `canvasx(x)` L13-13
  - `canvasy(y)` L14-14
  - `scan_mark()` L15-15
  - `scan_dragto()` L16-16
  - `configure()` L17-17
  - `delete()` L18-18
  - `create_rectangle()` L19-19
  - `create_line()` L20-20
- **class Editor** L22-33
  - `__init__()` L23-26
  - `_get_active_tab_index()` L27-27
  - `_diagram_node_size(k)` L28-28
  - `_hit_test_diagram_node(x, y)` L29-32
  - `draw_grid()` L33-33
- `event(x, y, state)` L35-35
- **class R11Tests** L37-108
  - `test_left_drag_pans_and_never_moves_blocks()` L38-41
  - `test_right_marquee_then_group_drag_respects_zoom_and_scrolling()` L43-47
  - `test_large_electrical_blocks_and_distance_lanes_never_overlap()` L49-66
  - `test_daily_balances_and_soc_boundaries()` L68-76
  - `test_detail_atlas_covers_every_module_with_readable_ids()` L78-85
  - `test_line_icons_are_images_not_unicode_glyphs()` L87-89
  - `test_dimensions_are_black_double_arrows_without_dots_or_dashes()` L91-99
  - `test_energy_axes_include_full_stacked_totals()` L101-108

### tests/test_r12.py (67 lignes)
Imports internes : mixins.material_tools, mixins.string_sizing, project_validation
Constantes : PARAMS, SPEC
- **class SizingTests** L8-53
  - `test_each_string_uses_actual_loop_and_own_module_count()` L9-18
  - `test_no_generic_fallback_for_missing_equipment()` L20-24
  - `test_invalid_mass_and_operating_values_are_unknown()` L26-32
  - `test_parameters_recalculate_without_mutating_saved_route()` L34-38
  - `test_total_is_unknown_when_any_active_string_is_missing()` L40-50
  - `test_global_weight_alias()` L52-53
- **class GlobalMassTests** L55-67
  - `test_weight_is_available_in_material_and_custom_formulas()` L56-67

### tests/test_r13.py (184 lignes)
Regression tests for persistence, geometry, energy boundaries and new palette.
Imports internes : async_jobs, battery_dispatch, bess_charts, detailed_electrical, energy_economics, engineering_inputs, mixins.installation_geometry, mixins.shadow_geometry, mixins.string_sizing, plan_renderer, project_store, self_consumption, shading_models, zone_registry
Constantes : ROOT
- **class Geometry** L25-31
  - `_invalidate_cable_routes()` L26-26
  - `_update_string_listbox()` L27-27
  - `_update_zone_combo()` L28-28
  - `_update_zone_entries_from_active()` L29-29
  - `draw_grid()` L30-30
  - `_clean_deleted_panels_from_strings()` L31-31
- `geometry()` L33-40
- `energy_app()` L42-50
- **class PersistenceTests** L52-85
  - `test_legacy_projects_keep_panel_ids_and_all_memberships()` L53-58
  - `test_atomic_failure_keeps_previous_project_and_image()` L59-65
  - `test_backups_and_content_named_image()` L66-71
  - `test_schema_and_nonfinite_inputs_rejected()` L72-77
  - `test_invalid_polygon_rejected()` L78-81
  - `test_equipment_link_reads_current_sheet()` L82-85
- **class GeometryTests** L87-106
  - `test_deleting_first_zone_preserves_second_geometry_and_string()` L88-91
  - `test_moved_zone_detaches_only_affected_string()` L92-96
  - `test_range_expands_above_100_without_collision()` L97-100
  - `test_gap_reduces_grid_and_preserves_module_area()` L101-103
  - `test_exclusions_reject_intersecting_panels()` L104-106
- **class EnergyTests** L108-147
  - `test_clipping_is_per_inverter()` L109-111
  - `test_no_assumed_125_kw_limit()` L112-115
  - `test_unconnected_modules_are_blocked()` L116-118
  - `test_stale_weather_is_blocked()` L119-122
  - `test_explicit_timestamp_dst_has_23_or_25_hours()` L123-128
  - `test_auxiliary_balance_and_hourly_export()` L129-137
  - `test_initial_stored_energy_is_not_credited_as_pv()` L138-143
  - `test_design_fingerprint_covers_geometry_routing_and_override()` L144-147
- **class ModelTests** L149-182
  - `test_overlap_is_not_double_counted()` L150-155
  - `test_bypass_model_is_explicit()` L156-158
  - `test_additional_cable_inventory_is_counted()` L159-163
  - `test_chosen_section_and_ampacity_are_checked()` L164-166
  - `test_worker_cancellation_does_not_return_success()` L167-173
  - `test_palette_is_vivid_and_categories_distinguishable()` L174-177
  - `test_full_plan_export_contains_offscreen_extent()` L178-182

### tests/test_r14.py (183 lignes)
R14 regression: questionnaire, every-tab history and actual frozen PDF class.
Imports internes : async_jobs, configuration_form, constants, diagram_layout, energy_engine, engineering_report, mixins.safe_project, report_plans, report_studies, shadow_engine, toolbar_icons
Constantes : ROOT, PROJECT
- `questionnaire_values(data, descriptors)` L25-34
- **class History** L36-46
  - `__init__()` L37-41
  - `_capture_cable_inputs()` L42-42
  - `_collect_project_data()` L43-43
  - `_apply_document(data, path)` L44-44
  - `_refresh_energy_workspace()` L45-45
  - `draw_grid()` L46-46
- **class QuestionnaireTests** L48-73
  - `test_all_attached_projects_questionnaire_roundtrip()` L49-63
  - `test_invalid_questionnaire_is_atomic()` L64-69
  - `test_choice_and_nonfinite_point_validation()` L70-73
- **class HistoryTests** L75-118
  - `test_undo_redo_for_each_tab_and_each_document_domain()` L76-81
  - `test_history_capture_keeps_uncommitted_widget_text()` L82-87
  - `test_unchanged_hourly_profiles_shared_between_history_states()` L89-94
  - `test_undo_preserves_source_image_and_view()` L96-100
  - `test_redo_invalidated_after_branch_edit()` L101-104
  - `test_buttons_available_for_all_ten_tabs()` L105-118
- **class ReportTests** L120-183
  - `test_real_app_frozen_image_export_and_all_requested_sections()` L121-143
  - `test_full_year_uses_real_hours_and_energy_weighted_loss()` L144-156
  - `test_cached_shadow_geometry_matches_original_with_overlapping_obstacles()` L157-165
  - `test_annual_study_cancellation_propagates()` L167-171
  - `test_string_palette_shared_and_bicolour()` L172-174
  - `test_distinct_primary_actions_have_distinct_icon_rasters()` L175-178
  - `test_natural_order_and_grouped_inverters()` L179-183

### tests/test_regressions.py (121 lignes)
Imports internes : battery_dispatch, energy_economics, mixins.spreadsheet_interactions, project_validation, self_consumption, single_line_516
Constantes : ROOT
- **class Regressions** L16-119
  - `test_all_supplied_projects()` L17-32
  - `test_generated_links_ignore_stale_manual_wiring()` L34-41
  - `test_orphans_numbering_and_coordinates()` L43-49
  - `test_portable_image_alias()` L51-54
  - `test_storage_before_export_curtailment_and_shared_power()` L56-68
  - `test_export_zero_and_invalid()` L70-75
  - `test_economics_net_cost_and_foregone_exports()` L77-85
  - `test_all_site_diagram_exports()` L87-97
  - `test_missing_specs_are_not_validated()` L99-103
  - `test_saved_french_formulas_migrate_without_touching_plain_text()` L105-115
  - `test_dragged_formula_moves_cell_references_only()` L117-119

### tests/test_technical_reference.py (26 lignes)
Protect the revised solar-year and displayed technical formulas.
Imports internes : home_reference, mixins.shadow_energy
- **class TechnicalReferenceTests** L9-23
  - `test_dated_solar_position_uses_leap_year_when_requested()` L10-14
  - `test_all_home_equations_render()` L16-23

### toolbar_icons.py (179 lignes)
Original monochrome line icons, drawn from geometric primitives (no glyphs).
Constantes : ICONS, DESCRIPTIONS, COMPOSITES, ACTION_ICONS
- `plain(text)` L36-37
- `icon_key(label)` L39-46
- `raster(key, size, color)` L48-57
- `_composite(base, badge)` L118-125
- `icon_key(label)` L175-177

### user_guide.py (128 lignes)
Expanded desktop workflow adapted from the supplied earlier tutorial.
Constantes : WORKFLOWS

### zone_registry.py (19 lignes)
Persistent zone coordinate ranges; migrate only when a range must grow.
- `allocate_ranges(zones, specs, remap)` L4-19
