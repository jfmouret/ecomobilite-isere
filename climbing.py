"""Sites Oblyk fournis en KMZ : rapprochement avec les arrêts, sans inférer l’accès."""
import html
import hiking
import territory

TERMS='https://oblyk.org/fr/conditions-d-utilisation'
LICENSES='<a href="https://creativecommons.org/licenses/">CC BY-NC-SA</a> et <a href="https://opendatacommons.org/licenses/odbl/">Open Database License</a>'


def load(data,prepared):
    sites=[]
    for site in data['sites']:
        if territory.contains(site,prepared):sites.append(dict(site,stops=[]))
    return sites


def associate(stops,sites):
    for stop in stops:
        stop['climbs']=[];stop['nearest_climbs']=[]
    best={}
    for site in sites:
        site['stops']=[];site['nearest_stops']=[]
        for stop in stops:
            distance=hiking.metres(stop,site)
            if distance>1000:continue
            stop['climbs'].append(dict(id=site['id'],name=site['name'],source=site['source'],distance_m=round(distance)))
            site['stops'].append(dict(id=stop['id'],name=stop['name'],distance_m=round(distance)))
            if not stop.get('in_isere'):continue
            for route in stop['routes']:
                key=(site['id'],route['id']);candidate=(distance,stop['id'])
                if key not in best or candidate<best[key][0]:best[key]=(candidate,stop,route,site)
    for (site_id,rid),((distance,_),stop,route,site) in sorted(best.items()):
        stop['nearest_climbs'].append(dict(site_id=site_id,route_id=rid,number=route['number'],network=route['network'],distance_m=round(distance)))
        site['nearest_stops'].append(dict(id=stop['id'],name=stop['name'],route_id=rid,number=route['number'],network=route['network'],distance_m=round(distance)))


def links(stop,base='../'):
    if not stop.get('climbs'):return ''
    body='<h2>Sites d’escalade à proximité</h2><p>Distance à vol d’oiseau vers le point du site Oblyk fourni dans le KMZ, pas nécessairement vers un parking ou une entrée. Cheminement et accès à vérifier.</p><ul>'
    for ref in sorted(stop['climbs'],key=lambda c:c['distance_m']):
        body+='<li><a href="'+base+'escalade/'+ref['id']+'.html">'+html.escape(ref['name'])+'</a> · '+str(ref['distance_m'])+' m'
        chosen=[n for n in stop.get('nearest_climbs',[]) if n['site_id']==ref['id']]
        if chosen:body+=' · arrêt le plus proche retenu pour '+html.escape(', '.join(n['network']+' — '+n['number'] for n in chosen))
        body+='</li>'
    return body+'</ul><p>©Oblyk · '+LICENSES+' · <a href="'+base+'sources.html">Provenance et limites de la sélection</a>.</p>'


def pages(out,sites,document,transport):
    folder=out/'escalade';folder.mkdir()
    intro='<p>Source : KMZ Oblyk_508_conention38.kmz fourni par l’utilisateur. Localisations conservées ; filtrage par les contours de l’Isère et calcul de proximité ajoutés. ©Oblyk · '+LICENSES+'. <a href="'+TERMS+'">Conditions et attribution</a>. Cette sélection est un instantané du fichier fourni, sans actualisation automatique des sites Oblyk.</p><p>Seuil de 1 km à vol d’oiseau jusqu’au point du site ; aucun itinéraire piéton calculé. Les mentions PDESI et conventionnement du fichier sont historiques et non revérifiées ; consulter les informations actuelles du gestionnaire et de la fiche Oblyk.</p>'
    index='<a href="../index.html">Accueil</a><h1>Escalade et transports en Isère</h1>'+intro+'<ul>'
    for site in sites:
        if not site['nearest_stops']:continue
        index+='<li><a href="'+site['id']+'.html">'+html.escape(site['name'])+'</a></li>'
    (folder/'index.html').write_text(document('Escalade et transports',index+'</ul>'))
    for site in sites:
        body='<a href="index.html">Sites accessibles à proximité d’un arrêt</a><h1>'+html.escape(site['name'])+'</h1><p><a class="button" href="'+html.escape(site['source'],quote=True)+'">Ouvrir la fiche Oblyk</a></p>'
        refs=[r for r in site['stops'] if r['id'].startswith('gtfs-')] or site['stops']
        body+=transport(refs)
        body+='<h2>Informations du site et sources</h2>'+intro
        body+='<details><summary>Informations conservées du fichier fourni — non actualisées</summary><p>PDESI : '+html.escape(site['pdesi'])+'</p><p>Conventionnement : '+html.escape(site['convention'])+'</p><p>Ces mentions ne valent ni statut actuel ni autorisation d’accès.</p></details>'
        (folder/(site['id']+'.html')).write_text(document(site['name'],body+'<p><a href="../sources.html">Sources et licences</a></p>'))
