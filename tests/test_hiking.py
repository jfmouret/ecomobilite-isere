import math
import unittest
import hiking


class HikingTests(unittest.TestCase):
    def record(self,activity):
        return dict(idtf='1',libelle='Test',activite={'libelle':activity},adresse={'latitude':'45','longitude':'6'})

    def test_season_comes_from_activity_not_altitude(self):
        self.assertEqual(hiking.departures([self.record('Randonnée pédestre')])[0]['season'],'ete')
        self.assertEqual(hiking.departures([self.record('Raquette')])[0]['season'],'hiver')
        self.assertEqual(hiking.departures([self.record('Ski de randonnée')])[0]['season'],'hiver')
        self.assertEqual(hiking.departures([self.record('Alpinisme')]),[])

    def test_threshold_uses_unrounded_geodesic_distance(self):
        h=hiking.departures([self.record('Raquette')])[0]
        stops=[]
        for name,metres in [('inside',999.8),('outside',1000.2)]:
            stops.append(dict(id=name,name=name,group='mreso',longitude=6,latitude=45+math.degrees(metres/6371008.8)))
        hiking.associate(stops,[h])
        self.assertEqual(len(stops[0]['hikes']),1)
        self.assertEqual(stops[1]['hikes'],[])
        self.assertEqual([s['id'] for s in h['stops']],['inside'])

    def test_bad_coordinates_are_skipped(self):
        r=self.record('Raquette');r['adresse']['latitude']=''
        self.assertEqual(hiking.departures([r]),[])
