"""Fiche matériel du projet : modules PV, onduleurs, câbles/protections et
champs personnalisés. Ces données sont indépendantes du layout et servent
de référence pour l'ensemble du projet (utilisées entre autres par
l'onglet Schéma Unifilaire).

Chaque catégorie (Modules PV, Onduleurs, Câbles/Protections, Champs
personnalisés) est affichée comme une vraie grille de tableur : colonnes
lettrées (A, B, C...), lignes numérotées (1, 2, 3...), cellules éditables
en cliquant dessus. Une cellule devient une formule si elle commence par
"=", avec le style Google Sheets/Excel :
    =C2*1.05
    =SOMME(C2:C10)
    =Onduleurs!C1          (référence vers une autre feuille/onglet)
    =SOMME(Onduleurs!C1:C4)
    =NB_MODULES*C2          (variables globales du projet, voir plus bas)

Les champs de l'onglet "Champs personnalisés" (colonne "Champ") sont en
plus utilisables comme variables nommées dans n'importe quelle formule,
sur n'importe quel onglet (ex. Champ="Marge", Valeur=0.05, puis ailleurs
=C2*(1+Marge)).

Les feuilles se référencent par un nom court, insensible à la casse :
Modules, Onduleurs, Cables, Perso.
"""

import re

import tkinter as tk
from tkinter import messagebox, ttk

# Catégories fixes de la fiche matériel : {clé: (titre, colonnes)}
MATERIAL_CATEGORY_DEFS = {
    "modules": ("Modules PV", ["Marque", "Modèle", "Pmax (W)", "Voc (V)", "Isc (A)", "Vmp (V)", "Imp (A)", "Voc temp coefficient (%/°C)", "Vmp temp coefficient (%/°C)", "Bifacial current gain (%)"]),
    "inverters": ("Onduleurs", ["Marque", "Modèle", "Puissance (kVA)", "Nb entrées MPPT", "Tension max (V)", "Puissance active (kW)", "Cos phi", "MPPT min (V)", "MPPT max (V)", "MPPT Imp max (A)", "MPPT Isc max (A)", "Input Isc max (A)", "PV max (kW)"]),
    "cables": ("Câbles / Protections", ["Désignation", "Section (mm²)", "Calibre fusible (A)", "Type de protection"]),
    "custom": ("Champs personnalisés", ["Champ", "Valeur"]),
}

# Display names only: JSON field names and formula references stay compatible.
MATERIAL_TITLES_EN = {
    'modules': 'PV modules', 'inverters': 'Inverters',
    'cables': 'Cables / protection', 'custom': 'Custom fields',
}
MATERIAL_COLUMNS_EN = {
    'Marque': 'Brand', 'Modèle': 'Model', 'Puissance (kVA)': 'Power (kVA)',
    'Nb entrées MPPT': 'MPPT inputs', 'Tension max (V)': 'Max voltage (V)',
    'Désignation': 'Description', 'Section (mm²)': 'Cross-section (mm²)',
    'Calibre fusible (A)': 'Fuse rating (A)',
    'Puissance active (kW)':'Active power (kW)', 'Cos phi':'Power factor',
    'MPPT min (V)':'Minimum MPPT voltage (V)', 'MPPT max (V)':'Maximum MPPT voltage (V)',
    'MPPT Imp max (A)':'Maximum MPPT operating current (A)', 'MPPT Isc max (A)':'Maximum MPPT short-circuit current (A)',
    'Type de protection': 'Protection type', 'Champ': 'Field', 'Valeur': 'Value',
}


def default_material_categories():
    """Structure par défaut (utilisée à l'init de l'app et au chargement d'un
    projet ne contenant pas encore de fiche matériel)."""
    return {key: {"rows": []} for key in MATERIAL_CATEGORY_DEFS}


# ============================================================
# ADRESSAGE DES CELLULES (A1, C2, ...) ET NOMS DE FEUILLES
# ============================================================

SHEET_ALIASES = {
    "modules": "modules", "module": "modules", "pv": "modules",
    "onduleurs": "inverters", "onduleur": "inverters", "inverters": "inverters", "inverter": "inverters",
    "cables": "cables", "cable": "cables", "protections": "cables",
    "perso": "custom", "custom": "custom", "personnalise": "custom", "personnalises": "custom", "champs": "custom",
}


def _resolve_sheet(name, default_key):
    if name is None:
        return default_key
    key = SHEET_ALIASES.get(name.lower())
    if key is None:
        raise ValueError(f"Unknown sheet: {name}")
    return key


def _col_index_to_letters(idx):
    idx += 1
    letters = ""
    while idx > 0:
        idx, rem = divmod(idx - 1, 26)
        letters = chr(65 + rem) + letters
    return letters


def _col_letters_to_index(letters):
    idx = 0
    for ch in letters.upper():
        idx = idx * 26 + (ord(ch) - ord("A") + 1)
    return idx - 1


_CELL_REF_RE = re.compile(r"^([A-Za-z]+)([0-9]+)$")


def _parse_cell_ref(token_str, sheet):
    m = _CELL_REF_RE.match(token_str)
    if not m:
        raise ValueError(f"Invalid cell reference: {token_str}")
    col_idx = _col_letters_to_index(m.group(1))
    row_idx = int(m.group(2)) - 1
    return ("ref", sheet, col_idx, row_idx)


def _sanitize_ident(name):
    """Transforme un nom de champ personnalisé ('Marge %') en identifiant
    utilisable dans une formule ('Marge')."""
    ident = re.sub(r"[^0-9A-Za-z_]", "_", str(name))
    ident = re.sub(r"_+", "_", ident).strip("_")
    if not ident:
        ident = "CHAMP"
    if ident[0].isdigit():
        ident = "_" + ident
    return ident


def _to_number(raw):
    """Convertit une valeur brute de cellule en float pour usage dans une
    formule ; une cellule vide vaut 0 (comme dans un tableur)."""
    if raw is None:
        return 0.0
    s = str(raw).strip()
    if s == "":
        return 0.0
    try:
        return float(s.replace(",", "."))
    except ValueError:
        return s


# ============================================================
# TOKENIZER + PARSER DE FORMULE (sans eval() : arithmétique, refs de
# cellules, plages, feuilles, SOMME(), variables)
# ============================================================

_TOKEN_SPEC = [
    ("NUMBER", r"\d+(?:\.\d+)?"),
    ("IDENT", r"[A-Za-z_][A-Za-z0-9_]*"),
    ("BANG", r"!"),
    ("COLON", r":"),
    ("LPAREN", r"\("),
    ("RPAREN", r"\)"),
    ("PLUS", r"\+"),
    ("MINUS", r"-"),
    ("STAR", r"\*"),
    ("SLASH", r"/"),
    ("SKIP", r"[ \t]+"),
]
_TOKEN_RE = re.compile("|".join(f"(?P<{n}>{p})" for n, p in _TOKEN_SPEC))


def _tokenize(s):
    tokens = []
    pos = 0
    while pos < len(s):
        m = _TOKEN_RE.match(s, pos)
        if not m:
            raise ValueError(f"Unexpected character: {s[pos]!r}")
        kind = m.lastgroup
        if kind != "SKIP":
            tokens.append((kind, m.group()))
        pos = m.end()
    tokens.append(("EOF", ""))
    return tokens


class _FormulaParser:
    """Grammaire : expr := terme (('+'|'-') terme)* ; terme := unaire
    (('*'|'/') unaire)* ; primaire := NOMBRE | '(' expr ')' | IDENT[...]
    IDENT peut être une référence de cellule (C2), une plage (C2:C10), une
    référence de feuille (Onduleurs!C1[:C4]), un appel SOMME(...), ou une
    variable nommée."""

    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    def _peek(self):
        return self.tokens[self.pos]

    def _advance(self):
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def _expect(self, kind):
        tok = self._advance()
        if tok[0] != kind:
            raise ValueError(f"Syntax error near {tok[1]!r}")
        return tok

    def parse(self):
        node = self._parse_expr()
        self._expect("EOF")
        return node

    def _parse_expr(self):
        node = self._parse_term()
        while self._peek()[0] in ("PLUS", "MINUS"):
            op = self._advance()[0]
            right = self._parse_term()
            node = ("binop", "+" if op == "PLUS" else "-", node, right)
        return node

    def _parse_term(self):
        node = self._parse_unary()
        while self._peek()[0] in ("STAR", "SLASH"):
            op = self._advance()[0]
            right = self._parse_unary()
            node = ("binop", "*" if op == "STAR" else "/", node, right)
        return node

    def _parse_unary(self):
        if self._peek()[0] in ("PLUS", "MINUS"):
            op = self._advance()[0]
            operand = self._parse_unary()
            return ("unary", "-" if op == "MINUS" else "+", operand)
        return self._parse_primary()

    def _parse_primary(self):
        kind, value = self._peek()
        if kind == "NUMBER":
            self._advance()
            return ("num", float(value))
        if kind == "LPAREN":
            self._advance()
            node = self._parse_expr()
            self._expect("RPAREN")
            return node
        if kind == "IDENT":
            return self._parse_ident_expr()
        raise ValueError(f"Syntax error near {value!r}")

    def _parse_ident_expr(self):
        ident = self._advance()[1]
        if self._peek()[0] == "LPAREN":
            self._advance()
            arg = self._parse_primary()
            self._expect("RPAREN")
            return ("call", ident.upper(), arg)
        if self._peek()[0] == "BANG":
            self._advance()
            cell_tok = self._expect("IDENT")
            ref = _parse_cell_ref(cell_tok[1], sheet=ident)
            if self._peek()[0] == "COLON":
                self._advance()
                cell2_tok = self._expect("IDENT")
                ref2 = _parse_cell_ref(cell2_tok[1], sheet=ident)
                return ("range", ident, ref[2], ref[3], ref2[2], ref2[3])
            return ref
        if _CELL_REF_RE.match(ident):
            ref = _parse_cell_ref(ident, sheet=None)
            if self._peek()[0] == "COLON":
                self._advance()
                cell2_tok = self._expect("IDENT")
                ref2 = _parse_cell_ref(cell2_tok[1], sheet=None)
                return ("range", None, ref[2], ref[3], ref2[2], ref2[3])
            return ref
        return ("var", ident)


class MaterialToolsMixin:
    # ========================================================
    # PANNEAU LATÉRAL — FICHE MATÉRIEL (grille type tableur)
    # ========================================================

    def _build_side_panel_material(self):
        self.side_panel_material = ttk.Frame(self.main_container, width=420, padding=5)

        explorer = ttk.LabelFrame(self.side_panel_material, text='🔎 Variable explorer', padding=5)
        explorer.pack(fill=tk.BOTH, expand=True, pady=(0, 7))
        search_row = ttk.Frame(explorer)
        search_row.pack(fill=tk.X, pady=(0, 4))
        self.variable_search = tk.StringVar()
        ttk.Entry(search_row, textvariable=self.variable_search).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(search_row, text='Insert', command=self._insert_selected_variable).pack(side=tk.LEFT, padx=4)
        tree_frame = ttk.Frame(explorer)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        self.variable_tree = ttk.Treeview(tree_frame, columns=('value',), show='tree headings', height=9)
        self.variable_tree.heading('#0', text='Formula variable')
        self.variable_tree.heading('value', text='Current value')
        self.variable_tree.column('#0', width=210, minwidth=120)
        self.variable_tree.column('value', width=120, minwidth=70, anchor='e')
        self.variable_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.variable_tree.yview)
        self.variable_tree.configure(yscrollcommand=tree_scroll.set)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.variable_tree.bind('<Double-1>', lambda event: self._insert_selected_variable())
        self.variable_tree.bind('<Return>', lambda event: self._insert_selected_variable())
        self.variable_search.trace_add('write', lambda *args: self._refresh_variable_explorer())
        ttk.Label(explorer, text='Double-click a variable to insert it in the selected spreadsheet cell.',
                  wraplength=390, foreground='#546E7A').pack(anchor='w', pady=(4, 0))

        self._equipment_window = tk.Toplevel(self.root)
        self._equipment_window.title('Project equipment configuration')
        self._equipment_window.withdraw()
        self._equipment_window.protocol('WM_DELETE_WINDOW', self._equipment_window.withdraw)
        self.material_notebook = ttk.Notebook(self._equipment_window)
        self.material_notebook.pack(fill=tk.BOTH, expand=True)

        self.material_grids = {}         # clé -> frame interne de la grille (scrollable)
        self.material_cell_widgets = {}  # clé -> {(ligne, colonne): Entry}
        self.material_row_labels = {}    # clé -> {ligne: Label numéro de ligne}
        self.material_selected_row = {}  # clé -> index de ligne sélectionné (ou None)

        for key, (title, columns) in MATERIAL_CATEGORY_DEFS.items():
            tab = ttk.Frame(self.material_notebook, padding=5)
            self.material_notebook.add(tab, text=MATERIAL_TITLES_EN[key])

            grid_area = ttk.Frame(tab)
            grid_area.pack(fill=tk.BOTH, expand=True)
            inner = self._make_scrollable_grid(grid_area)
            self.material_grids[key] = inner
            self.material_cell_widgets[key] = {}
            self.material_row_labels[key] = {}
            self.material_selected_row[key] = None

            self._build_material_grid_header(inner, columns)

            btn_box = ttk.Frame(tab)
            btn_box.pack(fill=tk.X, pady=(5, 0))
            ttk.Button(btn_box, text='➕ Row', command=lambda k=key: self._add_material_row(k)).pack(
                side=tk.LEFT, expand=True, fill=tk.X, padx=2
            )
            ttk.Button(
                btn_box, text='🗑️ Delete selected row', command=lambda k=key: self._delete_material_row(k)
            ).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        self._rebuild_all_material_grids()
        self._refresh_variable_explorer()

    def _make_scrollable_grid(self, parent):
        """Zone avec ascenseurs vertical + horizontal contenant une grille de widgets."""
        outer = ttk.Frame(parent)
        outer.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(outer, highlightthickness=0)
        vbar = ttk.Scrollbar(outer, orient=tk.VERTICAL, command=canvas.yview)
        hbar = ttk.Scrollbar(outer, orient=tk.HORIZONTAL, command=canvas.xview)
        canvas.configure(yscrollcommand=vbar.set, xscrollcommand=hbar.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        def _on_mousewheel(event):
            if event.num == 4:
                canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                canvas.yview_scroll(1, "units")
            elif getattr(event, "delta", 0):
                canvas.yview_scroll(-1 * (event.delta // 120), "units")

        def _bind_wheel(_e):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
            canvas.bind_all("<Button-4>", _on_mousewheel)
            canvas.bind_all("<Button-5>", _on_mousewheel)

        def _unbind_wheel(_e):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        canvas.bind("<Enter>", _bind_wheel)
        canvas.bind("<Leave>", _unbind_wheel)

        return inner

    def _build_material_grid_header(self, inner, columns):
        ttk.Label(inner, text="", width=4).grid(row=0, column=0, sticky="nsew")
        ttk.Label(inner, text="", width=4).grid(row=1, column=0, sticky="nsew")
        for col_idx, col_name in enumerate(columns):
            letter = _col_index_to_letters(col_idx)
            tk.Label(
                inner, text=letter, width=11, anchor="center",
                background="#37474F", foreground="white", font=("Arial", 8, "bold")
            ).grid(row=0, column=col_idx + 1, sticky="nsew", padx=1, pady=(0, 1))
            tk.Label(
                inner, text=MATERIAL_COLUMNS_EN.get(col_name, col_name), width=11, anchor="center",
                background="#ECEFF1", font=("Arial", 8, "bold"), wraplength=80
            ).grid(row=1, column=col_idx + 1, sticky="nsew", padx=1, pady=(0, 1))

    # ========================================================
    # LIGNES DE LA GRILLE
    # ========================================================

    def _rebuild_material_grid_rows(self, key):
        inner = self.material_grids[key]
        _, columns = MATERIAL_CATEGORY_DEFS[key]

        for widget in self.material_cell_widgets[key].values():
            widget.destroy()
        for widget in self.material_row_labels[key].values():
            widget.destroy()
        self.material_cell_widgets[key] = {}
        self.material_row_labels[key] = {}
        self.material_selected_row[key] = None

        rows = self.material_categories.get(key, {}).get("rows", [])
        for row_idx in range(len(rows)):
            row_label = tk.Label(
                inner, text=str(row_idx + 1), width=4, anchor="center",
                background="#ECEFF1", font=("Arial", 8, "bold"), cursor="hand2"
            )
            row_label.grid(row=row_idx + 2, column=0, sticky="nsew", padx=1, pady=1)
            row_label.bind("<Button-1>", lambda e, k=key, r=row_idx: self._select_material_row(k, r))
            self.material_row_labels[key][row_idx] = row_label

            for col_idx in range(len(columns)):
                entry = tk.Entry(inner, width=11, font=("Arial", 9), relief=tk.SOLID, borderwidth=1)
                entry.grid(row=row_idx + 2, column=col_idx + 1, sticky="nsew", padx=1, pady=1)
                entry.bind("<FocusIn>", lambda e, k=key, r=row_idx, c=col_idx: self._on_material_cell_focus_in(k, r, c))
                entry.bind("<FocusOut>", lambda e, k=key, r=row_idx, c=col_idx: self._on_material_cell_commit(k, r, c))
                entry.bind("<Return>", lambda e, k=key, r=row_idx, c=col_idx: self._on_material_cell_return(k, r, c))
                self.material_cell_widgets[key][(row_idx, col_idx)] = entry

    def _rebuild_all_material_grids(self):
        for key in MATERIAL_CATEGORY_DEFS:
            self._rebuild_material_grid_rows(key)
        self._refresh_material_trees()

    def _select_material_row(self, key, row_idx):
        prev = self.material_selected_row.get(key)
        if prev is not None and prev in self.material_row_labels[key]:
            self.material_row_labels[key][prev].configure(background="#ECEFF1")
        self.material_selected_row[key] = row_idx
        if row_idx in self.material_row_labels[key]:
            self.material_row_labels[key][row_idx].configure(background="#90CAF9")

    def _add_material_row(self, key):
        _, columns = MATERIAL_CATEGORY_DEFS[key]
        self.material_categories[key]["rows"].append({col: "" for col in columns})
        self._rebuild_material_grid_rows(key)
        self._refresh_material_trees()

    def _delete_material_row(self, key):
        idx = self.material_selected_row.get(key)
        if idx is None:
            messagebox.showinfo("Info", 'First click the number of the row to delete.')
            return
        rows = self.material_categories[key]["rows"]
        if 0 <= idx < len(rows) and messagebox.askyesno('Confirm', 'Delete this row?'):
            rows.pop(idx)
            self._rebuild_material_grid_rows(key)
            self._refresh_material_trees()

    # ========================================================
    # ÉDITION DES CELLULES
    # ========================================================

    def _on_material_cell_focus_in(self, key, row_idx, col_idx):
        """Au clic sur une cellule : affiche la formule brute (pas le résultat) pour édition."""
        _, columns = MATERIAL_CATEGORY_DEFS[key]
        col_name = columns[col_idx]
        rows = self.material_categories.get(key, {}).get("rows", [])
        raw = rows[row_idx].get(col_name, "") if row_idx < len(rows) else ""
        entry = self.material_cell_widgets[key][(row_idx, col_idx)]
        entry.delete(0, tk.END)
        entry.insert(0, "" if raw is None else str(raw))

    def _on_material_cell_commit(self, key, row_idx, col_idx):
        _, columns = MATERIAL_CATEGORY_DEFS[key]
        col_name = columns[col_idx]
        entry = self.material_cell_widgets[key][(row_idx, col_idx)]
        new_val = entry.get()
        rows = self.material_categories.get(key, {}).get("rows", [])
        if row_idx < len(rows):
            rows[row_idx][col_name] = new_val
        if key == "modules": self._sync_module_power()
        self._refresh_material_trees()

    def _on_material_cell_return(self, key, row_idx, col_idx):
        """Entrée : valide la cellule et passe à la ligne suivante (comme un tableur)."""
        self._on_material_cell_commit(key, row_idx, col_idx)
        next_entry = self.material_cell_widgets[key].get((row_idx + 1, col_idx))
        if next_entry is not None:
            next_entry.focus_set()
        else:
            self.side_panel_material.focus_set()
        return "break"

    # ========================================================
    # VARIABLES GLOBALES DU PROJET (utilisables dans les formules)
    # ========================================================

    def _get_material_global_vars(self):
        """Variables globales du projet utilisables dans une formule
        (ex. =NB_MODULES*C2). Sources : self.panels, self.strings (idem
        _update_stats_display de canvas_grid.py) et self.inverter_positions
        (idem project_io.py)."""
        nb_modules = len(getattr(self, "panels", {}) or {})
        strings = getattr(self, "strings", {}) or {}
        nb_strings = sum(1 for coords in strings.values() if coords)
        nb_onduleurs = len(getattr(self, "inverter_positions", {}) or {})

        puissance_totale_wc = 0.0
        modules_rows = self.material_categories.get("modules", {}).get("rows", [])
        if modules_rows:
            # Prend le Pmax de la 1ère ligne de la feuille Modules comme référence.
            # Pour préciser une autre ligne, écrire directement une formule telle
            # que =NB_MODULES*Modules!C3 dans un champ personnalisé.
            pmax = _to_number(modules_rows[0].get("Pmax (W)", ""))
            if isinstance(pmax, float):
                puissance_totale_wc = nb_modules * pmax

        variables = {
            "NB_MODULES": float(nb_modules),
            "NB_STRINGS": float(nb_strings),
            "NB_ONDULEURS": float(nb_onduleurs),
            "PUISSANCE_TOTALE_WC": float(puissance_totale_wc),
            "PANEL_COUNT": float(nb_modules),
            "STRING_COUNT": float(nb_strings),
            "INVERTER_COUNT": float(nb_onduleurs),
            "PV_CAPACITY_WP": float(puissance_totale_wc),
        }
        if hasattr(self, '_cable_mass_summary'):
            mass = self._cable_mass_summary()
            variables['CABLE_WEIGHT_MISSING_STRINGS'] = float(mass['missing'])
            if mass['total_kg'] is not None:
                variables['TOTAL_CABLE_WEIGHT_KG'] = float(mass['total_kg'])
                variables['POIDS_TOTAL_CABLAGES_KG'] = float(mass['total_kg'])
        return variables

    # ========================================================
    # CALCUL DES FORMULES
    # ========================================================

    def _compute_material_formulas(self):
        """Calcule toutes les cellules-formules de la fiche matériel.
        Retourne {(catégorie, ligne, colonne): valeur} où valeur est un
        float, un texte, ou "#ERR"/"#CIRC!" en cas d'erreur."""
        global_vars = self._get_material_global_vars()
        cache = {}
        visiting = set()

        def get_raw(category, row_idx, col_idx):
            rows = self.material_categories.get(category, {}).get("rows", [])
            _, columns = MATERIAL_CATEGORY_DEFS[category]
            if row_idx < 0 or row_idx >= len(rows) or col_idx < 0 or col_idx >= len(columns):
                return ""
            return rows[row_idx].get(columns[col_idx], "")

        def get_custom_vars():
            vars_ = {}
            for idx, row in enumerate(self.material_categories.get("custom", {}).get("rows", [])):
                champ = str(row.get("Champ", "")).strip()
                if champ:
                    vars_[_sanitize_ident(champ)] = eval_cell("custom", idx, 1)  # colonne B = Valeur
            return vars_

        def eval_cell(category, row_idx, col_idx):
            key = (category, row_idx, col_idx)
            if key in cache:
                return cache[key]
            raw = get_raw(category, row_idx, col_idx)
            raw_str = "" if raw is None else str(raw)
            if not raw_str.strip().startswith("="):
                cache[key] = _to_number(raw_str)
                return cache[key]
            if key in visiting:
                cache[key] = "#CIRC!"
                return cache[key]
            visiting.add(key)
            try:
                tokens = _tokenize(raw_str.strip()[1:])
                ast_node = _FormulaParser(tokens).parse()
                cache[key] = eval_node(ast_node, category)
            except Exception:
                cache[key] = "#ERR"
            finally:
                visiting.discard(key)
            return cache[key]

        def eval_range_sum(sheet, c1, r1, c2, r2, current_category):
            target = _resolve_sheet(sheet, current_category)
            total = 0.0
            for r in range(min(r1, r2), max(r1, r2) + 1):
                for c in range(min(c1, c2), max(c1, c2) + 1):
                    v = eval_cell(target, r, c)
                    if isinstance(v, float):
                        total += v
            return total

        def eval_node(node, category):
            kind = node[0]
            if kind == "num":
                return node[1]
            if kind == "var":
                name = node[1]
                if name in global_vars:
                    return global_vars[name]
                custom_vars = get_custom_vars()
                if name in custom_vars:
                    v = custom_vars[name]
                    if not isinstance(v, float):
                        raise ValueError(f"« {name}” is not numeric")
                    return v
                raise ValueError(f"Unknown variable: {name}")
            if kind == "ref":
                _, sheet, col, row = node
                target = _resolve_sheet(sheet, category)
                v = eval_cell(target, row, col)
                if not isinstance(v, float):
                    raise ValueError('Non-numeric reference')
                return v
            if kind == "range":
                raise ValueError('Ranges are only valid within SUM()')
            if kind == "call":
                _, fname, arg = node
                if fname not in ("SOMME", "SUM"):
                    raise ValueError('Only SUM() is supported')
                if arg[0] == "range":
                    _, sheet, c1, r1, c2, r2 = arg
                    return eval_range_sum(sheet, c1, r1, c2, r2, category)
                if arg[0] == "ref":
                    _, sheet, col, row = arg
                    target = _resolve_sheet(sheet, category)
                    v = eval_cell(target, row, col)
                    return v if isinstance(v, float) else 0.0
                v = eval_node(arg, category)
                return v if isinstance(v, float) else 0.0
            if kind == "binop":
                _, op, left, right = node
                lv, rv = eval_node(left, category), eval_node(right, category)
                if op == "+":
                    return lv + rv
                if op == "-":
                    return lv - rv
                if op == "*":
                    return lv * rv
                return lv / rv
            if kind == "unary":
                _, op, operand = node
                v = eval_node(operand, category)
                return -v if op == "-" else v
            raise ValueError('Unsupported formula expression')

        for category in MATERIAL_CATEGORY_DEFS:
            rows = self.material_categories.get(category, {}).get("rows", [])
            _, columns = MATERIAL_CATEGORY_DEFS[category]
            for row_idx in range(len(rows)):
                for col_idx in range(len(columns)):
                    eval_cell(category, row_idx, col_idx)

        return cache

    @staticmethod
    def _format_computed_value(value):
        if isinstance(value, float):
            if value == int(value):
                return str(int(value))
            return f"{value:.3f}".rstrip("0").rstrip(".")
        return "" if value is None else str(value)

    def _refresh_material_trees(self):
        """Point d'entrée public (nom conservé : appelé par project_io.py après
        chargement d'un projet). Recale la grille sur les données puis affiche
        les valeurs calculées."""
        if not hasattr(self, "material_cell_widgets"):
            return

        for key in MATERIAL_CATEGORY_DEFS:
            rows = self.material_categories.get(key, {}).get("rows", [])
            existing_rows = len({r for (r, _c) in self.material_cell_widgets.get(key, {})})
            if existing_rows != len(rows):
                self._rebuild_material_grid_rows(key)

        computed = self._compute_material_formulas()
        focused = self.side_panel_material.focus_get() if hasattr(self, "side_panel_material") else None

        for key, widgets in self.material_cell_widgets.items():
            _, columns = MATERIAL_CATEGORY_DEFS[key]
            rows = self.material_categories.get(key, {}).get("rows", [])
            for (row_idx, col_idx), entry in widgets.items():
                if entry is focused:
                    continue  # ne pas écraser une saisie en cours
                col_name = columns[col_idx]
                raw = rows[row_idx].get(col_name, "") if row_idx < len(rows) else ""
                is_formula = isinstance(raw, str) and raw.strip().startswith("=")
                if is_formula:
                    result = computed.get((key, row_idx, col_idx), "#ERR")
                    display = self._format_computed_value(result)
                    is_error = isinstance(result, str) and result.startswith("#")
                else:
                    display = "" if raw is None else str(raw)
                    is_error = False
                entry.delete(0, tk.END)
                entry.insert(0, display)
                entry.configure(
                    background="#FFF9C4" if is_formula else "white",
                    foreground="#C62828" if is_error else "black",
                )
