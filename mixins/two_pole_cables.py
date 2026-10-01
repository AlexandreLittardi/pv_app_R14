"""Both string terminals, using the supplied router and verified saved routes."""
import math
from single_line_516 import route_is_current
from project_validation import number
from geometry_layout import route_elevation
from mixins.string_sizing import StringSizingMixin

class TwoPoleCablesMixin(StringSizingMixin):
    def _route_signature(self):
        return {'strings':{sid:[f'{r},{c}' for r,c in coords] for sid,coords in self.strings.items()},
                'assignments':self.string_mppt_assignment.copy(),
                'inverter_positions':{k:[v['x'],v['y'],v.get('terminal_height_m')] for k,v in self.inverter_positions.items()},
                'cable_paths':[{'id':p.get('id'),'points':[list(q) for q in p.get('points',[])]} for p in self.cable_paths],
                'roof_zones':self.roof_zones,'roof_polygons':self.roof_polygons,
                'routing_model': 'installation_surfaces_v1', 'px_per_mm':self.px_per_mm,
                'panel_width_mm':self.panel_width_mm,'panel_height_mm':self.panel_height_mm,
                'routing_settings':self.routing_settings.copy(),
                'sizing_inputs':self._string_sizing_signature()}

    def get_two_pole_route(self,sid):
        plan=self.electrical_route_plan_3d
        data=self._project_snapshot();data['electrical_route_plan_3d']=plan
        if route_is_current(data,sid):
            sig=plan.get('source_signature',{})
            if (sig.get('routing_settings',self.routing_settings)==self.routing_settings
                    and sig.get('sizing_inputs') == self._string_sizing_signature()):
                return self._size_string_route(sid, plan['routes'][sid])
        return None

    def _calculate_two_pole_route(self,sid):
        saved=self.get_two_pole_route(sid)
        if saved:
            import copy
            return self._size_string_route(sid, copy.deepcopy(saved))
        coords=self.strings.get(sid,[])
        if not coords:return None
        a=self.string_mppt_assignment.get(sid,{})
        record={'inverter':a.get('block'),'mppt':a.get('mppt'),'modules':len(coords),
                'route_status':'ESTIMATE — routing and descent points require site validation'}
        for name,end in [('terminal_A',0),('terminal_B',-1)]:
            length,kind,points=super().compute_cable_route(sid,terminal=end)
            if length is None:return None
            idx=self._get_panel_zone_idx(coords[end])
            surfaces=[]
            for z in self.roof_zones:
                x1,x2=sorted((z['x1'],z['x2']));y1,y2=sorted((z['y1'],z['y2']))
                surfaces.append({'points':[(x1,y1),(x2,y1),(x2,y2),(x1,y2)],
                                 'height_m':z.get('installation_height_m')})
            surfaces.extend({'points':[tuple(q) for q in p['points']],
                             'height_m':p.get('installation_height_m')} for p in self.roof_polygons)
            try:
                dimensions=route_elevation(points,surfaces,self.px_per_mm,
                    self.inverter_positions.get(a.get('block'),{}).get('terminal_height_m',self.routing_settings['inverter_height_m']),
                    self.cable_string_params.get(sid,{}).get('reserve_per_pole_m',self.routing_settings['reserve_per_pole_m']),
                    self.routing_settings.get('bridge_gap_m',0.))
            except ValueError as exc:
                self._last_route_error=str(exc)
                return None
            record[name]={**dimensions,'roof_points_px':points,'ground_points_px':[],
                          'method':kind,'module_id':self.panels[coords[end]],
                          'zone':idx+1 if idx is not None else None}
        record['loop_length_m']=record['terminal_A']['length_m']+record['terminal_B']['length_m']
        return self._size_string_route(sid, record)

    def compute_cable_length_mm(self,sid):
        rec=self._calculate_two_pole_route(sid)
        return (rec['loop_length_m']*1000,True) if rec else (None,False)

    def compute_all_cable_routes(self):
        import copy
        records={};self.cable_network_routes={};failed=[];direct=0
        for sid in self._get_sorted_string_keys():
            if not self.strings.get(sid):continue
            rec=self._calculate_two_pole_route(sid)
            if not rec:failed.append(sid);continue
            records[sid]=rec
            pa=rec['terminal_A'];pb=rec['terminal_B']
            points=pa['roof_points_px']+pa.get('ground_points_px',[])
            points_b=pb['roof_points_px']+pb.get('ground_points_px',[])
            fallback=any(p.get('method')=='direct' for p in (pa,pb))
            direct+=int(fallback)
            self.cable_network_routes[sid]={'points':points,'points_b':points_b,'length_m':rec['loop_length_m'],
                'pole_a_m':pa['length_m'],'pole_b_m':pb['length_m'],'route_kind':'A+B estimate' if fallback else 'A+B 3D',
                'block':rec['inverter'],'status':rec['route_status'],
                **{key:rec.get(key) for key in ('working_section_mm2','drop_at_working_section_pct','mass_kg')}}
        self.electrical_route_plan_3d={'routes':records,'source_signature':copy.deepcopy(self._route_signature()),
                                      'status':'PRELIMINARY — both conductors; no inter-module or AC cables'}
        lengths=[r['length_m'] for r in self.cable_network_routes.values()]
        return {'ok':len(records),'failed':failed,'total_m':sum(lengths),'max_m':max(lengths,default=0),'direct_count':direct}

    def _draw_cable_network_routes(self,zoom):
        if not self.show_cable_network_routes or self._get_active_tab_index()!=8:return
        # Never draw a stale route after a module, path or inverter edit.
        for sid,route in list(self.cable_network_routes.items()):
            if not self.get_two_pole_route(sid):self.cable_network_routes.pop(sid,None)
        super()._draw_cable_network_routes(zoom)
        for sid,route in self.cable_network_routes.items():
            pts=route.get('points_b',[])
            if len(pts)>1:self.canvas.create_line(*[c*zoom for p in pts for c in p],fill='#7B1FA2',width=2,dash=(5,3))
        selected=getattr(self,'selected_cable_route',None)
        x=self.canvas.canvasx(14);y=self.canvas.canvasy(14)
        self.canvas.create_rectangle(x,y,x+360,y+88,fill='#F7FBFF',outline='#66849C')
        self.canvas.create_line(x+9,y+18,x+34,y+18,fill='#E65100',width=3)
        self.canvas.create_text(x+42,y+18,anchor='w',text='A: first module to inverter (solid, block colour)',fill='#18334A')
        self.canvas.create_line(x+9,y+41,x+34,y+41,fill='#7B1FA2',width=2,dash=(5,3))
        self.canvas.create_text(x+42,y+41,anchor='w',text='B: last module to inverter (purple dashed)',fill='#18334A')
        self.canvas.create_text(x+9,y+68,anchor='w',text='Inventory = A + B, including height steps and reserves',fill='#18334A')
        if selected in self.cable_network_routes:
            route=self.cable_network_routes[selected]
            for suffix,key in [('A','points'),('B','points_b')]:
                points=route.get(key,[])
                if points:
                    px,py=points[0]
                    self.canvas.create_text(px*zoom+12,py*zoom-12,anchor='w',
                        text=f"{selected.replace('String ','S')} {suffix} · {route['pole_'+suffix.lower()+'_m']:.1f} m",
                        fill='#C43A18' if suffix=='A' else '#7B1FA2',font=('Arial',9,'bold'))
