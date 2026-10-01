"""Shared, unit-neutral rigid layout geometry and installation cable elevations."""
import math


def rotate(point, centre, degrees):
    a = math.radians(degrees)
    x, y = point[0]-centre[0], point[1]-centre[1]
    return (centre[0]+x*math.cos(a)-y*math.sin(a),
            centre[1]+x*math.sin(a)+y*math.cos(a))


def inside(point, polygon):
    x, y = point
    hit = False
    for a, b in zip(polygon, polygon[1:]+polygon[:1]):
        dx, dy = b[0]-a[0], b[1]-a[1]
        cross = (x-a[0])*dy-(y-a[1])*dx
        if abs(cross) < 1e-7 and min(a[0],b[0])-1e-7 <= x <= max(a[0],b[0])+1e-7 and min(a[1],b[1])-1e-7 <= y <= max(a[1],b[1])+1e-7:
            return True
        if (a[1]>y) != (b[1]>y) and x < (b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:
            hit = not hit
    return hit


def grid_spec(zone, width, height, scale):
    x1,x2=sorted((zone['x1'],zone['x2'])); y1,y2=sorted((zone['y1'],zone['y2']))
    centre=((x1+x2)/2,(y1+y2)/2)
    a=zone.get('angle_deg',0)
    corners=[rotate(p,centre,-a) for p in [(x1,y1),(x2,y1),(x2,y2),(x1,y2)]]
    left=min(p[0] for p in corners); top=min(p[1] for p in corners)
    w=(max(p[0] for p in corners)-left)/scale; h=(max(p[1] for p in corners)-top)/scale
    gx=zone.get('gap_x_mm',0);gy=zone.get('gap_y_mm',0);edge=zone.get('edge_clearance_mm',0)
    cols=max(0,int((w-2*edge+gx+1e-7)//(width+gx)));rows=max(0,int((h-2*edge+gy+1e-7)//(height+gy)))
    ax={'Gau.':0,'Dro.':1}.get(zone.get('align_x'),.5)
    ay={'Haut':0,'Bas':1}.get(zone.get('align_y'),.5)
    return rows,cols,(left-x1)/scale+(w-(cols*width+max(0,cols-1)*gx))*ax,(top-y1)/scale+(h-(rows*height+max(0,rows-1)*gy))*ay


def route_elevation(points, surfaces, scale, inverter_height, reserve, bridge_gap):
    """Split each planar segment at surface edges. Orthogonal height steps.

    A short unsupported span retains the upstream elevation; longer spans use
    ground level. A downstream height step is counted once. No Shadow data.
    """
    if scale<=0 or not points: raise ValueError('A calibrated cable route is required.')
    if any(not math.isfinite(v) or v<0 for v in (inverter_height,reserve,bridge_gap)):
        raise ValueError('Cable elevations, reserve and bridge limit must be finite and nonnegative.')
    def surface_at(p):
        hits=[s for s in surfaces if inside(p,s['points'])]
        if not hits:return None
        heights=[s.get('height_m') for s in hits]
        if any(v is None or not math.isfinite(v) or v<0 for v in heights):
            raise ValueError('Enter the installation height for every crossed zone / polygon.')
        if max(heights)-min(heights)>1e-6:raise ValueError('Overlapping installation areas have conflicting heights.')
        return heights[0]
    pieces=[]
    for a,b in zip(points,points[1:]):
        dx,dy=b[0]-a[0],b[1]-a[1]; cuts={0.,1.}
        for s in surfaces:
            poly=s['points']
            for c,d in zip(poly,poly[1:]+poly[:1]):
                ex,ey=d[0]-c[0],d[1]-c[1]; den=dx*ey-dy*ex
                if abs(den)<1e-12:continue
                t=((c[0]-a[0])*ey-(c[1]-a[1])*ex)/den
                u=((c[0]-a[0])*dy-(c[1]-a[1])*dx)/den
                if 0<t<1 and 0<=u<=1:cuts.add(t)
        cuts=sorted(cuts)
        for lo,hi in zip(cuts,cuts[1:]):
            mid=(lo+hi)/2; height=surface_at((a[0]+mid*dx,a[1]+mid*dy))
            pieces.append([math.hypot(dx,dy)*(hi-lo)/scale/1000,height])
    start=surface_at(points[0])
    if start is None:raise ValueError('The string terminal needs an installation area with a height.')
    horizontal=sum(p[0] for p in pieces); vertical=0.; current=start; i=0
    while i<len(pieces):
        length,height=pieces[i]
        if height is None:
            j=i+1
            while j<len(pieces) and pieces[j][1] is None:
                length+=pieces[j][0];j+=1
            # Only bridge between two actual elevated areas, never to the inverter by assumption.
            height=current if j<len(pieces) and length<=bridge_gap+1e-9 else 0.
            i=j
        else:i+=1
        vertical+=abs(height-current);current=height
    vertical+=abs(current-inverter_height)
    return {'horizontal_m':horizontal,'vertical_drop_m':vertical,
            'terminal_reserve_m':reserve,'length_m':horizontal+vertical+reserve}


def polygons_overlap(a,b):
    """Strict overlap of convex panels; shared edges are allowed."""
    for poly in (a,b):
        for p,q in zip(poly,poly[1:]+poly[:1]):
            nx,ny=-(q[1]-p[1]),q[0]-p[0]
            pa=[x*nx+y*ny for x,y in a];pb=[x*nx+y*ny for x,y in b]
            if min(max(pa),max(pb))-max(min(pa),min(pb))<=1e-7:return False
    return True


def intersects_polygon(a,b):
    if any(inside(p,b) for p in a) or any(inside(p,a) for p in b):return True
    def cross(p,q,r):return (q[0]-p[0])*(r[1]-p[1])-(q[1]-p[1])*(r[0]-p[0])
    return any(cross(p,q,r)*cross(p,q,s)<0 and cross(r,s,p)*cross(r,s,q)<0
               for p,q in zip(a,a[1:]+a[:1]) for r,s in zip(b,b[1:]+b[:1]))
