from fractions import Fraction as F
from pathlib import Path
import tempfile
import unittest
from test_registered_sheet_charge import RegisteredSheetCharge
from compiled_sheet_charge_rational import build, payload, invoke, decode
from floating_sheet_charge import area, sheet, constant


class RationalRegisteredSheetCharge(RegisteredSheetCharge):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.binary = build(Path(cls.temp.name)/'build')

    def test_nonbinary_coordinates_and_shared_field_cancellation(self):
        points = [(F(1, 3), F(2, 5)), (F(4, 3), F(2, 5)),
                  (F(4, 3), F(7, 5)), (F(1, 3), F(7, 5))]
        template = dict(points=points, triangles=[[0, 1, 2], [0, 2, 3]])
        basis = payload(template, 'field:')
        box = [points[0][0], points[0][1], points[2][0], points[2][1]]
        rect = [[str(x.numerator), str(x.denominator)] for x in box]
        cases = [dict(id='reference', operator=['A', 1, 0, 1, rect, 1.0],
                      source_basis=basis, target_basis=dict(constant='REF')),
                 dict(id='same', operator=['A', 1, 1, 2, rect, 1.0],
                      source_basis=basis, target_basis=basis)]
        with tempfile.TemporaryDirectory() as temp:
            rows, _ = invoke(self.binary, cases, Path(temp)/'projection', threads=8)
            self.assertEqual(decode(rows[0], exact=True), area(sheet(template, 'field:'), constant('REF'), box))
            self.assertEqual(decode(rows[1], exact=True), {})


if __name__ == '__main__':
    unittest.main()
