#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check the current 25 MHz-reference coarse-DCO PLL release artifacts."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

EXPECTED_TARGETS = {
    100: {"multiplier": 4, "coarse_code": 20, "target_code": 93},
    250: {"multiplier": 10, "coarse_code": 6, "target_code": 234},
    300: {"multiplier": 12, "coarse_code": 4, "target_code": 90},
    400: {"multiplier": 16, "coarse_code": 2, "target_code": 76},
}

NEARSEED_MIN_RISES = {
    100: 3,
    250: 6,
    300: 8,
    400: 8,
}

def repo_path(path: str | Path) -> Path:
    path = Path(path).expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def artifact_text(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def require_file(path: Path) -> Path:
    if not path.is_file():
        raise ValueError(f"missing artifact: {artifact_text(path)}")
    return path


def read_csv(path: Path) -> list[dict[str, str]]:
    require_file(path)
    with path.open(newline="", encoding="ascii") as csv_file:
        return list(csv.DictReader(csv_file))


def read_json(path: Path) -> dict[str, object]:
    require_file(path)
    with path.open(encoding="ascii") as json_file:
        data = json.load(json_file)
    if not isinstance(data, dict):
        raise ValueError(f"{artifact_text(path)} is not a JSON object")
    return data


def to_int(row: dict[str, str], key: str) -> int:
    try:
        return int(float(row[key]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid integer field {key!r} in row {row}") from exc


def to_float(row: dict[str, str], key: str) -> float:
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid float field {key!r} in row {row}") from exc


def require_close(name: str, value: float, expected: float, tol: float = 1.0e-6) -> None:
    if abs(value - expected) > tol:
        raise ValueError(f"{name} is {value}, expected {expected}")


def check_dco_structure(root: Path) -> dict[str, str]:
    path = require_file(root / "sky130" / "IntegerPLL_DCO_einvp_coarse_sky130.v")
    text = path.read_text(encoding="ascii", errors="replace")
    required = (
        "module IntegerPLL_DCO_EINVP_COARSE",
        "input wire [46:0] COARSETHERMAL_CODE",
        "wire [47:0] mirror_fwd",
        "sky130_fd_sc_hs__nand2_4 osc_gate",
        "sky130_fd_sc_hs__nand2_4 mirror_forward",
        "sky130_fd_sc_hs__nand2b_4 mirror_turn",
        "sky130_fd_sc_hs__nand2b_4 mirror_return",
        "sky130_fd_sc_hs__nand2_4 mirror_merge",
        "sky130_fd_sc_hs__buf_1 out_buf",
        "sky130_fd_sc_hs__nand2_1 tune_load",
        "for (f = 0; f < 90; f = f + 1)",
        "DCO_THERM_INDEX",
    )
    missing = [fragment for fragment in required if fragment not in text]
    if missing:
        raise ValueError(f"{artifact_text(path)} missing required fragment(s): {missing}")

    forbidden = (
        "sky130_fd_sc_hd__inv_1",
        "sky130_fd_sc_hs__inv_1",
        "sky130_fd_sc_hd__mux4_1",
        "sky130_fd_sc_hs__mux4_1",
        "sky130_fd_sc_hd__einvp_1 tune_load",
        "sky130_fd_sc_hd__buf_2 out_buf",
        "sky130_fd_sc_hd__buf_4 out_buf",
        "sky130_fd_sc_hd__buf_8 out_buf",
        "sky130_fd_sc_hd__buf_16 out_buf",
        "sky130_fd_sc_hs__buf_2 out_buf",
        "sky130_fd_sc_hs__buf_4 out_buf",
        "sky130_fd_sc_hs__buf_8 out_buf",
        "sky130_fd_sc_hs__buf_16 out_buf",
        "gen_c19_slow_dco_load",
        "gen_slow_dco_load",
        "c19_slow_band",
        "c20_slow_band",
        "mirror_fwd[19]",
        "mirror_ret[19]",
        "mirror_fwd[20]",
        "mirror_ret[20]",
    )
    present = [fragment for fragment in forbidden if fragment in text]
    if present:
        raise ValueError(f"{artifact_text(path)} contains forbidden fragment(s): {present}")

    return {
        "rtl": artifact_text(path),
        "coarse_topology": "hs_nand_nand2b_mirror_delay",
        "output_buffer": "sky130_fd_sc_hs__buf_1",
        "fine_loads": "90 local hs_nand2 loads",
    }


def check_mode_config(root: Path) -> dict[str, object]:
    path = require_file(root / "rtl" / "IntegerPLL_25MHzModeConfig.v")
    text = path.read_text(encoding="ascii", errors="replace")
    fragments = (
        "module IntegerPLL_25MHzModeConfig",
        "MMDCLKDIV_RATIO = 8'd4",
        "COARSEBINARY_CODE = 6'd20",
        "TARGET_DCO_CODE = 8'd93",
        "DLF_Ext_Data = seed_word(8'd93)",
        "MMDCLKDIV_RATIO = 8'd10",
        "COARSEBINARY_CODE = 6'd6",
        "TARGET_DCO_CODE = 8'd234",
        "DLF_Ext_Data = seed_word(8'd234)",
        "MMDCLKDIV_RATIO = 8'd12",
        "COARSEBINARY_CODE = 6'd4",
        "TARGET_DCO_CODE = 8'd90",
        "DLF_Ext_Data = seed_word(8'd90)",
        "MMDCLKDIV_RATIO = 8'd16",
        "COARSEBINARY_CODE = 6'd2",
        "TARGET_DCO_CODE = 8'd76",
        "DLF_Ext_Data = seed_word(8'd76)",
        "DLF_KI = {{(GAIN_WIDTH-5){1'b0}}, 5'd16}",
        "DLF_KP = {{(GAIN_WIDTH-3){1'b0}}, 3'd4}",
    )
    missing = [fragment for fragment in fragments if fragment not in text]
    if missing:
        raise ValueError(f"{artifact_text(path)} missing mode-config fragment(s): {missing}")
    return {
        "rtl": artifact_text(path),
        "modes": [
            {"target_mhz": 100, "multiplier": 4, "coarse_code": 20, "target_code": 93},
            {"target_mhz": 250, "multiplier": 10, "coarse_code": 6, "target_code": 234},
            {"target_mhz": 300, "multiplier": 12, "coarse_code": 4, "target_code": 90},
            {"target_mhz": 400, "multiplier": 16, "coarse_code": 2, "target_code": 76},
        ],
        "ki": 16,
        "kp": 4,
        "dlf_seed": "target_code << 2 for CODE_WIDTH=10",
    }


def check_mode_controller(root: Path) -> dict[str, str]:
    controller_path = require_file(root / "rtl" / "IntegerPLL_25MHzModeController.v")
    controller_text = controller_path.read_text(encoding="ascii", errors="replace")
    controller_fragments = (
        "module IntegerPLL_25MHzModeController",
        "parameter CLEAR_CYCLES = 4",
        "STATE_LOAD",
        "STATE_TRACK",
        "mode_latched",
        "assign DLF_En = track_active",
        "assign DLF_Clear = load_active",
        "assign DLF_Ext_Override = 1'b0",
        "assign DLF_IN_POL = 1'b1",
        "IntegerPLL_25MHzModeConfig",
        "MODE_SELECT != mode_latched",
    )
    missing = [
        fragment for fragment in controller_fragments if fragment not in controller_text
    ]
    if missing:
        raise ValueError(
            f"{artifact_text(controller_path)} missing controller fragment(s): {missing}"
        )

    wrapper_path = require_file(root / "rtl" / "IntegerPLL_HardMacroTop_EINVP_25MHzConfigured.v")
    wrapper_text = wrapper_path.read_text(encoding="ascii", errors="replace")
    wrapper_fragments = (
        "module IntegerPLL_HardMacroTop_EINVP_25MHzConfigured",
        "input wire PLL_ENABLE",
        "input wire [1:0] MODE_SELECT",
        "output wire CONFIG_BUSY",
        "output wire TRACKING",
        "IntegerPLL_25MHzModeController",
        "IntegerPLL_HardMacroTop_EINVP hard_macro",
        ".DLF_En(dlf_en)",
        ".DLF_Clear(dlf_clear)",
        ".DLF_Ext_Data(dlf_ext_data)",
        ".COARSEBINARY_CODE(coarse_code)",
        ".MMDCLKDIV_RATIO(mmd_ratio)",
    )
    missing = [fragment for fragment in wrapper_fragments if fragment not in wrapper_text]
    if missing:
        raise ValueError(
            f"{artifact_text(wrapper_path)} missing wrapper fragment(s): {missing}"
        )

    test_path = require_file(root / "tb" / "tb_pll_25mhz_mode_controller.v")
    wrapper_test_path = require_file(root / "tb" / "tb_pll_25mhz_configured_wrapper.v")
    behavioral_test_path = require_file(root / "tb" / "tb_pll_25mhz_configured_behavioral.v")
    behavioral_model_path = require_file(root / "models" / "IntegerPLL_DCO_25MHzCoarse_model.v")
    stub_path = require_file(root / "tb" / "IntegerPLL_HardMacroTop_EINVP_stub.v")
    behavioral_model_text = behavioral_model_path.read_text(encoding="ascii", errors="replace")
    for fragment in (
        "module IntegerPLL_DCO",
        "input wire [5:0] COARSEBINARY_CODE",
        "c20_freq_mhz",
        "c06_freq_mhz",
        "c04_freq_mhz",
        "c02_freq_mhz",
        "6'd20",
        "6'd6",
        "6'd4",
        "6'd2",
    ):
        if fragment not in behavioral_model_text:
            raise ValueError(
                f"{artifact_text(behavioral_model_path)} missing behavioral model fragment {fragment!r}"
            )
    return {
        "controller_rtl": artifact_text(controller_path),
        "configured_wrapper_rtl": artifact_text(wrapper_path),
        "testbench": artifact_text(test_path),
        "configured_wrapper_testbench": artifact_text(wrapper_test_path),
        "configured_behavioral_testbench": artifact_text(behavioral_test_path),
        "configured_behavioral_dco_model": artifact_text(behavioral_model_path),
        "wrapper_syntax_stub": artifact_text(stub_path),
        "sequence": "load preset with DLF_Clear, then enable closed-loop tracking",
    }


def check_hardtop_summary(summary_path: Path, spice_summary_path: Path) -> dict[str, object]:
    summary = read_json(summary_path)
    if summary.get("status") != "pass":
        raise ValueError(f"{artifact_text(summary_path)} status is not pass")
    if summary.get("design") != "IntegerPLL_HardMacroTop_EINVP":
        raise ValueError(f"{artifact_text(summary_path)} has wrong design: {summary.get('design')}")
    if summary.get("dco_macro") != "IntegerPLL_DCO_EINVP_COARSE":
        raise ValueError(
            f"{artifact_text(summary_path)} has wrong DCO macro: {summary.get('dco_macro')}"
        )

    config = summary.get("config")
    signoff = summary.get("signoff")
    if not isinstance(config, dict) or not isinstance(signoff, dict):
        raise ValueError(f"{artifact_text(summary_path)} missing config/signoff data")
    if config.get("macro_count") != 3:
        raise ValueError(f"{artifact_text(summary_path)} macro count is {config.get('macro_count')}")
    if signoff.get("status") != "pass":
        raise ValueError(f"{artifact_text(summary_path)} signoff status is {signoff.get('status')}")
    if signoff.get("stdcells") != 61100:
        raise ValueError(f"{artifact_text(summary_path)} stdcell count changed: {signoff.get('stdcells')}")
    if signoff.get("vias") != 1826:
        raise ValueError(f"{artifact_text(summary_path)} via count changed: {signoff.get('vias')}")
    if signoff.get("wirelength") != 190674:
        raise ValueError(
            f"{artifact_text(summary_path)} wirelength changed: {signoff.get('wirelength')}"
        )

    placements = signoff.get("placements")
    if not isinstance(placements, list) or len(placements) != 3:
        raise ValueError(f"{artifact_text(summary_path)} placement summary is incomplete")
    placement_by_instance = {
        row.get("instance"): row for row in placements if isinstance(row, dict)
    }
    for instance, macro in (
        ("phase_detector", "IntegerPLL_BBPD"),
        ("digital_core", "IntegerPLL_DigitalCore"),
        ("oscillator", "IntegerPLL_DCO_EINVP_COARSE"),
    ):
        row = placement_by_instance.get(instance)
        if not isinstance(row, dict) or row.get("macro") != macro or row.get("status") != "FIXED":
            raise ValueError(f"{artifact_text(summary_path)} bad placement for {instance}: {row}")

    spice_summary = read_json(spice_summary_path)
    if spice_summary.get("status") != "pass":
        raise ValueError(f"{artifact_text(spice_summary_path)} status is not pass")
    expected_spice = {
        "top": "IntegerPLL_HardMacroTop_EINVP",
        "dco_subckt": "IntegerPLL_DCO_EINVP_COARSE",
        "top_port_count": 73,
        "dco_therm_connections": 255,
        "dco_coarse_therm_connections": 47,
        "antenna_dco_therm_connections": 5,
        "spef_d_nets": 374,
        "spef_cap_entries": 10082,
        "spef_res_entries": 1670,
    }
    for key, expected in expected_spice.items():
        if spice_summary.get(key) != expected:
            raise ValueError(
                f"{artifact_text(spice_summary_path)} {key} is {spice_summary.get(key)}, "
                f"expected {expected}"
            )
    xyce_norun = spice_summary.get("xyce_norun")
    if not isinstance(xyce_norun, dict) or xyce_norun.get("returncode") != 0:
        raise ValueError(f"{artifact_text(spice_summary_path)} Xyce -norun did not pass")

    return {
        "summary": artifact_text(summary_path),
        "spice_summary": artifact_text(spice_summary_path),
        "stdcells": signoff["stdcells"],
        "wirelength": signoff["wirelength"],
        "vias": signoff["vias"],
        "macro_count": config["macro_count"],
        "dco_macro": summary["dco_macro"],
        "top_ports": spice_summary["top_port_count"],
        "dco_therm_connections": spice_summary["dco_therm_connections"],
        "dco_coarse_therm_connections": spice_summary["dco_coarse_therm_connections"],
        "spef_cap_entries": spice_summary["spef_cap_entries"],
        "spef_res_entries": spice_summary["spef_res_entries"],
    }


def check_configured_hardtop_summary(summary_path: Path) -> dict[str, object]:
    summary = read_json(summary_path)
    if summary.get("status") != "pass":
        raise ValueError(f"{artifact_text(summary_path)} status is not pass")
    if summary.get("design") != "IntegerPLL_HardMacroTop_EINVP_25MHzConfigured":
        raise ValueError(f"{artifact_text(summary_path)} has wrong design: {summary.get('design')}")
    if summary.get("embedded_macro") != "IntegerPLL_HardMacroTop_EINVP":
        raise ValueError(
            f"{artifact_text(summary_path)} embeds wrong macro: {summary.get('embedded_macro')}"
        )

    config = summary.get("config")
    signoff = summary.get("signoff")
    if not isinstance(config, dict) or not isinstance(signoff, dict):
        raise ValueError(f"{artifact_text(summary_path)} missing config/signoff data")
    if config.get("macro_count") != 1:
        raise ValueError(f"{artifact_text(summary_path)} macro count is {config.get('macro_count')}")
    if signoff.get("status") != "pass":
        raise ValueError(f"{artifact_text(summary_path)} signoff status is {signoff.get('status')}")
    if signoff.get("stdcells") != 39777:
        raise ValueError(
            f"{artifact_text(summary_path)} stdcell count changed: {signoff.get('stdcells')}"
        )
    if signoff.get("vias") != 999:
        raise ValueError(f"{artifact_text(summary_path)} via count changed: {signoff.get('vias')}")
    if signoff.get("wirelength") != 40118:
        raise ValueError(
            f"{artifact_text(summary_path)} wirelength changed: {signoff.get('wirelength')}"
        )

    placements = signoff.get("placements")
    if not isinstance(placements, list) or len(placements) != 1:
        raise ValueError(f"{artifact_text(summary_path)} placement summary is incomplete")
    placement = placements[0]
    if (
        not isinstance(placement, dict)
        or placement.get("instance") != "hard_macro"
        or placement.get("macro") != "IntegerPLL_HardMacroTop_EINVP"
        or placement.get("status") != "FIXED"
        or placement.get("location_um") != [120.0, 120.0]
        or placement.get("orientation") != "N"
    ):
        raise ValueError(f"{artifact_text(summary_path)} bad configured placement: {placement}")

    return {
        "summary": artifact_text(summary_path),
        "stdcells": signoff["stdcells"],
        "wirelength": signoff["wirelength"],
        "vias": signoff["vias"],
        "macro_count": config["macro_count"],
        "embedded_macro": summary["embedded_macro"],
        "placement": placement,
    }


def check_target_results(path: Path, args: argparse.Namespace) -> list[dict[str, object]]:
    rows = read_csv(path)
    by_target = {int(round(to_float(row, "target_mhz"))): row for row in rows}
    checked: list[dict[str, object]] = []
    for target_mhz, expected in EXPECTED_TARGETS.items():
        row = by_target.get(target_mhz)
        if row is None:
            raise ValueError(f"{artifact_text(path)} missing target {target_mhz} MHz row")
        if row.get("status") != "pass":
            raise ValueError(f"target {target_mhz} MHz DCO row is not pass: {row}")
        require_close(f"{target_mhz} multiplier", to_float(row, "multiplier"), expected["multiplier"])
        if to_int(row, "coarse_code") != expected["coarse_code"]:
            raise ValueError(f"target {target_mhz} coarse code row is {row}")
        if to_int(row, "target_code") != expected["target_code"]:
            raise ValueError(f"target {target_mhz} fine code row is {row}")
        passing_gains = {
            item.strip()
            for item in row.get("passing_gains", "").split(";")
            if item.strip()
        }
        if "ki16_kp4" not in passing_gains:
            raise ValueError(f"target {target_mhz} missing promoted gain ki16_kp4: {row}")
        for key in ("low_duty_ratio", "high_duty_ratio"):
            duty = to_float(row, key)
            if duty < args.min_duty_ratio or duty > args.max_duty_ratio:
                raise ValueError(f"target {target_mhz} {key}={duty} outside limits")
        for key in (
            "low_rise_period_fraction",
            "high_rise_period_fraction",
            "low_fall_period_fraction",
            "high_fall_period_fraction",
        ):
            edge = to_float(row, key)
            if edge > args.max_edge_period_fraction:
                raise ValueError(f"target {target_mhz} {key}={edge} exceeds limit")
        checked.append(
            {
                "target_mhz": target_mhz,
                "multiplier": expected["multiplier"],
                "coarse_code": expected["coarse_code"],
                "target_code": expected["target_code"],
                "selection": row.get("selection", ""),
                "target_code_est": to_float(row, "target_code_est"),
                "passing_gains": sorted(passing_gains),
            }
        )
    return checked


def check_tracking_summary(path: Path, args: argparse.Namespace) -> list[dict[str, object]]:
    rows = read_csv(path)
    checked: list[dict[str, object]] = []
    for target_mhz, expected in EXPECTED_TARGETS.items():
        target_rows = [
            row
            for row in rows
            if int(round(to_float(row, "target_mhz"))) == target_mhz
            and to_int(row, "ki") == 16
            and to_int(row, "kp") == 4
        ]
        expects = {row.get("expect"): row for row in target_rows}
        if set(expects) != {"increase", "decrease"}:
            raise ValueError(
                f"{artifact_text(path)} target {target_mhz} lacks low/high ki16_kp4 rows"
            )
        for expect, row in sorted(expects.items()):
            if row.get("target_pass") != "1":
                raise ValueError(f"target {target_mhz} {expect} tracking row failed: {row}")
            require_close(f"{target_mhz} ref", to_float(row, "ref_mhz"), 25.0)
            require_close(
                f"{target_mhz} multiplier",
                to_float(row, "multiplier"),
                expected["multiplier"],
            )
            if to_int(row, "coarse_code") != expected["coarse_code"]:
                raise ValueError(f"target {target_mhz} tracking coarse mismatch: {row}")
            if to_int(row, "target_code") != expected["target_code"]:
                raise ValueError(f"target {target_mhz} tracking code mismatch: {row}")
            if to_int(row, "frac") != 2 or to_int(row, "track_decay_shift") != 0:
                raise ValueError(f"target {target_mhz} tracking uses non-promoted settings: {row}")
            if to_int(row, "expected_decisions") < args.min_expected_decisions:
                raise ValueError(f"target {target_mhz} {expect} has too few BBPD decisions: {row}")
            if row.get("tol_hit") != "1":
                raise ValueError(f"target {target_mhz} {expect} never reached code tolerance: {row}")
            freq_tol = to_float(row, "freq_tol_mhz")
            if freq_tol > args.tracking_freq_tol_mhz:
                raise ValueError(f"target {target_mhz} tracking freq tolerance loosened: {row}")
            if to_float(row, "final_freq_abs_error_mhz") > freq_tol:
                raise ValueError(f"target {target_mhz} final frequency error is too high: {row}")
            if to_float(row, "late_max_freq_abs_error_mhz") > freq_tol:
                raise ValueError(f"target {target_mhz} late frequency error is too high: {row}")
            if to_int(row, "late_code_span") > args.max_late_code_span:
                raise ValueError(f"target {target_mhz} late code span is too wide: {row}")
            checked.append(
                {
                    "case": row["case"],
                    "target_mhz": target_mhz,
                    "expect": expect,
                    "final_code": to_int(row, "final_code"),
                    "final_freq_abs_error_mhz": to_float(row, "final_freq_abs_error_mhz"),
                    "late_max_freq_abs_error_mhz": to_float(row, "late_max_freq_abs_error_mhz"),
                    "late_code_span": to_int(row, "late_code_span"),
                    "expected_decisions": to_int(row, "expected_decisions"),
                }
            )
    return checked


def check_hold_summary(path: Path) -> list[dict[str, object]]:
    rows = read_csv(path)
    by_target = {int(round(to_float(row, "target_mhz"))): row for row in rows}
    checked: list[dict[str, object]] = []
    for target_mhz, expected in EXPECTED_TARGETS.items():
        row = by_target.get(target_mhz)
        if row is None:
            raise ValueError(f"{artifact_text(path)} missing hold row for {target_mhz} MHz")
        if row.get("status") != "pass":
            raise ValueError(f"target {target_mhz} direct-RCX hold row failed: {row}")
        require_close(f"{target_mhz} ref", to_float(row, "ref_mhz"), 25.0)
        require_close(f"{target_mhz} multiplier", to_float(row, "multiplier"), expected["multiplier"])
        if to_int(row, "coarse_code") != expected["coarse_code"]:
            raise ValueError(f"target {target_mhz} hold coarse mismatch: {row}")
        if to_int(row, "target_code") != expected["target_code"]:
            raise ValueError(f"target {target_mhz} hold code mismatch: {row}")
        if to_int(row, "final_code") != expected["target_code"]:
            raise ValueError(f"target {target_mhz} hold final code mismatch: {row}")
        if to_float(row, "freq_abs_error_mhz") > to_float(row, "freq_tol_mhz"):
            raise ValueError(f"target {target_mhz} hold frequency error too high: {row}")
        if to_int(row, "pllout_rises") <= 0:
            raise ValueError(f"target {target_mhz} hold did not observe PLLOUT rises: {row}")
        checked.append(
            {
                "target_mhz": target_mhz,
                "coarse_code": expected["coarse_code"],
                "target_code": expected["target_code"],
                "measured_mhz": to_float(row, "measured_mhz"),
                "freq_abs_error_mhz": to_float(row, "freq_abs_error_mhz"),
                "pllout_rises": to_int(row, "pllout_rises"),
            }
        )
    return checked


def check_nearseed_summary(path: Path, args: argparse.Namespace) -> list[dict[str, object]]:
    rows = read_csv(path)
    by_case = {
        (int(round(to_float(row, "target_mhz"))), row.get("side")): row
        for row in rows
    }
    checked: list[dict[str, object]] = []
    for target_mhz, expected in EXPECTED_TARGETS.items():
        for side in ("low", "high"):
            row = by_case.get((target_mhz, side))
            if row is None:
                raise ValueError(
                    f"{artifact_text(path)} missing near-seed {target_mhz} MHz {side} row"
                )
            if row.get("status") != "pass":
                raise ValueError(f"near-seed {target_mhz} MHz {side} row failed: {row}")
            require_close(f"{target_mhz} near-seed ref", to_float(row, "ref_mhz"), 25.0)
            require_close(
                f"{target_mhz} near-seed multiplier",
                to_float(row, "multiplier"),
                expected["multiplier"],
            )
            if to_int(row, "coarse_code") != expected["coarse_code"]:
                raise ValueError(f"near-seed {target_mhz} MHz {side} coarse mismatch: {row}")
            target_code = expected["target_code"]
            if to_int(row, "target_code") != target_code:
                raise ValueError(f"near-seed {target_mhz} MHz {side} code mismatch: {row}")
            expected_init = target_code - 4 if side == "low" else target_code + 4
            if to_int(row, "init_code") != expected_init:
                raise ValueError(f"near-seed {target_mhz} MHz {side} init mismatch: {row}")
            expected_direction = "increase" if side == "low" else "decrease"
            if row.get("expect") != expected_direction:
                raise ValueError(f"near-seed {target_mhz} MHz {side} direction mismatch: {row}")
            expected_divider_seed = 0 if side == "low" else expected["multiplier"] - 1
            if to_int(row, "initial_divider_count") != expected_divider_seed:
                raise ValueError(
                    f"near-seed {target_mhz} MHz {side} divider seed mismatch: {row}"
                )
            expected_phase = -0.25 if side == "low" else 0.25
            require_close(
                f"{target_mhz} near-seed {side} phase",
                to_float(row, "clock_phase_offset"),
                expected_phase,
            )
            if to_int(row, "cycles") != 2:
                raise ValueError(f"near-seed {target_mhz} MHz {side} cycles mismatch: {row}")
            if to_int(row, "ki") != 16 or to_int(row, "kp") != 4 or to_int(row, "frac") != 2:
                raise ValueError(f"near-seed {target_mhz} MHz {side} gain mismatch: {row}")
            if to_int(row, "final_abs_error") > args.nearseed_tol_code:
                raise ValueError(f"near-seed {target_mhz} MHz {side} final error too high: {row}")
            if to_int(row, "expected_decisions") < args.nearseed_min_expected_decisions:
                raise ValueError(
                    f"near-seed {target_mhz} MHz {side} expected-decision count too low: {row}"
                )
            if to_float(row, "freq_abs_error_mhz") > to_float(row, "freq_tol_mhz"):
                raise ValueError(
                    f"near-seed {target_mhz} MHz {side} frequency estimate too far: {row}"
                )
            if to_int(row, "pllout_rises") < NEARSEED_MIN_RISES[target_mhz]:
                raise ValueError(
                    f"near-seed {target_mhz} MHz {side} PLLOUT rise count too low: {row}"
                )
            log_path = repo_path(row.get("log", ""))
            require_file(log_path)
            checked.append(
                {
                    "target_mhz": target_mhz,
                    "side": side,
                    "init_code": to_int(row, "init_code"),
                    "final_code": to_int(row, "final_code"),
                    "target_code": target_code,
                    "final_abs_error": to_int(row, "final_abs_error"),
                    "expected_decisions": to_int(row, "expected_decisions"),
                    "clock_phase_offset": to_float(row, "clock_phase_offset"),
                    "measured_mhz": to_float(row, "measured_mhz"),
                    "freq_abs_error_mhz": to_float(row, "freq_abs_error_mhz"),
                    "log": artifact_text(log_path),
                }
            )
    return checked


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target-results",
        default="build/xyce_pll_25mhz_target_sweep_coarse90_drv4_nodeepslow0_tracking_near4/pll_25mhz_target_results.csv",
    )
    parser.add_argument(
        "--tracking-summary",
        default="build/xyce_pll_25mhz_target_sweep_coarse90_drv4_nodeepslow0_tracking_near4/pll_25mhz_target_summary.csv",
    )
    parser.add_argument(
        "--hold-summary",
        default="build/xyce_pll_postlayout_dco_mixed_25mhz_coarse90_drv4_nodeepslow0/pll_postlayout_dco_25mhz_hold_summary.csv",
    )
    parser.add_argument(
        "--nearseed-summary",
        default="build/xyce_pll_postlayout_dco_mixed_25mhz_coarse90_drv4_nodeepslow0/pll_postlayout_dco_25mhz_nearseed_summary.csv",
    )
    parser.add_argument(
        "--hardtop-summary",
        default="build/hard_macro_top_einvp/hard_macro_top_einvp_summary.json",
    )
    parser.add_argument(
        "--hardtop-spice-summary",
        default="build/hard_macro_top_einvp_spice/hard_macro_top_spice_summary.json",
    )
    parser.add_argument(
        "--configured-hardtop-summary",
        default="build/configured_hard_macro_top_einvp/configured_hard_macro_top_einvp_summary.json",
    )
    parser.add_argument(
        "--out-json",
        default="build/sky130_pll_25mhz_release/check_summary.json",
    )
    parser.add_argument("--min-duty-ratio", type=float, default=0.35)
    parser.add_argument("--max-duty-ratio", type=float, default=0.65)
    parser.add_argument("--max-edge-period-fraction", type=float, default=0.25)
    parser.add_argument("--tracking-freq-tol-mhz", type=float, default=2.0)
    parser.add_argument("--max-late-code-span", type=int, default=16)
    parser.add_argument("--min-expected-decisions", type=int, default=1)
    parser.add_argument("--nearseed-tol-code", type=int, default=4)
    parser.add_argument("--nearseed-min-expected-decisions", type=int, default=2)
    args = parser.parse_args()

    target_results_path = repo_path(args.target_results)
    tracking_summary_path = repo_path(args.tracking_summary)
    hold_summary_path = repo_path(args.hold_summary)
    nearseed_summary_path = repo_path(args.nearseed_summary)
    hardtop_summary_path = repo_path(args.hardtop_summary)
    hardtop_spice_summary_path = repo_path(args.hardtop_spice_summary)
    configured_hardtop_summary_path = repo_path(args.configured_hardtop_summary)
    out_json_path = repo_path(args.out_json)

    summary = {
        "status": "pass",
        "ref_mhz": 25.0,
        "targets_mhz": sorted(EXPECTED_TARGETS),
        "artifacts": {
            "target_results": artifact_text(target_results_path),
            "tracking_summary": artifact_text(tracking_summary_path),
            "hold_summary": artifact_text(hold_summary_path),
            "nearseed_summary": artifact_text(nearseed_summary_path),
            "hardtop_summary": artifact_text(hardtop_summary_path),
            "hardtop_spice_summary": artifact_text(hardtop_spice_summary_path),
            "configured_hardtop_summary": artifact_text(configured_hardtop_summary_path),
        },
        "dco_structure": check_dco_structure(ROOT),
        "mode_config": check_mode_config(ROOT),
        "mode_controller": check_mode_controller(ROOT),
        "hardtop": check_hardtop_summary(hardtop_summary_path, hardtop_spice_summary_path),
        "configured_hardtop": check_configured_hardtop_summary(configured_hardtop_summary_path),
        "target_results": check_target_results(target_results_path, args),
        "configured_tracking": check_tracking_summary(tracking_summary_path, args),
        "direct_rcx_holds": check_hold_summary(hold_summary_path),
        "direct_rcx_nearseed": check_nearseed_summary(nearseed_summary_path, args),
    }

    out_json_path.parent.mkdir(parents=True, exist_ok=True)
    out_json_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="ascii")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
