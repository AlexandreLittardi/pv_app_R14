"""Geometrie de l'ombre : polygones, enveloppe convexe, projection, pourcentages d'ombrage."""

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



class ShadowGeometryMixin:
    @staticmethod
    def _polygon_area(points):
        if len(points) < 3:
            return 0.0
        return abs(sum(
            points[i][0] * points[(i + 1) % len(points)][1]
            - points[(i + 1) % len(points)][0] * points[i][1]
            for i in range(len(points))
        )) / 2.0

    @staticmethod
    def _clip_polygon_against_edge(subject, edge_start, edge_end):
        """Clippe un polygone convexe par une arête orientée (Sutherland-Hodgman)."""
        if not subject:
            return []
        ex, ey = edge_end[0] - edge_start[0], edge_end[1] - edge_start[1]

        def inside(p):
            return ex * (p[1] - edge_start[1]) - ey * (p[0] - edge_start[0]) >= -1e-9

        def intersection(a, b):
            dx, dy = b[0] - a[0], b[1] - a[1]
            denom = ex * dy - ey * dx
            if abs(denom) < 1e-12:
                return b
            t = (ex * (edge_start[1] - a[1]) - ey * (edge_start[0] - a[0])) / denom
            return (a[0] + t * dx, a[1] + t * dy)

        output = []
        prev = subject[-1]
        prev_inside = inside(prev)
        for curr in subject:
            curr_inside = inside(curr)
            if curr_inside:
                if not prev_inside:
                    output.append(intersection(prev, curr))
                output.append(curr)
            elif prev_inside:
                output.append(intersection(prev, curr))
            prev, prev_inside = curr, curr_inside
        return output

    @classmethod
    def _polygon_clip(cls, subject, clip):
        result = list(subject)
        if len(result) < 3:
            return []
        for i in range(len(clip)):
            result = cls._clip_polygon_against_edge(
                result, clip[i], clip[(i + 1) % len(clip)]
            )
            if len(result) < 3:
                return []
        return result

    def _panel_rect(self, coord):
        """Retourne le rectangle physique du panneau en coordonnées image."""
        r, c = coord
        if not self.roof_zones or self.px_per_mm <= 0:
            w = float(self.cell_size_px)
            h = float(self.cell_size_px) * (self.panel_height_mm / self.panel_width_mm)
            x1, y1 = c * w, r * h
            return [(x1, y1), (x1+w, y1), (x1+w, y1+h), (x1, y1+h)]

        self._recalculate_zone_grids()
        for z_idx, zone in enumerate(self.roof_zones):
            rows = zone.get("rows", 0)
            cols = zone.get("cols", 0)
            row_base = zone.get("row_base", z_idx * 100)
            if row_base <= r < row_base + rows and 0 <= c < cols:
                local_r = r - row_base
                x1 = min(zone["x1"], zone["x2"]) + zone.get("offset_x_mm", 0.0) * self.px_per_mm
                y1 = min(zone["y1"], zone["y2"]) + zone.get("offset_y_mm", 0.0) * self.px_per_mm
                pw = self.panel_width_mm * self.px_per_mm
                ph = self.panel_height_mm * self.px_per_mm
                px1, py1 = x1 + c * (pw+zone.get('gap_x_mm',0)*self.px_per_mm), y1 + local_r * (ph+zone.get('gap_y_mm',0)*self.px_per_mm)
                return self._zone_rotate_rect(zone, px1, py1, px1 + pw, py1 + ph)
        return []

    @staticmethod
    def _convex_hull(points):
        """Retourne l'enveloppe convexe d'un nuage de points 2D."""
        pts = sorted(set((float(x), float(y)) for x, y in points))
        if len(pts) <= 1:
            return pts

        def cross(o, a, b):
            return ((a[0] - o[0]) * (b[1] - o[1])
                    - (a[1] - o[1]) * (b[0] - o[0]))

        lower = []
        for p in pts:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 1e-12:
                lower.pop()
            lower.append(p)

        upper = []
        for p in reversed(pts):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 1e-12:
                upper.pop()
            upper.append(p)

        return lower[:-1] + upper[:-1]

    def _legacy_shadow_geometry(self, elevation, azimuth):
        """Calcule les polygones d'ombre projetés par le pylône, par hauteur de zone."""
        if elevation <= 0.1 or self.pylon_img_pos is None or self.px_per_mm <= 0:
            return []

        shadow_az = (azimuth + 180.0) % 360.0
        ang = math.radians(shadow_az + self.north_offset_deg)
        dir_x, dir_y = math.sin(ang), -math.cos(ang)
        px_pt, py_pt = self.pylon_img_pos
        half_w = (self.pylon_width_mm / 2.0) * self.px_per_mm
        
        # Empreinte au sol du pylône
        base = [
            (px_pt - half_w, py_pt - half_w),
            (px_pt + half_w, py_pt - half_w),
            (px_pt + half_w, py_pt + half_w),
            (px_pt - half_w, py_pt + half_w),
        ]
        
        tan_e = math.tan(math.radians(elevation))
        if tan_e <= 1e-9:
            return []

        self._recalculate_zone_grids()
        geometries = []
        for z_idx, zone in enumerate(self.roof_zones):
            z_height = zone.get("z_mm", 0.0)
            h_diff = self.pylon_height_mm - z_height
            if h_diff <= 0:
                continue

            # Longueur de l'ombre portée pour cette hauteur de plan
            distance_px = (h_diff / tan_e) * self.px_per_mm

            end_base = [
                (x + dir_x * distance_px, y + dir_y * distance_px)
                for x, y in base
            ]

            # L'ombre est l'enveloppe convexe de la base et de la projection du sommet
            shadow_poly = self._convex_hull(base + end_base)

            geometries.append({
                "zone_idx": z_idx,
                "zone_id": zone.get("id", z_idx + 1),
                "polygon": shadow_poly,
                "start": (px_pt, py_pt),
                "end": (
                    px_pt + dir_x * distance_px,
                    py_pt + dir_y * distance_px
                ),
            })
        return geometries

    def _compute_shadow_geometry(self,elevation,azimuth):
        geometries=self._legacy_shadow_geometry(elevation,azimuth)
        for g in geometries:g['opacity']=max(0,min(1,self.pylon_opacity))
        if elevation<=0.1 or self.px_per_mm<=0:return geometries
        angle=math.radians(azimuth+180+self.north_offset_deg)
        dx,dy=math.sin(angle),-math.cos(angle)
        for obstacle in getattr(self,'model_settings',{}).get('shadow_obstacles',[]):
            base=[tuple(p) for p in obstacle['footprint_px']]
            for idx,zone in enumerate(self.roof_zones):
                height=obstacle['height_mm']-zone.get('z_mm',0)
                if height<=0:continue
                distance=height/math.tan(math.radians(elevation))*self.px_per_mm
                poly=self._convex_hull(base+[(x+dx*distance,y+dy*distance) for x,y in base])
                center=tuple(sum(p[i] for p in base)/len(base) for i in (0,1))
                geometries.append({'zone_idx':idx,'zone_id':zone.get('id',idx+1),'polygon':poly,
                    'start':center,'end':(center[0]+dx*distance,center[1]+dy*distance),
                    'opacity':obstacle.get('opacity',1)})
        return geometries

    def _calculate_shadow_percentages(self, elevation, azimuth):
        """Calcule le % d'ombre panneau par panneau, avec la hauteur de sa zone."""
        shadow_pct = {}
        shadow_polygons = []
        geometries = self._compute_shadow_geometry(elevation, azimuth)
        from shading_models import optical_area
        geom_by_zone={}
        for g in geometries:geom_by_zone.setdefault(g['zone_idx'],[]).append(g)
        self._recalculate_zone_grids()
        for coord in self.panels:
            panel_poly=self._panel_rect(coord)
            if not panel_poly:continue
            zone_idx=next((i for i,z in enumerate(self.roof_zones) if z['row_base']<=coord[0]<z['row_base']+z['rows']),None)
            layers=[]
            for g in geom_by_zone.get(zone_idx,[]):
                clipped=self._polygon_clip(g['polygon'],panel_poly)
                if len(clipped)>=3:layers.append((clipped,g.get('opacity',1)))
            area=self._polygon_area(panel_poly)
            pct=min(100,100*optical_area(layers)/area) if area>1e-12 else 0
            if pct>0:
                shadow_pct[coord]=pct
                for clipped,alpha in layers:shadow_polygons.append({'coord':coord,'zone_idx':zone_idx,
                    'zone_id':self.roof_zones[zone_idx].get('id',zone_idx+1),'polygon':clipped,'pct':pct})

        return shadow_pct, shadow_polygons, geometries

    def _point_near_segment(self, px, py, x1, y1, x2, y2, max_dist):
        dx, dy = x2 - x1, y2 - y1
        seg_len_sq = dx * dx + dy * dy
        if seg_len_sq < 1e-9:
            return math.hypot(px - x1, py - y1) <= max_dist
        t = ((px - x1) * dx + (py - y1) * dy) / seg_len_sq
        t = max(0.0, min(1.0, t))
        proj_x = x1 + t * dx
        proj_y = y1 + t * dy
        return math.hypot(px - proj_x, py - proj_y) <= max_dist