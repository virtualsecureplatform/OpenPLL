#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Regression checks for modern release evidence freshness."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from check_sky130_modern_25mhz_release import require_current
from generate_modern_25mhz import render_mode_config, render_testbench
from pll_verification import load_spec
from sky130_modern_targets import TARGETS_MHZ, load_target_presets


class FreshnessTest(unittest.TestCase):
    def test_rejects_missing_and_older_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            output = root / "result"
            source.write_text("input", encoding="ascii")
            with self.assertRaisesRegex(ValueError, "missing result"):
                require_current(output, [source], "result")
            output.write_text("pass", encoding="ascii")
            os.utime(output, ns=(1_000_000_000, 1_000_000_000))
            os.utime(source, ns=(2_000_000_000, 2_000_000_000))
            with self.assertRaisesRegex(ValueError, "stale result"):
                require_current(output, [source], "result")
            os.utime(output, ns=(3_000_000_000, 3_000_000_000))
            require_current(output, [source], "result")


class ReleaseTargetTest(unittest.TestCase):
    def test_450_mhz_replaces_500_mhz(self) -> None:
        self.assertEqual(tuple(load_spec()["modes_mhz"]), TARGETS_MHZ)
        modes = {target: {"coarse_code": 1, "target_code": 121,
                          "ndiv": target // 25} for target in TARGETS_MHZ}
        rtl = render_mode_config(modes)
        self.assertIn("DIV_450MHZ = 5'd18;", rtl)
        self.assertIn("TARGET_MHZ = 16'd450;", rtl)
        self.assertNotIn("DIV_500MHZ", rtl)
        for name in ("mode_config", "mode_controller", "configured_wrapper",
                     "configured_behavioral"):
            bench = render_testbench(name, modes)
            self.assertIn("16'd450", bench)
            self.assertNotIn("16'd500", bench)

    def test_rejects_superseded_500_mhz_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "targets.json"
            manifest.write_text('{"targets": {"500": {}}}', encoding="ascii")
            with self.assertRaisesRegex(ValueError, "450"):
                load_target_presets(manifest, {})


if __name__ == "__main__":
    unittest.main()
