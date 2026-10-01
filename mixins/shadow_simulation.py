"""Fenetre de simulation temporelle d'ombrage (multi-jours, heatmap, export)."""

import calendar
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


# Dégradé vert → jaune → rouge (3 points de contrôle, sinon le milieu du
# dégradé vert→rouge direct est un brun terne et non un jaune).
_HEAT_STOPS = ((46, 204, 113), (255, 214, 10), (229, 28, 28))


def _heat_rgb(t):
    """Couleur (r, g, b) du dégradé pour t dans [0, 1]."""
    t = max(0.0, min(1.0, float(t)))
    seg = 0 if t < 0.5 else 1
    u = (t - 0.5 * seg) / 0.5
    a, b = _HEAT_STOPS[seg], _HEAT_STOPS[seg + 1]
    return tuple(int(round(a[i] + (b[i] - a[i]) * u)) for i in range(3))


def _rgb_hex(rgb):
    return "#{:02X}{:02X}{:02X}".format(*rgb)


def _text_on(rgb):
    """Texte sombre ou blanc selon la luminance du fond."""
    lum = 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]
    return "#263238" if lum > 150 else "white"


def _nice_ticks(vmax, n=5):
    """Graduations « rondes » (1, 2, 2.5, 5 × 10^k) couvrant [0, vmax]."""
    vmax = max(float(vmax), 1e-9)
    raw = vmax / max(1, n)
    mag = 10 ** math.floor(math.log10(raw))
    step = mag
    for m in (1, 2, 2.5, 5, 10):
        step = m * mag
        if step >= raw:
            break
    top = math.ceil(vmax / step - 1e-9) * step
    count = int(round(top / step))
    return step, [i * step for i in range(count + 1)]


# Abréviations fixes (indépendantes de la locale du système).
_MONTH_ABBR = ('jan.', 'feb.', 'mar.', 'apr.', 'may', 'jun.',
               'jul.', 'aug.', 'sep.', 'oct.', 'nov.', 'dec.')
_STEP_UNITS = {
    'Years': 'year', 'Months': 'month', 'Weeks': 'week', 'Days': 'day',
    'Hours': 'hour', 'Minutes': 'minute', 'Seconds': 'second',
}
_UNIT_SECONDS = {'week': 7 * 86400, 'day': 86400, 'hour': 3600,
                 'minute': 60, 'second': 1}
_CHART_MAX_PERIODS = 2000
_CHART_METRICS = {
    'Produced energy': ('produced',),
    'Energy lost': ('lost',),
    'Unshaded potential': ('potential',),
    'Produced + lost (stacked)': ('produced', 'lost'),
}
_CHART_PALETTES = {
    'produced': {'fill': '#43A047', 'edge': '#2E7D32', 'cap': '#A5D6A7',
                 'area': '#E8F5E9', 'name': 'Produced'},
    'lost': {'fill': '#E53935', 'edge': '#C62828', 'cap': '#EF9A9A',
             'area': '#FDECEA', 'name': 'Lost'},
    'potential': {'fill': '#1E88E5', 'edge': '#1565C0', 'cap': '#90CAF9',
                  'area': '#E3F2FD', 'name': 'Unshaded potential'},
}


class ShadowSimulationMixin:
    def _open_shadow_simulation(self):
        """Ouvre la simulation temporelle d'ombrage avec intégration par intervalles.

        Le pourcentage moyen est une moyenne temporelle pondérée. Les heures
        équivalentes sont l'intégrale de pct/100 sur toute la plage demandée.
        Le milieu de chaque intervalle sert à l'intégration (règle du point
        milieu).
        """
        if not self._read_shadow_params_from_entries():
            return
        if self.pylon_img_pos is None:
            messagebox.showwarning('Warning', 'Place the obstacle on the image first.')
            return
        if self.px_per_mm <= 0:
            messagebox.showwarning('Warning', 'Calibrate the scale first.')
            return

        win = tk.Toplevel(self.root)
        win.title('Shadow simulation — multiple days')
        self._center_window(win, 980, 700)
        win.transient(self.root)

        # ------------------------------------------------------------
        # Conteneur scrollable : tout le contenu (y compris les boutons
        # du bas) est placé dans un canvas avec une scrollbar verticale,
        # pour rester accessible même sur un écran plus petit que 700px.
        # ------------------------------------------------------------
        outer = ttk.Frame(win)
        outer.pack(fill=tk.BOTH, expand=True)

        outer_canvas = tk.Canvas(outer, borderwidth=0, highlightthickness=0)
        outer_vscroll = ttk.Scrollbar(
            outer, orient=tk.VERTICAL, command=outer_canvas.yview
        )
        outer_canvas.configure(yscrollcommand=outer_vscroll.set)
        outer_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        outer_vscroll.pack(side=tk.RIGHT, fill=tk.Y)

        frm = ttk.Frame(outer_canvas, padding=12)
        frm_window_id = outer_canvas.create_window((0, 0), window=frm, anchor="nw")

        def _on_frm_configure(event=None):
            outer_canvas.configure(scrollregion=outer_canvas.bbox("all"))

        def _on_outer_canvas_configure(event):
            # Le frame interne suit la largeur du canvas.
            outer_canvas.itemconfigure(frm_window_id, width=event.width)

        frm.bind("<Configure>", _on_frm_configure)
        outer_canvas.bind("<Configure>", _on_outer_canvas_configure)

        def _on_outer_mousewheel(event):
            if event.num == 4 or (hasattr(event, "delta") and event.delta > 0):
                outer_canvas.yview_scroll(-1, "units")
            else:
                outer_canvas.yview_scroll(1, "units")

        def _bind_outer_scroll(event=None):
            if sys.platform.startswith("linux"):
                outer_canvas.bind_all("<Button-4>", _on_outer_mousewheel)
                outer_canvas.bind_all("<Button-5>", _on_outer_mousewheel)
            else:
                outer_canvas.bind_all("<MouseWheel>", _on_outer_mousewheel)

        def _unbind_outer_scroll(event=None):
            # <Leave> est aussi émis en passant d'un widget enfant à un autre :
            # on ne débranche que si le curseur a réellement quitté la fenêtre.
            if event is not None and event.type == tk.EventType.Leave:
                try:
                    under = win.winfo_containing(event.x_root, event.y_root)
                except (KeyError, tk.TclError):
                    under = None
                if under is not None and under.winfo_toplevel() is win:
                    return
            if sys.platform.startswith("linux"):
                outer_canvas.unbind_all("<Button-4>")
                outer_canvas.unbind_all("<Button-5>")
            else:
                outer_canvas.unbind_all("<MouseWheel>")

        # Le scroll molette n'est actif que lorsque le curseur survole
        # la fenêtre de simulation (évite d'interférer avec le reste
        # de l'appli tant que la popup est ouverte).
        win.bind("<Enter>", _bind_outer_scroll)
        win.bind("<Leave>", _unbind_outer_scroll)
        win.bind("<Destroy>", _unbind_outer_scroll)

        ttk.Label(
            frm, text='Multi-day simulation', font=("Arial", 12, "bold")
        ).pack(anchor="w", pady=(0, 8))
        def mk_date_row(parent, label, day, month, year):
            row = ttk.Frame(parent); row.pack(fill=tk.X, pady=8)
            ttk.Label(row, text=label, width=22).pack(side=tk.LEFT)
            ed = ttk.Entry(row, width=4); ed.insert(0, str(day)); ed.pack(side=tk.LEFT)
            ttk.Label(row, text="/").pack(side=tk.LEFT, padx=2)
            em = ttk.Entry(row, width=4); em.insert(0, str(month)); em.pack(side=tk.LEFT)
            ttk.Label(row, text="/").pack(side=tk.LEFT, padx=2)
            ey = ttk.Entry(row, width=6); ey.insert(0, str(year)); ey.pack(side=tk.LEFT)
            return ed, em, ey

        # Années : par défaut l'année en cours (mémorisées d'une simulation à l'autre).
        import datetime as _dt0
        default_year = _dt0.date.today().year
        start_year = getattr(self, 'shadow_sim_start_year', None) or default_year
        end_year = getattr(self, 'shadow_sim_end_year', None) or start_year

        e_sd, e_sm, e_sy = mk_date_row(
            frm, 'Start (day/month/year)',
            self.shadow_sim_start_day, self.shadow_sim_start_month, start_year
        )
        e_ed, e_em, e_ey = mk_date_row(
            frm, 'End (day/month/year)',
            self.shadow_sim_end_day, self.shadow_sim_end_month, end_year
        )

        row = ttk.Frame(frm); row.pack(fill=tk.X, pady=8)
        ttk.Label(row, text='Time range', width=22).pack(side=tk.LEFT)
        e_sh = ttk.Entry(row, width=7); e_sh.insert(0, self._decimal_hour_to_hhmm(self.shadow_sim_start_hour)); e_sh.pack(side=tk.LEFT)
        ttk.Label(row, text=' to ').pack(side=tk.LEFT)
        e_eh = ttk.Entry(row, width=7); e_eh.insert(0, self._decimal_hour_to_hhmm(self.shadow_sim_end_hour)); e_eh.pack(side=tk.LEFT)

        row = ttk.Frame(frm); row.pack(fill=tk.X, pady=8)
        ttk.Label(row, text='Time step (min)', width=22).pack(side=tk.LEFT)
        e_step = ttk.Entry(row, width=7); e_step.insert(0, str(self.shadow_sim_step_min)); e_step.pack(side=tk.LEFT)

        ttk.Label(
            frm,
            text=f"Solar position: {self.solar_latitude:.5f}°, {self.solar_longitude:.5f}° — UTC{self.solar_utc_offset:+g}",
            font=("Arial", 8), foreground="#555555"
        ).pack(anchor="w", pady=(4, 2))

        progress = ttk.Progressbar(frm, mode="determinate")
        progress.pack(fill=tk.X, pady=(12, 5))
        status = ttk.Label(frm, text='Ready.')
        status.pack(anchor="w")

        summary_var = tk.StringVar(value='Total energy lost (all panels): —')
        ttk.Label(
            frm, textvariable=summary_var,
            font=("Arial", 13, "bold"), foreground="#B71C1C"
        ).pack(anchor="w", pady=(4, 0))

        stats_frame = ttk.Frame(frm)
        stats_frame.pack(fill=tk.X, pady=(6, 4))
        production_stat = tk.StringVar(value='Produced: —')
        potential_stat = tk.StringVar(value='Unshaded: —')
        lost_stat = tk.StringVar(value='Energy lost: —')
        for variable, color in ((production_stat, '#1B5E20'),
                                (potential_stat, '#1565C0'), (lost_stat, '#B71C1C')):
            ttk.Label(stats_frame, textvariable=variable, font=('Arial', 11, 'bold'),
                      foreground=color).pack(side=tk.LEFT, padx=(0, 24))

        # Vue synthétique du layout : chaque panneau est coloré selon
        # son ombrage moyen sur toute la période simulée.
        heatmap_frame = ttk.LabelFrame(
            frm, text='🌡️ Heatmap — shadow impact on the layout',
            padding=6
        )
        heatmap_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 6))

        heatmap_canvas = tk.Canvas(
            heatmap_frame, background="white", highlightthickness=1,
            highlightbackground="#BDBDBD", height=320
        )
        heatmap_vscroll = ttk.Scrollbar(
            heatmap_frame, orient=tk.VERTICAL, command=heatmap_canvas.yview
        )
        heatmap_hscroll = ttk.Scrollbar(
            heatmap_frame, orient=tk.HORIZONTAL, command=heatmap_canvas.xview
        )
        heatmap_canvas.configure(
            yscrollcommand=heatmap_vscroll.set,
            xscrollcommand=heatmap_hscroll.set
        )
        heatmap_canvas.grid(row=0, column=0, sticky="nsew")
        heatmap_canvas.bind('<ButtonPress-1>', lambda event: heatmap_canvas.scan_mark(event.x, event.y))
        heatmap_canvas.bind('<B1-Motion>', lambda event: heatmap_canvas.scan_dragto(event.x, event.y, gain=1))
        heatmap_vscroll.grid(row=0, column=1, sticky="ns")
        heatmap_hscroll.grid(row=1, column=0, sticky="ew")
        heatmap_frame.rowconfigure(0, weight=1)
        heatmap_frame.columnconfigure(0, weight=1)

        if not hasattr(self, "heatmap_zoom_level"):
            self.heatmap_zoom_level = 1.0

        def _on_heatmap_mousewheel(event):
            old_zoom = self.heatmap_zoom_level
            if event.num == 4 or (hasattr(event, 'delta') and event.delta > 0):
                self.heatmap_zoom_level = min(5.0, old_zoom * 1.1)
            else:
                self.heatmap_zoom_level = max(0.5, old_zoom / 1.1)
            
            if old_zoom != self.heatmap_zoom_level:
                # Store current results to redraw
                if self._shadow_current() and self.shadow_simulation_results.get("results"):
                    draw_simulation_heatmap(self.shadow_simulation_results["results"])
            # Empêche la molette de aussi faire défiler la fenêtre
            # englobante pendant qu'on zoome la heatmap.
            return "break"

        if sys.platform.startswith("linux"):
            heatmap_canvas.bind("<Button-4>", _on_heatmap_mousewheel)
            heatmap_canvas.bind("<Button-5>", _on_heatmap_mousewheel)
        else:
            heatmap_canvas.bind("<MouseWheel>", _on_heatmap_mousewheel)

        legend_frame = ttk.Frame(frm)
        legend_frame.pack(fill=tk.X, pady=(0, 4))
        ttk.Label(
            legend_frame,
            text='Green = low impact  |  Yellow = medium  |  Red = high  |  Wheel: zoom  |  Drag: pan'
        ).pack(side=tk.LEFT)

        def draw_simulation_heatmap(results):
            heatmap_canvas.delete("all")
            if not results:
                heatmap_canvas.create_text(
                    20, 20, anchor=tk.NW,
                    text='Run the simulation to display the heatmap.',
                    fill="#555555", font=("Arial", 10)
                )
                heatmap_canvas.configure(scrollregion=(0, 0, 600, 250))
                return

            by_coord = {tuple(r["coord"]): r for r in results if r.get("coord") is not None}
            h_zoom = self.heatmap_zoom_level

            # Calcul des bornes min/max des pertes pour l'échelle dynamique
            all_losses = [float(r.get("loss_pct", 0.0)) for r in results]
            min_loss = min(all_losses) if all_losses else 0.0
            max_loss = max(all_losses) if all_losses else 100.0
            loss_range = max_loss - min_loss
            if loss_range < 0.1: loss_range = 1.0

            def _heat_rgb_for(pct):
                # Échelle relative : vert pour le minimum de perte, rouge pour le maximum.
                return _heat_rgb((pct - min_loss) / loss_range)

            # Reuse the exact panel polygons from the main layout. This is important
            # for zones with a non-zero layout rotation: the previous heatmap rebuilt
            # axis-aligned rectangles and therefore displayed rotated zones incorrectly.
            shapes = []
            if self.roof_zones and self.px_per_mm > 0:
                self._recalculate_zone_grids()
                raw = []
                for coord in by_coord:
                    poly = self._panel_rect(coord)
                    if len(poly) >= 3:
                        raw.append((coord, poly))

                if raw:
                    all_points = [p for _, poly in raw for p in poly]
                    min_x_px = min(p[0] for p in all_points)
                    max_x_px = max(p[0] for p in all_points)
                    min_y_px = min(p[1] for p in all_points)
                    max_y_px = max(p[1] for p in all_points)
                    total_w_mm = (max_x_px - min_x_px) / self.px_per_mm
                    total_h_mm = (max_y_px - min_y_px) / self.px_per_mm
                    fit_scale = min(900.0 / max(1.0, total_w_mm), 600.0 / max(1.0, total_h_mm))
                    min_scale = max(22.0 / max(1.0, self.panel_width_mm), 35.0 / max(1.0, self.panel_height_mm))
                    max_scale = min(120.0 / max(1.0, self.panel_width_mm), 200.0 / max(1.0, self.panel_height_mm))
                    display_scale = max(min_scale, min(max_scale, fit_scale)) * h_zoom
                    px_to_display = display_scale / self.px_per_mm
                    for coord, poly in raw:
                        shown = [((x-min_x_px)*px_to_display+20, (y-min_y_px)*px_to_display+20) for x,y in poly]
                        shapes.append((coord, shown))
            else:
                coords = list(by_coord)
                min_r = min(r for r, _ in coords); max_r = max(r for r, _ in coords)
                min_c = min(c for _, c in coords); max_c = max(c for _, c in coords)
                num_rows = max(1, max_r-min_r+1); num_cols = max(1, max_c-min_c+1)
                cell_w = min(60, max(25, 900 // num_cols)) * h_zoom
                cell_h = min(90, max(40, 600 // num_rows)) * h_zoom
                for r,c in coords:
                    x1=(c-min_c)*cell_w+20; y1=(r-min_r)*cell_h+20
                    shapes.append(((r,c),[(x1,y1),(x1+cell_w-3,y1),(x1+cell_w-3,y1+cell_h-3),(x1,y1+cell_h-3)]))

            if not shapes:
                heatmap_canvas.create_text(20,20,anchor=tk.NW,text='No panels to display.',fill='#555555',font=('Arial',10))
                heatmap_canvas.configure(scrollregion=(0,0,600,250))
                return

            max_x = max(x for _, poly in shapes for x, _ in poly) + 30
            max_y = max(y for _, poly in shapes for _, y in poly) + 30

            # Draw the real panel polygons, including rotated installation zones.
            for coord, poly in shapes:
                item = by_coord[coord]
                pct = float(item.get('loss_pct',0.0))
                rgb = _heat_rgb_for(pct); fill = _rgb_hex(rgb); text_fill = _text_on(rgb)
                xs=[p[0] for p in poly]; ys=[p[1] for p in poly]
                cx=sum(xs)/len(xs); cy=sum(ys)/len(ys)
                block_name=self.panel_blocks.get(coord)
                outline=(self.blocks.get(block_name,{}).get('color','#455A64') if block_name else '#455A64')
                heatmap_canvas.create_polygon(*[v for pt in poly for v in pt],fill=fill,outline=outline,width=1)
                edges=[math.hypot(poly[(i+1)%len(poly)][0]-poly[i][0],poly[(i+1)%len(poly)][1]-poly[i][1]) for i in range(len(poly))]
                short_side=min(edges) if edges else 0
                fsize=max(4,min(8,int(short_side/3.2)))
                if short_side>14:
                    heatmap_canvas.create_text(cx,cy-(fsize+1),text=f"#{item['panel']}",fill=text_fill,font=('Arial',fsize,'bold'))
                    heatmap_canvas.create_text(cx,cy+fsize,text=f"{pct:.1f}%",fill=text_fill,font=('Arial',max(4,fsize-1),'bold'))
                elif short_side>7:
                    heatmap_canvas.create_text(cx,cy,text=f"{pct:.0f}%",fill=text_fill,font=('Arial',max(4,fsize),'bold'))

            # Échelle visuelle dynamique en bas à gauche.
            lx, ly, lw, lh = 10, max_y - 24, 220, 14
            for i in range(lw):
                heatmap_canvas.create_rectangle(
                    lx + i, ly, lx + i + 1, ly + lh,
                    fill=_rgb_hex(_heat_rgb(i / max(1, lw - 1))), outline=""
                )
            heatmap_canvas.create_text(lx, ly - 2, anchor=tk.SW, text=f"{min_loss:.1f}%", font=("Arial", 8))
            heatmap_canvas.create_text(lx + lw, ly - 2, anchor=tk.SE, text=f"{max_loss:.1f}%", font=("Arial", 8))

            heatmap_canvas.configure(scrollregion=(0, 0, max_x, max_y))

        def run():
            import datetime as _dt
            try:
                sd, sm, sy = int(e_sd.get()), int(e_sm.get()), int(e_sy.get())
                ed, em, ey = int(e_ed.get()), int(e_em.get()), int(e_ey.get())
                if not (1900 <= sy <= 2200 and 1900 <= ey <= 2200):
                    raise ValueError('Years must be between 1900 and 2200.')
                sh, eh = self._hhmm_to_decimal_hour(e_sh.get()), self._hhmm_to_decimal_hour(e_eh.get())
                step = int(e_step.get())

                start = _dt.date(sy, sm, sd)
                end = _dt.date(ey, em, ed)
                if end < start:
                    raise ValueError('End date is before start date.')
                if not (0.0 <= sh < 24.0 and 0.0 <= eh <= 24.0 and sh < eh):
                    raise ValueError('Invalid time range.')
                if step <= 0 or step > 1440:
                    raise ValueError('Invalid time step.')
            except Exception as exc:
                detail = str(exc) if isinstance(exc, ValueError) else ''
                messagebox.showerror(
                    'Error',
                    'Check the dates, time range and time step.'
                    + (f'\n\n{detail}' if detail else ''),
                    parent=win
                )
                return

            self.shadow_sim_start_day, self.shadow_sim_start_month = sd, sm
            self.shadow_sim_end_day, self.shadow_sim_end_month = ed, em
            self.shadow_sim_start_year, self.shadow_sim_end_year = sy, ey
            self.shadow_sim_start_hour, self.shadow_sim_end_hour = sh, eh
            self.shadow_sim_step_min = step

            coords = list(self.panels.keys())
            if not coords:
                messagebox.showwarning("Simulation", 'No panels in the layout.', parent=win)
                return

            intervals = []
            day = start
            while day <= end:
                base = _dt.datetime.combine(day, _dt.time())
                t0 = base + _dt.timedelta(minutes=sh * 60.0)
                t_end = base + _dt.timedelta(minutes=eh * 60.0)
                t = t0
                while t < t_end - _dt.timedelta(microseconds=1):
                    t_next = min(t + _dt.timedelta(minutes=step), t_end)
                    intervals.append((t, t_next))
                    t = t_next
                day += _dt.timedelta(days=1)

            if not intervals:
                messagebox.showwarning("Simulation", 'The selected hours contain no intervals.', parent=win)
                return

            total_work = len(intervals)
            if total_work * len(coords) > 3_000_000 and not messagebox.askyesno(
                    'Simulation',
                    f'This simulation covers {(end - start).days + 1} day(s): '
                    f'{total_work:,} intervals × {len(coords)} panel(s).\n'
                    'It may take a while. Continue?',
                    parent=win):
                return
            progress["maximum"] = max(1, total_work)
            run_btn.state(["!disabled"])
            
            from energy_engine import freeze_app
            from shadow_engine import calculate
            frozen=freeze_app(self);source_signature=self._shadow_signature()
            def complete(payload):
                if not win.winfo_exists():return
                run_btn.state(['!disabled'])
                if source_signature!=self._shadow_signature():
                    status.configure(text='Inputs changed. Run the simulation again.');return
                energy_lost,energy_potential,energy_shaded,timeline,interval_log=payload
                results = []
                for c in coords:
                    pot = energy_potential[c]
                    lost = energy_lost[c]
                    loss_pct = (lost / pot * 100.0) if pot > 0 else 0.0
                    results.append({
                        "coord": c,
                        "panel": self.panels[c],
                        "loss_pct": loss_pct,
                        "energy_lost_wh": lost,
                        "energy_pot_wh": pot,
                        "energy_shaded_wh": energy_shaded[c],
                    })

                results.sort(key=lambda x: x["panel"])

                total_lost_wh = sum(r["energy_lost_wh"] for r in results)
                total_pot_wh = sum(r["energy_pot_wh"] for r in results)
                total_loss_pct = (total_lost_wh / total_pot_wh * 100.0) if total_pot_wh > 0 else 0.0
                string_results = self._aggregate_shadow_results_by_string(results)

                self.shadow_source_signature=source_signature
                self.shadow_simulation_results = {
                    "results": results,
                    "string_results": string_results,
                    "total_lost_wh": total_lost_wh,
                    "total_pot_wh": total_pot_wh,
                    "total_loss_pct": total_loss_pct,
                    "timeline": timeline,
                    "intervals": interval_log,
                }

                progress["value"] = total_work
                status.config(text=f"Complete: {len(results)} panel(s) — {len(string_results)} string(s).")

                top_string_note = ""
                if string_results:
                    top = string_results[0]
                    top_string_note = (
                        f"  |  Most affected string: {top['string_id']} "
                        f"({top['loss_pct']:.1f}%, within-string spread {top['spread_pct']:.1f} pp)"
                    )
                production_stat.set(f"Produced: {sum(energy_shaded.values()) / 1000:.3f} kWh")
                potential_stat.set(f"Unshaded: {total_pot_wh / 1000:.3f} kWh")
                lost_stat.set(f"Energy lost: {total_lost_wh / 1000:.3f} kWh")
                summary_var.set(
                    f"Average electrical loss: {total_loss_pct:.2f}%"
                    f"{top_string_note}"
                )

                for item in tree.get_children():
                    tree.delete(item)
                for row_data in results:
                    tree.insert(
                        "", tk.END,
                        values=(
                            row_data["panel"],
                            f"{row_data['loss_pct']:.2f} %",
                            f"{row_data['energy_lost_wh']/1000.0:.3f} kWh",
                            f"{row_data['energy_pot_wh']/1000.0:.3f} kWh"
                        )
                    )

                for item in string_tree.get_children():
                    string_tree.delete(item)
                for s in string_results:
                    mismatch_flag = "⚠️" if s["spread_pct"] >= 15.0 else ""
                    string_tree.insert(
                        "", tk.END,
                        values=(
                            s["string_id"],
                            s["n_panels"],
                            f"{s['loss_pct']:.2f} %",
                            f"{s['energy_lost_wh']/1000.0:.3f} kWh",
                            f"#{s['worst_panel']} ({s['max_panel_loss_pct']:.1f} %)",
                            f"{mismatch_flag} {s['spread_pct']:.1f} pt".strip(),
                            s["n_panels_shaded"],
                        )
                    )

                draw_simulation_heatmap(results)
                export_btn.state(["!disabled"])
                chart_btn.state(["!disabled"])
            
            def update(done,total):
                if win.winfo_exists():
                    progress['value']=done;status.configure(text=f'Calculation: {done}/{total}')
            self._start_job(lambda report:calculate(frozen,intervals,report),complete,'Shade simulation',on_progress=update)

        tree_frame = ttk.Frame(frm)
        tree_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 6))
        tree = ttk.Treeview(
            tree_frame, columns=("panel", "loss", "energy_lost", "energy_pot"),
            show="headings", height=7
        )
        for col, title, width in [
            ("panel", "Panel", 90), ("loss", 'Energy loss (%)', 130),
            ("energy_lost", 'Energy lost', 120), ("energy_pot", 'Unshaded', 120)
        ]:
            tree.heading(col, text=title)
            tree.column(col, width=width, anchor="center")
        scroll = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # ------------------------------------------------------------
        # Table "Strings les plus touchées" : agrège les pertes par
        # string électrique et met en évidence l'écart intra-string
        # (indicateur de mismatch), utile pour repenser le découpage
        # du layout / le plan de câblage.
        # ------------------------------------------------------------
        string_frame = ttk.LabelFrame(
            frm, text='🔗 Most affected strings', padding=6
        )
        string_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 6))
        string_tree_frame = ttk.Frame(string_frame)
        string_tree_frame.pack(fill=tk.BOTH, expand=True)
        string_tree = ttk.Treeview(
            string_tree_frame,
            columns=("string", "n_panels", "loss", "energy_lost", "worst_panel", "spread", "n_shaded"),
            show="headings", height=5
        )
        for col, title, width in [
            ("string", "String", 130), ("n_panels", 'Panels', 70),
            ("loss", 'Average loss (%)', 120), ("energy_lost", 'Energy lost', 110),
            ("worst_panel", 'Most affected panel', 150), ("spread", 'Within-string spread', 130),
            ("n_shaded", 'Shaded panels', 110),
        ]:
            string_tree.heading(col, text=title)
            string_tree.column(col, width=width, anchor="center")
        string_scroll = ttk.Scrollbar(string_tree_frame, orient=tk.VERTICAL, command=string_tree.yview)
        string_tree.configure(yscrollcommand=string_scroll.set)
        string_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        string_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        def export_simulation():
            if not self._shadow_current():
                messagebox.showwarning('Simulation','Inputs changed. Run the simulation again.',parent=win);return
            if not self.shadow_simulation_results.get("results"):
                return
            path = filedialog.asksaveasfilename(
                parent=win, defaultextension=".csv",
                filetypes=[("CSV", "*.csv")]
            )
            if not path:
                return
            try:
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    w = csv.writer(f, delimiter=";")
                    w.writerow([
                        "Panel", 'Energy loss (%)',
                        'Electrical energy lost (kWh)', 'Unshaded production (kWh)'
                    ])
                    for r in self.shadow_simulation_results["results"]:
                        w.writerow([
                            r["panel"], f"{r['loss_pct']:.4f}",
                            f"{r['energy_lost_wh']/1000.0:.4f}",
                            f"{r['energy_pot_wh']/1000.0:.4f}"
                        ])
                    w.writerow([])
                    w.writerow([
                        "TOTAL", f"{self.shadow_simulation_results.get('total_loss_pct', 0.0):.4f}",
                        f"{self.shadow_simulation_results.get('total_lost_wh', 0.0)/1000.0:.4f}",
                        f"{self.shadow_simulation_results.get('total_pot_wh', 0.0)/1000.0:.4f}"
                    ])

                    w.writerow([])
                    w.writerow(['=== String analysis (descending loss) ==='])
                    w.writerow([
                        "String", 'Panel count', 'Average loss (%)', 'Energy lost (kWh)',
                        'Most affected panel', 'Worst panel loss (%)',
                        'Least affected panel', 'Least affected panel loss (%)',
                        'Within-string spread (pp)', 'Shaded panel count (>1%)'
                    ])
                    for s in self.shadow_simulation_results.get("string_results", []):
                        w.writerow([
                            s["string_id"], s["n_panels"], f"{s['loss_pct']:.4f}",
                            f"{s['energy_lost_wh']/1000.0:.4f}",
                            s["worst_panel"], f"{s['max_panel_loss_pct']:.4f}",
                            s["best_panel"], f"{s['min_panel_loss_pct']:.4f}",
                            f"{s['spread_pct']:.4f}", s["n_panels_shaded"]
                        ])
            except OSError as exc:
                messagebox.showerror("Export", f"Could not write the file:\n{exc}", parent=win)
                return
            messagebox.showinfo("Export", 'Electrical results exported as CSV.', parent=win)

        btns = ttk.Frame(frm); btns.pack(fill=tk.X, pady=(5, 0))
        run_btn = ttk.Button(btns, text='▶ Run simulation', command=run)
        run_btn.pack(side=tk.LEFT)
        ttk.Button(btns,text='Cancel calculation',command=self._cancel_task).pack(side=tk.LEFT,padx=6)
        export_btn = ttk.Button(btns, text='📊 Export CSV',
                                command=lambda:self._export_with_csv_preview(export_simulation,'shadow_results.csv'))
        export_btn.pack(side=tk.LEFT, padx=6)
        export_btn.state(["disabled"])
        chart_btn = ttk.Button(btns, text='📈 Chart for this simulation', command=self._show_simulation_chart)
        chart_btn.pack(side=tk.LEFT, padx=6)
        chart_btn.state(['disabled'])
        ttk.Button(btns, text='Close', command=win.destroy).pack(side=tk.RIGHT)

    # ------------------------------------------------------------------
    # Graphique : agrégation temporelle
    # ------------------------------------------------------------------
    @staticmethod
    def _aggregate_shadow_series(results, unit, count=1):
        """Agrège l'énergie simulée par période.

        results : dict ``shadow_simulation_results``
        unit    : 'year' | 'month' | 'week' | 'day' | 'hour' | 'minute' | 'second'
        count   : nombre d'unités par période (ex. 2 semaines, 15 minutes)

        Les mois sont de vrais mois calendaires (28 à 31 jours) ; les semaines
        commencent le lundi. Pour heures/minutes/secondes, l'énergie de chaque
        intervalle simulé est répartie au prorata de son recouvrement avec les
        périodes. Les périodes vides sont conservées (valeur 0).

        Retourne une liste de dicts {'start', 'end', 'produced', 'lost'} (kWh).
        Lève ValueError si le nombre de périodes dépasse _CHART_MAX_PERIODS.
        """
        import datetime as dt

        count = max(1, int(count))
        raw = results.get('intervals')
        if raw:
            items = [tuple(it) for it in raw]
        else:  # anciens résultats : uniquement le milieu de chaque intervalle
            items = [(t, t, p, l) for t, p, l in results.get('timeline', [])]
        if not items:
            return []
        items.sort(key=lambda it: it[0])
        first = items[0][0]
        midnight = first.replace(hour=0, minute=0, second=0, microsecond=0)
        eps = dt.timedelta(microseconds=1)

        if unit in ('month', 'year'):
            # Périodes calendaires : n mois, ou n années alignées sur le 1er janvier.
            months_per = count if unit == 'month' else 12 * count
            base = first.year * 12 + (first.month - 1 if unit == 'month' else 0)

            def key_of(t):
                return (t.year * 12 + t.month - 1 - base) // months_per

            def bounds(k):
                def month_start(total):
                    year, month0 = divmod(total, 12)
                    return dt.datetime(year, month0 + 1, 1)
                return (month_start(base + k * months_per),
                        month_start(base + (k + 1) * months_per))
        else:
            origin = midnight
            if unit == 'week':
                origin = midnight - dt.timedelta(days=midnight.weekday())
            size = dt.timedelta(seconds=_UNIT_SECONDS[unit] * count)
            size_s = size.total_seconds()

            def key_of(t):
                return int((t - origin).total_seconds() // size_s)

            def bounds(k):
                return origin + k * size, origin + (k + 1) * size

        def last_key(a, b):
            return key_of(b - eps) if b > a else key_of(a)

        k_first = key_of(first)
        k_last = max(last_key(a, b) for a, b, _, _ in items)
        n_periods = k_last - k_first + 1
        if n_periods > _CHART_MAX_PERIODS:
            raise ValueError(
                f'Too many periods ({n_periods}, max {_CHART_MAX_PERIODS}). '
                'Choose a larger step.'
            )

        acc = {}
        split = unit in ('hour', 'minute', 'second')
        for a, b, produced_wh, lost_wh in items:
            if split and b > a:
                total = (b - a).total_seconds()
                for k in range(key_of(a), key_of(b - eps) + 1):
                    s0, s1 = bounds(k)
                    frac = (min(b, s1) - max(a, s0)).total_seconds() / total
                    cell = acc.setdefault(k, [0.0, 0.0])
                    cell[0] += produced_wh * frac
                    cell[1] += lost_wh * frac
            else:
                cell = acc.setdefault(key_of(a), [0.0, 0.0])
                cell[0] += produced_wh
                cell[1] += lost_wh

        out = []
        for k in range(k_first, k_last + 1):
            s0, s1 = bounds(k)
            produced_wh, lost_wh = acc.get(k, (0.0, 0.0))
            out.append({'start': s0, 'end': s1,
                        'produced': produced_wh / 1000.0,
                        'lost': lost_wh / 1000.0})
        return out

    @staticmethod
    def _chart_label(unit, start, prev_start=None, multi_year=False):
        """Étiquette de l'axe X : « jan. », « 15 jan. », « 14:05\\n15 jan. »…"""
        mon = _MONTH_ABBR[start.month - 1]
        if unit == 'year':
            return str(start.year)
        if unit == 'month':
            return f'{mon} {start.year}' if multi_year else mon
        if unit in ('week', 'day'):
            if multi_year:
                return f'{start.day} {mon} {start.year}'
            return f'{start.day} {mon}'
        clock = start.strftime('%H:%M:%S' if unit == 'second' else '%H:%M')
        if prev_start is None or prev_start.date() != start.date():
            return f'{clock}\n{start.day} {mon}'
        return clock

    @staticmethod
    def _chart_range_text(unit, start, end):
        """Description complète d'une période (info-bulle)."""
        import datetime as dt
        last = end - dt.timedelta(microseconds=1)
        m0, m1 = _MONTH_ABBR[start.month - 1], _MONTH_ABBR[last.month - 1]
        if unit == 'year':
            if start.year == last.year:
                return str(start.year)
            return f'{start.year} → {last.year}'
        if unit == 'month':
            if (start.year, start.month) == (last.year, last.month):
                return f'{m0} {start.year}'
            return f'{m0} {start.year} → {m1} {last.year}'
        if unit in ('week', 'day'):
            if start.date() == last.date():
                return f'{start.day} {m0} {start.year}'
            return f'{start.day} {m0} → {last.day} {m1} {last.year}'
        fmt = '%H:%M:%S' if unit == 'second' else '%H:%M'
        head = f'{start.day} {m0} {start.year}  {start.strftime(fmt)}'
        if start.date() == end.date():
            return f'{head} → {end.strftime(fmt)}'
        return f'{head} → {end.day} {m1} {end.strftime(fmt)}'

    # ------------------------------------------------------------------
    # Graphique : fenêtre
    # ------------------------------------------------------------------
    def _show_simulation_chart(self):
        if not self._shadow_current():
            messagebox.showwarning('Simulation','Run a current simulation first.');return
        results = self.shadow_simulation_results
        timeline = results.get('timeline', [])
        if not timeline:
            return

        win = tk.Toplevel(self.root)
        win.title('Shadow simulation chart')
        self._center_window(win, 1080, 640)
        win.minsize(760, 460)
        win.transient(self.root)

        # Pas par défaut adapté à la durée simulée.
        span_days = (timeline[-1][0] - timeline[0][0]).total_seconds() / 86400.0
        if span_days > 1100:
            default_unit = 'Years'
        elif span_days > 92:
            default_unit = 'Months'
        else:
            default_unit = 'Hours' if span_days < 1.5 else 'Days'

        style_var = tk.StringVar(value='Bars')
        metric_var = tk.StringVar(value='Produced energy')
        unit_var = tk.StringVar(value=default_unit)
        count_var = tk.StringVar(value='1')

        controls = ttk.Frame(win, padding=(12, 10, 12, 4))
        controls.pack(fill=tk.X)

        def add_combo(label, var, values, width, gap=14):
            ttk.Label(controls, text=label).pack(side=tk.LEFT, padx=(0, 4))
            ttk.Combobox(controls, textvariable=var, values=values,
                         state='readonly', width=width).pack(side=tk.LEFT, padx=(0, gap))

        add_combo('Chart:', style_var, ('Bars', 'Line'), 7)
        add_combo('Value:', metric_var, tuple(_CHART_METRICS), 24)
        ttk.Label(controls, text='Time step:').pack(side=tk.LEFT, padx=(0, 4))
        ttk.Label(controls, text='every').pack(side=tk.LEFT, padx=(0, 3))
        ttk.Entry(controls, textvariable=count_var, width=5).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Combobox(controls, textvariable=unit_var, values=tuple(_STEP_UNITS),
                     state='readonly', width=10).pack(side=tk.LEFT)

        stats = ttk.Frame(win, padding=(12, 2, 12, 0))
        stats.pack(fill=tk.X)
        stat_vars = {k: tk.StringVar(value='') for k in ('produced', 'lost', 'loss', 'peak')}
        for key, color in (('produced', '#2E7D32'), ('lost', '#C62828'),
                           ('loss', '#EF6C00'), ('peak', '#1565C0')):
            ttk.Label(stats, textvariable=stat_vars[key], font=('Arial', 10, 'bold'),
                      foreground=color).pack(side=tk.LEFT, padx=(0, 22))

        status = ttk.Label(win, text='', foreground='#455A64', font=('Arial', 9))
        status.pack(anchor='w', padx=12, pady=(2, 4))

        frame = ttk.Frame(win)
        frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        horizontal = ttk.Scrollbar(frame, orient=tk.HORIZONTAL)
        horizontal.pack(side=tk.BOTTOM, fill=tk.X)
        canvas = tk.Canvas(frame, bg='white', highlightthickness=1,
                           highlightbackground='#CFD8DC')
        canvas.configure(xscrollcommand=horizontal.set)
        horizontal.configure(command=canvas.xview)
        canvas.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        state = {'layout': None}

        def show_error(message):
            status.config(text=message, foreground='#B71C1C')
            for var in stat_vars.values():
                var.set('')
            canvas.configure(scrollregion=(0, 0, 1, 1))

        def draw(event=None):
            canvas.delete('all')
            state['layout'] = None
            try:
                count = int(count_var.get())
                if not 1 <= count <= 100000:
                    raise ValueError
            except ValueError:
                show_error('Enter a whole number ≥ 1 for the time step.')
                return
            unit = _STEP_UNITS[unit_var.get()]
            try:
                buckets = self._aggregate_shadow_series(results, unit, count)
            except ValueError as exc:
                show_error(str(exc))
                return
            if not buckets:
                show_error('No data to display.')
                return

            keys = _CHART_METRICS[metric_var.get()]

            def value_of(bucket, key):
                if key == 'potential':
                    return bucket['produced'] + bucket['lost']
                return bucket[key]

            layers = [(key, [value_of(b, key) for b in buckets]) for key in keys]
            stacked = len(layers) > 1
            as_bars = style_var.get() == 'Bars'
            n = len(buckets)

            # --- Indicateurs -------------------------------------------------
            tot_prod = sum(b['produced'] for b in buckets)
            tot_lost = sum(b['lost'] for b in buckets)
            tot_pot = tot_prod + tot_lost
            stat_vars['produced'].set(f'Produced: {tot_prod:.3f} kWh')
            stat_vars['lost'].set(f'Lost: {tot_lost:.3f} kWh')
            stat_vars['loss'].set(
                f'Loss: {tot_lost / tot_pot * 100:.2f} %' if tot_pot > 0 else 'Loss: —')

            if stacked and as_bars:
                totals = [sum(vals[i] for _, vals in layers) for i in range(n)]
            elif stacked:
                totals = [max(vals[i] for _, vals in layers) for i in range(n)]
            else:
                totals = list(layers[0][1])
            peak_i = max(range(n), key=lambda i: totals[i])
            peak_v = totals[peak_i]
            peak_when = self._chart_label(unit, buckets[peak_i]['start'], None,
                                          buckets[0]['start'].year != buckets[-1]['start'].year
                                          ).replace('\n', ' ')
            stat_vars['peak'].set(
                f'Peak: {peak_v:.3f} kWh ({peak_when})' if peak_v > 0 else 'Peak: —')

            unit_txt = unit_var.get().lower()
            if count == 1:
                unit_txt = unit_txt[:-1]
            status.config(
                text=f'{n} period{"s" if n > 1 else ""} of {count} {unit_txt}'
                     f'  •  hover the chart for details',
                foreground='#455A64')

            # --- Échelle Y ---------------------------------------------------
            y_step, ticks = _nice_ticks(peak_v * 1.05 if peak_v > 0 else 1.0)
            upper = ticks[-1]
            exp = math.floor(math.log10(y_step))
            decimals = max(0, -exp)
            if exp <= 0 and abs(y_step / 10 ** exp - 2.5) < 1e-6:
                decimals += 1
            decimals = min(decimals, 4)

            # --- Géométrie ---------------------------------------------------
            canvas_w = max(canvas.winfo_width(), 420)
            height = max(canvas.winfo_height(), 300)
            left, right, top, bottom = 76, 30, 40, 70
            slot = max((canvas_w - left - right) / n, 10.0)
            right_x = left + slot * n
            width = right_x + right
            base_y = height - bottom
            plot_h = base_y - top
            canvas.configure(scrollregion=(0, 0, max(width, canvas_w), height))

            def y_of(v):
                return base_y - v / upper * plot_h

            def x_of(i):
                return left + (i + 0.5) * slot

            # Fond de la zone de tracé
            canvas.create_rectangle(left, top, right_x, base_y, fill='#F7F9FB', outline='')

            # Aire sous la courbe (mode ligne, une seule série)
            pts_by_layer = []
            if not as_bars:
                for key, vals in layers:
                    pts_by_layer.append(
                        (key, [(x_of(i), y_of(vals[i])) for i in range(n)]))
                if not stacked and n >= 2:
                    pts = pts_by_layer[0][1]
                    flat = [c for pt in pts for c in pt]
                    canvas.create_polygon(
                        pts[0][0], base_y, *flat, pts[-1][0], base_y,
                        fill=_CHART_PALETTES[layers[0][0]]['area'], outline='')

            # Grille + graduations Y
            for tick in ticks:
                y = y_of(tick)
                if tick > 0:
                    canvas.create_line(left, y, right_x, y, fill='#DDE3E8', dash=(2, 4))
                canvas.create_text(left - 8, y, anchor=tk.E, fill='#546E7A',
                                   text=f'{tick:.{decimals}f}', font=('Arial', 9))
            canvas.create_text(left - 8, top - 16, anchor=tk.E, fill='#37474F',
                               text='kWh', font=('Arial', 9, 'bold'))

            # --- Données -----------------------------------------------------
            show_labels = slot >= 46
            if as_bars:
                bar_w = min(slot * 0.72, 48.0)
                for i in range(n):
                    cx = x_of(i)
                    acc = 0.0
                    for key, vals in layers:
                        v = vals[i]
                        if v <= 0:
                            continue
                        pal = _CHART_PALETTES[key]
                        y0, y1 = y_of(acc + v), y_of(acc)
                        acc += v
                        if y1 - y0 < 0.5:
                            continue
                        canvas.create_rectangle(cx - bar_w / 2, y0, cx + bar_w / 2, y1,
                                                fill=pal['fill'], outline=pal['edge'])
                        if y1 - y0 > 6:
                            canvas.create_rectangle(
                                cx - bar_w / 2 + 1, y0 + 1, cx + bar_w / 2 - 1,
                                y0 + min(4, y1 - y0 - 1), fill=pal['cap'], outline='')
                    if totals[i] > 0 and (show_labels or (i == peak_i and n > 1)):
                        is_peak = (i == peak_i and n > 1)
                        canvas.create_text(
                            cx, y_of(totals[i]) - 4, anchor=tk.S, fill='#37474F',
                            text=f'{totals[i]:.2f}',
                            font=('Arial', 8, 'bold' if is_peak else 'normal'))
                if n > 1 and peak_v > 0:
                    cx = x_of(peak_i)
                    canvas.create_rectangle(
                        cx - bar_w / 2 - 2, y_of(peak_v) - 2, cx + bar_w / 2 + 2, base_y,
                        outline='#FFB300', width=2)
            else:
                for key, pts in pts_by_layer:
                    pal = _CHART_PALETTES[key]
                    if n >= 2:
                        flat = [c for pt in pts for c in pt]
                        canvas.create_line(*flat, fill=pal['edge'], width=2.5,
                                           joinstyle='round', capstyle='round')
                    if slot >= 14 or n == 1:
                        for x, y in pts:
                            canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill='white',
                                               outline=pal['edge'], width=2)
                if peak_v > 0 and n > 1:
                    px, py = x_of(peak_i), y_of(peak_v)
                    canvas.create_oval(px - 6, py - 6, px + 6, py + 6,
                                       outline='#FFB300', width=2)
                    canvas.create_text(px, py - 10, anchor=tk.S, fill='#37474F',
                                       text=f'{peak_v:.2f}', font=('Arial', 8, 'bold'))

            # Ligne de moyenne (une seule série)
            if not stacked and n > 1:
                avg = sum(layers[0][1]) / n
                if avg > 0:
                    ya = y_of(avg)
                    canvas.create_line(left, ya, right_x, ya, fill='#FB8C00',
                                       dash=(6, 3), width=1.5)
                    canvas.create_text(right_x - 4, ya - 3, anchor=tk.SE, fill='#EF6C00',
                                       text=f'avg {avg:.2f}', font=('Arial', 8, 'bold'))

            # --- Axes + étiquettes X ----------------------------------------
            canvas.create_line(left, top, left, base_y, fill='#B0BEC5')
            canvas.create_line(left, base_y, right_x, base_y, fill='#78909C', width=1.5)
            multi_year = buckets[0]['start'].year != buckets[-1]['start'].year
            if multi_year:
                min_px = {'year': 44, 'month': 68, 'week': 92, 'day': 92}.get(unit, 52)
            else:
                min_px = {'year': 44, 'month': 44, 'second': 60}.get(unit, 52)
            stride = max(1, math.ceil(min_px / slot))
            label_font = ('Arial', 9 if unit in ('year', 'month', 'week', 'day') else 8)
            prev = None
            for i in range(0, n, stride):
                start = buckets[i]['start']
                cx = x_of(i)
                canvas.create_line(cx, base_y, cx, base_y + 4, fill='#78909C')
                canvas.create_text(cx, base_y + 8, anchor=tk.N, justify=tk.CENTER,
                                   fill='#455A64', font=label_font,
                                   text=self._chart_label(unit, start, prev, multi_year))
                prev = start
            canvas.create_text(left, height - 10, anchor=tk.W, fill='#90A4AE',
                               font=('Arial', 8),
                               text=f'Time step: {count} {unit_txt}')

            # --- Légende -----------------------------------------------------
            lx = left + 4
            legend = [(_CHART_PALETTES[k]['name'], _CHART_PALETTES[k]['fill'], '') for k, _ in layers]
            if n > 1 and peak_v > 0:
                legend.append(('Peak', '', '#FFB300'))
            for name, fill, outline in legend:
                canvas.create_rectangle(lx, top - 24, lx + 10, top - 14,
                                        fill=fill, outline=outline or fill,
                                        width=2 if outline else 1)
                canvas.create_text(lx + 15, top - 19, anchor=tk.W, text=name,
                                   fill='#455A64', font=('Arial', 9))
                lx += 30 + 7 * len(name)

            state['layout'] = {'left': left, 'right_x': right_x, 'top': top,
                               'base': base_y, 'slot': slot, 'n': n,
                               'buckets': buckets, 'unit': unit}

        # --- Info-bulle au survol ------------------------------------------
        def on_motion(event):
            canvas.delete('hover')
            lay = state['layout']
            if not lay:
                return
            x, y = canvas.canvasx(event.x), canvas.canvasy(event.y)
            if not (lay['left'] <= x <= lay['right_x'] and lay['top'] <= y <= lay['base']):
                return
            i = max(0, min(lay['n'] - 1, int((x - lay['left']) // lay['slot'])))
            bucket = lay['buckets'][i]
            cx = lay['left'] + (i + 0.5) * lay['slot']
            canvas.create_line(cx, lay['top'], cx, lay['base'], fill='#607D8B',
                               dash=(3, 3), tags='hover')
            pot = bucket['produced'] + bucket['lost']
            lines = [self._chart_range_text(lay['unit'], bucket['start'], bucket['end']),
                     f"Produced: {bucket['produced']:.3f} kWh",
                     f"Lost: {bucket['lost']:.3f} kWh"]
            if pot > 0:
                lines.append(f"Shading loss: {bucket['lost'] / pot * 100:.1f} %")
            txt = canvas.create_text(cx + 12, lay['top'] + 8, anchor=tk.NW, fill='white',
                                     text='\n'.join(lines), font=('Arial', 9),
                                     justify=tk.LEFT, tags='hover')
            bb = canvas.bbox(txt)
            visible_right = canvas.canvasx(canvas.winfo_width())
            if bb and bb[2] + 10 > visible_right:
                canvas.move(txt, -(bb[2] - bb[0]) - 24, 0)
                bb = canvas.bbox(txt)
            if bb:
                box = canvas.create_rectangle(bb[0] - 6, bb[1] - 5, bb[2] + 6, bb[3] + 5,
                                              fill='#263238', outline='#263238',
                                              tags='hover')
                canvas.tag_lower(box, txt)

        def on_wheel(event):
            if event.num == 4 or getattr(event, 'delta', 0) > 0:
                canvas.xview_scroll(-3, 'units')
            else:
                canvas.xview_scroll(3, 'units')
            return 'break'

        if sys.platform.startswith('linux'):
            canvas.bind('<Button-4>', on_wheel)
            canvas.bind('<Button-5>', on_wheel)
        else:
            canvas.bind('<MouseWheel>', on_wheel)
        canvas.bind('<Motion>', on_motion)
        canvas.bind('<Leave>', lambda e: canvas.delete('hover'))

        for variable in (style_var, metric_var, unit_var, count_var):
            variable.trace_add('write', lambda *args: draw())
        canvas.bind('<Configure>', draw)
        draw()
