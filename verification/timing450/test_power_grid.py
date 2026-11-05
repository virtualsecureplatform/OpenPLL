from pathlib import Path
import tempfile
import unittest

from characterize_power_grid import clock_periods, numeric, resistance_models, summarize


LOG = '''Total 0.01 0.02 0.001 0.031 100.0%
[INFO PSM-0040] All shapes on net VDD are connected.
########## IR report #################
Net              : VDD
Worstcase IR drop: 1.0e-03 V
######################################
[INFO PSM-0040] All shapes on net VSS are connected.
########## IR report #################
Net              : VSS
Worstcase IR drop: 2.0e-03 V
######################################
'''


def fixture(directory):
    for net, voltage in [('VDD', 1.599), ('VSS', .002)]:
        (directory / f'{net}.em.csv').write_text('Current\n0.0002\n-0.0001\n')
        (directory / f'{net}.voltage.csv').write_text('Instance,Voltage\na,' + str(voltage) + '\n')


def magic_tables():
    text = '# Resistances are in milliohms per square\n'
    for label, resistance in [('(),(orig),(si)', 125), ('(hrhc),(hrlc)', 145), ('(lrhc),(lrlc)', 105)]:
        text += f'variants {label}\n'
        text += ''.join(f' resist (allm{n})/metal{n} {resistance}\n' for n in range(1, 6))
        text += ''.join(f' contact {name} 4500\n' for name in ('mcon', 'm2c', 'm3c', 'via3', 'via4'))
    return text


class PowerGridTest(unittest.TestCase):
    def test_complete_resolved_clocks(self):
        log = '\n'.join(f'POWER_CLOCK_PERIOD {name} {value}' for name, value in
                        [('REFCLK', 40), ('PLLOUT', 1000 / 450), ('FINECLK', 40),
                         ('EVENT_BBPD[0]', 40), ('EVENT_BBPD[1]', 40)])
        self.assertEqual(clock_periods(log, 450)['FINECLK'], 40)

    def test_rejects_unresolved_or_wrong_clocks(self):
        log = '\n'.join(f'POWER_CLOCK_PERIOD {name} {value}' for name, value in
                        [('REFCLK', 40), ('PLLOUT', 1000 / 450), ('FINECLK', 40),
                         ('EVENT_BBPD[0]', 40), ('EVENT_BBPD[1]', 40)])
        for text in (log.replace('FINECLK 40', 'FINECLK 0'),
                     log.replace('FINECLK 40', 'FINECLK 20'),
                     log.replace('FINECLK 40', 'FINECLK nan'),
                     log + '\nPOWER_CLOCK_PERIOD FINECLK 40',
                     log.replace('POWER_CLOCK_PERIOD FINECLK 40', '')):
            with self.assertRaises(RuntimeError):
                clock_periods(text, 450)

    def test_magic_units_and_mapping(self):
        models = resistance_models(magic_tables())
        self.assertEqual(models['nom']['sheet_ohms']['met1'], .125)
        self.assertEqual(models['max']['sheet_ohms']['met1'], .145)
        self.assertEqual(models['min']['via_ohms']['via2'], 4.5)

    def test_rejects_incomplete_or_ambiguous_resistance(self):
        for text in (magic_tables().replace(' contact via4 4500\n', ''),
                     magic_tables().replace('milliohms per square', 'unknown units'),
                     magic_tables() + magic_tables()):
            with self.assertRaises(RuntimeError):
                resistance_models(text)

    def test_finite_values(self):
        for value in ('nan', 'inf', '-inf'):
            with self.assertRaises(RuntimeError):
                numeric(value)

    def test_complete_grid(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            fixture(directory)
            result = summarize(LOG, directory, 1.6)
            self.assertAlmostEqual(result['minimum_effective_instance_supply_v'], 1.597)
            self.assertEqual(result['rails']['VDD']['maximum_segment_current_a'], .0002)

    def test_rejects_bad_native_log(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            fixture(directory)
            for text in (LOG + '\nzero resistance', LOG + '\nNaN', LOG + '\nSTA-1648',
                         LOG.replace('0.031', '0.04'), LOG.replace('Net              : VSS', 'Net : X'),
                         LOG.replace('All shapes on net VDD are connected.', 'grid failed')):
                with self.assertRaises(RuntimeError):
                    summarize(text, directory, 1.6)

    def test_rejects_empty_or_nonfinite_current(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            fixture(directory)
            for text in ('Current\n', 'Current\nnan\n'):
                (directory / 'VDD.em.csv').write_text(text)
                with self.assertRaises(RuntimeError):
                    summarize(LOG, directory, 1.6)

    def test_rejects_unmatched_duplicate_or_invalid_rail(self):
        with tempfile.TemporaryDirectory() as name:
            directory = Path(name)
            fixture(directory)
            for text in ('Instance,Voltage\nb,1.599\n', 'Instance,Voltage\na,1.599\na,1.599\n',
                         'Instance,Voltage\na,inf\n', 'Instance,Voltage\na,1.7\n',
                         'Instance,Voltage\na,0.001\n'):
                (directory / 'VDD.voltage.csv').write_text(text)
                with self.assertRaises(RuntimeError):
                    summarize(LOG, directory, 1.6)


if __name__ == '__main__':
    unittest.main()
