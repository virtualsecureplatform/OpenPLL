import unittest
from fractions import Fraction as F
from prototype_spef_v2 import parse

FIXTURE='''*SPEF "ieee 1481-1999"
*DESIGN "test"
*DESIGN_FLOW "PIN_CAP NONE"
*C_UNIT 1 PF
*R_UNIT 1 OHM
*NAME_MAP
*1 wire
*2 cell
*PORTS
input I
*D_NET *1 0.5
*CONN
*P input I
*I *2:A I
*CAP
1 input 0.25
2 *2:A 0.25
*RES
1 input *2:A 2.5
*END
'''


class SPEFControls(unittest.TestCase):
    def test_exact_units_names_and_ports(self):
        result=parse(FIXTURE);net=result['nets'][0]
        self.assertEqual(net['name'],'wire')
        self.assertEqual(net['connections'][1]['node'],'cell:A')
        self.assertEqual(F(net['capacitors'][0]['farads']),F(1,4*10**12))
        self.assertEqual(F(net['resistors'][0]['ohms']),F(5,2))
        self.assertTrue(result['pin_capacitance_excluded'])

    def test_negative_values_unresolved_names_truncation_and_duplicate_ids_rejected(self):
        for text in [FIXTURE.replace('2.5','-2.5'),FIXTURE.replace('*2:A','*99:A'),
                     FIXTURE.replace('*END',''),FIXTURE.replace('2 *2:A 0.25','1 *2:A 0.25'),
                     FIXTURE.replace('*R_UNIT 1 OHM','*R_UNIT 1 UNKNOWN')]:
            with self.subTest(text=text):
                with self.assertRaises(ValueError):parse(text)


if __name__=='__main__':unittest.main()
