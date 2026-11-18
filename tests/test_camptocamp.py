import json
import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import hiking


class CamptocampTests(unittest.TestCase):
    def test_web_mercator_is_not_interpreted_as_latlon(self):
        lon,lat=6,45
        geom={'geom':json.dumps(dict(type='Point',coordinates=[6378137*math.radians(lon),6378137*math.log(math.tan(math.pi/4+math.radians(lat)/2))]))}
        x,y=hiking.lonlat(geom)
        self.assertAlmostEqual(x,lon,places=7);self.assertAlmostEqual(y,lat,places=7)
        with self.assertRaises(ValueError):hiking.lonlat({'geom':'{"type":"LineString","coordinates":[]} '})

    @patch('time.sleep')
    def test_only_access_coordinates_and_linked_activities_are_used(self,_):
        license=dict(id='CC-BY-SA-3.0',attribution_url='https://www.camptocamp.org/waypoints/history/1/fr')
        point=dict(document_id=1,waypoint_type='access',geometry={'geom':'{"type":"Point","coordinates":[0,0]}'},license=license,locales=[dict(lang='fr',title='Accès')])
        route=dict(document_id=2,activities=['hiking','snowshoeing'],license=license,locales=[dict(lang='fr',title='Itinéraire')],geometry={'geom':'{"type":"Point","coordinates":[999999,999999]}'})
        detail=point|{'associations':{'all_routes':dict(total=2,documents=[route,route|dict(document_id=3,activities=['rock_climbing'])])}}
        calls=[]
        def download(url):
            calls.append(url)
            return json.dumps(detail if url.endswith('/waypoints/1') else dict(total=1,documents=[point])).encode()
        stop=dict(id='test',name='Arrêt',group='cars',latitude=0,longitude=0)
        with tempfile.TemporaryDirectory() as t:
            hikes=hiking.c2c_accesses([stop],Path(t),download)
        self.assertEqual({h['season'] for h in hikes},{'ete','hiver'})
        self.assertTrue(all(h['latitude']==0 and h['longitude']==0 for h in hikes))
        self.assertTrue(all([r['id'] for r in h['routes']]==[2] for h in hikes))
        hiking.associate([stop],hikes)
        self.assertEqual(len(stop['hikes']),2)
        self.assertTrue(all(h['distance_m']==0 for h in stop['hikes']))
        self.assertEqual(len(calls),2)
