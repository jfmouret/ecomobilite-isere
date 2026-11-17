import datetime as dt
import io
import unittest
import zipfile
import build


class MatchingTests(unittest.TestCase):
    def point(self, **changes):
        p=dict(name='Col, École', latitude=45.0, longitude=6.0, feed='SEM', source_id='p', root_id='p', is_station=True)
        return p | changes

    def test_name_and_position_are_both_required(self):
        seed=self.point()
        self.assertEqual(build.match_stop(seed,[self.point(name='Autre arrêt')])[1],'non_retrouve')
        self.assertEqual(build.match_stop(seed,[self.point(latitude=45.01)])[1],'non_retrouve')
        self.assertEqual(build.match_stop(seed,[self.point(name='COL ECOLE',latitude=45.0001)])[1],'nom_et_proximite')

    def test_ambiguous_platforms_are_rejected(self):
        a=self.point(source_id='a',is_station=False,root_id='parent')
        b=self.point(source_id='b',is_station=False,root_id='parent')
        self.assertEqual(build.match_stop(a,[a,b]),([],'ambigu'))

    def test_parent_aggregates_children_but_separate_networks_survive(self):
        parent=self.point()
        child=self.point(source_id='child',is_station=False)
        other=self.point(feed='GSV')
        matches,status=build.match_stop(parent,[parent,child,other])
        self.assertEqual({(p['feed'],p['source_id']) for p in matches},{('SEM','p'),('GSV','p')})
        self.assertEqual(status,'exact')


class FeedTests(unittest.TestCase):
    def feed(self, missing_trip=False):
        tables={
            'stops.txt':'stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\np,Col,45,6,1,\na,Col quai A,45.0001,6,0,p\nb,Col quai B,45.0002,6,0,p\n',
            'routes.txt':'route_id,route_short_name,route_long_name\n1,59,Col - Ville\n2,60,Ville - Montagne\n',
            'trips.txt':'route_id,trip_id,service_id\n1,t1,s\n2,t2,s\n',
            'stop_times.txt':'trip_id,stop_id,stop_sequence\n'+('unknown' if missing_trip else 't1')+',a,1\nt2,b,1\n',
            'calendar_dates.txt':'service_id,date,exception_type\ns,20261118,1\n',
        }
        f=io.BytesIO()
        with zipfile.ZipFile(f,'w') as z:
            for name,data in tables.items():z.writestr(name,data)
        return f.getvalue()

    def test_parent_all_routes_platform_only_own_routes(self):
        f=build.read_feed('SEM',self.feed(),{'SEM:1':dict(id='SEM:59',timeSheet=True),'SEM:2':dict(id='SEM:60',timeSheet=True)},{'SEM:59':'https://www.reso-m.fr/8-horaires.htm?code=SEM%3A59'})
        points={p['source_id']:p for p in f['points']}
        self.assertEqual({r['number'] for r in points['p']['routes']},{'59','60'})
        self.assertEqual([r['number'] for r in points['a']['routes']],['59'])
        self.assertEqual([r['number'] for r in points['b']['routes']],['60'])
        self.assertIn('code=SEM%3A60',points['b']['routes'][0]['url'])
        self.assertEqual(f['period_start'],'20261118')

    def test_broken_trip_aborts_publication(self):
        with self.assertRaisesRegex(ValueError,'Référence GTFS'):
            build.read_feed('SEM',self.feed(True),{}, {})

    def test_unknown_m_link_is_not_invented(self):
        f=build.read_feed('SEM',self.feed(),{}, {})
        self.assertTrue(all(not r['url'] for p in f['points'] for r in p['routes']))

    def test_official_link_parser_rejects_other_domains(self):
        parser=build.OfficialLinks()
        parser.feed('<a href="/8-horaires.htm?code=SEM%3A59">Horaire</a><a href="https://example.com/8-horaires.htm?code=SEM%3A60">Faux</a>')
        self.assertEqual(set(parser.links),{'SEM:59'})

    def test_unmatched_and_expired_are_explicit_and_names_escaped(self):
        now=dt.datetime(2026,11,18,tzinfo=dt.timezone.utc)
        s=dict(name='<script>STOP</script>',group='mreso',altitude=600,status='non_retrouve',matches=[],routes=[])
        page=build.stop_page(s,{},now)
        self.assertIn('Correspondance à vérifier',page)
        self.assertNotIn('<script>STOP',page)
        s.update(status='exact',matches=[dict(feed='SEM',source_id='p',distance_m=0)])
        page=build.stop_page(s,{'SEM':dict(period_start='20250101',period_end='20250102')},now)
        self.assertIn('Offre publiée expirée',page)


if __name__=='__main__':unittest.main()
