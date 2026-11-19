#!/usr/bin/env python3
"""Arrêts sélectionnés -> fiches web et KMZ, à partir des GTFS officiels."""
import argparse
import hiking
import territory
import climbing
import activity_map
import pdipr_pilot
import focused_kmz
import csv
import struct
import zlib
import datetime as dt
import hashlib
import html
import io
import json
import math
from pathlib import Path
import re
import shutil
import time
import unicodedata
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

ROOT=Path(__file__).resolve().parent
PARIS=ZoneInfo('Europe/Paris')
K='http://www.opengis.net/kml/2.2'
ET.register_namespace('',K)
SOURCES={
    'ISERE':('Cars Région Isère / Transaltitude','https://www.data.gouv.fr/api/1/datasets/r/40ee9d6c-3bb9-409e-b670-986212de63f2'),
    'SEM':('M réso — Métropole grenobloise','https://data.mobilites-m.fr/api/gtfs/SEM'),
    'GSV':('M réso — Grésivaudan','https://data.mobilites-m.fr/api/gtfs/GSV'),
    'TPV':('M réso — Pays Voironnais','https://data.mobilites-m.fr/api/gtfs/TPV'),
    'RUBAN':('Ruban — Porte de l’Isère','https://www.data.gouv.fr/api/1/datasets/r/34d2cc17-3eb5-4581-917b-a8c06a112e61'),
    'LVA':('L’va — Vienne Condrieu','https://www.data.gouv.fr/api/1/datasets/r/e0831d78-5577-4cae-aa00-de5eeaf3ecb6'),
}
NETWORK_PAGES={
    'ISERE':'https://www.laregionvoustransporte.fr/cars-region/cars-region-de-lisere/',
    'SEM':'https://www.reso-m.fr/61-lignes-et-horaires.htm',
    'GSV':'https://www.reso-m.fr/61-lignes-et-horaires.htm',
    'TPV':'https://www.reso-m.fr/61-lignes-et-horaires.htm',
    'RUBAN':'https://www.rubantransport.com/lignes-regulieres/',
    'LVA':'https://www.lva-mobilite.fr/se-deplacer/plan-et-fiches-horaires-du-reseau',
}


def network_group(code):return 'mreso' if code in ('SEM','GSV','TPV') else 'cars'


M_ROUTES='https://data.mobilites-m.fr/api/routers/default/index/routes'
M_SCHEDULES='https://www.reso-m.fr/61-lignes-et-horaires.htm'


def norm(value):
    return re.sub('[^a-z0-9]','',unicodedata.normalize('NFKD',value).encode('ascii','ignore').decode().lower())


def distance(a,b):
    return 111_000*math.hypot(a['latitude']-b['latitude'],(a['longitude']-b['longitude'])*math.cos(math.radians(a['latitude'])))


def match_stop(seed,candidates):
    named=[p for p in candidates if norm(p['name'])==norm(seed['name'])]
    exact=[p for p in named if distance(seed,p)<.2]
    selected=exact or [p for p in named if distance(seed,p)<=25]
    # Une correspondance par réseau au maximum ; plusieurs réseaux peuvent partager l'arrêt.
    if not selected:return [],'non_retrouve'
    resolved=[]
    for feed in {p['feed'] for p in selected}:
        group=[p for p in selected if p['feed']==feed]
        if len(group)>1:
            parents=[p for p in group if p.get('is_station')]
            if len(parents)==1 and all(p.get('root_id')==parents[0].get('root_id') for p in group):
                group=parents
            else:return [],'ambigu'
        resolved.extend(group)
    return resolved,'exact' if exact else 'nom_et_proximite'


def download(url):
    for attempt in range(3):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'CAF-Ecomobilite-Isere/1.0'})
            with urllib.request.urlopen(req,timeout=60) as r:return r.read()
        except urllib.error.HTTPError as error:
            if error.code<500 and error.code!=429:raise
            if attempt==2:raise
            time.sleep(2**attempt)
        except (OSError,TimeoutError):
            if attempt==2:raise
            time.sleep(2**attempt)


class OfficialLinks(HTMLParser):
    def __init__(self):super().__init__();self.links={}
    def handle_starttag(self,tag,attrs):
        if tag!='a':return
        a=dict(attrs);href=a.get('href','')
        url=urllib.parse.urljoin(M_SCHEDULES,html.unescape(href))
        parsed=urllib.parse.urlparse(url)
        code=urllib.parse.parse_qs(parsed.query).get('code',[''])[0]
        if parsed.hostname=='www.reso-m.fr' and parsed.path=='/8-horaires.htm' and code:
            self.links[code]=url


def read_feed(code,payload,route_meta,official_links):
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        if z.testzip() is not None:raise ValueError(code+' : archive GTFS invalide')
        def rows(name):
            if name not in z.namelist():return []
            with z.open(name) as f:return list(csv.DictReader(io.TextIOWrapper(f,encoding='utf-8-sig')))
        stops={r['stop_id']:r for r in rows('stops.txt')}
        routes={r['route_id']:r for r in rows('routes.txt')}
        trips={r['trip_id']:r for r in rows('trips.txt')}
        if not stops or not routes or not trips:raise ValueError(code+' : GTFS incomplet')
        def parent_id(stop_id):
            seen=set()
            while stop_id in stops and stops[stop_id].get('parent_station'):
                if stop_id in seen:raise ValueError('Cycle de parenté GTFS')
                seen.add(stop_id);stop_id=stops[stop_id]['parent_station']
            if stop_id not in stops:raise ValueError('Parent GTFS absent')
            return stop_id
        associations=defaultdict(set);direct=defaultdict(set)
        for st in rows('stop_times.txt'):
            if st['trip_id'] not in trips or st['stop_id'] not in stops:raise ValueError('Référence GTFS manquante')
            rid=trips[st['trip_id']]['route_id']
            if rid not in routes:raise ValueError('Ligne GTFS absente')
            associations[parent_id(st['stop_id'])].add(rid)
            direct[st['stop_id']].add(rid)
        period=rows('feed_info.txt');calendar=rows('calendar.txt')
        exceptions=rows('calendar_dates.txt')
        start=(period[0].get('feed_start_date') if period else None) or min([r['start_date'] for r in calendar]+[r['date'] for r in exceptions],default='')
        end=(period[0].get('feed_end_date') if period else None) or max([r['end_date'] for r in calendar]+[r['date'] for r in exceptions],default='')
        route_records={}
        for rid,r in routes.items():
            meta=route_meta.get(code+':'+rid,{})
            url=None;kind=''
            if code=='ISERE':
                url='https://sim.laregionvoustransporte.fr/fr/schedules/line/'+urllib.parse.quote(rid,safe='')
                kind='horaires_ligne_region'
            elif code in ('RUBAN','LVA'):
                url=NETWORK_PAGES[code];kind='catalogue_reseau'
            elif meta.get('id') in official_links:
                url=official_links[meta['id']];kind='lien_extrait_site_officiel'
            elif meta.get('timeSheet') is True:
                # Format présent dans les liens officiels ; code confirmé par l'API M.
                url='https://www.reso-m.fr/8-horaires.htm?'+urllib.parse.urlencode({'code':meta['id']})
                kind='code_api_m_confirme'
            route_records[rid]=dict(id=code+':'+rid,feed=code,number=r.get('route_short_name') or rid,name=r.get('route_long_name') or '',network=SOURCES[code][0],url=url,link_method=kind)
        points=[]
        for sid,s in stops.items():
            station=s.get('location_type')=='1' or not s.get('parent_station')
            linked=associations[sid] if station else direct[sid]
            points.append(dict(feed=code,source_id=sid,root_id=parent_id(sid),is_station=station,name=s['stop_name'],latitude=float(s['stop_lat']),longitude=float(s['stop_lon']),routes=[route_records[r] for r in sorted(linked)]))
        return dict(feed=code,source_url=SOURCES[code][1],sha256=hashlib.sha256(payload).hexdigest(),period_start=start,period_end=end,points=points,route_count=len(routes))


def display_date(value):
    try:return dt.datetime.strptime(value,'%Y%m%d').strftime('%d/%m/%Y')
    except ValueError:return 'non renseignée'


def route_cards(routes):
    esc=lambda x:html.escape(str(x),quote=True)
    body=''
    for r in routes:
        body+='<section><h3>Ligne '+esc(r['number'])+'</h3><p>'+esc(r['name'])+'</p><p class="muted">'+esc(r['network'])+'</p>'
        if r['url']:body+='<a class="button" href="'+esc(r['url'])+'">'+('Catalogue horaires — rechercher la ligne ' if r.get('link_method')=='catalogue_reseau' else 'Horaires officiels — ligne ')+esc(r['number'])+'</a>'
        else:body+='<p>Lien détaillé non confirmé. Consulter le site officiel du réseau ci-dessous.</p>'
        body+='<p><a href="../lignes/'+focused_kmz.line_filename(r['id'])+'">Afficher tous les arrêts de cette ligne dans AlpineQuest — télécharger le KMZ</a></p>'
        body+='</section>'
    return body


def access_transport(refs,stops):
    esc=lambda x:html.escape(str(x),quote=True)
    by_id={s['id']:s for s in stops}
    grouped={}
    for ref in refs:
        if ref['id'] not in grouped:grouped[ref['id']]=dict(ref,route_ids=set())
        grouped[ref['id']]['route_ids'].add(ref['route_id'])
    body='<h2>Venir en bus ou en car</h2><p>Un seul arrêt, le plus proche par ligne dans un rayon de 1 km à vol d’oiseau ; cheminement piéton et accès à vérifier. Choisir la ligne selon votre provenance, puis vérifier la date, le sens et le retour dans les horaires officiels. L’offre publiée ne garantit pas une desserte chaque jour.</p>'
    for ref in sorted(grouped.values(),key=lambda r:(r['distance_m'],r['id'])):
        stop=by_id.get(ref['id'])
        body+='<section><h3>Arrêt '+esc(ref['name'])+' — '+str(ref['distance_m'])+' m</h3><p>Distance à vol d’oiseau · <a href="../arrets/'+esc(ref['id'])+'.html">Fiche de l’arrêt et informations du réseau</a></p>'
        if stop and stop['status'] in ('exact','nom_et_proximite') and stop['routes']:
            body+=route_cards([r for r in stop['routes'] if r['id'] in ref['route_ids']])
        else:body+='<p>Desserte à vérifier sur la fiche de l’arrêt.</p>'
        body+='</section>'
    if not refs:body+='<p>Aucun arrêt retenu dans le rayon de 1 km parmi les données intégrées.</p>'
    return body


def stop_page(s,feeds,now):
    esc=lambda x:html.escape(str(x),quote=True)
    matched=s['status'] in ('exact','nom_et_proximite')
    body='<a href="../index.html">Tous les arrêts</a><h1>'+esc(s['name'])+'</h1>'
    body+='<p>'+(' / '.join(dict.fromkeys(SOURCES[m['feed']][0] for m in s['matches'])) or ('M réso' if s['group']=='mreso' else 'Cars Région Isère'))+(' · altitude indiquée dans ton KMZ initial : '+esc(s['altitude'])+' m (IGN, non recalculée).' if s.get('altitude') is not None else ' · arrêt issu du GTFS officiel ; altitude non renseignée.')+'</p>'
    body+='<p class="muted">Données récupérées le '+now.astimezone(PARIS).strftime('%d/%m/%Y à %H h %M')+', heure de Paris.</p>'
    today=now.astimezone(PARIS).strftime('%Y%m%d')
    for code in sorted({m['feed'] for m in s['matches']}):
        f=feeds[code]
        if f['period_end'] and f['period_end']<today:
            body+='<p class="notice"><b>Offre publiée expirée pour '+esc(SOURCES[code][0])+'.</b> Les lignes ci-dessous proviennent d’un fichier dont la période se termine le '+display_date(f['period_end'])+'. Consulter le réseau avant de préparer un trajet.</p>'
        elif f['period_start'] and f['period_start']>today:
            body+='<p class="notice"><b>Offre future pour '+esc(SOURCES[code][0])+'.</b> Ce fichier commence le '+display_date(f['period_start'])+'. Vérifier les horaires de la date de voyage sur le site officiel.</p>'
    if not matched:
        body+='<p class="notice"><b>Correspondance à vérifier.</b> Cet arrêt n’a pas été retrouvé avec certitude dans les données officielles actuelles. Aucune ancienne liste de lignes n’est présentée comme actualisée.</p>'
    else:
        body+='<h2>Lignes et horaires officiels</h2><p>Choisis la date et le sens de circulation sur la page officielle. La liste ci-dessous décrit l’offre publiée, pas une garantie de desserte chaque jour ni des prochains départs en temps réel.</p>'
        body+=route_cards(s['routes'])
        if not s['routes']:body+='<p>Aucune desserte trouvée dans le fichier publié.</p>'
        body+='<details><summary>Correspondance avec les données officielles</summary>'
        for ref in s['matches']:
            f=feeds[ref['feed']]
            body+='<p>'+esc(SOURCES[ref['feed']][0])+' · identifiant '+esc(ref['source_id'])+' · écart de position '+esc(ref['distance_m'])+' m.<br>Période du fichier : '+display_date(f['period_start'])+' au '+display_date(f['period_end'])+'.</p>'
            if f['period_end'] and f['period_end']<now.astimezone(PARIS).strftime('%Y%m%d'):
                body+='<p class="notice">La période du fichier GTFS est dépassée. Vérifier impérativement les informations du réseau.</p>'
        body+='</details>'
    body+=hiking_links(s,with_routes=True)
    body+=climbing.links(s)
    body+='<h2>Informations du réseau</h2>'
    for code in sorted({m['feed'] for m in s['matches']}):body+='<p><a href="'+NETWORK_PAGES[code]+'">'+esc(SOURCES[code][0])+': horaires et informations voyageurs</a></p>'
    body+='<p><a href="https://www.oura.com/">Oùra : recherche d’itinéraires</a></p><p class="muted">Les conditions de réservation, les services scolaires, vacances et perturbations doivent être vérifiés auprès du réseau. Cette fiche nécessite du réseau ; une page restée ouverte n’est pas une garantie de consultation hors ligne.</p>'
    body+='<footer><a href="../sources.html">Sources, méthode et licences</a> · Mise en forme CAF indépendante des réseaux.</footer>'
    return document(s['name'],body)


def document(title,body):
    css='body{font:19px/1.5 system-ui,sans-serif;margin:0;background:#f5f7f8;color:#172d38}main{max-width:46rem;margin:auto;padding:20px 16px 40px}h1{font-size:1.6rem;line-height:1.25}h2{font-size:1.3rem;margin-top:28px}h3{margin:0;font-size:1.2rem}a{color:#155476;overflow-wrap:anywhere}section{padding:16px;background:white;border:1px solid #dce4e8;border-radius:10px;margin:14px 0}.button{display:inline-block;background:#18516c;color:white;padding:10px 14px;border-radius:7px;text-decoration:none}.muted,footer,details{font-size:16px;color:#52636d}.notice{border-left:4px solid #ab6c00;padding:12px;background:#fff4db}input{font:inherit;padding:10px;box-sizing:border-box;width:100%}li{margin:8px 0}footer{margin-top:30px;border-top:1px solid #ddd;padding-top:16px}'
    return '<!doctype html><html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(title)+'</title><style>'+css+'</style></head><body><main>'+body+'</main></body></html>'


def colour_icon(rgb):
    """PNG RGBA autonome : pastille de couleur bordée de blanc."""
    def chunk(tag,data):
        return struct.pack('>I',len(data))+tag+data+struct.pack('>I',zlib.crc32(tag+data)&0xffffffff)
    raw=bytearray()
    for y in range(32):
        raw.append(0)
        for x in range(32):
            radius=math.hypot(x-15.5,y-15.5)
            raw.extend((*rgb,255) if radius<11.5 else ((255,255,255,255) if radius<14 else (0,0,0,0)))
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',32,32,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(bytes(raw)))+chunk(b'IEND',b'')


PALETTE=['1769aa','c62828','2e7d32','7b1fa2','ef6c00','00838f','ad1457','5d4037','455a64','827717','4527a0','00796b']


def make_kmz(group,selection,out,base,complete=None,hikes=None):
    def sub(parent,tag,text=None,**attrs):
        e=ET.SubElement(parent,'{'+K+'}'+tag,attrs)
        if text is not None:e.text=str(text)
        return e
    root=ET.Element('{'+K+'}kml');doc=sub(root,'Document')
    sub(doc,'name',('M réso' if group=='mreso' else 'Cars et réseaux locaux Isère')+' — Isère et lignes complètes')
    sub(doc,'description','Vue générale dans « Tous les arrêts ». Masquer cette vue puis afficher un dossier dans « Par ligne ». Les dossiers par ligne contiennent tous les arrêts publiés, y compris en plaine. La vue générale conserve seulement la sélection initiale à partir de 600 m. Les couleurs peuvent se répéter : le numéro identifie la ligne. Les dossiers reflètent les données à la date de génération du KMZ ; les fiches web continuent à s’actualiser.')
    style=sub(doc,'Style',id='arret');icon=sub(style,'IconStyle');sub(icon,'scale',1.1);sub(sub(icon,'Icon'),'href','icons/'+group+'.png')
    selected=[s for s in selection if s['group']==group]
    route_stops=defaultdict(list);routes={}
    for s in selected+([p for p in complete if p['group']==group] if complete is not None else []):
        for r in s['routes']:
            routes[r['id']]=r
    for s in (complete if complete is not None else selected):
        if s['group']!=group:continue
        for r in s['routes']:
            if r['id'] in routes:route_stops[r['id']].append(s)
    # Clé naturelle sous forme homogène pour les codes numériques/alphanumériques.
    ids=sorted(routes,key=lambda rid:(routes[rid]['feed'],re.sub(r'\d+',lambda m:m[0].zfill(8),routes[rid]['number']),rid))
    icons={}
    for rid in ids:
        colour=PALETTE[int(hashlib.sha256(rid.encode()).hexdigest()[:8],16)%len(PALETTE)]
        icons[colour]=colour_icon(tuple(bytes.fromhex(colour)))
        st=sub(doc,'Style',id='colour-'+colour)
        ic=sub(st,'IconStyle');sub(ic,'scale',1.1);sub(sub(ic,'Icon'),'href','icons/'+colour+'.png')
    # Une définition par couleur (plusieurs lignes peuvent partager cette couleur).
    seen=set()
    for st in list(doc):
        if st.tag=='{'+K+'}Style':
            if st.attrib['id'] in seen:doc.remove(st)
            else:seen.add(st.attrib['id'])
    def point(parent,s,uid,route=None):
        p=sub(parent,'Placemark',id=uid)
        sub(p,'name',(route['number']+' · ' if route else '')+s['name'])
        colour=PALETTE[int(hashlib.sha256(route['id'].encode()).hexdigest()[:8],16)%len(PALETTE)] if route else None
        sub(p,'styleUrl','#colour-'+colour if colour else '#arret')
        link=base.rstrip('/')+'/arrets/'+s['id']+'.html'
        numbers=', '.join(dict.fromkeys(r['number'] for r in s['routes'])) or 'à vérifier'
        altitude='Altitude indiquée : '+str(s['altitude'])+' m.' if s.get('altitude') is not None else 'Altitude non renseignée dans les données officielles.'
        info='<div style="font-size:20px;max-width:320px"><h2>'+html.escape(s['name'])+'</h2><p>'+altitude+'</p><p>Lignes à la génération du KMZ : '+html.escape(numbers)+'.</p>'
        if route:info+='<p><b>Ligne '+html.escape(route['number'])+'</b> : '+html.escape(route['name'])+'</p>'
        info+='<p><a href="'+html.escape(link,quote=True)+'"><b>Consulter les lignes et horaires actualisés — connexion requise</b></a></p></div>'
        info+=hiking_links(s,base.rstrip('/')+'/')
        sub(p,'description',info);sub(sub(p,'Point'),'coordinates',f'{s["longitude"]},{s["latitude"]},0')
    general=sub(doc,'Folder',id='all-stops');sub(general,'name','Tous les arrêts ≥ 600 m');sub(general,'visibility',1)
    for s in selected:point(general,s,s['id'])
    all_isere=sub(doc,'Folder',id='isere-stops');sub(all_isere,'name','Tous les arrêts en Isère');sub(all_isere,'visibility',0)
    for s in complete or []:
        if s['group']==group and s.get('in_isere'):point(all_isere,s,'isere-'+s['id'])
    per_line=sub(doc,'Folder',id='by-line');sub(per_line,'name','Par ligne');sub(per_line,'visibility',0)
    for i,rid in enumerate(ids):
        r=routes[rid];folder=sub(per_line,'Folder',id='line-'+str(i))
        sub(folder,'name','Ligne '+r['number']+' — '+r['name']+' · '+r['network']+' ('+str(len(route_stops[rid]))+' points)')
        sub(folder,'visibility',0)
        for s in route_stops[rid]:point(folder,s,'line-'+str(i)+'-'+s['id'],r)
    for season,title in [('ete','Accès rando été — pédestre'),('hiver','Accès rando hiver — raquettes et ski')]:
        hf=sub(doc,'Folder',id='hiking-'+season);sub(hf,'name',title);sub(hf,'visibility',0)
        for h in hikes or []:
            if h['season']!=season or not any(t['group']==group for t in h['stops']):continue
            hp=sub(hf,'Placemark',id='hike-'+h['id']);sub(hp,'name',h['activity']+' · '+h['name'])
            sub(hp,'description','<p>Point d’accès Camptocamp et itinéraires associés (CC BY-SA 3.0). Arrêt(s) à 1 km maximum à vol d’oiseau ; accès à pied à vérifier.</p><p><a href="'+base.rstrip('/')+'/randos/'+h['id']+'.html">Voir les arrêts proches et les informations du départ</a></p>')
            sub(sub(hp,'Point'),'coordinates',str(h['longitude'])+','+str(h['latitude'])+',0')
    filename='Mreso_600m_en_ligne.kmz' if group=='mreso' else 'Cars_Isere_600m_en_ligne.kmz'
    with zipfile.ZipFile(out/filename,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('doc.kml',ET.tostring(root,encoding='utf-8',xml_declaration=True));z.write(ROOT/'data'/f'{group}.png','icons/'+group+'.png')
        for colour,data in icons.items():z.writestr('icons/'+colour+'.png',data)


def hiking_links(stop,base='../',with_routes=False):
    if not stop.get('hikes'):return '<h2>Accès Camptocamp à proximité</h2><p>Aucun accès associé à une randonnée pédestre, raquettes ou ski trouvé à 1 km maximum à vol d’oiseau dans les données récupérées. Ce résultat ne garantit pas l’absence de randonnée : la base est contributive.</p>'
    body='<h2>Accès Camptocamp à proximité</h2><p>Présélection à 1 km maximum <b>à vol d’oiseau</b>. Le cheminement réel à pied peut être plus long ou impossible ; accès à vérifier. Été désigne ici l’activité pédestre, sans validation de saison. Hiver distingue raquettes et ski, sans garantir les conditions ni la sécurité avalanche.</p>'
    for season,title in [('ete','Été / pédestre'),('hiver','Hiver / raquettes et ski')]:
        items=[h for h in stop['hikes'] if h['season']==season]
        if not items:continue
        body+='<h3>'+title+'</h3><ul>'
        for h in sorted(items,key=lambda h:h['distance_m']):
            body+='<li><a href="'+base+'randos/'+h['id']+'.html">'+html.escape(h['name'])+'</a> · '+str(h['distance_m'])+' m à vol d’oiseau'
            choices=[a for a in stop.get('nearest_accesses',[]) if a['access_id']==h['id']]
            if choices:body+='<p><b>Arrêt retenu comme le plus proche pour : '+html.escape(', '.join(a['network']+' — '+a['number'] for a in choices))+'.</b> Distance à vol d’oiseau ; cheminement et sens de desserte à vérifier.</p>'
            if with_routes:
                body+='<ul>'
                for route in h.get('routes',[]):
                    acts=', '.join(hiking.ACTIVITIES[a][1] for a in route['activities'] if hiking.ACTIVITIES[a][0]==season)
                    body+='<li><a href="'+html.escape(route['url'],quote=True)+'">'+html.escape(route['name'])+'</a> · '+html.escape(acts)+'</li>'
                body+='</ul>'
            body+='</li>'
        body+='</ul>'
    body+='<p class="muted">Camptocamp.org et ses contributeurs · <a href="https://creativecommons.org/licenses/by-sa/3.0/">CC BY-SA 3.0</a>. Données extraites ; distance calculée. Attribution détaillée sur chaque fiche liée.</p>'
    return body


def make_hiking_pages(out,hikes,now,stops=()):
    (out/'randos').mkdir()
    intro='<p>Points d’accès et itinéraires associés : Camptocamp.org et ses contributeurs, <a href="https://creativecommons.org/licenses/by-sa/3.0/">CC BY-SA 3.0</a>. Données extraites et coordonnées converties pour cette présentation le '+now.astimezone(PARIS).strftime('%d/%m/%Y à %H h %M')+'.</p><p>Arrêts à 1 km maximum <b>à vol d’oiseau</b> : cheminement piéton à vérifier. Un point d’accès associé peut être un départ ou une arrivée de traversée ; lire le topo. Pédestre est regroupé sous été, raquettes et ski sous hiver, selon les activités du topo, sans garantie saisonnière ou de sécurité.</p>'
    listing='<a href="../index.html">Accueil</a><h1>Accès Camptocamp proches des arrêts</h1>'+intro
    for season,title in [('ete','Été / pédestre'),('hiver','Hiver / raquettes et ski')]:
        listing+='<h2>'+title+'</h2><ul>'
        for h in hikes:
            if h['season']!=season or not h['stops']:continue
            listing+='<li><a href="'+h['id']+'.html">'+html.escape(h['name'])+'</a> · '+html.escape(h['activity'])+'</li>'
        listing+='</ul>'
    (out/'randos/index.html').write_text(document('Accès Camptocamp',listing))
    for h in hikes:
        if not h['stops']:continue
        body='<a href="index.html">Tous les départs</a><h1>'+html.escape(h['name'])+'</h1><p>'+html.escape(h['activity'])+' · '+html.escape(h['massif'])+'</p>'
        body+='<p><a href="'+html.escape(h['source'],quote=True)+'">Point d’accès sur Camptocamp</a></p>'
        # Réutiliser les gagnants calculés sans arrondi pour la carte AlpineQuest.
        refs=[dict(id=stop['id'],name=stop['name'],distance_m=choice['distance_m'],route_id=choice['route_id'])
              for stop in stops for choice in stop.get('nearest_accesses',[])
              if choice['access_id']==h['id']]
        body+=access_transport(refs,stops)
        body+='<h2>Choisir une course depuis ce point d’accès</h2><p>Itinéraires associés au point d’accès Camptocamp. Lire chaque topo pour vérifier le départ, l’approche et l’arrivée éventuelle à un autre endroit.</p><ul>'
        for route in h['routes']:
            activities=', '.join(hiking.ACTIVITIES[a][1] for a in route['activities'] if hiking.ACTIVITIES[a][0]==h['season'])
            body+='<li><a href="'+html.escape(route['url'],quote=True)+'">'+html.escape(route['name'])+'</a> · '+html.escape(activities)+' · <a href="'+html.escape(route['license']['attribution_url'],quote=True)+'">contributeurs</a></li>'
        body+='</ul>'
        gpx=h.get('gpx','')
        if urllib.parse.urlparse(gpx).hostname in ('www.grenoble-montagne.com','grenoble-montagne.com'):
            body+='<p><a href="'+html.escape(gpx,quote=True)+'">Trace GPX indiquée par la source (disponibilité non garantie)</a></p>'
        body+='<h2>Sources et informations complémentaires</h2><p>Départ indiqué : '+html.escape(h['departure'])+'</p><p>Difficulté : '+html.escape(h['difficulty'])+'</p>'+intro
        body+='<p><a href="'+html.escape(h['license']['attribution_url'],quote=True)+'">Historique et contributeurs Camptocamp</a> · <a href="../sources.html">Sources et méthode</a></p>'
        (out/'randos'/(h['id']+'.html')).write_text(document(h['name'],body))


def build(base,out,cache,cache_only=False):
    now=dt.datetime.now(dt.timezone.utc)
    cache.mkdir(parents=True,exist_ok=True)
    urls={code+'.zip':u for code,(_,u) in SOURCES.items()}
    urls.update({'m-routes.json':M_ROUTES,'m-horaires.html':M_SCHEDULES,'isere-limits.json':territory.SOURCE})
    unavailable={}
    def fetch(item):
        name,url=item;p=cache/name
        try:
            if cache_only:
                if not p.exists():raise ValueError('Cache de test absent : '+name)
            else:p.write_bytes(download(url))
            return name,p.read_bytes()
        except (OSError,ValueError) as error:
            if name not in ('RUBAN.zip','LVA.zip'):raise
            unavailable[name[:-4]]=str(error)
            return name,None
    with ThreadPoolExecutor(max_workers=3) as pool:payload=dict(pool.map(fetch,urls.items()))
    route_meta={r['gtfsId']:r for r in json.loads(payload['m-routes.json']) if r.get('gtfsId')}
    links=OfficialLinks();links.feed(payload['m-horaires.html'].decode('utf-8'))
    if not links.links:raise ValueError('Liens horaires M réso absents du site officiel')
    feeds={}
    for c in SOURCES:
        if payload[c+'.zip'] is None:continue
        try:feeds[c]=read_feed(c,payload[c+'.zip'],route_meta,links.links)
        except (ValueError,zipfile.BadZipFile) as error:
            if c not in ('RUBAN','LVA'):raise
            unavailable[c]=str(error)
    selected=json.loads((ROOT/'data/selection.json').read_text())
    indexes={'cars':defaultdict(list),'mreso':defaultdict(list)}
    for c,f in feeds.items():
        for p in f['points']:indexes[network_group(c)][norm(p['name'])].append(p)
    result=[]
    for seed in selected:
        candidates=indexes[seed['group']].get(norm(seed['name']),[])
        matched,status=match_stop(seed,candidates)
        current=dict(seed,status=status,matches=[dict(feed=p['feed'],source_id=p['source_id'],distance_m=round(distance(seed,p),1)) for p in matched])
        routes={r['id']:r for p in matched for r in p['routes']}
        current['routes']=sorted(routes.values(),key=lambda r:(r['feed'],r['number']))
        result.append(current)
    prepared=territory.polygons(json.loads(payload['isere-limits.json']))
    selected_routes={r['id'] for stop in result for r in stop['routes']}
    for feed in feeds.values():
        for p in feed['points']:
            p['in_isere']=territory.contains(p,prepared) if p['is_station'] else False
            if p['is_station'] and p['in_isere']:selected_routes.update(r['id'] for r in p['routes'])
    complete=[]
    for code,feed in feeds.items():
        for p in feed['points']:
            rr=[r for r in p['routes'] if r['id'] in selected_routes]
            if not p['is_station'] or not rr:continue
            sid='gtfs-'+code.lower()+'-'+hashlib.sha256(p['source_id'].encode()).hexdigest()[:20]
            complete.append(dict(id=sid,group=network_group(code),name=p['name'],latitude=p['latitude'],longitude=p['longitude'],altitude=None,status='exact',matches=[dict(feed=code,source_id=p['source_id'],distance_m=0)],routes=rr,in_isere=p['in_isere'],network=SOURCES[code][0]))
    hikes=hiking.c2c_accesses(result+complete,cache,download,cache_only)
    hiking.associate(result+complete,hikes)
    focused_kmz.select_nearest(complete,hikes)
    climbing_input=json.loads((ROOT/'data/climbing-sites.json').read_text())
    climbing_sites=climbing.load(climbing_input,prepared)
    climbing.associate(result+complete,climbing_sites)
    activity_map.enrich(complete,hikes)
    if out.exists():shutil.rmtree(out)
    (out/'arrets').mkdir(parents=True)
    for s in result+complete:(out/'arrets'/(s['id']+'.html')).write_text(stop_page(s,feeds,now))
    make_hiking_pages(out,hikes,now,result+complete)
    climbing.pages(out,climbing_sites,document,lambda refs:access_transport(refs,result+complete))
    for group in ('cars','mreso'):make_kmz(group,result,out,base,complete,hikes)
    focused_count,line_downloads=focused_kmz.generate(complete,out,base,ROOT,colour_icon,PALETTE)
    activity_places=activity_map.generate(complete,hikes,climbing_sites,out,base,out/'Isere_arrets_rando_escalade.kmz')
    activity_map.camptocamp_points(complete,hikes,out,base)
    pdipr_results=pdipr_pilot.generate(complete,json.loads((ROOT/'data/pdipr-pilot.json').read_text()),out,base,document)
    metadata={c:{k:v for k,v in f.items() if k!='points'} for c,f in feeds.items()}
    (out/'escalade.json').write_text(json.dumps(dict(provenance=climbing_input['provenance'],sha256_input=climbing_input['sha256'],attribution='©Oblyk',licenses=['CC BY-NC-SA (contenu)','Open Database License (base)'],license_source=climbing.TERMS,sites=climbing_sites),ensure_ascii=False,separators=(',',':')))
    report=dict(pdipr_pilot_results=pdipr_results,activity_places=activity_places,activity_place_count=len(activity_places),climbing_site_count=len(climbing_sites),climbing_sites_near_stops=sum(bool(site['nearest_stops']) for site in climbing_sites),climbing_stop_count=sum(bool(p['nearest_climbs']) for p in complete),combined_stop_count=sum(bool(p.get('nearest_accesses') or p.get('nearest_climbs')) for p in complete if p['in_isere']),generated_at=now.isoformat(),coverage='Département de l’Isère : arrêts publiés par Cars Région Isère, M réso SEM/GSV/TPV, Ruban et L’va ; sélection montagne initiale conservée',department_boundary_source=territory.SOURCE,licence='ODbL 1.0 (transports) ; CC BY-SA 3.0 (Camptocamp) ; CC BY-NC-SA et ODbL (Oblyk)',sources=metadata,unavailable_sources=unavailable,focused_stop_count=focused_count,line_download_count=line_downloads,counts=dict(Counter(s['status'] for s in result)),stops=result,line_stops=complete,hikes=hikes,hiking_source=hiking.API,hiking_distance_method="great_circle",hiking_threshold_m=1000)
    (out/'camptocamp.json').write_text(json.dumps(dict(generated_at=now.isoformat(),license='CC-BY-SA-3.0',attribution='Camptocamp.org et ses contributeurs',source=hiking.API,modifications='Extraction, conversion de coordonnées, rapprochement géographique avec les arrêts GTFS ; seuil à vol d’oiseau de 1000 m',accesses=hikes),ensure_ascii=False,separators=(',',':')))
    (out/'arrets.json').write_text(json.dumps(report,ensure_ascii=False,separators=(',',':')))
    with (out/'correspondances.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['id','nom','groupe','statut','references_officielles','lignes_actuelles'])
        for s in result:w.writerow([s['id'],s['name'],s['group'],s['status'],';'.join(p['feed']+':'+p['source_id'] for p in s['matches']),';'.join(r['feed']+':'+r['number'] for r in s['routes'])])
    source_body='<h1>Sources et méthode</h1><p>Données : Région Auvergne-Rhône-Alpes / Oùra, SMMAG / Mobilités M, sous licence ODbL 1.0. Sélection et altitudes fournies dans les deux KMZ initiaux. Les valeurs d’altitude n’ont pas été recalculées.</p><ul>'
    for c,f in feeds.items():source_body+='<li>'+html.escape(SOURCES[c][0])+' : <a href="'+html.escape(f['source_url'],quote=True)+'">source GTFS</a>, période '+display_date(f['period_start'])+' au '+display_date(f['period_end'])+'.</li>'
    for c,reason in unavailable.items():source_body+='<li>'+html.escape(SOURCES[c][0])+' : données indisponibles ('+html.escape(reason)+'). <a href="'+NETWORK_PAGES[c]+'">Consulter le réseau officiel</a>.</li>'
    source_body+='</ul><p>La desserte est reconstruite par les identifiants GTFS des courses, arrêts et stations parentes, pas par la proximité d’une ligne dessinée. La sélection initiale est associée par nom normalisé et position (moins de 0,2 m, sinon 25 m maximum), une correspondance au plus par réseau. Les ambiguïtés sont signalées et ne fournissent aucune ligne supposée. Plusieurs réseaux peuvent partager un même arrêt nommé et situé au même endroit.</p><p>Les lignes sont celles de l’offre publiée, toutes périodes confondues. Les calendriers et exceptions ne sont pas interprétés comme une desserte quotidienne : les horaires, la date et le sens sont consultés sur le site officiel. Aucun retard ni prochain départ n’est présenté comme du temps réel ici.</p><p>Les liens Région emploient les identifiants de lignes officiels dans le calculateur régional. Les liens M réso sont extraits du site officiel ou utilisent son format avec un code confirmé par l’API M et la disponibilité timeSheet. Aucun nom de PDF saisonnier n’est deviné.</p><p><a href="arrets.json">Données et licences par source</a> · <a href="correspondances.csv">Rapport de correspondances</a> · <a href="camptocamp.json">Données Camptocamp CC BY-SA 3.0</a> · <a href="https://opendatacommons.org/licenses/odbl/1-0/">Texte de la licence ODbL 1.0</a> · <a href="index.html">Retour aux arrêts</a></p>'
    source_body+='<h2>Limites de l’Isère</h2><p>Contours communaux du département 38 : <a href="'+territory.SOURCE+'">API Découpage administratif de l’État</a>. Les arrêts du dossier départemental sont filtrés dans ces polygones. Les quais d’une station sont regroupés selon le GTFS, sans fusion arbitraire entre réseaux. Les dossiers par ligne peuvent dépasser le département. Les nouvelles altitudes ne sont pas inventées. La couverture dépend des sources disponibles ; services absents de leurs GTFS et réseaux indisponibles ne sont pas présentés comme recensés.</p>'
    source_body+='<h2>Camptocamp</h2><p>Points d’accès et itinéraires associés : Camptocamp.org et ses contributeurs, <a href="https://creativecommons.org/licenses/by-sa/3.0/">CC BY-SA 3.0</a>. Extraction des noms, activités, associations et conversion des coordonnées EPSG:3857 en WGS84. Les fiches donnent les liens vers les documents et leurs historiques de contributeurs. La réutilisation des éléments Camptocamp doit respecter cette licence, distincte de l’ODbL des transports. Rapprochements limités à 1 km à vol d’oiseau ; aucun cheminement validé ni sens de départ déduit. La distinction été/hiver décrit les activités, sans évaluation de praticabilité. Les sommets et le centre géométrique des itinéraires ne servent pas de points de départ.</p>'
    source_body+='<h2>Sites d’escalade Oblyk</h2><p>©Oblyk : '+climbing.LICENSES+'. <a href="'+climbing.TERMS+'">Conditions</a>. Source : KMZ fourni par l’utilisateur, 508 sites, dont '+str(len(climbing_sites))+' dans les contours de l’Isère. Les coordonnées sont conservées, sans assimilation à un parking ou un départ de sentier. L’analyse et les transports sont actualisés ; le fichier des sites est un instantané. Les statuts PDESI et conventionnement de 2024 restent datés et non revérifiés. <a href="escalade.json">Données et provenance Oblyk</a>.</p>'
    source_body+='<h2>Essai PDIPR</h2><p>© Département de l’Isère, <a href="https://www.etalab.gouv.fr/licence-ouverte-open-licence/">Licence Ouverte 2.0</a>. <a href="'+pdipr_pilot.CATALOG+'">Catalogue et données</a>. Un instantané local limité autour de cinq arrêts conserve les géométries originales du réseau. Les proximités sont calculées sur chaque segment, par projection locale puis distance haversine. Aucun circuit, point de départ, balisage PR/GR de Pays ou cheminement d’accès n’est déduit. La carte est un essai séparé de la sélection principale. <a href="pdipr/analyse.json">Résultats et méthode</a>.</p>'
    (out/'sources.html').write_text(document('Sources et méthode',source_body))
    body='<h1>Écomobilité — Isère entière</h1><p>Couverture départementale à partir des GTFS Cars Région Isère, M réso (SEM, GSV, TPV), Ruban et L’va. Les arrêts sont filtrés par les contours officiels des communes de l’Isère. Les dossiers par ligne conservent aussi leurs arrêts hors département pour préparer le trajet complet. La vue montagne initiale est conservée. Les services absents de ces GTFS ne sont pas recensés.</p><p>Données récupérées le '+now.astimezone(PARIS).strftime('%d/%m/%Y à %H h %M')+'. Actualisation quotidienne à 07 h 15, heure de Paris, sous réserve de disponibilité des sources.</p><p><a class="button" href="Mreso_600m_en_ligne.kmz">KMZ M réso — Isère et lignes complètes</a></p><p><a class="button" href="Cars_Isere_600m_en_ligne.kmz">KMZ cars Région, Ruban et L’va — Isère et lignes complètes</a></p><p>Importer ces repères dans AlpineQuest, toucher un arrêt puis son lien pour consulter sa fiche actualisée. Chaque KMZ contient « Tous les arrêts ≥ 600 m » (sélection initiale), « Tous les arrêts en Isère » et « Par ligne ». Masquer la vue générale avant d’afficher une ligne. Les couleurs se répètent ; les numéros distinguent les lignes. La vue générale conserve les 912 points sélectionnés à partir de 600 m ; les dossiers par ligne comprennent aussi les arrêts de plaine et les branches publiées. Tous les cars ne desservent pas chaque branche : vérifier le sens et les horaires. Les dossiers et couleurs sont figés à la génération : télécharger et réimporter pour actualiser la répartition. Les fiches en ligne continuent à s’actualiser.</p>'
    body+='<section><h2>Essai : chemins de plaine autour des arrêts</h2><p><a href="pdipr/index.html">Voir l’essai PDIPR autour de cinq arrêts du secteur de Vienne</a> · <a href="Essai_PDIPR_Vienne.kmz">Télécharger la petite carte d’essai</a></p><p>Ce réseau de tronçons est distinct des circuits Camptocamp. Les points de proximité sont géométriques, pas des départs ou des jonctions accessibles confirmés. Aucun balisage jaune ni GR de Pays n’est supposé.</p></section>'
    body+='<section><h2>Points d’accès Camptocamp nommés</h2><p><a class="button" href="Isere_acces_Camptocamp.kmz">KMZ — accès Camptocamp avec leurs noms</a></p><p>Vert : été / pédestre ; bleu : hiver / raquettes et ski ; violet : été et hiver. Un point par accès, liens vers les transports et les topos. Les couleurs décrivent les activités, sans garantie de praticabilité saisonnière.</p></section>'
    body+='<section><h2>Carte avec pictogrammes et lieux des activités</h2><p><a class="button" href="Isere_ecomobilite_activites.kmz">KMZ complet — arrêts + accès randonnée/ski + sites d’escalade</a></p><p><a href="Isere_points_activites.kmz">Lieux d’activités seuls</a> pour les afficher dans un espace randonnée ou escalade, en complément des arrêts.</p><p>Pictogrammes : marcheur vert, raquettes violettes, skieur bleu, grimpeur orange. La taille des pictogrammes est multipliée par le nombre d’activités (1, 2, 3 ou 4). Le petit badge bus identifie un arrêt ; les lieux d’activités n’ont pas ce badge. Les repères Multi desservent plusieurs activités, détaillées dans leur description. Les dossiers Arrêts bus, Accès randonnée/raquettes/ski et Sites d’escalade peuvent être affichés ou masqués séparément.</p></section>'
    body+='<section><h2>Randonnée et escalade</h2><p><a class="button" href="Isere_arrets_rando_escalade.kmz">KMZ léger — randonnée et escalade réunies</a></p><p><a href="Isere_arrets_escalade.kmz">KMZ escalade uniquement</a> · <a href="escalade/index.html">Consulter les sites d’escalade et leurs arrêts</a></p><p>Même règle : un arrêt le plus proche par ligne et par point d’intérêt, dans un rayon de 1 km à vol d’oiseau. Les sites d’escalade proviennent du KMZ fourni.</p></section>'
    if unavailable:body+='<p class="notice"><b>Couverture incomplète :</b> données indisponibles pour '+', '.join(html.escape(SOURCES[c][0]) for c in unavailable)+'. Ces réseaux ne sont pas intégrés aux repères de cette génération. Voir les sources et les sites officiels.</p>'
    body+='<section><h2>Vue randonnée conseillée</h2><p><a class="button" href="Isere_arrets_randonnee.kmz">Télécharger le KMZ léger — '+str(focused_count)+' arrêts avec accès randonnée</a></p><p>Ce fichier retient, pour chaque ligne et chaque accès Camptocamp, un seul arrêt : le plus proche parmi les arrêts d’Isère, à 1 km maximum à vol d’oiseau. Un arrêt peut rester présent parce qu’il est le meilleur choix pour une autre randonnée ou une autre ligne. En cas d’égalité exacte, un identifiant stable départage les arrêts. Le sens de desserte et le cheminement restent à vérifier. Depuis la fiche d’un arrêt, consulter les sorties puis télécharger la ligne choisie avec tous ses arrêts. Masquer la vue randonnée si nécessaire avant d’afficher la ligne ; masquer ensuite cette ligne pour revenir à la vue légère. Les horaires se consultent depuis les mêmes fiches.</p></section>'
    body+='<p><a href="randos/index.html">Accès Camptocamp et itinéraires été / hiver</a> — présélection à 1 km maximum à vol d’oiseau, cheminement piéton à vérifier.</p>'
    body+='<p><b>'+str(sum(s['status'] in ('exact','nom_et_proximite') for s in result))+' correspondances trouvées sur '+str(len(result))+' points.</b> Les autres restent visibles avec une mention de vérification.</p><label for="search">Rechercher un arrêt ou une commune</label><input id="search" type="search" placeholder="Exemple : Uriage, Chartreuse…"><ul id="stops">'
    for s in [p for p in complete if p.get('in_isere')]:body+='<li data-name="'+html.escape(norm(s['name']),quote=True)+'"><a href="arrets/'+s['id']+'.html">'+html.escape(s['name'])+'</a> · '+(' / '.join(dict.fromkeys(SOURCES[m['feed']][0] for m in s['matches'])))+(' · à vérifier' if s['status'] not in ('exact','nom_et_proximite') else '')+'</li>'
    body+='</ul><p><a href="sources.html">Sources, licence et méthode</a> · <a href="correspondances.csv">Rapport de vérification</a></p><script>document.getElementById("search").addEventListener("input",e=>{const q=e.target.value.normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^a-z0-9]/g,"");document.querySelectorAll("#stops li").forEach(li=>li.hidden=!li.dataset.name.includes(q));});</script>'
    (out/'index.html').write_text(document('Écomobilité — Isère entière',body));(out/'.nojekyll').touch()
    print(json.dumps({'points':len(result),'counts':report['counts'],'site_bytes':sum(p.stat().st_size for p in out.rglob('*') if p.is_file())},ensure_ascii=False))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base-url',default='https://jfmouret.github.io/ecomobilite-isere');ap.add_argument('--output',default='dist');ap.add_argument('--cache',default='.cache');ap.add_argument('--cache-only',action='store_true');a=ap.parse_args()
    build(a.base_url,Path(a.output),Path(a.cache),a.cache_only)


if __name__=='__main__':main()
