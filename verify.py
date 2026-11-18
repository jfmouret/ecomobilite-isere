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
    assert len(list((out/'arrets').glob('*.html')))==len(seeds)
    by_id={s['id']:s for s in report['stops']}
    for group,filename,count in [('mreso','Mreso_600m_en_ligne.kmz',165),('cars','Cars_Isere_600m_en_ligne.kmz',747)]:
        with zipfile.ZipFile(out/filename) as z:
            assert z.testzip() is None
            root=ET.fromstring(z.read('doc.kml'))
            ns={'k':K}
            doc=root.find('k:Document',ns)
            general=doc.find("k:Folder[@id='all-stops']",ns)
            lines=doc.find("k:Folder[@id='by-line']",ns)
            marks=general.findall('k:Placemark',ns)
            assert len(marks)==count
            icon=root.find('.//k:Icon/k:href',ns).text
            assert z.read(icon).startswith(b'\x89PNG\r\n\x1a\n')
            all_ids=[e.attrib['id'] for e in root.iter() if 'id' in e.attrib]
            assert len(all_ids)==len(set(all_ids))
            for href in root.findall('.//k:Icon/k:href',ns):
                assert z.read(href.text).startswith(b'\x89PNG\r\n\x1a\n')
            expected={}
            for seed in report['stops']:
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
                        assert u.hostname in ('www.reso-m.fr','sim.laregionvoustransporte.fr')
    print('Vérifié : 912 fiches, 165 + 747 points de référence et dossiers par ligne, positions et icônes vérifiées, liens officiels.')


if __name__=='__main__':verify()
