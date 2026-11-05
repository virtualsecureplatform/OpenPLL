import unittest
from write_prototype_native_liberty import observed_table, table


class NativeLibertyTests(unittest.TestCase):
    def surface(self,metric):
        return dict(metric=metric,observed_lower_extension_ns=.003,observed_upper_extension_ns=.002,
            native_grid=dict(input_slew_20_to_80_ns=[.012,.12,1],external_load_pf=[0,.02,.08],
                             lower_ns=[[.005]*3 for _ in range(3)],upper_ns=[[.007]*3 for _ in range(3)]))

    def test_early_and_late_holdout_extensions_and_allowance_are_not_reversed(self):
        early=observed_table(self.surface('delay'),'early',.01)[2]
        late=observed_table(self.surface('delay'),'late',.01)[2]
        self.assertAlmostEqual(early[0][0],-.008)
        self.assertAlmostEqual(late[0][0],.019)
        self.assertTrue(all(a<=.005 and b>=.007 for ar,br in zip(early,late) for a,b in zip(ar,br)))

    def test_slew_floor_does_not_clip_signed_propagation_delays(self):
        self.assertEqual(observed_table(self.surface('slew'),'early',.01)[2][0][0],0)
        self.assertLess(observed_table(self.surface('delay'),'early',.01)[2][0][0],0)

    def test_incomplete_table_dimensions_rejected(self):
        with self.assertRaisesRegex(ValueError,'dimensions differ'):
            table('cell_rise','propagation',[.012,.12,1],[0,.02,.08],[[1,2,3]])


if __name__=='__main__':unittest.main()
