import unittest
from compare_parallel_geometry_v2 import feedback_records, spef_without_date, density_without_run_metadata


class GeometryComparison(unittest.TestCase):
    def test_only_spef_date_is_ignored(self):
        source='*DATE "a"\n*C_UNIT 1 PF\n1 *1:2 *2:3 0.123456789\n'
        self.assertEqual(spef_without_date(source),spef_without_date(source.replace('"a"','"b"')))
        self.assertNotEqual(spef_without_date(source),spef_without_date(source.replace('0.123456789','0.123456788')))
        self.assertNotEqual(spef_without_date(source),spef_without_date(source.replace('1 PF','1 FF')))

    def test_feedback_order_can_change_but_duplicates_and_coordinates_cannot(self):
        a='box 1 2 3 4\nfeedback add "Antenna error at plane metal3\n" pale\n'
        b='box 5 6 7 8\nfeedback add "Antenna error at plane metal4\n" pale\n'
        self.assertEqual(feedback_records(a+b),feedback_records(b+a))
        self.assertNotEqual(feedback_records(a+a),feedback_records(a))
        self.assertNotEqual(feedback_records(a),feedback_records(a.replace('1 2 3 4','1 2 3 5')))
        for malformed in ('garbage',a+'unparsed data\n',a.replace('1 2 3 4','1 2 3')):
            with self.assertRaises(ValueError):feedback_records(malformed)

    def test_density_normalization_preserves_measurements(self):
        text='Started reading GDS: 10/28/2026 12:11:35\nStarting density checks: 10/28/2026 12:11:36\nMET1: 0.123\nEnded: 10/28/2026 12:11:49\n'
        other=text.replace('12:11:', '12:12:')
        self.assertEqual(density_without_run_metadata(text,'/out'),density_without_run_metadata(other,'/out'))
        self.assertNotEqual(density_without_run_metadata(text,'/out'),density_without_run_metadata(text.replace('0.123','0.124'),'/out'))
        with self.assertRaises(ValueError):density_without_run_metadata(text+'Ended: 10/28/2026 12:11:49\n','/out')


if __name__=='__main__':unittest.main()
