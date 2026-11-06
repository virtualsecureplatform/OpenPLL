"""Reject leakage and invalid waiting sets before touching native probe inputs."""
from pathlib import Path
import tempfile
import unittest
from follow_selected_corner_detector_bracket_v2 import run


class FollowupSetControls(unittest.TestCase):
    def rejected(self,waiting,fitting,holdouts):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError,'disjoint nonempty training/holdout sets'):
                run(list(map(Path,waiting)),list(map(Path,fitting)),list(map(Path,holdouts)),
                    'ss',Path(temp)/'observer')

    def test_holdout_cannot_also_be_training(self):
        self.rejected(['probe'],['probe'],['probe'])

    def test_waiting_probe_must_be_assigned(self):
        self.rejected(['unassigned'],['training'],['holdout'])

    def test_duplicate_waiting_probe_rejected(self):
        self.rejected(['training','training'],['training'],['holdout'])

    def test_independent_holdout_required(self):
        self.rejected(['training'],['training'],[])


if __name__ == '__main__':
    unittest.main()
