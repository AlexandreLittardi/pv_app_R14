"""Left drag pans the diagram; right drag selects, or moves the selected group."""
import tkinter as tk
from tkinter import ttk
from diagram_layout import arrange

class DiagramEditorMixin:
    def _build_tab_diagram_tools(self):
        super()._build_tab_diagram_tools()
        ttk.Button(self.tab_diagram,text='Reflow diagram',command=self._reflow_diagram).pack(side='left',padx=3)
        ttk.Button(self.tab_diagram,text='Fit diagram',command=self._fit_diagram).pack(side='left',padx=3)
        ttk.Button(self.tab_diagram,text='Show electrical values',command=self._toggle_diagram_electrical).pack(side='left',padx=3)

    def _build_main_area(self):
        super()._build_main_area()
        self.canvas.bind('<ButtonRelease-3>',self.on_right_release)

    def on_left_press(self,event):
        if self._get_active_tab_index()!=7:return super().on_left_press(event)
        if self.diagram_link_mode:return super().on_left_press(event)
        self._diagram_pan_start=(event.x,event.y);self._auto_fit=False
        self.canvas.scan_mark(event.x,event.y);self.canvas.configure(cursor='fleur')
        return 'break'

    def on_left_drag(self,event):
        if self._get_active_tab_index()!=7:return super().on_left_drag(event)
        if getattr(self,'_diagram_pan_start',None):self.canvas.scan_dragto(event.x,event.y,gain=1)
        return 'break'

    def on_left_release(self,event):
        if self._get_active_tab_index()!=7:return super().on_left_release(event)
        self._diagram_pan_start=None;self.canvas.configure(cursor='');return 'break'

    def on_right_press(self,event):
        if self._get_active_tab_index()!=7:return super().on_right_press(event)
        x,y=self.canvas.canvasx(event.x),self.canvas.canvasy(event.y)
        selected=set(getattr(self,'diagram_selected_nodes',set()))
        hit=self._hit_test_diagram_node(x,y)
        self._diagram_right={'start':(x,y),'selected':selected,'add':bool(event.state&0x0005),'hit':hit}
        # A right drag from an already selected block moves that selection.
        if hit in selected and not self._diagram_right['add']:
            self._diagram_right['original']={k:(self.diagram_nodes[k]['x'],self.diagram_nodes[k]['y']) for k in selected}
        return 'break'

    def on_right_drag(self,event):
        if self._get_active_tab_index()!=7:return super().on_right_drag(event)
        state=getattr(self,'_diagram_right',None)
        if not state:return 'break'
        x,y=self.canvas.canvasx(event.x),self.canvas.canvasy(event.y);x0,y0=state['start']
        if 'original' in state:
            for key,(ox,oy) in state['original'].items():self.diagram_nodes[key].update(x=ox+(x-x0)/self.zoom_level,y=oy+(y-y0)/self.zoom_level)
            self.draw_grid()
        else:
            self.canvas.delete('diagram_selection_box')
            self.canvas.create_rectangle(x0,y0,x,y,outline='#2E5B86',width=1,tags='diagram_selection_box')
        return 'break'

    def on_right_release(self,event):
        if self._get_active_tab_index()!=7:self.last_drag_cell=None;return
        state=getattr(self,'_diagram_right',None);self._diagram_right=None
        self.canvas.delete('diagram_selection_box')
        if not state:return
        x,y=self.canvas.canvasx(event.x),self.canvas.canvasy(event.y);x0,y0=state['start']
        if 'original' not in state:
            selected=state['selected'] if state['add'] else set()
            if abs(x-x0)+abs(y-y0)<5:
                if state['hit']:
                    if state['add'] and state['hit'] in selected:selected.remove(state['hit'])
                    else:selected.add(state['hit'])
            else:
                left,right=sorted((x0/self.zoom_level,x/self.zoom_level));top,bottom=sorted((y0/self.zoom_level,y/self.zoom_level))
                for key,node in self.diagram_nodes.items():
                    w,h=self._diagram_node_size(key)
                    if left<=node['x']+w/2 and right>=node['x']-w/2 and top<=node['y']+h/2 and bottom>=node['y']-h/2:selected.add(key)
            self.diagram_selected_nodes=selected;self.diagram_selected_node=next(iter(selected),None)
        self.draw_grid()

    def _diagram_node_size(self,key):
        from tkinter.font import Font
        label=self.diagram_nodes[key].get('label',key)
        metrics=self._diagram_node_metric_lines(key)
        if not hasattr(self,'_diagram_measure_font'):self._diagram_measure_font=Font(root=self.root,family='Arial',size=10)
        font=self._diagram_measure_font
        width=max(280,max((font.measure(t) for t in [label]+metrics),default=0)+35)
        return width,(82 if self.diagram_nodes[key].get('type')=='string' else 62)+19*len(metrics)

    def _diagram_layout_signature(self):
        return (tuple((k,self._diagram_node_size(k)) for k in self.diagram_nodes),
                tuple((l['a'],l['b']) for l in self.diagram_links if l.get('auto')),self.diagram_show_electrical)

    def _reflow_diagram(self):
        sizes={k:self._diagram_node_size(k) for k in self.diagram_nodes}
        positions=arrange(self.diagram_nodes,self.diagram_links,sizes)
        for key,(x,y) in positions.items():self.diagram_nodes[key].update(x=x,y=y)
        self._diagram_layout_applied=self._diagram_layout_signature();self.draw_grid()

    def _draw_diagram(self):
        signature=self._diagram_layout_signature()
        if not getattr(self,'_restoring',False) and getattr(self,'_diagram_layout_applied',None)!=signature:
            positions=arrange(self.diagram_nodes,self.diagram_links,{k:self._diagram_node_size(k) for k in self.diagram_nodes})
            for key,(x,y) in positions.items():self.diagram_nodes[key].update(x=x,y=y)
            self._diagram_layout_applied=signature
        route_source=repr(self._route_signature())
        if getattr(self,'_diagram_routes_source',None)!=route_source or any(l.get('auto') and l['a'].startswith('str::') and 'distance_label' not in l for l in self.diagram_links):
            for link in self.diagram_links:
                if link.get('auto') and link['a'].startswith('str::'):
                    length,_=self.compute_cable_length_mm(link['a'].split('::',1)[1])
                    link['distance_label']=f'A+B {length/1000:.1f} m' if length is not None else 'A+B not calculated'
            self._diagram_routes_source=route_source
        from project_validation import natural
        for inv in sorted((k for k in self.diagram_nodes if k.startswith('inv::')),key=natural):
            block=inv.split('::',1)[1]
            keys=[inv]+[k for k in self.diagram_nodes if k.startswith('mppt::'+block+'::')]
            keys += ['str::'+sid for sid,a in self.string_mppt_assignment.items() if a.get('block')==block and 'str::'+sid in self.diagram_nodes]
            left=min(self.diagram_nodes[k]['x']-self._diagram_node_size(k)[0]/2 for k in keys)-18
            top=min(self.diagram_nodes[k]['y']-self._diagram_node_size(k)[1]/2 for k in keys)-45
            right=max(self.diagram_nodes[k]['x']+self._diagram_node_size(k)[0]/2 for k in keys)+18
            bottom=max(self.diagram_nodes[k]['y']+self._diagram_node_size(k)[1]/2 for k in keys)+18
            z=self.zoom_level
            self.canvas.create_rectangle(left*z,top*z,right*z,bottom*z,fill='#F1F5F9',outline='#CBD5E1',width=1)
            self.canvas.create_text((left+12)*z,(top+18)*z,text=block+'  •  Strings → MPPT → Inverter',anchor='w',fill='#334155',font=('Arial',max(9,int(13*z)),'bold'))
        return super()._draw_diagram()

    def generate_diagram_auto(self):
        self._diagram_layout_applied=None
        return super().generate_diagram_auto()

    def _fit_diagram(self):
        self._auto_fit=False;self.draw_grid()
        bounds=self.canvas.bbox('all')
        if not bounds:return
        width=max(1,bounds[2]-bounds[0]);height=max(1,bounds[3]-bounds[1])
        factor=min((self.canvas.winfo_width()-30)/width,(self.canvas.winfo_height()-30)/height)
        self.zoom_level=max(.08,min(3,self.zoom_level*factor));self.draw_grid()
        self.canvas.xview_moveto(0);self.canvas.yview_moveto(0)
