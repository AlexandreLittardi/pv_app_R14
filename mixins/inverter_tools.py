"""Placement physique des onduleurs sur le plan (Onglet Layout & Blocs).

Un onduleur placé est toujours rattaché à un Bloc existant (self.blocks) :
la position (coordonnées image d'origine) est stockée dans
self.inverter_positions[block_name]. Le modèle (marque/puissance/MPPT...) est
repris depuis la Fiche Matériel du projet (onglet "Matériel" ▸ Onduleurs) au
moment du placement — une copie ("snapshot") de la ligne est conservée pour
que l'affichage reste correct même si la fiche matériel est modifiée plus tard.
"""

import re
import tkinter as tk
from tkinter import messagebox, ttk

from mixins.material_tools import MATERIAL_CATEGORY_DEFS, MATERIAL_COLUMNS_EN


def natural_sort_key(s):
    """Clé de tri naturel pour ordonner correctement 'INV2' avant 'INV10' et 'String 2' avant 'String 10'."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]


class InverterToolsMixin:
    # ========================================================
    # DIALOGUE DE SÉLECTION DE L'ONDULEUR
    # ========================================================

    def open_inverter_selection_dialog(self):
        if not self.active_block_name or self.active_block_name not in self.blocks:
            messagebox.showwarning(
                'Warning',
                "First select (or create) an active block in Layout and blocks. "
                "Each placed inverter belongs to one block."
            )
            return

        rows = self.material_categories.get("inverters", {}).get("rows", [])
        if not rows:
            messagebox.showwarning(
                'Warning',
                "No inverter is listed in the project equipment sheet "
                "(Equipment > Inverters). Add one first."
            )
            return

        _, columns = MATERIAL_CATEGORY_DEFS["inverters"]

        dialog = tk.Toplevel(self.root)
        dialog.title(f"Choose inverter for block “{self.active_block_name}”")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(
            dialog,
            text=f"Select the inverter model for block “{self.active_block_name}”,\n"
                 "then click Place on image and choose its position.",
            justify=tk.LEFT, padding=8
        ).pack(fill=tk.X)

        tree_frame = ttk.Frame(dialog, padding=(8, 0))
        tree_frame.pack(fill=tk.BOTH, expand=True)

        tree = ttk.Treeview(tree_frame, columns=columns, show="headings", height=10)
        for col in columns:
            tree.heading(col, text=MATERIAL_COLUMNS_EN.get(col, col))
            tree.column(col, width=110, anchor="center")
        tree_scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=tree_scroll.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        for idx, row in enumerate(rows):
            values = [row.get(col, "") for col in columns]
            tree.insert("", tk.END, iid=str(idx), values=values)

        # Pré-sélectionne l'onduleur déjà placé pour ce bloc, le cas échéant
        current = self.inverter_positions.get(self.active_block_name)
        if current and current.get("material_row") in rows:
            try:
                tree.selection_set(str(rows.index(current["material_row"])))
            except ValueError:
                pass

        btn_row = ttk.Frame(dialog, padding=8)
        btn_row.pack(fill=tk.X)

        def on_select():
            sel = tree.selection()
            if not sel:
                messagebox.showinfo("Info", 'Select an inverter from the list.')
                return
            idx = int(sel[0])
            row = dict(rows[idx])
            dialog.destroy()
            self._start_inverter_placement(row)

        def on_cancel():
            dialog.destroy()

        ttk.Button(btn_row, text='📍 Place on image', command=on_select).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_row, text='Cancel', command=on_cancel).pack(side=tk.LEFT, padx=5)

        self._center_window(dialog, width=min(900, 140 + 110 * len(columns)), height=420)
        dialog.wait_window()

    # ========================================================
    # PLACEMENT SUR LE CANVAS
    # ========================================================

    def _start_inverter_placement(self, material_row):
        if not self.roof_pil_img:
            messagebox.showwarning('Warning', 'Load a roof image first.')
            return

        self.pending_inverter_placement = {
            "block_name": self.active_block_name,
            "material_row": material_row,
        }
        self.layout_mode = "place_inverter"
        self.canvas.config(cursor="crosshair")

    def _place_pending_inverter_at(self, img_x, img_y):
        """Appelé depuis on_left_press (canvas_grid.py) lorsque layout_mode == 'place_inverter'."""
        pending = self.pending_inverter_placement
        if not pending:
            self.layout_mode = "select"
            return

        self.inverter_positions[pending["block_name"]] = {
            "x": img_x,
            "y": img_y,
            "material_row": pending["material_row"],
        }
        self.pending_inverter_placement = None
        self.layout_mode = "select"
        self.canvas.config(cursor="")
        self._refresh_equipment_tree()
        self.draw_grid()

    def remove_inverter_placement(self):
        if not self.active_block_name:
            messagebox.showinfo("Info", 'Select an active block.')
            return
        if self.active_block_name not in self.inverter_positions:
            messagebox.showinfo("Info", 'This block has no inverter placed on the image.')
            return
        if messagebox.askyesno(
            'Confirm',
            f"Remove inverter placement for block “{self.active_block_name}”?"
        ):
            self.inverter_positions.pop(self.active_block_name, None)
            self._refresh_equipment_tree()
            self.draw_grid()

    # ========================================================
    # DISTRIBUTION SÉQUENTIELLE DES STRINGS DANS LES ONDULEURS
    # ========================================================

    def assign_strings_to_inverters(self):
        """
        Affecte séquentiellement les strings aux MPPT des onduleurs.
        self.strings reste sous la forme :
            {"String 1": [coord1, coord2, ...], ...}

        Les affectations électriques sont stockées séparément dans
        self.mppt_assignments.
        """
        if not hasattr(self, "strings") or not self.strings:
            return

        if not hasattr(self, "inverter_positions") or not self.inverter_positions:
            return

        if not hasattr(self, "mppt_assignments"):
            self.mppt_assignments = {}

        # Nettoyage des anciennes affectations
        self.mppt_assignments.clear()

        sorted_string_names = sorted(
            self.strings.keys(),
            key=natural_sort_key
        )

        sorted_inverter_names = sorted(
            self.inverter_positions.keys(),
            key=natural_sort_key
        )

        string_idx = 0
        total_strings = len(sorted_string_names)

        for inv_name in sorted_inverter_names:
            if string_idx >= total_strings:
                break

            inv_data = self.inverter_positions[inv_name]

            mppt_inputs = inv_data.get(
                "mppt_inputs",
                [1] * 9 + [2]
            )

            for mppt_idx, capacity in enumerate(mppt_inputs, start=1):
                if string_idx >= total_strings:
                    break

                for _ in range(capacity):
                    if string_idx >= total_strings:
                        break

                    string_name = sorted_string_names[string_idx]

                    self.mppt_assignments[string_name] = {
                        "inverter": inv_name,
                        "mppt": mppt_idx,
                    }

                    string_idx += 1

    # ========================================================
    # AFFICHAGE CANVAS
    # ========================================================

    def _draw_inverters(self, zoom):
        """Dessine un marqueur pour chaque onduleur placé. Appelé depuis draw_grid()
        (canvas_grid.py) pour les onglets Layout & Blocs, Répartition MPPT et Chemins."""
        if not hasattr(self, "canvas") or not self.inverter_positions:
            return

        # Affichage des onduleurs dans l'ordre croissant
        sorted_blocks = sorted(self.inverter_positions.keys(), key=natural_sort_key)

        for block_name in sorted_blocks:
            pos = self.inverter_positions[block_name]
            x, y = pos["x"] * zoom, pos["y"] * zoom
            color = self.blocks.get(block_name, {}).get("color", "#6A1B9A")

            self.canvas.create_rectangle(x - 9, y - 9, x + 9, y + 9, fill=color, outline="white", width=2)
            self.canvas.create_text(x, y, text="⏚", fill="white", font=("Arial", 9, "bold"))

            row = pos.get("material_row", {}) or {}
            model_label = " ".join(v for v in [row.get("Marque", ""), row.get("Modèle", "")] if v).strip()
            label = f"🔌 {block_name}" + (f" — {model_label}" if model_label else "")
            self._draw_text_with_bg(x + 14, y - 12, label, fill=color, anchor="w")