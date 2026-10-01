"""Classe principale de l'application : assemble tous les mixins et contient
l'initialisation de l'etat (self.xxx) de l'application."""

import tkinter as tk
from tkinter import messagebox
import os

try:
    from PIL import Image, ImageDraw, ImageTk, ImageFont
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from mixins.installation_geometry import InstallationGeometryMixin
from mixins.diagram_editor import DiagramEditorMixin
from mixins.project_workspace import ProjectWorkspaceMixin
from mixins.editor_interactions import EditorInteractionsMixin
from mixins.project_integrity import ProjectIntegrityMixin
from mixins.workspace_improvements import WorkspaceImprovementsMixin
from mixins.spreadsheet_interactions import SpreadsheetInteractionsMixin
from mixins.detailed_electrical_ui import DetailedElectricalUIMixin
from mixins.responsive_ui import ResponsiveUIMixin
from mixins.self_consumption_ui import SelfConsumptionMixin
from mixins.hourly_chart_ui import HourlyChartMixin
from mixins.two_pole_cables import TwoPoleCablesMixin
from constants import STRING_COLORS, BLOCK_COLORS
from mixins.ui_builders import UIBuildersMixin
from mixins.paths_tools import PathsToolsMixin
from mixins.equipment_tools import EquipmentToolsMixin
from mixins.shadow_tools import ShadowToolsMixin
from mixins.zone_tools import ZoneToolsMixin
from mixins.canvas_grid import CanvasGridMixin
from mixins.stringing_tools import StringingToolsMixin
from mixins.project_io import ProjectIOMixin
from mixins.material_tools import MaterialToolsMixin, default_material_categories
from mixins.diagram_tools import DiagramToolsMixin
from mixins.notes_tools import NotesToolsMixin
from mixins.inverter_tools import InverterToolsMixin
from mixins.cable_network import CableNetworkMixin
from mixins.spreadsheet_tools import SpreadsheetToolsMixin


from mixins.safe_project import SafeProjectMixin

class PVLayoutRibbonApp(
    SafeProjectMixin,
    DiagramEditorMixin,
    ProjectWorkspaceMixin,
    EditorInteractionsMixin,
    InstallationGeometryMixin,
    WorkspaceImprovementsMixin,
    DetailedElectricalUIMixin,
    SpreadsheetInteractionsMixin,
    ResponsiveUIMixin,
    ProjectIntegrityMixin,
    TwoPoleCablesMixin,
    SelfConsumptionMixin,
    HourlyChartMixin,
    UIBuildersMixin,
    PathsToolsMixin,
    EquipmentToolsMixin,
    ShadowToolsMixin,
    ZoneToolsMixin,
    CanvasGridMixin,
    StringingToolsMixin,
    ProjectIOMixin,
    MaterialToolsMixin,
    DiagramToolsMixin,
    NotesToolsMixin,
    InverterToolsMixin,
    CableNetworkMixin,
    SpreadsheetToolsMixin,
):
    def __init__(self, root):
        self.root = root
        from project_store import MODEL_DEFAULTS
        self.model_settings=dict(MODEL_DEFAULTS)
        self.equipment_links={}
        self.panel_uids={}
        self.layout_geometry={}
        self.connection_review_required=[]
        self.shadow_source_signature=None
        self.root.title('PV Layout and Stringing — R14 · 30 September 2026')
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        self.root.minsize(min(480, screen_width), min(320, screen_height))
        window_width = min(1440, max(320, screen_width - 80), screen_width)
        window_height = min(900, max(240, screen_height - 80), screen_height)
        self.root.geometry(f"{window_width}x{window_height}")

        if not HAS_PIL:
            messagebox.showwarning(
                'Missing library',
                "Pillow (PIL) is not installed. Install it with pip install pillow "
                "to load roof images and export the full JPG."
            )

        # ----------------------------------------------------
        # Projet & Dimensions
        # ----------------------------------------------------

        self.project_name = 'New Project'
        self.current_project_filepath = None

        self.panel_width_mm = 1000.0
        self.panel_height_mm = 1700.0

        # ----------------------------------------------------
        # Zoom global
        # ----------------------------------------------------
        self.zoom_level = 1.0  # 1.0 = 100%

        # ----------------------------------------------------
        # Données de Toiture & Échelle (Onglet 2)
        # ----------------------------------------------------

        self.roof_image_path = None
        self.roof_pil_img = None
        self.roof_tk_img = None

        self.scale_p1 = None  # (x, y) px image originale
        self.scale_p2 = None  # (x, y) px image originale
        self.scale_length_mm = 0.0
        self.px_per_mm = 0.0  # Échelle calculée (px image originale / mm)

        # Outil de mesure (Liste pour gérer plusieurs mesures)
        self.measures = []  # Ex: [((x1, y1), (x2, y2)), ...]
        self.measure_drag_idx = None
        self.measure_p1 = None
        self.measure_p2 = None

        self.roof_zones = []
        self.active_zone_idx = None
        self.selected_zone_indices = set()  # Multisélection de zones

        self.roof_mode = "select"  # "select", "scale", "zone", "measure"
        self.temp_draw_start = None

        # ----------------------------------------------------
        # Chemins : polygone de zone de câblage disponible (Onglet Chemins)
        # ----------------------------------------------------
        self.roof_polygons = []  # [{"id": n, "points": [(x, y), ...] px image d'origine}]
        self.active_polygon_idx = None
        self.path_mode = "select"  # "select", "draw_polygon", "measure_distance", "draw_cable_path"
        self.temp_polygon_points = []  # points (px image d'origine) du polygone en cours de tracé
        self.polygon_drag_mode = None  # None ou "move"
        self.polygon_drag_start_pt = None
        self.polygon_drag_initial_points = None
        self.distance_markers = []  # [{"point": (x,y), "nearest_point": (x,y), "label": str, "distance_mm": float}]
        self.roof_overlay_tk_img = None  # référence PhotoImage de la zone disponible coloriée
        self.zone_drag_mode = None  # None, "move", "resize_tl", "resize_tr", "resize_bl", "resize_br"
        self.zone_drag_start_pt = None
        self.zone_drag_initial_rect = None
        self.zone_drag_initial_rects = {}
        self.drag_occurred = False
        self.pending_toggle_zone = None
        self.pending_single_select_zone = None

        # ----------------------------------------------------
        # Chemins de câbles : réseau de polylignes pour le routage préférentiel
        # des câbles (Dijkstra), tracé dans le même onglet "Chemins"
        # ----------------------------------------------------
        self.cable_paths = []  # [{"id": n, "points": [(x, y), ...] px image d'origine}]
        self.active_cable_path_idx = None
        self.temp_cable_path_points = []  # points en cours de tracé

        # ----------------------------------------------------
        # Ombre du Pylône (Onglet Ombre Pylône)
        # ----------------------------------------------------
        self.pylon_img_pos = None        # (x, y) px image d'origine - position du pylône
        self.pylon_ref_img_pos = None    # (x, y) px image d'origine - point de référence
        self.pylon_height_mm = 3000.0
        self.pylon_width_mm = 300.0
        # Opacité du pylône : 1.0 = plein (opaque), valeur < 1.0 = structure
        # en treillis laissant passer une partie de la lumière.
        self.pylon_opacity = 1.0
        self.north_offset_deg = 0.0      # orientation du Nord (° horaire depuis le haut de l'image)

        self.solar_latitude = 43.7384
        self.solar_longitude = 7.4246
        self.solar_utc_offset = 1.0
        self.solar_day = 21
        self.solar_month = 6
        self.solar_hour = 12.0
        self.panel_pmax_w = 450.0
        self.panel_efficiency_pct = 22.0
        self.panel_temp_coeff_pct = -0.30
        self.panel_noct_c = 45.0

        self.shadow_mode = "select"      # "select", "place_pylon", "place_ref"
        self.shadow_result = {
            "elevation": None, "azimuth": None, "shadowed": set(),
            "shadow_pct": {}, "shadow_polygons": [], "segments": [], "message": None
        }
        self.shadow_simulation_results = {}
        self.active_shadow_zone_idx = None
        self.shadow_sim_start_day = 21
        self.shadow_sim_start_month = 6
        self.shadow_sim_end_day = 21
        self.shadow_sim_end_month = 6
        self.shadow_sim_start_hour = 8.0
        self.shadow_sim_end_hour = 18.0
        self.shadow_sim_step_min = 15

        # Zoom pour la heatmap
        self.heatmap_zoom_level = 1.0

        # ----------------------------------------------------
        # Données structurelles (Layout & Stringing)
        # ----------------------------------------------------

        self.panels = {}        # {(row, col): number}
        self.panel_tilt_deg = 8.0
        self.panel_azimuth_deg = 180.0
        self.panel_orientations = {}  # (row, col): {tilt_deg, azimuth_deg}
        self.selected_panel_coords = set()
        self.panel_blocks = {}   # {(row, col): "Block_Name"}
        self.blocks = {}         # {"Block_Name": {"color": "#HEX"}}

        self.strings = {
            "String 1": []
        }                        # {"String 1": [(r, c), ...]}
        self.manual_strings = set()  # Noms des strings éditées ou créées manuellement

        self.active_string_id = "String 1"
        self.active_block_name = None

        # Répartition des strings dans les MPPT : {string_id: {"block": nom_bloc, "mppt": n° mppt (1-based)}}
        self.string_mppt_assignment = {}
        self.var_dim_mppt_strings = tk.BooleanVar(value=False)
        self._equip_drag_item = None

        # Drag and drop listbox
        self.drag_start_index = None

        # ----------------------------------------------------
        # Onduleurs placés sur le plan (Onglet Layout & Blocs)
        # ----------------------------------------------------
        # Chaque onduleur placé est rattaché à un Bloc existant (self.blocks) :
        # {block_name: {"x": img_x, "y": img_y, "material_row": {...}}}
        self.inverter_positions = {}
        self.layout_mode = "select"  # "select" ou "place_inverter"
        self.pending_inverter_placement = None  # {"block_name": str, "material_row": dict}

        # ----------------------------------------------------
        # Paramètres d'affichage Canvas
        # ----------------------------------------------------

        self.cell_size_px = 40
        self.margin_cells = 15
        self.last_drag_cell = None

        self.min_r = -self.margin_cells
        self.min_c = -self.margin_cells
        self.total_w = 1
        self.total_h = 1

        self.projects_dir = "pv_projects"
        os.makedirs(self.projects_dir, exist_ok=True)
        self._load_ui_preferences()

        # ----------------------------------------------------
        # Fiche Matériel (Onglet Matériel)
        # ----------------------------------------------------
        self.material_categories = default_material_categories()

        # ----------------------------------------------------
        # Notes (Onglet Notes)
        # ----------------------------------------------------
        self._init_notes_state()

        # ----------------------------------------------------
        # Schéma Unifilaire (Onglet Schéma Unifilaire)
        # ----------------------------------------------------
        self.diagram_nodes = {}       # {node_id: {"type", "label", "x", "y"}}
        self.diagram_links = []       # [{"a": id, "b": id, "auto": bool}]
        self.diagram_next_custom_id = 1
        self.diagram_selected_node = None
        self.diagram_drag_node = None
        self.diagram_drag_start = None
        self.diagram_drag_orig = None
        self.diagram_link_mode = False
        self.diagram_link_first = None
        self.diagram_link_style = 'solid'
        self.diagram_electrical_specs = {}
        self.diagram_show_electrical = False

        # ----------------------------------------------------
        # Feuille de calcul (Onglet Matériel, zone principale)
        # ----------------------------------------------------
        self._init_spreadsheet_state()

        # ----------------------------------------------------
        # Construction Interface
        # ----------------------------------------------------

        self._init_energy_state()
        self._build_root_scroller()
        self._build_ribbon_ui()
        self._build_self_consumption_tab()
        self._build_main_area()
        self._install_responsive_ui()
        self._install_home()

        # ----------------------------------------------------
        # Sauvegarde : raccourci clavier et sauvegarde automatique
        # ----------------------------------------------------
        self.root.bind_all("<Control-s>", self._on_ctrl_s)
        self.root.bind_all("<Control-S>", self._on_ctrl_s)
        self.root.bind_all("<Escape>", self._on_escape_key)

        self.autosave_interval_ms = 5 * 60 * 1000  # 5 minutes
        self.root.after(self.autosave_interval_ms, self._auto_save)
        self._install_project_guard()

    # ========================================================
    # UTILITAIRES & ZOOM
    # ========================================================
