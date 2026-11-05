import copy
import json
from pathlib import Path
import tempfile
import unittest

from charge_R_domain_bridge import domain_bridge_pins


class DomainBridgeTests(unittest.TestCase):
    def test_corrected_domain_requires_reference_equivalence(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ref = root/'reference/domain/assessment.json'
            corrected = root/'corrected/domain/assessment.json'
            ref.parent.mkdir(parents=True)
            corrected.parent.mkdir(parents=True)
            ref.write_text(json.dumps({'input_sha256': {'reference.gds': 'gds'}}))
            native = {'input_sha256': {str(ref): 'reference', 'reference.gds': 'gds',
                                      'pdk/sky130A.tech': 'tech'}}
            report = {'input_sha256': {str(ref): 'reference', 'staged.gds': 'gds',
                                      'pdk/sky130A.tech': 'tech'}, 'artifacts': {},
                      'native_rc_export_completed': True,
                      'pre_resistance_capacitance_preserved': True}
            for suffix in ('pre_resistance.spice', 'Prototype400_FilledCapacitanceView.ext'):
                source = str(ref.parent/'trace'/suffix)
                native['input_sha256'][source] = suffix
                report['input_sha256'][source] = suffix
                report['artifacts'][str(corrected.parent/'trace'/suffix)] = 'corrected-'+suffix
            corrected.write_text(json.dumps(report))
            pins = domain_bridge_pins(native, corrected, 'corrected')
            self.assertEqual(pins[str(ref)], 'reference')
            self.assertEqual(pins[str(corrected)], 'corrected')
            self.assertIn('staged.gds', pins)
            mutations = [
                ('reference hash', lambda d: d['input_sha256'].update({str(ref): 'wrong'})),
                ('GDS hash', lambda d: d['input_sha256'].update({'staged.gds': 'wrong'})),
                ('technology', lambda d: d['input_sha256'].update({'pdk/sky130A.tech': 'wrong'})),
                ('card hash', lambda d: d['input_sha256'].update({str(ref.parent/'trace/pre_resistance.spice'): 'wrong'})),
                ('incomplete', lambda d: d.update(native_rc_export_completed=False)),
                ('no equivalence', lambda d: d.update(pre_resistance_capacitance_preserved=False)),
            ]
            for name, mutate in mutations:
                with self.subTest(name=name):
                    bad = copy.deepcopy(report)
                    mutate(bad)
                    corrected.write_text(json.dumps(bad))
                    with self.assertRaises(ValueError):
                        domain_bridge_pins(native, corrected, 'corrected')


if __name__ == '__main__':
    unittest.main()
