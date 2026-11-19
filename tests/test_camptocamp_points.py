import tempfile
import unittest
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile
import activity_map
import map_icons


class CamptocampPointsTests(unittest.TestCase):
    def test_seasons_merge_without_losing_routes_or_coordinates(self):
        route=dict(id=1,name='Course',url='https://www.camptocamp.org/routes/1/fr',activities=['hiking'])
        common=dict(name='Accès',source='https://www.camptocamp.org/waypoints/2/fr',latitude=45,longitude=6,routes=[route])
        hikes=[dict(common,id='c2c-2-ete',season='ete'),dict(common,id='c2c-2-hiver',season='hiver'),dict(common,id='excluded',season='ete')]
        stops=[dict(nearest_accesses=[dict(access_id=h['id']) for h in hikes[:2]])]
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(activity_map.camptocamp_points(stops,hikes,Path(tmp),'https://example.org'),1)
            with zipfile.ZipFile(Path(tmp)/'Isere_acces_Camptocamp.kmz') as z:
                root=ET.fromstring(z.read('doc.kml'));ns={'k':activity_map.K}
                marks=root.findall('.//k:Placemark',ns);self.assertEqual(len(marks),1)
                self.assertEqual(marks[0].find('k:name',ns).text,'Accès')
                self.assertEqual(marks[0].find('k:styleUrl',ns).text,'#access-mixte')
                self.assertEqual(marks[0].find('k:Point/k:coordinates',ns).text,'6,45,0')
                desc=marks[0].find('k:description',ns).text
                for h in hikes[:2]:self.assertIn(h['id']+'.html',desc)
                self.assertIn(route['url'],desc)
                for link in root.findall('.//k:Icon/k:href',ns):self.assertIn(link.text,z.namelist())
        self.assertEqual([map_icons.activity_scale(map_icons.ORDER[:n]) for n in range(1,5)],[.65,1.3,1.9500000000000002,2.6])
