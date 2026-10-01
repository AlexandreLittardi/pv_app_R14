"""Vector plans and complete, non-overlapping physical-block detail sheets."""
import math
import re
from reportlab.graphics.shapes import Drawing,Line,Polygon,Rect,String
from reportlab.graphics import renderPDF,renderSVG
from reportlab.lib.colors import HexColor,Color,black,white

from constants import STRING_COLORS
PALETTE=STRING_COLORS

def clip_segment(a,b,bounds):
    left,top,right,bottom=bounds;dx=b[0]-a[0];dy=b[1]-a[1];lo,hi=0.,1.
    for p,q in [(-dx,a[0]-left),(dx,right-a[0]),(-dy,a[1]-top),(dy,bottom-a[1])]:
        if abs(p)<1e-12:
            if q<0:return None
        else:
            t=q/p
            if p<0:lo=max(lo,t)
            else:hi=min(hi,t)
            if lo>hi:return None
    return ((a[0]+lo*dx,a[1]+lo*dy),(a[0]+hi*dx,a[1]+hi*dy))

def scene(app):
    panels=[(coord,number,app._panel_rect(coord)) for coord,number in app.panels.items()]
    panels=[p for p in panels if p[2]]
    pts=[pt for _,_,poly in panels for pt in poly]
    pts += [tuple(pt) for p in app.cable_paths for pt in p.get('points',[])]
    pts += [(v['x'],v['y']) for v in app.inverter_positions.values()]
    pts += [p for z in app.roof_zones for p in [(z['x1'],z['y1']),(z['x2'],z['y2'])]]
    if not pts:pts=[(0,0),(100,100)]
    bounds=(min(x for x,y in pts),min(y for x,y in pts),max(x for x,y in pts),max(y for x,y in pts))
    return panels,bounds

def detail_tiles(panels,width=475,height=550):
    if not panels:return []
    points=[p for _,_,poly in panels for p in poly]
    short=min(math.dist(poly[0],poly[1]) for _,_,poly in panels)
    short=min(short,min(math.dist(poly[1],poly[2]) for _,_,poly in panels))
    # >= 28 pt per module short edge permits an 8 pt multi-digit identifier.
    digits=max(len(str(n)) for _,n,_ in panels)
    scale=max(28,digits*4.5+8)/max(short,1e-6)
    tw,th=(width-24)/scale,(height-35)/scale
    diameter=max(math.dist(poly[0],poly[2]) for _,_,poly in panels)
    overlap=min(diameter*1.05,min(tw,th)*.35)
    left=min(p[0] for p in points)-diameter*.08;right=max(p[0] for p in points)+diameter*.08
    top=min(p[1] for p in points)-diameter*.08;bottom=max(p[1] for p in points)+diameter*.08
    xs=[];x=left
    while True:
        xs.append(x)
        if x+tw>=right:break
        x+=tw-overlap
    ys=[];y=top
    while True:
        ys.append(y)
        if y+th>=bottom:break
        y+=th-overlap
    tiles=[]
    for row,y in enumerate(ys):
        for col,x in enumerate(xs):
            members=[p for p in panels if all(x<=px<=x+tw and y<=py<=y+th for px,py in p[2])]
            if members:tiles.append((f'{row+1}-{col+1}',(x,y,x+tw,y+th),members))
    covered={p[0] for _,_,items in tiles for p in items}
    if covered!={p[0] for p in panels}:raise ValueError('Detail atlas cannot cover all module identifiers; check extreme module dimensions.')
    return tiles

def physical_blocks(app, panels):
    """Partition modules by physical installation zone, with no repeated IDs."""
    remaining={coord:(coord,num,poly) for coord,num,poly in panels};result=[]
    for index,zone in enumerate(app.roof_zones,1):
        base=zone.get('row_base',100*(index-1))
        members=[item for coord,item in remaining.items() if base<=coord[0]<base+zone.get('rows',0)]
        if members:
            for coord,_,_ in members:remaining.pop(coord)
            points=[point for _,_,poly in members for point in poly]+[(zone['x1'],zone['y1']),(zone['x2'],zone['y2'])]
            bounds=(min(x for x,y in points),min(y for x,y in points),max(x for x,y in points),max(y for x,y in points))
            result.append((f'B{index}',zone,bounds,members))
    # Legacy/unzoned modules still receive complete, disjoint detail sheets.
    while remaining:
        seed=next(iter(remaining));todo=[seed];members=[]
        while todo:
            coord=todo.pop()
            if coord not in remaining:continue
            members.append(remaining.pop(coord));r,c=coord
            todo.extend(n for n in ((r-1,c),(r+1,c),(r,c-1),(r,c+1)) if n in remaining)
        points=[point for _,_,poly in members for point in poly]
        bounds=(min(x for x,y in points),min(y for x,y in points),max(x for x,y in points),max(y for x,y in points))
        result.append((f'Additional block {len(result)+1}',None,bounds,members))
    return result


def plate(app,panels,bounds,layer='layout',numbered=False,routes=None,font='Times-Roman',title='',zone=None):
    from reportlab.pdfbase.pdfmetrics import stringWidth
    from project_validation import natural
    width,height=742,350;d=Drawing(width,height);left,top,right,bottom=bounds
    scale=min((width-110 if zone else width-42)/max(right-left,1e-6),(height-75 if zone else height-58)/max(bottom-top,1e-6))
    ox=(width-(right-left)*scale)/2+(12 if zone else 0);oy=(height-(bottom-top)*scale)/2-8
    def xy(pt):return ox+(pt[0]-left)*scale,oy+(bottom-pt[1])*scale
    def line(a,b,color=black,stroke=.5,dash=None):
        d.add(Line(*a,*b,strokeColor=color,strokeWidth=stroke,strokeDashArray=dash))
    colors={sid:HexColor(PALETTE[i%2]) for i,sid in enumerate(sorted(app.strings,key=natural))}
    member_coords={coord for coord,_,_ in panels}
    if not zone:
        for i,z in enumerate(app.roof_zones,1):
            a,b=xy((z['x1'],z['y1'])),xy((z['x2'],z['y2']));lx,rx=sorted((a[0],b[0]));by,ty=sorted((a[1],b[1]))
            d.add(Rect(lx,by,rx-lx,ty-by,fillColor=None,strokeColor=HexColor('#888888'),strokeWidth=.3,strokeDashArray=[2,2]))
            label=f'B{i}'
            if app.px_per_mm:label+=f": {abs(z['x2']-z['x1'])/app.px_per_mm/1000:.2f} x {abs(z['y2']-z['y1'])/app.px_per_mm/1000:.2f} m"
            lw=stringWidth(label,font,7);d.add(Rect((lx+rx-lw)/2-2,ty+2,lw+4,9,fillColor=white,strokeColor=None))
            d.add(String((lx+rx)/2,ty+4,label,textAnchor='middle',fontName=font,fontSize=7,fillColor=black))
    for coord,num,poly in panels:
        d.add(Polygon([v for p in poly for v in xy(p)],fillColor=white,strokeColor=HexColor('#888888'),strokeWidth=.3))
    if layer=='strings':
        for sid,coords in app.strings.items():
            for a,b in zip(coords,coords[1:]):
                if tuple(a) in member_coords and tuple(b) in member_coords:
                    line(xy(app._get_panel_physical_center(tuple(a))),xy(app._get_panel_physical_center(tuple(b))),colors[sid],1.05)
    if layer=='cables':
        for path in app.cable_paths:
            for a,b in zip(path.get('points',[]),path.get('points',[])[1:]):line(xy(a),xy(b),HexColor('#555555'),1.5)
        for sid,record in routes or []:
            for pole,dash in [('terminal_A',None),('terminal_B',[3,2])]:
                pts=record[pole].get('roof_points_px',[])
                for a,b in zip(pts,pts[1:]):line(xy(a),xy(b),colors.get(sid,black),.8,dash)
        for i,(name,inv) in enumerate(sorted(app.inverter_positions.items())):
            x,y=xy((inv['x'],inv['y']));d.add(Rect(x-2,y-2,4,4,fillColor=black,strokeColor=None))
            lx=ox+20+i*45;ly=12;line((x,y),(lx,ly+8),black,.4)
            d.add(String(lx,ly,name,textAnchor='middle',fontName=font,fontSize=7,fillColor=black))
    if numbered:
        for coord,num,poly in panels:
            x,y=xy(app._get_panel_physical_center(coord));short=min(math.dist(xy(poly[0]),xy(poly[1])),math.dist(xy(poly[1]),xy(poly[2])))
            fs=min(8,max(3,short*.40))
            if layer=='strings':
                lw=stringWidth(str(num),font,fs);d.add(Rect(x-lw/2-1,y-fs*.5,lw+2,fs+1,fillColor=white,strokeColor=None))
            d.add(String(x,y-fs*.3,str(num),textAnchor='middle',fontName=font,fontSize=fs,fillColor=black))
    if layer=='strings':
        for sid,coords in app.strings.items():
            selected=[tuple(c) for c in coords if tuple(c) in member_coords]
            if not selected:continue
            # In details the label is offset from the module identifier.
            x,y=xy(app._get_panel_physical_center(selected[0]));label=re.sub(r'^String\s*','S',sid,flags=re.I)
            fs=6;lw=stringWidth(label,font,fs);y+=8 if numbered else 0
            d.add(Rect(x-lw/2-1,y-2,lw+2,8,fillColor=white,strokeColor=colors[sid],strokeWidth=.45))
            d.add(String(x,y,label,textAnchor='middle',fontName=font,fontSize=fs,fillColor=black))
    if zone and app.px_per_mm:
        a,b=xy((zone['x1'],zone['y1'])),xy((zone['x2'],zone['y2']));lx,rx=sorted((a[0],b[0]));by,ty=sorted((a[1],b[1]));dy=ty+15;dx=lx-17
        for x in (lx,rx):line((x,ty),(x,dy+4),black,.4)
        line((lx,dy),(rx,dy))
        for x,sign in ((lx,1),(rx,-1)):
            line((x,dy),(x+4*sign,dy+2));line((x,dy),(x+4*sign,dy-2))
        d.add(String((lx+rx)/2,dy+5,f"{abs(zone['x2']-zone['x1'])/app.px_per_mm/1000:.2f} m",textAnchor='middle',fontName=font,fontSize=9,fillColor=black))
        for y in (by,ty):line((lx,y),(dx-4,y),black,.4)
        line((dx,by),(dx,ty))
        for y,sign in ((by,1),(ty,-1)):
            line((dx,y),(dx+2,y+4*sign));line((dx,y),(dx-2,y+4*sign))
        d.add(String(dx-5,(by+ty)/2,f"{abs(zone['y2']-zone['y1'])/app.px_per_mm/1000:.2f} m",textAnchor='end',fontName=font,fontSize=9,fillColor=black))
    return d


def vector_blocks(app,assets,routes,font='Times-Roman'):
    panels,bounds=scene(app);blocks=[]
    def add(name,d,caption):
        pdf=assets/(name+'.pdf');svg=assets/(name+'.svg')
        renderPDF.drawToFile(d,str(pdf));renderSVG.drawToFile(d,str(svg))
        blocks.append(('vector',d,caption,pdf))
    if getattr(app,'roof_pil_img',None) is not None:
        image=assets/'roof_source.png';app.roof_pil_img.save(image)
        blocks.append(('image',image,'Source roof plan.'))
    for layer,caption in [('layout','Numbered installation layout. Dimensions describe the zone boundaries in metres.'),
                          ('strings','String connections on unfilled panels. S1 = String 1, etc.; zone dimensions in metres.'),
                          ('cables','DC cable plan. Grey: trays. Solid: conductor A; dashed: conductor B. Unavailable routes are not zero-length routes.')]:
        add(layer+'_overview',plate(app,panels,bounds,layer,layer=='layout',routes,font),caption)
    for name,zone,bbox,members in physical_blocks(app,panels):
        add('detail_'+name.replace(' ','_'),plate(app,members,bbox,'strings',True,font=font,zone=zone),
            f'Physical block {name}. {len(members)} modules, no repeated modules between detail sheets. Zone dimensions in metres; module IDs and string connections are shown.')
    return blocks
