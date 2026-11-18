"""Filtre géographique sur les contours communaux officiels du département 38."""
SOURCE='https://geo.api.gouv.fr/departements/38/communes?format=geojson&geometry=contour'


def polygons(collection):
    result=[]
    for f in collection['features']:
        if not str(f['properties']['code']).startswith('38'):raise ValueError('Commune hors Isère dans le référentiel')
        g=f['geometry']
        if g['type']=='Polygon':parts=[g['coordinates']]
        elif g['type']=='MultiPolygon':parts=g['coordinates']
        else:raise ValueError('Contour communal non polygonal')
        for rings in parts:
            xs=[p[0] for p in rings[0]];ys=[p[1] for p in rings[0]]
            result.append(((min(xs),min(ys),max(xs),max(ys)),rings))
    if not result:raise ValueError('Contours Isère absents')
    return result


def in_ring(x,y,ring):
    inside=False
    for i,(x1,y1,*_) in enumerate(ring):
        x2,y2=ring[i-1][:2]
        cross=(x-x1)*(y2-y1)-(y-y1)*(x2-x1)
        if abs(cross)<1e-12 and min(x1,x2)<=x<=max(x1,x2) and min(y1,y2)<=y<=max(y1,y2):return True
        if (y1>y)!=(y2>y) and x<(x2-x1)*(y-y1)/(y2-y1)+x1:inside=not inside
    return inside


def contains(point,prepared):
    x,y=point['longitude'],point['latitude']
    return any(xmin<=x<=xmax and ymin<=y<=ymax and in_ring(x,y,rings[0]) and not any(in_ring(x,y,h) for h in rings[1:]) for (xmin,ymin,xmax,ymax),rings in prepared)
