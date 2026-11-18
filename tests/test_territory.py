import unittest
import territory


class TerritoryTests(unittest.TestCase):
    def test_polygon_holes_and_border(self):
        f=dict(type='FeatureCollection',features=[dict(properties=dict(code='38001'),geometry=dict(type='Polygon',coordinates=[[[0,0],[4,0],[4,4],[0,4],[0,0]],[[1,1],[2,1],[2,2],[1,2],[1,1]]]))])
        p=territory.polygons(f)
        def inside(x,y):return territory.contains(dict(longitude=x,latitude=y),p)
        self.assertTrue(inside(3,3));self.assertTrue(inside(0,3));self.assertFalse(inside(1.5,1.5));self.assertFalse(inside(5,3))
        f['features'][0]['properties']['code']='69001'
        with self.assertRaises(ValueError):territory.polygons(f)
