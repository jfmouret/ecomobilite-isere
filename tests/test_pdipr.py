import math
import unittest
import pdipr_pilot


class PdiprTests(unittest.TestCase):
    def stop(self):return dict(id='a',name='Arrêt',latitude=45,longitude=6)
    def line(self,lat):return dict(properties=dict(id='1'),geometry=dict(type='LineString',coordinates=[[5.98,lat],[6.02,lat]]))

    def test_projection_checks_segment_not_centroid_or_endpoints(self):
        distance,p=pdipr_pilot.closest(self.stop(),self.line(45.001))
        self.assertAlmostEqual(p['longitude'],6)
        self.assertTrue(110<distance<112)
        self.assertAlmostEqual(p['latitude'],45.001)

    def test_threshold_before_rounding_and_missing_stop(self):
        s=self.stop()
        inside=self.line(45+math.degrees(999.8/6371008.8));outside=self.line(45+math.degrees(1000.2/6371008.8));outside['properties']['id']='2'
        snap=dict(pilots=[s],features=[inside,outside])
        result=pdipr_pilot.analyse([s],snap)[0]
        self.assertEqual([p['feature_id'] for p in result['near']],['1'])
        self.assertEqual(pdipr_pilot.analyse([],snap)[0]['near'],[])
        moved=s|dict(latitude=46)
        self.assertIn('position modifiée',pdipr_pilot.analyse([moved],snap)[0]['status'])
