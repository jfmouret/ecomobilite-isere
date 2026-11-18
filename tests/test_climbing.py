import unittest
import climbing


class ClimbingTests(unittest.TestCase):
    def stop(self,sid,lon,lines):
        return dict(id=sid,name=sid,latitude=45,longitude=lon,in_isere=True,routes=[dict(id=l,number=l,network='Test') for l in lines])

    def test_distance_filter_and_one_nearest_per_line(self):
        site=dict(id='oblyk-1',name='Falaise',latitude=45,longitude=6,source='https://oblyk.org/crags/1')
        a=self.stop('a',6.001,['A']);b=self.stop('b',6.003,['A','B']);far=self.stop('far',6.1,['A'])
        climbing.associate([a,b,far],[site])
        self.assertEqual([r['route_id'] for r in a['nearest_climbs']],['A'])
        self.assertEqual([r['route_id'] for r in b['nearest_climbs']],['B'])
        self.assertEqual(far['climbs'],[])
        self.assertEqual({r['id'] for r in site['nearest_stops']},{'a','b'})

    def test_ties_and_no_assumption_about_pdesi(self):
        site=dict(id='oblyk-1',name='Falaise',latitude=45,longitude=6,source='https://oblyk.org/crags/1',pdesi='Non confirmé')
        b=self.stop('b',6,['A']);a=self.stop('a',6,['A'])
        climbing.associate([b,a],[site])
        self.assertEqual(site['nearest_stops'][0]['id'],'a')
        self.assertEqual(site['pdesi'],'Non confirmé')
