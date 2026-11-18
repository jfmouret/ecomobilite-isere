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
            style=sub(doc,'Style',id=style_id);ic=sub(style,'IconStyle');sub(ic,'scale',.65);sub(sub(ic,'Icon'),'href','icons/'+style_id+'.png');sub(sub(style,'LabelStyle'),'scale',.8)
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
    save('Isere_ecomobilite_activites.kmz',root)
    doc.remove(folder);doc.find('{'+K+'}name').text='Isère — lieux des activités accessibles depuis les bus'
    save('Isere_points_activites.kmz',root)
    return records
