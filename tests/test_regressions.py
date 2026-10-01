import unittest
import json
import tempfile
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from project_validation import normalize_project,sync_diagram,resolve_image,audit_project,english_formula
from mixins.spreadsheet_interactions import shift_formula
from battery_dispatch import simulate_three_options,BatterySettings
from self_consumption import balance
from energy_economics import evaluate_options
from single_line_516 import build_model,write_svg

ROOT=Path(__file__).resolve().parents[1]

class Regressions(unittest.TestCase):
    def test_all_supplied_projects(self):
        for name,count in [('Usine_Frimo_462',462),('Usine_Frimo_517',517),('Usine_Frimo_562',562),('Volfrigo_516_autoconsumo',516)]:
            d=json.loads((ROOT/'pv_projects'/f'{name}.json').read_text())
            n=normalize_project(d)
            self.assertEqual(len(n['panels']),count)
            self.assertEqual(n['panel_pmax_w'],720)
            self.assertEqual(sorted(n['panels'].values()),list(range(1,count+1)))
            self.assertTrue(set(n['panel_blocks'])<=set(n['panels']))
            members=[x for coords in n['strings'].values() for x in coords]
            self.assertEqual(len(members),len(set(members)))
            self.assertEqual(set(members),set(n['panels']))
            for sid,a in n['string_mppt_assignment'].items():
                links=[l for l in n['diagram_links'] if l['a']=='str::'+sid]
                self.assertEqual([l['b'] for l in links],[f"mppt::{a['block']}::{a['mppt']}"])
                self.assertIn(str(len(n['strings'][sid])),n['diagram_nodes']['str::'+sid]['label'])
            self.assertEqual(normalize_project(n),n)

    def test_generated_links_ignore_stale_manual_wiring(self):
        d={'panels':{'0,0':8},'strings':{'String 1':['0,0']},'blocks':{'INV1':{'mppt_count':2}},
           'string_mppt_assignment':{'String 1':{'block':'INV1','mppt':1}},
           'diagram_nodes':{'custom::1':{'type':'custom','label':'Protection','x':33,'y':44}},
           'diagram_links':[{'a':'str::String 1','b':'mppt::INV1::2','auto':False}]}
        sync_diagram(d)
        self.assertEqual(d['diagram_nodes']['custom::1']['x'],33)
        self.assertFalse(any(l['a']=='str::String 1' and l['b'].endswith('::2') for l in d['diagram_links']))

    def test_orphans_numbering_and_coordinates(self):
        d={'panels':{'0,0':1,'1,0':8},'panel_blocks':{'0,0':'INV1','9,9':'INV1'},
           'strings':{'String 1':['0,0','1,0','9,9']},'continuous_panel_numbers':True}
        n=normalize_project(d)
        self.assertEqual(n['panels'],{'0,0':1,'1,0':8})
        self.assertEqual(n['strings']['String 1'],['0,0','1,0'])
        self.assertNotIn('9,9',n['panel_blocks'])

    def test_portable_image_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'Projet Importé_roof_scaled(1).png';p.write_bytes(b'image')
            self.assertEqual(resolve_image(Path(tmp)/'project.json','Projet Importé_roof_scaled.png'),str(p))

    def test_storage_before_export_curtailment_and_shared_power(self):
        p={'start_date':'2026-01-01','end_date':'2026-01-01','hourly_kwh':[0]+[150]*23,'imputed_indices':[]}
        result=simulate_three_options(p,[700]+[0]*23,BatterySettings(),300)
        self.assertEqual(result['without_bess']['annual']['curtailed_kwh'],400)
        for key in ['one_bess','two_bess']:
            row=result[key]['rows'][0]
            self.assertEqual(row[4],250)
            self.assertEqual(row[8],300)
            self.assertEqual(result[key]['annual']['curtailed_kwh'],150)
            for row in result[key]['rows']:
                self.assertAlmostEqual(row[1],row[6]+row[7])
                self.assertLessEqual(row[5],150)
        self.assertEqual(result['two_bess']['settings']['nominal_kwh'],2*result['one_bess']['settings']['nominal_kwh'])

    def test_export_zero_and_invalid(self):
        p={'start_date':'2026-01-01','end_date':'2026-01-01','hourly_kwh':[10]*24,'imputed_indices':[]}
        a=balance(p,[20]*24,0)['annual']
        self.assertEqual(a['export_kwh'],0);self.assertEqual(a['curtailed_kwh'],240)
        for v in [-1,float('nan')]:
            with self.assertRaises(ValueError):balance(p,[20]*24,v)

    def test_economics_net_cost_and_foregone_exports(self):
        d=json.loads((ROOT/'pv_projects/Volfrigo_516_autoconsumo.json').read_text())
        annuals=[d[k]['annual'] for k in ['self_consumption_summary','bess_summary','two_bess_summary']]
        for price in [.25,.32]:
            rows=evaluate_options(annuals,{'import_eur_kwh':price})
            for r in rows:
                self.assertAlmostEqual(r['total_benefit_eur'],annuals[0]['load_kwh']*price-r['net_energy_outlay_eur'])
            for i in [1,2,4,5]:
                self.assertAlmostEqual(rows[i]['incremental_benefit_eur'],rows[i]['avoided_purchases_eur']-rows[i-1]['avoided_purchases_eur']-rows[i]['foregone_export_eur'])

    def test_all_site_diagram_exports(self):
        with tempfile.TemporaryDirectory() as tmp:
            for path in (ROOT/'pv_projects').glob('*.json'):
                d=normalize_project(json.loads(path.read_text()))
                for count in [0,1,2]:
                    for language in ['en','fr']:
                        dest=Path(tmp)/f'{path.stem}-{count}-{language}.svg'
                        model=build_model(d,count);write_svg(model,dest,language)
                        self.assertEqual(model['modules'],len(d['panels']))
                        import xml.etree.ElementTree as ET
                        self.assertEqual(ET.parse(dest).getroot().tag,'{http://www.w3.org/2000/svg}svg')

    def test_missing_specs_are_not_validated(self):
        d=json.loads((ROOT/'pv_projects/Usine_Frimo_517.json').read_text())
        self.assertTrue(any('incomplete' in x for x in audit_project(d)))
        d['electrical_checks']={'inverter_max_pv_kw':''}
        self.assertEqual(build_model(d,0)['modules'],517)

    def test_saved_french_formulas_migrate_without_touching_plain_text(self):
        data={'material_spreadsheet':{'cells':{'A1':'=NB_MODULES+ZONE2_LARGEUR_MM+STRING1_NB_PANNEAUX',
                                               'B1':'SOMME is documentation'}},
              'material_categories':{'modules':{'rows':[{'Quantity':'=SOMME(A1:A4)+COURANT_A'}]}}}
        migrated=normalize_project(data)
        self.assertEqual(migrated['material_spreadsheet']['cells']['A1'],
                         '=PANEL_COUNT+ZONE2_WIDTH_MM+STRING1_PANEL_COUNT')
        self.assertEqual(migrated['material_spreadsheet']['cells']['B1'],'SOMME is documentation')
        self.assertEqual(migrated['material_categories']['modules']['rows'][0]['Quantity'],
                         '=SUM(A1:A4)+CURRENT_A')
        self.assertEqual(english_formula('=PANEL_COUNT+SUM(A1:A4)'), '=PANEL_COUNT+SUM(A1:A4)')

    def test_dragged_formula_moves_cell_references_only(self):
        self.assertEqual(shift_formula('=SUM(A1:B2)+PANEL_COUNT+ZONE1_WIDTH_MM',2,1),
                         '=SUM(B3:C4)+PANEL_COUNT+ZONE1_WIDTH_MM')

if __name__=='__main__':unittest.main()
