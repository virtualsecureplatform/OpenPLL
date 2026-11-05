import tempfile
from pathlib import Path
import unittest
from common_v3 import sha
from compare_prototype_clock_train_resolution_v3 import budget_period


class ClockTrainBudgetPeriodTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.phase=Path(self.temp.name)/'assessment.json'
        self.constraints=self.phase.parent/'enabled_phase.sdc'
        self.constraints.write_text('create_clock -name PLLOUT -period 2.48694354638 [get_ports PLLOUT]\n')
        self.record=dict(input_sha256={str(self.constraints):sha(self.constraints)},source_clock_period_ns=2.48694354638)

    def test_actual_budget_period_is_separate_from_two_ns_native_train(self):
        path,period=budget_period(self.phase,self.record)
        self.assertEqual(path,self.constraints)
        self.assertAlmostEqual(period,2.48694354638)

    def test_stale_period_metadata_rejected(self):
        self.record['source_clock_period_ns']=2
        with self.assertRaises(ValueError):budget_period(self.phase,self.record)

    def test_changed_constraints_rejected(self):
        self.constraints.write_text('create_clock -name PLLOUT -period 2 [get_ports PLLOUT]\n')
        with self.assertRaises(ValueError):budget_period(self.phase,self.record)


if __name__=='__main__':unittest.main()
