"""Accès Camptocamp : présélection géographique, sans validation de cheminement."""
import math



def metres(a,b):
    lat1,lat2=map(math.radians,(a['latitude'],b['latitude']))
    dlat=lat2-lat1;dlon=math.radians(b['longitude']-a['longitude'])
    h=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371008.8*2*math.asin(min(1,math.sqrt(h)))


def associate(stops,hikes):
    for s in stops:
        s['hikes']=[]
        for h in hikes:
            d=metres(s,h)
            if d<=1000:
                s['hikes'].append(dict(id=h['id'],name=h['name'],season=h['season'],activity=h['activity'],distance_m=round(d),source=h.get('source'),license=h.get('license'),routes=h.get('routes',[])))
                h['stops'].append(dict(id=s['id'],name=s['name'],group=s['group'],distance_m=round(d)))


API='https://api.camptocamp.org'
ACTIVITIES={'hiking':('ete','Randonnée pédestre'),'snowshoeing':('hiver','Raquettes'),'skitouring':('hiver','Ski de randonnée')}


def lonlat(geometry):
    import json
    point=json.loads(geometry['geom'])
    if point['type']!='Point':raise ValueError('Camptocamp : accès sans géométrie ponctuelle')
    x,y=point['coordinates'][:2]
    return math.degrees(x/6378137),math.degrees(2*math.atan(math.exp(y/6378137))-math.pi/2)


def title(doc):
    locales=doc.get('locales',[])
    chosen=next((l for l in locales if l['lang']=='fr'),locales[0] if locales else {})
    return ' : '.join(v for v in [chosen.get('title_prefix'),chosen.get('title')] if v) or str(doc['document_id'])


def c2c_accesses(stops,cache,download,cache_only=False):
    """Requêtes bornées au territoire des lignes et aux accès à moins de 1 km."""
    import json,time,urllib.parse
    def get(path):
        key=__import__('hashlib').sha256(path.encode()).hexdigest()+'.json'
        target=cache/'camptocamp'/key;target.parent.mkdir(parents=True,exist_ok=True)
        if cache_only:
            if not target.exists():raise ValueError('Cache Camptocamp absent : '+path)
        elif not target.exists() or time.time()-target.stat().st_mtime>86400:
            target.write_bytes(download(API+path))
            time.sleep(.2)  # appels séquentiels, pas de rafale
        return json.loads(target.read_bytes())
    def listing(path):
        result=[];offset=0;seen=set()
        while True:
            x=get(path+('&' if '?' in path else '?')+urllib.parse.urlencode({'limit':100,'offset':offset}))
            docs=x['documents']
            if not docs and len(result)<x['total']:raise ValueError('Camptocamp : pagination incomplète')
            for d in docs:
                if d['document_id'] in seen:raise ValueError('Camptocamp : pagination répétée')
                seen.add(d['document_id']);result.append(d)
            offset+=len(docs)
            if offset>=x['total']:return result
    def merc(lon,lat):
        return 6378137*math.radians(lon),6378137*math.log(math.tan(math.pi/4+math.radians(lat)/2))
    # Marge > 1 km pour que le préfiltre ne coupe pas les accès proches des bords.
    xmin,ymin=merc(min(s['longitude'] for s in stops)-.02,min(s['latitude'] for s in stops)-.02)
    xmax,ymax=merc(max(s['longitude'] for s in stops)+.02,max(s['latitude'] for s in stops)+.02)
    bbox=','.join(str(round(v)) for v in [xmin,ymin,xmax,ymax])
    candidates=listing('/waypoints?'+urllib.parse.urlencode({'wtyp':'access','bbox':bbox}))
    print('Camptocamp :',len(candidates),'accès à examiner',flush=True)
    nearby=[]
    for p in candidates:
        if p.get('waypoint_type')!='access':raise ValueError('Filtre Camptocamp ignoré')
        lon,lat=lonlat(p['geometry']);point=dict(latitude=lat,longitude=lon)
        if any(metres(s,point)<=1000 for s in stops):nearby.append(p)
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as pool:
        documents=list(pool.map(lambda p:get('/waypoints/'+str(p['document_id'])),nearby))
    hikes=[];near=len(nearby)
    for doc in documents:
        if doc.get('waypoint_type')!='access':continue
        license=doc.get('license',{})
        if license.get('id')!='CC-BY-SA-3.0':raise ValueError('Licence Camptocamp non prise en charge')
        lon,lat=lonlat(doc['geometry'])
        linked=doc.get('associations',{}).get('all_routes',{})
        routes=linked.get('documents',[])
        if len(routes)<linked.get('total',0):
            routes=listing('/routes?'+urllib.parse.urlencode({'w':doc['document_id']}))
        selected=[]
        for r in routes:
            acts=[a for a in r.get('activities',[]) if a in ACTIVITIES]
            if not acts:continue
            lic=r.get('license',{})
            if lic.get('id')!='CC-BY-SA-3.0':raise ValueError('Licence itinéraire Camptocamp non prise en charge')
            selected.append(dict(id=r['document_id'],name=title(r),activities=acts,url='https://www.camptocamp.org/routes/'+str(r['document_id'])+'/fr',version=r.get('version'),license=lic))
        for season in ('ete','hiver'):
            rr=[r for r in selected if any(ACTIVITIES[a][0]==season for a in r['activities'])]
            if not rr:continue
            hikes.append(dict(id='c2c-'+str(doc['document_id'])+'-'+season,name=title(doc),latitude=lat,longitude=lon,season=season,activity='Pédestre' if season=='ete' else 'Raquettes / ski',departure='Point d’accès associé aux itinéraires ; départ ou arrivée à vérifier dans le topo.',massif='',difficulty='voir chaque topo',source='https://www.camptocamp.org/waypoints/'+str(doc['document_id'])+'/fr',license=license,version=doc.get('version'),routes=rr,stops=[]))
    print('Camptocamp :',len(candidates),'accès examinés,',near,'proches des arrêts,',len(hikes),'fiches par activité',flush=True)
    return hikes
