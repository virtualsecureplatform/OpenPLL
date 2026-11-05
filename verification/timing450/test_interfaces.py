import unittest

from characterize_interfaces import PORTS, parse_loads


def report():
    return ''.join(f'''Net {port}
 Pin capacitance: 0.02
 Wire capacitance: 0.17
 Total capacitance: 0.19
 Number of drivers: 1

Driver pins
 {port} input port (446, 450)
''' for port in PORTS)


class InterfaceLoadsTest(unittest.TestCase):
    def test_complete_report(self):
        loads = parse_loads(report())
        self.assertEqual(set(loads), set(PORTS))
        self.assertEqual(loads['BBPD[0]']['total_pf'], .19)

    def test_rejects_missing_or_duplicate_port(self):
        for text in (report().split('Net PLLOUT')[0], report() + report()):
            with self.assertRaises(RuntimeError):
                parse_loads(text)

    def test_rejects_invalid_capacitance(self):
        for value in ('0', '-1', '1e999', '0.5'):
            with self.assertRaises(RuntimeError):
                parse_loads(report().replace('Total capacitance: 0.19',
                                            'Total capacitance: ' + value))

    def test_rejects_extraction_errors_and_wrong_driver(self):
        for text in (report() + '\nError: failed', report() + '\nSTA-1648',
                     report().replace('Number of drivers: 1', 'Number of drivers: 2'),
                     report().replace(' input port ', ' output port ')):
            with self.assertRaises(RuntimeError):
                parse_loads(text)


if __name__ == '__main__':
    unittest.main()
