import unittest,tempfile
from pathlib import Path
from compare_keeper_reduced_replay import compatible,native_wall_seconds
class ReducedReplayComparison(unittest.TestCase):
    def fixture(self):
        a=dict(normal_native_replay_complete=True,all_saved_replay_values_finite=True,PLLOUT_forced=False,sampled_boundary_replay_only=True,native_executable_sha256='binary',max_step_ps=50,shared_knot_carrier_used=True,source_representation='shared',literal_samples_preserved=True)
        b=dict(a,symbolic_boundary_reduction_used=True,literal_aggregated_samples_preserved=True,roundoff_audited_at_source_samples=True);b.pop('literal_samples_preserved');return a,b
    def test_same_completed_conditions_accepted(self):self.assertTrue(compatible(*self.fixture()))
    def test_incomplete_or_changed_conditions_rejected(self):
        for field,value in [('normal_native_replay_complete',False),('PLLOUT_forced',True),('native_executable_sha256','other'),('max_step_ps',10),('roundoff_audited_at_source_samples',False)]:
            a,b=self.fixture();b[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):compatible(a,b)
    def test_native_wall_measurement_excludes_controller_queue_time(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'memory.log'
            for duration,expected in [('1:02.50',62.5),('2:03:04.25',7384.25)]:
                p.write_text('Elapsed (wall clock) time (h:mm:ss or m:ss): '+duration+'\n')
                self.assertEqual(native_wall_seconds(p),expected)
            p.write_text('')
            with self.assertRaises(ValueError):native_wall_seconds(p)
if __name__=='__main__':unittest.main()
