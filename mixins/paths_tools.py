"""Outils de tracage des chemins/polygones de cablage et mesures de distance."""

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


class PathsToolsMixin:
    def _activate_polygon_select_mode(self):
        self.roof_mode = 'select'
        self.path_mode = 'select_polygon'
        self.draw_grid()

    def _activate_polygon_draw_mode(self):
        if not self.roof_pil_img:
            messagebox.showwarning('Warning', 'Load a roof image first.')
            return
        if self.px_per_mm <= 0:
            messagebox.showwarning('Warning', 'Set the scale before drawing a polygon.')
            return
        self.path_mode = "draw_polygon"
        self.roof_mode = "select"
        self.temp_polygon_points = []
        self.draw_grid()

    def _cancel_polygon_draw(self):
        self.temp_polygon_points = []
        self.path_mode = "select"
        self.draw_grid()

    def _finish_polygon_draw(self):
        if self.path_mode != "draw_polygon":
            return
        from project_store import valid_polygon
        if len(self.temp_polygon_points) >= 3 and valid_polygon(self.temp_polygon_points):
            new_polygon = {
                "id": len(self.roof_polygons) + 1,
                "points": [tuple(p) for p in self.temp_polygon_points]
            }
            self.roof_polygons.append(new_polygon)
            self.active_polygon_idx = len(self.roof_polygons) - 1
            self._update_polygon_combo()
        else:
            messagebox.showinfo("Cable routing area", 'An area needs distinct vertices, no self-intersection and positive area.')

        self.temp_polygon_points = []
        self.path_mode = "select"
        self.draw_grid()

    def _update_polygon_combo(self):
        values = [f"Cable area {p['id']}" for p in self.roof_polygons]
        self.combo_polygons["values"] = values
        if self.active_polygon_idx is not None and 0 <= self.active_polygon_idx < len(self.roof_polygons):
            self.combo_polygons.set(f"Cable area {self.roof_polygons[self.active_polygon_idx]['id']}")
        else:
            self.combo_polygons.set("")

    def _on_polygon_combo_selected(self, event):
        idx = self.combo_polygons.current()
        if 0 <= idx < len(self.roof_polygons):
            self.active_polygon_idx = idx
            self.path_mode = 'select_polygon'
            self.draw_grid()

    # --------------------------------------------------------
    # Chemins de câbles (réseau de polylignes pour le routage Dijkstra)
    # --------------------------------------------------------

    def _activate_cable_path_draw_mode(self):
        if not self.roof_pil_img:
            messagebox.showwarning('Warning', 'Load a roof image first.')
            return
        if self.px_per_mm <= 0:
            messagebox.showwarning('Warning', 'Set the scale before drawing a cable path.')
            return
        self.path_mode = "draw_cable_path"
        self.temp_cable_path_points = []
        self.draw_grid()

    def _cancel_cable_path_draw(self):
        self.temp_cable_path_points = []
        self.path_mode = "select"
        self.draw_grid()

    def _finish_cable_path_draw(self):
        if self.path_mode != "draw_cable_path":
            return
        if len(self.temp_cable_path_points) >= 2:
            new_path = {
                "id": max((int(path.get('id', 0)) for path in self.cable_paths), default=0) + 1,
                "points": [tuple(p) for p in self.temp_cable_path_points]
            }
            self.cable_paths.append(new_path)
            self.active_cable_path_idx = len(self.cable_paths) - 1
            self._invalidate_cable_routes()
            self._update_cable_path_combo()
        else:
            messagebox.showinfo('Cable path', 'A path needs at least 2 points.')

        self.temp_cable_path_points = []
        self.path_mode = "select"
        self._refresh_equipment_tree()
        self.draw_grid()

    def _update_cable_path_combo(self):
        if hasattr(self, '_refresh_cabling_paths'):
            self._refresh_cabling_paths()
        if not hasattr(self, "combo_cable_paths"):
            return
        values = [f"Path {p['id']}" for p in self.cable_paths]
        self.combo_cable_paths["values"] = values
        if self.active_cable_path_idx is not None and 0 <= self.active_cable_path_idx < len(self.cable_paths):
            self.combo_cable_paths.set(f"Path {self.cable_paths[self.active_cable_path_idx]['id']}")
        else:
            self.combo_cable_paths.set("")

    def _on_cable_path_combo_selected(self, event):
        idx = self.combo_cable_paths.current()
        if 0 <= idx < len(self.cable_paths):
            self.active_cable_path_idx = idx
            self._refresh_cabling_paths()
            self.draw_grid()

    def delete_active_cable_path(self):
        if self.active_cable_path_idx is None or self.active_cable_path_idx >= len(self.cable_paths):
            messagebox.showinfo("Info", 'Select a cable path to delete.')
            return
        self.cable_paths.pop(self.active_cable_path_idx)
        self._invalidate_cable_routes()
        if self.cable_paths:
            self.active_cable_path_idx = min(self.active_cable_path_idx, len(self.cable_paths) - 1)
        else:
            self.active_cable_path_idx = None
        self._update_cable_path_combo()
        self._refresh_equipment_tree()
        self.draw_grid()

    def delete_active_polygon(self):
        if self.active_polygon_idx is None or self.active_polygon_idx >= len(self.roof_polygons):
            return
        self.roof_polygons.pop(self.active_polygon_idx)
        if self.roof_polygons:
            self.active_polygon_idx = min(self.active_polygon_idx, len(self.roof_polygons) - 1)
        else:
            self.active_polygon_idx = None
        self._update_polygon_combo()
        self.draw_grid()

    @staticmethod
    def _point_in_polygon(px, py, points):
        """Test point-dans-polygone (ray casting)."""
        n = len(points)
        inside = False
        x1, y1 = points[0]
        for i in range(1, n + 1):
            x2, y2 = points[i % n]
            if ((y1 > py) != (y2 > py)) and (px < (x2 - x1) * (py - y1) / (y2 - y1 + 1e-12) + x1):
                inside = not inside
            x1, y1 = x2, y2
        return inside

    def _hit_test_polygon(self, img_x, img_y):
        """img_x, img_y en coordonnées image d'origine. Retourne l'index du polygone contenant le point, ou None."""
        for idx, poly in enumerate(self.roof_polygons):
            if len(poly["points"]) >= 3 and self._point_in_polygon(img_x, img_y, poly["points"]):
                return idx
        return None

    # --------------------------------------------------------
    # Mesure de distance à la zone la plus proche
    # --------------------------------------------------------

    def _toggle_distance_mode(self):
        if not self.roof_zones:
            messagebox.showwarning('Warning', 'Define at least one zone first.')
            return
        if self.path_mode == "draw_polygon":
            self.temp_polygon_points = []
        if self.path_mode == "measure_distance":
            self.path_mode = "select"
        else:
            self.path_mode = "measure_distance"
            self.roof_mode = 'select'
        self.draw_grid()

    def clear_distance_markers(self):
        self.distance_markers = []
        self.draw_grid()

    def _get_all_borders(self):
        """Renvoie la liste de tous les bords : contour(s) du/des polygone(s) et contour de chaque
        zone (qui forme un « trou » dans le polygone). Chaque bord est identifié par une source
        unique, ce qui permet d'exclure le bord de départ lors de la recherche du bord opposé."""
        borders = []
        for poly in self.roof_polygons:
            pts = poly["points"]
            n = len(pts)
            if n < 2:
                continue
            segs = [(pts[i][0], pts[i][1], pts[(i + 1) % n][0], pts[(i + 1) % n][1]) for i in range(n)]
            borders.append({"source": ("polygon", poly["id"]), "label": f"Cable area {poly['id']}", "segments": segs})

        for z in self.roof_zones:
            x1, y1 = min(z["x1"], z["x2"]), min(z["y1"], z["y2"])
            x2, y2 = max(z["x1"], z["x2"]), max(z["y1"], z["y2"])
            segs = [(x1, y1, x2, y1), (x2, y1, x2, y2), (x2, y2, x1, y2), (x1, y2, x1, y1)]
            borders.append({"source": ("zone", z["id"]), "label": f"Zone {z['id']}", "segments": segs})

        return borders

    @staticmethod
    def _nearest_point_on_segment(px, py, x1, y1, x2, y2):
        dx, dy = x2 - x1, y2 - y1
        if dx == 0 and dy == 0:
            return x1, y1, math.hypot(px - x1, py - y1)
        t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
        t = max(0.0, min(1.0, t))
        nx, ny = x1 + t * dx, y1 + t * dy
        return nx, ny, math.hypot(px - nx, py - ny)

    def _nearest_point_on_borders(self, px, py, borders, exclude_source=None):
        """Retourne (x, y, distance, border) du point le plus proche de (px, py) parmi tous les bords,
        en excluant éventuellement un bord donné (pour chercher le bord OPPOSÉ)."""
        best = None
        for b in borders:
            if exclude_source is not None and b["source"] == exclude_source:
                continue
            for (x1, y1, x2, y2) in b["segments"]:
                nx, ny, dist = self._nearest_point_on_segment(px, py, x1, y1, x2, y2)
                if best is None or dist < best[2]:
                    best = (nx, ny, dist, b)
        return best

    def _add_distance_marker_at(self, img_x, img_y):
        """Trouve le bord le plus proche du clic, puis le bord OPPOSÉ le plus proche de ce premier
        bord : la distance entre les deux représente la largeur de l'espace disponible à cet endroit."""
        borders = self._get_all_borders()
        if not borders:
            return

        nearest1 = self._nearest_point_on_borders(img_x, img_y, borders)
        if nearest1 is None:
            return
        p1x, p1y, _dist1, border1 = nearest1

        nearest2 = self._nearest_point_on_borders(p1x, p1y, borders, exclude_source=border1["source"])
        if nearest2 is None:
            return
        p2x, p2y, dist2, border2 = nearest2

        dist_mm = dist2 / self.px_per_mm if self.px_per_mm > 0 else dist2
        self.distance_markers.append({
            "point": (p1x, p1y),
            "nearest_point": (p2x, p2y),
            "label": border2["label"],
            "distance_mm": dist_mm
        })

    def _hit_test_distance_marker(self, cx, cy, threshold=10):
        """cx, cy en coordonnées canvas (déjà zoomées). Retourne l'index de la mesure la plus proche
        du clic (sur son segment point → bord opposé), ou None si aucune n'est assez proche."""
        zoom = self.zoom_level
        best_idx = None
        best_dist = None
        for idx, marker in enumerate(self.distance_markers):
            x1, y1 = marker["point"][0] * zoom, marker["point"][1] * zoom
            x2, y2 = marker["nearest_point"][0] * zoom, marker["nearest_point"][1] * zoom
            _, _, dist = self._nearest_point_on_segment(cx, cy, x1, y1, x2, y2)
            if dist <= threshold and (best_dist is None or dist < best_dist):
                best_dist = dist
                best_idx = idx
        return best_idx

    def _draw_text_with_bg(self, x, y, text, fill="#D32F2F", font=("Arial", 9, "bold"), anchor="center"):
        """Dessine un texte sur le canvas avec un fond blanc opaque derrière, pour la lisibilité."""
        txt_id = self.canvas.create_text(x, y, text=text, fill=fill, font=font, anchor=anchor)
        bbox = self.canvas.bbox(txt_id)
        if bbox:
            pad = 3
            rect_id = self.canvas.create_rectangle(
                bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad,
                fill="white", outline="#BDBDBD"
            )
            self.canvas.tag_lower(rect_id, txt_id)
        return txt_id

    # --------------------------------------------------------
    # Zone disponible coloriée (polygone moins les zones)
    # --------------------------------------------------------

    def _compute_polygon_overlay(self, zoom):
        if not HAS_PIL or not self.roof_pil_img or not self.roof_polygons:
            return None
        w, h = self.roof_pil_img.size
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        fill_color = (46, 204, 113, 120)  # vert translucide = espace disponible

        for poly in self.roof_polygons:
            if len(poly["points"]) >= 3:
                draw.polygon(poly["points"], fill=fill_color)

        # On "découpe" les zones occupées (transparence totale)
        for z in self.roof_zones:
            x1, y1 = min(z["x1"], z["x2"]), min(z["y1"], z["y2"])
            x2, y2 = max(z["x1"], z["x2"]), max(z["y1"], z["y2"])
            draw.rectangle([x1, y1, x2, y2], fill=(0, 0, 0, 0))

        if zoom != 1.0:
            new_w = max(1, int(w * zoom))
            new_h = max(1, int(h * zoom))
            overlay = overlay.resize((new_w, new_h), self._get_image_resample_filter())

        return overlay

    def _on_canvas_motion(self, event):
        tab_idx = self._get_active_tab_index()
        self.canvas.delete("string_hover")
        if tab_idx == 3 and not (event.state & 0x0100):
            cell = self._get_cell_coords(event)
            if cell in self.panels:
                for string_id, coords in self.strings.items():
                    if cell in coords:
                        x = self.canvas.canvasx(event.x) + 16
                        y = self.canvas.canvasy(event.y) - 18
                        label = f"{string_id} · panel #{self.panels[cell]} · position {coords.index(cell) + 1}/{len(coords)}"
                        item = self.canvas.create_text(x, y, text=label, anchor=tk.SW,
                                                       font=("Arial", 12, "bold"), fill="#FFFFFF",
                                                       tags="string_hover")
                        bbox = self.canvas.bbox(item)
                        if bbox:
                            box = self.canvas.create_rectangle(bbox[0] - 7, bbox[1] - 4,
                                                               bbox[2] + 7, bbox[3] + 4,
                                                               fill="#263238", outline="#FFFFFF",
                                                               tags="string_hover")
                            self.canvas.tag_lower(box, item)
                        break
            return
        if tab_idx == 1 and self.path_mode == "draw_polygon" and self.temp_polygon_points:
            self.draw_grid()
            cx = self.canvas.canvasx(event.x)
            cy = self.canvas.canvasy(event.y)
            zoom = self.zoom_level
            pts = [(x * zoom, y * zoom) for (x, y) in self.temp_polygon_points]
            for i in range(len(pts) - 1):
                self.canvas.create_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                                        fill="#2E7D32", width=3)
            self.canvas.create_line(pts[-1][0], pts[-1][1], cx, cy, fill="#2E7D32", width=2, dash=(4, 3))
            # Aperçu de la fermeture du polygone (retour au premier point)
            self.canvas.create_line(cx, cy, pts[0][0], pts[0][1], fill="#2E7D32", width=1, dash=(2, 4))
            for (px, py) in pts:
                self.canvas.create_oval(px - 4, py - 4, px + 4, py + 4, fill="#2E7D32", outline="white")
            return

        if tab_idx == 8 and self.path_mode == "draw_cable_path" and self.temp_cable_path_points:
            self.draw_grid()
            cx = self.canvas.canvasx(event.x)
            cy = self.canvas.canvasy(event.y)
            zoom = self.zoom_level
            pts = [(x * zoom, y * zoom) for (x, y) in self.temp_cable_path_points]
            for i in range(len(pts) - 1):
                self.canvas.create_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                                        fill="#EF6C00", width=3)
            # Aperçu du segment en cours (PAS de fermeture : c'est une polyligne ouverte)
            self.canvas.create_line(pts[-1][0], pts[-1][1], cx, cy, fill="#EF6C00", width=2, dash=(4, 3))
            for (px, py) in pts:
                self.canvas.create_oval(px - 4, py - 4, px + 4, py + 4, fill="#EF6C00", outline="white")

    def _on_escape_key(self, event=None):
        if self.path_mode == "draw_polygon":
            self._cancel_polygon_draw()
        elif self.path_mode == "draw_cable_path":
            self._cancel_cable_path_draw()
        elif self.path_mode == "place_gather_point":
            self.path_mode = "select"
            self.draw_grid()
