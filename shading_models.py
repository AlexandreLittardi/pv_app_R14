"""Geometric optical loss for overlapping obstacles; optional bypass approximation."""
import math

def attenuation(fraction,settings):
    fraction=max(0.,min(1.,fraction))
    if settings.get('shadow_model')=='bypass_estimate':
        groups=int(settings.get('bypass_groups',3))
        return min(1.,math.ceil(fraction*groups-1e-12)/groups)
    return fraction

def optical_area(layers):
    """Integrate 1-product(transmission) on polygon union, without double counting.

    Polygon edges are linear. All vertices and edge intersections partition x
    into strips with unchanged edge order; integrate each band by trapezoids.
    """
    layers=[(poly,max(0,min(1,alpha))) for poly,alpha in layers if len(poly)>=3 and alpha>0]
    if not layers:return 0.
    edges=[];xs=[]
    for poly,_ in layers:
        xs.extend(p[0] for p in poly)
        for a,b in zip(poly,poly[1:]+poly[:1]):
            if abs(a[0]-b[0])>1e-12:
                m=(b[1]-a[1])/(b[0]-a[0]);edges.append((min(a[0],b[0]),max(a[0],b[0]),m,a[1]-m*a[0]))
    for i,a in enumerate(edges):
        for b in edges[i+1:]:
            if abs(a[2]-b[2])>1e-12:
                x=(b[3]-a[3])/(a[2]-b[2])
                if max(a[0],b[0])<x<min(a[1],b[1]):xs.append(x)
    def inside(x,y,poly):
        hit=False
        for a,b in zip(poly,poly[1:]+poly[:1]):
            if (a[1]>y)!=(b[1]>y) and x<(b[0]-a[0])*(y-a[1])/(b[1]-a[1])+a[0]:hit=not hit
        return hit
    area=0.;xs=sorted(set(xs))
    for left,right in zip(xs,xs[1:]):
        if right-left<1e-12:continue
        mid=(left+right)/2
        active=sorted((e for e in edges if e[0]<mid<e[1]),key=lambda e:e[2]*mid+e[3])
        for low,high in zip(active,active[1:]):
            y=(low[2]*mid+low[3]+high[2]*mid+high[3])/2
            transmission=1.
            for poly,alpha in layers:
                if inside(mid,y,poly):transmission*=1-alpha
            if transmission==1:continue
            h0=(high[2]-low[2])*left+high[3]-low[3];h1=(high[2]-low[2])*right+high[3]-low[3]
            area+=(right-left)*(h0+h1)/2*(1-transmission)
    return max(0.,area)
