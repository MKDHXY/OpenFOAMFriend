"""Planar simple-polygon solids stored in local normalized coordinates, in SI."""
import math

def vertices(s):
    if s['kind']=='polygon': return [(s['x']+x*s['width'],s['y']+y*s['height']) for x,y in s['vertices']]
    x,y=s['x'],s['y']; a,b=s['width']/2,s['height']/2
    return [(x-a,y-b),(x+a,y-b),(x,y+b)] if s['kind']=='triangle' else [(x-a,y-b),(x+a,y-b),(x+a,y+b),(x-a,y+b)]

def validate_polygon(points):
    if len(points)<3 or any(len(p)!=2 or not all(math.isfinite(float(v)) for v in p) for p in points): raise ValueError('A closed solid needs at least three finite x,y vertices.')
    if any(math.dist(a,b)<1e-10 for a,b in zip(points,points[1:]+points[:1])): raise ValueError('Duplicate / zero-length polygon edge.')
    area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1]))/2
    if abs(area)<1e-12: raise ValueError('Polygon area is zero.')
    def cross(a,b,c): return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    def intersects(a,b,c,d):
        eps=1e-12; u,v,w,z=cross(a,b,c),cross(a,b,d),cross(c,d,a),cross(c,d,b)
        if u*v<-eps and w*z<-eps: return True
        return any(abs(k)<eps and min(p[0],q[0])-eps<=r[0]<=max(p[0],q[0])+eps and min(p[1],q[1])-eps<=r[1]<=max(p[1],q[1])+eps for k,p,q,r in ((u,a,b,c),(v,a,b,d),(w,c,d,a),(z,c,d,b)))
    n=len(points)
    for i in range(n):
        for j in range(i+1,n):
            if j==i+1 or (i==0 and j==n-1): continue
            if intersects(points[i],points[(i+1)%n],points[j],points[(j+1)%n]): raise ValueError('Self-intersecting / touching polygon edges are not a valid simple solid.')
    return area

def polygon(points,name='Polygon'):
    p=[list(map(float,v)) for v in points]
    if len(p)>1 and math.dist(p[0],p[-1])<1e-10: p.pop()
    area=validate_polygon(p)
    if area<0: p.reverse()
    xs,ys=zip(*p); w=max(xs)-min(xs); h=max(ys)-min(ys); x=(max(xs)+min(xs))/2; y=(max(ys)+min(ys))/2
    return {'kind':'polygon','name':name,'x':x,'y':y,'width':w,'height':h,'vertices':[[(a-x)/w,(b-y)/h] for a,b in p]}
