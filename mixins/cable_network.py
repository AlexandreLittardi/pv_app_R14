"""Réseau de chemins de câbles (self.cable_paths, tracé dans l'onglet "Chemins")
et calcul de la longueur de câble entre une string et l'onduleur de son bloc.

Rassemblement par zone (cheminement "pro") :
Les câbles des strings d'une même zone de toiture ne partent pas chacun en
ligne droite vers l'onduleur. Ils sont d'abord routés jusqu'à un point de
rassemblement unique par zone (point de sortie), comme un tirage de câbles
réel le long des rails jusqu'à un même passage de toit. De ce point de
rassemblement part un tronc commun vers l'onduleur, calculé une seule fois
par (zone, onduleur) : toutes les strings de la zone empruntent donc
exactement le même tracé sur ce tronçon (effet de faisceau à l'affichage).

Le point de rassemblement de chaque zone est soit placé manuellement par
l'utilisateur (onglet Chemins, persisté dans roof_zones[i]["gather_point"]),
soit calculé automatiquement : le point du bord de la zone le plus proche de
l'onduleur concerné.

Cheminement à angle droit ("coudes") :
Comme un vrai tirage de câble (conduits, chemins de câbles, rails de
fixation), aucun tronçon n'est jamais tracé en diagonale : chaque segment
est horizontal ou vertical, et les changements de direction se font par des
coudes à 90°. Ceci s'applique au segment local (string -> point de
rassemblement), au tronc commun en secours "ligne directe", et au routage
par zone de passage (grille 4-directions, sans coupe en diagonale).

Ordre de priorité du routage du tronc commun (point de rassemblement -> onduleur) :
1. Plus court chemin le long du réseau de chemins de câbles tracé à la main
   (self.cable_paths), via Dijkstra sur un graphe de segments.
2. À défaut (point(s) non connecté(s) au réseau) : routage automatique par
   évitement d'obstacles sur la zone de passage tracée dans l'onglet Chemins
   (self.roof_polygons moins self.roof_zones), par grille rasterisée
   4-directions (horizontal/vertical uniquement) + Dijkstra + simplification
   des points alignés (sans jamais raccourcir en diagonale).
3. En dernier recours (aucune zone de passage tracée non plus) : chemin à
   un coude (deux segments perpendiculaires) entre les deux points.
"""

import heapq
import math
from array import array
from tkinter import messagebox

try:
    from PIL import Image, ImageDraw
    HAS_PIL_CN = True
except ImportError:
    HAS_PIL_CN = False

_NET_ROUTE_COLORS = ("#D84315", "#1565C0", "#2E7D32", "#6A1B9A", "#EF6C00", "#00838F", "#AD1457")

# Déplacements 4-directions uniquement (pas de diagonale) : le routage par
# grille doit lui aussi ne produire que des coudes à 90°.
_GRID_NEIGHBORS = (
    (1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
)
_MAX_GRID_DIM = 900


class CableNetworkMixin:
    # ========================================================
    # RÉSEAU DE CHEMINS TRACÉ À LA MAIN (priorité 1)
    # ========================================================

    def _build_cable_network_graph(self):
        """Construit un graphe {noeud: [(voisin, poids_px), ...]} à partir de
        self.cable_paths (coordonnées image d'origine). Les points d'une même
        polyligne sont reliés à leurs voisins immédiats ; les segments de
        polylignes différentes qui se croisent sont reliés par un nœud
        d'intersection, pour permettre à Dijkstra de changer de chemin."""
        graph = {}

        def _key(pt):
            return (round(pt[0], 2), round(pt[1], 2))

        def _add_node(pt):
            k = _key(pt)
            graph.setdefault(k, [])
            return k

        def _add_edge(a, b):
            if a == b:
                return
            w = math.hypot(a[0] - b[0], a[1] - b[1])
            graph[a].append((b, w))
            graph[b].append((a, w))

        all_segments = []
        for path in self.cable_paths:
            pts = [tuple(p) for p in path.get("points", [])]
            for i in range(len(pts) - 1):
                a = _add_node(pts[i])
                b = _add_node(pts[i + 1])
                _add_edge(a, b)
                all_segments.append((pts[i], pts[i + 1]))

        n = len(all_segments)
        for i in range(n):
            for j in range(i + 1, n):
                inter = self._segment_intersection(all_segments[i], all_segments[j])
                if inter is None:
                    continue
                ik = _add_node(inter)
                for seg in (all_segments[i], all_segments[j]):
                    a = _add_node(seg[0])
                    b = _add_node(seg[1])
                    _add_edge(a, ik)
                    _add_edge(ik, b)

        return graph

    @staticmethod
    def _segment_intersection(seg1, seg2):
        """Retourne le point d'intersection de deux segments, ou None s'ils ne
        se croisent pas (ou sont parallèles)."""
        (x1, y1), (x2, y2) = seg1
        (x3, y3), (x4, y4) = seg2

        d = (x2 - x1) * (y4 - y3) - (y2 - y1) * (x4 - x3)
        if abs(d) < 1e-9:
            return None

        t = ((x3 - x1) * (y4 - y3) - (y3 - y1) * (x4 - x3)) / d
        u = ((x3 - x1) * (y2 - y1) - (y3 - y1) * (x2 - x1)) / d

        if -1e-6 <= t <= 1 + 1e-6 and -1e-6 <= u <= 1 + 1e-6:
            return (x1 + t * (x2 - x1), y1 + t * (y2 - y1))
        return None

    def _snap_point_to_network(self, graph, pt):
        """Projette pt sur le segment le plus proche du réseau de chemins de
        câbles, insère un nœud de projection relié aux deux extrémités du
        segment, puis un nœud pour pt relié à cette projection. Retourne la
        clé de nœud représentant pt, ou None si le réseau est vide."""
        # Split the CURRENT graph edge so two terminals projected on the same
        # tray can take the direct interval between them, not a detour to an end.
        original_segments=[(tuple(a),tuple(b)) for path in self.cable_paths
                           for a,b in zip(path.get('points',[]),path.get('points',[])[1:])]
        best=None
        for a,neighbors in list(graph.items()):
            for b,_ in neighbors:
                if a>=b:continue
                on_tray=any(self._nearest_point_on_segment(*a,*u,*v)[2]<.02 and
                            self._nearest_point_on_segment(*b,*u,*v)[2]<.02
                            for u,v in original_segments)
                if not on_tray:continue
                nx,ny,dist=self._nearest_point_on_segment(pt[0],pt[1],*a,*b)
                if best is None or dist<best[0]:best=(dist,(nx,ny),a,b)
        if best is None:return None
        _,projection,a,b=best
        key=(round(projection[0],4),round(projection[1],4))
        # Reuse the exact graph endpoint when the projection coincides with it.
        if math.dist(key,a)<1e-3:key=a
        elif math.dist(key,b)<1e-3:key=b
        if key not in (a,b):
            graph[a]=[(n,w) for n,w in graph[a] if n!=b]
            graph[b]=[(n,w) for n,w in graph[b] if n!=a]
            graph.setdefault(key,[])
            for end in (a,b):
                distance=math.dist(key,end)
                graph[key].append((end,distance));graph[end].append((key,distance))
        terminal=(round(pt[0],4),round(pt[1],4))
        if terminal!=key:
            distance=math.dist(terminal,key)
            graph.setdefault(terminal,[]).append((key,distance));graph[key].append((terminal,distance))
        return terminal

    @staticmethod
    def _dijkstra(graph, start, end):
        """Plus court chemin entre deux nœuds du graphe de chemins tracés.
        Retourne (distance_px, chemin) ou (None, None)."""
        if start not in graph or end not in graph:
            return None, None
        if start == end:
            return 0.0, [start]

        dist = {start: 0.0}
        prev = {}
        visited = set()
        heap = [(0.0, start)]

        while heap:
            d, u = heapq.heappop(heap)
            if u in visited:
                continue
            visited.add(u)
            if u == end:
                break
            for v, w in graph.get(u, []):
                nd = d + w
                if nd < dist.get(v, math.inf):
                    dist[v] = nd
                    prev[v] = u
                    heapq.heappush(heap, (nd, v))

        if end not in dist:
            return None, None

        path = [end]
        while path[-1] != start:
            path.append(prev[path[-1]])
        path.reverse()
        return dist[end], path

    # ========================================================
    # ROUTAGE DE SECOURS : ZONE DE PASSAGE (priorité 2, évitement d'obstacles)
    # ========================================================

    def _build_walkable_grid(self):
        """Rasterise la zone de passage (polygones de l'onglet Chemins moins
        les zones de panneaux). Renvoie (grille bytearray, gw, gh, step_px)
        ou None si aucun polygone de passage n'est tracé, ou PIL indisponible."""
        if not HAS_PIL_CN or not self.roof_pil_img:
            return None
        if not any(len(p["points"]) >= 3 for p in getattr(self, "roof_polygons", [])):
            return None

        w, h = self.roof_pil_img.size
        step = max(1, math.ceil(max(w, h) / _MAX_GRID_DIM))
        gw, gh = max(1, math.ceil(w / step)), max(1, math.ceil(h / step))
        mask = Image.new("L", (gw, gh), 0)
        draw = ImageDraw.Draw(mask)
        for poly in self.roof_polygons:
            if len(poly["points"]) >= 3:
                draw.polygon([(x / step, y / step) for x, y in poly["points"]], fill=255)
        for z in getattr(self, "roof_zones", []):
            x1, y1 = min(z["x1"], z["x2"]) / step, min(z["y1"], z["y2"]) / step
            x2, y2 = max(z["x1"], z["x2"]) / step, max(z["y1"], z["y2"]) / step
            draw.rectangle([x1, y1, x2, y2], fill=0)
        return bytearray(mask.tobytes()), gw, gh, step

    @staticmethod
    def _nearest_walkable_cell(grid, gw, gh, gx, gy):
        """Cellule de passage la plus proche de (gx, gy) (recherche en anneaux)."""
        gx = min(max(int(gx), 0), gw - 1)
        gy = min(max(int(gy), 0), gh - 1)
        if grid[gy * gw + gx]:
            return gx, gy
        for r in range(1, max(gw, gh)):
            best, best_d = None, None
            for dy in range(-r, r + 1):
                y = gy + dy
                if y < 0 or y >= gh:
                    continue
                xs = range(-r, r + 1) if abs(dy) == r else (-r, r)
                for dx in xs:
                    x = gx + dx
                    if 0 <= x < gw and grid[y * gw + x]:
                        d = dx * dx + dy * dy
                        if best_d is None or d < best_d:
                            best, best_d = (x, y), d
            if best:
                return best
        return None

    @staticmethod
    def _grid_dijkstra(grid, gw, gh, src):
        n = gw * gh
        dist = array("d", [float("inf")]) * n
        parent = array("i", [-1]) * n
        s = src[1] * gw + src[0]
        dist[s] = 0.0
        heap = [(0.0, s)]
        while heap:
            d, u = heapq.heappop(heap)
            if d > dist[u]:
                continue
            uy, ux = divmod(u, gw)
            for dx, dy, c in _GRID_NEIGHBORS:
                vx, vy = ux + dx, uy + dy
                if vx < 0 or vy < 0 or vx >= gw or vy >= gh:
                    continue
                v = vy * gw + vx
                if not grid[v]:
                    continue
                nd = d + c
                if nd < dist[v]:
                    dist[v] = nd
                    parent[v] = u
                    heapq.heappush(heap, (nd, v))
        return dist, parent

    @staticmethod
    def _grid_smooth_path(cells):
        """Simplifie le chemin en grille en ne gardant que les points de
        coude (changement de direction horizontale/verticale). Comme le
        déplacement en grille est désormais strictement 4-directions
        (_GRID_NEIGHBORS), cette simplification ne fait que fusionner les
        pas consécutifs alignés — elle ne raccourcit jamais en diagonale."""
        if len(cells) <= 2:
            return cells
        out = [cells[0]]
        prev_dir = None
        for i in range(1, len(cells)):
            direction = (cells[i][0] - cells[i - 1][0], cells[i][1] - cells[i - 1][1])
            if prev_dir is not None and direction != prev_dir:
                out.append(cells[i - 1])
            prev_dir = direction
        out.append(cells[-1])
        return out

    def _route_via_walkable_area(self, point_a, point_b):
        """Route point_a -> point_b en évitant les obstacles, via la zone de
        passage tracée dans l'onglet Chemins (grille 4-directions : le
        résultat ne comporte que des segments horizontaux/verticaux, jamais
        de diagonale). Retourne (longueur_mm, points) ou (None, None) si
        impossible (pas de zone tracée, ou points non reliés à la même
        composante de passage)."""
        built = self._build_walkable_grid()
        if built is None:
            return None, None
        grid, gw, gh, step = built

        cell_a = self._nearest_walkable_cell(grid, gw, gh, point_a[0] // step, point_a[1] // step)
        cell_b = self._nearest_walkable_cell(grid, gw, gh, point_b[0] // step, point_b[1] // step)
        if cell_a is None or cell_b is None:
            return None, None

        dist, parent = self._grid_dijkstra(grid, gw, gh, cell_a)
        idx_b = cell_b[1] * gw + cell_b[0]
        if dist[idx_b] == float("inf"):
            return None, None

        cells, u = [], idx_b
        while u != -1:
            cells.append((u % gw, u // gw))
            u = parent[u]
        cells.reverse()
        cells = self._grid_smooth_path(cells)
        cell_centers = [((cx + 0.5) * step, (cy + 0.5) * step) for cx, cy in cells]

        # Raccordement point_a/point_b <-> premier/dernier centre de cellule
        # lui aussi en coude (jamais en diagonale), au cas où le point exact
        # ne soit pas centré sur sa cellule.
        pts = self._orthogonal_points(point_a, cell_centers[0])[:-1] \
            + cell_centers \
            + self._orthogonal_points(cell_centers[-1], point_b)[1:]

        length_px = sum(math.hypot(pts[k + 1][0] - pts[k][0], pts[k + 1][1] - pts[k][1])
                        for k in range(len(pts) - 1))
        return length_px / self.px_per_mm, [list(p) for p in pts]

    @staticmethod
    def _orthogonal_points(p1, p2):
        """Chemin à un coude (deux segments perpendiculaires) entre p1 et
        p2, comme un tirage de câble réel : jamais de diagonale. Si p1 et p2
        sont déjà alignés horizontalement ou verticalement, renvoie
        directement le segment simple (aucun coude nécessaire)."""
        x1, y1 = p1
        x2, y2 = p2
        if abs(x1 - x2) < 1e-6 or abs(y1 - y2) < 1e-6:
            return [list(p1), list(p2)]
        # On parcourt d'abord l'axe le plus long, pour un tracé plus naturel.
        if abs(x2 - x1) >= abs(y2 - y1):
            corner = (x2, y1)
        else:
            corner = (x1, y2)
        return [list(p1), list(corner), list(p2)]

    # ========================================================
    # LONGUEUR / ROUTE DE CÂBLE STRING -> ONDULEUR (point d'entrée)
    # ========================================================

    def compute_cable_route(self, string_id, terminal=-1):
        """Retourne (longueur_totale_mm, route_kind, points) pour la string
        -> l'onduleur de son bloc, EN PASSANT PAR LE POINT DE RASSEMBLEMENT
        de la zone du dernier panneau de la string (si la string est dans
        une zone connue) : les câbles d'une même zone convergent d'abord
        vers ce point (segment "local"), puis suivent un tronc commun
        jusqu'à l'onduleur (segment partagé par toutes les strings de la
        zone -> effet de faisceau). route_kind (parmi "network", "area",
        "direct") qualifie ce tronc commun. Retourne (None, None, None) si
        le calcul est impossible."""
        if getattr(self, "px_per_mm", 0) <= 0:
            return None, None, None

        assign = self.string_mppt_assignment.get(string_id)
        block_name = assign.get("block") if assign else self._get_string_block(string_id)
        if not block_name:
            return None, None, None

        inverter = self.inverter_positions.get(block_name)
        if not inverter:
            return None, None, None

        coords = self.strings.get(string_id, [])
        if not coords:
            return None, None, None

        string_point = self._get_panel_physical_center(coords[terminal])
        inverter_point = (inverter["x"], inverter["y"])

        zone_idx = self._get_panel_zone_idx(coords[terminal])
        gather_point = self._get_zone_gather_point(zone_idx, inverter_point) if zone_idx is not None else None
        trunk_start = gather_point if gather_point is not None else string_point

        trunk_mm, route_kind, trunk_points = None, None, None

        if self.cable_paths:
            graph = self._build_cable_network_graph()
            start_key = self._snap_point_to_network(graph, trunk_start)
            end_key = self._snap_point_to_network(graph, inverter_point)
            if start_key is not None and end_key is not None:
                dist_px, path = self._dijkstra(graph, start_key, end_key)
                if dist_px is not None:
                    trunk_mm, route_kind, trunk_points = dist_px / self.px_per_mm, "network", list(path)

        if trunk_mm is None:
            area_mm, area_points = self._route_via_walkable_area(trunk_start, inverter_point)
            if area_mm is not None:
                trunk_mm, route_kind, trunk_points = area_mm, "area", area_points

        if trunk_mm is None:
            trunk_points = self._orthogonal_points(trunk_start, inverter_point)
            trunk_len_px = sum(math.hypot(trunk_points[k + 1][0] - trunk_points[k][0],
                                          trunk_points[k + 1][1] - trunk_points[k][1])
                               for k in range(len(trunk_points) - 1))
            trunk_mm, route_kind = trunk_len_px / self.px_per_mm, "direct"

        if gather_point is not None:
            local_points = self._orthogonal_points(string_point, gather_point)
            local_len_px = sum(math.hypot(local_points[k + 1][0] - local_points[k][0],
                                          local_points[k + 1][1] - local_points[k][1])
                               for k in range(len(local_points) - 1))
            local_mm = local_len_px / self.px_per_mm
            points = local_points[:-1] + trunk_points
        else:
            local_mm = 0.0
            points = trunk_points

        total_mm = local_mm + trunk_mm
        return total_mm, route_kind, points

    def compute_cable_length_mm(self, string_id):
        """Compatibilité : retourne (longueur_mm, via_reseau_ou_zone) — utilisé
        par equipment_tools.py (_format_cable_length_label) et diagram_tools.py
        (generate_diagram_auto)."""
        length_mm, route_kind, _points = self.compute_cable_route(string_id)
        via_network = route_kind is not None and route_kind != "direct"
        return length_mm, via_network

    def compute_all_cable_routes(self):
        self.cable_network_routes = {}
        ok, failed = 0, []
        direct_count = 0
        total_m, max_m = 0.0, 0.0
        for sid in self._get_sorted_string_keys():
            if not self.strings.get(sid):
                continue
            length_mm, route_kind, points = self.compute_cable_route(sid)
            if length_mm is None:
                failed.append(sid)
                continue
            length_m = length_mm / 1000.0
            if route_kind == "direct":
                direct_count += 1
            self.cable_network_routes[sid] = {
                "points": points, "length_m": length_m,
                "route_kind": route_kind,
                "block": self._get_string_block(sid),
            }
            ok += 1
            total_m += length_m
            max_m = max(max_m, length_m)
        return {
            "ok": ok, "failed": failed, "total_m": total_m, "max_m": max_m,
            "direct_count": direct_count,
        }

    def _draw_cable_network_routes(self, zoom):
        """Dessine les câbles calculés par compute_all_cable_routes().
        Appelé depuis draw_grid() (canvas_grid.py)."""
        if not getattr(self, "show_cable_network_routes", False) or not self.cable_network_routes:
            return
        block_colors = {}
        selected = getattr(self, 'selected_cable_route', None)
        for sid, route in sorted(self.cable_network_routes.items(), key=lambda item: item[0] == selected):
            pts = route.get("points")
            if not pts or len(pts) < 2:
                continue
            block_name = route.get("block")
            if block_name not in block_colors:
                block_colors[block_name] = _NET_ROUTE_COLORS[len(block_colors) % len(_NET_ROUTE_COLORS)]
            color = block_colors[block_name]
            flat = [c * zoom for p in pts for c in p]
            # Pointillé réservé au tout dernier recours (ligne droite, aucune
            # zone de passage tracée) : "network" et "area" suivent un vrai
            # tracé, donc trait plein dans les deux cas.
            dash = (4, 3) if route.get("route_kind") == "direct" else ()
            is_selected = sid == selected
            display_color = '#D32F2F' if is_selected else color
            self.canvas.create_line(*flat, fill=display_color,
                                    width=4 if is_selected else 2, dash=dash)
            mx, my = pts[len(pts) // 2]
            label = f"🔌 {route['length_m']:.1f} m"
            if hasattr(self, "_draw_text_with_bg"):
                self._draw_text_with_bg(mx * zoom, my * zoom, label, fill=display_color)
            else:
                self.canvas.create_text(mx * zoom, my * zoom, text=label, fill=display_color,
                                        font=("Arial", 8, "bold"))

    # ========================================================
    # ZONES : GÉOMÉTRIE & POINT DE RASSEMBLEMENT DES CÂBLES
    # ========================================================

    @staticmethod
    def _dist_point_to_zone_rect(px, py, z):
        x1, y1 = min(z["x1"], z["x2"]), min(z["y1"], z["y2"])
        x2, y2 = max(z["x1"], z["x2"]), max(z["y1"], z["y2"])
        dx = max(x1 - px, 0.0, px - x2)
        dy = max(y1 - py, 0.0, py - y2)
        return math.hypot(dx, dy)

    def _get_panel_zone_idx(self, coord):
        """Retourne l'index (dans self.roof_zones) de la zone contenant ce
        panneau (r, c), ou None. Même logique de correspondance ligne <->
        zone que _get_panel_physical_center (stringing_tools.py)."""
        r, _c = coord
        for z_idx, zone in enumerate(self.roof_zones):
            rows = zone.get("rows", 0)
            row_base = zone.get("row_base", z_idx * 100)
            if row_base <= r < row_base + rows:
                return z_idx
        return None

    def _get_zone_gather_point(self, zone_idx, inverter_point):
        """Point où les câbles d'une même zone se rassemblent avant le tronc
        commun vers l'onduleur : position placée manuellement si définie
        (roof_zones[zone_idx]["gather_point"], "gather_point_manual" = True),
        sinon le point du bord de la zone le plus proche de l'onduleur
        (recalculé à la volée, donc toujours à jour si l'onduleur bouge).

        Limite connue : si une même zone alimente plusieurs onduleurs (cas
        rare, un même pan de toit scindé en plusieurs blocs), le point
        MANUEL est unique pour la zone (pas par onduleur) ; le point
        automatique, lui, reste correct dans tous les cas car recalculé pour
        chaque onduleur à l'appel."""
        if not (0 <= zone_idx < len(self.roof_zones)):
            return None
        zone = self.roof_zones[zone_idx]

        if zone.get("gather_point_manual") and zone.get("gather_point"):
            return tuple(zone["gather_point"])

        x1, y1 = min(zone["x1"], zone["x2"]), min(zone["y1"], zone["y2"])
        x2, y2 = max(zone["x1"], zone["x2"]), max(zone["y1"], zone["y2"])
        borders = [(x1, y1, x2, y1), (x2, y1, x2, y2), (x2, y2, x1, y2), (x1, y2, x1, y1)]
        best = None
        for (sx1, sy1, sx2, sy2) in borders:
            nx, ny, dist = self._nearest_point_on_segment(inverter_point[0], inverter_point[1], sx1, sy1, sx2, sy2)
            if best is None or dist < best[2]:
                best = (nx, ny, dist)
        return (best[0], best[1])

    def _place_gather_point_at(self, img_x, img_y):
        """Place/déplace manuellement le point de rassemblement de la zone la
        plus proche du clic. Appelé depuis on_left_press (canvas_grid.py) en
        mode self.path_mode == 'place_gather_point'."""
        if not self.roof_zones:
            return
        best_idx, best_dist = None, None
        for idx, z in enumerate(self.roof_zones):
            d = self._dist_point_to_zone_rect(img_x, img_y, z)
            if best_dist is None or d < best_dist:
                best_idx, best_dist = idx, d
        if best_idx is None:
            return
        self.roof_zones[best_idx]["gather_point"] = (img_x, img_y)
        self.roof_zones[best_idx]["gather_point_manual"] = True
        if hasattr(self, '_invalidate_cable_routes'):
            self._invalidate_cable_routes()
        self.path_mode = "select"
        if hasattr(self, "_refresh_equipment_tree"):
            self._refresh_equipment_tree()
        self.draw_grid()

    def _activate_gather_point_mode(self):
        if not self.roof_zones:
            messagebox.showwarning('Warning', 'Define at least one zone first.')
            return
        self.path_mode = "place_gather_point"
        self.draw_grid()

    def _reset_gather_points(self):
        """Repasse toutes les zones en calcul automatique du point de
        rassemblement (bord de zone le plus proche de l'onduleur)."""
        if not self.roof_zones:
            return
        for zone in self.roof_zones:
            zone["gather_point_manual"] = False
            zone.pop("gather_point", None)
        if hasattr(self, '_invalidate_cable_routes'):
            self._invalidate_cable_routes()
        if hasattr(self, "_refresh_equipment_tree"):
            self._refresh_equipment_tree()
        self.draw_grid()
