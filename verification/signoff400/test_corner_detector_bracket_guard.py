"""Reject phase probes that cannot support a negative transition bracket."""
import unittest
from follow_selected_corner_detector_bracket import negative_bracket


class BracketGuard(unittest.TestCase):
    def bracket(self, pairs):
        return negative_bracket([dict(cycles=[dict(phase_ps=p, decision=d) for p,d in pairs])])

    def test_opposite_signs_alone_are_insufficient(self):
        self.assertIsNone(self.bracket([(-190,'dn'), (210,'up')]))
        self.assertIsNone(self.bracket([(-10,'dn'), (-190,'up')]))

    def test_same_decision_does_not_supply_bracket(self):
        self.assertIsNone(self.bracket([(-190,'dn'), (-10,'dn')]))
        self.assertIsNone(self.bracket([(-190,'up'), (-10,'up')]))

    def test_contradictory_cycles_reject_otherwise_valid_pair(self):
        self.assertIsNone(self.bracket([(-190,'dn'), (-10,'up'), (-5,'dn')]))

    def test_tightest_measured_ordered_negative_pair(self):
        self.assertEqual(self.bracket([(-500,'dn'),(-190,'dn'),(-10,'up'),(210,'up')]), [-190,-10])


if __name__ == '__main__':
    unittest.main()
