import unittest
import build


class AccessTransportTests(unittest.TestCase):
    def test_only_selected_lines_are_shown_and_shared_stop_is_grouped(self):
        routes=[dict(id=n,number=n,name=n,network='Test',url='https://example.org/'+n) for n in ('A','B','C')]
        stops=[dict(id='near',name='Proche',status='exact',routes=routes),
               dict(id='far',name='Éloigné',status='exact',routes=routes)]
        refs=[dict(id='near',name='Proche',distance_m=100,route_id='A'),
              dict(id='near',name='Proche',distance_m=100,route_id='B'),
              dict(id='far',name='Éloigné',distance_m=300,route_id='C')]
        page=build.access_transport(refs,stops)
        self.assertEqual(page.count('<h3>Arrêt '),2)
        for n in ('A','B','C'):
            self.assertEqual(page.count('<h3>Ligne '+n+'</h3>'),1)
        self.assertLess(page.index('Arrêt Proche'),page.index('Arrêt Éloigné'))
        self.assertNotIn('Desserte à vérifier',page)
