"""Contrôle du produit réellement généré, exécuté avant publication."""
import json
from pathlib import Path
import urllib.parse
import xml.etree.ElementTree as ET
import zipfile
from build import ROOT,K


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
            root=ET.fromstring(z.read('doc.kml'))
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
        tree=ET.fromstring(z.read('doc.kml'))
        assert {p.attrib['id'] for p in tree.findall('.//{'+K+'}Placemark')}==focused
        assert not tree.findall('.//{'+K+'}Folder')
    expected_lines={r['id'] for s in report['line_stops'] for r in s['routes']}
    assert len(list((out/'lignes').glob('*.kmz')))==len(expected_lines)
    for rid in expected_lines:
        expected_stops={s['id'] for s in report['line_stops'] if any(r['id']==rid for r in s['routes'])}
        with zipfile.ZipFile(out/'lignes'/focused_kmz.line_filename(rid)) as z:
            assert z.testzip() is None
            tree=ET.fromstring(z.read('doc.kml'))
            assert {p.attrib['id'] for p in tree.findall('.//{'+K+'}Placemark')}==expected_stops
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
    print('Vérifié : 912 fiches, 165 + 747 points de référence et dossiers par ligne, positions et icônes vérifiées, liens officiels.')


if __name__=='__main__':verify()
