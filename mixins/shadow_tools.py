"""Onglet/panneau lateral ombre du pylone et callbacks UI."""

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


from .shadow_geometry import ShadowGeometryMixin
from .shadow_energy import ShadowEnergyMixin
from .shadow_simulation import ShadowSimulationMixin


class ShadowToolsMixin(ShadowGeometryMixin, ShadowEnergyMixin, ShadowSimulationMixin):
    def _build_tab_shadow_tools(self):
        mb_pylon = ttk.Menubutton(self.tab_shadow, text='🗼 Obstacle')
        menu_pylon = tk.Menu(mb_pylon, tearoff=0)
        menu_pylon.add_command(label='📍 Place obstacle (click image)', command=self._activate_place_pylon_mode)
        menu_pylon.add_command(label='🎯 Set reference point (click)', command=self._activate_place_ref_mode)
        menu_pylon.add_separator()
        menu_pylon.add_command(label='🗑️ Clear obstacle', command=self._clear_pylon)
        mb_pylon["menu"] = menu_pylon
        mb_pylon.pack(side=tk.LEFT, padx=5)

        ttk.Separator(self.tab_shadow, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=5)

        ttk.Button(
            self.tab_shadow, text='📅 Multi-day simulation', command=self._open_shadow_simulation
        ).pack(side=tk.LEFT, padx=5)

        ttk.Separator(self.tab_shadow, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        self.lbl_shadow_status = ttk.Label(self.tab_shadow, text='Obstacle not placed.', font=("Arial", 10, "bold"), foreground='#1A237E')
        self.lbl_shadow_status.pack(side=tk.LEFT, padx=5)

        ttk.Separator(self.tab_shadow, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        mb_zoom_shadow = ttk.Menubutton(self.tab_shadow, text="🔍 Zoom")
        menu_zoom_shadow = tk.Menu(mb_zoom_shadow, tearoff=0)
        menu_zoom_shadow.add_command(label='🔍 Zoom in (+)', command=lambda: self._zoom_button_change(1.2))
        menu_zoom_shadow.add_command(label='🔍 Zoom out (-)', command=lambda: self._zoom_button_change(1/1.2))
        menu_zoom_shadow.add_separator()
        menu_zoom_shadow.add_command(label='🎯 Reset (100%)', command=self._reset_zoom)
        mb_zoom_shadow["menu"] = menu_zoom_shadow
        mb_zoom_shadow.pack(side=tk.RIGHT, padx=5)

    def _build_side_panel_shadow(self):
        """Construit le panneau latéral de paramétrage de l'ombre du pylône."""
        self.side_panel_shadow = ttk.Frame(self.main_container, width=290, padding=5)
        scroller=tk.Canvas(self.side_panel_shadow,highlightthickness=0,width=272)
        scrollbar=ttk.Scrollbar(self.side_panel_shadow,orient=tk.VERTICAL,command=scroller.yview)
        scrollbar.pack(side=tk.RIGHT,fill=tk.Y)
        scroller.pack(side=tk.LEFT,fill=tk.BOTH,expand=True)
        scroller.configure(yscrollcommand=scrollbar.set)
        content=ttk.Frame(scroller)
        scroller.create_window((0,0),window=content,anchor=tk.NW,tags=('content',))
        content.bind('<Configure>',lambda event:scroller.configure(scrollregion=scroller.bbox('all')))
        scroller.bind('<Configure>',lambda event:scroller.itemconfigure('content',width=event.width))

        ttk.Label(content, text='Obstacle shadow', font=("Arial", 10, "bold")).pack(pady=(0, 8))

        # --- Section Pylône ---
        frm_pylon = ttk.LabelFrame(content, text='🗼 Obstacle', padding=6)
        frm_pylon.pack(fill=tk.X, pady=4)

        row1 = ttk.Frame(frm_pylon)
        row1.pack(fill=tk.X, pady=2)
        ttk.Label(row1, text='Height (mm):', width=14).pack(side=tk.LEFT)
        self.entry_pylon_height = ttk.Entry(row1, width=10)
        self.entry_pylon_height.insert(0, str(int(self.pylon_height_mm)))
        self.entry_pylon_height.pack(side=tk.LEFT)

        row2 = ttk.Frame(frm_pylon)
        row2.pack(fill=tk.X, pady=2)
        ttk.Label(row2, text='Width (mm):', width=14).pack(side=tk.LEFT)
        self.entry_pylon_width = ttk.Entry(row2, width=10)
        self.entry_pylon_width.insert(0, str(int(self.pylon_width_mm)))
        self.entry_pylon_width.pack(side=tk.LEFT)

        row_opacity = ttk.Frame(frm_pylon)
        row_opacity.pack(fill=tk.X, pady=2)
        ttk.Label(row_opacity, text='Opacity (%):', width=14).pack(side=tk.LEFT)
        self.entry_pylon_opacity = ttk.Entry(row_opacity, width=10)
        self.entry_pylon_opacity.insert(0, str(int(round(self.pylon_opacity * 100.0))))
        self.entry_pylon_opacity.pack(side=tk.LEFT)
        ttk.Label(
            frm_pylon,
            text='Position relative to reference point:',
            font=("Arial", 8), foreground="#555555"
        ).pack(anchor="w", pady=(6, 0))

        row3 = ttk.Frame(frm_pylon)
        row3.pack(fill=tk.X, pady=2)
        ttk.Label(row3, text="ΔX (mm):", width=14).pack(side=tk.LEFT)
        self.entry_pylon_dx = ttk.Entry(row3, width=10)
        self.entry_pylon_dx.pack(side=tk.LEFT)

        row4 = ttk.Frame(frm_pylon)
        row4.pack(fill=tk.X, pady=2)
        ttk.Label(row4, text="ΔY (mm):", width=14).pack(side=tk.LEFT)
        self.entry_pylon_dy = ttk.Entry(row4, width=10)
        self.entry_pylon_dy.pack(side=tk.LEFT)

        ttk.Button(
            frm_pylon, text='Apply position (ΔX/ΔY)', command=self._apply_pylon_delta_position
        ).pack(fill=tk.X, pady=(4, 0))

        # --- Section Spécifications du panneau ---
        frm_panel = ttk.LabelFrame(content, text='🔆 Panel specifications', padding=6)
        frm_panel.pack(fill=tk.X, pady=4)

        def _mk_panel_row(label, value):
            row = ttk.Frame(frm_panel)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=label, width=20).pack(side=tk.LEFT)
            e = ttk.Entry(row, width=10)
            e.insert(0, str(value))
            e.pack(side=tk.LEFT)
            return e

        self.entry_panel_pmax = _mk_panel_row('Pmax (Wp):', getattr(self, "panel_pmax_w", 450.0))
        self.entry_panel_efficiency = _mk_panel_row('STC efficiency (%):', getattr(self, "panel_efficiency_pct", 22.0))
        self.entry_panel_temp_coeff = _mk_panel_row('Pmax temperature coefficient (%/°C):', getattr(self, "panel_temp_coeff_pct", -0.30))
        self.entry_panel_noct = _mk_panel_row("NOCT (°C):", getattr(self, "panel_noct_c", 45.0))
        # --- Section Calcul solaire ---
        frm_solar = ttk.LabelFrame(content, text='☀️ Sun position', padding=6)
        frm_solar.pack(fill=tk.X, pady=4)

        def _mk_row(parent, label, width=10):
            row = ttk.Frame(parent)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=label, width=14).pack(side=tk.LEFT)
            e = ttk.Entry(row, width=width)
            e.pack(side=tk.LEFT)
            return e

        self.entry_solar_lat = _mk_row(frm_solar, "Latitude (°):")
        self.entry_solar_lat.insert(0, str(self.solar_latitude))

        self.entry_solar_lon = _mk_row(frm_solar, "Longitude (°):")
        self.entry_solar_lon.insert(0, str(self.solar_longitude))

        row_date = ttk.Frame(frm_solar)
        row_date.pack(fill=tk.X, pady=2)
        ttk.Label(row_date, text='Day / month:', width=14).pack(side=tk.LEFT)
        self.entry_solar_day = ttk.Entry(row_date, width=4)
        self.entry_solar_day.insert(0, str(self.solar_day))
        self.entry_solar_day.pack(side=tk.LEFT)
        ttk.Label(row_date, text="/").pack(side=tk.LEFT, padx=2)
        self.entry_solar_month = ttk.Entry(row_date, width=4)
        self.entry_solar_month.insert(0, str(self.solar_month))
        self.entry_solar_month.pack(side=tk.LEFT)

        self.entry_solar_hour = _mk_row(frm_solar, 'Local time:')
        self.entry_solar_hour.insert(0, self._decimal_hour_to_hhmm(self.solar_hour))

        # Curseur horaire : permet de déplacer l'heure sans retaper la valeur.
        row_slider = ttk.Frame(frm_solar)
        row_slider.pack(fill=tk.X, pady=(4, 2))
        ttk.Label(row_slider, text='Time:').pack(side=tk.LEFT)
        self.shadow_hour_var = tk.DoubleVar(value=float(self.solar_hour))
        self.shadow_hour_scale = ttk.Scale(
            row_slider, from_=0.0, to=23.75, variable=self.shadow_hour_var,
            command=self._on_shadow_hour_slider
        )
        self.shadow_hour_scale.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.lbl_shadow_hour = ttk.Label(row_slider, text=self._decimal_hour_to_hhmm(self.solar_hour), width=7)
        self.lbl_shadow_hour.pack(side=tk.RIGHT)

        self.entry_solar_utc = _mk_row(frm_solar, 'Time zone (UTC+):')
        self.entry_solar_utc.insert(0, str(self.solar_utc_offset))

        self.entry_north_offset = _mk_row(frm_solar, 'North (° / top):')
        self.entry_north_offset.insert(0, str(self.north_offset_deg))

        self.lbl_solar_result = ttk.Label(
            frm_solar, text='Azimuth / elevation: —', font=("Arial", 10, "bold"),
            foreground="#555555", justify=tk.LEFT, wraplength=260
        )
        self.lbl_solar_result.pack(anchor="w", pady=(6, 0))

        self.lbl_shadow_impact = ttk.Label(frm_solar, text='Affected panels: —',
                                           font=('Arial', 11, 'bold'), foreground='#B71C1C',
                                           wraplength=260)
        self.lbl_shadow_impact.pack(anchor='w', pady=(5, 0))

        # --- Section Hauteurs de zones ---
        frm_zones = ttk.LabelFrame(content, text='🔲 Zone heights', padding=6)
        frm_zones.pack(fill=tk.BOTH, expand=True, pady=4)

        self.lst_shadow_zones = tk.Listbox(frm_zones, height=6)
        self.lst_shadow_zones.pack(fill=tk.BOTH, expand=True, pady=(0, 4))
        self.lst_shadow_zones.bind("<<ListboxSelect>>", self._on_shadow_zone_selected)

        row_h = ttk.Frame(frm_zones)
        row_h.pack(fill=tk.X)
        ttk.Label(row_h, text='Height (mm):').pack(side=tk.LEFT)
        self.entry_zone_height_shadow = ttk.Entry(row_h, width=10)
        self.entry_zone_height_shadow.pack(side=tk.LEFT, padx=4)
        ttk.Button(row_h, text='Apply', command=self._apply_shadow_zone_height).pack(side=tk.LEFT)

        # --- Légende ---
        frm_legend = ttk.LabelFrame(content, text='Legend', padding=6)
        frm_legend.pack(fill=tk.X, pady=4)
        for color, label in [
            ("#FFF59D", 'Unshaded area'),
            ("#37474F", 'Shaded area'),
        ]:
            row = tk.Frame(frm_legend)
            row.pack(fill=tk.X, pady=1)
            tk.Frame(row, bg=color, width=14, height=14, relief="solid", bd=1).pack(side=tk.LEFT, padx=(0, 6))
            ttk.Label(row, text=label, font=("Arial", 8)).pack(side=tk.LEFT)

        for entry in (self.entry_pylon_height, self.entry_pylon_width, self.entry_pylon_opacity,
                      self.entry_solar_lat, self.entry_solar_lon, self.entry_solar_day,
                      self.entry_solar_month, self.entry_solar_hour, self.entry_solar_utc,
                      self.entry_north_offset, self.entry_panel_pmax,
                      self.entry_panel_efficiency, self.entry_panel_temp_coeff,
                      self.entry_panel_noct):
            entry.bind('<KeyRelease>', self._schedule_shadow_recompute)
            entry.bind('<FocusOut>', self._schedule_shadow_recompute)
            entry.bind('<Return>', self._schedule_shadow_recompute)

    def _toggle_shadow_params_panel(self):
        if self.side_panel_shadow.winfo_ismapped():
            self.side_panel_shadow.pack_forget()
        else:
            self.side_panel_shadow.pack(side=tk.LEFT, fill=tk.Y)
            self._refresh_shadow_zone_list()

    def _activate_place_pylon_mode(self):
        if not self.roof_pil_img:
            messagebox.showwarning('Warning', 'Load a roof image first.')
            return
        self.shadow_mode = "place_pylon"
        self.lbl_shadow_status.config(text='Click image to place the obstacle…')

    def _activate_place_ref_mode(self):
        if not self.roof_pil_img:
            messagebox.showwarning('Warning', 'Load a roof image first.')
            return
        self.shadow_mode = "place_ref"
        self.lbl_shadow_status.config(text='Click image to set the reference point…')

    def _clear_pylon(self):
        self.pylon_img_pos = None
        self.pylon_ref_img_pos = None
        self.shadow_result = {
            "elevation": None, "azimuth": None, "shadowed": set(),
            "shadow_pct": {}, "shadow_polygons": [], "segments": [], "message": None
        }
        self._update_shadow_delta_entries()
        self._update_shadow_status_label()
        self.draw_grid()

    def _update_shadow_delta_entries(self):
        if not hasattr(self, "entry_pylon_dx"):
            return
        self.entry_pylon_dx.delete(0, tk.END)
        self.entry_pylon_dy.delete(0, tk.END)
        if self.pylon_img_pos and self.pylon_ref_img_pos and self.px_per_mm > 0:
            dx_mm = (self.pylon_img_pos[0] - self.pylon_ref_img_pos[0]) / self.px_per_mm
            dy_mm = (self.pylon_img_pos[1] - self.pylon_ref_img_pos[1]) / self.px_per_mm
            self.entry_pylon_dx.insert(0, f"{dx_mm:.0f}")
            self.entry_pylon_dy.insert(0, f"{dy_mm:.0f}")

    def _apply_pylon_delta_position(self):
        if not self.pylon_ref_img_pos:
            messagebox.showwarning('Warning', 'Set a reference point first (click the image).')
            return
        if self.px_per_mm <= 0:
            messagebox.showwarning('Warning', 'Calibrate the scale in Installation area first.')
            return
        try:
            dx_mm = float(self.entry_pylon_dx.get())
            dy_mm = float(self.entry_pylon_dy.get())
        except ValueError:
            messagebox.showerror('Error', 'ΔX and ΔY must be numbers.')
            return
        rx, ry = self.pylon_ref_img_pos
        self.pylon_img_pos = (rx + dx_mm * self.px_per_mm, ry + dy_mm * self.px_per_mm)
        self._recompute_shadow()
        self.draw_grid()

    def _refresh_shadow_zone_list(self):
        if not hasattr(self, "lst_shadow_zones"):
            return
        self.lst_shadow_zones.delete(0, tk.END)
        for z in self.roof_zones:
            h = z.get("z_mm", 0.0)
            self.lst_shadow_zones.insert(tk.END, f"Zone {z['id']} — height: {h:.0f} mm")

    def _on_shadow_zone_selected(self, event):
        sel = self.lst_shadow_zones.curselection()
        if not sel:
            return
        idx = sel[0]
        if 0 <= idx < len(self.roof_zones):
            self.active_shadow_zone_idx = idx
            h = self.roof_zones[idx].get("z_mm", 0.0)
            self.entry_zone_height_shadow.delete(0, tk.END)
            self.entry_zone_height_shadow.insert(0, f"{h:.0f}")

    def _apply_shadow_zone_height(self):
        if self.active_shadow_zone_idx is None or not (0 <= self.active_shadow_zone_idx < len(self.roof_zones)):
            messagebox.showwarning('Warning', 'Select a zone from the list first.')
            return
        try:
            h_mm = float(self.entry_zone_height_shadow.get())
        except ValueError:
            messagebox.showerror('Error', 'Height must be a number.')
            return
        self.roof_zones[self.active_shadow_zone_idx]["z_mm"] = h_mm
        self._refresh_shadow_zone_list()
        self.lst_shadow_zones.select_set(self.active_shadow_zone_idx)
        self._recompute_shadow()
        self.draw_grid()

    @staticmethod
    def _decimal_hour_to_hhmm(hour):
        total_minutes = max(0, min(1440, int(round(float(hour) * 60))))
        hh, mm = divmod(total_minutes, 60)
        return f"{hh:02d}:{mm:02d}"

    @staticmethod
    def _hhmm_to_decimal_hour(value):
        value = value.strip()
        if ":" not in value:
            return float(value)
        hh, mm = map(int, value.split(":", 1))
        if not (0 <= hh <= 24 and 0 <= mm < 60) or (hh == 24 and mm != 0):
            raise ValueError('Invalid time')
        return hh + mm / 60.0

    def _on_shadow_hour_slider(self, value):
        """Synchronise le curseur avec l'heure solaire locale et recalcule immédiatement."""
        if getattr(self, '_updating_shadow_settings', False):
            return
        try:
            hour = max(0.0, min(23.75, float(value)))
        except (TypeError, ValueError):
            return
        self.solar_hour = round(hour * 4) / 4.0
        if hasattr(self, "entry_solar_hour"):
            self.entry_solar_hour.delete(0, tk.END)
            self.entry_solar_hour.insert(0, self._decimal_hour_to_hhmm(self.solar_hour))
        if hasattr(self, "lbl_shadow_hour"):
            self.lbl_shadow_hour.config(text=self._decimal_hour_to_hhmm(self.solar_hour))
        if self.pylon_img_pos is not None and self.px_per_mm > 0:
            self._schedule_shadow_recompute()

    def _schedule_shadow_recompute(self, event=None):
        if getattr(self, '_updating_shadow_settings', False):
            return
        job = getattr(self, '_shadow_recompute_job', None)
        if job is not None:
            self.root.after_cancel(job)
        self._shadow_recompute_job = self.root.after(250, self._auto_recompute_shadow)

    def _auto_recompute_shadow(self):
        self._shadow_recompute_job = None
        if not self._read_shadow_params_from_entries(show_errors=False):
            return
        self._recompute_shadow()
        if self._get_active_tab_index() == 5:
            self.draw_grid()

    def _read_shadow_params_from_entries(self, show_errors=True):
        """Lit les entrées du panneau latéral et met à jour les paramètres. Renvoie True si succès."""
        if not hasattr(self, "entry_pylon_height"):
            return True
        try:
            import datetime as dt
            values = {
                'pylon_height_mm': float(self.entry_pylon_height.get()),
                'pylon_width_mm': float(self.entry_pylon_width.get()),
                'pylon_opacity': float(self.entry_pylon_opacity.get()) / 100.0,
                'solar_latitude': float(self.entry_solar_lat.get()),
                'solar_longitude': float(self.entry_solar_lon.get()),
                'solar_day': int(self.entry_solar_day.get()),
                'solar_month': int(self.entry_solar_month.get()),
                'solar_hour': self._hhmm_to_decimal_hour(self.entry_solar_hour.get()),
                'solar_utc_offset': float(self.entry_solar_utc.get()),
                'north_offset_deg': float(self.entry_north_offset.get()),
                'panel_pmax_w': float(self.entry_panel_pmax.get()),
                'panel_efficiency_pct': float(self.entry_panel_efficiency.get()),
                'panel_temp_coeff_pct': float(self.entry_panel_temp_coeff.get()),
                'panel_noct_c': float(self.entry_panel_noct.get()),
            }
            dt.date(2024, values['solar_month'], values['solar_day'])
            if (not all(math.isfinite(v) for v in values.values())
                    or values['pylon_height_mm'] <= 0 or values['pylon_width_mm'] <= 0
                    or not 0 <= values['pylon_opacity'] <= 1
                    or not -90 <= values['solar_latitude'] <= 90
                    or not -180 <= values['solar_longitude'] <= 180
                    or not 0 <= values['solar_hour'] <= 23.75
                    or values['panel_pmax_w'] <= 0
                    or not 0 < values['panel_efficiency_pct'] <= 100
                    or values['panel_noct_c'] <= 0):
                raise ValueError('Invalid shadow settings')
            self._updating_shadow_settings = True
            for name, value in values.items():
                setattr(self, name, value)
            if hasattr(self, 'shadow_hour_var'):
                self.shadow_hour_var.set(self.solar_hour)
            if hasattr(self, 'lbl_shadow_hour'):
                self.lbl_shadow_hour.config(text=self._decimal_hour_to_hhmm(self.solar_hour))
        except (ValueError, OverflowError):
            if show_errors:
                messagebox.showerror('Error', 'Check the entered values (numbers expected).')
            return False
        finally:
            self._updating_shadow_settings = False
        return True

    def _update_shadow_status_label(self):
        if not hasattr(self, "lbl_shadow_status"):
            return
        if self.pylon_img_pos is None:
            self.lbl_shadow_status.config(text='Obstacle not placed.')
            if hasattr(self, 'lbl_shadow_impact'):
                self.lbl_shadow_impact.config(text='Affected panels: —')
            if hasattr(self, 'lbl_solar_result'):
                self.lbl_solar_result.config(text='Azimuth / elevation: —')
            return
        res = self.shadow_result
        if res.get("message"):
            self.lbl_shadow_status.config(text=res["message"])
        elif res.get("elevation") is not None:
            self.lbl_shadow_status.config(
                text=f"Azimuth {res['azimuth']:.0f}° / Elevation {res['elevation']:.1f}° — "
                     f"{len(res.get('shadowed', set()))} panel(s) affected by shadow"
            )
        else:
            self.lbl_shadow_status.config(text='Obstacle placed — shadow updates automatically.')

        if hasattr(self, "lbl_solar_result"):
            if res.get("elevation") is not None:
                max_pct = max(res.get("shadow_pct", {}).values(), default=0.0)
                self.lbl_solar_result.config(
                    text=f"Azimuth: {res['azimuth']:.1f}°   Elevation: {res['elevation']:.1f}°\n"
                         f"{len(res.get('shadowed', set()))} panel(s) affected — max {max_pct:.1f}% on one panel"
                         + (f"\n{res['message']}" if res.get("message") else "")
                )
            else:
                self.lbl_solar_result.config(text=res.get("message") or 'Azimuth / elevation: —')
        if hasattr(self, 'lbl_shadow_impact'):
            pct = max(res.get('shadow_pct', {}).values(), default=0.0)
            self.lbl_shadow_impact.config(
                text=f"Affected: {len(res.get('shadowed', set()))} panels  |  Maximum shade: {pct:.1f}%")

    # ========================================================
    # ZONE PRINCIPALE (CANVAS + PANNEAU LATÉRAL STRINGING)
    # ========================================================

    def _recompute_shadow(self):
        """Recalcule la position solaire et le % d'ombre de chaque panneau."""
        result = {
            "elevation": None, "azimuth": None, "shadowed": set(),
            "shadow_pct": {}, "shadow_polygons": [], "segments": [], "message": None
        }

        if self.pylon_img_pos is None and not getattr(self,'model_settings',{}).get('shadow_obstacles'):
            result["message"] = 'Place the obstacle on the image first.'
            self.shadow_result = result
            self._update_shadow_status_label()
            return result

        if self.px_per_mm <= 0:
            result["message"] = 'Calibrate the scale in Installation area first.'
            self.shadow_result = result
            self._update_shadow_status_label()
            return result

        elevation, azimuth = self._compute_solar_position(
            self.solar_latitude, self.solar_longitude,
            self.solar_day, self.solar_month, self.solar_hour, self.solar_utc_offset
        )
        result["elevation"], result["azimuth"] = elevation, azimuth

        if elevation <= 0.1:
            result["message"] = 'Sun below horizon: no cast shadow.'
            self.shadow_result = result
            self._update_shadow_status_label()
            return result

        shadow_pct, shadow_polygons, geometries = self._calculate_shadow_percentages(
            elevation, azimuth
        )
        result["shadow_pct"] = shadow_pct
        result["shadow_polygons"] = shadow_polygons
        result["segments"] = [
            (g["start"][0], g["start"][1], g["end"][0], g["end"][1])
            for g in geometries
        ]
        result["shadowed"] = {c for c, pct in shadow_pct.items() if pct > 0.01}

        self.shadow_result = result
        self._update_shadow_status_label()
        return result

    # ========================================================
    # ÉDITION ET PERSISTANCE MANUELLE DES STRINGS
