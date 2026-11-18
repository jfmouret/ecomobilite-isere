import unittest
import activity_map
import map_icons


class ActivityMapTests(unittest.TestCase):
    def test_hiking_and_climbing_labels_follow_selected_associations(self):
        s=dict(nearest_accesses=[dict(access_id='c2c-1-hiver')],nearest_climbs=[dict(site_id='oblyk-1')],hikes=[dict(id='c2c-1-hiver',season='hiver',routes=[dict(activities=['snowshoeing'])]),dict(id='not-selected',season='ete',routes=[])])
        activity_map.enrich([s],[])
        self.assertEqual(set(s['activity_types']),{'raquettes','escalade'})
        self.assertNotIn('ski',s['activity_types'])
        self.assertNotIn('rando',s['activity_types'])

    def test_same_access_in_summer_and_winter_is_one_marker(self):
        stop=dict(nearest_accesses=[dict(access_id='c2c-1-ete'),dict(access_id='c2c-1-hiver')])
        common=dict(source='https://www.camptocamp.org/waypoints/1/fr',name='Col',latitude=45,longitude=6,routes=[dict(activities=['hiking','skitouring'])])
        places=activity_map.destinations([stop],[common|dict(id='c2c-1-ete',season='ete'),common|dict(id='c2c-1-hiver',season='hiver')],[])
        self.assertEqual(len(places),1)
        self.assertEqual(set(places[0]['types']),{'rando','ski'})
        self.assertEqual(len(places[0]['links']),2)

    def test_pictograms_are_self_contained_and_stop_differs_from_place(self):
        self.assertTrue(map_icons.icon(['rando']).startswith(b'\x89PNG\r\n\x1a\n'))
        self.assertNotEqual(map_icons.icon(['rando']),map_icons.icon(['rando'],stop=True))
        self.assertNotEqual(map_icons.icon(['ski']),map_icons.icon(['escalade']))
