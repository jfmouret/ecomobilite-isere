"""Départs officiels : présélection géographique, sans validation de cheminement."""
import math

SOURCE='https://entrepot.metropolegrenoble.fr/opendata/38185-GRE/Environnement/json/balade.json'
CATALOG='https://www.data.gouv.fr/datasets/balades-dans-les-massifs-autour-de-grenoble-1'


def metres(a,b):
    lat1,lat2=map(math.radians,(a['latitude'],b['latitude']))
    dlat=lat2-lat1;dlon=math.radians(b['longitude']-a['longitude'])
    h=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371008.8*2*math.asin(min(1,math.sqrt(h)))


def departures(records):
    hikes=[]
    for r in records:
        # La géolocalisation du catalogue n’est pas toujours celle du départ.
        # Exiger une validation explicite avant tout rapprochement public.
        if r.get('depart_verifie') is not True:continue
        activity=r.get('activite',{}).get('libelle','')
        if activity=='Randonnée pédestre':season='ete'
        elif activity in ('Raquette','Raquettes','Ski de randonnée','ski de randonnée'):season='hiver'
        else:continue
        try:
            lat=float(r['adresse']['latitude']);lon=float(r['adresse']['longitude'])
            if not 43<lat<47 or not 4<lon<8:continue
        except (KeyError,ValueError,TypeError):continue
        hikes.append(dict(id='grenoble-'+str(r['idtf']),name=r['libelle'],latitude=lat,longitude=lon,season=season,activity=activity,departure=r.get('depart',''),massif=r.get('massif',{}).get('libelle',''),difficulty=r.get('difficulte',''),gpx=r.get('gpx',''),source=CATALOG,stops=[]))
    return hikes


def associate(stops,hikes):
    for s in stops:
        s['hikes']=[]
        for h in hikes:
            d=metres(s,h)
            if d<=1000:
                s['hikes'].append(dict(id=h['id'],name=h['name'],season=h['season'],activity=h['activity'],distance_m=round(d)))
                h['stops'].append(dict(id=s['id'],name=s['name'],group=s['group'],distance_m=round(d)))
