#!/usr/bin/env python3
import tempfile
import unittest
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from spice_dco_postlayout import dco_netlist
from pvt_release_gate import has_xyce_temperature


class TemperatureDeckTest(unittest.TestCase):
    def test_translated_include_cannot_be_reused_at_another_operating_point(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root / 'sky130A/libs.tech/ngspice/sky130.lib.spice'
            model.parent.mkdir(parents=True)
            model.write_text('* model fixture\n')
            rcx = root / 'translated.spice'
            rcx.write_text('* translated fixture\n')
            rcx.with_suffix('.translation.json').write_text(json.dumps({
                'corner': 'tt', 'temperature_c': 27,
                'output_sha256': hashlib.sha256(rcx.read_bytes()).hexdigest()}))
            args = SimpleNamespace(pdk_root=root, pdk='sky130A', rcx_netlist=rcx,
                                   simulator='xyce', corner='ss', temperature_c=27)
            for corner, temperature, simulator in [('ss', 27, 'xyce'), ('tt', 125, 'xyce'),
                                                    ('tt', 27, 'ngspice')]:
                args.corner, args.temperature_c, args.simulator = corner, temperature, simulator
                with self.assertRaisesRegex(ValueError, 'translated diode netlist'):
                    dco_netlist(args, 8, 0, [])
            args.corner, args.temperature_c, args.simulator = 'tt', 27, 'xyce'
            rcx.write_text('* modified after translation\n')
            with self.assertRaisesRegex(ValueError, 'translated diode netlist'):
                dco_netlist(args, 8, 0, [])
            rcx.with_suffix('.translation.json').unlink()
            rcx.write_text('.subckt openpll_pw2nd_qualified_geometry N P\n.ends\n')
            with self.assertRaisesRegex(ValueError, 'missing corner and temperature provenance'):
                dco_netlist(args, 8, 0, [])

    def test_generated_temperature_controls_match_each_simulator(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            model = root / 'sky130A/libs.tech/ngspice/sky130.lib.spice'
            model.parent.mkdir(parents=True)
            model.write_text('* fake model library for deck generation\n')
            rcx = root / 'dco.spice'
            rcx.write_text('* fake extracted circuit\n')
            args = SimpleNamespace(pdk_root=root, pdk='sky130A', rcx_netlist=rcx,
                                   therm_invert=True, subckt_name='DCO', corner='ss',
                                   reset_release_ns=5, sim_time_ns=70, step_ps=20,
                                   meas_start_ns=12, ngspice_threads=1)
            for simulator in ('xyce', 'ngspice'):
                args.simulator = simulator
                for temperature in (-40, 27, 125):
                    args.temperature_c = temperature
                    deck = dco_netlist(args, 8, 0, ['RESET_N', 'PLLOUT'])
                    if simulator == 'xyce':
                        self.assertTrue(has_xyce_temperature(deck, temperature))
                    else:
                        self.assertIn(f'.temp {temperature}\n', deck)
                        self.assertNotIn('.options device temp=', deck)


if __name__ == '__main__':
    unittest.main()
