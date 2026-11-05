#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Audit the diode-free multi-macro physical hierarchy (not PLL release)."""

import json
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PDK_VERSION = "1689ac3f2dc763876eaf967227c7dfe831b031ae"
DESIGNS = (
    (
        "IntegerPLL_BBPD",
        "librelane_signoff",
        ("sky130/IntegerPLL_BBPD_sky130.v",
         "openlane/IntegerPLL_BBPD/config.json",
         "openlane/IntegerPLL_BBPD/async_false_paths.sdc"),
        (),
        False,
    ),
    (
        "IntegerPLL_DigitalCore",
        "librelane_signoff_force127_s4a2",
        ("rtl/IntegerPLL_B2TH.v", "rtl/IntegerPLL_MMD_Retimer.v",
         "rtl/IntegerPLL_Divider.v", "rtl/IntegerPLL_DLF.v",
         "rtl/IntegerPLL_DigitalCore.v",
         "openlane/IntegerPLL_DigitalCore/config.json",
         "openlane/IntegerPLL_DigitalCore/pnr.sdc"),
        (),
        False,
    ),
    (
        "IntegerPLL_DCO_EINVP_COARSE_V5_TURN10",
        "pvt_probe_turn10",
        ("sky130/IntegerPLL_DCO_einvp_coarse_v5_turn10_sky130.v",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10/config.json",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10/pin_order.cfg",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10/no_clock.sdc"),
        (),
        True,
    ),
    (
        "IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8",
        "pvt_probe_turn10_boost8",
        ("sky130/IntegerPLL_DCO_einvp_coarse_v5_turn10_boost8_sky130.v",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8/config.json",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8/pin_order.cfg",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8/no_clock.sdc"),
        (),
        True,
    ),
    (
        "IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8",
        "pvt_probe_turn10_boost8_osc8",
        ("sky130/IntegerPLL_DCO_einvp_coarse_v5_turn10_boost8_osc8_sky130.v",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8/config.json",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8/pin_order.cfg",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8/no_clock.sdc"),
        (),
        True,
    ),
    (
        "IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_LOAD24",
        "pvt_probe_turn10_boost8_load24",
        ("sky130/IntegerPLL_DCO_einvp_coarse_v5_turn10_boost8_load24_sky130.v",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_LOAD24/config.json",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_LOAD24/pin_order.cfg",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_LOAD24/no_clock.sdc"),
        (),
        True,
    ),
    (
        "IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_LOAD18",
        "pvt_probe_turn10_boost8_load18",
        ("sky130/IntegerPLL_DCO_einvp_coarse_v5_turn10_boost8_load18_sky130.v",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_LOAD18/config.json",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_LOAD18/pin_order.cfg",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_LOAD18/no_clock.sdc"),
        (),
        True,
    ),
    (
        "IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD24",
        "pvt_probe_turn10_boost8_osc8_load24",
        ("sky130/IntegerPLL_DCO_einvp_coarse_v5_turn10_boost8_osc8_load24_sky130.v",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD24/config.json",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD24/pin_order.cfg",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD24/no_clock.sdc"),
        (),
        True,
    ),
    (
        "IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_DBUF_GUARD",
        "pvt_probe_turn10_dualmacro_dbuf_guard",
        ("sky130/IntegerPLL_DCO_einvp_coarse_v5_turn10_dualmacro_dbuf_guard_sky130.v",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_DBUF_GUARD/config.json",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_DBUF_GUARD/pin_order.cfg",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_DBUF_GUARD/no_clock.sdc"),
        ("IntegerPLL_DCO_EINVP_COARSE_V5_TURN10",
         "IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8"),
        True,
    ),
    (
        "IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_OSC8_DBUF_GUARD",
        "pvt_probe_turn10_dualmacro_osc8_dbuf_guard_slow240",
        ("sky130/IntegerPLL_DCO_einvp_coarse_v5_turn10_dualmacro_osc8_dbuf_guard_sky130.v",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_OSC8_DBUF_GUARD/config.json",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_OSC8_DBUF_GUARD/pin_order.cfg",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_OSC8_DBUF_GUARD/no_clock.sdc"),
        ("IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8",
         "IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8"),
        True,
    ),
    (
        "IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_OSC8_DBUF_GUARD_IDLE_RESET",
        "pvt_probe_turn10_dualmacro_osc8_dbuf_guard_idle_reset",
        ("sky130/IntegerPLL_DCO_einvp_coarse_v5_turn10_dualmacro_osc8_dbuf_guard_idle_reset_sky130.v",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_OSC8_DBUF_GUARD_IDLE_RESET/config.json",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_OSC8_DBUF_GUARD_IDLE_RESET/pin_order.cfg",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_OSC8_DBUF_GUARD_IDLE_RESET/no_clock.sdc"),
        ("IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8",
         "IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8"),
        True,
    ),
    (
        "IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_OSC8_REMAP_DBUF_GUARD",
        "pvt_probe_turn10_dualmacro_osc8_remap_dbuf_guard_fast60_slow245",
        ("sky130/IntegerPLL_DCO_einvp_coarse_v5_turn10_dualmacro_osc8_remap_dbuf_guard_sky130.v",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_OSC8_REMAP_DBUF_GUARD/config.json",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_OSC8_REMAP_DBUF_GUARD/pin_order.cfg",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_OSC8_REMAP_DBUF_GUARD/no_clock.sdc"),
        ("IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8",
         "IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8"),
        True,
    ),
    (
        "IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_OSC8_REMAP_LOAD24_DBUF_GUARD",
        "pvt_probe_turn10_dualmacro_osc8_remap_load24_dbuf_guard_slow240_bufsel_guard24",
        ("sky130/IntegerPLL_DCO_einvp_coarse_v5_turn10_dualmacro_osc8_remap_load24_dbuf_guard_sky130.v",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_OSC8_REMAP_LOAD24_DBUF_GUARD/config.json",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_OSC8_REMAP_LOAD24_DBUF_GUARD/pin_order.cfg",
         "openlane/IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_OSC8_REMAP_LOAD24_DBUF_GUARD/no_clock.sdc"),
        ("IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8",
         "IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_LOAD24"),
        True,
    ),
    (
        "IntegerPLL_HardMacroTop_EINVP_DUALMACRO_GUARD",
        "pvt_probe_dualmacro_guard_hardtop_therm2",
        ("rtl/IntegerPLL_HardMacroTop_EINVP_DUALMACRO_GUARD.v",
         "openlane/IntegerPLL_HardMacroTop_EINVP_DUALMACRO_GUARD/config.json",
         "openlane/IntegerPLL_HardMacroTop_EINVP_DUALMACRO_GUARD/pin_order.cfg",
         "openlane/IntegerPLL_HardMacroTop_EINVP_DUALMACRO_GUARD/async_macro_top.sdc"),
        ("IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_DBUF_GUARD",),
        False,
    ),
    (
        "IntegerPLL_HardMacroTop_EINVP_DUALMACRO_OSC8_REMAP_LOAD24_GUARD",
        "pvt_probe_dualmacro_osc8_remap_load24_guard_top",
        ("rtl/IntegerPLL_HardMacroTop_EINVP_DUALMACRO_OSC8_REMAP_LOAD24_GUARD.v",
         "openlane/IntegerPLL_HardMacroTop_EINVP_DUALMACRO_OSC8_REMAP_LOAD24_GUARD/config.json",
         "openlane/IntegerPLL_HardMacroTop_EINVP_DUALMACRO_OSC8_REMAP_LOAD24_GUARD/pin_order.cfg",
         "openlane/IntegerPLL_HardMacroTop_EINVP_DUALMACRO_OSC8_REMAP_LOAD24_GUARD/async_macro_top.sdc"),
        ("IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_OSC8_REMAP_LOAD24_DBUF_GUARD",),
        False,
    ),
    (
        "IntegerPLL_HardMacroTop_EINVP_25MHzConfigured_DUALMACRO_GUARD",
        "pvt_probe_dualmacro_guard_configured_status_west",
        ("rtl/IntegerPLL_25MHzModeConfig_modern.v",
         "rtl/IntegerPLL_25MHzModeController.v",
         "rtl/IntegerPLL_HardMacroTop_EINVP_25MHzConfigured_DUALMACRO_GUARD.v",
         "openlane/IntegerPLL_HardMacroTop_EINVP_25MHzConfigured_DUALMACRO_GUARD/config.json",
         "openlane/IntegerPLL_HardMacroTop_EINVP_25MHzConfigured_DUALMACRO_GUARD/pin_order.cfg",
         "openlane/IntegerPLL_HardMacroTop_EINVP_25MHzConfigured_DUALMACRO_GUARD/async_configured_top.sdc"),
        ("IntegerPLL_HardMacroTop_EINVP_DUALMACRO_GUARD",),
        False,
    ),
    (
        "IntegerPLL_HardMacroTop_EINVP_25MHzConfigured_DUALMACRO_OSC8_REMAP_LOAD24_GUARD",
        "pvt_probe_configured_dualmacro_osc8_remap_load24_guard_top",
        ("rtl/IntegerPLL_25MHzModeConfig_modern.v",
         "rtl/IntegerPLL_25MHzModeController.v",
         "rtl/IntegerPLL_HardMacroTop_EINVP_25MHzConfigured_DUALMACRO_OSC8_REMAP_LOAD24_GUARD.v",
         "openlane/IntegerPLL_HardMacroTop_EINVP_25MHzConfigured_DUALMACRO_OSC8_REMAP_LOAD24_GUARD/config.json",
         "openlane/IntegerPLL_HardMacroTop_EINVP_25MHzConfigured_DUALMACRO_OSC8_REMAP_LOAD24_GUARD/pin_order.cfg",
         "openlane/IntegerPLL_HardMacroTop_EINVP_25MHzConfigured_DUALMACRO_OSC8_REMAP_LOAD24_GUARD/async_configured_top.sdc"),
        ("IntegerPLL_HardMacroTop_EINVP_DUALMACRO_OSC8_REMAP_LOAD24_GUARD",),
        False,
    ),
)
RUN_TAG_BY_DESIGN = {design: run_tag for design, run_tag, *_ in DESIGNS}


def check_one(design, run_tag, sources, macro_cells, skip_streamout):
    directory = ROOT / "openlane" / design
    final = directory / "runs" / run_tag / "final"
    config = json.loads((directory / "config.json").read_text())
    if config.get("DESIGN_NAME") != design:
        raise ValueError(f"wrong design name in {directory / 'config.json'}")
    resolved = json.loads((directory / "runs" / run_tag / "resolved.json").read_text())
    if (resolved.get("PDK") != "sky130A"
            or Path(resolved.get("PDK_ROOT", "")).name != PDK_VERSION):
        raise ValueError(f"{design} was not run with the pinned Ciel Sky130 PDK")
    command = [sys.executable, str(ROOT / "scripts/check_librelane_signoff.py"),
               "--design-name", design, "--final-dir", str(final)]
    for source in sources:
        command += ["--source-file", source]
    if skip_streamout:
        command += ["--skip-magic-streamout", "--skip-xor"]
    subprocess.run(command, cwd=ROOT, check=True)

    netlist = (final / "nl" / f"{design}.nl.v").read_text()
    diode_count = len(re.findall(r"\bsky130_fd_sc_hd__diode_2\s+\S+\s*\(", netlist))
    if diode_count:
        raise ValueError(f"{design} contains {diode_count} antenna diode cells")
    for macro in macro_cells:
        count = len(re.findall(rf"\b{re.escape(macro)}\s+\S+\s*\(", netlist))
        if count != 1:
            raise ValueError(f"{design} contains {count} instances of {macro}; expected one")
        entry = config.get("MACROS", {}).get(macro)
        if not isinstance(entry, dict):
            raise ValueError(f"{design} does not configure {macro} as a hard macro")
        for view in ("gds", "lef", "vh", "pnl", "spice"):
            values = entry.get(view)
            if not isinstance(values, list) or len(values) != 1:
                raise ValueError(f"{design} has no unique {macro} {view} view")
            name = values[0]
            if not name.startswith("dir::"):
                raise ValueError(f"{design} has a non-local {macro} {view} view")
            path = (directory / name.removeprefix("dir::")).resolve()
            if not path.is_file():
                raise ValueError(f"{design} has a missing {macro} {view} view: {path}")
            expected_run = RUN_TAG_BY_DESIGN.get(macro)
            if expected_run is not None:
                expected_final = (ROOT / "openlane" / macro / "runs" / expected_run / "final").resolve()
                if not path.is_relative_to(expected_final):
                    raise ValueError(f"{design} uses an unexpected {macro} {view} run: {path}")
            if path.stat().st_mtime_ns > (final / "metrics.json").stat().st_mtime_ns:
                raise ValueError(f"{design} signoff predates its {macro} {view}")
    print(f"PASS: {design} is diode-free with the expected macro instances")


def main():
    for args in DESIGNS:
        check_one(*args)
    print("PASS: diode-free multi-macro physical hierarchy; functional release remains separate")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
