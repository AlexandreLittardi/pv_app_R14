"""Render the complete project in source coordinates, independently of Tk/zoom."""
import math
from PIL import Image,ImageDraw,ImageFont,ImageColor
from report_plans import scene,PALETTE

def render_plan(app,path,scale=4):
    panels,bounds=scene(app)
    points=[pt for p in getattr(app,'roof_polygons',[]) for pt in p.get('points',[])]
    points += [pt for m in getattr(app,'measures',[]) for pt in (m.get('p1'),m.get('p2')) if pt]
    left,top,right,bottom=bounds
    if points:left=min(left,min(p[0] for p in points));top=min(top,min(p[1] for p in points));right=max(right,max(p[0] for p in points));bottom=max(bottom,max(p[1] for p in points))
    source=app.roof_pil_img
    if source is not None:left=min(0,left);top=min(0,top);right=max(source.width,right);bottom=max(source.height,bottom)
    margin=12;left-=margin;top-=margin;right+=margin;bottom+=margin
    if not math.isfinite(scale) or scale<=0:raise ValueError('Positive resolution required.')
    width,height=math.ceil((right-left)*scale),math.ceil((bottom-top)*scale)
    if width*height>100_000_000:raise ValueError('Export exceeds 100 megapixels. Choose a lower resolution.')
    image=Image.new('RGB',(width,height),'white')
    def xy(p):return ((p[0]-left)*scale,(p[1]-top)*scale)
    if source is not None:
        image.paste(source.convert('RGB').resize((round(source.width*scale),round(source.height*scale)),Image.Resampling.LANCZOS),tuple(round(v) for v in xy((0,0))))
    draw=ImageDraw.Draw(image);font=ImageFont.load_default(size=max(10,round(3.5*scale)))
    owners={c:sid for sid,coords in app.strings.items() for c in coords}
    colors={sid:PALETTE[i%len(PALETTE)] for i,sid in enumerate(app.strings)}
    for p in getattr(app,'roof_polygons',[]):draw.line([xy(v) for v in p['points']+[p['points'][0]]],fill='#505050',width=max(1,round(scale)))
    for coord,num,poly in panels:
        color=colors.get(owners.get(coord),'#334155')
        fill=tuple(round(.35*255+.65*value) for value in ImageColor.getrgb(color)) if coord in owners else '#38BDF8'
        draw.polygon([xy(p) for p in poly],fill=fill,outline=color,width=max(1,round(scale)))
        center=xy(tuple(sum(p[i] for p in poly)/len(poly) for i in (0,1)))
        label=str(num);box=draw.textbbox(center,label,font=font,anchor='mm');draw.rectangle(box,fill='white');draw.text(center,label,fill='#111827',font=font,anchor='mm')
    for sid,coords in app.strings.items():
        pts=[xy(app._get_panel_physical_center(c)) for c in coords if c in app.panels]
        if len(pts)>1:draw.line(pts,fill=colors[sid],width=max(1,round(scale/2)))
    for cable in app.cable_paths:
        if len(cable.get('points',[]))>1:draw.line([xy(p) for p in cable['points']],fill='#E67700',width=max(1,round(scale*1.5)))
    for block,inv in app.inverter_positions.items():
        x,y=xy((inv['x'],inv['y']));r=3*scale;draw.rectangle((x-r,y-r,x+r,y+r),fill='#111827');draw.text((x+r+scale,y),block,font=font,fill='#111827')
    for m in getattr(app,'measures',[]):
        if m.get('p1') and m.get('p2'):draw.line([xy(m['p1']),xy(m['p2'])],fill='#DC2626',width=max(1,round(scale)))
    image.save(path,'JPEG',quality=95,subsampling=0,dpi=(300,300))
    return image.size
