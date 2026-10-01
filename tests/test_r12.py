import unittest
from mixins.string_sizing import size_string, StringSizingMixin
from project_validation import english_formula

PARAMS={'resistivity':.017,'target_drop_pct':1.}
SPEC={'Imp (A)':12.,'Vmp (V)':40.}

class SizingTests(unittest.TestCase):
    def test_each_string_uses_actual_loop_and_own_module_count(self):
        a=size_string({'loop_length_m':100},10,SPEC,{},PARAMS,{'6':.08})
        b=size_string({'loop_length_m':100},20,SPEC,{},PARAMS,{'4':.05})
        self.assertEqual(a['working_section_mm2'],6)
        self.assertEqual(b['working_section_mm2'],4)
        self.assertAlmostEqual(a['mass_kg'],8)
        self.assertAlmostEqual(b['mass_kg'],5)
        self.assertLessEqual(a['drop_at_working_section_pct'],1)
        c=size_string({'loop_length_m':200},10,SPEC,{},PARAMS,{})
        self.assertGreater(c['working_section_mm2'],a['working_section_mm2'])

    def test_no_generic_fallback_for_missing_equipment(self):
        rec=size_string({'loop_length_m':100},10,{}, {},PARAMS,{'6':.08})
        self.assertIsNone(rec['working_section_mm2'])
        rec=size_string({'loop_length_m':100},10,{}, {'current_a':12,'voltage_v':400},PARAMS,{'6':.08})
        self.assertEqual(rec['working_section_mm2'],6)

    def test_invalid_mass_and_operating_values_are_unknown(self):
        for value in (None,0,-1,'NaN','invalid'):
            rec=size_string({'loop_length_m':100},10,SPEC,{},PARAMS,{'6':value})
            self.assertIsNone(rec['mass_kg'])
        for value in (0,-1,'NaN'):
            rec=size_string({'loop_length_m':100},10,SPEC,{'current_a':value},PARAMS,{})
            self.assertIsNone(rec['working_section_mm2'])

    def test_parameters_recalculate_without_mutating_saved_route(self):
        original={'loop_length_m':100,'working_section_mm2':999}
        rec=size_string(original,10,SPEC,{}, {'resistivity':.017,'target_drop_pct':.5},{})
        self.assertEqual(rec['working_section_mm2'],16)
        self.assertEqual(original['working_section_mm2'],999)

    def test_total_is_unknown_when_any_active_string_is_missing(self):
        class Mass(StringSizingMixin):
            strings={'A':[(0,0)],'B':[(1,0)],'Empty':[]}
            records={'A':{'mass_kg':4},'B':{'mass_kg':None}}
            def get_two_pole_route(self,sid):return self.records.get(sid)
        app=Mass()
        self.assertEqual(app._cable_mass_summary(),{'total_kg':None,'known_kg':4,'missing':1})
        app.records['B']={'mass_kg':6}
        self.assertEqual(app._cable_mass_summary()['total_kg'],10)
        app.records['A']=None
        self.assertIsNone(app._cable_mass_summary()['total_kg'])

    def test_global_weight_alias(self):
        self.assertEqual(english_formula('=POIDS_TOTAL_CABLAGES_KG*2'),'=TOTAL_CABLE_WEIGHT_KG*2')

class GlobalMassTests(unittest.TestCase):
    def test_weight_is_available_in_material_and_custom_formulas(self):
        from mixins.material_tools import MaterialToolsMixin
        class App(MaterialToolsMixin):
            material_categories={'modules':{'rows':[]}}
            total=15.
            def _cable_mass_summary(self):return {'total_kg':self.total,'missing':int(self.total is None)}
        app=App()
        variables=app._get_material_global_vars()
        self.assertEqual(variables['TOTAL_CABLE_WEIGHT_KG'],15.)
        self.assertEqual(variables['POIDS_TOTAL_CABLAGES_KG'],15.)
        app.total=None
        self.assertNotIn('TOTAL_CABLE_WEIGHT_KG',app._get_material_global_vars())
