"""Construction de l'interface ruban (onglets, panneaux lateraux)."""

import csv
import json
import math
import os
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

try:
    import io
    from PIL import Image, ImageDraw, ImageTk, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


QUICK_START_GUIDE = """QUICK START

1. On Home, import an existing JSON project or begin with a new project.
2. In Installation area, load the roof image, draw a known distance and enter its actual length to calibrate the scale.
3. Draw the installation zones and adjust them in the side panel.
4. In Layout and blocks, enter the panel dimensions in millimetres and generate the layout. Create blocks and assign panels.
5. In Stringing, set the minimum and maximum number of panels per string and generate or edit the strings.
6. In MPPT assignment, configure the blocks' capacities and assign strings to MPPTs.
7. Use Equipment for component data and calculations, Shadow for simulations, and Home or Stringing for exports.
8. Save a JSON project using Home > Project > Save or Ctrl+S.

The formula and engineering calculation tabs explain the calculations used by the application.
"""

FORMULA_GUIDE = """FORMULAS — EQUIPMENT TAB

There are two calculation areas: the free spreadsheet in the centre and the structured equipment sheet in the side panel. Every formula begins with =. Row numbers start at 1.

FREE SPREADSHEET
• Operators: +, -, *, /, % (modulo), ** (power), parentheses and unary + / -.
• Cell references: =A1*B1. An empty referenced cell is treated as 0.
• Sum: =SUM(A1:A10) or =SUM(A1:B5). Non-numeric cells in a range are ignored. Older saved formula aliases remain supported.
• Project variables: =PANEL_COUNT*720 ; =PV_CAPACITY_WP/1000 ; =STRING1_PANEL_COUNT. Search the side explorer and double-click a variable to insert it.
• Clear-sky variables: IRRADIANCE_NOW_W_M2 and IRRADIANCE_AVG_W_M2 (daylight hourly mean on the chosen date); SHADOW_AVG_PCT, SIM_LOSS_KWH and SIM_PRODUCTION_KWH come from the latest calculations. These are estimates, not measured weather data.
• Other variables: STRING_COUNT, INVERTER_COUNT; ZONE1_PANEL_COUNT, ZONE1_WIDTH_MM, ZONE1_HEIGHT_MM, ZONE1_ROWS, ZONE1_COLUMNS; STRING1_PANEL_COUNT. Indices depend on the existing zones and strings.
• If cable parameters are set: CURRENT_A, VOLTAGE_V, LENGTH_M, RESISTIVITY, TARGET_DROP_PCT. Variable names are retained for compatibility with saved formulas.

STRUCTURED EQUIPMENT SHEET (side panel)
• Operators: +, -, *, / and parentheses. % and ** are not supported here.
• An unprefixed reference points to the current category: =C2*1.05.
• Reference another category: =Inverters!C1 or =Modules!C2. Accepted names: Modules, Inverters, Cables, Custom and the previous aliases (legacy saved aliases).
• Sum: =SUM(C2:C10) or =SUM(Inverters!C1:C4). Older saved aliases remain valid.
• Global variables: PANEL_COUNT, STRING_COUNT, INVERTER_COUNT, PV_CAPACITY_WP.
• A custom row with Field = Margin and Value = 0.05 permits =C2*(1+Margin). Spaces and punctuation in field names become underscores.

NOTES
• PANEL_COUNT counts layout panels; STRING_COUNT counts nonempty strings; INVERTER_COUNT counts placed inverters.
• PV_CAPACITY_WP = PANEL_COUNT × Pmax (W) in the first PV module row if numeric, otherwise 0. Unit: watts peak.
• Empty cells in the structured sheet count as 0. An invalid formula displays #ERR; circular references in the free spreadsheet display #CIRC!.
• Common Excel functions such as AVERAGE(), IF() and VLOOKUP() are not supported. The free spreadsheet does not accept category references such as Modules!C1.
"""

TECHNICAL_GUIDE = """ENGINEERING CALCULATIONS

LAYOUT AND SCALE
• Scale = reference segment length (image pixels) / entered real length (mm), in pixels/mm.
• Zone width and height (mm) = dimensions in image pixels / scale.
• Columns = floor(zone width / panel width); rows = floor(zone height / panel height). Remaining space is distributed according to horizontal and vertical alignment.
• The zone angle rotates the complete panel grid around the zone centre. The layout calculations do not verify installation clearances or fasteners.

OBSTACLE SHADOW
• Solar position uses latitude, longitude, date, local time and UTC offset. Azimuth is measured clockwise from north.
• At each roof height: shadow length (mm) = (obstacle height − roof zone height) / tan(solar elevation). An obstacle below the roof zone casts no shadow on it.
• Shaded fraction = overlapping shadow area / panel area × obstacle opacity. Opacity 0.55 blocks 55% of light within the overlapping area.
• The obstacle has a square footprint with the configured width; the shadow polygon joins that footprint to the projected top.

IRRADIANCE AND ENERGY — SIMPLIFIED CLEAR-SKY MODEL
• DNI (W/m²) = 1367 × 0.7 ^ (air mass ^ 0.675), where air mass = 1 / cos(zenith). DNI is zero at solar elevation ≤ 0.5°.
• Plane-of-array irradiance = direct incidence + simplified isotropic diffuse component (12% of horizontal DNI) + ground reflection (albedo 0.20). Tilt 0° means horizontal; azimuths 0° north, 90° east, 180° south, 270° west.
• Effective irradiance G = plane-of-array irradiance × (1 − shaded fraction). Cell temperature (°C) = 20 + (NOCT − 20) × G / 800.
• Panel power (W) = Pmax STC × G / 1000 × max[0, 1 + temperature coefficient (%/°C) × (cell temperature − 25) / 100].
• Interval energy (Wh) = power (W) × duration (h). Loss = unshaded energy − shaded energy; loss (%) = 100 × lost energy / unshaded energy when positive. 1 kWh = 1,000 Wh.
• Multi-day simulations evaluate irradiance and shading at each interval midpoint and sum energy. The chart groups the selected simulation results by the chosen number of hours per point.
• String losses sum estimated panel losses; the within-string spread is the worst panel loss (%) minus the best. This model does not calculate I-V curves, bypass diode behaviour or electrical string mismatch losses.
• Results assume theoretical clear skies and a 20°C reference ambient temperature. They are not a forecast based on measured weather data.

CABLING
• A string's route starts at its last panel, reaches the zone gathering point if available, then follows the cable network, walkable area or a direct orthogonal path to the inverter. Real length (mm) = route pixels / scale.
• Calculated DC cross-section (mm²) = 2 × one-way length (m) × current (A) × resistivity (Ω·mm²/m) / maximum voltage drop (V). The voltage-drop limit is the percentage entered in DC sizing (default: 1%).
• Recommended cross-section is the first adequate listed value from 1.5 to 240 mm². If the required section exceeds 240 mm², no standard recommendation is shown. Actual voltage drop (%) = 100 × 2 × one-way length × resistivity × current / (recommended cross-section × voltage).
• The Cabling route inventory shows each calculated string-to-inverter route and its method. Use "Use longest calculated route" in DC sizing to copy the longest length; enter a maximum voltage-drop percentage. Ampacity, cable temperature and protective devices require separate checks.
"""

class UIBuildersMixin:
    def _load_ui_preferences(self):
        self.ui_font_percent = 100
        settings_path = os.path.join(self.projects_dir, "ui_preferences.json")
        try:
            with open(settings_path, "r", encoding="utf-8") as settings_file:
                settings = json.load(settings_file)
            percentage = int(settings.get("font_percent", 100))
            if 75 <= percentage <= 200:
                self.ui_font_percent = percentage
            size = settings.get("window_size", "Automatic")
            if size != "Automatic":
                width, height = (int(part) for part in size.lower().split("x"))
                self.root.geometry(f"{min(width, self.root.winfo_screenwidth())}x"
                                   f"{min(height, self.root.winfo_screenheight())}")
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            pass
        self._default_tk_scaling = float(self.root.tk.call("tk", "scaling"))
        self.root.tk.call("tk", "scaling", self._default_tk_scaling * self.ui_font_percent / 100)

    def _show_ui_preferences(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Display settings")
        dialog.transient(self.root)
        self._center_window(dialog, 360, 230)
        body = ttk.Frame(dialog, padding=16)
        body.pack(fill=tk.BOTH, expand=True)
        ttk.Label(body, text="Font size (%)").grid(row=0, column=0, sticky="w", pady=8)
        font_var = tk.StringVar(value=str(self.ui_font_percent))
        ttk.Spinbox(body, from_=75, to=200, increment=5, textvariable=font_var,
                    width=9).grid(row=0, column=1, sticky="w", pady=8)
        ttk.Label(body, text="Window size").grid(row=1, column=0, sticky="w", pady=8)
        size_var = tk.StringVar(value=f"{self.root.winfo_width()}x{self.root.winfo_height()}")
        combo = ttk.Combobox(body, textvariable=size_var, width=15,
                             values=("Automatic", "1024x768", "1280x800", "1440x900"))
        combo.grid(row=1, column=1, sticky="w", pady=8)

        def apply():
            try:
                percentage = int(font_var.get())
                if not 75 <= percentage <= 200:
                    raise ValueError("Font size must be between 75% and 200%.")
                size = size_var.get().strip()
                if size == "Automatic":
                    width = min(1440, max(320, self.root.winfo_screenwidth() - 80))
                    height = min(900, max(240, self.root.winfo_screenheight() - 80))
                else:
                    width, height = (int(part) for part in size.lower().split("x"))
                    if width < 320 or height < 240:
                        raise ValueError("Minimum size: 320x240.")
                self.ui_font_percent = percentage
                self.root.tk.call("tk", "scaling", self._default_tk_scaling * percentage / 100)
                self.root.geometry(f"{min(width, self.root.winfo_screenwidth())}x"
                                   f"{min(height, self.root.winfo_screenheight())}")
                with open(settings_path := os.path.join(self.projects_dir, "ui_preferences.json"),
                          "w", encoding="utf-8") as settings_file:
                    json.dump({"font_percent": percentage, "window_size": size}, settings_file)
                dialog.destroy()
            except (ValueError, OSError) as error:
                messagebox.showerror("Display settings", str(error), parent=dialog)

        ttk.Button(body, text="Apply", command=apply).grid(row=2, column=1, pady=18, sticky="e")

    def _build_root_scroller(self):
        """One outer scrollbar pair for the complete toolbar and work area."""
        shell = ttk.Frame(self.root)
        shell.pack(fill=tk.BOTH, expand=True)
        shell.rowconfigure(0, weight=1)
        shell.columnconfigure(0, weight=1)

        self.ui_canvas = tk.Canvas(shell, highlightthickness=0, borderwidth=0)
        self.ui_canvas.grid(row=0, column=0, sticky="nsew")
        self.ui_vbar = ttk.Scrollbar(shell, orient=tk.VERTICAL, command=self.ui_canvas.yview)
        self.ui_vbar.grid(row=0, column=1, sticky="ns")
        self.ui_hbar = ttk.Scrollbar(shell, orient=tk.HORIZONTAL, command=self.ui_canvas.xview)
        self.ui_hbar.grid(row=1, column=0, sticky="ew")
        self.ui_canvas.configure(xscrollcommand=self.ui_hbar.set,
                                 yscrollcommand=self.ui_vbar.set)

        self.ui_content = ttk.Frame(self.ui_canvas)
        self._ui_window = self.ui_canvas.create_window(0, 0, window=self.ui_content,
                                                        anchor="nw")
        self.ui_content.bind("<Configure>", self._update_root_scrollregion)
        self.ui_canvas.bind("<Configure>", self._resize_root_scroll_content)

    def _update_root_scrollregion(self, event=None):
        self.ui_canvas.configure(scrollregion=self.ui_canvas.bbox("all"))

    def _resize_root_scroll_content(self, event):
        # Fill the viewport when there is room; retain enough size to scroll
        # the full toolbar and the active side panel on smaller screens.
        self.ui_canvas.itemconfigure(
            self._ui_window,
            width=max(event.width, self.ui_content.winfo_reqwidth(), 1024),
            height=max(event.height, self.ui_content.winfo_reqheight(), 768),
        )
        self._update_root_scrollregion()

    def _collapse_treeview(self, tree):
        """Collapse every hierarchical item without changing selection or content."""
        def collapse(parent=''):
            for item in tree.get_children(parent):
                try:
                    tree.item(item, open=False)
                except tk.TclError:
                    pass
                collapse(item)
        collapse()

    def _collapse_all_treeviews(self, widget=None):
        """Start every ttk.Treeview hierarchy collapsed by default."""
        widget = widget or self.root
        try:
            children = widget.winfo_children()
        except (AttributeError, tk.TclError):
            return
        for child in children:
            if isinstance(child, ttk.Treeview):
                self._collapse_treeview(child)
            self._collapse_all_treeviews(child)

    def _show_help(self, page="quick"):
        """Affiche une aide intégrée sans dépendre d'un fichier externe."""
        window = tk.Toplevel(self.root)
        window.title('Help — Tutorial and formulas')
        window.transient(self.root)
        self._center_window(window, width=760, height=590)
        window.minsize(500, 350)

        notebook = ttk.Notebook(window)
        notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        pages = []
        for title, content in (('Quick start', QUICK_START_GUIDE),
                               ('Spreadsheet formulas', FORMULA_GUIDE),
                               ('Engineering calculations', TECHNICAL_GUIDE)):
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=title)
            text_widget = tk.Text(frame, wrap=tk.WORD, padx=15, pady=12,
                                  font=("Arial", 11), cursor="arrow")
            scrollbar = ttk.Scrollbar(frame, orient=tk.VERTICAL,
                                      command=text_widget.yview)
            text_widget.configure(yscrollcommand=scrollbar.set)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            text_widget.insert("1.0", content)
            text_widget.configure(state=tk.DISABLED)
            pages.append(frame)
        notebook.select(pages[{"quick": 0, "formulas": 1, "technical": 2}.get(page, 0)])
        ttk.Button(window, text='Close', command=window.destroy).pack(pady=(0, 10))

    def _center_window(self, window, width=450, height=350):
        window.update_idletasks()
        screen_w = window.winfo_screenwidth()
        screen_h = window.winfo_screenheight()
        x = (screen_w // 2) - (width // 2)
        y = (screen_h // 2) - (height // 2)
        window.geometry(f"{width}x{height}+{x}+{y}")

    def _fix_combobox_popdown_position(self, combo):
        try:
            popdown = combo.tk.call("ttk::combobox::PopdownWindow", combo)
        except tk.TclError:
            return

        def _reposition(event=None):
            try:
                x = combo.winfo_rootx()
                y = combo.winfo_rooty() + combo.winfo_height()
                combo.tk.call("wm", "geometry", popdown, f"+{x}+{y}")
            except tk.TclError:
                pass

        combo.tk.call("bind", popdown, "<Map>", combo.register(_reposition))

    def _zoom_button_change(self, factor):
        old_zoom = self.zoom_level
        new_zoom = max(0.2, min(5.0, old_zoom * factor))
        if old_zoom != new_zoom:
            self.zoom_level = new_zoom
            self.cell_size_px = max(10, int(40 * self.zoom_level))
            self.draw_grid()

    def _reset_zoom(self):
        self.zoom_level = 1.0
        self.cell_size_px = 40
        self.draw_grid()

    @staticmethod
    def _get_image_resample_filter():
        """Retourne un filtre de redimensionnement compatible avec Pillow."""
        resampling = getattr(Image, "Resampling", None)
        if resampling is not None:
            return resampling.LANCZOS
        return Image.LANCZOS

    # ========================================================
    # STRUCTURATION DU RUBAN
    # ========================================================

    def _build_ribbon_ui(self):
        self.ribbon_frame = ttk.Frame(self.ui_content)
        self.ribbon_frame.pack(side=tk.TOP, fill=tk.X)

        self.ribbon_notebook = ttk.Notebook(self.ribbon_frame)
        self.ribbon_notebook.pack(fill=tk.X, expand=True)

        # Onglets
        self.tab_file = ttk.Frame(self.ribbon_notebook, padding=5)
        self.tab_roof = ttk.Frame(self.ribbon_notebook, padding=5)
        self.tab_layout = ttk.Frame(self.ribbon_notebook, padding=5)
        self.tab_stringing = ttk.Frame(self.ribbon_notebook, padding=5)
        self.tab_equipment = ttk.Frame(self.ribbon_notebook, padding=5)
        self.tab_shadow = ttk.Frame(self.ribbon_notebook, padding=5)
        self.tab_material = ttk.Frame(self.ribbon_notebook, padding=5)
        self.tab_diagram = ttk.Frame(self.ribbon_notebook, padding=5)
        self.tab_notes = ttk.Frame(self.ribbon_notebook, padding=5)

        self.ribbon_notebook.add(self.tab_file, text=' 📁 Home ')
        self.ribbon_notebook.add(self.tab_roof, text=' 🏠 Installation area ')
        self.ribbon_notebook.add(self.tab_layout, text=' 📐 Layout and blocks ')
        self.ribbon_notebook.add(self.tab_stringing, text=" ⚡ Stringing ")
        self.ribbon_notebook.add(self.tab_equipment, text=' 🔀 MPPT assignment ')
        self.ribbon_notebook.add(self.tab_shadow, text=' 🌑 Shadow ')
        self.ribbon_notebook.add(self.tab_material, text=' 🧮 Spreadsheet ')
        self.ribbon_notebook.add(self.tab_diagram, text=' 🗺️ Electrical single-line diagram ')
        self.ribbon_notebook.add(self.tab_notes, text=' ⚡ Cabling ')

        self._build_tab_file_tools()
        self._build_tab_roof_tools()
        self._build_tab_layout_tools()
        self._build_tab_stringing_tools()
        self._build_tab_equipment_tools()
        self._build_tab_shadow_tools()
        self._build_tab_material_tools()
        self._build_tab_diagram_tools()
        self._build_tab_notes_tools()

        self.ribbon_notebook.bind("<<NotebookTabChanged>>", self._on_ribbon_tab_changed)

        # Hierarchical explorers start closed. Run once after idle and once after
        # the remaining startup widgets/data have had time to populate.
        self.root.after_idle(self._collapse_all_treeviews)
        self.root.after(250, self._collapse_all_treeviews)

    # ========================================================
    # ONGLET FICHIER
    # ========================================================

    def _build_tab_file_tools(self):
        # ----------------------------------------------------
        # MENU DÉROULANT : PROJET
        # ----------------------------------------------------
        mb_project = ttk.Menubutton(self.tab_file, text='📁 Project')
        menu_project = tk.Menu(mb_project, tearoff=0)
        menu_project.add_command(label='📂 Import JSON', command=self.import_project)
        menu_project.add_separator()
        menu_project.add_command(label='💾 Save', command=self.save_project)
        mb_project["menu"] = menu_project
        mb_project.pack(side=tk.LEFT, padx=5)

        ttk.Separator(self.tab_file, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # ----------------------------------------------------
        # MENU DÉROULANT : EXPORT
        # ----------------------------------------------------
        mb_export = ttk.Menubutton(self.tab_file, text='📤 Export screenshot')
        menu_export = tk.Menu(mb_export, tearoff=0)
        menu_export.add_command(label='🖼️ Export final JPG', command=self.export_jpg_final)
        mb_export["menu"] = menu_export
        mb_export.pack(side=tk.LEFT, padx=5)

        ttk.Separator(self.tab_file, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        self.lbl_project_info = ttk.Label(self.tab_file, text=f"Active project: {self.project_name}", font=("Arial", 10, "bold"))
        self.lbl_project_info.pack(side=tk.LEFT, padx=10)

        ttk.Button(self.tab_file, text='❔ Quick start',
                   command=self._show_help).pack(side=tk.RIGHT, padx=5)
        ttk.Button(self.tab_file, text='ƒx Formula guide',
                   command=lambda: self._show_help("formulas")).pack(side=tk.RIGHT, padx=5)
        ttk.Button(self.tab_file, text='∑ Engineering calculations',
                   command=lambda: self._show_help("technical")).pack(side=tk.RIGHT, padx=5)
        ttk.Button(self.tab_file, text="⚙️ Display settings",
                   command=self._show_ui_preferences).pack(side=tk.RIGHT, padx=5)

    # ========================================================
    # ONGLET TOIT & ÉCHELLE
    # ========================================================

    def _build_tab_roof_tools(self):
        # ----------------------------------------------------
        # MENU DÉROULANT : IMAGE
        # ----------------------------------------------------
        # Roof image import is available under Home > Project.

        # ----------------------------------------------------
        # MENU DÉROULANT : ÉCHELLE & MESURE
        # ----------------------------------------------------
        mb_measure = ttk.Menubutton(self.tab_roof, text='📏 Scale and measurements')
        menu_measure = tk.Menu(mb_measure, tearoff=0)
        menu_measure.add_command(label='📏 Draw scale reference', command=self._activate_scale_mode)
        
        menu_measure.add_command(
            label='Aligned dimension',
            command=lambda: self._activate_dimension('aligned')
        )
        menu_measure.add_command(label='📏 Measure distance to zone', command=self._toggle_distance_mode)
        menu_measure.add_separator()
        menu_measure.add_command(label='🗑️ Clear measurements', command=self.clear_measures)
        menu_measure.add_command(label='🗑️ Clear distance markers', command=self.clear_distance_markers)
        mb_measure["menu"] = menu_measure
        mb_measure.pack(side=tk.LEFT, padx=5)

        polygons = ttk.Menubutton(self.tab_roof, text='🔷 Cable routing area')
        polygon_menu = tk.Menu(polygons, tearoff=0)
        polygon_menu.add_command(label='➕ Draw cable routing area', command=self._activate_polygon_draw_mode)
        polygon_menu.add_command(label='✅ Finish drawing (right-click)', command=self._finish_polygon_draw)
        polygon_menu.add_command(label='Transform selected area', command=self._activate_polygon_select_mode)
        polygon_menu.add_command(label='Installation heights / cable bridges', command=self._show_installation_heights)
        polygon_menu.add_separator()
        polygon_menu.add_command(label='🗑️ Delete selected area', command=self.delete_active_polygon)
        polygons['menu'] = polygon_menu
        polygons.pack(side=tk.LEFT, padx=5)
        self.combo_polygons = ttk.Combobox(self.tab_roof, values=[], width=10, state='readonly')
        self.combo_polygons.pack(side=tk.LEFT, padx=2)
        self.combo_polygons.bind('<<ComboboxSelected>>', self._on_polygon_combo_selected)
        self._fix_combobox_popdown_position(self.combo_polygons)

        ttk.Separator(self.tab_roof, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

        # ----------------------------------------------------
        # MENU DÉROULANT : ZONES
        # ----------------------------------------------------
        mb_zones = ttk.Menubutton(self.tab_roof, text='🔲 Zones')
        menu_zones = tk.Menu(mb_zones, tearoff=0)
        menu_zones.add_command(label='➕ Draw rectangular zone', command=self._activate_zone_mode)
        menu_zones.add_command(label='Transform zones', command=self._activate_zone_select_mode)
        menu_zones.add_command(label='Installation heights', command=self._show_installation_heights)
        menu_zones.add_command(label='🗑️ Delete zone(s)', command=self.delete_active_zone)
        mb_zones["menu"] = menu_zones
        mb_zones.pack(side=tk.LEFT, padx=5)

        ttk.Label(self.tab_roof, text="Zone:").pack(side=tk.LEFT, padx=(5, 2))
        self.combo_zones = ttk.Combobox(self.tab_roof, values=[], width=8, state="readonly")
        self.combo_zones.pack(side=tk.LEFT, padx=2)
        self.combo_zones.bind("<<ComboboxSelected>>", self._on_zone_combo_selected)
        self._fix_combobox_popdown_position(self.combo_zones)

        ttk.Button(
            self.tab_roof,
            text='⚙️ Settings',
            command=self._toggle_zone_params_panel
        ).pack(side=tk.LEFT, padx=5)

        ttk.Separator(self.tab_roof, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

        mb_zoom_roof = ttk.Menubutton(self.tab_roof, text="🔍 Zoom")
        menu_zoom_roof = tk.Menu(mb_zoom_roof, tearoff=0)
        menu_zoom_roof.add_command(label='🔍 Zoom in (+)', command=lambda: self._zoom_button_change(1.2))
        menu_zoom_roof.add_command(label='🔍 Zoom out (-)', command=lambda: self._zoom_button_change(1/1.2))
        menu_zoom_roof.add_separator()
        menu_zoom_roof.add_command(label='🎯 Reset (100%)', command=self._reset_zoom)
        mb_zoom_roof["menu"] = menu_zoom_roof
        mb_zoom_roof.pack(side=tk.RIGHT, padx=5)

    # ========================================================
    # ONGLET LAYOUT
    # ========================================================

    def _build_tab_layout_tools(self):
        ttk.Label(self.tab_layout, text='Panel (mm) W:').pack(side=tk.LEFT, padx=2)
        self.entry_width = ttk.Entry(self.tab_layout, width=5)
        self.entry_width.insert(0, str(int(self.panel_width_mm)))
        self.entry_width.pack(side=tk.LEFT, padx=2)

        ttk.Label(self.tab_layout, text="H:").pack(side=tk.LEFT, padx=2)
        self.entry_height = ttk.Entry(self.tab_layout, width=5)
        self.entry_height.insert(0, str(int(self.panel_height_mm)))
        self.entry_height.pack(side=tk.LEFT, padx=2)

        ttk.Button(self.tab_layout, text='Apply', command=self.update_dimensions).pack(side=tk.LEFT, padx=5)
        self.var_continuous_numbers = tk.BooleanVar(value=True)
        ttk.Checkbutton(self.tab_layout, text="Consecutive panel numbers",
                        variable=self.var_continuous_numbers).pack(side=tk.LEFT, padx=5)

        ttk.Label(self.tab_layout, text="Tilt °:").pack(side=tk.LEFT, padx=(8, 2))
        self.entry_layout_tilt = ttk.Entry(self.tab_layout, width=4)
        self.entry_layout_tilt.insert(0, str(self.panel_tilt_deg))
        self.entry_layout_tilt.pack(side=tk.LEFT, padx=2)
        ttk.Label(self.tab_layout, text="Azimuth °:").pack(side=tk.LEFT, padx=2)
        self.entry_layout_azimuth = ttk.Entry(self.tab_layout, width=4)
        self.entry_layout_azimuth.insert(0, str(self.panel_azimuth_deg))
        self.entry_layout_azimuth.pack(side=tk.LEFT, padx=2)
        ttk.Button(self.tab_layout, text="Apply orientation", command=self.apply_panel_orientation).pack(side=tk.LEFT, padx=4)
        ttk.Label(self.tab_layout, text="Shift-click to select; none = all panels").pack(side=tk.LEFT, padx=2)

        ttk.Separator(self.tab_layout, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # ----------------------------------------------------
        # MENU DÉROULANT : LAYOUT
        # ----------------------------------------------------
        mb_layout = ttk.Menubutton(self.tab_layout, text="🚀 Layout")
        menu_layout = tk.Menu(mb_layout, tearoff=0)
        menu_layout.add_command(label='🚀 Generate layout', command=self.generate_panels_from_zones)
        mb_layout["menu"] = menu_layout
        mb_layout.pack(side=tk.LEFT, padx=5)

        ttk.Separator(self.tab_layout, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Label(self.tab_layout, text='Active block:').pack(side=tk.LEFT, padx=2)
        self.combo_blocks = ttk.Combobox(self.tab_layout, values=['No Block'], width=12, state="readonly")
        self.combo_blocks.set('No Block')
        self.combo_blocks.pack(side=tk.LEFT, padx=2)
        self.combo_blocks.bind("<<ComboboxSelected>>", self._on_block_selected)
        self._fix_combobox_popdown_position(self.combo_blocks)

        # ----------------------------------------------------
        # MENU DÉROULANT : ACTIONS SUR LES BLOCS
        # ----------------------------------------------------
        mb_blocks = ttk.Menubutton(self.tab_layout, text='🎨 Block actions')
        menu_blocks = tk.Menu(mb_blocks, tearoff=0)
        menu_blocks.add_command(label='+ New block', command=self.create_new_block)
        menu_blocks.add_command(label='🗑️ Delete active block', command=self.delete_active_block)
        menu_blocks.add_separator()

        self.var_block_paint_only = tk.BooleanVar(value=False)
        menu_blocks.add_checkbutton(
            label='🖌️ Paint block only',
            variable=self.var_block_paint_only
        )

        mb_blocks["menu"] = menu_blocks
        mb_blocks.pack(side=tk.LEFT, padx=5)

        ttk.Separator(self.tab_layout, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        # ----------------------------------------------------
        # PLACEMENT PHYSIQUE DE L'ONDULEUR DU BLOC ACTIF
        # ----------------------------------------------------
        mb_inverter = ttk.Menubutton(self.tab_layout, text="🔌 Active block inverter")
        inverter_menu = tk.Menu(mb_inverter, tearoff=0)
        inverter_menu.add_command(label="📍 Place inverter for active block",
                                  command=self.open_inverter_selection_dialog)
        inverter_menu.add_command(label="🗑️ Remove placement",
                                  command=self.remove_inverter_placement)
        mb_inverter["menu"] = inverter_menu
        mb_inverter.pack(side=tk.LEFT, padx=5)

        mb_zoom_roof = ttk.Menubutton(self.tab_layout, text="🔍 Zoom")
        menu_zoom_roof = tk.Menu(mb_zoom_roof, tearoff=0)
        menu_zoom_roof.add_command(label='🔍 Zoom in (+)', command=lambda: self._zoom_button_change(1.2))
        menu_zoom_roof.add_command(label='🔍 Zoom out (-)', command=lambda: self._zoom_button_change(1/1.2))
        menu_zoom_roof.add_separator()
        menu_zoom_roof.add_command(label='🎯 Reset (100%)', command=self._reset_zoom)
        mb_zoom_roof["menu"] = menu_zoom_roof
        mb_zoom_roof.pack(side=tk.RIGHT, padx=5)

    # ========================================================
    # ONGLET STRINGING
    # ========================================================

    def _build_tab_stringing_tools(self):
        ttk.Button(self.tab_stringing, text='📊 Export CSV', command=self.export_csv).pack(side=tk.LEFT, padx=5)
        ttk.Button(self.tab_stringing, text='⚡ Generate strings', command=self.generate_auto_strings).pack(side=tk.LEFT, padx=5)

        config = ttk.Menubutton(self.tab_stringing, text='⚙️ Configuration')
        config_menu = tk.Menu(config, tearoff=0)
        self.string_min_var = tk.StringVar(value='6')
        self.string_max_var = tk.StringVar(value='10')
        self.string_direction_var = tk.StringVar(value='Auto (layout)')
        config_menu.add_command(label='⚙️ String settings…', command=self._show_string_settings)
        config['menu'] = config_menu
        config.pack(side=tk.LEFT, padx=5)

        self.var_dim_inactive_strings = tk.BooleanVar(value=False)
        actions = ttk.Menubutton(self.tab_stringing, text='⚡ String actions')
        actions_menu = tk.Menu(actions, tearoff=0)
        actions_menu.add_command(label='➕ Add string', command=self.add_new_string)
        actions_menu.add_command(label='🗑️ Delete active string', command=self.delete_active_string)
        actions_menu.add_checkbutton(label='👁️ Dim other strings',
                                     variable=self.var_dim_inactive_strings, command=self.draw_grid)
        actions_menu.add_separator()
        actions_menu.add_command(label='❌ Delete all strings', command=self.clear_all_strings)
        actions['menu'] = actions_menu
        actions.pack(side=tk.LEFT, padx=5)

        ttk.Label(self.tab_stringing, text='Active string:').pack(side=tk.LEFT, padx=(10, 2))
        self.combo_strings = ttk.Combobox(self.tab_stringing, values=['String 1'], width=12, state='readonly')
        self.combo_strings.set('String 1')
        self.combo_strings.pack(side=tk.LEFT, padx=5)
        self.combo_strings.bind('<<ComboboxSelected>>', self._on_active_string_changed)
        self._fix_combobox_popdown_position(self.combo_strings)

        zoom = ttk.Menubutton(self.tab_stringing, text='🔍 Zoom')
        zoom_menu = tk.Menu(zoom, tearoff=0)
        zoom_menu.add_command(label='🔍 Zoom in (+)', command=lambda: self._zoom_button_change(1.2))
        zoom_menu.add_command(label='🔍 Zoom out (-)', command=lambda: self._zoom_button_change(1/1.2))
        zoom_menu.add_separator()
        zoom_menu.add_command(label='🎯 Reset (100%)', command=self._reset_zoom)
        zoom['menu'] = zoom_menu
        zoom.pack(side=tk.RIGHT, padx=5)

    def _show_string_settings(self):
        dialog = tk.Toplevel(self.root)
        dialog.title('String configuration')
        dialog.transient(self.root)
        dialog.grab_set()
        settings = ttk.Frame(dialog, padding=16)
        settings.pack(fill=tk.BOTH, expand=True)
        ttk.Label(settings, text='Minimum panels per string:').grid(row=0, column=0, sticky='w', pady=6)
        min_entry = ttk.Entry(settings, textvariable=self.string_min_var, width=8)
        min_entry.grid(row=0, column=1, padx=8)
        ttk.Label(settings, text='Maximum panels per string:').grid(row=1, column=0, sticky='w', pady=6)
        ttk.Entry(settings, textvariable=self.string_max_var, width=8).grid(row=1, column=1, padx=8)
        ttk.Label(settings, text='String direction:').grid(row=2, column=0, sticky='w', pady=6)
        ttk.Combobox(settings, textvariable=self.string_direction_var,
                     values=['Auto (layout)', 'Horizontal', 'Vertical'],
                     state='readonly', width=15).grid(row=2, column=1, padx=8)
        ttk.Button(settings, text='Close', command=dialog.destroy).grid(row=3, column=1, pady=(12, 0))
        min_entry.focus_set()

    # ========================================================
    # ONGLET MATÉRIEL (ONDULEURS / MPPT)
    # ========================================================

    def _build_tab_equipment_tools(self):
        actions = ttk.Menubutton(self.tab_equipment, text='🔀 MPPT actions')
        action_menu = tk.Menu(actions, tearoff=0)
        action_menu.add_command(label='🔀 Assign strings to MPPTs', command=self._auto_distribute_strings_to_mppt)
        action_menu.add_command(label='🧹 Clear MPPT assignments', command=self._clear_mppt_assignments)
        action_menu.add_checkbutton(label='👁️ Dim unselected strings',
                                    variable=self.var_dim_mppt_strings, command=self.draw_grid)
        actions['menu'] = action_menu
        actions.pack(side=tk.LEFT, padx=5)

        ttk.Label(self.tab_equipment, text='Current string:').pack(side=tk.LEFT, padx=(8, 2))
        self.combo_mppt_current_string = ttk.Combobox(
            self.tab_equipment, values=['String 1'], width=13, state='readonly')
        self.combo_mppt_current_string.set('String 1')
        self.combo_mppt_current_string.pack(side=tk.LEFT, padx=3)
        self.combo_mppt_current_string.bind('<<ComboboxSelected>>', self._on_mppt_current_string_changed)
        self._fix_combobox_popdown_position(self.combo_mppt_current_string)

        ttk.Button(self.tab_equipment, text='📊 Export CSV',
                   command=self.export_mppt_csv).pack(side=tk.LEFT, padx=5)
        config = ttk.Menubutton(self.tab_equipment, text='⚙️ Configuration')
        config_menu = tk.Menu(config, tearoff=0)
        config_menu.add_command(label='⚙️ Configure block MPPT capacity…',
                                command=self._show_mppt_settings)
        config['menu'] = config_menu
        config.pack(side=tk.LEFT, padx=5)

        # Values are shared with the configuration dialog, and remain available
        # to block updates even after that dialog has been closed.
        self.mppt_block_var = tk.StringVar(value='No Block')
        self.mppt_count_var = tk.StringVar()
        self.mppt_strings_per_var = tk.StringVar()
        self.combo_blocks_equip = ttk.Combobox(
            self.tab_equipment, textvariable=self.mppt_block_var,
            values=['No Block'], state='readonly')
        self.entry_mppt_count = ttk.Entry(self.tab_equipment, textvariable=self.mppt_count_var)
        self.entry_strings_per_mppt = ttk.Entry(self.tab_equipment, textvariable=self.mppt_strings_per_var)
        self.lbl_block_capacity = ttk.Label(self.tab_equipment, text='Capacity: - / -')

        zoom = ttk.Menubutton(self.tab_equipment, text='🔍 Zoom')
        zoom_menu = tk.Menu(zoom, tearoff=0)
        zoom_menu.add_command(label='🔍 Zoom in (+)', command=lambda: self._zoom_button_change(1.2))
        zoom_menu.add_command(label='🔍 Zoom out (-)', command=lambda: self._zoom_button_change(1/1.2))
        zoom_menu.add_separator()
        zoom_menu.add_command(label='🎯 Reset (100%)', command=self._reset_zoom)
        zoom['menu'] = zoom_menu
        zoom.pack(side=tk.RIGHT, padx=5)

    def _show_mppt_settings(self):
        dialog = tk.Toplevel(self.root)
        dialog.title('MPPT configuration')
        dialog.transient(self.root)
        dialog.grab_set()
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(frame, text='Block (inverter):').grid(row=0, column=0, sticky='w', pady=6)
        block_combo = ttk.Combobox(frame, textvariable=self.mppt_block_var,
                                   values=self.combo_blocks_equip['values'], width=18, state='readonly')
        block_combo.grid(row=0, column=1, padx=8)
        block_combo.bind('<<ComboboxSelected>>', self._on_block_selected_equip)
        ttk.Label(frame, text='MPPT count:').grid(row=1, column=0, sticky='w', pady=6)
        ttk.Entry(frame, textvariable=self.mppt_count_var, width=8).grid(row=1, column=1, padx=8)
        ttk.Label(frame, text='Max strings / MPPT:').grid(row=2, column=0, sticky='w', pady=6)
        ttk.Entry(frame, textvariable=self.mppt_strings_per_var, width=8).grid(row=2, column=1, padx=8)
        capacity = ttk.Label(frame, text=self.lbl_block_capacity.cget('text'))
        capacity.grid(row=3, column=0, columnspan=2, sticky='w', pady=6)
        self.lbl_mppt_dialog_capacity = capacity
        ttk.Button(frame, text='Apply', command=self._apply_block_equipment).grid(row=4, column=0, pady=(10, 0))
        ttk.Button(frame, text='Close', command=dialog.destroy).grid(row=4, column=1, pady=(10, 0))
        dialog.bind('<Destroy>', lambda event: setattr(self, 'lbl_mppt_dialog_capacity', None)
                    if event.widget == dialog else None)

    # ========================================================
    # ONGLET MATÉRIEL (FICHE MATÉRIEL DU PROJET)
    # ========================================================

    def _build_tab_material_tools(self):
        file_btn = ttk.Menubutton(self.tab_material, text='📁 File')
        file_menu = tk.Menu(file_btn, tearoff=0)
        file_menu.add_command(label='📤 Export spreadsheet CSV', command=self._export_spreadsheet_csv)
        file_menu.add_command(label='📥 Import spreadsheet CSV', command=self._import_spreadsheet_csv)
        file_btn['menu'] = file_menu
        file_btn.pack(side=tk.LEFT, padx=5)

        chart_btn = ttk.Menubutton(self.tab_material, text='📊 Charts')
        chart_menu = tk.Menu(chart_btn, tearoff=0)
        chart_menu.add_command(label='📈 Chart spreadsheet values', command=self._show_spreadsheet_chart)
        chart_btn['menu'] = chart_menu
        chart_btn.pack(side=tk.LEFT, padx=5)

        tools_btn = ttk.Menubutton(self.tab_material, text='🛠️ Tools')
        tools_menu = tk.Menu(tools_btn, tearoff=0)
        tools_menu.add_command(label='➕ Add row', command=self._add_spreadsheet_row)
        tools_menu.add_command(label='➕ Add column', command=self._add_spreadsheet_col)
        tools_menu.add_command(label='➖ Remove last row', command=self._remove_spreadsheet_row)
        tools_menu.add_command(label='➖ Remove last column', command=self._remove_spreadsheet_col)
        tools_menu.add_separator()
        tools_menu.add_command(label='🔄 Recalculate', command=self._refresh_spreadsheet)
        tools_menu.add_command(label='🗑️ Clear spreadsheet', command=self._clear_spreadsheet)
        tools_menu.add_command(label='ƒx Formula help', command=lambda: self._show_help('formulas'))
        tools_btn['menu'] = tools_menu
        tools_btn.pack(side=tk.LEFT, padx=5)

        zoom = ttk.Menubutton(self.tab_material, text='🔍 Zoom')
        zoom_menu = tk.Menu(zoom, tearoff=0)
        zoom_menu.add_command(label='🔍 Zoom in (+)', command=lambda: self._zoom_spreadsheet(1.2))
        zoom_menu.add_command(label='🔍 Zoom out (-)', command=lambda: self._zoom_spreadsheet(1 / 1.2))
        zoom_menu.add_separator()
        zoom_menu.add_command(label='🎯 Reset (100%)', command=self._reset_spreadsheet_zoom)
        zoom['menu'] = zoom_menu
        zoom.pack(side=tk.RIGHT, padx=5)

    # ========================================================
    # ONGLET SCHÉMA UNIFILAIRE
    # ========================================================
    # Construit par DiagramToolsMixin._build_tab_diagram_tools (mixins/diagram_tools.py)
