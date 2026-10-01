"""Gestion des zones de toiture, de l'echelle et de la zone principale."""

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


class ZoneToolsMixin:
    def _build_main_area(self):
        self.main_container = ttk.Frame(self.ui_content)
        self.main_container.pack(fill=tk.BOTH, expand=True)

        # Frame Canvas
        self.canvas_frame = ttk.Frame(self.main_container)
        self.canvas_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(self.canvas_frame, bg="#e0e0e0", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # ----------------------------------------------------
        # Feuille de calcul (Onglet Matériel) : occupe la même zone que
        # self.canvas, mais uniquement quand l'onglet Matériel est actif.
        # Construite ici (non empaquetée) ; le basculement avec self.canvas
        # est géré par _on_ribbon_tab_changed ci-dessous, ce qui n'affecte
        # en rien le canvas des autres onglets.
        # ----------------------------------------------------
        self._build_material_spreadsheet_area()

        # Panneau latéral d'édition des Strings
        self.side_panel_stringing = ttk.Frame(self.main_container, width=290, padding=5)

        ttk.Label(self.side_panel_stringing, text='Strings and panels', font=("Arial", 11, "bold")).pack(pady=5)

        tree_frame = ttk.Frame(self.side_panel_stringing)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        self.string_tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse", height=20)
        self.string_tree.column("#0", width=255, minwidth=180)
        self.string_tree.tag_configure("string", font=("Arial", 11, "bold"))
        self.string_tree.tag_configure("panel", font=("Arial", 10))
        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self.string_tree.yview)
        self.string_tree.configure(yscrollcommand=tree_scroll.set)
        self.string_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.string_tree.bind("<<TreeviewSelect>>", self._on_string_tree_selected)

        self.string_tree.bind("<ButtonPress-1>", self._on_string_tree_start_drag)
        self.string_tree.bind("<ButtonRelease-1>", self._on_string_tree_drop)

        btn_box = ttk.Frame(self.side_panel_stringing)
        btn_box.pack(fill=tk.X, pady=2)
        ttk.Button(btn_box, text='▲ Move up', command=lambda: self._move_panel_in_string(-1)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(btn_box, text='▼ Move down', command=lambda: self._move_panel_in_string(1)).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        btn_box2 = ttk.Frame(self.side_panel_stringing)
        btn_box2.pack(fill=tk.X, pady=2)
        ttk.Button(btn_box2, text='➕ Add panel', command=self._add_panel_manual_dialog).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)
        ttk.Button(btn_box2, text='➖ Remove', command=self._remove_panel_from_string_list).pack(side=tk.LEFT, expand=True, fill=tk.X, padx=2)

        # ----------------------------------------------------
        # Panneau latéral Matériel : arborescence Onduleur -> MPPT -> String
        # ----------------------------------------------------
        self.side_panel_equipment = ttk.Frame(self.main_container, width=300, padding=5)

        ttk.Label(
            self.side_panel_equipment, text='Inverter / MPPT / string assignment',
            font=("Arial", 10, "bold")
        ).pack(pady=5)

        ttk.Label(
            self.side_panel_equipment,
            text="Drag a string onto an MPPT to reassign it.\n"
                 "Strings on the same MPPT must have the same panel count.",
            font=("Arial", 8), foreground="#555555", justify=tk.LEFT, wraplength=280
        ).pack(pady=(0, 5), fill=tk.X)

        equip_tree_frame = ttk.Frame(self.side_panel_equipment)
        equip_tree_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.equip_tree = ttk.Treeview(equip_tree_frame, show="tree", height=24, selectmode="browse")
        equip_scroll = ttk.Scrollbar(equip_tree_frame, orient=tk.VERTICAL, command=self.equip_tree.yview)
        self.equip_tree.configure(yscrollcommand=equip_scroll.set)
        self.equip_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        equip_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.equip_tree.tag_configure("block", font=("Arial", 9, "bold"))
        self.equip_tree.tag_configure("mppt", font=("Arial", 9, "italic"))
        self.equip_tree.tag_configure("string", font=("Arial", 9))
        self.equip_tree.tag_configure("over", foreground="#C62828")

        # Drag and drop dans l'arborescence Matériel
        self.equip_tree.bind("<ButtonPress-1>", self._on_equip_tree_press)
        self.equip_tree.bind("<ButtonRelease-1>", self._on_equip_tree_release)
        self.equip_tree.bind("<<TreeviewSelect>>", lambda e: self.draw_grid())

        ttk.Button(
            self.side_panel_equipment, text='🔄 Refresh', command=self._refresh_equipment_tree
        ).pack(fill=tk.X, pady=(5, 0))

        # ----------------------------------------------------
        # Panneau latéral Ombre Pylône
        # ----------------------------------------------------
        self._build_side_panel_shadow()

        # ----------------------------------------------------
        # Panneau latéral Fiche Matériel
        # ----------------------------------------------------
        self._build_side_panel_material()

        # ----------------------------------------------------
        # Panneau latéral Schéma Unifilaire
        # ----------------------------------------------------
        self._build_side_panel_diagram()

        # ----------------------------------------------------
        # Panneau latéral Notes
        # ----------------------------------------------------
        self._build_side_panel_notes()

        # Bindings Canvas
        self.canvas.bind("<ButtonPress-1>", self.on_left_press)
        self.canvas.bind("<B1-Motion>", self.on_left_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_left_release)

        self.canvas.bind("<ButtonPress-3>", self.on_right_press)
        self.canvas.bind("<B3-Motion>", self.on_right_drag)
        self.canvas.bind("<ButtonRelease-3>", lambda e: setattr(self, "last_drag_cell", None))

        if sys.platform.startswith("linux"):
            self.canvas.bind("<Button-4>", lambda e: self._zoom_at_pointer(e, 5))
            self.canvas.bind("<Button-5>", lambda e: self._zoom_at_pointer(e, -5))
        else:
            self.canvas.bind("<MouseWheel>", lambda e: self._zoom_at_pointer(e, 5 if e.delta > 0 else -5))

        self.canvas.bind("<Motion>", self._on_canvas_motion)

        # Compteurs en bas à droite
        self.stats_frame = tk.Frame(
            self.canvas_frame,
            bg="#2C3E50",
            bd=1,
            relief="solid",
            padx=10,
            pady=5
        )
        self.lbl_stats = tk.Label(
            self.stats_frame,
            text='Panels: 0  |  Strings: 0',
            font=("Arial", 9, "bold"),
            bg="#2C3E50",
            fg="#FFFFFF"
        )
        self.lbl_stats.pack()
        self.stats_frame.place(relx=1.0, rely=1.0, anchor="se", x=-15, y=-15)

        # ----------------------------------------------------
        # Boîte des Paramètres de Zone (bas gauche, ouvrable/fermable)
        # ----------------------------------------------------
        self.zone_params_visible = False

        self.zone_params_frame = tk.Frame(
            self.canvas_frame,
            bg="#2C3E50",
            bd=1,
            relief="solid",
            padx=10,
            pady=8
        )

        header_row = tk.Frame(self.zone_params_frame, bg="#2C3E50")
        header_row.pack(fill=tk.X)
        tk.Label(
            header_row, text='⚙️ Zone settings',
            font=("Arial", 9, "bold"), bg="#2C3E50", fg="#FFFFFF"
        ).pack(side=tk.LEFT)
        tk.Button(
            header_row, text="✕", command=self._toggle_zone_params_panel,
            bg="#2C3E50", fg="#FFFFFF", bd=0, activebackground="#37474F",
            font=("Arial", 9, "bold"), padx=4
        ).pack(side=tk.RIGHT)

        body = tk.Frame(self.zone_params_frame, bg="#2C3E50")
        body.pack(fill=tk.X, pady=(6, 0))

        def _mk_label(parent, text, row, col):
            tk.Label(parent, text=text, bg="#2C3E50", fg="#FFFFFF", font=("Arial", 9)).grid(
                row=row, column=col, sticky="w", padx=(0, 4), pady=2
            )

        _mk_label(body, "X:", 0, 0)
        self.entry_zone_x = ttk.Entry(body, width=8)
        self.entry_zone_x.grid(row=0, column=1, padx=(0, 10), pady=2)

        _mk_label(body, "Y:", 0, 2)
        self.entry_zone_y = ttk.Entry(body, width=8)
        self.entry_zone_y.grid(row=0, column=3, pady=2)

        _mk_label(body, "L:", 1, 0)
        self.entry_zone_w = ttk.Entry(body, width=8)
        self.entry_zone_w.grid(row=1, column=1, padx=(0, 10), pady=2)

        _mk_label(body, "H:", 1, 2)
        self.entry_zone_h = ttk.Entry(body, width=8)
        self.entry_zone_h.grid(row=1, column=3, pady=2)

        _mk_label(body, 'Horizontal alignment:', 2, 0)
        self.combo_align_x = ttk.Combobox(body, values=["Left", "Center", "Right"], width=6, state="readonly")
        self.combo_align_x.set("Center")
        self.combo_align_x.grid(row=2, column=1, padx=(0, 10), pady=2)

        _mk_label(body, 'Vertical alignment:', 2, 2)
        self.combo_align_y = ttk.Combobox(body, values=["Top", "Center", "Bottom"], width=6, state="readonly")
        self.combo_align_y.set("Center")
        self.combo_align_y.grid(row=2, column=3, pady=2)

        _mk_label(body, 'Angle (°):', 3, 0)
        self.entry_zone_angle = ttk.Entry(body, width=8)
        self.entry_zone_angle.insert(0, "0")
        self.entry_zone_angle.grid(row=3, column=1, padx=(0, 10), pady=2)

        _mk_label(body, 'Angle (°):', 3, 0)
        self.entry_zone_angle = ttk.Entry(body, width=8)
        self.entry_zone_angle.insert(0, "0")
        self.entry_zone_angle.grid(row=3, column=1, padx=(0, 10), pady=2)

        ttk.Button(
            self.zone_params_frame, text='Apply changes', command=self.update_active_zone_params
        ).pack(fill=tk.X, pady=(8, 0))

        # Le panneau démarre fermé ; place() est appliqué par _toggle_zone_params_panel

    def _toggle_zone_params_panel(self):
        self.zone_params_visible = not self.zone_params_visible
        if self.zone_params_visible:
            self._update_zone_entries_from_active()
            self.zone_params_frame.place(relx=0.0, rely=1.0, anchor="sw", x=15, y=-15)
        else:
            self.zone_params_frame.place_forget()

    # ========================================================
    # DRAG & DROP DES PANNEAUX DANS L'ARBORESCENCE
    # ========================================================

    def _on_string_tree_start_drag(self, event):
        self.drag_start_index = self.string_tree.identify_row(event.y)

    def _on_string_tree_drop(self, event):
        source = self.drag_start_index
        self.drag_start_index = None
        if not source or not self.string_tree.exists(source):
            return
        target = self.string_tree.identify_row(event.y)
        if not target or not self.string_tree.exists(target):
            return
        parent = self.string_tree.parent(source)
        if not parent or parent != self.string_tree.parent(target) or source == target:
            return
        source_idx = self.string_tree.index(source)
        target_idx = self.string_tree.index(target)
        string_id = self._string_tree_ids[parent]
        coords = self.strings[string_id]
        coords.insert(target_idx, coords.pop(source_idx))
        self.manual_strings.add(string_id)
        self._update_string_listbox(selected_panel_index=target_idx)
        self.draw_grid()

    # ========================================================
    # GESTION DES ONGLETS DU RUBAN
    # ========================================================

    def _on_ribbon_tab_changed(self, event):
        idx = self._get_active_tab_index()
        if idx == 3:  # Onglet Stringing
            self.side_panel_stringing.pack(side=tk.LEFT, fill=tk.Y, before=self.canvas_frame)
            self._update_string_listbox()
        else:
            self.side_panel_stringing.pack_forget()

        if idx == 4:  # Onglet Matériel
            self.side_panel_equipment.pack(side=tk.LEFT, fill=tk.Y, before=self.canvas_frame)
            self._refresh_equipment_tree()
        else:
            self.side_panel_equipment.pack_forget()

        if idx != 2:  # Onglet Layout & Blocs
            if getattr(self, "layout_mode", "select") == "place_inverter":
                self.layout_mode = "select"
                self.pending_inverter_placement = None
                if hasattr(self, "canvas"):
                    self.canvas.config(cursor="")

        if idx != 1 and self.path_mode in ('draw_polygon', 'select_polygon', 'measure_distance'):
            self.temp_polygon_points = []
            self.path_mode = 'select'
        if idx != 8 and self.path_mode in ('draw_cable_path', 'place_gather_point'):
            self.temp_cable_path_points = []
            self.path_mode = 'select'

        if idx == 5:  # Onglet Ombre Pylône
            self.side_panel_shadow.pack(side=tk.LEFT, fill=tk.Y, before=self.canvas_frame)
            self._read_shadow_params_from_entries(show_errors=False)
            self._recompute_shadow()
            self._refresh_shadow_zone_list()
            self._update_shadow_status_label()
        else:
            self.side_panel_shadow.pack_forget()
            self.shadow_mode = "select"

        if idx == 6:  # Onglet Matériel
            self.side_panel_material.pack(side=tk.RIGHT, fill=tk.Y)
            self._refresh_material_trees()
            # Zone principale : feuille de calcul (Canvas) à la place du
            # canvas habituel, uniquement pour cet onglet.
            self.stats_frame.place_forget()
            self.canvas.pack_forget()
            self.spreadsheet_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
            self._refresh_spreadsheet()
            self._refresh_variable_explorer()
            self.root.after(50, lambda: self.spreadsheet_data_canvas.focus_set())
        else:
            self.side_panel_material.pack_forget()
            if getattr(self, "spreadsheet_frame", None) is not None and self.spreadsheet_frame.winfo_manager():
                self._spreadsheet_commit_edit()
                self.spreadsheet_frame.pack_forget()
                self.canvas.pack(fill=tk.BOTH, expand=True)
                self.stats_frame.place(relx=1.0, rely=1.0, anchor="se", x=-15, y=-15)

        if idx == 7:  # Onglet Schéma Unifilaire
            self.side_panel_diagram.pack(side=tk.RIGHT, fill=tk.Y)
            self._refresh_diagram_list()
        else:
            self.side_panel_diagram.pack_forget()
            self._cancel_diagram_link_mode()

        if idx == 8:  # Onglet Notes
            self.side_panel_notes.pack(side=tk.RIGHT, fill=tk.Y)
            if self.cable_routes_calculated:
                self.compute_all_cable_routes()
            self._refresh_cabling_paths()
            self._refresh_cable_route_table()
        else:
            self.side_panel_notes.pack_forget()

        self.draw_grid()

    # ========================================================
    # LOGIQUE ONGLET TOIT & ÉCHELLE
    # ========================================================

    def load_roof_image(self):
        if not HAS_PIL:
            messagebox.showerror('Error', 'Pillow (PIL) is required to load images.')
            return

        filepath = filedialog.askopenfilename(
            parent=self.root,
            title='Select roof image',
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp"), ('All files', "*.*")]
        )
        if not filepath:
            return

        try:
            with Image.open(filepath) as image:
                new_img = image.copy()
            self.roof_image_path = filepath
            self.roof_pil_img = new_img

            # Si une échelle et des zones existent déjà dans le projet
            if self.px_per_mm > 0 and (self.roof_zones or self.scale_length_mm > 0):
                ans = messagebox.askyesno(
                    'Rescale image to project scale',
                    "A scale and/or zones already exist in this project.\n\n"
                    "Draw a reference segment on the new image to resize it "
                    "automatically to the project scale?",
                    parent=self.root
                )
                if ans:
                    self._activate_scale_mode()
                    messagebox.showinfo(
                        'Image calibration',
                        'Draw a known-length segment on the new image to calibrate it.',
                        parent=self.root
                    )
                else:
                    self.draw_grid()
            else:
                self.draw_grid()
        except Exception as e:
            messagebox.showerror('Error', f"Unable to open image:\n{e}")

    def _activate_scale_mode(self):
        if not self.roof_pil_img:
            messagebox.showwarning('Warning', 'Load a roof image first.')
            return
        self.roof_mode = "scale"
        self.path_mode = 'select'
        self.temp_draw_start = None

    def _activate_measure_mode(self):
        if not self.roof_pil_img:
            messagebox.showwarning('Warning', 'Load a roof image first.')
            return
        if self.px_per_mm <= 0:
            messagebox.showwarning('Warning', 'Set the scale before measuring.')
            return
        self.roof_mode = "measure"
        self.path_mode = 'select'
        self.temp_draw_start = None

    def clear_measures(self):
        self.measures.clear()
        self.measure_p1 = None
        self.measure_p2 = None
        self.draw_grid()

    def _activate_zone_mode(self):
        if not self.roof_pil_img:
            messagebox.showwarning('Warning', 'Load a roof image first.')
            return
        if self.px_per_mm <= 0:
            messagebox.showwarning('Warning', 'Set the scale before creating zones.')
            return
        self.roof_mode = "zone"
        self.path_mode = 'select'
        self.temp_draw_start = None

    def _activate_zone_select_mode(self):
        self.roof_mode = 'select'
        self.path_mode = 'select'
        self.draw_grid()

    def _update_zone_combo(self):
        values = [f"Zone {z['id']}" for z in self.roof_zones]
        self.combo_zones["values"] = values
        if self.active_zone_idx is not None and 0 <= self.active_zone_idx < len(self.roof_zones):
            self.combo_zones.set(f"Zone {self.roof_zones[self.active_zone_idx]['id']}")
        else:
            self.combo_zones.set("")

    def _on_zone_combo_selected(self, event):
        idx = self.combo_zones.current()
        if 0 <= idx < len(self.roof_zones):
            self.active_zone_idx = idx
            self.selected_zone_indices = {idx}
            self._update_zone_entries_from_active()
            self.draw_grid()

    def delete_active_zone(self):
        to_delete = sorted(list(self.selected_zone_indices), reverse=True)
        if not to_delete and self.active_zone_idx is not None:
            to_delete = [self.active_zone_idx]

        if to_delete:
            for idx in to_delete:
                if 0 <= idx < len(self.roof_zones):
                    self.roof_zones.pop(idx)
            self.selected_zone_indices.clear()
            if self.roof_zones:
                self.active_zone_idx = min(to_delete[-1], len(self.roof_zones) - 1)
                self.selected_zone_indices = {self.active_zone_idx}
            else:
                self.active_zone_idx = None

            self._update_zone_combo()
            self._update_zone_entries_from_active()
            self._recalculate_zone_grids()
            self.draw_grid()

    def _update_zone_entries_from_active(self):
        if self.active_zone_idx is None or self.active_zone_idx >= len(self.roof_zones):
            return

        z = self.roof_zones[self.active_zone_idx]
        x1, y1 = min(z["x1"], z["x2"]), min(z["y1"], z["y2"])
        x2, y2 = max(z["x1"], z["x2"]), max(z["y1"], z["y2"])

        if self.px_per_mm > 0:
            x_val = round(x1 / self.px_per_mm, 1)
            y_val = round(y1 / self.px_per_mm, 1)
            w_val = round((x2 - x1) / self.px_per_mm, 1)
            h_val = round((y2 - y1) / self.px_per_mm, 1)
        else:
            x_val, y_val, w_val, h_val = round(x1, 1), round(y1, 1), round(x2 - x1, 1), round(y2 - y1, 1)

        self.entry_zone_x.delete(0, tk.END)
        self.entry_zone_x.insert(0, str(x_val))
        self.entry_zone_y.delete(0, tk.END)
        self.entry_zone_y.insert(0, str(y_val))
        self.entry_zone_w.delete(0, tk.END)
        self.entry_zone_w.insert(0, str(w_val))
        self.entry_zone_h.delete(0, tk.END)
        self.entry_zone_h.insert(0, str(h_val))
        self.combo_align_x.set({"Gau.": "Left", "Centre": "Center", "Dro.": "Right"}.get(z.get("align_x"), "Center"))
        self.combo_align_y.set({"Haut": "Top", "Centre": "Center", "Bas": "Bottom"}.get(z.get("align_y"), "Center"))
        self.entry_zone_angle.delete(0, tk.END)
        self.entry_zone_angle.insert(0, str(z.get("angle_deg", 0.0)))
        self._update_zone_combo()

    def update_active_zone_params(self):
        if self.active_zone_idx is None or self.active_zone_idx >= len(self.roof_zones):
            return

        try:
            x_val = float(self.entry_zone_x.get())
            y_val = float(self.entry_zone_y.get())
            w_val = float(self.entry_zone_w.get())
            h_val = float(self.entry_zone_h.get())
            angle_val = float(self.entry_zone_angle.get())
            align_x = {"Left": "Gau.", "Center": "Centre", "Right": "Dro."}[self.combo_align_x.get()]
            align_y = {"Top": "Haut", "Center": "Centre", "Bottom": "Bas"}[self.combo_align_y.get()]

            zone = self.roof_zones[self.active_zone_idx]

            if self.px_per_mm > 0:
                x1 = x_val * self.px_per_mm
                y1 = y_val * self.px_per_mm
                x2 = x1 + w_val * self.px_per_mm
                y2 = y1 + h_val * self.px_per_mm
            else:
                x1, y1 = x_val, y_val
                x2, y2 = x1 + w_val, y1 + h_val

            zone["x1"], zone["y1"] = x1, y1
            zone["x2"], zone["y2"] = x2, y2
            zone["align_x"] = align_x
            zone["align_y"] = align_y
            zone["angle_deg"] = angle_val
            zone["w_mm"] = w_val
            zone["h_mm"] = h_val

            self._recalculate_zone_grids()
            self.draw_grid()
        except ValueError:
            messagebox.showerror('Error', 'Invalid zone values.')

    def _recalculate_zone_grids(self):
        """Calcule le nombre de lignes/colonnes et l'offset exact au mm près pour chaque zone."""
        if self.px_per_mm <= 0:
            return

        for z_idx, zone in enumerate(self.roof_zones):
            x1, y1 = min(zone["x1"], zone["x2"]), min(zone["y1"], zone["y2"])
            x2, y2 = max(zone["x1"], zone["x2"]), max(zone["y1"], zone["y2"])

            width_px = x2 - x1
            height_px = y2 - y1

            width_mm = width_px / self.px_per_mm
            height_mm = height_px / self.px_per_mm

            avail_w_mm = width_mm
            avail_h_mm = height_mm

            if avail_w_mm < self.panel_width_mm or avail_h_mm < self.panel_height_mm:
                zone["rows"] = 0
                zone["cols"] = 0
                zone["row_base"] = z_idx * 100
                zone["offset_x_mm"] = 0.0
                zone["offset_y_mm"] = 0.0
                continue

            cols = int(avail_w_mm // self.panel_width_mm)
            rows = int(avail_h_mm // self.panel_height_mm)

            used_w_mm = cols * self.panel_width_mm
            used_h_mm = rows * self.panel_height_mm

            rem_w_mm = avail_w_mm - used_w_mm
            rem_h_mm = avail_h_mm - used_h_mm

            align_x = zone.get("align_x", "Centre")
            align_y = zone.get("align_y", "Centre")

            if align_x == "Gau.":
                offset_x_mm = 0.0
            elif align_x == "Dro.":
                offset_x_mm = rem_w_mm
            else:  # Centre
                offset_x_mm = rem_w_mm / 2.0

            if align_y == "Haut":
                offset_y_mm = 0.0
            elif align_y == "Bas":
                offset_y_mm = rem_h_mm
            else:  # Centre
                offset_y_mm = rem_h_mm / 2.0

            zone["rows"] = rows
            zone["cols"] = cols
            zone["row_base"] = z_idx * 100
            zone["offset_x_mm"] = offset_x_mm
            zone["offset_y_mm"] = offset_y_mm

    # ========================================================
    # ROTATION DES PANNEAUX (chaque panneau tourne indépendamment
    # autour de son propre centre — pas autour du centre de la zone.
    # La position de la cellule dans la grille ne bouge pas, seul
    # son carré visuel pivote sur place.)
    # ========================================================

    @staticmethod
    def _zone_panel_center(x1, y1, x2, y2):
        return ((x1 + x2) / 2.0, (y1 + y2) / 2.0)

    def _zone_rotate_point(self, zone, cx, cy, x, y):
        """Tourne un point (x, y) autour du centre donné (cx, cy), selon
        zone['angle_deg']. (cx, cy) est le centre PROPRE du panneau concerné,
        pas celui de la zone — c'est ce qui rend la rotation indépendante
        panneau par panneau."""
        angle_deg = zone.get("angle_deg", 0.0)
        if not angle_deg:
            return (x, y)
        angle = math.radians(angle_deg)
        dx, dy = x - cx, y - cy
        cos_a, sin_a = math.cos(angle), math.sin(angle)
        return (cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a)

    def _zone_rotate_rect(self, zone, x1, y1, x2, y2):
        """4 coins tournés (TL, TR, BR, BL) d'un panneau autour de SON PROPRE
        centre (donc rotation indépendante par panneau, pas du bloc entier)."""
        cx, cy = self._zone_panel_center(x1, y1, x2, y2)
        corners = [(x1, y1), (x2, y1), (x2, y2), (x1, y2)]
        return [self._zone_rotate_point(zone, cx, cy, px, py) for px, py in corners]

    def _update_zones_from_scale(self):
        """Recalcule les grilles de zones et rafraîchit l'affichage suite au calibrage."""
        self._recalculate_zone_grids()
        self._update_zone_entries_from_active()
        self.draw_grid()

    def generate_panels_from_zones(self):
        if not self.roof_zones or self.px_per_mm <= 0:
            messagebox.showwarning('Warning', 'Define at least one zone and a valid scale.')
            return

        self._recalculate_zone_grids()
        old_panels = dict(self.panels)
        self.panels.clear()
        consecutive = self.var_continuous_numbers.get()
        panel_id = 1 if consecutive else max(old_panels.values(), default=0) + 1

        for zone in self.roof_zones:
            rows = zone.get("rows", 0)
            cols = zone.get("cols", 0)
            row_base = zone.get("row_base", 0)

            for r in range(rows):
                for c in range(cols):
                    coord = (row_base + r, c)
                    if not consecutive and coord in old_panels:
                        self.panels[coord] = old_panels[coord]
                    else:
                        self.panels[coord] = panel_id
                        panel_id += 1

        self.panel_orientations = {coord: orientation for coord, orientation in self.panel_orientations.items()
                                   if coord in self.panels}
        self.selected_panel_coords.intersection_update(self.panels)
        self.draw_grid()

    # ========================================================
    # INTERACTIONS SOURIS ET EVENEMENTS CANVAS
    # ========================================================
