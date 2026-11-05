import unittest
from audit_selected_clock_source_variant import normalize_deck


class ClockSourceVariantAuditTest(unittest.TestCase):
    def test_observation_paths_and_RAW_precision_do_not_change_solver_identity(self):
        a='.include "/a/devices.spice"\n.include "/a/sources.spice"\n.options timeint reltol=1e-5 abstol=1e-9\n.print tran format=raw file=/a/probe.raw v(q)'
        b=a.replace('/a/','/b/').replace('format=raw file=','format=raw precision=17 file=')
        self.assertEqual(normalize_deck(a),normalize_deck(b))
        self.assertNotEqual(normalize_deck(a),normalize_deck(b.replace('reltol=1e-5','reltol=1e-4')))
        self.assertNotEqual(normalize_deck(a),normalize_deck(b.replace('v(q)','v(other)')))

    def test_unknown_included_model_cannot_hide_behind_path_normalization(self):
        with self.assertRaisesRegex(ValueError,'unexpected include'):normalize_deck('.include "/elsewhere/other_model.spice"')


if __name__=='__main__':unittest.main()
