import unittest
from pathlib import Path
from build_prototype_DCO_broad_fine_candidate import revise


class BroadFineCandidateTests(unittest.TestCase):
    def test_forward_load_does_not_change_merge_logic(self):
        source = Path(__file__).resolve().parents[2]/'sky130/IntegerPLL_DCO_einvp_coarse_v5_turn10_boost8_osc8_load36_c1fine160_sky130.v'
        result = revise(source.read_text())
        self.assertIn('.Y(mirror_ret[1]), .A(mirror_turn_n[1]), .B(mirror_pass_n[1])', result)
        self.assertIn('\n                .A(mirror_fwd[1]),\n                .TE(DCO_THERM[(255*c1fine)/320]),', result)
        # The enlarged bank must retain every thermometer bit, including 254.
        controls = [(255*i)//320 for i in range(320)]
        self.assertEqual(set(controls), set(range(255)))

    def test_ambiguous_source_rejected(self):
        with self.assertRaises(ValueError):
            revise('')
