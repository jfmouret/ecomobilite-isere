import unittest
import focused_kmz
import hiking


class NearestTests(unittest.TestCase):
    def stop(self,sid,lon,routes):
        return dict(id=sid,name=sid,latitude=45,longitude=lon,in_isere=True,group='mreso',routes=[dict(id=r,number=r,network='Test') for r in routes])

    def access(self,aid,lon):
        return dict(id=aid,name=aid,latitude=45,longitude=lon,season='ete',activity='Pédestre',stops=[])

    def test_one_nearest_per_route_but_other_access_can_keep_second_stop(self):
        a=self.stop('a',6,['A']);b=self.stop('b',6.003,['A','B'])
        first=self.access('h1',6.0001)
        hiking.associate([a,b],[first])
        focused_kmz.select_nearest([a,b],[first])
        self.assertEqual({(r['access_id'],r['route_id']) for r in a['nearest_accesses']},{('h1','A')})
        self.assertEqual({(r['access_id'],r['route_id']) for r in b['nearest_accesses']},{('h1','B')})
        second=self.access('h2',6.0029)
        hiking.associate([a,b],[first,second]);focused_kmz.select_nearest([a,b],[first,second])
        self.assertIn(('h2','A'),{(r['access_id'],r['route_id']) for r in b['nearest_accesses']})

    def test_tie_is_stable_and_outside_department_not_selected(self):
        a=self.stop('a',6,['A']);b=self.stop('b',6,['A']);outside=self.stop('0',6,['A']);outside['in_isere']=False
        h=self.access('h',6)
        hiking.associate([b,a,outside],[h])
        self.assertEqual([s['id'] for s in focused_kmz.select_nearest([b,a,outside],[h])],['a'])

    def test_comparison_uses_unrounded_distance(self):
        a=self.stop('a',6.000002,['A']);z=self.stop('z',6.000001,['A']);h=self.access('h',6)
        hiking.associate([a,z],[h])
        self.assertEqual(a['hikes'][0]['distance_m'],z['hikes'][0]['distance_m'])
        self.assertEqual([s['id'] for s in focused_kmz.select_nearest([a,z],[h])],['z'])
