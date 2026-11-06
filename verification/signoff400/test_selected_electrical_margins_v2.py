import unittest
from report_selected_electrical_margins_v2 import margins, BEGIN, END


class ElectricalMarginsTest(unittest.TestCase):
    def report(self):
        return (BEGIN+'\nmax slew\n\nPin clock/CLK ^\nmax slew    0.240000000\n'
                'slew        0.160000000\n-----------------------\nSlack       0.080000000 (MET)\n\n'
                'max capacitance\n\nPin data/Y ^\nmax capacitance    0.067000000\n'
                'capacitance        0.040000000\n------------------------------\n'
                'Slack              0.027000000 (MET)\n\n'+END+'\n')

    def test_measured_pass_and_failure(self):
        self.assertEqual(margins(self.report())['slew']['slack'], .08)
        failed = self.report().replace('slew        0.160000000', 'slew        0.260000000').replace('0.080000000 (MET)', '-0.020000000 (VIOLATED)')
        self.assertFalse(margins(failed)['slew']['passed'])

    def test_native_single_precision_subtraction(self):
        report = self.report().replace('0.240000000', '0.239999995').replace('0.160000000', '0.131120056').replace('0.080000000', '0.108879946')
        self.assertTrue(margins(report)['slew']['passed'])

    def test_missing_partial_duplicate_and_inconsistent_reports_rejected(self):
        report = self.report()
        for damaged in ('', report.replace(END, ''), report.replace('max slew\n\n', ''),
                        report+report, report.replace('0.080000000', '0.090000000'),
                        report.replace('0.080000000 (MET)', '0.080000000 (VIOLATED)'),
                        report+'Error: failed command\n'):
            with self.subTest(damaged=damaged), self.assertRaises(ValueError): margins(damaged)


if __name__ == '__main__': unittest.main()
