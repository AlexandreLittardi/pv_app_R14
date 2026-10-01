"""Gestion des strings (creation, edition, generation automatique)."""

import csv
import json
import math
import os
import re
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from project_validation import string_label

try:
    import io
    from PIL import Image, ImageDraw, ImageTk, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


def natural_sort_key(s):
    """Clé de tri naturel pour ordonner correctement 'INV2' avant 'INV10' et 'String 2' avant 'String 10'."""
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]


class StringingToolsMixin:
    def add_panel_to_string(self, cell):
        if cell is None:
            return

        for s_id, coords in self.strings.items():
            if cell in coords:
                if s_id != self.active_string_id:
                    messagebox.showwarning('Warning', f"Panel already assigned to {s_id}")
                return

        if self.active_string_id not in self.strings:
            self.strings[self.active_string_id] = []

        self.strings[self.active_string_id].append(cell)
        self.manual_strings.add(self.active_string_id)
        self._update_string_listbox()
        self.draw_grid()

    def remove_panel_from_strings(self, cell):
        if cell is None:
            return

        for s_id, coords in self.strings.items():
            if cell in coords:
                coords.remove(cell)
                self.manual_strings.add(s_id)
                self._update_string_listbox()
                self.draw_grid()
                break

    def _clean_deleted_panels_from_strings(self):
        for s_id in list(self.strings.keys()):
            previous=self.strings[s_id]
            self.strings[s_id] = [c for c in previous if c in self.panels]
            if self.strings[s_id]!=previous or not self.strings[s_id]:
                self.string_mppt_assignment.pop(s_id,None)
            if not self.strings[s_id]:getattr(self,'cable_string_params',{}).pop(s_id,None)
        for sid in list(self.string_mppt_assignment):
            if sid not in self.strings:self.string_mppt_assignment.pop(sid,None)

    def _update_string_listbox(self, selected_panel_index=None):
        tree = self.string_tree
        if hasattr(self, "combo_mppt_current_string"):
            self.combo_mppt_current_string.set(self.active_string_id)
        self._string_tree_ids = {}
        self._updating_string_tree = True
        try:
            children = tree.get_children()
            if children:
                tree.delete(*children)
            for string_idx, string_id in enumerate(self._get_sorted_string_keys()):
                root = f"str_{string_idx}"
                self._string_tree_ids[root] = string_id
                coords = self.strings[string_id]
                tree.insert("", tk.END, iid=root, text=f"{string_label(string_id)} ({len(coords)} panels)",
                            open=True, tags=("string",))
                for panel_idx, coord in enumerate(coords):
                    number = self.panels.get(coord, "?")
                    tree.insert(root, tk.END, iid=f"panel_{string_idx}_{panel_idx}",
                                text=f"{panel_idx+1}. Panel #{number} (r:{coord[0]}, c:{coord[1]})",
                                tags=("panel",))
                if string_id == self.active_string_id:
                    item = f"panel_{string_idx}_{selected_panel_index}" if selected_panel_index is not None else root
                    if tree.exists(item):
                        tree.selection_set(item)
                        tree.see(item)
        finally:
            self._updating_string_tree = False

    def _on_string_tree_selected(self, event=None):
        if getattr(self, "_updating_string_tree", False):
            return
        selected = self.string_tree.selection()
        if not selected:
            return
        root = self.string_tree.parent(selected[0]) or selected[0]
        string_id = self._string_tree_ids.get(root)
        if string_id and string_id != self.active_string_id:
            self.active_string_id = string_id
            self.combo_strings.set(string_id)
            self.draw_grid()

    def _selected_string_panel_index(self):
        selected = self.string_tree.selection()
        if not selected or not self.string_tree.parent(selected[0]):
            return None
        root = self.string_tree.parent(selected[0])
        if self._string_tree_ids.get(root) != self.active_string_id:
            return None
        return self.string_tree.index(selected[0])

    def _move_panel_in_string(self, direction):
        idx = self._selected_string_panel_index()
        if idx is None:
            return
        new_idx = idx + direction
        coords = self.strings.get(self.active_string_id, [])

        if 0 <= new_idx < len(coords):
            coords[idx], coords[new_idx] = coords[new_idx], coords[idx]
            self.manual_strings.add(self.active_string_id)
            self._update_string_listbox(selected_panel_index=new_idx)
            self.draw_grid()

    def _add_panel_manual_dialog(self):
        p_num = simpledialog.askinteger('Add panel', 'Number of panel to add:', parent=self.root)
        if not p_num:
            return
        target_cell = None
        for cell, num in self.panels.items():
            if num == p_num:
                target_cell = cell
                break

        if target_cell:
            self.add_panel_to_string(target_cell)
        else:
            messagebox.showerror('Error', f"Panel #{p_num} does not exist in the layout.")

    def _remove_panel_from_string_list(self):
        idx = self._selected_string_panel_index()
        if idx is None:
            return
        coords = self.strings.get(self.active_string_id, [])
        if 0 <= idx < len(coords):
            coords.pop(idx)
            self.manual_strings.add(self.active_string_id)
            self._update_string_listbox()
            self.draw_grid()

    def add_new_string(self):
        default_id = f"String {len(self.strings) + 1}"
        new_id = simpledialog.askstring('New string', 'String name:', initialvalue=default_id, parent=self.root)
        if not new_id or not new_id.strip():
            return
        new_id = new_id.strip()
        if new_id in self.strings:
            messagebox.showwarning('Warning', 'This name already exists.')
            return

        self.strings[new_id] = []
        self.manual_strings.add(new_id)
        self._update_combo_strings()
        self.combo_strings.set(new_id)
        self.active_string_id = new_id
        self._update_string_listbox()

    def delete_active_string(self):
        if not self.active_string_id or self.active_string_id not in self.strings:
            return
        if len(self.strings) <= 1:
            self.strings[self.active_string_id] = []
        else:
            if messagebox.askyesno('Confirm', f"Delete '{self.active_string_id}' ?"):
                del self.strings[self.active_string_id]
                self.manual_strings.discard(self.active_string_id)
                self.string_mppt_assignment.pop(self.active_string_id,None)
                self.cable_string_params.pop(self.active_string_id,None)
                sorted_keys = self._get_sorted_string_keys()
                self.active_string_id = sorted_keys[0] if sorted_keys else "String 1"

        self._update_combo_strings()
        self.combo_strings.set(self.active_string_id)
        self._update_string_listbox()
        self.draw_grid()

    def clear_all_strings(self):
        self.strings = {"String 1": []}
        self.manual_strings.clear()
        self.string_mppt_assignment.clear()
        self.cable_string_params.clear()
        self.active_string_id = "String 1"
        self._update_combo_strings()
        self.combo_strings.set(self.active_string_id)
        self._update_string_listbox()
        self.draw_grid()

    def _get_sorted_string_keys(self):
        return sorted(list(self.strings.keys()), key=natural_sort_key)

    def _update_combo_strings(self):
        sorted_keys = self._get_sorted_string_keys()
        if not sorted_keys:
            self.strings = {"String 1": []}
            sorted_keys = ["String 1"]
        self.combo_strings["values"] = sorted_keys
        if hasattr(self, "combo_mppt_current_string"):
            self.combo_mppt_current_string["values"] = sorted_keys
            if self.combo_mppt_current_string.get() not in sorted_keys:
                self.combo_mppt_current_string.set(sorted_keys[0])

    def _on_active_string_changed(self, event):
        self.active_string_id = self.combo_strings.get()
        if hasattr(self, "combo_mppt_current_string"):
            self.combo_mppt_current_string.set(self.active_string_id)
        self._update_string_listbox()
        self.draw_grid()

    # ========================================================
    # GENERATION AUTOMATIQUE
    # ========================================================

    def _get_panel_physical_center(self, coord):
        r, c = coord
        if self.roof_zones and self.px_per_mm > 0:
            self._recalculate_zone_grids()
            for z_idx, zone in enumerate(self.roof_zones):
                rows = zone.get("rows", 0)
                cols = zone.get("cols", 0)
                row_base = zone.get("row_base", z_idx * 100)
                if row_base <= r < row_base + rows:
                    local_r = r - row_base
                    x1 = min(zone["x1"], zone["x2"])
                    y1 = min(zone["y1"], zone["y2"])
                    off_x_px = zone.get("offset_x_mm", 0.0) * self.px_per_mm
                    off_y_px = zone.get("offset_y_mm", 0.0) * self.px_per_mm
                    pw_px = self.panel_width_mm * self.px_per_mm
                    ph_px = self.panel_height_mm * self.px_per_mm
                    cx = x1 + off_x_px + (c + 0.5) * pw_px
                    cy = y1 + off_y_px + (local_r + 0.5) * ph_px
                    return (cx, cy)
        return (c * self.cell_size_px, r * int(self.cell_size_px * (self.panel_height_mm / self.panel_width_mm)))

    def generate_auto_strings(self):
        try:
            max_per_string = int(self.string_max_var.get())
            if max_per_string <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror('Error', 'Invalid maximum size.')
            return

        try:
            min_per_string = int(self.string_min_var.get())
            if min_per_string <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror('Error', 'Invalid minimum size.')
            return

        if min_per_string > max_per_string:
            messagebox.showerror('Error', 'Minimum cannot exceed maximum.')
            return

        if not self.panels:
            return

        preserved_strings = {k: v for k, v in self.strings.items() if k in self.manual_strings}
        assigned_cells = set(c for coords in preserved_strings.values() for c in coords)
        available_panels = set(p for p in self.panels.keys() if p not in assigned_cells)

        if not available_panels:
            return

        orientation = self.string_direction_var.get()

        block_groups = {}
        for coord in available_panels:
            b_name = self.panel_blocks.get(coord, "__NO_BLOCK__")
            zone_idx, zone = self._find_zone_for_panel(coord)
            group_key = b_name
            if group_key not in block_groups:
                block_groups[group_key] = {"zone": zone, "items": []}
            cx, cy = self._get_panel_physical_center(coord)
            block_groups[group_key]["items"].append((coord, cx, cy))

        if self.px_per_mm > 0:
            pw_px = max(1.0, self.panel_width_mm * self.px_per_mm)
            ph_px = max(1.0, self.panel_height_mm * self.px_per_mm)
        else:
            pw_px = max(1.0, float(self.cell_size_px))
            ph_px = max(1.0, float(self.cell_size_px) * (self.panel_height_mm / self.panel_width_mm))

        default_orientation = self.string_direction_var.get()

        auto_strings = {}
        current_idx = 1
        undersized_found = False

        def _get_next_auto_name():
            nonlocal current_idx
            name = f"String {current_idx}"
            while name in preserved_strings or name in auto_strings:
                current_idx += 1
                name = f"String {current_idx}"
            return name

        def _group_sort_key(kv):
            return natural_sort_key(kv[0])

        for group_key, group_data in sorted(block_groups.items(), key=_group_sort_key):
            zone = group_data["zone"]
            group = group_data["items"]
            orientation = default_orientation
            if orientation == "Auto (layout)":
                if zone:
                    orientation = "Vertical" if zone.get("rows", 0) >= zone.get("cols", 0) else "Horizontal"
                else:
                    unique_rows = len({item[0][0] for item in group})
                    unique_cols = len({item[0][1] for item in group})
                    orientation = "Vertical" if unique_rows >= unique_cols else "Horizontal"
            is_horizontal = (orientation == "Horizontal")

            tol = (ph_px * 0.5) if is_horizontal else (pw_px * 0.5)
            axis_primary = 2 if is_horizontal else 1
            axis_secondary = 1 if is_horizontal else 2

            sorted_items = sorted(group, key=lambda it: it[axis_primary])

            stripes = []
            curr_group = []
            curr_avg = None

            for item in sorted_items:
                val = item[axis_primary]
                if curr_avg is None:
                    curr_avg = val
                    curr_group.append(item)
                elif abs(val - curr_avg) <= tol:
                    curr_group.append(item)
                    curr_avg = sum(it[axis_primary] for it in curr_group) / len(curr_group)
                else:
                    stripes.append(curr_group)
                    curr_group = [item]
                    curr_avg = val
            if curr_group:
                stripes.append(curr_group)

            ordered_panels = []
            for idx, stripe in enumerate(stripes):
                reverse_order = (idx % 2 != 0)
                stripe_sorted = sorted(stripe, key=lambda it: it[axis_secondary], reverse=reverse_order)
                ordered_panels.extend(stripe_sorted)

            for chunk in self._split_balanced(ordered_panels, min_per_string, max_per_string):
                current_name = _get_next_auto_name()
                auto_strings[current_name] = [item[0] for item in chunk]
                if len(chunk) < min_per_string:
                    undersized_found = True

        new_strings = preserved_strings
        for k, v in auto_strings.items():
            if len(v) > 0:
                new_strings[k] = v

        if not new_strings:
            new_strings = {"String 1": []}

        self.strings = new_strings

        # --- RE-REPARTITION SEQUENTIELLE DANS LES MPPT/ONDULEURS ---
        if hasattr(self, "assign_strings_to_inverters"):
            self.assign_strings_to_inverters()

        self._update_combo_strings()
        sorted_keys = self._get_sorted_string_keys()
        self.combo_strings.set(sorted_keys[0])
        self.active_string_id = sorted_keys[0]

        self._update_string_listbox()
        if hasattr(self, "_refresh_equipment_tree"):
            self._refresh_equipment_tree()
        self.draw_grid()

        if undersized_found:
            messagebox.showinfo(
                "Information",
                f"Some zones or blocks do not have enough panels to ensure "
                f"{min_per_string} panels per string. Their sizes were maximized "
                f"but remain below the minimum."
            )

    def _split_balanced(self, items, min_per_string, max_per_string):
        n = len(items)
        if n == 0:
            return []

        k = max(1, math.ceil(n / max_per_string))

        while k > 1 and math.ceil(n / (k - 1)) <= max_per_string and (n // k) < min_per_string:
            k -= 1

        base = n // k
        rem = n % k
        sizes = [base + 1 if i < rem else base for i in range(k)]

        chunks = []
        idx = 0
        for size in sizes:
            chunks.append(items[idx:idx + size])
            idx += size
        return chunks

    # ==========================================================
    # GESTION DES PROJETS & EXPORTATIONS
    # ==========================================================

    def _get_next_available_panel_number(self):
        existing = set(self.panels.values())
        num = 1
        while num in existing:
            num += 1
        return num

    def update_dimensions(self):
        try:
            w = float(self.entry_width.get())
            h = float(self.entry_height.get())
            if w <= 0 or h <= 0:
                raise ValueError
            self.panel_width_mm = w
            self.panel_height_mm = h
            self._mark_geometry_change()
            self.draw_grid()
        except ValueError:
            messagebox.showerror('Error', 'Invalid dimensions.')
    
    def _find_zone_for_panel(self, coord):
        r, c = coord
        if not self.roof_zones:
            return None, None
        self._recalculate_zone_grids()
        for z_idx, zone in enumerate(self.roof_zones):
            rows = zone.get("rows", 0)
            cols = zone.get("cols", 0)
            row_base = zone.get("row_base", z_idx * 100)
            if row_base <= r < row_base + rows and 0 <= c < cols:
                return z_idx, zone
        return None, None
