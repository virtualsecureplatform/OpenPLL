import unittest
from write_prototype_load_envelope_liberty import rewrite

class LoadEnvelopeLiberty(unittest.TestCase):
    def test_only_input_load_changes_and_early_late_differ(self):
        text='library (test) {\n cell (inv) {\n pin (A) { direction : input; capacitance : 0.01; }\n pin (Y) { direction : output; function : "!A"; max_capacitance : 0.2; }\n }\n}\n'
        bounds={('inv','A'):dict(native_assumed_TT_capacitance_pf=.01,supplied_minimum_pf=.008,supplied_maximum_pf=.014)}
        early,_=rewrite(text,bounds,'early');late,_=rewrite(text,bounds,'late')
        self.assertEqual(early,text.replace('capacitance : 0.01;','capacitance : 0.008;'))
        self.assertEqual(late,text.replace('capacitance : 0.01;','capacitance : 0.014;'))
        with self.assertRaises(ValueError):rewrite(text,{},'early')

if __name__=='__main__':unittest.main()
