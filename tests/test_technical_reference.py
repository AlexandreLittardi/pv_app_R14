"""Protect the revised solar-year and displayed technical formulas."""
import io
import unittest

from home_reference import FORMULAS
from mixins.shadow_energy import ShadowEnergyMixin


class TechnicalReferenceTests(unittest.TestCase):
    def test_dated_solar_position_uses_leap_year_when_requested(self):
        calculator=ShadowEnergyMixin()
        leap=calculator._compute_solar_position(43.55,10.31,1,9,12,2,year=2024)
        normal=calculator._compute_solar_position(43.55,10.31,1,9,12,2,year=2025)
        self.assertGreater(abs(leap[0]-normal[0]),0.001)

    def test_all_home_equations_render(self):
        from matplotlib.mathtext import math_to_image
        for section,_,equations in FORMULAS:
            for expression,_ in equations:
                with self.subTest(section=section,formula=expression):
                    image=io.BytesIO()
                    math_to_image('$'+expression+'$',image,format='png',dpi=80)
                    self.assertGreater(len(image.getvalue()),100)


if __name__=='__main__':unittest.main()
