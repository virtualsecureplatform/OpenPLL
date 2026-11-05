#!/usr/bin/env python3
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pvt_release_gate import check_pvt_grid, has_xyce_temperature
from dco_calibration import measure


def write_waveform(path, frequency_mhz):
    period_ns = 1000 / frequency_mhz
    rows = []
    for cycle in range(110):
        t = cycle * period_ns
        rows.extend(((t, 0), (t + .02, 1.62),
                     (t + period_ns / 2, 1.62),
                     (t + period_ns / 2 + .02, 0)))
    path.write_text(''.join(
        f'{index} {time_ns * 1e-9:.17g} {voltage}\n'
        for index, (time_ns, voltage) in enumerate(rows)))


class PVTReleaseGateTest(unittest.TestCase):
    def test_rejects_ignored_or_wrong_temperature_syntax(self):
        self.assertTrue(has_xyce_temperature('.options device temp=-40\n', -40))
        self.assertTrue(has_xyce_temperature('.OPTIONS DEVICE GMIN=1e-18 TEMP=125\n', 125))
        for deck in ('.temp 125\n', '.options device temp=27\n', '',
                     '.options device temp=125\n.options device temp=125\n'):
            self.assertFalse(has_xyce_temperature(deck, 125))
    def test_requires_every_corner_and_current_extraction(self):
        spec = {"modes_mhz": [500], "corners": ["tt", "ss"],
                "voltages": [1.62], "temperatures_c": [125],
                "fine_code_min": 8, "fine_code_max": 12,
                "frequency_error_ppm": 1000,
                "calibration_error_ppm": 100,
                "calibration_error_local_lsb": 0.25}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rcx = root / "dco.rcx.spice"
            rcx.write_text("original extraction\n")
            digest = hashlib.sha256(rcx.read_bytes()).hexdigest()
            report = {
                "stage": "qualify", "mode_mhz": 500, "corner": "tt",
                "vdd": 1.62, "temperature_c": 125, "simulator": "Xyce",
                "subckt_name": "DCO", "evidence": "deterministic_frequency_only",
                "errors": [], "convergence_passed": True,
                "coverage_passed": True, "interpolation_validated": True,
                "target_frequency_passed": True,
                "target_monotonic_passed": True, "target_code": 8,
                "target_frequency_mhz": 500.0,
                "coarse": 0, "samples": {"0": {
                    variant: {str(code): {"mhz": 500 + (code - 8) * .1,
                                          "half_window_difference_mhz": 0}
                              for code in (8, 9, 11, 12)}
                    for variant in ("baseline", "tolerance", "step", "settling")}},
                "provenance": {variant: {
                    "files": {str(rcx): digest},
                    "parameters": {"corner": "tt", "vdd": 1.62,
                                   "temperature_c": 125, "subckt_name": "DCO"}}
                    for variant in ("baseline", "tolerance", "step", "settling",
                                    "interpolation")},
            }
            report["samples"]["0"]["interpolation"] = {
                "10": {"mhz": 500.2, "half_window_difference_mhz": 0}}
            for corner in ("tt", "ss"):
                point = root / "mode_500" / f"{corner}_1.62V_125C"
                point.mkdir(parents=True)
                report["corner"] = corner
                for variant, record in report["provenance"].items():
                    record["parameters"]["corner"] = corner
                    record["parameters"]["meas_start_ns"] = 100
                    record["parameters"]["sim_time_ns"] = 200
                    record["fingerprint"] = hashlib.sha256(json.dumps(
                        {"files": record["files"],
                         "parameters": record["parameters"]},
                        sort_keys=True, allow_nan=False).encode()).hexdigest()
                    run = point / variant
                    run.mkdir()
                    (run / "provenance.json").write_text(json.dumps(record))
                    for text_code in report["samples"]["0"][variant]:
                        code = int(text_code)
                        base = run / f"dco_postlayout_{corner}_coarse_00_code_{code:03d}"
                        write_waveform(base.with_suffix(".prn"),
                                       500 + (code - 8) * .1)
                        deck = '.options device temp=125\n.end\n'
                        base.with_suffix('.spice').write_text(deck)
                        base.with_suffix(".provenance.json").write_text(
                            json.dumps({**record, "completed": True,
                                        "netlist_sha256": hashlib.sha256(deck.encode()).hexdigest()}))
                        report["samples"]["0"][variant][text_code] = measure(
                            base.with_suffix(".prn"), 100, 200, 1.62)
                report["target_frequency_mhz"] = (
                    report["samples"]["0"]["settling"]["8"]["mhz"])
                (point / "calibration.json").write_text(json.dumps(report))
            result = check_pvt_grid(root, spec, rcx, "DCO")
            self.assertEqual((result["expected"], result["qualified"]), (2, 2))
            self.assertTrue(result["passed"])
            base = (root / 'mode_500' / 'tt_1.62V_125C' / 'baseline'
                    / 'dco_postlayout_tt_coarse_00_code_008')
            correct_deck = base.with_suffix('.spice').read_text()
            sidecar_path = base.with_suffix('.provenance.json')
            correct_sidecar = sidecar_path.read_text()
            base.with_suffix('.spice').write_text('.temp 125\n.end\n')
            legacy = json.loads(correct_sidecar)
            legacy['netlist_sha256'] = hashlib.sha256(base.with_suffix('.spice').read_bytes()).hexdigest()
            sidecar_path.write_text(json.dumps(legacy))
            self.assertFalse(check_pvt_grid(root, spec, rcx, 'DCO')['passed'])
            base.with_suffix('.spice').write_text(correct_deck)
            sidecar_path.write_text(correct_sidecar)
            target_report = root / "mode_500" / "tt_1.62V_125C" / "calibration.json"
            altered = json.loads(target_report.read_text())
            altered["samples"]["0"]["interpolation"]["10"]["mhz"] = 499.8
            target_report.write_text(json.dumps(altered))
            self.assertFalse(check_pvt_grid(root, spec, rcx, "DCO")["passed"])
            altered["samples"]["0"]["interpolation"]["10"]["mhz"] = 500.2
            target_report.write_text(json.dumps(altered))
            waveform = (root / "mode_500" / "tt_1.62V_125C" / "interpolation"
                        / "dco_postlayout_tt_coarse_00_code_010.prn")
            original_waveform = waveform.read_text()
            waveform.write_text("broken waveform\n")
            self.assertFalse(check_pvt_grid(root, spec, rcx, "DCO")["passed"])
            waveform.write_text(original_waveform)
            rcx.write_text("changed extraction\n")
            self.assertFalse(check_pvt_grid(root, spec, rcx, "DCO")["passed"])
            (root / "mode_500" / "ss_1.62V_125C" / "calibration.json").unlink()
            result = check_pvt_grid(root, spec, rcx, "DCO")
            self.assertEqual(result["present"], 1)
            self.assertEqual(result["issue_count"], 2)


if __name__ == "__main__":
    unittest.main()
