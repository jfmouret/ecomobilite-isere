import unittest
import xml.etree.ElementTree as ET
import map_icons


class SeparateSymbolsTests(unittest.TestCase):
    def test_three_symbols_keep_coordinates_links_and_standard_images(self):
        k='{http://www.opengis.net/kml/2.2}'
        root=ET.Element(k+'kml');doc=ET.SubElement(root,k+'Document')
        style=ET.SubElement(doc,k+'Style',id='place-rando-raquettes-ski')
        ic=ET.SubElement(style,k+'IconStyle');ET.SubElement(ET.SubElement(ic,k+'Icon'),k+'href').text='old.png'
        p=ET.SubElement(doc,k+'Placemark',id='access');ET.SubElement(p,k+'name').text='Accès'
        ET.SubElement(p,k+'styleUrl').text='#place-rando-raquettes-ski'
        ET.SubElement(p,k+'description').text='<a href="https://example.org">Topo</a>'
        ET.SubElement(ET.SubElement(p,k+'Point'),k+'coordinates').text='6,45,0'
        assets={'old.png':b'old'};map_icons.separate_symbols(root,assets)
        marks=list(root.iter(k+'Placemark'));self.assertEqual(len(marks),3)
        self.assertEqual(len({p.attrib['id'] for p in marks}),3)
        for p in marks:
            self.assertEqual(p.find(k+'Point/'+k+'coordinates').text,'6,45,0')
            self.assertIn('https://example.org',p.find(k+'description').text)
        self.assertEqual({e.attrib['x'] for e in root.iter(k+'hotSpot')},{'1.5','0.5','-0.5'})
        self.assertNotIn('old.png',assets)
        for image in assets.values():
            self.assertEqual(int.from_bytes(image[16:20],'big'),48)
            self.assertEqual(int.from_bytes(image[20:24],'big'),48)
        map_icons.separate_symbols(root,assets)
        self.assertEqual(len(list(root.iter(k+'Placemark'))),3)
