"""Position solaire, irradiance ciel clair, puissance/energie des panneaux, agregation par string."""

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



class ShadowEnergyMixin:
    def _get_clear_sky_irradiance(self, elevation_deg):
        """
        Estime le DNI (irradiance normale directe) en W/m².

        Ce modèle est volontairement simple. Il est conservé comme source
        solaire interne à la simulation; l'énergie électrique est ensuite
        calculée avec Pmax du module et l'irradiance incidente sur son plan.
        """
        if elevation_deg <= 0.5:
            return 0.0

        I_ext = 1367.0
        tau = 0.7
        zenith_rad = math.radians(90.0 - elevation_deg)
        cos_z = math.cos(zenith_rad)
        if cos_z < 0.01:
            return 0.0
        air_mass = 1.0 / cos_z
        return I_ext * (tau ** (air_mass ** 0.675))

    def _get_clear_sky_poa_irradiance(self, elevation_deg, solar_azimuth_deg, panel_coord=None):
        """
        Convertit le DNI simplifié en irradiance approximative sur le plan du module.

        POA = direct sur le plan + diffus isotrope + albédo simplifié.
        Azimuts: 0=N, 90=E, 180=S, 270=O; inclinaison 0=horizontale.
        """
        dni = self._get_clear_sky_irradiance(elevation_deg)
        if dni <= 0.0:
            return 0.0

        orientation = self.panel_orientations.get(panel_coord, {}) if panel_coord is not None else {}
        beta = math.radians(float(orientation.get("tilt_deg", self.panel_tilt_deg)))
        gamma_p = math.radians(float(orientation.get("azimuth_deg", self.panel_azimuth_deg)))
        gamma_s = math.radians(float(solar_azimuth_deg))
        elev = math.radians(float(elevation_deg))

        # Cosinus de l'angle d'incidence sur le plan incliné.
        cos_inc = (
            math.sin(elev) * math.cos(beta)
            + math.cos(elev) * math.sin(beta) * math.cos(gamma_s - gamma_p)
        )
        cos_inc = max(0.0, min(1.0, cos_inc))

        direct_poa = dni * cos_inc

        # Diffus isotrope très simplifié à partir du DNI.
        diffuse_horizontal = 0.12 * dni * max(0.0, math.sin(elev))
        diffuse_poa = diffuse_horizontal * (1.0 + math.cos(beta)) / 2.0

        # Albédo sol = 0.2 par défaut.
        ground_albedo = 0.20
        global_horizontal = dni * max(0.0, math.sin(elev)) + diffuse_horizontal
        albedo_poa = global_horizontal * ground_albedo * (1.0 - math.cos(beta)) / 2.0

        return max(0.0, direct_poa + diffuse_poa + albedo_poa)

    def _estimate_cell_temperature(self, poa_irradiance):
        """Température cellule estimée par NOCT, sans données météo réelles."""
        return 20.0 + (float(self.panel_noct_c) - 20.0) * (poa_irradiance / 800.0)

    def _estimate_panel_power_w(self, poa_irradiance, shaded_fraction=0.0):
        """
        Puissance électrique estimée du panneau à partir de Pmax STC.

        On applique d'abord la réduction d'irradiance due à l'ombre, puis la
        correction de température de Pmax. C'est un modèle linéaire en courant
        et non une simulation I-V complète. Le mode bypass_estimate applique
        une perte discrète conservatrice selon le nombre de groupes déclaré.
        """
        G = max(0.0, float(poa_irradiance))
        from shading_models import attenuation
        shade = attenuation(float(shaded_fraction),getattr(self,'model_settings',{}))
        G_effective = G * (1.0 - shade)
        if G_effective <= 0.0:
            return 0.0

        t_cell = self._estimate_cell_temperature(G_effective)
        temp_delta = t_cell - 25.0
        temp_factor = 1.0 + (float(self.panel_temp_coeff_pct) / 100.0) * temp_delta
        temp_factor = max(0.0, temp_factor)

        # Mise à l'échelle de Pmax STC (1000 W/m², cellule 25 °C).
        return max(0.0, float(self.panel_pmax_w) * (G_effective / 1000.0) * temp_factor)

    def _panel_energy_step(self, poa_irradiance, shaded_fraction, dt_hours):
        """Retourne (énergie idéale Wh, énergie ombrée Wh, perte Wh)."""
        p_ideal = self._estimate_panel_power_w(poa_irradiance, 0.0)
        p_shaded = self._estimate_panel_power_w(poa_irradiance, shaded_fraction)
        e_ideal = p_ideal * dt_hours
        e_shaded = p_shaded * dt_hours
        return e_ideal, e_shaded, max(0.0, e_ideal - e_shaded)

    def _summarize_string_group(self, string_id, members):
        """Agrège les résultats panneau (dict issus de `results`) d'une string."""
        s_pot = sum(r["energy_pot_wh"] for r in members)
        s_lost = sum(r["energy_lost_wh"] for r in members)
        s_loss_pct = (s_lost / s_pot * 100.0) if s_pot > 0 else 0.0
        worst = max(members, key=lambda r: r["loss_pct"])
        best = min(members, key=lambda r: r["loss_pct"])
        n_shaded = sum(1 for r in members if r["loss_pct"] > 1.0)
        return {
            "string_id": string_id,
            "n_panels": len(members),
            "n_panels_shaded": n_shaded,
            "energy_pot_wh": s_pot,
            "energy_lost_wh": s_lost,
            "loss_pct": s_loss_pct,
            "worst_panel": worst["panel"],
            "max_panel_loss_pct": worst["loss_pct"],
            "best_panel": best["panel"],
            "min_panel_loss_pct": best["loss_pct"],
            # Écart intra-string : une string étant câblée en série, sa
            # production réelle colle au comportement du panneau le plus
            # ombragé (limitation de courant / diodes bypass). Un spread
            # élevé signale un risque de mismatch électrique, même quand
            # la perte moyenne de la string reste modérée — c'est le
            # signal le plus utile pour repenser le découpage en strings.
            "spread_pct": worst["loss_pct"] - best["loss_pct"],
        }

    def _aggregate_shadow_results_by_string(self, results):
        """Regroupe les résultats de simulation par string électrique.

        Ne modélise pas les diodes bypass (le calcul par panneau reste une
        estimation linéaire, cf. `_estimate_panel_power_w`) mais agrège les
        pertes déjà calculées à l'échelle de la string pour repérer les
        chaînes les plus touchées et détecter les déséquilibres internes
        utiles à un rework du layout / du plan de câblage.
        """
        coord_to_result = {r["coord"]: r for r in results}
        assigned_coords = set()
        string_results = []

        strings_dict = getattr(self, "strings", {}) or {}
        for s_id in self._get_sorted_string_keys() if hasattr(self, "_get_sorted_string_keys") else strings_dict.keys():
            coords_list = strings_dict.get(s_id, [])
            members = [coord_to_result[c] for c in coords_list if c in coord_to_result]
            assigned_coords.update(c for c in coords_list if c in coord_to_result)
            if not members:
                continue
            string_results.append(self._summarize_string_group(s_id, members))

        unassigned = [r for c, r in coord_to_result.items() if c not in assigned_coords]
        if unassigned:
            string_results.append(
                self._summarize_string_group('⚠ Not assigned to a string', unassigned)
            )

        string_results.sort(key=lambda s: s["loss_pct"], reverse=True)
        return string_results

    def _compute_solar_position(self, lat_deg, lon_deg, day, month, hour_decimal, utc_offset, year=2024):
        """Calcule l'élévation et l'azimut solaire avec haute précision (Spencer/NOAA)."""
        import datetime as _dt
        try:
            d0 = _dt.date(year, 1, 1)
            d1 = _dt.date(year, int(month), int(day))
            doy = (d1 - d0).days + 1
        except Exception:
            doy = 172

        # Fraction de l'année en radians
        year_days=(_dt.date(year+1,1,1)-_dt.date(year,1,1)).days
        gamma = 2 * math.pi / year_days * (doy - 1 + (hour_decimal - 12) / 24)

        # Équation du temps (minutes) - Spencer (1971)
        eqtime = 229.18 * (
            0.000075 + 0.001868 * math.cos(gamma) - 0.032077 * math.sin(gamma)
            - 0.014615 * math.cos(2 * gamma) - 0.040849 * math.sin(2 * gamma)
        )
        
        # Déclinaison solaire (radians) - Spencer (1971)
        decl = (
            0.006918 - 0.399912 * math.cos(gamma) + 0.070257 * math.sin(gamma)
            - 0.006758 * math.cos(2 * gamma) + 0.000907 * math.sin(2 * gamma)
            - 0.002697 * math.cos(3 * gamma) + 0.00148 * math.sin(3 * gamma)
        )

        # Temps solaire vrai
        time_offset = eqtime + 4 * lon_deg - 60 * utc_offset
        true_solar_time = hour_decimal * 60 + time_offset 
        
        ha_deg = (true_solar_time / 4) - 180
        ha_rad = math.radians(ha_deg)
        lat_rad = math.radians(lat_deg)

        # Élévation géométrique
        sin_elev = (math.sin(lat_rad) * math.sin(decl) +
                    math.cos(lat_rad) * math.cos(decl) * math.cos(ha_rad))
        sin_elev = max(-1.0, min(1.0, sin_elev))
        elev_rad = math.asin(sin_elev)
        elev_deg = math.degrees(elev_rad)

        # Correction de la réfraction atmosphérique (Saemundsson, 1986)
        if elev_deg > -0.85:
            ref_arcmin = 1.02 / math.tan(math.radians(elev_deg + 10.3 / (elev_deg + 5.11)))
            elev_deg += ref_arcmin / 60.0
        
        # Azimut (depuis le Nord, horaire)
        denom = math.cos(elev_rad) * math.cos(lat_rad)
        if abs(denom) > 1e-7:
            cos_az = (math.sin(decl) - sin_elev * math.sin(lat_rad)) / denom
            cos_az = max(-1.0, min(1.0, cos_az))
            az = math.degrees(math.acos(cos_az))
            if ha_deg > 0:
                az = 360.0 - az
        else:
            az = 180.0 if lat_deg > 0 else 0.0

        return elev_deg, az
