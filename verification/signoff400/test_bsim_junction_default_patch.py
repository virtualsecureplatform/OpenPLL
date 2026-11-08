import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tools/xyce_umfpack'))
from build_bsim_junction import correct_default

class JunctionDefaultPatch(unittest.TestCase):
    def test_only_omitted_drain_gate_potential_changes(self):
        a='preserved\n  if (!given("PBSWGD"))\n    DGatesidewallJctPotential = DsidewallJctPotential;\nexplicit values preserved\n'
        self.assertEqual(correct_default(a),a.replace('= DsidewallJctPotential;','= SGatesidewallJctPotential;'))
    def test_unexpected_or_already_corrected_source_rejected(self):
        for a in ['', '  if (!given("PBSWGD"))\n    DGatesidewallJctPotential = SGatesidewallJctPotential;']:
            with self.assertRaises(ValueError):correct_default(a)

if __name__=='__main__':unittest.main()
