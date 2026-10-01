"""Explicit desktop editor gestures, without left-button canvas panning conflicts."""
import tkinter as tk

class EditorInteractionsMixin:
    def on_left_press(self,event):
        idx=self._get_active_tab_index();x=self.canvas.canvasx(event.x);y=self.canvas.canvasy(event.y)
        if idx==1:
            self._canvas_pan_start=None
            # Polygon is chosen in its list; drag vertices or its interior to transform it.
            if self.path_mode=='select_polygon' and self.active_polygon_idx is not None:
                poly=self.roof_polygons[self.active_polygon_idx]
                self._polygon_vertex=next((i for i,p in enumerate(poly['points']) if abs(p[0]*self.zoom_level-x)<8 and abs(p[1]*self.zoom_level-y)<8),None)
                self.polygon_drag_mode='vertex' if self._polygon_vertex is not None else 'move'
                self.polygon_drag_start_pt=(x,y)
                self.polygon_drag_initial_points=[tuple(p) for p in poly['points']]
                return
            # Bypass only the pan wrapper, retaining the existing zone resize tool.
            from mixins.canvas_grid import CanvasGridMixin
            return CanvasGridMixin.on_left_press(self,event)
        if idx==7 and not self.diagram_link_mode:
            self._canvas_pan_start=None
            hit=self._hit_test_diagram_node(x,y)
            selected=set(getattr(self,'diagram_selected_nodes',set()))
            if hit:
                if event.state & 0x0005:
                    if hit in selected:selected.remove(hit)
                    else:selected.add(hit)
                elif hit not in selected:selected={hit}
                self.diagram_selected_nodes=selected;self.diagram_selected_node=hit if hit in selected else next(iter(selected),None)
                self._diagram_group_start=(x,y)
                self._diagram_group_original={k:(self.diagram_nodes[k]['x'],self.diagram_nodes[k]['y']) for k in selected if k in self.diagram_nodes}
            else:
                self.diagram_selected_nodes=set();self.diagram_selected_node=None
                self._diagram_group_start=None
            self.draw_grid();return
        return super().on_left_press(event)

    def on_left_drag(self,event):
        if self._get_active_tab_index()==1:
            if self.polygon_drag_mode and self.active_polygon_idx is not None:
                x,y=self.polygon_drag_start_pt
                dx=(self.canvas.canvasx(event.x)-x)/self.zoom_level;dy=(self.canvas.canvasy(event.y)-y)/self.zoom_level
                points=list(self.polygon_drag_initial_points)
                vertex=getattr(self,'_polygon_vertex',None)
                if vertex is None:points=[(a+dx,b+dy) for a,b in points]
                else:points[vertex]=(points[vertex][0]+dx,points[vertex][1]+dy)
                from project_store import valid_polygon
                if valid_polygon(points):
                    self.roof_polygons[self.active_polygon_idx]['points']=points
                    self._invalidate_cable_routes();self.draw_grid()
                return
            from mixins.canvas_grid import CanvasGridMixin
            return CanvasGridMixin.on_left_drag(self,event)
        start=getattr(self,'_diagram_group_start',None)
        if self._get_active_tab_index()==7 and start:
            dx=(self.canvas.canvasx(event.x)-start[0])/self.zoom_level;dy=(self.canvas.canvasy(event.y)-start[1])/self.zoom_level
            for key,(x,y) in self._diagram_group_original.items():self.diagram_nodes[key].update(x=x+dx,y=y+dy)
            self.draw_grid();return
        return super().on_left_drag(event)

    def on_left_release(self,event):
        self._diagram_group_start=None
        previous=len(self.measures)
        if self._get_active_tab_index()==1:
            from mixins.canvas_grid import CanvasGridMixin
            result=CanvasGridMixin.on_left_release(self,event)
        else:result=super().on_left_release(event)
        if len(self.measures)>previous:
            self.measures[-1]['axis']=getattr(self,'dimension_mode','aligned');self.draw_grid()
        return result

    def _on_diagram_list_select(self,event):
        self.diagram_selected_nodes={self._diagram_list_ids[i] for i in self.lst_diagram_nodes.curselection()}
        self.diagram_selected_node=next(iter(self.diagram_selected_nodes),None);self.draw_grid()

    def _delete_selected_diagram_node(self):
        selected=getattr(self,'diagram_selected_nodes',set()) or {self.diagram_selected_node}
        self.diagram_nodes={k:v for k,v in self.diagram_nodes.items() if k not in selected}
        self.diagram_links=[link for link in self.diagram_links if link['a'] not in selected and link['b'] not in selected]
        self.diagram_selected_nodes=set();self.diagram_selected_node=None;self._refresh_diagram_list();self.draw_grid()

    def draw_grid(self):
        result=super().draw_grid()
        if self._get_active_tab_index()==1 and self.path_mode=='select_polygon' and self.active_polygon_idx is not None:
            for x,y in self.roof_polygons[self.active_polygon_idx]['points']:
                x*=self.zoom_level;y*=self.zoom_level
                self.canvas.create_rectangle(x-4,y-4,x+4,y+4,fill='white',outline='#222222',width=1)
        return result

    def _on_zone_combo_selected(self,event):
        self.path_mode='select';self.roof_mode='select'
        return super()._on_zone_combo_selected(event)
