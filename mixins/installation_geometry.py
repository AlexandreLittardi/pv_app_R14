"""Installation transforms, common panel geometry, dimensions and elevations."""
import math
import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from geometry_layout import rotate, grid_spec, inside, polygons_overlap

class InstallationGeometryMixin:
    def _recalculate_zone_grids(self):
        if self.px_per_mm<=0:return
        from zone_registry import allocate_ranges
        settings=getattr(self,'model_settings',{})
        specs=[]
        for z in self.roof_zones:
            z.update(gap_x_mm=settings.get('module_gap_x_mm',0),gap_y_mm=settings.get('module_gap_y_mm',0),edge_clearance_mm=settings.get('edge_clearance_mm',0))
            specs.append(grid_spec(z,self.panel_width_mm,self.panel_height_mm,self.px_per_mm))
        allocate_ranges(self.roof_zones,specs,getattr(self,'_remap_zone_rows',None))

    def _remap_zone_rows(self,base,capacity,new_base):
        def key(coord):return (new_base+coord[0]-base,coord[1]) if base<=coord[0]<base+capacity else coord
        for name in ('panels','panel_blocks','panel_orientations','panel_uids'):
            if hasattr(self,name):setattr(self,name,{key(c):v for c,v in getattr(self,name).items()})
        if hasattr(self,'layout_geometry'):
            remapped={}
            for coord,value in self.layout_geometry.items():
                r,c=key(tuple(map(int,coord.split(','))));remapped[f'{r},{c}']=value
            self.layout_geometry=remapped
        if hasattr(self,'strings'):self.strings={s:[key(c) for c in coords] for s,coords in self.strings.items()}
        if hasattr(self,'selected_panel_coords'):self.selected_panel_coords={key(c) for c in self.selected_panel_coords}

    def _panel_pitch_mm(self):
        cfg=getattr(self,'model_settings',{})
        return self.panel_width_mm+cfg.get('module_gap_x_mm',0),self.panel_height_mm+cfg.get('module_gap_y_mm',0)

    def _mark_geometry_change(self):
        self._invalidate_cable_routes()
        self.shadow_source_signature=None

    def delete_active_zone(self):
        indices=set(self.selected_zone_indices or ([self.active_zone_idx] if self.active_zone_idx is not None else []))
        removed={c for c in self.panels for i in indices if 0<=i<len(self.roof_zones) and self.roof_zones[i]['row_base']<=c[0]<self.roof_zones[i]['row_base']+self.roof_zones[i].get('row_capacity',100)}
        self._detach_coords(removed)
        for c in removed:
            self.panels.pop(c,None);self.panel_blocks.pop(c,None);self.panel_orientations.pop(c,None)
        self.selected_panel_coords.difference_update(removed)
        self.roof_zones=[z for i,z in enumerate(self.roof_zones) if i not in indices]
        self.selected_zone_indices.clear();self.active_zone_idx=0 if self.roof_zones else None
        self._update_zone_combo();self._update_zone_entries_from_active();self._recalculate_zone_grids()
        self._mark_geometry_change();self._update_string_listbox();self.draw_grid()

    def _detach_coords(self,coords):
        for sid,members in self.strings.items():
            if any(c in coords for c in members):
                self.connection_review_required=list(set(getattr(self,'connection_review_required',[])+[sid]))
                self.strings[sid]=[c for c in members if c not in coords]
                self.string_mppt_assignment.pop(sid,None)
        self._clean_deleted_panels_from_strings()

    def _zone_rotate_rect(self,zone,x1,y1,x2,y2):
        # Used both in image pixels and in zoomed canvas pixels.
        scale=(x2-x1)/(self.panel_width_mm*self.px_per_mm)
        centre=((zone['x1']+zone['x2'])*scale/2,(zone['y1']+zone['y2'])*scale/2)
        return [rotate(p,centre,zone.get('angle_deg',0)) for p in [(x1,y1),(x2,y1),(x2,y2),(x1,y2)]]

    def _valid_zone_cell(self,zone,r,c):
        p=self.px_per_mm
        x=min(zone['x1'],zone['x2'])+(zone['offset_x_mm']+c*self._panel_pitch_mm()[0])*p
        y=min(zone['y1'],zone['y2'])+(zone['offset_y_mm']+r*self._panel_pitch_mm()[1])*p
        corners=self._zone_rotate_rect(zone,x,y,x+self.panel_width_mm*p,y+self.panel_height_mm*p)
        edge=zone.get('edge_clearance_mm',0)*p
        valid=all(min(zone['x1'],zone['x2'])+edge-1e-6<=a<=max(zone['x1'],zone['x2'])-edge+1e-6 and
                  min(zone['y1'],zone['y2'])+edge-1e-6<=b<=max(zone['y1'],zone['y2'])-edge+1e-6 for a,b in corners)
        from geometry_layout import intersects_polygon
        return valid and not any(intersects_polygon(corners,poly) for poly in getattr(self,'model_settings',{}).get('layout_exclusions',[]))

    def _get_panel_physical_center(self,coord):
        points=self._panel_rect(coord)
        if points:return tuple(sum(p[i] for p in points)/len(points) for i in (0,1))
        return super()._get_panel_physical_center(coord)

    def _get_cell_coords(self,event):
        if not self.roof_zones or self.px_per_mm<=0:return super()._get_cell_coords(event)
        point=(self.canvas.canvasx(event.x)/self.zoom_level,self.canvas.canvasy(event.y)/self.zoom_level)
        for z in self.roof_zones:
            centre=((z['x1']+z['x2'])/2,(z['y1']+z['y2'])/2)
            x,y=rotate(point,centre,-z.get('angle_deg',0))
            c=math.floor(((x-min(z['x1'],z['x2']))/self.px_per_mm-z['offset_x_mm'])/self._panel_pitch_mm()[0])
            r=math.floor(((y-min(z['y1'],z['y2']))/self.px_per_mm-z['offset_y_mm'])/self._panel_pitch_mm()[1])
            if 0<=r<z['rows'] and 0<=c<z['cols'] and self._valid_zone_cell(z,r,c):
                coord=(z['row_base']+r,c)
                if inside(point,self._panel_rect(coord)):return coord
        return None

    def generate_panels_from_zones(self):
        if not self.roof_zones or self.px_per_mm<=0:
            messagebox.showwarning('Layout','Define zones and calibrate the roof scale.');return
        old=dict(self.panels);old_geometry=getattr(self,'layout_geometry',{})
        self._recalculate_zone_grids();new={};accepted=[];next_id=max(old.values(),default=0)+1
        changed=set()
        from project_store import fingerprint
        for z in self.roof_zones:
            for r in range(z['rows']):
                for c in range(z['cols']):
                    coord=(z['row_base']+r,c)
                    if not self._valid_zone_cell(z,r,c):continue
                    poly=self._panel_rect(coord)
                    if any(polygons_overlap(poly,other) for other in accepted):continue
                    accepted.append(poly);stamp=fingerprint(poly);key=f'{coord[0]},{coord[1]}'
                    if coord in old and (not old_geometry or old_geometry.get(key)==stamp):new[coord]=old[coord]
                    else:
                        new[coord]=next_id;next_id+=1
                        if coord in old:changed.add(coord)
        changed.update(set(old)-set(new))
        self._detach_coords(changed);self.panels=new
        if hasattr(self,'panel_uids'):self.panel_uids={c:v for c,v in self.panel_uids.items() if c in new and c not in changed}
        self.panel_blocks={c:v for c,v in self.panel_blocks.items() if c in new and c not in changed}
        self.panel_orientations={c:v for c,v in self.panel_orientations.items() if c in new and c not in changed}
        self.selected_panel_coords.intersection_update(new)
        self._clean_deleted_panels_from_strings();self._mark_geometry_change()
        self.layout_geometry={f'{c[0]},{c[1]}':fingerprint(self._panel_rect(c)) for c in new}
        self._update_string_listbox();self.draw_grid()

    def _show_installation_heights(self):
        win=tk.Toplevel(self.root);win.title('Installation elevations for cable routing')
        frm=ttk.Frame(win,padding=12);frm.pack(fill='both',expand=True)
        ttk.Label(frm,text='Heights above the same ground datum, in metres. Blank = unknown.\nThese values are independent of Shadow roof heights.').pack(anchor='w')
        canvas=tk.Canvas(frm,height=280);canvas.pack(fill='both',expand=True)
        body=ttk.Frame(canvas);canvas.create_window(0,0,window=body,anchor='nw')
        scroll=ttk.Scrollbar(frm,command=canvas.yview);scroll.pack(side='right',fill='y');canvas.configure(yscrollcommand=scroll.set)
        body.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        entries=[]
        for label,items in [('Zone',self.roof_zones),('Polygon',self.roof_polygons)]:
            for i,item in enumerate(items):
                row=ttk.Frame(body);row.pack(fill='x');ttk.Label(row,text=f'{label} {i+1}',width=18).pack(side='left')
                entry=ttk.Entry(row,width=12);entry.pack(side='left');entry.insert(0,str(item.get('installation_height_m','')))
                entries.append((item,'installation_height_m',entry))
        for key,label,default in [('inverter_height_m','Inverter terminal height (m)',0),('reserve_per_pole_m','Reserve per conductor (m)',2),('bridge_gap_m','Maximum bridged gap (m)',0)]:
            row=ttk.Frame(frm);row.pack(fill='x');ttk.Label(row,text=label,width=32).pack(side='left');entry=ttk.Entry(row,width=12);entry.pack(side='left');entry.insert(0,str(self.routing_settings.get(key,default)));entries.append((self.routing_settings,key,entry))
        def save():
            try:
                values=[None if not e.get().strip() else float(e.get()) for _,_,e in entries]
                if any(v is not None and (not math.isfinite(v) or v<0) for v in values):raise ValueError
                if any(v is None for (obj,k,e),v in zip(entries,values) if obj is self.routing_settings):raise ValueError
            except ValueError:messagebox.showerror('Invalid height','Use nonnegative finite numbers.',parent=win);return
            for (obj,k,e),v in zip(entries,values):
                if v is None:obj.pop(k,None)
                else:obj[k]=v
            self._invalidate_cable_routes();win.destroy()
        ttk.Button(frm,text='Apply',command=save).pack(anchor='e',pady=8)
        self._fit_dialog(win,570,500)

    def _activate_dimension(self,mode):
        self.dimension_mode=mode;self._activate_measure_mode()

    def _draw_dimension(self,measure,zoom):
        p1,p2=measure['p1'],measure['p2'];label=measure['label'];mode=measure.get('axis','aligned')
        if mode=='horizontal':a=(p1[0],label[1]);b=(p2[0],label[1]);length=abs(p2[0]-p1[0])
        elif mode=='vertical':a=(label[0],p1[1]);b=(label[0],p2[1]);length=abs(p2[1]-p1[1])
        else:
            dx,dy=p2[0]-p1[0],p2[1]-p1[1];length=math.hypot(dx,dy)
            if length==0:return
            normal=(-dy/length,dx/length);offset=(label[0]-(p1[0]+p2[0])/2)*normal[0]+(label[1]-(p1[1]+p2[1])/2)*normal[1]
            a=(p1[0]+offset*normal[0],p1[1]+offset*normal[1]);b=(p2[0]+offset*normal[0],p2[1]+offset*normal[1])
        for start,end in [(p1,a),(p2,b)]:self.canvas.create_line(*(v*zoom for p in (start,end) for v in p),fill='#000000',width=1)
        self.canvas.create_line(*(v*zoom for p in (a,b) for v in p),fill='#000000',width=1,arrow=tk.BOTH,arrowshape=(8,10,3))
        self._draw_text_with_bg(label[0]*zoom,label[1]*zoom,text=f'{length/self.px_per_mm:.0f} mm',fill='#000000',font=('Times New Roman',10))

    def _layout_issues(self):
        issues=[];accepted=[]
        for coord in self.panels:
            z=next((z for z in self.roof_zones if z.get('row_base',0)<=coord[0]<z.get('row_base',0)+z.get('rows',0) and 0<=coord[1]<z.get('cols',0)),None)
            if self.roof_zones and (z is None or not self._valid_zone_cell(z,coord[0]-z['row_base'],coord[1])):
                issues.append(f'Module {self.panels[coord]} outside its installation zone');continue
            poly=self._panel_rect(coord)
            if any(polygons_overlap(poly,other) for other in accepted):issues.append(f'Module {self.panels[coord]} overlaps another module')
            accepted.append(poly)
        return issues

    def _draw_clearance_dimension(self,marker,zoom):
        a,b=marker['point'],marker['nearest_point']
        self._draw_dimension({'p1':a,'p2':b,'label':((a[0]+b[0])/2,(a[1]+b[1])/2-14/zoom),'axis':'aligned'},zoom)
