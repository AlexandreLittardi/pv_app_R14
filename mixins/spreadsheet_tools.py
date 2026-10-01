"""Feuille de calcul type tableur (façon Google Sheets simplifié) affichée
DANS LA ZONE PRINCIPALE (canvas_frame), pour l'onglet "Matériel" uniquement.

Contrairement à la Fiche Matériel structurée (mixins/material_tools.py,
affichée dans le panneau latéral de droite), cette feuille est une grille
libre de cellules A1, B2, ... dessinées nativement sur un tk.Canvas
(rectangles + texte), avec en-têtes de lignes/colonnes qui restent visibles
pendant le défilement, sélection de cellule à la souris ou au clavier
(flèches, Tab, Entrée) et édition via un Entry flottant superposé à la
cellule sélectionnée.

Le moteur de formules supporte + - * / % ** et les parenthèses, la
référence à d'autres cellules ("=C3*B2"), les sommes de plage
("=SOMME(A1:A10)") et les variables globales du projet (NB_MODULES,
NB_STRINGS, NB_ONDULEURS, PUISSANCE_TOTALE_WC, COURANT_A, TENSION_V,
LONGUEUR_M, RESISTIVITE, CHUTE_CIBLE_PCT).

Persistance : self.material_spreadsheet = {"rows": int, "cols": int,
"cells": {"A1": "12", "B1": "=A1*2", ...}}. Voir default_spreadsheet_state()
et le câblage dans project_io.py (save_project / _load_project_file), qui
utilise déjà ces noms et n'a pas besoin d'être modifié.

Intégration (déjà faite dans app.py) :
  1. from mixins.spreadsheet_tools import SpreadsheetToolsMixin
  2. SpreadsheetToolsMixin ajouté aux classes de base de PVLayoutRibbonApp
  3. self._init_spreadsheet_state() appelé dans __init__, AVANT
     self._build_ribbon_ui() / self._build_main_area()
  4. mixins/zone_tools.py : _build_main_area() construit la zone
     (self.spreadsheet_frame, non empaquetée au départ) juste après
     self.canvas ; _on_ribbon_tab_changed() bascule l'affichage entre
     self.canvas et self.spreadsheet_frame selon l'onglet actif, sans
     toucher au fonctionnement des autres onglets.
"""

import ast
import csv
import math
import operator
import re

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

DEFAULT_ROWS = 20
DEFAULT_COLS = 8
MAX_ROWS = 200
MAX_COLS = 52  # A..Z puis AA..AZ

_CELL_REF_RE = re.compile(r"^([A-Za-z]+)([0-9]+)$")
_COLON_RANGE_RE = re.compile(r"([A-Za-z]+[0-9]+)\s*:\s*([A-Za-z]+[0-9]+)")
_RANGE_TOKEN_RE = re.compile(r"^([A-Za-z]+[0-9]+)_RANGE_([A-Za-z]+[0-9]+)$")

_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


# ============================================================
# ADRESSAGE DE CELLULES (A1, B2, ...)
# ============================================================

def col_letter(index):
    """0 -> 'A', 25 -> 'Z', 26 -> 'AA' ..."""
    letters = ""
    index += 1
    while index > 0:
        index, rem = divmod(index - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def col_index(letters):
    """'A' -> 0, 'Z' -> 25, 'AA' -> 26 ..."""
    idx = 0
    for ch in letters.upper():
        idx = idx * 26 + (ord(ch) - 64)
    return idx - 1


def cell_id(row, col):
    """(0, 0) -> 'A1' (row/col 0-indexés)."""
    return f"{col_letter(col)}{row + 1}"


def parse_cell_id(ref):
    """'C3' -> (2, 2) (row, col 0-indexés), ou None si ce n'est pas une
    référence de cellule valide."""
    m = _CELL_REF_RE.match(ref.strip())
    if not m:
        return None
    return int(m.group(2)) - 1, col_index(m.group(1))


def _to_number(raw):
    """Convertit une valeur brute de cellule en float si possible, sinon la
    laisse telle quelle (texte)."""
    if raw is None:
        return ""
    s = str(raw).strip()
    if s == "":
        return ""
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return s


def default_spreadsheet_state():
    """Structure par défaut (utilisée à l'init de l'app et au chargement
    d'un projet ne contenant pas encore de feuille de calcul)."""
    return {"rows": DEFAULT_ROWS, "cols": DEFAULT_COLS, "cells": {},
            "col_widths": [], "row_heights": []}


# ============================================================
# MOTEUR DE FORMULES
# ============================================================

class _FormulaError(Exception):
    pass


def _eval_formula_ast(expr, cell_lookup, variables):
    """Évalue en toute sécurité une formule : + - * / % ** parenthèses,
    références de cellules (C3), plages (SOMME(A1:A10)) et variables
    numériques nommées."""
    # "A1:B5" n'est pas une syntaxe Python valide -> transformée en un
    # identifiant "A1_RANGE_B5" avant de parser, reconnu spécifiquement
    # ci-dessous.
    safe_expr = _COLON_RANGE_RE.sub(lambda m: f"{m.group(1)}_RANGE_{m.group(2)}", expr)
    tree = ast.parse(safe_expr, mode="eval")

    def _eval(node):
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
                return node.value
            raise _FormulaError('Unsupported constant')
        if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
            return _BINOPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
            return _UNARY[type(node.op)](_eval(node.operand))
        if isinstance(node, ast.Name):
            range_m = _RANGE_TOKEN_RE.match(node.id)
            if range_m:
                start = parse_cell_id(range_m.group(1))
                end = parse_cell_id(range_m.group(2))
                if start is None or end is None:
                    raise _FormulaError(f"Invalid range: {node.id}")
                r0, c0 = start
                r1, c1 = end
                total = 0.0
                for r in range(min(r0, r1), max(r0, r1) + 1):
                    for c in range(min(c0, c1), max(c0, c1) + 1):
                        v = cell_lookup(r, c)
                        if v == '#CIRC!':
                            raise _FormulaError('#CIRC!')
                        if isinstance(v, (int, float)) and not isinstance(v, bool):
                            total += v
                return total
            ref = parse_cell_id(node.id)
            if ref is not None:
                v = cell_lookup(*ref)
                if v == '#CIRC!':
                    raise _FormulaError('#CIRC!')
                if v == "":
                    return 0.0  # cellule vide référencée -> traitée comme 0
                if not isinstance(v, (int, float)) or isinstance(v, bool):
                    raise _FormulaError(f"« {node.id}” is not numeric")
                return v
            if node.id in variables:
                val = variables[node.id]
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                    raise _FormulaError(f"« {node.id}” is not numeric")
                return val
            raise _FormulaError(f"Unknown reference: {node.id}")
        if isinstance(node, ast.Call):
            fname = getattr(node.func, "id", None)
            if fname not in ("SOMME", "SUM"):
                raise _FormulaError('Only SUM() is supported')
            if len(node.args) != 1:
                raise _FormulaError('SUM() expects a range, e.g. SUM(A1:A10)')
            return _eval(node.args[0])
        raise _FormulaError('Unsupported expression')

    return _eval(tree)


class SpreadsheetToolsMixin:
    # ========================================================
    # ÉTAT
    # ========================================================

    def _init_spreadsheet_state(self):
        self.material_spreadsheet = default_spreadsheet_state()

        self.spreadsheet_cell_items = {}
        self.spreadsheet_selection_rect = None
        self.spreadsheet_selected = None

        self.spreadsheet_editing_cell = None
        self.spreadsheet_edit_entry = None
        self.spreadsheet_edit_window_id = None

        self.spreadsheet_cell_w = 100
        self.spreadsheet_cell_h = 26
        self.spreadsheet_zoom_level = 1.0
        self.spreadsheet_header_w = 50
        self.spreadsheet_header_h = 26

        # Redimensionnement colonnes/lignes (drag sur bordure d'en-tête)
        self.spreadsheet_resize_col = None
        self.spreadsheet_resize_row = None
        self.spreadsheet_resize_start_px = None
        self.spreadsheet_resize_start_size = None

    # ========================================================
    # VARIABLES DU PROJET UTILISABLES DANS LES FORMULES
    # ========================================================

    def _get_spreadsheet_variables(self):
        """Variables numériques disponibles dans les formules, en plus des
        références de cellules : les variables globales de la fiche
        matériel (NB_MODULES, ...) si disponibles (MaterialToolsMixin), et
        les paramètres du calcul de câblage de la side-bar Notes
        (COURANT_A, TENSION_V, LONGUEUR_M, RESISTIVITE, CHUTE_CIBLE_PCT)."""
        variables = {}
        get_material_vars = getattr(self, "_get_material_global_vars", None)
        if callable(get_material_vars):
            try:
                from project_validation import FORMULA_ALIASES
                variables.update({name:value for name,value in get_material_vars().items()
                                  if name not in FORMULA_ALIASES})
            except Exception:
                pass
        
        variables.update(self._get_zone_string_insert_vars()) 

        # The average uses clear-sky plane-of-array irradiance during daylight
        # on the selected solar date (hourly samples). It is not a weather forecast.
        coords = list(getattr(self, 'panels', {}) or {}) or [None]
        def mean_plane_irradiance(elevation, azimuth):
            return sum(self._get_clear_sky_poa_irradiance(elevation, azimuth, coord)
                       for coord in coords) / len(coords)

        try:
            elevation, azimuth = self._compute_solar_position(
                self.solar_latitude, self.solar_longitude,
                self.solar_day, self.solar_month, self.solar_hour,
                self.solar_utc_offset)
            current_irradiance = mean_plane_irradiance(elevation, azimuth) if elevation > 0.1 else 0.0
            daylight_values = []
            for hour in range(24):
                elevation, azimuth = self._compute_solar_position(
                    self.solar_latitude, self.solar_longitude,
                    self.solar_day, self.solar_month, hour + 0.5,
                    self.solar_utc_offset)
                if elevation > 0.1:
                    daylight_values.append(mean_plane_irradiance(elevation, azimuth))
            daylight_average = sum(daylight_values) / len(daylight_values) if daylight_values else 0.0
        except (AttributeError, ValueError, ZeroDivisionError):
            current_irradiance = daylight_average = 0.0

        current_shadow=not hasattr(self,'_shadow_current') or self._shadow_current()
        shade = (getattr(self, 'shadow_result', {}) or {}) if current_shadow else {}
        shade_pct = shade.get('shadow_pct', {}) or {}
        mean_shade = sum(shade_pct.get(c, 0.0) for c in coords if c is not None) / max(1, len(coords))
        simulation = (getattr(self, 'shadow_simulation_results', {}) or {}) if current_shadow else {}
        variables.update({
            'IRRADIANCE_NOW_W_M2': current_irradiance,
            'IRRADIANCE_AVG_W_M2': daylight_average,
            'SHADOW_AVG_PCT': mean_shade,
            'SIM_LOSS_KWH': float(simulation.get('total_lost_wh', 0.0)) / 1000.0,
            'SIM_PRODUCTION_KWH': sum(float(item.get('energy_shaded_wh', 0.0))
                                      for item in simulation.get('results', [])) / 1000.0,
            'PANEL_AREA_M2': len(getattr(self, 'panels', {}))
                             * self.panel_width_mm * self.panel_height_mm / 1000000.0,
        })

        if not current_shadow:
            for key in ('SHADOW_AVG_PCT','SIM_LOSS_KWH','SIM_PRODUCTION_KWH'):variables.pop(key,None)

        cable_params = getattr(self, "cable_calc_params", None)
        if isinstance(cable_params, dict):
            mapping = {
                "current_a": "CURRENT_A",
                "voltage_v": "VOLTAGE_V",
                "length_m": "LENGTH_M",
                "resistivity": "RESISTIVITY",
                "target_drop_pct": "TARGET_DROP_PCT",
            }
            for src_key, var_name in mapping.items():
                if src_key in cable_params:
                    try:
                        variables[var_name] = float(cable_params[src_key])
                    except (TypeError, ValueError):
                        pass

        if hasattr(self, '_cable_mass_summary'):
            mass = self._cable_mass_summary()
            variables['CABLE_WEIGHT_MISSING_STRINGS'] = mass['missing']
            if mass['total_kg'] is not None:
                variables['TOTAL_CABLE_WEIGHT_KG'] = mass['total_kg']

        return variables

    def _refresh_variable_explorer(self):
        if not hasattr(self, 'variable_tree'):
            return
        tree = self.variable_tree
        children = tree.get_children()
        if children:
            tree.delete(*children)
        query = self.variable_search.get().strip().lower()
        variables = self._get_spreadsheet_variables()
        groups = {'Project': [], 'Irradiance & shadow': [], 'Zones': [],
                  'Strings': [], 'Cabling': []}
        for name, value in sorted(variables.items()):
            if query and query not in name.lower():
                continue
            if name.startswith('ZONE'):
                group = 'Zones'
            elif name.startswith('STRING') and name != 'STRING_COUNT':
                group = 'Strings'
            elif name in ('CURRENT_A', 'VOLTAGE_V', 'LENGTH_M', 'RESISTIVITY', 'TARGET_DROP_PCT'):
                group = 'Cabling'
            elif name.startswith(('IRRADIANCE_', 'SHADOW_', 'SIM_')):
                group = 'Irradiance & shadow'
            else:
                group = 'Project'
            groups[group].append((name, value))
        for group, members in groups.items():
            if not members:
                continue
            parent = tree.insert('', tk.END, text=f'{group} ({len(members)})', open=True)
            for name, value in members:
                display = f'{value:.3f}' if isinstance(value, (int, float)) else str(value)
                tree.insert(parent, tk.END, iid=f'variable::{name}', text=name, values=(display,))

    def _insert_selected_variable(self):
        selection = self.variable_tree.selection()
        if selection and selection[0].startswith('variable::'):
            self._insert_spreadsheet_variable(selection[0].split('::', 1)[1])

    # ========================================================
    # CALCUL DES FORMULES
    # ========================================================

    def _compute_spreadsheet_values(self):
        """Calcule toutes les cellules de la feuille de calcul. Retourne
        {(row, col): valeur} où valeur est un float, une chaîne (texte
        brut, cellule non-formule) ou "#ERR"/"#CIRC!" en cas d'erreur ou
        de référence circulaire."""
        variables = self._get_spreadsheet_variables()
        cells = self.material_spreadsheet.get("cells", {})
        cache = {}
        visiting = set()

        def eval_cell(row, col):
            key = (row, col)
            if key in cache:
                return cache[key]
            raw = cells.get(cell_id(row, col), "")
            raw_str = "" if raw is None else str(raw)
            if not raw_str.strip().startswith("="):
                cache[key] = _to_number(raw_str)
                return cache[key]
            if key in visiting:
                cache[key] = "#CIRC!"
                return cache[key]
            visiting.add(key)
            try:
                cache[key] = _eval_formula_ast(raw_str.strip()[1:], eval_cell, variables)
            except Exception as exc:
                cache[key] = "#CIRC!" if str(exc) == '#CIRC!' else "#ERR"
            finally:
                visiting.discard(key)
            return cache[key]

        rows = self.material_spreadsheet.get("rows", DEFAULT_ROWS)
        cols = self.material_spreadsheet.get("cols", DEFAULT_COLS)
        for r in range(rows):
            for c in range(cols):
                eval_cell(r, c)

        return cache

    @staticmethod
    def _format_spreadsheet_value(value):
        if isinstance(value, float):
            if not math.isfinite(value):
                return '#ERR'
            if value == int(value):
                return str(int(value))
            return f"{value:.4f}".rstrip("0").rstrip(".")
        return "" if value is None else str(value)

    # ========================================================
    # CONSTRUCTION DE L'INTERFACE (Canvas, zone principale)
    # ========================================================

    def _build_material_spreadsheet_area(self):
        """Construit la grille de calcul dessinée nativement sur un Canvas
        (façon tableur), à l'intérieur de canvas_frame. N'est PAS empaquetée
        ici : self.spreadsheet_frame reste non géré (invisible) jusqu'à ce
        que l'onglet "Matériel" soit actif — voir _on_ribbon_tab_changed
        dans mixins/zone_tools.py, qui bascule avec self.canvas."""
        self.spreadsheet_frame = ttk.Frame(self.canvas_frame)
        # Pas de .pack() ici : géré par _on_ribbon_tab_changed.

        formula_bar = ttk.Frame(self.spreadsheet_frame, padding=(4, 4))
        formula_bar.pack(side=tk.TOP, fill=tk.X)
        self.spreadsheet_address_var = tk.StringVar(value='A1')
        self.spreadsheet_formula_var = tk.StringVar()
        ttk.Label(formula_bar, textvariable=self.spreadsheet_address_var,
                  font=('Arial', 10, 'bold'), width=7).pack(side=tk.LEFT)
        ttk.Label(formula_bar, text='ƒx', font=('Arial', 11, 'bold')).pack(side=tk.LEFT, padx=(4, 7))
        self.spreadsheet_formula_entry = ttk.Entry(formula_bar, textvariable=self.spreadsheet_formula_var)
        self.spreadsheet_formula_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.spreadsheet_formula_entry.bind('<Return>', self._apply_spreadsheet_formula_bar)
        ttk.Button(formula_bar, text='Apply', command=self._apply_spreadsheet_formula_bar).pack(side=tk.LEFT, padx=5)

        grid_container = ttk.Frame(self.spreadsheet_frame)
        grid_container.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        grid_container.rowconfigure(1, weight=1)
        grid_container.columnconfigure(1, weight=1)

        corner = tk.Canvas(
            grid_container, width=self.spreadsheet_header_w, height=self.spreadsheet_header_h,
            bg="#37474F", highlightthickness=0
        )
        corner.grid(row=0, column=0, sticky="nsew")

        self.spreadsheet_colheader_canvas = tk.Canvas(
            grid_container, height=self.spreadsheet_header_h, bg="#37474F", highlightthickness=0
        )
        self.spreadsheet_colheader_canvas.grid(row=0, column=1, sticky="ew")

        self.spreadsheet_rowheader_canvas = tk.Canvas(
            grid_container, width=self.spreadsheet_header_w, bg="#37474F", highlightthickness=0
        )
        self.spreadsheet_rowheader_canvas.grid(row=1, column=0, sticky="ns")
            
        self.spreadsheet_colheader_canvas.bind("<Motion>", self._on_spreadsheet_colheader_motion)
        self.spreadsheet_colheader_canvas.bind("<Button-1>", self._on_spreadsheet_colheader_press)
        self.spreadsheet_colheader_canvas.bind("<B1-Motion>", self._on_spreadsheet_colheader_drag)
        self.spreadsheet_colheader_canvas.bind("<ButtonRelease-1>", self._on_spreadsheet_colheader_release)

        self.spreadsheet_rowheader_canvas.bind("<Motion>", self._on_spreadsheet_rowheader_motion)
        self.spreadsheet_rowheader_canvas.bind("<Button-1>", self._on_spreadsheet_rowheader_press)
        self.spreadsheet_rowheader_canvas.bind("<B1-Motion>", self._on_spreadsheet_rowheader_drag)
        self.spreadsheet_rowheader_canvas.bind("<ButtonRelease-1>", self._on_spreadsheet_rowheader_release)
        
        self.spreadsheet_data_canvas = tk.Canvas(
            grid_container, bg="white", highlightthickness=1, highlightbackground="#B0BEC5"
        )
        self.spreadsheet_data_canvas.grid(row=1, column=1, sticky="nsew")

        vbar = ttk.Scrollbar(grid_container, orient=tk.VERTICAL, command=self.spreadsheet_data_canvas.yview)
        vbar.grid(row=1, column=2, sticky="ns")
        hbar = ttk.Scrollbar(grid_container, orient=tk.HORIZONTAL, command=self.spreadsheet_data_canvas.xview)
        hbar.grid(row=2, column=1, sticky="ew")
        self.spreadsheet_vbar = vbar
        self.spreadsheet_hbar = hbar

        self.spreadsheet_data_canvas.configure(
            yscrollcommand=self._on_spreadsheet_data_yscroll,
            xscrollcommand=self._on_spreadsheet_data_xscroll,
            yscrollincrement=10,
            xscrollincrement=10,
        )

        # ------------------------------------------------
        # Souris
        # ------------------------------------------------
        self.spreadsheet_data_canvas.bind("<Button-1>", self._on_spreadsheet_cell_click)
        self.spreadsheet_data_canvas.bind("<Double-Button-1>", self._on_spreadsheet_cell_double_click)
        self.spreadsheet_data_canvas.bind("<MouseWheel>", self._on_spreadsheet_mousewheel)
        self.spreadsheet_data_canvas.bind("<Shift-MouseWheel>", self._on_spreadsheet_mousewheel_shift)
        self.spreadsheet_data_canvas.bind("<Button-4>", lambda e: self.spreadsheet_data_canvas.yview_scroll(-1, "units"))
        self.spreadsheet_data_canvas.bind("<Button-5>", lambda e: self.spreadsheet_data_canvas.yview_scroll(1, "units"))

        # ------------------------------------------------
        # Clavier (navigation + édition façon tableur)
        # ------------------------------------------------
        self.spreadsheet_data_canvas.bind("<Up>", lambda e: self._spreadsheet_move_selection(-1, 0))
        self.spreadsheet_data_canvas.bind("<Down>", lambda e: self._spreadsheet_move_selection(1, 0))
        self.spreadsheet_data_canvas.bind("<Left>", lambda e: self._spreadsheet_move_selection(0, -1))
        self.spreadsheet_data_canvas.bind("<Right>", lambda e: self._spreadsheet_move_selection(0, 1))
        self.spreadsheet_data_canvas.bind("<Tab>", lambda e: self._spreadsheet_move_selection(0, 1))
        self.spreadsheet_data_canvas.bind("<Return>", self._on_spreadsheet_key_return)
        self.spreadsheet_data_canvas.bind("<F2>", self._on_spreadsheet_key_return)
        self.spreadsheet_data_canvas.bind("<Delete>", self._on_spreadsheet_key_delete)
        self.spreadsheet_data_canvas.bind("<BackSpace>", self._on_spreadsheet_key_delete)
        self.spreadsheet_data_canvas.bind("<Key>", self._on_spreadsheet_key_type)

        self._rebuild_spreadsheet_grid()

    def _on_spreadsheet_data_yscroll(self, first, last):
        self.spreadsheet_vbar.set(first, last)
        self.spreadsheet_rowheader_canvas.yview_moveto(first)

    def _on_spreadsheet_data_xscroll(self, first, last):
        self.spreadsheet_hbar.set(first, last)
        self.spreadsheet_colheader_canvas.xview_moveto(first)

    def _on_spreadsheet_mousewheel(self, event):
        self.spreadsheet_data_canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"

    def _on_spreadsheet_mousewheel_shift(self, event):
        self.spreadsheet_data_canvas.xview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"
    
    # ========================================================
    # DIMENSIONS PAR COLONNE / LIGNE (redimensionnement)
    # ========================================================

    _SPREADSHEET_MIN_COL_W = 30
    _SPREADSHEET_MIN_ROW_H = 16
    _SPREADSHEET_RESIZE_MARGIN = 4  # px de tolérance autour d'une bordure

    def _spreadsheet_col_w(self, c):
        widths = self.material_spreadsheet.get("col_widths", [])
        if 0 <= c < len(widths) and widths[c]:
            return max(1, round(widths[c] * self.spreadsheet_zoom_level))
        return max(1, round(self.spreadsheet_cell_w * self.spreadsheet_zoom_level))

    def _spreadsheet_row_h(self, r):
        heights = self.material_spreadsheet.get("row_heights", [])
        if 0 <= r < len(heights) and heights[r]:
            return max(1, round(heights[r] * self.spreadsheet_zoom_level))
        return max(1, round(self.spreadsheet_cell_h * self.spreadsheet_zoom_level))

    def _spreadsheet_col_x(self, c):
        return sum(self._spreadsheet_col_w(i) for i in range(c))

    def _spreadsheet_row_y(self, r):
        return sum(self._spreadsheet_row_h(i) for i in range(r))

    def _spreadsheet_set_col_w(self, c, width):
        cols = self.material_spreadsheet.get("cols", DEFAULT_COLS)
        widths = self.material_spreadsheet.setdefault("col_widths", [])
        while len(widths) < cols:
            widths.append(0)
        widths[c] = max(self._SPREADSHEET_MIN_COL_W, round(width / self.spreadsheet_zoom_level))

    def _spreadsheet_set_row_h(self, r, height):
        rows = self.material_spreadsheet.get("rows", DEFAULT_ROWS)
        heights = self.material_spreadsheet.setdefault("row_heights", [])
        while len(heights) < rows:
            heights.append(0)
        heights[r] = max(self._SPREADSHEET_MIN_ROW_H, round(height / self.spreadsheet_zoom_level))

    def _zoom_spreadsheet(self, factor):
        self._spreadsheet_commit_edit()
        self.spreadsheet_zoom_level = max(.6, min(2.5, self.spreadsheet_zoom_level * factor))
        self._rebuild_spreadsheet_grid()

    def _reset_spreadsheet_zoom(self):
        self._spreadsheet_commit_edit()
        self.spreadsheet_zoom_level = 1.0
        self._rebuild_spreadsheet_grid()

    def _spreadsheet_col_border_at(self, cx):
        """Index de la colonne dont la bordure droite passe près de cx, ou None."""
        cols = self.material_spreadsheet.get("cols", DEFAULT_COLS)
        x = 0
        for c in range(cols):
            x += self._spreadsheet_col_w(c)
            if abs(cx - x) <= self._SPREADSHEET_RESIZE_MARGIN:
                return c
        return None

    def _spreadsheet_row_border_at(self, cy):
        rows = self.material_spreadsheet.get("rows", DEFAULT_ROWS)
        y = 0
        for r in range(rows):
            y += self._spreadsheet_row_h(r)
            if abs(cy - y) <= self._SPREADSHEET_RESIZE_MARGIN:
                return r
        return None

    # --- Colonnes ---

    def _on_spreadsheet_colheader_motion(self, event):
        if self.spreadsheet_resize_col is not None:
            return
        cx = self.spreadsheet_colheader_canvas.canvasx(event.x)
        c = self._spreadsheet_col_border_at(cx)
        self.spreadsheet_colheader_canvas.config(cursor="sb_h_double_arrow" if c is not None else "")

    def _on_spreadsheet_colheader_press(self, event):
        cx = self.spreadsheet_colheader_canvas.canvasx(event.x)
        c = self._spreadsheet_col_border_at(cx)
        if c is None:
            return
        self.spreadsheet_resize_col = c
        self.spreadsheet_resize_start_px = cx
        self.spreadsheet_resize_start_size = self._spreadsheet_col_w(c)

    def _on_spreadsheet_colheader_drag(self, event):
        if self.spreadsheet_resize_col is None:
            return
        cx = self.spreadsheet_colheader_canvas.canvasx(event.x)
        delta = cx - self.spreadsheet_resize_start_px
        self._spreadsheet_set_col_w(self.spreadsheet_resize_col, self.spreadsheet_resize_start_size + delta)
        self._rebuild_spreadsheet_grid()

    def _on_spreadsheet_colheader_release(self, event):
        self.spreadsheet_resize_col = None
        self.spreadsheet_resize_start_px = None
        self.spreadsheet_resize_start_size = None

    # --- Lignes (symétrique) ---

    def _on_spreadsheet_rowheader_motion(self, event):
        if self.spreadsheet_resize_row is not None:
            return
        cy = self.spreadsheet_rowheader_canvas.canvasy(event.y)
        r = self._spreadsheet_row_border_at(cy)
        self.spreadsheet_rowheader_canvas.config(cursor="sb_v_double_arrow" if r is not None else "")

    def _on_spreadsheet_rowheader_press(self, event):
        cy = self.spreadsheet_rowheader_canvas.canvasy(event.y)
        r = self._spreadsheet_row_border_at(cy)
        if r is None:
            return
        self.spreadsheet_resize_row = r
        self.spreadsheet_resize_start_px = cy
        self.spreadsheet_resize_start_size = self._spreadsheet_row_h(r)

    def _on_spreadsheet_rowheader_drag(self, event):
        if self.spreadsheet_resize_row is None:
            return
        cy = self.spreadsheet_rowheader_canvas.canvasy(event.y)
        delta = cy - self.spreadsheet_resize_start_px
        self._spreadsheet_set_row_h(self.spreadsheet_resize_row, self.spreadsheet_resize_start_size + delta)
        self._rebuild_spreadsheet_grid()

    def _on_spreadsheet_rowheader_release(self, event):
        self.spreadsheet_resize_row = None
        self.spreadsheet_resize_start_px = None
        self.spreadsheet_resize_start_size = None
    # ========================================================
    # (RE)CONSTRUCTION DE LA GRILLE
    # ========================================================

    def _rebuild_spreadsheet_grid(self):
        """(Re)dessine entièrement la grille (après ajout/suppression de
        lignes/colonnes, ou chargement d'un projet). Point d'entrée public :
        nom conservé, appelé par project_io.py après chargement d'un projet."""
        if not hasattr(self, "spreadsheet_data_canvas"):
            return

        self._spreadsheet_cancel_edit()

        data = self.spreadsheet_data_canvas
        colhdr = self.spreadsheet_colheader_canvas
        rowhdr = self.spreadsheet_rowheader_canvas
        data.delete("all")
        colhdr.delete("all")
        rowhdr.delete("all")
        self.spreadsheet_cell_items = {}
        self.spreadsheet_selection_rect = None

        rows = self.material_spreadsheet.get("rows", DEFAULT_ROWS)
        cols = self.material_spreadsheet.get("cols", DEFAULT_COLS)

        col_x = [0]
        for c in range(cols):
            col_x.append(col_x[-1] + self._spreadsheet_col_w(c))
        row_y = [0]
        for r in range(rows):
            row_y.append(row_y[-1] + self._spreadsheet_row_h(r))

        total_w = max(col_x[-1], 1)
        total_h = max(row_y[-1], 1)

        data.configure(scrollregion=(0, 0, total_w, total_h))
        colhdr.configure(scrollregion=(0, 0, total_w, self.spreadsheet_header_h))
        rowhdr.configure(scrollregion=(0, 0, self.spreadsheet_header_w, total_h))

        for c in range(cols):
            x0, x1 = col_x[c], col_x[c + 1]
            colhdr.create_rectangle(x0, 0, x1, self.spreadsheet_header_h, fill="#37474F", outline="#263238")
            colhdr.create_text(
                (x0 + x1) / 2, self.spreadsheet_header_h / 2, text=col_letter(c),
                fill="white", font=("Arial", max(8, round(9 * self.spreadsheet_zoom_level)), "bold")
            )

        for r in range(rows):
            y0, y1 = row_y[r], row_y[r + 1]
            rowhdr.create_rectangle(0, y0, self.spreadsheet_header_w, y1, fill="#37474F", outline="#263238")
            rowhdr.create_text(
                self.spreadsheet_header_w / 2, (y0 + y1) / 2, text=str(r + 1),
                fill="white", font=("Arial", max(8, round(9 * self.spreadsheet_zoom_level)), "bold")
            )

        for r in range(rows):
            y0, y1 = row_y[r], row_y[r + 1]
            for c in range(cols):
                x0, x1 = col_x[c], col_x[c + 1]
                rect_id = data.create_rectangle(x0, y0, x1, y1, fill="white", outline="#CFD8DC")
                text_id = data.create_text(
                    x1 - 5, (y0 + y1) / 2, text="", anchor="e",
                    font=("Arial", max(8, round(9 * self.spreadsheet_zoom_level))), fill="black"
                )
                self.spreadsheet_cell_items[(r, c)] = (rect_id, text_id)

        if self.spreadsheet_selected is None or not (
            0 <= self.spreadsheet_selected[0] < rows and 0 <= self.spreadsheet_selected[1] < cols
        ):
            self.spreadsheet_selected = (0, 0) if rows and cols else None

        self._draw_spreadsheet_selection()
        self._refresh_spreadsheet()

    def _refresh_spreadsheet(self):
        """Recalcule toutes les formules et met à jour l'affichage de
        chaque cellule (met juste à jour les items Canvas existants, pas
        de reconstruction complète — rapide même avec beaucoup de lignes)."""
        if not getattr(self, "spreadsheet_cell_items", None):
            return
        computed = self._compute_spreadsheet_values()
        cells = self.material_spreadsheet.get("cells", {})
        data = self.spreadsheet_data_canvas
        for (r, c), (rect_id, text_id) in self.spreadsheet_cell_items.items():
            raw = cells.get(cell_id(r, c), "")
            is_formula = isinstance(raw, str) and raw.strip().startswith("=")
            if is_formula:
                result = computed.get((r, c), "#ERR")
                display = self._format_spreadsheet_value(result)
                is_error = display in ("#ERR", "#CIRC!")
            else:
                display = "" if raw is None else str(raw)
                is_error = False
            data.itemconfigure(text_id, text=display, fill="#C62828" if is_error else "black")
            data.itemconfigure(rect_id, fill="#FFF9C4" if is_formula else "white")

    # ========================================================
    # SÉLECTION
    # ========================================================

    def _draw_spreadsheet_selection(self):
        data = self.spreadsheet_data_canvas
        if self.spreadsheet_selected is None:
            if self.spreadsheet_selection_rect is not None:
                data.itemconfigure(self.spreadsheet_selection_rect, state="hidden")
            if hasattr(self, 'spreadsheet_address_var'):
                self.spreadsheet_address_var.set('')
                self.spreadsheet_formula_var.set('')
            return
        r, c = self.spreadsheet_selected
        if hasattr(self, 'spreadsheet_address_var'):
            self.spreadsheet_address_var.set(cell_id(r, c))
            self.spreadsheet_formula_var.set(str(self.material_spreadsheet['cells'].get(cell_id(r, c), '')))
        cw, ch = self._spreadsheet_col_w(c), self._spreadsheet_row_h(r)
        x0, y0 = self._spreadsheet_col_x(c), self._spreadsheet_row_y(r)
        x1, y1 = x0 + cw, y0 + ch
        if self.spreadsheet_selection_rect is None:
            self.spreadsheet_selection_rect = data.create_rectangle(
                x0, y0, x1, y1, outline="#1565C0", width=2, fill=""
            )
        else:
            data.coords(self.spreadsheet_selection_rect, x0, y0, x1, y1)
            data.itemconfigure(self.spreadsheet_selection_rect, state="normal")
        data.tag_raise(self.spreadsheet_selection_rect)

    def _spreadsheet_ensure_visible(self, row, col):
        data = self.spreadsheet_data_canvas
        rows = self.material_spreadsheet.get("rows", DEFAULT_ROWS)
        cols = self.material_spreadsheet.get("cols", DEFAULT_COLS)
        total_w = max(sum(self._spreadsheet_col_w(i) for i in range(cols)), 1)
        total_h = max(sum(self._spreadsheet_row_h(i) for i in range(rows)), 1)

        x0, y0 = self._spreadsheet_col_x(col), self._spreadsheet_row_y(row)
        x1, y1 = x0 + self._spreadsheet_col_w(col), y0 + self._spreadsheet_row_h(row)

        view_w = data.winfo_width() or 1
        view_h = data.winfo_height() or 1

        xfrac0, xfrac1 = data.xview()
        yfrac0, yfrac1 = data.yview()
        vis_x0, vis_x1 = xfrac0 * total_w, xfrac1 * total_w
        vis_y0, vis_y1 = yfrac0 * total_h, yfrac1 * total_h

        if x0 < vis_x0:
            data.xview_moveto(x0 / total_w)
        elif x1 > vis_x1:
            data.xview_moveto(max(0.0, (x1 - view_w)) / total_w)

        if y0 < vis_y0:
            data.yview_moveto(y0 / total_h)
        elif y1 > vis_y1:
            data.yview_moveto(max(0.0, (y1 - view_h)) / total_h)

    def _spreadsheet_cell_at_event(self, event):
        data = self.spreadsheet_data_canvas
        cx = data.canvasx(event.x)
        cy = data.canvasy(event.y)
        rows = self.material_spreadsheet.get("rows", DEFAULT_ROWS)
        cols = self.material_spreadsheet.get("cols", DEFAULT_COLS)

        c, x = None, 0
        for i in range(cols):
            w = self._spreadsheet_col_w(i)
            if x <= cx < x + w:
                c = i
                break
            x += w
        r, y = None, 0
        for i in range(rows):
            h = self._spreadsheet_row_h(i)
            if y <= cy < y + h:
                r = i
                break
            y += h

        if r is not None and c is not None:
            return r, c
        return None

    def _on_spreadsheet_cell_click(self, event):
        self.spreadsheet_data_canvas.focus_set()
        cell = self._spreadsheet_cell_at_event(event)
        if cell is None:
            return
        if self.spreadsheet_editing_cell is not None and self.spreadsheet_editing_cell != cell:
            self._spreadsheet_commit_edit()
        self.spreadsheet_selected = cell
        self._draw_spreadsheet_selection()

    def _on_spreadsheet_cell_double_click(self, event):
        cell = self._spreadsheet_cell_at_event(event)
        if cell is None:
            return
        self.spreadsheet_selected = cell
        self._draw_spreadsheet_selection()
        self._spreadsheet_start_edit()

    def _spreadsheet_move_selection(self, dr, dc):
        if self.spreadsheet_editing_cell is not None:
            self._spreadsheet_commit_edit()
        rows = self.material_spreadsheet.get("rows", DEFAULT_ROWS)
        cols = self.material_spreadsheet.get("cols", DEFAULT_COLS)
        if not rows or not cols:
            return "break"
        if self.spreadsheet_selected is None:
            self.spreadsheet_selected = (0, 0)
        r, c = self.spreadsheet_selected
        r = max(0, min(rows - 1, r + dr))
        c = max(0, min(cols - 1, c + dc))
        self.spreadsheet_selected = (r, c)
        self._draw_spreadsheet_selection()
        self._spreadsheet_ensure_visible(r, c)
        return "break"

    # ========================================================
    # ÉDITION (Entry flottant superposé à la cellule sélectionnée)
    # ========================================================

    def _spreadsheet_start_edit(self, initial_text=None):
        if self.spreadsheet_selected is None:
            return
        r, c = self.spreadsheet_selected
        if self.spreadsheet_editing_cell == (r, c):
            return
        self._spreadsheet_cancel_edit()

        cw, ch = self._spreadsheet_col_w(c), self._spreadsheet_row_h(r)
        x0, y0 = self._spreadsheet_col_x(c), self._spreadsheet_row_y(r)

        raw = self.material_spreadsheet["cells"].get(cell_id(r, c), "")
        entry = tk.Entry(self.spreadsheet_data_canvas,
                         font=("Arial", max(9, round(9 * self.spreadsheet_zoom_level))),
                         relief=tk.SOLID, borderwidth=1, justify="right")
        entry.insert(0, initial_text if initial_text is not None else ("" if raw is None else str(raw)))
        entry.icursor(tk.END)

        win_id = self.spreadsheet_data_canvas.create_window(
            x0, y0, window=entry, anchor="nw", width=cw, height=ch
        )
        entry.focus_set()
        entry.bind("<Return>", lambda e: self._spreadsheet_finish_edit(move_down=True))
        entry.bind("<Escape>", lambda e: self._spreadsheet_cancel_edit())
        entry.bind("<Tab>", lambda e: (self._spreadsheet_finish_edit(move_right=True), "break")[-1])
        entry.bind("<FocusOut>", lambda e: self._spreadsheet_finish_edit())

        self.spreadsheet_editing_cell = (r, c)
        self.spreadsheet_edit_entry = entry
        self.spreadsheet_edit_window_id = win_id

    def _spreadsheet_finish_edit(self, move_down=False, move_right=False):
        if self.spreadsheet_editing_cell is None:
            return
        r, c = self.spreadsheet_editing_cell
        entry = self.spreadsheet_edit_entry
        value = entry.get().strip() if entry is not None else ""
        cid = cell_id(r, c)
        if value == "":
            self.material_spreadsheet["cells"].pop(cid, None)
        else:
            self.material_spreadsheet["cells"][cid] = value

        self._spreadsheet_destroy_edit_widget()
        self._refresh_spreadsheet()

        if move_down:
            self._spreadsheet_move_selection(1, 0)
        elif move_right:
            self._spreadsheet_move_selection(0, 1)
        else:
            self._draw_spreadsheet_selection()

    def _spreadsheet_commit_edit(self):
        """Valide la cellule en cours d'édition sans déplacer la sélection
        (utilisé quand on clique ailleurs ou qu'on quitte l'onglet)."""
        self._spreadsheet_finish_edit()

    def _spreadsheet_cancel_edit(self):
        self._spreadsheet_destroy_edit_widget()

    def _spreadsheet_destroy_edit_widget(self):
        if getattr(self, "spreadsheet_edit_window_id", None) is not None and hasattr(self, "spreadsheet_data_canvas"):
            try:
                self.spreadsheet_data_canvas.delete(self.spreadsheet_edit_window_id)
            except tk.TclError:
                pass
        if getattr(self, "spreadsheet_edit_entry", None) is not None:
            try:
                self.spreadsheet_edit_entry.destroy()
            except tk.TclError:
                pass
        self.spreadsheet_editing_cell = None
        self.spreadsheet_edit_entry = None
        self.spreadsheet_edit_window_id = None

    # ------------------------------------------------
    # Raccourcis clavier (quand le Canvas a le focus, pas l'Entry d'édition)
    # ------------------------------------------------

    def _on_spreadsheet_key_return(self, event):
        if self.spreadsheet_editing_cell is not None:
            self._spreadsheet_finish_edit(move_down=True)
        else:
            self._spreadsheet_start_edit()
        return "break"

    def _on_spreadsheet_key_delete(self, event):
        if self.spreadsheet_editing_cell is not None or self.spreadsheet_selected is None:
            return
        r, c = self.spreadsheet_selected
        self.material_spreadsheet["cells"].pop(cell_id(r, c), None)
        self._refresh_spreadsheet()
        self._draw_spreadsheet_selection()
        return "break"

    def _on_spreadsheet_key_type(self, event):
        """Taper directement un caractère sur une cellule sélectionnée
        (non éditée) démarre l'édition avec ce caractère, comme un tableur
        classique. Les touches de navigation ont leur propre binding et
        renvoient "break", donc n'atteignent jamais ce gestionnaire."""
        if self.spreadsheet_selected is None or self.spreadsheet_editing_cell is not None:
            return
        ch = event.char
        if not ch or not ch.isprintable():
            return
        self._spreadsheet_start_edit(initial_text=ch)
        return "break"

    # ========================================================
    # AJOUT / SUPPRESSION DE LIGNES / COLONNES
    # ========================================================

    def _add_spreadsheet_row(self):
        if self.material_spreadsheet["rows"] >= MAX_ROWS:
            messagebox.showinfo("Info", f"Maximum row count reached ({MAX_ROWS}).")
            return
        self.material_spreadsheet["rows"] += 1
        self._rebuild_spreadsheet_grid()

    def _add_spreadsheet_col(self):
        if self.material_spreadsheet["cols"] >= MAX_COLS:
            messagebox.showinfo("Info", f"Maximum column count reached ({MAX_COLS}).")
            return
        self.material_spreadsheet["cols"] += 1
        self._rebuild_spreadsheet_grid()

    def _remove_spreadsheet_row(self):
        rows = self.material_spreadsheet["rows"]
        if rows <= 1:
            return
        last_row = rows - 1
        cols = self.material_spreadsheet["cols"]
        used = [
            c for c in range(cols)
            if str(self.material_spreadsheet["cells"].get(cell_id(last_row, c), "")).strip()
        ]
        if used and not messagebox.askyesno(
            'Confirm', 'The last row contains data. Delete it anyway?'
        ):
            return
        for c in range(cols):
            self.material_spreadsheet["cells"].pop(cell_id(last_row, c), None)
        self.material_spreadsheet["rows"] -= 1
        heights = self.material_spreadsheet.get("row_heights", [])   # <-- ajout
        if len(heights) > self.material_spreadsheet["rows"]:          # <-- ajout
            del heights[self.material_spreadsheet["rows"]:]           # <-- ajout
        if self.spreadsheet_selected is not None and self.spreadsheet_selected[0] >= self.material_spreadsheet["rows"]:
            self.spreadsheet_selected = (self.material_spreadsheet["rows"] - 1, self.spreadsheet_selected[1])
        self._rebuild_spreadsheet_grid()

    def _remove_spreadsheet_col(self):
        cols = self.material_spreadsheet["cols"]
        if cols <= 1:
            return
        last_col = cols - 1
        rows = self.material_spreadsheet["rows"]
        used = [
            r for r in range(rows)
            if str(self.material_spreadsheet["cells"].get(cell_id(r, last_col), "")).strip()
        ]
        if used and not messagebox.askyesno(
            'Confirm', 'The last column contains data. Delete it anyway?'
        ):
            return
        for r in range(rows):
            self.material_spreadsheet["cells"].pop(cell_id(r, last_col), None)
        self.material_spreadsheet["cols"] -= 1
        widths = self.material_spreadsheet.get("col_widths", [])      # <-- ajout
        if len(widths) > self.material_spreadsheet["cols"]:           # <-- ajout
            del widths[self.material_spreadsheet["cols"]:]            # <-- ajout
        if self.spreadsheet_selected is not None and self.spreadsheet_selected[1] >= self.material_spreadsheet["cols"]:
            self.spreadsheet_selected = (self.spreadsheet_selected[0], self.material_spreadsheet["cols"] - 1)
        self._rebuild_spreadsheet_grid()

    def _clear_spreadsheet(self):
        if not self.material_spreadsheet["cells"]:
            return
        if messagebox.askyesno('Confirm', 'Clear all spreadsheet cells?'):
            self.material_spreadsheet["cells"] = {}
            self._refresh_spreadsheet()
            self._draw_spreadsheet_selection()
    
    def _get_zone_string_insert_vars(self):
        """Variables numériques (catégorie A) générées dynamiquement à partir
        des zones de toiture et des strings existantes, pour les menus
        d'insertion de l'onglet Matériel. Retourne un dict {NOM: valeur}."""
        variables = {}

        for z_idx, zone in enumerate(getattr(self, "roof_zones", []) or [], start=1):
            rows = zone.get("rows", 0) or 0
            cols = zone.get("cols", 0) or 0
            variables[f"ZONE{z_idx}_PANEL_COUNT"] = float(sum(1 for r,c in self.panels if zone.get("row_base",(z_idx-1)*100)<=r<zone.get("row_base",(z_idx-1)*100)+rows and 0<=c<cols))
            variables[f"ZONE{z_idx}_WIDTH_MM"] = float(zone.get("w_mm", 0) or 0)
            variables[f"ZONE{z_idx}_HEIGHT_MM"] = float(zone.get("h_mm", 0) or 0)
            variables[f"ZONE{z_idx}_ROWS"] = float(rows)
            variables[f"ZONE{z_idx}_COLUMNS"] = float(cols)

        strings = getattr(self, "strings", {}) or {}
        sorted_keys = self._get_sorted_string_keys() if hasattr(self, "_get_sorted_string_keys") else list(strings.keys())
        for i, key in enumerate(sorted_keys, start=1):
            coords = strings.get(key, [])
            variables[f"STRING{i}_PANEL_COUNT"] = float(len(coords))

        return variables


    def _insert_text_into_active_cell(self, text):
        """Insère `text` dans la cellule active, à la position du curseur si
        une édition est en cours ; sinon démarre l'édition avec le contenu
        existant de la cellule (curseur en fin) puis insère à la suite.
        Ne fait rien si aucune cellule n'est sélectionnée."""
        if self.spreadsheet_selected is None:
            return

        if self.spreadsheet_editing_cell is None:
            self._spreadsheet_start_edit()  # charge le texte déjà écrit, curseur en fin (icursor(tk.END))

        entry = self.spreadsheet_edit_entry
        if entry is None:
            return

        pos = entry.index(tk.INSERT)
        entry.insert(pos, text)
        entry.icursor(pos + len(text))
        entry.focus_set()

    def _insert_spreadsheet_variable(self, name):
        if self.spreadsheet_selected is None:
            messagebox.showinfo('Spreadsheet', 'Select a cell before inserting a variable.')
            return
        row, col = self.spreadsheet_selected
        ref = cell_id(row, col)
        raw = str(self.material_spreadsheet['cells'].get(ref, ''))
        if self.spreadsheet_editing_cell == (row, col):
            entry = self.spreadsheet_edit_entry
            if not entry.get().strip():
                entry.delete(0, tk.END)
                entry.insert(0, '=' + name)
                entry.icursor(tk.END)
                entry.focus_set()
                return
            elif not entry.get().lstrip().startswith('='):
                messagebox.showinfo('Spreadsheet', 'Insert variables in a blank cell or a formula.')
                return
            entry.insert(tk.INSERT, name)
            entry.focus_set()
            return
        if not raw:
            self.material_spreadsheet['cells'][ref] = '=' + name
            self._refresh_spreadsheet()
            self._draw_spreadsheet_selection()
        elif raw.lstrip().startswith('='):
            self._spreadsheet_start_edit()
            self.spreadsheet_edit_entry.insert(tk.INSERT, name)
            self.spreadsheet_edit_entry.focus_set()
        else:
            messagebox.showinfo('Spreadsheet', 'Select a blank cell or an existing formula.')

    def _apply_spreadsheet_formula_bar(self, event=None):
        if self.spreadsheet_selected is None:
            return 'break'
        raw = self.spreadsheet_formula_var.get().strip()
        self._spreadsheet_cancel_edit()
        ref = cell_id(*self.spreadsheet_selected)
        if raw:
            self.material_spreadsheet['cells'][ref] = raw
        else:
            self.material_spreadsheet['cells'].pop(ref, None)
        self._refresh_spreadsheet()
        self._draw_spreadsheet_selection()
        self.spreadsheet_data_canvas.focus_set()
        return 'break'

    def _export_spreadsheet_csv(self):
        self._spreadsheet_commit_edit()
        filepath = filedialog.asksaveasfilename(defaultextension='.csv',
                                                 filetypes=[('CSV files', '*.csv')],
                                                 title='Export spreadsheet formulas as CSV')
        if not filepath:
            return
        try:
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as output:
                writer = csv.writer(output, delimiter=';')
                data = self.material_spreadsheet
                for row in range(data['rows']):
                    writer.writerow([data['cells'].get(cell_id(row, col), '')
                                     for col in range(data['cols'])])
            messagebox.showinfo('Export', f'Spreadsheet exported:\n{filepath}')
        except OSError as exc:
            messagebox.showerror('Export', str(exc))

    def _import_spreadsheet_csv(self):
        filepath = filedialog.askopenfilename(filetypes=[('CSV files', '*.csv')],
                                              title='Import spreadsheet CSV')
        if not filepath:
            return
        try:
            with open(filepath, newline='', encoding='utf-8-sig') as source:
                sample = source.read(4096)
                source.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=';,\t')
                except csv.Error:
                    dialect = csv.excel
                values = list(csv.reader(source, dialect))
            rows = len(values)
            cols = max((len(row) for row in values), default=0)
            if not rows or not cols or rows > MAX_ROWS or cols > MAX_COLS:
                raise ValueError(f'CSV must contain 1–{MAX_ROWS} rows and 1–{MAX_COLS} columns.')
        except (OSError, ValueError, UnicodeError, csv.Error) as exc:
            messagebox.showerror('Import', str(exc))
            return
        if self.material_spreadsheet['cells'] and not messagebox.askyesno(
                'Import', 'Replace the current spreadsheet with the imported CSV?'):
            return
        self._spreadsheet_cancel_edit()
        self.material_spreadsheet = {
            'rows': rows, 'cols': cols,
            'cells': {cell_id(row, col): value for row, items in enumerate(values)
                      for col, value in enumerate(items) if value != ''},
            'col_widths': [], 'row_heights': [],
        }
        self.spreadsheet_selected = (0, 0)
        self._rebuild_spreadsheet_grid()

    def _show_spreadsheet_chart(self):
        self._spreadsheet_commit_edit()
        data = self.material_spreadsheet
        columns = [col_letter(index) for index in range(data['cols'])]
        dialog = tk.Toplevel(self.root)
        dialog.title('Spreadsheet chart')
        self._center_window(dialog, 850, 500)
        dialog.transient(self.root)

        controls = ttk.Frame(dialog, padding=8)
        controls.pack(fill=tk.X)
        kind = tk.StringVar(value='Bars')
        value_column = tk.StringVar(value=columns[min(1, len(columns) - 1)])
        label_column = tk.StringVar(value='Row number')
        for title, variable, options in (
            ('Chart:', kind, ['Bars', 'Line']),
            ('Values:', value_column, columns),
            ('Labels:', label_column, ['Row number'] + columns),
        ):
            ttk.Label(controls, text=title).pack(side=tk.LEFT, padx=(5, 3))
            ttk.Combobox(controls, textvariable=variable, values=options,
                         state='readonly', width=12).pack(side=tk.LEFT, padx=(0, 12))

        info = ttk.Label(dialog, text='')
        info.pack(anchor='w', padx=12)
        frame = ttk.Frame(dialog)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        canvas = tk.Canvas(frame, bg='white', highlightthickness=1,
                           highlightbackground='#BDBDBD')
        bar = ttk.Scrollbar(frame, orient=tk.HORIZONTAL, command=canvas.xview)
        canvas.configure(xscrollcommand=bar.set)
        canvas.pack(fill=tk.BOTH, expand=True)
        bar.pack(fill=tk.X)

        def draw(event=None):
            canvas.delete('all')
            computed = self._compute_spreadsheet_values()
            value_idx = col_index(value_column.get())
            label_idx = col_index(label_column.get()) if label_column.get() != 'Row number' else None
            points = []
            for row in range(data['rows']):
                raw = data['cells'].get(cell_id(row, value_idx), '')
                value = computed.get((row, value_idx))
                if not str(raw).strip() or not isinstance(value, (float, int)) or not math.isfinite(value):
                    continue
                label = str(row + 1) if label_idx is None else str(computed.get((row, label_idx), '') or row + 1)
                points.append((label, float(value)))
            info.config(text=f'{len(points)} numeric cells from column {value_column.get()}')
            if not points:
                canvas.create_text(20, 20, anchor=tk.NW,
                                   text='Enter numeric values or formulas in the selected column.')
                return
            width = max(canvas.winfo_width(), len(points) * 34 + 90)
            height = max(canvas.winfo_height(), 280)
            left, top, bottom, right = 58, 25, 50, 20
            plot_w, plot_h = width - left - right, height - top - bottom
            minimum = min(0.0, min(value for _, value in points))
            maximum = max(0.0, max(value for _, value in points))
            spread = max(0.01, maximum - minimum)
            zero_y = top + (maximum / spread) * plot_h
            stride = max(1, (len(points) + 11) // 12)
            coords = []
            for tick in range(5):
                value = minimum + spread * tick / 4
                y = top + plot_h * (1 - tick / 4)
                canvas.create_line(left, y, width - right, y, fill='#ECEFF1')
                canvas.create_text(left - 6, y, text=f'{value:.1f}', anchor=tk.E, font=('Arial', 8))
            for i, (label, value) in enumerate(points):
                x = left + plot_w * (i + .5) / len(points)
                y = top + (maximum - value) / spread * plot_h
                coords.extend((x, y))
                if kind.get() == 'Bars':
                    canvas.create_rectangle(x - 10, min(y, zero_y), x + 10, max(y, zero_y),
                                            fill='#1976D2', outline='#0D47A1')
                if i % stride == 0:
                    canvas.create_text(x, top + plot_h + 10, text=label[:12],
                                       anchor=tk.N, font=('Arial', 8))
            if kind.get() == 'Line':
                if len(coords) >= 4:
                    canvas.create_line(*coords, width=2, fill='#D32F2F')
                for x, y in zip(coords[::2], coords[1::2]):
                    canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill='#D32F2F', outline='white')
            canvas.configure(scrollregion=(0, 0, width, height))

        for var in (kind, value_column, label_column):
            var.trace_add('write', lambda *args: draw())
        canvas.bind('<Configure>', draw)
        draw()
