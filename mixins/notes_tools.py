"""Cabling workspace: route inventory, DC voltage-drop estimate and project notes."""

import csv
import math
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from project_validation import string_label


STANDARD_DC_SECTIONS = (1.5, 2.5, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240)


def calculate_dc_cable_size(current_a, voltage_v, length_m, resistivity, target_drop_pct):
    """Estimate a two-conductor DC circuit from one-way cable length.

    This only checks voltage drop. It does not check ampacity, temperature,
    installation method, insulation, protection, or national standards.
    """
    values = (current_a, voltage_v, length_m, resistivity, target_drop_pct)
    if any(not math.isfinite(value) or value <= 0 for value in values):
        raise ValueError('All sizing values must be positive, finite numbers.')
    if target_drop_pct >= 100:
        raise ValueError('Maximum voltage drop must be below 100%.')
    minimum = 2 * length_m * current_a * resistivity / (voltage_v * target_drop_pct / 100)
    recommended = next((s for s in STANDARD_DC_SECTIONS if s >= minimum), None)
    drop_pct = (2 * length_m * current_a * resistivity / recommended / voltage_v * 100
                if recommended is not None else None)
    return {'minimum_mm2': minimum, 'recommended_mm2': recommended,
            'actual_drop_pct': drop_pct, 'target_drop_pct': target_drop_pct}


class NotesToolsMixin:
    def _init_notes_state(self):
        self.project_notes = ''
        self.cable_inventory = []
        self.cable_string_params = {}
        self.cable_mass_by_section = {}
        self.cable_calc_params = {
            'current_a': 10.0, 'voltage_v': 600.0, 'length_m': 50.0,
            'resistivity': 0.017, 'target_drop_pct': 1.0,
        }
        self.show_cable_network_routes = False
        self.cable_network_routes = {}
        self.cable_routes_calculated = False
        self.selected_cable_route = None

    def _build_tab_notes_tools(self):
        cable_paths = ttk.Menubutton(self.tab_notes, text='🔌 Cable paths')
        cable_menu = tk.Menu(cable_paths, tearoff=0)
        cable_menu.add_command(label='➕ Draw cable path', command=self._activate_cable_path_draw_mode)
        cable_menu.add_command(label='✅ Finish drawing (right-click)', command=self._finish_cable_path_draw)
        cable_menu.add_separator()
        cable_menu.add_command(label='🗑️ Delete selected path', command=self.delete_active_cable_path)
        cable_paths['menu'] = cable_menu
        cable_paths.pack(side=tk.LEFT, padx=5)

        ttk.Label(self.tab_notes, text='Path:').pack(side=tk.LEFT, padx=2)
        self.combo_cable_paths = ttk.Combobox(self.tab_notes, values=[], width=10, state='readonly')
        self.combo_cable_paths.pack(side=tk.LEFT, padx=2)
        self.combo_cable_paths.bind('<<ComboboxSelected>>', self._on_cable_path_combo_selected)
        self._fix_combobox_popdown_position(self.combo_cable_paths)

        gather = ttk.Menubutton(self.tab_notes, text='📍 Gathering points')
        gather_menu = tk.Menu(gather, tearoff=0)
        gather_menu.add_command(label='🎯 Place / move (click roof)', command=self._activate_gather_point_mode)
        gather_menu.add_command(label='🔄 Reset to automatic (all zones)', command=self._reset_gather_points)
        gather['menu'] = gather_menu
        gather.pack(side=tk.LEFT, padx=5)

        routing = ttk.Menubutton(self.tab_notes, text='🧭 String routes')
        routing_menu = tk.Menu(routing, tearoff=0)
        routing_menu.add_command(label='Calculate / update routes', command=self._calculate_and_show_cable_routes)
        routing_menu.add_command(label='Installation heights / bridge settings', command=self._show_installation_heights)
        routing_menu.add_command(label='Hide routes on roof', command=self._hide_cable_routes)
        routing_menu.add_separator()
        routing_menu.add_command(label='Export route inventory CSV', command=self._export_cable_routes_csv)
        routing['menu'] = routing_menu
        routing.pack(side=tk.LEFT, padx=5)

        zoom = ttk.Menubutton(self.tab_notes, text='🔍 Zoom')
        zoom_menu = tk.Menu(zoom, tearoff=0)
        zoom_menu.add_command(label='🔍 Zoom in (+)', command=lambda: self._zoom_button_change(1.2))
        zoom_menu.add_command(label='🔍 Zoom out (-)', command=lambda: self._zoom_button_change(1 / 1.2))
        zoom_menu.add_separator()
        zoom_menu.add_command(label='🎯 Reset (100%)', command=self._reset_zoom)
        zoom['menu'] = zoom_menu
        zoom.pack(side=tk.RIGHT, padx=5)

    def _build_side_panel_notes(self):
        self.side_panel_notes = ttk.Frame(self.main_container, width=370, padding=5)
        notebook = ttk.Notebook(self.side_panel_notes)
        notebook.pack(fill=tk.BOTH, expand=True)

        routes_page = ttk.Frame(notebook, padding=7)
        sizing_page = ttk.Frame(notebook, padding=7)
        notes_page = ttk.Frame(notebook, padding=7)
        notebook.add(routes_page, text='Routes')
        notebook.add(sizing_page, text='DC sizing')
        self._build_string_sizing_page(notebook)
        notebook.add(notes_page, text='Notes')

        ttk.Label(routes_page, text='Calculated string → inverter routes',
                  font=('Arial', 10, 'bold')).pack(anchor='w')
        self.lbl_routes_summary = ttk.Label(routes_page, text='Calculate routes to see lengths and routing methods.',
                                            wraplength=340)
        self.lbl_routes_summary.pack(anchor='w', pady=(5, 8))
        routes_frame = ttk.Frame(routes_page)
        routes_frame.pack(fill=tk.BOTH, expand=True)
        self.cable_routes_tree = ttk.Treeview(routes_frame, columns=('block', 'mppt', 'length', 'method'),
                                              show='tree headings', height=12, selectmode='browse')
        for key, title, width in (('#0', 'String', 70), ('block', 'Block', 70),
                                  ('mppt', 'MPPT', 48), ('length', 'A+B (m)', 78),
                                  ('method', 'Method', 73)):
            self.cable_routes_tree.heading(key, text=title)
            self.cable_routes_tree.column(key, width=width, minwidth=45,
                                          anchor='e' if key == 'length' else 'w')
        self.cable_routes_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scroll = ttk.Scrollbar(routes_frame, orient=tk.VERTICAL, command=self.cable_routes_tree.yview)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.cable_routes_tree.configure(yscrollcommand=scroll.set)
        self.cable_routes_tree.bind('<<TreeviewSelect>>', self._on_cable_route_selected)
        ttk.Button(routes_page, text='Calculate / refresh routes',
                   command=self._calculate_and_show_cable_routes).pack(fill=tk.X, pady=(8, 3))
        ttk.Button(routes_page, text='Export route inventory CSV',
                   command=self._export_cable_routes_csv).pack(fill=tk.X)
        ttk.Label(routes_page, text='Network uses drawn paths; area uses walkable space; '
                  'direct is an orthogonal fallback. Failed routes need a scale, an assigned block and a placed inverter.',
                  wraplength=340, foreground='#546E7A').pack(anchor='w', pady=(8, 0))

        ttk.Label(routes_page, text='Drawn cable paths', font=('Arial', 10, 'bold')).pack(anchor='w', pady=(12, 2))
        self.cable_paths_tree = ttk.Treeview(routes_page, columns=('points', 'length'),
                                             show='tree headings', height=5, selectmode='browse')
        for key, title, width in (('#0', 'Path', 95), ('points', 'Points', 70),
                                  ('length', 'Length (m)', 100)):
            self.cable_paths_tree.heading(key, text=title)
            self.cable_paths_tree.column(key, width=width, minwidth=50)
        self.cable_paths_tree.pack(fill=tk.X, pady=(0, 4))
        self.cable_paths_tree.bind('<<TreeviewSelect>>', self._on_cable_path_tree_selected)

        ttk.Label(sizing_page, text='DC voltage-drop estimate',
                  font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 8))
        form = ttk.Frame(sizing_page)
        form.pack(fill=tk.X)
        fields = (
            ('Current (A)', 'current_a'), ('DC voltage (V)', 'voltage_v'),
            ('One-way length (m)', 'length_m'),
            ('Resistivity (Ω·mm²/m)', 'resistivity'),
            ('Maximum voltage drop (%)', 'target_drop_pct'),
        )
        self.cable_entries = {}
        for row, (label, key) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky='w', pady=4)
            entry = ttk.Entry(form, width=13)
            entry.insert(0, str(self.cable_calc_params.get(key, '')))
            entry.grid(row=row, column=1, sticky='e', padx=(8, 0), pady=4)
            entry.bind('<FocusOut>', lambda event: self._capture_cable_inputs())
            self.cable_entries[key] = entry
        ttk.Button(sizing_page, text='Calculate cross-section',
                   command=self._compute_cable_size).pack(fill=tk.X, pady=(10, 5))
        ttk.Button(sizing_page, text='Use longest calculated route',
                   command=self._use_longest_cable_route).pack(fill=tk.X)
        self.lbl_cable_result = ttk.Label(sizing_page, text='', wraplength=330,
                                          foreground='#154C79', justify=tk.LEFT)
        self.lbl_cable_result.pack(anchor='w', pady=(12, 5))
        ttk.Label(sizing_page, text='Voltage drop only: confirm ampacity, temperature, installation '
                  'conditions and protective devices separately.', wraplength=330,
                  foreground='#546E7A').pack(anchor='w', pady=(5, 0))

        ttk.Label(notes_page, text='Project notes', font=('Arial', 10, 'bold')).pack(anchor='w', pady=(0, 5))
        notes_frame = ttk.Frame(notes_page)
        notes_frame.pack(fill=tk.BOTH, expand=True)
        self.txt_notes = tk.Text(notes_frame, wrap=tk.WORD, width=35, height=18)
        self.txt_notes.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        note_scroll = ttk.Scrollbar(notes_frame, orient=tk.VERTICAL, command=self.txt_notes.yview)
        note_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_notes.configure(yscrollcommand=note_scroll.set)
        self.txt_notes.bind('<<Modified>>', self._on_notes_changed)
        self.txt_notes.edit_modified(False)
        self._refresh_cabling_paths()
        self._refresh_cable_route_table()

    def _capture_cable_inputs(self):
        """Store valid edits so tab switches and project saves keep the current input."""
        try:
            values = {key: float(entry.get().strip().replace(',', '.'))
                      for key, entry in self.cable_entries.items()}
            calculate_dc_cable_size(**values)
        except (ValueError, TypeError):
            return False
        changed = self.cable_calc_params != values
        self.cable_calc_params = values
        if changed and hasattr(self, 'string_sizing_tree'):
            self._refresh_string_sizing_table()
        return True

    def _compute_cable_size(self):
        if not self._capture_cable_inputs():
            self.lbl_cable_result.configure(text='Enter positive numeric values; voltage drop must be below 100%.')
            return
        result = calculate_dc_cable_size(**self.cable_calc_params)
        section = result['recommended_mm2']
        if section is None:
            recommendation = 'Beyond listed standard sizes (up to 240 mm²); assess another design.'
        else:
            recommendation = (f'Recommended standard cross-section: {section:g} mm²\n'
                              f'Estimated voltage drop: {result["actual_drop_pct"]:.2f} % '
                              f'(limit {result["target_drop_pct"]:g} %)')
        self.lbl_cable_result.configure(text=f'Minimum calculated section: {result["minimum_mm2"]:.2f} mm²\n'
                                             + recommendation)

    def _on_notes_changed(self, event=None):
        if not self.txt_notes.edit_modified():
            return
        self.project_notes = self.txt_notes.get('1.0', 'end-1c')
        self.txt_notes.edit_modified(False)

    def _refresh_notes(self):
        self.txt_notes.delete('1.0', tk.END)
        self.txt_notes.insert('1.0', self.project_notes)
        self.txt_notes.edit_modified(False)
        for key, entry in self.cable_entries.items():
            entry.delete(0, tk.END)
            entry.insert(0, str(self.cable_calc_params.get(key, '')))
        self.lbl_cable_result.configure(text='')
        self._refresh_cabling_paths()
        self._refresh_cable_route_table()

    def _refresh_cabling_paths(self):
        if not hasattr(self, 'cable_paths_tree'):
            return
        tree = self.cable_paths_tree
        tree.delete(*tree.get_children())
        for index, path in enumerate(self.cable_paths):
            points = path.get('points', [])
            distance_px = sum(math.dist(a, b) for a, b in zip(points, points[1:]))
            length = f'{distance_px / self.px_per_mm / 1000:.1f}' if self.px_per_mm > 0 else '—'
            tree.insert('', tk.END, iid=f'path::{index}', text=f'Path {path.get("id", index + 1)}',
                        values=(len(points), length))
        active = getattr(self, 'active_cable_path_idx', None)
        if active is not None and tree.exists(f'path::{active}'):
            tree.selection_set(f'path::{active}')

    def _invalidate_cable_routes(self):
        self.cable_network_routes = {}
        self.cable_routes_calculated = False
        self.show_cable_network_routes = False
        self.selected_cable_route = None
        self._refresh_cable_route_table()

    def _on_cable_path_tree_selected(self, event=None):
        selection = self.cable_paths_tree.selection()
        if not selection:
            return
        index = int(selection[0].split('::', 1)[1])
        if index == self.active_cable_path_idx:
            return
        self.active_cable_path_idx = index
        self._update_cable_path_combo()
        self.draw_grid()

    def _refresh_cable_route_table(self, summary=None):
        if not hasattr(self, 'cable_routes_tree'):
            return
        tree = self.cable_routes_tree
        tree.delete(*tree.get_children())
        sorted_ids = [sid for sid in self._get_sorted_string_keys() if self.strings.get(sid)]
        failed = []
        for sid in sorted_ids:
            route = self.cable_network_routes.get(sid)
            if hasattr(self,'get_two_pole_route') and not self.get_two_pole_route(sid):route=None
            assignment = self.string_mppt_assignment.get(sid, {})
            block = assignment.get('block') or self._get_string_block(sid) or '—'
            mppt = assignment.get('mppt', '—')
            length = f'{route["length_m"]:.2f}' if route else '—'
            method = route.get('route_kind', '—') if route else 'Unavailable'
            if not route:
                failed.append(sid)
            tree.insert('', tk.END, iid=f'route::{sid}', text=string_label(sid),
                        values=(block, mppt, length, method))
        if not self.cable_routes_calculated:
            status = f'{len(sorted_ids)} strings; calculate routes to see their lengths.'
        elif not self.cable_network_routes:
            status = f'0 / {len(sorted_ids)} routes available.'
            if failed:
                status += f' Check scale, blocks and inverter placement: {", ".join(failed)}'
        else:
            routes = self.cable_network_routes.values()
            status = (f'{len(self.cable_network_routes)} / {len(sorted_ids)} routes  |  '
                      f'Total {sum(r["length_m"] for r in routes):.1f} m  |  '
                      f'Longest {max(r["length_m"] for r in self.cable_network_routes.values()):.1f} m')
            if failed:
                status += f'  |  Unavailable: {", ".join(failed)}'
        self.lbl_routes_summary.configure(text=status)
        if hasattr(self, "string_sizing_tree"):
            self._refresh_string_sizing_table()

    def _on_cable_route_selected(self, event=None):
        selection = self.cable_routes_tree.selection()
        self.selected_cable_route = selection[0].split('::', 1)[1] if selection else None
        self.draw_grid()

    def _calculate_and_show_cable_routes(self):
        if not self._capture_cable_inputs():
            messagebox.showerror('Cabling', 'Correct the DC sizing inputs before calculating routes.')
            return
        summary = self.compute_all_cable_routes()
        self.cable_routes_calculated = True
        self.show_cable_network_routes = bool(summary['ok'])
        self._refresh_cable_route_table(summary)
        if summary.get('failed') and getattr(self,'_last_route_error',None):
            messagebox.showwarning('Incomplete cable routes', self._last_route_error)
        self.draw_grid()

    def _hide_cable_routes(self):
        self.show_cable_network_routes = False
        self.draw_grid()

    def _on_click_trace_cables(self):
        """Retained for old callbacks; the new toolbar uses the route inventory."""
        if self.show_cable_network_routes:
            self._hide_cable_routes()
        else:
            self._calculate_and_show_cable_routes()

    def _use_longest_cable_route(self):
        if not self.cable_network_routes:
            self._calculate_and_show_cable_routes()
        if not self.cable_network_routes:
            messagebox.showinfo('Cable sizing', 'No calculable string-to-inverter route.')
            return
        length = max(route['length_m'] for route in self.cable_network_routes.values()) / 2
        entry = self.cable_entries['length_m']
        entry.delete(0, tk.END)
        entry.insert(0, f'{length:.3f}')
        self._compute_cable_size()

    def _export_cable_routes_csv(self):
        # Recompute so the export reflects recent string, path and inverter changes.
        self.compute_all_cable_routes()
        self.cable_routes_calculated = True
        self._refresh_cable_route_table()
        filename = filedialog.asksaveasfilename(defaultextension='.csv',
                                                filetypes=[('CSV files', '*.csv')],
                                                title='Export cable route inventory')
        if not filename:
            return
        try:
            with open(filename, 'w', newline='', encoding='utf-8-sig') as output:
                writer = csv.writer(output, delimiter=';')
                writer.writerow(['String', 'Block', 'MPPT', 'Panels', 'A+B length (m)', 'Method', 'Status', 'Pole A (m)', 'Pole B (m)', 'Section (mm2)', 'Voltage drop (%)', 'Mass (kg)'])
                for sid in self._get_sorted_string_keys():
                    if not self.strings.get(sid):
                        continue
                    route = self.cable_network_routes.get(sid)
                    assignment = self.string_mppt_assignment.get(sid, {})
                    writer.writerow([sid, assignment.get('block') or self._get_string_block(sid) or '',
                                     assignment.get('mppt', ''), len(self.strings.get(sid, [])),
                                     f'{route["length_m"]:.3f}' if route else '',
                                     route.get('route_kind', '') if route else '',
                                     route.get('status','Preliminary') if route else 'Unavailable',
                                     route.get('pole_a_m','') if route else '',route.get('pole_b_m','') if route else '',
                                     route.get('working_section_mm2','') if route else '',
                                     route.get('drop_at_working_section_pct','') if route else '',
                                     route.get('mass_kg','') if route else ''])
            messagebox.showinfo('Cable routes', f'Inventory exported:\n{filename}')
        except OSError as exc:
            messagebox.showerror('Cable routes', str(exc))
