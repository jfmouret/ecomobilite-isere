"""Essai de proximité du réseau PDIPR ; aucun départ ou chemin d’accès n’est inféré."""
import html
import math
import xml.etree.ElementTree as ET
import zipfile
import hiking

SOURCE='https://opendata.isere.fr/api/explore/v2.1/catalog/datasets/plan-departemental-des-itineraires-de-promenades-et-de-randonnees-departement-de/exports/geojson'
CATALOG='https://www.data.gouv.fr/datasets/plan-departemental-des-itineraires-de-promenades-et-de-randonnees-departement-de-lisere'
K='http://www.opengis.net/kml/2.2'


def parts(feature):
    g=feature['geometry']
    if g['type']=='LineString':return [g['coordinates']]
    if g['type']=='MultiLineString':return g['coordinates']
    raise ValueError('PDIPR : géométrie non linéaire')


def closest(stop,feature):
    best=(float('inf'),None);cos=math.cos(math.radians(stop['latitude']))
    for line in parts(feature):
        for a,b in zip(line,line[1:]):
            ax=(a[0]-stop['longitude'])*cos;ay=a[1]-stop['latitude'];dx=(b[0]-a[0])*cos;dy=b[1]-a[1]
            t=max(0,min(1,-(ax*dx+ay*dy)/(dx*dx+dy*dy))) if dx*dx+dy*dy else 0
            p=dict(longitude=a[0]+t*(b[0]-a[0]),latitude=a[1]+t*(b[1]-a[1]))
            distance=hiking.metres(stop,p)
            if distance<best[0]:best=(distance,p)
    return best


def analyse(stops,snapshot):
    by_id={s['id']:s for s in stops};features=snapshot['features'];results=[]
    for pilot in snapshot['pilots']:
        stop=by_id.get(pilot['id'])
        if stop is None:
            results.append(dict(id=pilot['id'],name=pilot['name'],status='arrêt absent du GTFS actuel',near=[]));continue
        if hiking.metres(stop,pilot)>500:
            results.append(dict(id=pilot['id'],name=stop['name'],status='position modifiée : instantané à renouveler',near=[]));continue
        near=[];minimum=(float('inf'),None,None)
        for feature in features:
            d,p=closest(stop,feature);fid=str(feature['properties']['id'])
            if d<minimum[0]:minimum=(d,p,fid)
            if d<=1000:near.append(dict(feature_id=fid,distance_m=round(d),distance_unrounded=d,point=p))
        results.append(dict(id=stop['id'],name=stop['name'],latitude=stop['latitude'],longitude=stop['longitude'],status='analyse géométrique, accès non validé',near=sorted(near,key=lambda r:r['distance_unrounded']),minimum_m=round(minimum[0]) if math.isfinite(minimum[0]) else None))
    return results


def generate(stops,snapshot,out,base,document):
    results=analyse(stops,snapshot);outdir=out/'pdipr';outdir.mkdir()
    features={str(f['properties']['id']):f for f in snapshot['features']}
    intro='<p>Essai séparé autour de cinq arrêts du secteur de Vienne. Source : Département de l’Isère, PDIPR, <a href="'+CATALOG+'">Licence Ouverte 2.0</a>. Réseau téléchargé le '+html.escape(snapshot['retrieved_at'])+'. Les transports sont issus de la génération actuelle.</p><p><b>Il s’agit de proximité d’un réseau, pas de départs de circuits validés.</b> Le point le plus proche résulte d’une projection géométrique sur les lignes. Il peut ne pas être accessible depuis l’arrêt. Aucun trajet piéton ni franchissement n’est calculé. Le jeu ne renseigne pas les noms de circuits, GR de Pays, PR ou couleurs de balisage ; rien de tel n’est déduit ici.</p>'
    index='<a href="../index.html">Accueil</a><h1>Essai PDIPR — secteur de Vienne</h1>'+intro+'<p><a class="button" href="../Essai_PDIPR_Vienne.kmz">Télécharger la carte d’essai AlpineQuest</a></p><ul>'
    root=ET.Element('{'+K+'}kml');doc=ET.SubElement(root,'{'+K+'}Document')
    def sub(p,t,text=None,**attrs):
        e=ET.SubElement(p,'{'+K+'}'+t,attrs)
        if text is not None:e.text=str(text)
        return e
    sub(doc,'name','ESSAI — proximité PDIPR autour de Vienne, accès non validés')
    sub(doc,'description','© Département de l’Isère, Licence Ouverte 2.0. Instantané du réseau : '+snapshot['retrieved_at']+'. Les tracés turquoise sont des tronçons PDIPR, leur couleur ne représente pas un balisage officiel. Les points de proximité ne sont ni des départs de balade ni des jonctions accessibles confirmées.')
    style=sub(doc,'Style',id='network');ls=sub(style,'LineStyle');sub(ls,'color','ffb0a000');sub(ls,'width',3)
    for sid,colour in [('bus','ffbb6611'),('near','ff00aaff')]:
        st=sub(doc,'Style',id=sid);ic=sub(st,'IconStyle');sub(ic,'color',colour);sub(ic,'scale',.7)
    fstop=sub(doc,'Folder',id='pilot-stops');sub(fstop,'name','Arrêts de l’essai')
    fpoint=sub(doc,'Folder',id='near-network');sub(fpoint,'name','Points géométriques proches — à vérifier')
    fline=sub(doc,'Folder',id='network-lines');sub(fline,'name','Tronçons PDIPR proches — pas des circuits')
    used=set()
    for result in results:
        near=result['near'];distance=result.get('minimum_m')
        index+='<li><a href="'+result['id']+'.html">'+html.escape(result['name'])+'</a> : '+str(len(near))+' tronçons dans le rayon de 1 km'+(' · minimum '+str(distance)+' m' if distance is not None else '')+'</li>'
        body='<a href="index.html">Retour à l’essai</a><h1>'+html.escape(result['name'])+'</h1>'+intro+'<p>Statut : '+html.escape(result['status'])+'.</p>'
        if near:
            body+='<p><b>'+str(len(near))+' tronçons sont à 1 km maximum à vol d’oiseau ; le réseau le plus proche est à environ '+str(distance)+' m.</b> Les tronçons complets sont affichés : certaines portions peuvent sortir du rayon.</p>'
        else:body+='<p>Aucun tronçon trouvé dans le rayon de 1 km dans cet essai.'+(' Le réseau le plus proche trouvé dans l’instantané est à '+str(distance)+' m.' if distance is not None else ' La distance n’est pas disponible pour ce point.')+'</p>'
        if 'longitude' in result:body+='<p><a href="../arrets/'+result['id']+'.html">Lignes et horaires de cet arrêt</a> · <a href="https://isereoutdoor.fr/fr">Consulter Isère Outdoor (recherche complémentaire, sans filtre de distance garanti)</a></p><h2>Tronçons proches</h2><ul>'
        for n in near:
            feature=features[n['feature_id']]
            body+='<li>Tronçon '+html.escape(n['feature_id'])+' — '+str(n['distance_m'])+' m — gestionnaire : '+html.escape(feature['properties'].get('gestionnaire_nom') or 'non renseigné')+'</li>'
            used.add(n['feature_id'])
        (outdir/(result['id']+'.html')).write_text(document(result['name']+' — essai PDIPR',body+'</ul><p><a href="../sources.html">Sources et méthode</a></p>'))
        if 'longitude' not in result:continue
        p=sub(fstop,'Placemark',id=result['id']);sub(p,'name','Bus — '+result['name']);sub(p,'styleUrl','#bus');sub(p,'description','<a href="'+base.rstrip('/')+'/pdipr/'+result['id']+'.html">Proximité du réseau PDIPR — résultats, limites et horaires</a>');sub(sub(p,'Point'),'coordinates',str(result['longitude'])+','+str(result['latitude'])+',0')
        if near:
            n=near[0];p=sub(fpoint,'Placemark',id='projection-'+result['id']);sub(p,'name','PDIPR proche — accès à vérifier');sub(p,'styleUrl','#near');sub(p,'description','<a href="'+base.rstrip('/')+'/pdipr/'+result['id']+'.html">Projection géométrique à '+str(n['distance_m'])+' m : pas un départ officiel ni un cheminement validé</a>');sub(sub(p,'Point'),'coordinates',str(n['point']['longitude'])+','+str(n['point']['latitude'])+',0')
    for fid in sorted(used):
        feature=features[fid];p=sub(fline,'Placemark',id='pdipr-'+fid);sub(p,'name','PDIPR — tronçon '+fid);sub(p,'styleUrl','#network');sub(p,'description','© Département de l’Isère — Licence Ouverte 2.0. Géométrie conservée. Aucun nom de circuit ou balisage n’est déduit. Source : '+CATALOG)
        geom=sub(p,'MultiGeometry')
        for line in parts(feature):sub(sub(geom,'LineString'),'coordinates',' '.join(str(p[0])+','+str(p[1])+',0' for p in line))
    with zipfile.ZipFile(out/'Essai_PDIPR_Vienne.kmz','w',zipfile.ZIP_DEFLATED) as z:z.writestr('doc.kml',ET.tostring(root,encoding='utf-8',xml_declaration=True))
    (outdir/'index.html').write_text(document('Essai PDIPR Vienne',index+'</ul>'))
    import json
    (outdir/'analyse.json').write_text(json.dumps(dict(source=CATALOG,retrieved_at=snapshot['retrieved_at'],licence='Licence Ouverte 2.0',method='Projection locale sur chaque segment puis distance haversine ; seuil non arrondi 1000 m ; aucun cheminement ou départ validé',results=results),ensure_ascii=False,separators=(',',':')))
    return results
