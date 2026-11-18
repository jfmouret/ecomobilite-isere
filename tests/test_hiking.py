import math
import unittest
import hiking


class HikingTests(unittest.TestCase):
    def test_threshold_uses_unrounded_geodesic_distance(self):
        h=dict(id='a',name='Accès',latitude=45,longitude=6,season='hiver',activity='Raquettes',stops=[])
        stops=[]
        for name,metres in [('inside',999.8),('outside',1000.2)]:
            stops.append(dict(id=name,name=name,group='mreso',longitude=6,latitude=45+math.degrees(metres/6371008.8)))
        hiking.associate(stops,[h])
        self.assertEqual(len(stops[0]['hikes']),1)
        self.assertEqual(stops[1]['hikes'],[])
        self.assertEqual([s['id'] for s in h['stops']],['inside'])
