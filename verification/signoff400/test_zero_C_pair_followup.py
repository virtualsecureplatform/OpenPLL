import tempfile
from pathlib import Path
import unittest
from zero_C_pair_followup import trace_targets
from test_zero_C_followup import FollowupNamespaceControls


class PairTargetControls(unittest.TestCase):
    def test_actual_zero_positive_and_negative_diagonals_are_preserved(self):
        for integer in ('0','7','-3'):
            with self.subTest(integer=integer),tempfile.TemporaryDirectory() as folder:
                paths=FollowupNamespaceControls().fixture(Path(folder))
                result=trace_targets([(2,integer)],-166,*paths,4)
                self.assertEqual(result['negative_nodes'][0]['energy_integer'],integer)
                self.assertEqual(result['energy_binary_quantum_exponent'],-166)
                self.assertEqual([n['node'] for n in result['negative_nodes'][0]['original_voltage_nodes']],[2,3])

    def test_reference_duplicates_and_bad_namespace_rejected(self):
        for witnesses in ([],[(0,'0')],[(4,'7')],[(2,'0'),(2,'7')]):
            with self.subTest(witnesses=witnesses),tempfile.TemporaryDirectory() as folder:
                paths=FollowupNamespaceControls().fixture(Path(folder))
                with self.assertRaises(ValueError):trace_targets(witnesses,-166,*paths,4)


if __name__=='__main__':unittest.main()
