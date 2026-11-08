import unittest
from measure_keeper_reset_endpoint_coverage import slacks, section


class EndpointReportGuards(unittest.TestCase):
    def test_positive_negative_and_explicit_no_path(self):
        self.assertEqual(slacks('0.125 slack (MET)\n-0.01 slack (VIOLATED)'), [.125, -.01])
        self.assertEqual(slacks('No paths found.'), [])

    def test_inconsistent_status_is_rejected(self):
        for text in ('-0.125 slack (MET)', '0.01 slack (VIOLATED)'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                slacks(text)

    def test_truncated_or_duplicate_query_is_rejected(self):
        self.assertEqual(section('A_BEGIN\nNo paths found.\nA_END', 'A').strip(), 'No paths found.')
        for text in ('A_BEGIN', 'A_END', 'A_BEGIN A_BEGIN A_END', 'A_BEGIN A_END A_END'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                section(text, 'A')


if __name__ == '__main__':
    unittest.main()
