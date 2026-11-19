"""Contrôle du produit réellement généré, exécuté avant publication."""
import json
from pathlib import Path
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from build import ROOT,K


def logical_tree(payload):
    """Vérifie les copies graphiques avant de compter les lieux physiques."""
    root=ET.fromstring(payload);k='{'+K+'}'
    marks={p.attrib['id']:p for p in root.iter(k+'Placemark')}
    for parent in root.iter():
        for p in list(parent):
            data=p.find(k+'ExtendedData/'+k+'Data[@name="symbol_parent"]/'+k+'value')
            if data is None:continue
            original=marks[data.text]
            assert p.find(k+'Point/'+k+'coordinates').text==original.find(k+'Point/'+k+'coordinates').text
            assert p.find(k+'description').text==original.find(k+'description').text
            assert p.find(k+'styleUrl').text.startswith('#separate-')
            parent.remove(p)
    return root


def verify(out=Path('dist')):
    seeds=json.loads((ROOT/'data/selection.json').read_text())
    report=json.loads((out/'arrets.json').read_text())
    assert len(seeds)==912 and len({s['id'] for s in seeds})==912
    assert min(s['altitude'] for s in seeds)>=600
    assert len(report['stops'])==len(seeds)
    assert len(list((out/'arrets').glob('*.html')))==len(seeds)+len(report['line_stops'])
    by_id={s['id']:s for s in report['stops']+report['line_stops']}
    for group,filename,count in [('mreso','Mreso_600m_en_ligne.kmz',165),('cars','Cars_Isere_600m_en_ligne.kmz',747)]:
        with zipfile.ZipFile(out/filename) as z:
            assert z.testzip() is None
            root=logical_tree(z.read('doc.kml'))
            ns={'k':K}
            doc=root.find('k:Document',ns)
            general=doc.find("k:Folder[@id='all-stops']",ns)
            lines=doc.find("k:Folder[@id='by-line']",ns)
            dept=doc.find("k:Folder[@id='isere-stops']",ns)
            dept_ids={p.attrib['id'].removeprefix('isere-') for p in dept.findall('k:Placemark',ns)}
            assert dept_ids=={p['id'] for p in report['line_stops'] if p['group']==group and p['in_isere']}
            for sid in dept_ids:assert (out/'arrets'/(sid+'.html')).is_file()
            marks=general.findall('k:Placemark',ns)
            assert len(marks)==count
            icon=root.find('.//k:Icon/k:href',ns).text
            assert z.read(icon).startswith(b'\x89PNG\r\n\x1a\n')
            all_ids=[e.attrib['id'] for e in root.iter() if 'id' in e.attrib]
            assert len(all_ids)==len(set(all_ids))
            for href in root.findall('.//k:Icon/k:href',ns):
                assert z.read(href.text).startswith(b'\x89PNG\r\n\x1a\n')
            expected={}
            for seed in report['line_stops']:
                if seed['group']==group:
                    for route in seed['routes']:expected.setdefault(route['id'],set()).add(seed['id'])
            folders=lines.findall('k:Folder',ns)
            assert len(folders)==len(expected)
            actual_sets=[]
            for folder in folders:
                ids=set()
                for point in folder.findall('k:Placemark',ns):
                    sid=point.attrib['id'].split('-',2)[2]
                    ids.add(sid)
                    assert point.find('k:styleUrl',ns).text.startswith('#colour-')
                    route_number=point.find('k:name',ns).text.split(' · ',1)[0]
                    assert any(r['number']==route_number for r in by_id[sid]['routes'])
                actual_sets.append(ids)
            # Multiset: deux lignes peuvent desservir exactement les mêmes points.
            from collections import Counter
            assert Counter(frozenset(x) for x in actual_sets)==Counter(frozenset(x) for x in expected.values())
            for p in marks:
                s=by_id[p.attrib['id']]
                assert s['group']==group
                xyz=p.find('k:Point/k:coordinates',ns).text.split(',')
                assert (float(xyz[0]),float(xyz[1]))==(s['longitude'],s['latitude'])
                text=p.find('k:description',ns).text
                assert '/arrets/'+s['id']+'.html' in text
                assert 'Lignes :' not in text
                page=out/'arrets'/(s['id']+'.html')
                assert page.is_file()
                if s['status'] not in ('exact','nom_et_proximite'):
                    assert not s['routes']
                    assert 'Correspondance à vérifier' in page.read_text()
                for r in s['routes']:
                    if r['url']:
                        u=urllib.parse.urlparse(r['url'])
                        assert u.scheme=='https'
                        assert u.hostname in ('www.reso-m.fr','sim.laregionvoustransporte.fr','www.rubantransport.com','www.lva-mobilite.fr')
    import focused_kmz
    focused={s['id'] for s in report['line_stops'] if s.get('in_isere') and s.get('nearest_accesses')}
    with zipfile.ZipFile(out/'Isere_arrets_randonnee.kmz') as z:
        assert z.testzip() is None
        tree=logical_tree(z.read('doc.kml'))
        assert {p.attrib['id'] for p in tree.findall('.//{'+K+'}Placemark')}==focused
        assert not tree.findall('.//{'+K+'}Folder')
    expected_lines={r['id'] for s in report['line_stops'] for r in s['routes']}
    assert len(list((out/'lignes').glob('*.kmz')))==len(expected_lines)
    for rid in expected_lines:
        expected_stops={s['id'] for s in report['line_stops'] if any(r['id']==rid for r in s['routes'])}
        with zipfile.ZipFile(out/'lignes'/focused_kmz.line_filename(rid)) as z:
            assert z.testzip() is None
            tree=logical_tree(z.read('doc.kml'))
            assert {p.attrib['id'] for p in tree.findall('.//{'+K+'}Placemark')}==expected_stops
    climb_data=json.loads((out/'escalade.json').read_text())
    site_by_id={s['id']:s for s in climb_data['sites']}
    original_sites={s['id']:s for s in json.loads((ROOT/'data/climbing-sites.json').read_text())['sites']}
    for site in site_by_id.values():
        assert (site['latitude'],site['longitude'])==(original_sites[site['id']]['latitude'],original_sites[site['id']]['longitude'])
        assert (out/'escalade'/(site['id']+'.html')).is_file()
    import hiking
    pairs=set()
    for stop in report['line_stops']:
        for ref in stop.get('climbs',[]):assert hiking.metres(stop,site_by_id[ref['id']])<=1000
        for ref in stop.get('nearest_climbs',[]):
            key=(ref['site_id'],ref['route_id'])
            assert key not in pairs
            pairs.add(key)
            candidates=[p for p in report['line_stops'] if p['in_isere'] and any(r['id']==ref['route_id'] for r in p['routes']) and any(c['id']==ref['site_id'] for c in p['climbs'])]
            winner=min(candidates,key=lambda p:(hiking.metres(p,site_by_id[ref['site_id']]),p['id']))
            assert winner['id']==stop['id']
    climb_ids={p['id'] for p in report['line_stops'] if p['in_isere'] and p.get('nearest_climbs')}
    for filename,expected in [('Isere_arrets_escalade.kmz',climb_ids),('Isere_arrets_rando_escalade.kmz',climb_ids|focused)]:
        with zipfile.ZipFile(out/filename) as z:
            assert z.testzip() is None
            tree=logical_tree(z.read('doc.kml'))
            assert {p.attrib['id'] for p in tree.findall('.//{'+K+'}Placemark')}==expected
    assert report['climbing_stop_count']==len(climb_ids)
    # Carte complète : un dossier bus et deux dossiers de lieux, sans doubler un accès été/hiver.
    for filename,with_stops in [('Isere_ecomobilite_activites.kmz',True),('Isere_points_activites.kmz',False)]:
        with zipfile.ZipFile(out/filename) as z:
            assert z.testzip() is None
            root=logical_tree(z.read('doc.kml'));ns={'k':K}
            stop_folder=root.find(".//k:Folder[@id='bus-stops']",ns)
            if with_stops:assert {p.attrib['id'] for p in stop_folder.findall('k:Placemark',ns)}==climb_ids|focused
            else:assert stop_folder is None
            actual={p.attrib['id']:p for p in root.findall(".//k:Folder[@id='places-access']/k:Placemark",ns)+root.findall(".//k:Folder[@id='places-climbing']/k:Placemark",ns)}
            assert set(actual)=={p['id'] for p in report['activity_places']}
            for record in report['activity_places']:
                coords=actual[record['id']].find('k:Point/k:coordinates',ns).text.split(',')
                assert (float(coords[0]),float(coords[1]))==(record['longitude'],record['latitude'])
                for label,path in record['links']:assert (out/path).is_file()
            ids=[e.attrib['id'] for e in root.iter() if 'id' in e.attrib]
            assert len(ids)==len(set(ids))
            for href in root.findall('.//k:Icon/k:href',ns):assert z.read(href.text).startswith(b'\x89PNG\r\n\x1a\n')
    assert report['combined_stop_count']==len(climb_ids|focused)
    assert report['focused_stop_count']==len(focused)
    import hiking
    access_by_id={h['id']:h for h in report['hikes']}
    winners={}
    for stop in report['line_stops']:
        for ref in stop.get('nearest_accesses',[]):
            key=(ref['access_id'],ref['route_id'])
            assert key not in winners
            assert stop['in_isere']
            assert any(r['id']==ref['route_id'] for r in stop['routes'])
            winners[key]=stop['id']
    for key,sid in winners.items():
        aid,rid=key
        candidates=[s for s in report['line_stops'] if s.get('in_isere') and any(r['id']==rid for r in s['routes']) and any(h['id']==aid for h in s['hikes'])]
        expected=min(candidates,key=lambda s:(hiking.metres(s,access_by_id[aid]),s['id']))
        assert expected['id']==sid

    import territory
    prepared=territory.polygons(json.loads((ROOT/'.cache/isere-limits.json').read_text()))
    for stop in report['line_stops']:assert stop['in_isere']==territory.contains(stop,prepared)
    import hiking
    hikes={h['id']:h for h in report['hikes']}
    for stop in report['stops']+report['line_stops']:
        for ref in stop.get('hikes',[]):
            h=hikes[ref['id']]
            assert hiking.metres(stop,h)<=1000
            assert h['season'] in ('ete','hiver')
            assert (out/'randos'/(h['id']+'.html')).is_file()
    assert (out/'randos/index.html').is_file()
    assert (out/'camptocamp.json').is_file()
    for h in hikes.values():
        assert h['id'].startswith('c2c-')
        assert h['license']['id']=='CC-BY-SA-3.0'
        assert h['routes']
        for route in h['routes']:
            assert route['url']=='https://www.camptocamp.org/routes/'+str(route['id'])+'/fr'
            assert route['license']['id']=='CC-BY-SA-3.0'
    for stop in report['stops']+report['line_stops']:
        if stop.get('hikes'):
            page=(out/'arrets'/(stop['id']+'.html')).read_text()
            for h in stop['hikes']:
                for route in h.get('routes',[]):assert route['url'] in page
    import pdipr_pilot
    snapshot=json.loads((ROOT/'data/pdipr-pilot.json').read_text())
    analyses=pdipr_pilot.analyse(report['line_stops'],snapshot)
    assert analyses==report['pdipr_pilot_results']
    for result in analyses:
        assert (out/'pdipr'/(result['id']+'.html')).is_file()
        for near in result['near']:assert near['distance_unrounded']<=1000
    with zipfile.ZipFile(out/'Essai_PDIPR_Vienne.kmz') as z:
        assert z.testzip() is None
        tree=logical_tree(z.read('doc.kml'))
        assert len(tree.findall(".//{K}Folder[@id='pilot-stops']/{K}Placemark".format(K='{'+K+'}')))==sum('longitude' in r for r in analyses)
        assert len(tree.findall(".//{K}Folder[@id='near-network']/{K}Placemark".format(K='{'+K+'}')))==sum(bool(r['near']) for r in analyses)
    print('Vérifié : 912 fiches, 165 + 747 points de référence et dossiers par ligne, positions et icônes vérifiées, liens officiels.')


if __name__=='__main__':verify()
