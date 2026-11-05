import unittest
from audit_selected_detector_cut import attachments

class DetectorCutTests(unittest.TestCase):
    def test_resistive_loads_include_directionless_clamp_and_repeated_terminals(self):
        r=attachments({'inside':['signal','VGND'], 'clamp':['remote','VGND','remote'],
                       'unrelated':['other','VGND']}, [('wire','signal','remote')],
                      [('coupling','remote','other','1f'),('rail','signal','VGND','2f')], {'inside'})
        self.assertEqual(set(r['external_primitive_terminals']),{'clamp'})
        self.assertEqual([x['terminal_index'] for x in r['external_primitive_terminals']['clamp']],[0,2])
        self.assertEqual([x['remote_is_fixed_rail'] for x in r['crossing_capacitors']],[False,True])
    def test_unknown_selected_primitive_is_rejected(self):
        with self.assertRaises(ValueError):attachments({},[],[],{'absent'})

if __name__=='__main__':unittest.main()
