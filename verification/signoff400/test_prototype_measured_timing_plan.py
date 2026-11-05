import unittest
from extend_prototype_plan_measured_timing import data_path, next_strength


class MeasuredTimingPlanTests(unittest.TestCase):
    def path(self, pin='D', slack='-0.04'):
        return f'''launch
Endpoint: capture
Path Type: min
 .12 .4 ^ gate/Y (sky130_fd_sc_hs__nand2_1)
 .01 .41 ^ capture/{pin} (sky130_fd_sc_hs__dfrtp_1)
 .41 data arrival time
 {slack} slack (VIOLATED)
'''

    def test_data_endpoint_and_output_arc_retained(self):
        endpoint, kind, slack, rows = data_path(self.path())
        self.assertEqual((endpoint, kind, slack), ('capture', 'min', -.04))
        self.assertEqual(rows[0][1:3], ('gate', 'Y'))

    def test_reset_or_clock_paths_cannot_be_data_repairs(self):
        for pin in ('RESET_B', 'CLK'):
            with self.assertRaises(ValueError): data_path(self.path(pin))

    def test_positive_or_missing_slack_rejected(self):
        for block in (self.path(slack='.04'), self.path().replace('slack', 'missing')):
            with self.assertRaises(ValueError): data_path(block)

    def test_only_next_available_same_family_strength(self):
        available = {'lib__nor2_1', 'lib__nor2_4', 'lib__nor2_8', 'lib__nand2_2'}
        self.assertEqual(next_strength('lib__nor2_1', available), 'lib__nor2_4')
        self.assertIsNone(next_strength('lib__nor2_8', available))


if __name__ == '__main__': unittest.main()
