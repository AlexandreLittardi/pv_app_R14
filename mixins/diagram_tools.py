"""Onglet Schéma Unifilaire : génère automatiquement un schéma
Strings -> MPPT -> Onduleurs à partir des données de stringing/MPPT déjà
définies, et permet de l'ajuster manuellement (déplacer, ajouter des
éléments personnalisés, relier librement deux éléments)."""

import math
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk, filedialog
import webbrowser

NODE_COLORS = {
    "inverter": "#FF9800",
    "mppt": "#039BE5",
    "string": "#43A047",
    "custom": "#8E24AA",
}

NODE_W = 150
NODE_H = 46

# Diagram text is deliberately screen-sized, not zoom-sized.  The boxes have a
# minimum on-screen footprint so labels remain readable when the canvas is zoomed out.
DIAGRAM_FONT_LABEL = 9
DIAGRAM_FONT_DETAIL = 8
DIAGRAM_FONT_DISTANCE = 9
DIAGRAM_MIN_SCREEN_W = 150
DIAGRAM_MIN_SCREEN_H = 46
DIAGRAM_COLLISION_GAP = 14
LINK_STYLES = {
    'solid': ('Solid line', ()),
    'dashed': ('Dashed line', (7, 4)),
    'dotted': ('Dotted line', (2, 4)),
    'dashdot': ('Dash-dot line', (8, 3, 2, 3)),
}


class DiagramToolsMixin:
    # ========================================================
    # ONGLET RUBAN
    # ========================================================

    def _build_tab_diagram_tools(self):
        ttk.Button(
            self.tab_diagram, text='🔁 Auto generate (Strings → MPPT → Inverters)',
            command=self.generate_diagram_auto
        ).pack(side=tk.LEFT, padx=5)

        ttk.Separator(self.tab_diagram, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        ttk.Button(
            self.tab_diagram, text='➕ Custom element', command=self._add_custom_diagram_node
        ).pack(side=tk.LEFT, padx=5)

        self.diagram_link_menu_button = ttk.Menubutton(self.tab_diagram, text='🔗 Custom links')
        links_menu = tk.Menu(self.diagram_link_menu_button, tearoff=0)
        for style, (label, _dash) in LINK_STYLES.items():
            links_menu.add_command(label=label, command=lambda s=style: self._toggle_diagram_link_mode(s))
        self.diagram_link_menu_button['menu'] = links_menu
        self.diagram_link_menu_button.pack(side=tk.LEFT, padx=5)

        ttk.Button(
            self.tab_diagram, text='🗑️ Delete selected element', command=self._delete_selected_diagram_node
        ).pack(side=tk.LEFT, padx=5)

        ttk.Separator(self.tab_diagram, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)

        mb_zoom_diagram = ttk.Menubutton(self.tab_diagram, text="🔍 Zoom")
        menu_zoom_diagram = tk.Menu(mb_zoom_diagram, tearoff=0)
        menu_zoom_diagram.add_command(label='🔍 Zoom in (+)', command=lambda: self._zoom_button_change(1.2))
        menu_zoom_diagram.add_command(label='🔍 Zoom out (-)', command=lambda: self._zoom_button_change(1 / 1.2))
        menu_zoom_diagram.add_separator()
        menu_zoom_diagram.add_command(label='🎯 Reset (100%)', command=self._reset_zoom)
        mb_zoom_diagram["menu"] = menu_zoom_diagram
        mb_zoom_diagram.pack(side=tk.RIGHT, padx=5)

        ttk.Label(
            self.tab_diagram,
            text='Left drag: pan | Right drag: select | Right drag selected block: move group',
            font=("Arial", 8), foreground="#555555"
        ).pack(side=tk.LEFT, padx=10)

    # ========================================================
    # PANNEAU LATÉRAL
    # ========================================================

    def _build_side_panel_diagram(self):
        self.side_panel_diagram = ttk.Frame(self.main_container, width=260, padding=5)

        ttk.Label(
            self.side_panel_diagram, text='Diagram elements', font=("Arial", 10, "bold")
        ).pack(pady=5)

        self.lst_diagram_nodes = tk.Listbox(self.side_panel_diagram, selectmode=tk.EXTENDED, exportselection=False, height=24)
        self.lst_diagram_nodes.pack(fill=tk.BOTH, expand=True, pady=5)
        self.lst_diagram_nodes.bind("<<ListboxSelect>>", self._on_diagram_list_select)

        ttk.Button(
            self.side_panel_diagram, text='🗑️ Delete', command=self._delete_selected_diagram_node
        ).pack(fill=tk.X, pady=(0, 5))

        ttk.Label(
            self.side_panel_diagram,
            text="This list reflects the generated diagram. Add custom elements "
                 "(protective devices, switchboard, meter) with the toolbar, "
                 "then choose a custom link style and click two elements. "
                 "Enter equipment values in Home > Configuration. Shift/Ctrl-click to select several elements.",
            font=("Arial", 8), foreground="#555555", justify=tk.LEFT, wraplength=240
        ).pack(pady=5, fill=tk.X)

    # ========================================================
    # GÉNÉRATION AUTOMATIQUE
    # ========================================================

    def _export_site_single_line(self, batteries,language='en'):
        """Rebuild the site topology from the CURRENT project, not a saved image."""
        try:
            from single_line_516 import build_model, write_svg
            snapshot = {
                'project_name': self.project_name,
                'panels': {f'{r},{c}':num for (r,c),num in self.panels.items()},
                'strings': {sid:[f'{r},{c}' for r,c in coords] for sid,coords in self.strings.items()},
                'string_mppt_assignment':self.string_mppt_assignment,
                'blocks':self.blocks,
                'panel_pmax_w':self.panel_pmax_w,
                'panel_width_mm':self.panel_width_mm,
                'panel_height_mm':self.panel_height_mm,
                'px_per_mm':self.px_per_mm,
                'inverter_positions':self.inverter_positions,
                'cable_paths':self.cable_paths,
                'roof_zones':self.roof_zones,
                'electrical_route_plan_3d':getattr(self,'electrical_route_plan_3d',{}),
                'bess_summary':self.bess_summary,
                'electrical_checks':getattr(self,'electrical_checks',{}),
            }
            model=build_model(snapshot,batteries)
            path=filedialog.asksaveasfilename(
                parent=self.root,title='Export preliminary single-line diagram',
                initialfile=f'Volfrigo_{len(self.panels)}_single_line_{batteries}_BESS_{language.upper()}.svg',
                defaultextension='.svg',filetypes=[('Vector diagram SVG','*.svg')])
            if not path:return
            write_svg(model,path,language=language)
            problems='\n'.join(model['issues'][:6]) or 'No inconsistency detected by the automatic checks.'
            messagebox.showinfo('Preliminary diagram exported',
                                f'{path}\n\nChecks: {problems}\n\nDesigner review and sign-off required.',
                                parent=self.root)
            webbrowser.open_new_tab(__import__('pathlib').Path(path).resolve().as_uri())
        except (ValueError,OSError,KeyError,TypeError) as exc:
            messagebox.showerror('Diagram not exported',str(exc),parent=self.root)

    def generate_diagram_auto(self):
        desired_ids = set()
        new_auto_links = []

        x_str, x_mppt, x_inv = 160, 520, 880
        string_step = 155 if self.diagram_show_electrical else 90
        mppt_step = 155 if self.diagram_show_electrical else 100
        y_cursor_inv = 60

        for block_name, block in self.blocks.items():
            inv_id = f"inv::{block_name}"
            desired_ids.add(inv_id)
            mppt_count = max(1, int(block.get("mppt_count", 2)))

            mppt_ids_here = [f"mppt::{block_name}::{m}" for m in range(1, mppt_count + 1)]
            block_top_y = y_cursor_inv
            y_cursor_mppt = block_top_y

            for m in range(1, mppt_count + 1):
                mppt_id = f"mppt::{block_name}::{m}"
                desired_ids.add(mppt_id)

                strs = [
                    sid for sid, a in self.string_mppt_assignment.items()
                    if a.get("block") == block_name and a.get("mppt") == m
                ]

                y_cursor_str = y_cursor_mppt
                for sid in strs:
                    s_node_id = f"str::{sid}"
                    desired_ids.add(s_node_id)
                    node = self.diagram_nodes.setdefault(s_node_id, {})
                    
                    n_panels = len(self.strings.get(sid, []))
                    label_text = f"⚡ {sid.replace('String ', 'S')} ({n_panels} panels)"

                    node.update({"x":x_str,"y":y_cursor_str,"type": "string", "label": label_text})
                    new_auto_links.append((s_node_id, mppt_id))
                    y_cursor_str += string_step

                mppt_node = self.diagram_nodes.setdefault(mppt_id, {})
                mppt_node.update({"x":x_mppt,"y":y_cursor_mppt+(max(1,len(strs))-1)*string_step/2,
                                  "type": "mppt", "label": f"MPPT {m}"})
                new_auto_links.append((mppt_id, inv_id))

                y_cursor_mppt += max(mppt_step, len(strs) * string_step)

            inv_node = self.diagram_nodes.setdefault(inv_id, {})
            inv_node.update({"x":x_inv,"y":(block_top_y+y_cursor_mppt)/2,
                             "type": "inverter", "label": f"🔌 {block_name}"})

            y_cursor_inv = y_cursor_mppt + 100

        # Nettoyage des noeuds auto obsolètes (plus présents dans les données actuelles)
        for node_id in list(self.diagram_nodes.keys()):
            if node_id.startswith(("inv::", "mppt::", "str::")) and node_id not in desired_ids:
                del self.diagram_nodes[node_id]

        # On garde les liens manuels valides, on régénère les liens auto
        self.diagram_links = [
            link for link in self.diagram_links
            if not link.get("auto") and link["a"] in self.diagram_nodes and link["b"] in self.diagram_nodes
            and not any(link[end].startswith(("str::", "mppt::")) for end in ("a", "b"))
        ]
        for a, b in new_auto_links:
            dist = 0.0
            if a.startswith("str::"):
                sid = a.split("::")[1]
                length_mm = None
                if hasattr(self, "compute_cable_length_mm"):
                    length_mm, _via = self.compute_cable_length_mm(sid)
                if length_mm is not None:
                    dist = length_mm / 1000.0
                elif sid in self.strings and self.px_per_mm > 0:
                    # Repli si pas d'onduleur placé : longueur panneau à panneau
                    px_dist = 0.0
                    coords = self.strings[sid]
                    for i in range(len(coords) - 1):
                        p1 = self._get_panel_physical_center(coords[i])
                        p2 = self._get_panel_physical_center(coords[i + 1])
                        px_dist += math.hypot(p2[0] - p1[0], p2[1] - p1[1])
                    dist = (px_dist / self.px_per_mm) / 1000.0

            self.diagram_links.append({"a": a, "b": b, "auto": True, "distance_m": dist})

        self.diagram_selected_node = None
        self._resolve_diagram_collisions()
        self._refresh_diagram_list()
        self.draw_grid()

    # ========================================================
    # ÉDITION MANUELLE
    # ========================================================

    def _add_custom_diagram_node(self):
        label = simpledialog.askstring(
            'Custom element', 'Element name (e.g. AC protection, switchboard, meter):', parent=self.root
        )
        if not label or not label.strip():
            return
        dist = simpledialog.askfloat(
            "Distance", f"Cable distance to element '{label}' (metres):",
            initialvalue=5.0, parent=self.root
        )
        if dist is None: dist = 0.0

        node_id = f"custom::{self.diagram_next_custom_id}"
        self.diagram_next_custom_id += 1
        self.diagram_nodes[node_id] = {"type": "custom", "label": label.strip(), "x": 420, "y": 40}
        
        # On ajoute un lien automatique avec la distance si un élément était sélectionné
        if self.diagram_selected_node:
            self.diagram_links.append({
                "a": self.diagram_selected_node,
                "b": node_id,
                "auto": False,
                "style": self.diagram_link_style,
                "distance_m": dist
            })

        self.diagram_selected_node = node_id
        self._resolve_diagram_collisions()
        self._refresh_diagram_list()
        self.draw_grid()

    def _toggle_diagram_link_mode(self, style='solid'):
        if style not in LINK_STYLES:
            return
        if self.diagram_link_mode and self.diagram_link_style == style:
            self._cancel_diagram_link_mode()
            return
        self.diagram_link_style = style
        self.diagram_link_mode = True
        self.diagram_link_first = None
        self.diagram_link_menu_button.configure(text=f'🔗 {LINK_STYLES[style][0]}: select two')

    def _cancel_diagram_link_mode(self):
        self.diagram_link_mode = False
        self.diagram_link_first = None
        self.diagram_link_menu_button.configure(text='🔗 Custom links')

    def _edit_diagram_electrical_specs(self):
        """Record STC module ratings and an optional nominal inverter AC rating."""
        dialog = tk.Toplevel(self.root)
        dialog.title('Electrical values in single-line diagram')
        dialog.transient(self.root)
        dialog.resizable(False, False)
        fields = (
            ('pmax_w', 'Module Pmax (W)'), ('voc_v', 'Module Voc (V)'),
            ('vmp_v', 'Module Vmp / Vmpp (V)'), ('isc_a', 'Module Isc (A)'),
            ('imp_a', 'Module Imp / Impp (A)'),
            ('inverter_ac_kw', 'Inverter nominal AC power (kW, optional)'),
        )
        body = ttk.Frame(dialog, padding=14)
        body.pack(fill=tk.BOTH, expand=True)
        ttk.Label(body, text='Module ratings at STC; values are multiplied by the actual panel count.',
                  wraplength=385).grid(row=0, column=0, columnspan=2, sticky='w', pady=(0, 8))
        entries = {}
        for i, (key, label) in enumerate(fields, 1):
            ttk.Label(body, text=label).grid(row=i, column=0, sticky='w', pady=3)
            entry = ttk.Entry(body, width=16)
            value = self.diagram_electrical_specs.get(key)
            if value is not None:
                entry.insert(0, str(value))
            entry.grid(row=i, column=1, sticky='e', padx=(12, 0), pady=3)
            entries[key] = entry

        def from_equipment():
            categories = getattr(self, 'material_categories', {}) or {}
            modules = categories.get('modules', {}).get('rows', [])
            inverters = categories.get('inverters', {}).get('rows', [])
            if not modules:
                messagebox.showinfo('Electrical values', 'Enter a PV module in the equipment sheet first.', parent=dialog)
                return
            module = modules[0]
            column_keys = {'pmax_w': 'Pmax (W)', 'voc_v': 'Voc (V)', 'vmp_v': 'Vmp (V)',
                           'isc_a': 'Isc (A)', 'imp_a': 'Imp (A)'}
            for key, column in column_keys.items():
                if str(module.get(column, '')).strip():
                    entries[key].delete(0, tk.END)
                    entries[key].insert(0, str(module[column]))
            if inverters and str(inverters[0].get('Puissance (kVA)', '')).strip():
                # kVA cannot be converted to kW without a power factor.
                messagebox.showinfo('Electrical values',
                                    'The equipment sheet lists inverter kVA. Enter nominal AC kW separately.',
                                    parent=dialog)

        ttk.Button(body, text='Copy PV module from equipment sheet', command=from_equipment).grid(
            row=7, column=0, columnspan=2, sticky='w', pady=(12, 4))
        show = tk.BooleanVar(value=self.diagram_show_electrical)
        ttk.Checkbutton(body, text='Show electrical values on diagram', variable=show).grid(
            row=8, column=0, columnspan=2, sticky='w', pady=4)

        def save():
            parsed = {}
            try:
                for key, _label in fields:
                    raw = entries[key].get().strip()
                    if raw:
                        value = float(raw.replace(',', '.'))
                        if not math.isfinite(value) or value <= 0:
                            raise ValueError(f'{key} must be positive.')
                        parsed[key] = value
                if show.get() and any(key not in parsed for key in ('pmax_w', 'voc_v', 'vmp_v', 'isc_a', 'imp_a')):
                    raise ValueError('Enter all five PV module ratings to show electrical values.')
                if parsed.get('vmp_v', 0) > parsed.get('voc_v', float('inf')):
                    raise ValueError('Module Vmp must not exceed Voc.')
                if parsed.get('imp_a', 0) > parsed.get('isc_a', float('inf')):
                    raise ValueError('Module Imp must not exceed Isc.')
            except ValueError as exc:
                messagebox.showerror('Electrical values', str(exc), parent=dialog)
                return
            self.diagram_electrical_specs = parsed
            self.diagram_show_electrical = show.get()
            dialog.destroy()
            self.draw_grid()

        buttons = ttk.Frame(body)
        buttons.grid(row=9, column=0, columnspan=2, sticky='e', pady=(12, 0))
        ttk.Button(buttons, text='Cancel', command=dialog.destroy).pack(side=tk.RIGHT, padx=4)
        ttk.Button(buttons, text='Apply', command=save).pack(side=tk.RIGHT, padx=4)
        dialog.bind('<Escape>', lambda event: dialog.destroy())
        dialog.bind('<Return>', lambda event: save())
        dialog.grab_set()
        entries['pmax_w'].focus_set()

    def _toggle_diagram_electrical(self):
        if not self.diagram_show_electrical and not all(
                key in self.diagram_electrical_specs for key in ('pmax_w', 'voc_v', 'vmp_v', 'isc_a', 'imp_a')):
            self._edit_diagram_electrical_specs()
            return
        self._diagram_layout_applied = None
        self.diagram_show_electrical = not self.diagram_show_electrical
        self.draw_grid()

    def _diagram_node_metric_lines(self, node_id):
        """Calculate STC DC ratings using each string's actual number of modules."""
        specs = self.diagram_electrical_specs
        if not self.diagram_show_electrical or not all(
                key in specs for key in ('pmax_w', 'voc_v', 'vmp_v', 'isc_a', 'imp_a')):
            return []
        if node_id.startswith('str::'):
            sid = node_id.split('::', 1)[1]
            count = len(self.strings.get(sid, []))
            return [f'Pdc {count * specs["pmax_w"] / 1000:.2f} kW  |  Voc {count * specs["voc_v"]:.1f} V',
                    f'Vmp {count * specs["vmp_v"]:.1f} V  |  Isc {specs["isc_a"]:.1f} A  Imp {specs["imp_a"]:.1f} A']
        if node_id.startswith('mppt::'):
            _, block, mppt = node_id.split('::', 2)
            sids = [sid for sid, assignment in self.string_mppt_assignment.items()
                    if assignment.get('block') == block and str(assignment.get('mppt')) == mppt
                    and self.strings.get(sid)]
            counts = [len(self.strings[sid]) for sid in sids]
            if not counts:
                return ['No assigned strings']
            volts = lambda key: f'{min(counts) * specs[key]:.1f}' if min(counts) == max(counts) else \
                f'{min(counts) * specs[key]:.1f}–{max(counts) * specs[key]:.1f}'
            return [f'{len(counts)} strings  |  Pdc {sum(counts) * specs["pmax_w"] / 1000:.2f} kW',
                    f'Voc {volts("voc_v")} V  |  Vmp {volts("vmp_v")} V',
                    f'Isc Σ {len(counts) * specs["isc_a"]:.1f} A  |  Imp Σ {len(counts) * specs["imp_a"]:.1f} A']
        if node_id.startswith('inv::'):
            block = node_id.split('::', 1)[1]
            count = sum(len(self.strings.get(sid, [])) for sid, assignment in self.string_mppt_assignment.items()
                        if assignment.get('block') == block)
            lines = [f'Assigned Pdc {count * specs["pmax_w"] / 1000:.2f} kW']
            if 'inverter_ac_kw' in specs:
                lines.append(f'Nominal Pac {specs["inverter_ac_kw"]:.2f} kW')
            return lines
        return []

    def _delete_selected_diagram_node(self):
        node_id = self.diagram_selected_node
        if not node_id or node_id not in self.diagram_nodes:
            messagebox.showinfo("Info", 'Select an element to delete.')
            return
        del self.diagram_nodes[node_id]
        self.diagram_links = [
            l for l in self.diagram_links if l["a"] != node_id and l["b"] != node_id
        ]
        self.diagram_selected_node = None
        self._refresh_diagram_list()
        self.draw_grid()

    def _diagram_screen_node_size(self, node_id):
        """Return the actual box size in canvas pixels for the current zoom.

        Text stays at a fixed screen size, therefore the node cannot shrink below
        the minimum area required to keep its text legible.
        """
        logical_w, logical_h = self._diagram_node_size(node_id)
        zoom = max(0.05, float(self.zoom_level))
        metric_lines = self._diagram_node_metric_lines(node_id)
        node = self.diagram_nodes.get(node_id, {})
        is_string = node.get('type') == 'string'

        # Fixed-screen text requires a stable minimum box.  Electrical-detail
        # nodes need more height because they contain several independent lines.
        min_w = 225 if metric_lines else DIAGRAM_MIN_SCREEN_W
        if metric_lines:
            min_h = max(78, (65 if is_string else 42) + 17 * len(metric_lines) + 10)
        elif is_string:
            min_h = 52
        else:
            min_h = DIAGRAM_MIN_SCREEN_H

        return max(logical_w * zoom, min_w), max(logical_h * zoom, min_h)

    def _diagram_screen_centres(self):
        """Canvas-space centres after applying zoom."""
        zoom = max(0.05, float(self.zoom_level))
        return {
            node_id: (float(node.get('x', 0.0)) * zoom,
                      float(node.get('y', 0.0)) * zoom)
            for node_id, node in self.diagram_nodes.items()
        }

    def _resolve_diagram_collisions(self):
        """Separate overlapping diagram blocks while preserving their columns.

        The automatic topology is column-based (strings -> MPPT -> inverter), so
        vertical displacement is the least disruptive correction.  Custom nodes
        are treated the same way.  Positions are stored back in logical canvas
        coordinates so links, hit testing and subsequent dragging stay coherent.
        """
        if len(self.diagram_nodes) < 2:
            return

        zoom = max(0.05, float(self.zoom_level))
        gap = DIAGRAM_COLLISION_GAP
        ids = list(self.diagram_nodes)

        # A bounded relaxation is deterministic and sufficient for the small
        # number of columns used by the single-line diagram.
        for _pass in range(max(4, len(ids) * 2)):
            moved = False
            centres = self._diagram_screen_centres()

            # Process top-to-bottom, then left-to-right.  Earlier nodes keep their
            # location; later nodes are pushed down only as much as necessary.
            ordered = sorted(ids, key=lambda nid: (centres[nid][1], centres[nid][0], nid))
            placed = []
            for node_id in ordered:
                cx, cy = centres[node_id]
                w, h = self._diagram_screen_node_size(node_id)

                while True:
                    collision = None
                    for other_id in placed:
                        ox, oy = centres[other_id]
                        ow, oh = self._diagram_screen_node_size(other_id)
                        x_overlap = abs(cx - ox) < (w + ow) / 2 + gap
                        y_overlap = abs(cy - oy) < (h + oh) / 2 + gap
                        if x_overlap and y_overlap:
                            collision = (other_id, oy, oh)
                            break
                    if collision is None:
                        break

                    _other_id, oy, oh = collision
                    cy = oy + (oh + h) / 2 + gap
                    centres[node_id] = (cx, cy)
                    moved = True

                placed.append(node_id)

            if moved:
                for node_id, (cx, cy) in centres.items():
                    self.diagram_nodes[node_id]['x'] = cx / zoom
                    self.diagram_nodes[node_id]['y'] = cy / zoom
            else:
                break

    def _hit_test_diagram_node(self, cx, cy):
        zoom = self.zoom_level
        for node_id, node in self.diagram_nodes.items():
            nx, ny = node["x"] * zoom, node["y"] * zoom
            w, h = self._diagram_screen_node_size(node_id)
            if nx - w / 2 <= cx <= nx + w / 2 and ny - h / 2 <= cy <= ny + h / 2:
                return node_id
        return None

    def _diagram_node_size(self, node_id):
        lines = self._diagram_node_metric_lines(node_id)
        return (225, max(78, 36 + 17 * len(lines))) if lines else (NODE_W, NODE_H)

    def _on_diagram_list_select(self, event):
        sel = self.lst_diagram_nodes.curselection()
        if not sel:
            return
        node_id = self._diagram_list_ids[sel[0]]
        self.diagram_selected_node = node_id
        self.draw_grid()

    def _refresh_diagram_list(self):
        if not hasattr(self, "lst_diagram_nodes"):
            return
        self.lst_diagram_nodes.delete(0, tk.END)
        self._diagram_list_ids = []
        for node_id, node in self.diagram_nodes.items():
            self.lst_diagram_nodes.insert(tk.END, node.get("label", node_id))
            self._diagram_list_ids.append(node_id)

    def _get_string_length_m(self, sid):
        """Longueur cumulée (en m) du câblage d'une string, panneau à panneau.
        Retourne None si l'échelle n'est pas définie."""
        if self.px_per_mm <= 0:
            return None
        coords = self.strings.get(sid, [])
        px_dist = 0.0
        for i in range(len(coords) - 1):
            p1 = self._get_panel_physical_center(coords[i])
            p2 = self._get_panel_physical_center(coords[i + 1])
            px_dist += math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        return (px_dist / self.px_per_mm) / 1000.0

    # ========================================================
    # RENDU
    # ========================================================

    def _draw_diagram(self):
        zoom = max(0.05, float(self.zoom_level))
        max_w, max_h = 400, 300

        # Zooming out brings logical centres closer together while text remains
        # fixed-size.  Re-separate boxes before drawing so labels never pile up.
        self._resolve_diagram_collisions()

        for link in self.diagram_links:
            a, b = self.diagram_nodes.get(link["a"]), self.diagram_nodes.get(link["b"])
            if not a or not b:
                continue
            ax, ay = a["x"] * zoom, a["y"] * zoom
            bx, by = b["x"] * zoom, b["y"] * zoom
            color = "#90A4AE" if link.get("auto") else "#D32F2F"
            dash = () if link.get("auto") else LINK_STYLES.get(
                link.get('style', 'dashed'), LINK_STYLES['dashed'])[1]

            # Orthogonal bus lanes avoid diagonal crossings in generated trees.
            a_width = self._diagram_screen_node_size(link['a'])[0]
            b_width = self._diagram_screen_node_size(link['b'])[0]
            if ax < bx:
                left, right = ax + a_width / 2, bx - b_width / 2
            else:
                left, right = ax - a_width / 2, bx + b_width / 2
            lane = (left + right) / 2
            self.canvas.create_line(
                left, ay, lane, ay, lane, by, right, by,
                fill=color, width=2, dash=dash
            )

            dist_m = link.get("distance_m", 0.0)
            if link.get("distance_label") or (dist_m is not None and dist_m > 0):
                # Fixed 12 px visual offset: labels do not collapse toward the line.
                mx, my = (left + lane) / 2, ay - 12
                label = link.get("distance_label") or f"{dist_m:.1f} m"
                if hasattr(self, "_draw_text_with_bg"):
                    self._draw_text_with_bg(
                        mx, my, label, fill="black",
                        font=("Times New Roman", DIAGRAM_FONT_DISTANCE)
                    )
                else:
                    self.canvas.create_text(
                        mx, my, text=label, fill=color,
                        font=("Arial", DIAGRAM_FONT_DISTANCE, "bold")
                    )

        for node_id, node in self.diagram_nodes.items():
            nx, ny = node["x"] * zoom, node["y"] * zoom
            metric_lines = self._diagram_node_metric_lines(node_id)
            w, h = self._diagram_screen_node_size(node_id)
            x1, y1, x2, y2 = nx - w / 2, ny - h / 2, nx + w / 2, ny + h / 2
            color = NODE_COLORS.get(node.get("type"), "#607D8B")
            is_selected = (
                node_id in getattr(self, "diagram_selected_nodes", set())
                or node_id == self.diagram_selected_node
            )
            outline = "#0055FF" if is_selected else "#263238"
            width_val = 3 if is_selected else 1
            self.canvas.create_rectangle(
                x1, y1, x2, y2, fill=color, outline=outline, width=width_val
            )

            label = node.get("label", node_id)
            wrap_width = max(80, int(w - 12))

            if node.get("type") == "string" and node_id.startswith("str::"):
                label = label.split(" | ")[0]
                length_m = self._get_string_length_m(node_id.split("::", 1)[1])

                # All offsets and fonts are screen-space constants.
                label_y = y1 + 15 if metric_lines else ny - 9
                self.canvas.create_text(
                    nx, label_y, text=label, fill="white",
                    font=("Arial", DIAGRAM_FONT_LABEL, "bold"),
                    width=wrap_width
                )

                length_txt = (
                    'Module chain: scale not set'
                    if length_m is None else f"Module chain ~ {length_m:.1f} m"
                )
                length_y = y1 + 33 if metric_lines else ny + 10
                self.canvas.create_text(
                    nx, length_y, text=length_txt, fill="#FFEB3B",
                    font=("Arial", DIAGRAM_FONT_LABEL, "bold"),
                    width=wrap_width
                )
            else:
                label_y = y1 + 17 if metric_lines else ny
                self.canvas.create_text(
                    nx, label_y, text=label, fill="white",
                    font=("Arial", DIAGRAM_FONT_LABEL, "bold"),
                    width=wrap_width
                )

            metric_start = y1 + (65 if node.get('type') == 'string' else 42)
            for index, line in enumerate(metric_lines):
                y = metric_start + index * 17
                self.canvas.create_text(
                    nx, y, text=line, fill='#FFFFFF',
                    font=('Arial', DIAGRAM_FONT_DETAIL),
                    width=max(100, int(w - 10))
                )

            max_w = max(max_w, x2 + 150)
            max_h = max(max_h, y2 + 150)

        if not self.diagram_nodes:
            self.canvas.create_text(
                200, 100, anchor=tk.NW,
                text="No elements. Click Auto generate to build the diagram from\n"
                     "existing strings, MPPTs and inverters, or add a custom element.",
                fill="#616161", font=("Arial", 10), justify=tk.LEFT
            )

        self.total_w = max_w
        self.total_h = max_h
        self.canvas.config(scrollregion=(0, 0, max_w, max_h))
