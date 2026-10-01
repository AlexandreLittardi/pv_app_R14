"""Ensure the exported physical connections follow the active project."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from detailed_electrical import build_detailed_model,default_design,source_fingerprint,write_detailed_svg

PROJECT=Path(__file__).resolve().parents[1]/'pv_projects'/'Volfrigo_516_autoconsumo.json'


class DetailedElectricalTests(unittest.TestCase):
    def setUp(self):
        self.project=json.loads(PROJECT.read_text(encoding='utf-8'))

    def test_project_mppt_two_poles_and_dc_battery_ports(self):
        design=default_design();design['bess_count']=1
        model=build_detailed_model(self.project,design)
        self.assertEqual(len(model['lines']),31)
        self.assertEqual(sum(line['count'] for line in model['lines']),516)
        self.assertEqual([b['id'] for b in model['inverters']],['INV1','INV2','INV3'])
        self.assertEqual(model['battery'][0]['links'],['INV1','INV2'])
        self.assertNotIn('INV3',model['battery'][0]['links'])
        # Legacy route lengths use Shadow heights and are intentionally invalidated in R10.
        self.assertTrue(all(line['route'] is None for line in model['lines']))
        for row in model['lines']:
            self.assertEqual(row['mppt'],self.project['string_mppt_assignment'][row['id']]['mppt'])
            self.assertTrue(row['voc_stc_v'] and row['vmp_stc_v'])
        self.assertTrue(any('missing' in issue for issue in model['issues']))

    def test_two_cabinets_do_not_invent_parallel_connection(self):
        design=default_design();design['bess_count']=2
        model=build_detailed_model(self.project,design)
        self.assertEqual(model['battery'][1]['links'],['',''])
        self.assertTrue(any('does not confirm' in warning for warning in model['issues']))
        design['battery']['2']['cluster_1_to']='INV1'
        self.assertTrue(any('multiple clusters' in warning for warning in
                            build_detailed_model(self.project,design)['issues']))

    def test_stale_design_ratings_and_valid_vector_export(self):
        design=default_design()
        design['source_fingerprint']=source_fingerprint(self.project)
        design['ac_voltage_v']='400';design['power_factor']='1'
        design['ac']['INV1']={'breaker_a':'160'}
        model=build_detailed_model(self.project,design)
        self.assertTrue(any('breaker rating 160 A' in warning for warning in model['issues']))
        with tempfile.TemporaryDirectory() as folder:
            path=write_detailed_svg(model,Path(folder)/'current.svg')
            root=ET.parse(path).getroot()
            self.assertEqual(root.tag,'{http://www.w3.org/2000/svg}svg')
            values=' '.join(node.text or '' for node in root.iter() if node.tag.endswith('}text'))
            self.assertIn('INV3',values)
            self.assertIn('300 kW',values)
            self.assertIn('String 31',values)
        altered=copy.deepcopy(self.project)
        altered['string_mppt_assignment']['String 1']['mppt']=2
        self.assertTrue(any('changed' in warning for warning in
                            build_detailed_model(altered,design)['issues']))


if __name__=='__main__':unittest.main()
