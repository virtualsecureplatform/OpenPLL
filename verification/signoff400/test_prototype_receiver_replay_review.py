import unittest
from review_prototype_receiver_glitch_replay import table


class ReplayTableIntegrity(unittest.TestCase):
    def test_complete_trace_accepted(self):
        self.assertEqual(len(table('No. of Data Rows : 2\n0 0 0 0 0\n1 1.2e-8 0 0 0\n')),2)

    def test_nan_truncation_duplicate_time_and_missing_rows_rejected(self):
        for text in (
            'No. of Data Rows : 2\n0 0 0 0 0\n1 1.2e-8 0 0 nan\n',
            'No. of Data Rows : 2\n0 0 0 0 0\n1 1.1e-8 0 0 0\n',
            'No. of Data Rows : 2\n0 0 0 0 0\n1 0 0 0 0\n',
            'No. of Data Rows : 3\n0 0 0 0 0\n1 1.2e-8 0 0 0\n'):
            with self.assertRaises(ValueError):table(text)


if __name__=='__main__':unittest.main()
