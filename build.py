#!/usr/bin/env python3
"""Arrêts sélectionnés -> fiches web et KMZ, à partir des GTFS officiels."""
import argparse
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
}
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


def stop_page(s,feeds,now):
    esc=lambda x:html.escape(str(x),quote=True)
    matched=s['status'] in ('exact','nom_et_proximite')
    body='<a href="../index.html">Tous les arrêts</a><h1>'+esc(s['name'])+'</h1>'
    body+='<p>'+('M réso' if s['group']=='mreso' else 'Cars Région Isère')+' · altitude indiquée dans ton KMZ initial : '+esc(s['altitude'])+' m (IGN, non recalculée).</p>'
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
        for r in s['routes']:
            body+='<section><h3>Ligne '+esc(r['number'])+'</h3><p>'+esc(r['name'])+'</p><p class="muted">'+esc(r['network'])+'</p>'
            if r['url']:body+='<a class="button" href="'+esc(r['url'])+'">Horaires officiels — ligne '+esc(r['number'])+'</a>'
            else:body+='<p>Lien détaillé non confirmé. Consulter le site officiel du réseau ci-dessous.</p>'
            body+='</section>'
        if not s['routes']:body+='<p>Aucune desserte trouvée dans le fichier publié.</p>'
        body+='<details><summary>Correspondance avec les données officielles</summary>'
        for ref in s['matches']:
            f=feeds[ref['feed']]
            body+='<p>'+esc(SOURCES[ref['feed']][0])+' · identifiant '+esc(ref['source_id'])+' · écart de position '+esc(ref['distance_m'])+' m.<br>Période du fichier : '+display_date(f['period_start'])+' au '+display_date(f['period_end'])+'.</p>'
            if f['period_end'] and f['period_end']<now.astimezone(PARIS).strftime('%Y%m%d'):
                body+='<p class="notice">La période du fichier GTFS est dépassée. Vérifier impérativement les informations du réseau.</p>'
        body+='</details>'
    body+='<h2>Informations du réseau</h2>'
    if s['group']=='mreso':body+='<p><a href="https://www.reso-m.fr/61-lignes-et-horaires.htm">M réso : horaires et informations voyageurs</a></p>'
    else:body+='<p><a href="https://www.laregionvoustransporte.fr/cars-region/cars-region-de-lisere/">Cars Région Isère : informations voyageurs</a></p>'
    body+='<p><a href="https://www.oura.com/">Oùra : recherche d’itinéraires</a></p><p class="muted">Les conditions de réservation, les services scolaires, vacances et perturbations doivent être vérifiés auprès du réseau. Cette fiche nécessite du réseau ; une page restée ouverte n’est pas une garantie de consultation hors ligne.</p>'
    body+='<footer><a href="../sources.html">Sources, méthode et licence ODbL 1.0</a> · Mise en forme CAF indépendante des réseaux.</footer>'
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


def make_kmz(group,selection,out,base):
    def sub(parent,tag,text=None,**attrs):
        e=ET.SubElement(parent,'{'+K+'}'+tag,attrs)
        if text is not None:e.text=str(text)
        return e
    root=ET.Element('{'+K+'}kml');doc=sub(root,'Document')
    sub(doc,'name',('M réso' if group=='mreso' else 'Cars Isère')+' — 600 m et plus — par ligne')
    sub(doc,'description','Vue générale dans « Tous les arrêts ». Masquer cette vue puis afficher un dossier dans « Par ligne ». Seuls les arrêts de la sélection initiale à partir de 600 m sont inclus, pas tous les arrêts des lignes. Les couleurs peuvent se répéter : le numéro identifie la ligne. Les dossiers reflètent les données à la date de génération du KMZ ; les fiches web continuent à s’actualiser.')
    style=sub(doc,'Style',id='arret');icon=sub(style,'IconStyle');sub(icon,'scale',1.1);sub(sub(icon,'Icon'),'href','icons/'+group+'.png')
    selected=[s for s in selection if s['group']==group]
    route_stops=defaultdict(list);routes={}
    for s in selected:
        for r in s['routes']:
            routes[r['id']]=r;route_stops[r['id']].append(s)
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
        info='<div style="font-size:20px;max-width:320px"><h2>'+html.escape(s['name'])+'</h2><p>Altitude indiquée : '+str(s['altitude'])+' m.</p><p>Lignes à la génération du KMZ : '+html.escape(numbers)+'.</p>'
        if route:info+='<p><b>Ligne '+html.escape(route['number'])+'</b> : '+html.escape(route['name'])+'</p>'
        info+='<p><a href="'+html.escape(link,quote=True)+'"><b>Consulter les lignes et horaires actualisés — connexion requise</b></a></p></div>'
        sub(p,'description',info);sub(sub(p,'Point'),'coordinates',f'{s["longitude"]},{s["latitude"]},0')
    general=sub(doc,'Folder',id='all-stops');sub(general,'name','Tous les arrêts');sub(general,'visibility',1)
    for s in selected:point(general,s,s['id'])
    per_line=sub(doc,'Folder',id='by-line');sub(per_line,'name','Par ligne');sub(per_line,'visibility',0)
    for i,rid in enumerate(ids):
        r=routes[rid];folder=sub(per_line,'Folder',id='line-'+str(i))
        sub(folder,'name','Ligne '+r['number']+' — '+r['name']+' ('+str(len(route_stops[rid]))+' points)')
        sub(folder,'visibility',0)
        for s in route_stops[rid]:point(folder,s,'line-'+str(i)+'-'+s['id'],r)
    filename='Mreso_600m_en_ligne.kmz' if group=='mreso' else 'Cars_Isere_600m_en_ligne.kmz'
    with zipfile.ZipFile(out/filename,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('doc.kml',ET.tostring(root,encoding='utf-8',xml_declaration=True));z.write(ROOT/'data'/f'{group}.png','icons/'+group+'.png')
        for colour,data in icons.items():z.writestr('icons/'+colour+'.png',data)


def build(base,out,cache,cache_only=False):
    now=dt.datetime.now(dt.timezone.utc)
    cache.mkdir(parents=True,exist_ok=True)
    urls={code+'.zip':u for code,(_,u) in SOURCES.items()}
    urls.update({'m-routes.json':M_ROUTES,'m-horaires.html':M_SCHEDULES})
    def fetch(item):
        name,url=item;p=cache/name
        if cache_only:
            if not p.exists():raise ValueError('Cache de test absent : '+name)
        else:p.write_bytes(download(url))
        return name,p.read_bytes()
    with ThreadPoolExecutor(max_workers=3) as pool:payload=dict(pool.map(fetch,urls.items()))
    route_meta={r['gtfsId']:r for r in json.loads(payload['m-routes.json']) if r.get('gtfsId')}
    links=OfficialLinks();links.feed(payload['m-horaires.html'].decode('utf-8'))
    if not links.links:raise ValueError('Liens horaires M réso absents du site officiel')
    feeds={c:read_feed(c,payload[c+'.zip'],route_meta,links.links) for c in SOURCES}
    selected=json.loads((ROOT/'data/selection.json').read_text())
    indexes={'cars':defaultdict(list),'mreso':defaultdict(list)}
    for c,f in feeds.items():
        for p in f['points']:indexes['cars' if c=='ISERE' else 'mreso'][norm(p['name'])].append(p)
    result=[]
    for seed in selected:
        candidates=indexes[seed['group']].get(norm(seed['name']),[])
        matched,status=match_stop(seed,candidates)
        current=dict(seed,status=status,matches=[dict(feed=p['feed'],source_id=p['source_id'],distance_m=round(distance(seed,p),1)) for p in matched])
        routes={r['id']:r for p in matched for r in p['routes']}
        current['routes']=sorted(routes.values(),key=lambda r:(r['feed'],r['number']))
        result.append(current)
    if out.exists():shutil.rmtree(out)
    (out/'arrets').mkdir(parents=True)
    for s in result:(out/'arrets'/(s['id']+'.html')).write_text(stop_page(s,feeds,now))
    for group in ('cars','mreso'):make_kmz(group,result,out,base)
    metadata={c:{k:v for k,v in f.items() if k!='points'} for c,f in feeds.items()}
    report=dict(generated_at=now.isoformat(),coverage='Sélection initiale à partir de 600 m, non exhaustive du département',licence='ODbL 1.0',sources=metadata,counts=dict(Counter(s['status'] for s in result)),stops=result)
    (out/'arrets.json').write_text(json.dumps(report,ensure_ascii=False,separators=(',',':')))
    with (out/'correspondances.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['id','nom','groupe','statut','references_officielles','lignes_actuelles'])
        for s in result:w.writerow([s['id'],s['name'],s['group'],s['status'],';'.join(p['feed']+':'+p['source_id'] for p in s['matches']),';'.join(r['feed']+':'+r['number'] for r in s['routes'])])
    source_body='<h1>Sources et méthode</h1><p>Données : Région Auvergne-Rhône-Alpes / Oùra, SMMAG / Mobilités M, sous licence ODbL 1.0. Sélection et altitudes fournies dans les deux KMZ initiaux. Les valeurs d’altitude n’ont pas été recalculées.</p><ul>'
    for c,f in feeds.items():source_body+='<li>'+html.escape(SOURCES[c][0])+' : <a href="'+html.escape(f['source_url'],quote=True)+'">source GTFS</a>, période '+display_date(f['period_start'])+' au '+display_date(f['period_end'])+'.</li>'
    source_body+='</ul><p>La desserte est reconstruite par les identifiants GTFS des courses, arrêts et stations parentes, pas par la proximité d’une ligne dessinée. La sélection initiale est associée par nom normalisé et position (moins de 0,2 m, sinon 25 m maximum), une correspondance au plus par réseau. Les ambiguïtés sont signalées et ne fournissent aucune ligne supposée. Plusieurs réseaux peuvent partager un même arrêt nommé et situé au même endroit.</p><p>Les lignes sont celles de l’offre publiée, toutes périodes confondues. Les calendriers et exceptions ne sont pas interprétés comme une desserte quotidienne : les horaires, la date et le sens sont consultés sur le site officiel. Aucun retard ni prochain départ n’est présenté comme du temps réel ici.</p><p>Les liens Région emploient les identifiants de lignes officiels dans le calculateur régional. Les liens M réso sont extraits du site officiel ou utilisent son format avec un code confirmé par l’API M et la disponibilité timeSheet. Aucun nom de PDF saisonnier n’est deviné.</p><p><a href="arrets.json">Base dérivée publiée sous ODbL 1.0</a> · <a href="correspondances.csv">Rapport de correspondances</a> · <a href="https://opendatacommons.org/licenses/odbl/1-0/">Texte de la licence ODbL 1.0</a> · <a href="index.html">Retour aux arrêts</a></p>'
    (out/'sources.html').write_text(document('Sources et méthode',source_body))
    body='<h1>Écomobilité — arrêts à partir de 600 m</h1><p>Cars Région Isère et M réso : sélection issue de tes deux KMZ. Ce catalogue ne recense pas tous les arrêts du département ; certains arrêts du réseau régional se trouvent dans les départements voisins.</p><p>Données récupérées le '+now.astimezone(PARIS).strftime('%d/%m/%Y à %H h %M')+'. Actualisation quotidienne à 07 h 15, heure de Paris, sous réserve de disponibilité des sources.</p><p><a class="button" href="Mreso_600m_en_ligne.kmz">KMZ M réso — 165 points</a></p><p><a class="button" href="Cars_Isere_600m_en_ligne.kmz">KMZ cars Région — 747 points</a></p><p>Importer ces repères dans AlpineQuest, toucher un arrêt puis son lien pour consulter sa fiche actualisée. Chaque KMZ contient « Tous les arrêts » et « Par ligne ». Masquer la vue générale avant d’afficher une ligne. Les couleurs se répètent ; les numéros distinguent les lignes. Seuls les arrêts sélectionnés à partir de 600 m sont inclus. Les dossiers et couleurs sont figés à la génération : télécharger et réimporter pour actualiser la répartition. Les fiches en ligne continuent à s’actualiser.</p>'
    body+='<p><b>'+str(sum(s['status'] in ('exact','nom_et_proximite') for s in result))+' correspondances trouvées sur '+str(len(result))+' points.</b> Les autres restent visibles avec une mention de vérification.</p><label for="search">Rechercher un arrêt ou une commune</label><input id="search" type="search" placeholder="Exemple : Uriage, Chartreuse…"><ul id="stops">'
    for s in result:body+='<li data-name="'+html.escape(norm(s['name']),quote=True)+'"><a href="arrets/'+s['id']+'.html">'+html.escape(s['name'])+'</a> · '+('M réso' if s['group']=='mreso' else 'Cars Région')+(' · à vérifier' if s['status'] not in ('exact','nom_et_proximite') else '')+'</li>'
    body+='</ul><p><a href="sources.html">Sources, licence et méthode</a> · <a href="correspondances.csv">Rapport de vérification</a></p><script>document.getElementById("search").addEventListener("input",e=>{const q=e.target.value.normalize("NFD").replace(/[\u0300-\u036f]/g,"").toLowerCase().replace(/[^a-z0-9]/g,"");document.querySelectorAll("#stops li").forEach(li=>li.hidden=!li.dataset.name.includes(q));});</script>'
    (out/'index.html').write_text(document('Écomobilité Isère — 600 m et plus',body));(out/'.nojekyll').touch()
    print(json.dumps({'points':len(result),'counts':report['counts'],'site_bytes':sum(p.stat().st_size for p in out.rglob('*') if p.is_file())},ensure_ascii=False))


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base-url',default='https://jfmouret.github.io/ecomobilite-isere');ap.add_argument('--output',default='dist');ap.add_argument('--cache',default='.cache');ap.add_argument('--cache-only',action='store_true');a=ap.parse_args()
    build(a.base_url,Path(a.output),Path(a.cache),a.cache_only)


if __name__=='__main__':main()
