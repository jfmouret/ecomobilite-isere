"""Points physiques des activités et catégories des arrêts desservants."""
import html
import xml.etree.ElementTree as ET
import zipfile
import map_icons

K='http://www.opengis.net/kml/2.2'


def enrich(stops,hikes):
    for s in stops:
        selected={n['access_id'] for n in s.get('nearest_accesses',[])};types=set()
        for h in s.get('hikes',[]):
            if h['id'] not in selected:continue
            if h['season']=='ete':types.add('rando')
            for r in h.get('routes',[]):
                if h['season']=='hiver':
                    if 'skitouring' in r['activities']:types.add('ski')
                    if 'snowshoeing' in r['activities']:types.add('raquettes')
        if s.get('nearest_climbs'):types.add('escalade')
        s['activity_types']=[t for t in map_icons.ORDER if t in types]


def destinations(stops,hikes,sites):
    chosen={r['access_id'] for s in stops for r in s.get('nearest_accesses',[])}
    selected_sites={r['site_id'] for s in stops for r in s.get('nearest_climbs',[])}
    by_source={}
    for h in hikes:
        if h['id'] not in chosen:continue
        record=by_source.setdefault(h['source'],dict(id='activity-'+h['id'].rsplit('-',1)[0],name=h['name'],latitude=h['latitude'],longitude=h['longitude'],kind='access',types=set(),links=[]))
        if h['season']=='ete':record['types'].add('rando')
        else:
            for r in h['routes']:
                if 'skitouring' in r['activities']:record['types'].add('ski')
                if 'snowshoeing' in r['activities']:record['types'].add('raquettes')
        record['links'].append(('Accès et itinéraires '+('pédestres' if h['season']=='ete' else 'hivernaux'),'randos/'+h['id']+'.html'))
    records=list(by_source.values())
    for site in sites:
        if site['id'] in selected_sites:records.append(dict(id='activity-'+site['id'],name=site['name'],latitude=site['latitude'],longitude=site['longitude'],kind='climbing',types={'escalade'},links=[('Site et arrêts proches','escalade/'+site['id']+'.html')]))
    for r in records:r['types']=[t for t in map_icons.ORDER if t in r['types']]
    return records


def generate(stops,hikes,sites,out,base,stop_file):
    records=destinations(stops,hikes,sites)
    # Le fichier combiné conserve les repères d’arrêts, puis ajoute les lieux dans des dossiers séparés.
    with zipfile.ZipFile(stop_file) as z:
        root=ET.fromstring(z.read('doc.kml'));assets={n:z.read(n) for n in z.namelist() if n!='doc.kml'}
    def sub(p,t,text=None,**attrs):
        e=ET.SubElement(p,'{'+K+'}'+t,attrs)
        if text is not None:e.text=str(text)
        return e
    doc=root.find('{'+K+'}Document');doc.find('{'+K+'}name').text='Isère — écomobilité et lieux des activités'
    folder=sub(doc,'Folder',id='bus-stops');sub(folder,'name','Arrêts bus — activités accessibles');sub(folder,'visibility',1)
    for p in list(doc):
        if p.tag=='{'+K+'}Placemark':doc.remove(p);folder.append(p)
    groups={}
    for kind,title in [('access','Accès randonnée, raquettes et ski'),('climbing','Sites d’escalade')]:
        f=sub(doc,'Folder',id='places-'+kind);sub(f,'name',title);sub(f,'visibility',1);groups[kind]=f
    styles=set()
    for record in records:
        key=map_icons.key(record['types']);style_id='place-'+key
        if style_id not in styles:
            style=sub(doc,'Style',id=style_id);ic=sub(style,'IconStyle');sub(ic,'scale',map_icons.activity_scale(record['types']));sub(sub(ic,'Icon'),'href','icons/'+style_id+'.png');sub(sub(style,'LabelStyle'),'scale',.8)
            assets['icons/'+style_id+'.png']=map_icons.icon(record['types']);styles.add(style_id)
        p=sub(groups[record['kind']],'Placemark',id=record['id']);sub(p,'name',map_icons.label(record['types'])+' · '+record['name']);sub(p,'styleUrl','#'+style_id)
        desc='<div style="font-size:20px;max-width:320px"><h2>'+html.escape(record['name'])+'</h2><p>'+('Point du site Oblyk fourni, pas nécessairement un parking ni une entrée.' if record['kind']=='climbing' else 'Point d’accès Camptocamp associé aux itinéraires ; départ ou arrivée de traversée à vérifier dans le topo.')+'</p>'
        for label,path in record['links']:desc+='<p><a href="'+base.rstrip('/')+'/'+path+'">'+label+'</a></p>'
        desc+='<p><a href="'+base.rstrip('/')+'/sources.html">Sources et licences : ©Oblyk, CC BY-NC-SA et ODbL ; Camptocamp et contributeurs, CC BY-SA 3.0</a></p></div>'
        sub(p,'description',desc);sub(sub(p,'Point'),'coordinates',str(record['longitude'])+','+str(record['latitude'])+',0')
    def save(filename,root):
        with zipfile.ZipFile(out/filename,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('doc.kml',ET.tostring(root,encoding='utf-8',xml_declaration=True))
            for name,data in assets.items():z.writestr(name,data)
    map_icons.separate_symbols(root,assets)
    save('Isere_ecomobilite_activites.kmz',root)
    doc.remove(folder);doc.find('{'+K+'}name').text='Isère — lieux des activités accessibles depuis les bus'
    save('Isere_points_activites.kmz',root)
    return records


def camptocamp_points(stops,hikes,out,base):
    """Un point nommé par accès physique ; couleur selon les activités associées."""
    chosen={r['access_id'] for s in stops for r in s.get('nearest_accesses',[])}
    points={}
    for h in hikes:
        if h['id'] not in chosen:continue
        point=points.setdefault(h['source'],dict(name=h['name'],latitude=h['latitude'],longitude=h['longitude'],source=h['source'],seasons=set(),accesses=[],routes={}))
        point['seasons'].add(h['season']);point['accesses'].append(h)
        for route in h['routes']:point['routes'][route['id']]=route
    def sub(p,t,text=None,**attrs):
        e=ET.SubElement(p,'{'+K+'}'+t,attrs)
        if text is not None:e.text=str(text)
        return e
    root=ET.Element('{'+K+'}kml');doc=sub(root,'Document')
    sub(doc,'name','Isère — points d’accès Camptocamp nommés')
    sub(doc,'description','Vert : pédestre (été) ; bleu : raquettes/ski (hiver) ; violet : les deux. Ces catégories décrivent les activités associées, sans garantir la praticabilité saisonnière. Points d’accès Camptocamp, pas nécessairement départs de chaque course ; vérifier les topos. Aucune liaison piétonne depuis le bus n’est calculée. © Camptocamp.org et ses contributeurs, CC BY-SA 3.0. Coordonnées converties, regroupement par accès et couleurs ajoutés.')
    assets={};folders={}
    for key,title,colour in [('ete','Été — pédestre',(46,125,50)),('hiver','Hiver — raquettes et ski',(21,101,192)),('mixte','Été et hiver',(123,31,162))]:
        style=sub(doc,'Style',id='access-'+key);ic=sub(style,'IconStyle');sub(ic,'scale',.65)
        sub(sub(ic,'Icon'),'href','icons/access-'+key+'.png')
        sub(sub(style,'LabelStyle'),'scale',1)
        canvas=map_icons.Canvas();canvas.disc(24,24,15,(255,255,255));canvas.disc(24,24,12,colour)
        assets['icons/access-'+key+'.png']=canvas.png()
        folders[key]=sub(doc,'Folder',id='accesses-'+key);sub(folders[key],'name',title)
    esc=lambda x:html.escape(str(x),quote=True)
    for i,p in enumerate(sorted(points.values(),key=lambda p:p['name'].casefold())):
        key='mixte' if len(p['seasons'])==2 else next(iter(p['seasons']))
        mark=sub(folders[key],'Placemark',id='c2c-access-'+str(i));sub(mark,'name',p['name']);sub(mark,'styleUrl','#access-'+key)
        desc='<h2>'+esc(p['name'])+'</h2><p>Point d’accès associé aux itinéraires, départ ou arrivée à vérifier dans chaque topo. Cheminement depuis l’arrêt à préparer sur la carte.</p><p><a href="'+esc(p['source'])+'">Point d’accès sur Camptocamp</a></p>'
        for access in p['accesses']:
            desc+='<p><a href="'+esc(base.rstrip('/')+'/randos/'+access['id']+'.html')+'">Transports et itinéraires '+('pédestres' if access['season']=='ete' else 'hivernaux')+'</a></p>'
        desc+='<h3>Topos Camptocamp associés</h3><ul>'
        for route in sorted(p['routes'].values(),key=lambda r:r['name'].casefold()):
            desc+='<li><a href="'+esc(route['url'])+'">'+esc(route['name'])+'</a> · '+esc(', '.join({'hiking':'Randonnée pédestre','snowshoeing':'Raquettes','skitouring':'Ski de randonnée'}.get(a,a) for a in route['activities']))+'</li>'
        desc+='</ul><p>© Camptocamp.org et ses contributeurs · <a href="https://creativecommons.org/licenses/by-sa/3.0/">CC BY-SA 3.0</a> · <a href="'+esc(p['source'].replace('/waypoints/','/waypoints/history/'))+'">Historique et contributeurs du point</a>. Attribution des itinéraires sur leurs fiches liées.</p>'
        sub(mark,'description',desc);sub(sub(mark,'Point'),'coordinates',str(p['longitude'])+','+str(p['latitude'])+',0')
    with zipfile.ZipFile(out/'Isere_acces_Camptocamp.kmz','w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('doc.kml',ET.tostring(root,encoding='utf-8',xml_declaration=True))
        for name,data in assets.items():z.writestr(name,data)
    return len(points)
