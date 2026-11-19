"""Repères randonnée légers et fichiers des lignes téléchargeables à la demande."""
import hashlib
import html
import xml.etree.ElementTree as ET
import zipfile
from collections import defaultdict
import hiking
import map_icons

K='http://www.opengis.net/kml/2.2'


def line_filename(route_id):return hashlib.sha256(route_id.encode()).hexdigest()[:24]+'.kmz'


def write_kmz(stops,destination,base,title,icon_bytes,route=None,purpose="rando"):
    def sub(parent,tag,text=None,**attrs):
        e=ET.SubElement(parent,'{'+K+'}'+tag,attrs)
        if text is not None:e.text=str(text)
        return e
    root=ET.Element('{'+K+'}kml');doc=sub(root,'Document');sub(doc,'name',title)
    sub(doc,'description','Repères extraits des données officielles. Ouvrir la fiche de l’arrêt pour les randonnées et horaires actualisés. Un accès à moins de 1 km à vol d’oiseau ne garantit pas un cheminement piéton.')
    style=sub(doc,'Style',id='bus');icon=sub(style,'IconStyle');sub(icon,'scale',1.1);sub(sub(icon,'Icon'),'href','icons/bus.png')
    assets={'icons/bus.png':icon_bytes};styles=set()
    for s in stops:
        types=s.get('activity_types',[]) if route is None else []
        marker=map_icons.key(types)
        style_url='#bus'
        if types:
            if marker not in styles:
                style=sub(doc,'Style',id='activity-'+marker);ic=sub(style,'IconStyle');sub(ic,'scale',map_icons.activity_scale(types));sub(sub(ic,'Icon'),'href','icons/'+marker+'.png');sub(sub(style,'LabelStyle'),'scale',.8)
                assets['icons/'+marker+'.png']=map_icons.icon(types,stop=True);styles.add(marker)
            style_url='#activity-'+marker
        p=sub(doc,'Placemark',id=s['id']);sub(p,'name',(map_icons.label(types)+' · ' if types else '')+s['name']);sub(p,'styleUrl',style_url)
        numbers=', '.join(dict.fromkeys(r['number'] for r in s['routes']))
        info='<div style="font-size:20px;max-width:320px"><h2>'+html.escape(s['name'])+'</h2><p>Lignes à la génération du fichier : '+html.escape(numbers)+'.</p>'
        if types:info+='<p>Activités : '+html.escape(', '.join(map_icons.LABELS[t] for t in types))+'. Le pictogramme bus représente cet arrêt ; ses activités sont indiquées dans le nom et cette fiche.</p>'
        if route:info+='<p>'+html.escape(route['network'])+' · ligne '+html.escape(route['number'])+' · '+html.escape(route['name'])+'</p>'
        elif purpose!='rando':info+='<p>Arrêt retenu comme le plus proche sur sa ligne pour au moins un '+('site d’escalade' if purpose=='escalade' else 'accès randonnée ou site d’escalade')+' dans le rayon de 1 km à vol d’oiseau. Cheminement et sens de desserte à vérifier.</p>'
        else:info+='<p>Arrêt le plus proche, parmi les arrêts d’Isère de sa ligne, pour au moins un accès Camptocamp à 1 km maximum à vol d’oiseau. Cheminement et sens de desserte à vérifier.</p>'
        info+='<p><a href="'+base.rstrip('/')+'/arrets/'+s['id']+'.html"><b>Randonnées, escalade, horaires et affichage d’une ligne complète</b></a></p></div>'
        sub(p,'description',info);sub(sub(p,'Point'),'coordinates',str(s['longitude'])+','+str(s['latitude'])+',0')
    map_icons.separate_symbols(root,assets)
    with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('doc.kml',ET.tostring(root,encoding='utf-8',xml_declaration=True))
        for name,data in assets.items():z.writestr(name,data)


def select_nearest(stops,hikes):
    """Un gagnant par accès/activité et identifiant de ligne, sans arrondir le classement."""
    by_id={h['id']:h for h in hikes}
    best={}
    for s in stops:
        s['nearest_accesses']=[]
        if not s.get('in_isere'):continue
        for ref in s.get('hikes',[]):
            distance=hiking.metres(s,by_id[ref['id']])
            if distance>1000:continue
            for route in s['routes']:
                key=(ref['id'],route['id'])
                candidate=(distance,s['id'])
                if key not in best or candidate<best[key][0]:best[key]=(candidate,s,route)
    for (access_id,rid),((distance,_),s,route) in sorted(best.items()):
        s['nearest_accesses'].append(dict(access_id=access_id,route_id=rid,number=route['number'],network=route['network'],distance_m=round(distance)))
    return [s for s in stops if s['nearest_accesses']]


def generate(stops,out,base,root,colour_icon,palette):
    focused=[s for s in stops if s.get('in_isere') and s.get('nearest_accesses')]
    write_kmz(focused,out/'Isere_arrets_randonnee.kmz',base,'Isère — arrêts avec accès randonnée à 1 km',(root/'data/mreso.png').read_bytes())
    climbing_stops=[s for s in stops if s.get('in_isere') and s.get('nearest_climbs')]
    combined=[s for s in stops if s.get('in_isere') and (s.get('nearest_accesses') or s.get('nearest_climbs'))]
    write_kmz(climbing_stops,out/'Isere_arrets_escalade.kmz',base,'Isère — arrêts pour les sites d’escalade',(root/'data/mreso.png').read_bytes(),purpose='escalade')
    write_kmz(combined,out/'Isere_arrets_rando_escalade.kmz',base,'Isère — arrêts randonnée et escalade',(root/'data/mreso.png').read_bytes(),purpose='rando-escalade')
    lines=defaultdict(list);routes={}
    for s in stops:
        for route in s['routes']:
            lines[route['id']].append(s);routes[route['id']]=route
    (out/'lignes').mkdir()
    for rid,route in routes.items():
        rgb=bytes.fromhex(palette[int(hashlib.sha256(rid.encode()).hexdigest()[:8],16)%len(palette)])
        write_kmz(lines[rid],out/'lignes'/line_filename(rid),base,route['network']+' — ligne '+route['number']+' — '+route['name'],colour_icon(tuple(rgb)),route)
    return len(focused),len(lines)
