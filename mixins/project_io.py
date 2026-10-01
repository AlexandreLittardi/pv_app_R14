"""Sauvegarde/chargement du projet JSON et exports (CSV, JPG)."""

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

from project_validation import normalize_project, normalize_formula_storage, resolve_image
from mixins.material_tools import default_material_categories
from mixins.spreadsheet_tools import default_spreadsheet_state


class ProjectIOMixin:
    def _collect_project_data(self):
        self._clean_deleted_panels_from_strings()
        extra = self._prepare_project_save()
        data = {
            "project_name": self.project_name,
            "panel_width_mm": self.panel_width_mm,
            "panel_height_mm": self.panel_height_mm,
            "continuous_panel_numbers": self.var_continuous_numbers.get(),
            "string_min_panels": self.string_min_var.get(),
            "string_max_panels": self.string_max_var.get(),
            "string_direction": self.string_direction_var.get(),
            "panel_tilt_deg": self.panel_tilt_deg,
            "panel_azimuth_deg": self.panel_azimuth_deg,
            "panel_orientations": {
                f"{r},{c}": orientation for (r, c), orientation in self.panel_orientations.items()
                if (r, c) in self.panels
            },
            "roof_image_path": self.roof_image_path,
            "scale_p1": self.scale_p1,
            "scale_p2": self.scale_p2,
            "scale_length_mm": self.scale_length_mm,
            "px_per_mm": self.px_per_mm,
            "roof_zones": self.roof_zones,
            "roof_polygons": self.roof_polygons,
            "distance_markers": self.distance_markers,
            "measures": self.measures,
            "cable_paths": self.cable_paths,
            "blocks": self.blocks,
            "inverter_positions": {
                block_name: {
                    **pos, "x": pos["x"], "y": pos["y"], "material_row": pos.get("material_row", {})
                }
                for block_name, pos in self.inverter_positions.items()
            },
            "panels": {f"{r},{c}": num for (r, c), num in self.panels.items()},
            "panel_blocks": {f"{r},{c}": b for (r, c), b in self.panel_blocks.items()},
            "strings": {s_id: [f"{r},{c}" for r, c in coords] for s_id, coords in self.strings.items()},
            "manual_strings": list(self.manual_strings),
            "string_mppt_assignment": self.string_mppt_assignment,
            "pylon_img_pos": self.pylon_img_pos,
            "pylon_ref_img_pos": self.pylon_ref_img_pos,
            "pylon_height_mm": self.pylon_height_mm,
            "pylon_width_mm": self.pylon_width_mm,
            "pylon_opacity": self.pylon_opacity,
            "north_offset_deg": self.north_offset_deg,
            "solar_latitude": self.solar_latitude,
            "solar_longitude": self.solar_longitude,
            "solar_utc_offset": self.solar_utc_offset,
            "solar_day": self.solar_day,
            "solar_month": self.solar_month,
            "solar_hour": self.solar_hour,
            "panel_pmax_w": self.panel_pmax_w,
            "panel_efficiency_pct": self.panel_efficiency_pct,
            "panel_temp_coeff_pct": self.panel_temp_coeff_pct,
            "panel_noct_c": self.panel_noct_c,
            "material_categories": self.material_categories,
            "material_spreadsheet": self.material_spreadsheet,
            "diagram_nodes": self.diagram_nodes,
            "diagram_links": self.diagram_links,
            "diagram_electrical_specs": self.diagram_electrical_specs,
            "diagram_show_electrical": self.diagram_show_electrical,
            "diagram_next_custom_id": self.diagram_next_custom_id,
            "project_notes": self.project_notes,
            "cable_calc_params": self.cable_calc_params,
            "cable_string_params": self.cable_string_params,
            "cable_mass_by_section": self.cable_mass_by_section,
        }

        data.update(extra)
        from project_store import EXTRA_STATE, serial
        for name in EXTRA_STATE:
            if hasattr(self, name): data[name] = serial(getattr(self, name))
        normalize_formula_storage(data)
        return data

    def _on_ctrl_s(self, event=None):
        self.save_project()
        return "break"

    def _auto_save(self):
        try:
            self.save_project(silent=True)
        except Exception as e:
            print(f"Autosave error: {e}")
        finally:
            self.root.after(self.autosave_interval_ms, self._auto_save)

    def _flash_autosave_notice(self):
        """Affiche brièvement une confirmation discrète de sauvegarde automatique."""
        original_text = f"Active project: {self.project_name}"
        self.lbl_project_info.config(text=f"💾 {original_text} (autosaved)")
        self.root.after(3000, lambda: self.lbl_project_info.config(text=original_text))

    def import_project(self):
        filepath = filedialog.askopenfilename(
            parent=self.root,
            title='Import a JSON project',
            filetypes=[('JSON files', "*.json"), ('All files', "*.*")]
        )
        if filepath:
            self._load_project_file(filepath)

    def _load_project_file(self, filepath, data_override=None, quiet=False):
        try:
            if data_override is None:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = normalize_project(json.load(f))
            else:
                data = data_override

            self.project_name = data.get("project_name", os.path.splitext(os.path.basename(filepath))[0])
            self.current_project_filepath = filepath

            self.panel_width_mm = float(data.get("panel_width_mm", 1000.0))
            self.panel_height_mm = float(data.get("panel_height_mm", 1700.0))

            self.entry_width.delete(0, tk.END)
            self.entry_width.insert(0, str(int(self.panel_width_mm)))
            self.entry_height.delete(0, tk.END)
            self.entry_height.insert(0, str(int(self.panel_height_mm)))

            img_path = resolve_image(filepath, data.get("roof_image_path"))
            self.roof_pil_img = None
            self.roof_image_path = None

            if img_path:
                if not os.path.isabs(img_path):
                    img_path = os.path.join(self.projects_dir, img_path)

                if HAS_PIL and os.path.exists(img_path):
                    try:
                        with Image.open(img_path) as image:
                            self.roof_pil_img = image.copy()
                        self.roof_image_path = img_path
                    except Exception as e:
                        print(f"Unable to load image: {e}")

            self.scale_p1 = data.get("scale_p1")
            self.scale_p2 = data.get("scale_p2")
            self.scale_length_mm = float(data.get("scale_length_mm", 0.0))
            self.px_per_mm = float(data.get("px_per_mm", 0.0))
            self.roof_zones = data.get("roof_zones", [])
            self.roof_polygons = []
            for p in data.get("roof_polygons", []):
                pts = [tuple(pt) for pt in p.get("points", [])]
                self.roof_polygons.append({
                    "id": p.get("id", len(self.roof_polygons) + 1),
                    "points": pts,
                    **({"installation_height_m": p["installation_height_m"]} if "installation_height_m" in p else {})
                })
            self.distance_markers = []
            for m in data.get("distance_markers", []):
                self.distance_markers.append({
                    "point": tuple(m.get("point", (0, 0))),
                    "nearest_point": tuple(m.get("nearest_point", (0, 0))),
                    "label": m.get("label", m.get("zone_id", "edge")),
                    "distance_mm": float(m.get("distance_mm", 0.0))
                })
            self.active_polygon_idx = 0 if self.roof_polygons else None
            self.path_mode = "select"
            self.temp_polygon_points = []
            self.measures = []
            for measure in data.get("measures", []):
                if isinstance(measure, dict):
                    self.measures.append({**{key: tuple(measure[key]) for key in ("p1", "p2", "label")}, "axis": measure.get("axis", "aligned")})
                elif len(measure) == 2:
                    p1, p2 = measure
                    self.measures.append({"p1": tuple(p1), "p2": tuple(p2),
                                          "label": ((p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2)})

            self.cable_paths = []
            for p in data.get("cable_paths", []):
                pts = [tuple(pt) for pt in p.get("points", [])]
                self.cable_paths.append({
                    "id": p.get("id", len(self.cable_paths) + 1),
                    "points": pts
                })
            self.active_cable_path_idx = 0 if self.cable_paths else None
            self.temp_cable_path_points = []
            self._invalidate_cable_routes()
            self._update_cable_path_combo()

            self.blocks = data.get("blocks", {})

            self.inverter_positions = {}
            for block_name, pos in data.get("inverter_positions", {}).items():
                if "x" not in pos or "y" not in pos:
                    continue
                self.inverter_positions[block_name] = {
                    **pos,
                    "x": float(pos["x"]),
                    "y": float(pos["y"]),
                    "material_row": dict(pos.get("material_row", {})),
                }
            self.layout_mode = "select"
            self.pending_inverter_placement = None

            self.panels = {}
            self.var_continuous_numbers.set(bool(data.get("continuous_panel_numbers", True)))
            self.string_min_var.set(str(data.get("string_min_panels", "6")))
            self.string_max_var.set(str(data.get("string_max_panels", "10")))
            direction = data.get("string_direction", "Auto (layout)")
            self.string_direction_var.set(direction if direction in
                                          ("Auto (layout)", "Horizontal", "Vertical") else "Auto (layout)")
            self.panel_tilt_deg = float(data.get("panel_tilt_deg", 8.0))
            self.panel_azimuth_deg = float(data.get("panel_azimuth_deg", 180.0))
            self._set_layout_orientation_entries(self.panel_tilt_deg, self.panel_azimuth_deg)
            for k, num in data.get("panels", {}).items():
                r, c = map(int, k.split(","))
                self.panels[(r, c)] = num

            self.panel_orientations = {}
            for key, orientation in data.get("panel_orientations", {}).items():
                coord = tuple(map(int, key.split(",")))
                if coord in self.panels and isinstance(orientation, dict):
                    self.panel_orientations[coord] = {
                        "tilt_deg": float(orientation.get("tilt_deg", self.panel_tilt_deg)),
                        "azimuth_deg": float(orientation.get("azimuth_deg", self.panel_azimuth_deg)),
                    }
            self.selected_panel_coords.clear()

            self.panel_blocks = {}
            for k, b in data.get("panel_blocks", {}).items():
                r, c = map(int, k.split(","))
                self.panel_blocks[(r, c)] = b

            self.strings = {}
            for s_id, coords_str in data.get("strings", {}).items():
                coords = []
                for k in coords_str:
                    r, c = map(int, k.split(","))
                    coords.append((r, c))
                self.strings[s_id] = coords

            if not self.strings:
                self.strings = {"String 1": []}

            self.manual_strings = set(data.get("manual_strings", []))

            self.string_mppt_assignment = {}
            for sid, assign in data.get("string_mppt_assignment", {}).items():
                if isinstance(assign, dict) and "block" in assign and "mppt" in assign:
                    self.string_mppt_assignment[sid] = {"block": assign["block"], "mppt": int(assign["mppt"])}
            self._prune_mppt_assignments()

            self._update_combo_blocks()
            self._update_combo_strings()
            sorted_keys = self._get_sorted_string_keys()
            self.active_string_id = sorted_keys[0] if sorted_keys else "String 1"
            self.combo_strings.set(self.active_string_id)

            self.selected_zone_indices.clear()
            self.active_zone_idx = 0 if self.roof_zones else None
            self._update_zone_combo()
            self._update_zone_entries_from_active()
            self._update_polygon_combo()
            self._update_string_listbox()

            # ------------------------------------------------
            # Ombre du Pylône
            # ------------------------------------------------
            p_pos = data.get("pylon_img_pos")
            self.pylon_img_pos = tuple(p_pos) if p_pos else None
            r_pos = data.get("pylon_ref_img_pos")
            self.pylon_ref_img_pos = tuple(r_pos) if r_pos else None
            self.pylon_height_mm = float(data.get("pylon_height_mm", 3000.0))
            self.pylon_width_mm = float(data.get("pylon_width_mm", 300.0))
            self.pylon_opacity = max(0.0, min(1.0, float(data.get("pylon_opacity", 1.0))))
            self.north_offset_deg = float(data.get("north_offset_deg", 0.0))
            self.solar_latitude = float(data.get("solar_latitude", self.solar_latitude))
            self.solar_longitude = float(data.get("solar_longitude", self.solar_longitude))
            self.solar_utc_offset = float(data.get("solar_utc_offset", self.solar_utc_offset))
            self.solar_day = int(data.get("solar_day", self.solar_day))
            self.solar_month = int(data.get("solar_month", self.solar_month))
            self.solar_hour = float(data.get("solar_hour", self.solar_hour))
            self.panel_pmax_w = float(data.get('panel_pmax_w', self.panel_pmax_w))
            self.panel_efficiency_pct = float(data.get('panel_efficiency_pct', self.panel_efficiency_pct))
            self.panel_temp_coeff_pct = float(data.get('panel_temp_coeff_pct', self.panel_temp_coeff_pct))
            self.panel_noct_c = float(data.get('panel_noct_c', self.panel_noct_c))
            self.active_shadow_zone_idx = None
            self.shadow_result = {"elevation": None, "azimuth": None, "shadowed": set(), "message": None}

            if hasattr(self, "entry_pylon_height"):
                for entry, value in [
                    (self.entry_pylon_height, int(self.pylon_height_mm)),
                    (self.entry_pylon_width, int(self.pylon_width_mm)),
                    (self.entry_solar_lat, self.solar_latitude),
                    (self.entry_solar_lon, self.solar_longitude),
                    (self.entry_solar_day, self.solar_day),
                    (self.entry_solar_month, self.solar_month),
                    (self.entry_solar_hour, self._decimal_hour_to_hhmm(self.solar_hour)),
                    (self.entry_solar_utc, self.solar_utc_offset),
                    (self.entry_north_offset, self.north_offset_deg),
                    (self.entry_panel_pmax, self.panel_pmax_w),
                    (self.entry_panel_efficiency, self.panel_efficiency_pct),
                    (self.entry_panel_temp_coeff, self.panel_temp_coeff_pct),
                    (self.entry_panel_noct, self.panel_noct_c),
                ]:
                    entry.delete(0, tk.END)
                    entry.insert(0, str(value))
                if hasattr(self, "entry_pylon_opacity"):
                    self.entry_pylon_opacity.delete(0, tk.END)
                    self.entry_pylon_opacity.insert(0, str(int(round(self.pylon_opacity * 100.0))))
                self._update_shadow_delta_entries()
                self._refresh_shadow_zone_list()
                if self.pylon_img_pos:
                    self._recompute_shadow()
                self._update_shadow_status_label()

            # ------------------------------------------------
            # Fiche Matériel
            # ------------------------------------------------
            loaded_materials = data.get("material_categories")
            if loaded_materials:
                defaults = default_material_categories()
                defaults.update(loaded_materials)
                self.material_categories = defaults
            else:
                self.material_categories = default_material_categories()
            self._refresh_material_trees()

            # ------------------------------------------------
            # Feuille de calcul (Fiche Matériel)
            # ------------------------------------------------
            loaded_spreadsheet = data.get("material_spreadsheet")
            if loaded_spreadsheet:
                defaults = default_spreadsheet_state()
                defaults.update(loaded_spreadsheet)
                self.material_spreadsheet = defaults
            else:
                self.material_spreadsheet = default_spreadsheet_state()
            if hasattr(self, "_rebuild_spreadsheet_grid"):
                self._rebuild_spreadsheet_grid()

            # ------------------------------------------------
            # Schéma Unifilaire
            # ------------------------------------------------
            self.diagram_nodes = {
                node_id: dict(node) for node_id, node in data.get("diagram_nodes", {}).items()
            }
            self.diagram_links = list(data.get("diagram_links", []))
            specs = data.get("diagram_electrical_specs", {})
            self.diagram_electrical_specs = dict(specs) if isinstance(specs, dict) else {}
            self.diagram_show_electrical = bool(data.get("diagram_show_electrical", False))
            self.diagram_next_custom_id = int(data.get("diagram_next_custom_id", 1))
            self.diagram_selected_node = None
            self._refresh_diagram_list()

            self.project_notes = data.get("project_notes", "")
            defaults = {"current_a": 10.0, "voltage_v": 600.0, "length_m": 50.0,
                        "resistivity": 0.017, "target_drop_pct": 1.0}
            loaded_cable_params = data.get("cable_calc_params", {})
            if isinstance(loaded_cable_params, dict):
                defaults.update(loaded_cable_params)
            self.cable_calc_params = defaults
            self.cable_string_params = dict(data.get("cable_string_params") or {})
            self.cable_mass_by_section = dict(data.get("cable_mass_by_section") or {})
            if hasattr(self, "txt_notes"):
                self._refresh_notes()

            if hasattr(self, "equip_tree"):
                self._refresh_equipment_tree()

            self._load_energy_state(data)
            self.lbl_project_info.config(text=f"Active project: {self.project_name}")
            self._remember_recent_project(filepath)
            self.draw_grid()

        except Exception as e:
            if quiet: raise
            messagebox.showerror('Error', f"Unable to load JSON file:\n{e}")

    def export_csv(self):
        if not self.strings:
            messagebox.showwarning('Warning', 'No strings to export.')
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[('CSV files', "*.csv")],
            title='Export stringing as CSV'
        )
        if not filepath:
            return

        try:
            with open(filepath, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f, delimiter=";")

                sorted_keys = self._get_sorted_string_keys()
                for str_id in sorted_keys:
                    coords = self.strings[str_id]
                    if not coords:
                        continue

                    # Détermine le(s) bloc(s) associés à la string
                    block_names = []
                    for (r, c) in coords:
                        b_name = self.panel_blocks.get((r, c), "No block")
                        if b_name not in block_names:
                            block_names.append(b_name)
                    block_label = block_names[0] if len(block_names) == 1 else "Mixed (" + "/".join(block_names) + ")"

                    # Numéro de string (ex: "String 5" -> "5"), sinon le nom complet
                    match = re.search(r"(\d+)\s*$", str_id)
                    string_num = match.group(1) if match else str_id

                    panel_numbers = [str(self.panels.get((r, c), "")) for (r, c) in coords]

                    writer.writerow([block_label, string_num] + panel_numbers)

            messagebox.showinfo('Success', f"CSV export complete:\n{filepath}")
        except Exception as e:
            messagebox.showerror('Error', f"Unable to export CSV:\n{e}")


    def export_jpg_final(self, scale=4):
        filepath=filedialog.asksaveasfilename(defaultextension='.jpg',filetypes=[('JPG image','*.jpg')],title='Export complete project plan')
        if not filepath:return
        try:
            from plan_renderer import render_plan
            size=render_plan(self,filepath,scale)
            messagebox.showinfo('Export',f'Complete plan exported: {size[0]} × {size[1]} pixels.\n{filepath}')
        except Exception as exc:messagebox.showerror('Export',str(exc))
