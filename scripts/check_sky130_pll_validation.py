#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Audit promoted Sky130 PLL validation artifacts.

This checker intentionally reads promoted signoff/SPICE/RTL artifacts instead
of diagnostic sweeps. It is a fast gate for the evidence that currently supports
the Sky130 PLL implementation.
"""

import argparse
import csv
import json
import math
import sys
from pathlib import Path


ZERO_METRICS = (
    "route__drc_errors",
    "antenna__violating__nets",
    "antenna__violating__pins",
    "route__antenna_violation__count",
    "design__power_grid_violation__count",
    "timing__setup__wns",
    "timing__setup__tns",
    "timing__hold__wns",
    "timing__hold__tns",
    "timing__setup_vio__count",
    "timing__hold_vio__count",
    "design__max_slew_violation__count",
    "design__max_cap_violation__count",
    "design__max_fanout_violation__count",
    "design__violations",
    "magic__drc_error__count",
    "klayout__drc_error__count",
    "design__xor_difference__count",
    "magic__illegal_overlap__count",
    "design__lvs_error__count",
    "design__lvs_device_difference__count",
    "design__lvs_net_difference__count",
    "design__lvs_property_fail__count",
    "design__lvs_unmatched_device__count",
    "design__lvs_unmatched_net__count",
    "design__lvs_unmatched_pin__count",
)


EXPECTED_CORNERS = ("ff", "fs", "sf", "ss", "tt")


def read_csv(path):
    with path.open(newline="", encoding="ascii") as csv_file:
        return list(csv.DictReader(csv_file))


def read_json(path):
    return json.loads(path.read_text(encoding="ascii"))


def to_int(row, key):
    try:
        return int(float(row[key]))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid integer field {key!r} in row {row}") from exc


def to_float(row, key):
    try:
        return float(row[key])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid float field {key!r} in row {row}") from exc


def is_zero(value):
    return value in (0, 0.0, "0")


def require_path(root, relpath):
    path = root / relpath
    if not path.is_file():
        raise ValueError(f"missing artifact: {path}")
    return path


def require_text_fragments(root, relpath, fragments):
    path = require_path(root, relpath)
    text = path.read_text(encoding="ascii", errors="replace")
    missing = [fragment for fragment in fragments if fragment not in text]
    if missing:
        raise ValueError(f"{relpath} is missing expected fragment(s): {missing}")
    return text


def require_text_absent(root, relpath, fragments):
    path = require_path(root, relpath)
    text = path.read_text(encoding="ascii", errors="replace")
    present = [fragment for fragment in fragments if fragment in text]
    if present:
        raise ValueError(f"{relpath} contains forbidden fragment(s): {present}")
    return text


def require_all_pass(rows, status_key="status", pass_value="pass"):
    failed = [row for row in rows if row.get(status_key) != pass_value]
    if failed:
        preview = ", ".join(str(row) for row in failed[:3])
        raise ValueError(f"{len(failed)} row(s) are not {pass_value!r}: {preview}")


def xyce_elapsed_run_time_s(log_text):
    for line in log_text.splitlines():
        if "***** Total Elapsed Run Time:" not in line:
            continue
        value = line.split(":", 1)[1].split("seconds", 1)[0].strip()
        try:
            return float(value)
        except ValueError:
            return None
    return None


def check_signoff_block(
    root,
    block,
    rel_run_dir,
    require_spef,
    source_relpaths,
    require_rcx=True,
):
    run_dir = root / rel_run_dir
    final_dir = run_dir / "final"
    metrics_path = require_path(root, f"{rel_run_dir}/final/metrics.json")
    metrics = read_json(metrics_path)

    rel_views = [
        f"{rel_run_dir}/final/def/{block}.def",
        f"{rel_run_dir}/final/gds/{block}.gds",
        f"{rel_run_dir}/final/klayout_gds/{block}.klayout.gds",
        f"{rel_run_dir}/final/lef/{block}.lef",
        f"{rel_run_dir}/final/nl/{block}.nl.v",
        f"{rel_run_dir}/final/odb/{block}.odb",
        f"{rel_run_dir}/final/pnl/{block}.pnl.v",
        f"{rel_run_dir}/final/sdc/{block}.sdc",
        f"{rel_run_dir}/final/spice/{block}.spice",
    ]
    if require_spef:
        rel_views.extend(
            [
                f"{rel_run_dir}/final/spef/min/{block}.min.spef",
                f"{rel_run_dir}/final/spef/nom/{block}.nom.spef",
                f"{rel_run_dir}/final/spef/max/{block}.max.spef",
            ]
        )
    elif require_rcx:
        rel_views.extend(
            [
                f"{rel_run_dir}/51-openroad-rcx/min/{block}.min.spef",
                f"{rel_run_dir}/51-openroad-rcx/nom/{block}.nom.spef",
                f"{rel_run_dir}/51-openroad-rcx/max/{block}.max.spef",
                f"{rel_run_dir}/rcx-magic/{block}.rcx.spice",
            ]
        )

    for relpath in rel_views:
        require_path(root, relpath)

    metric_failures = []
    for key in ZERO_METRICS:
        if key not in metrics:
            metric_failures.append(f"missing {key}")
        elif not is_zero(metrics[key]):
            metric_failures.append(f"{key}={metrics[key]}")
    metrics_mtime = metrics_path.stat().st_mtime
    for relpath in source_relpaths:
        source_path = require_path(root, relpath)
        if source_path.stat().st_mtime > metrics_mtime:
            metric_failures.append(
                f"stale signoff: {metrics_path} is older than {source_path}"
            )
    if metric_failures:
        raise ValueError("; ".join(metric_failures))

    return {
        "block": block,
        "stdcells": metrics.get("design__instance__count__stdcell"),
        "utilization": metrics.get("design__instance__utilization"),
        "wirelength": metrics.get("route__wirelength"),
        "vias": metrics.get("route__vias"),
        "metrics": str(metrics_path),
        "final_dir": str(final_dir),
    }


def check_sky130_top_smoke(root):
    compile_path = require_path(root, "build/check/sky130_macro_compile.vvp")
    einvp_compile_path = require_path(root, "build/check/sky130_dco_einvp_compile.vvp")
    smoke_path = require_path(root, "build/check/sky130_macro_top_smoke.vvp")
    log_path = require_path(root, "build/check/sky130_macro_top_smoke.log")
    log_text = log_path.read_text(encoding="ascii")

    expected_lines = (
        "CHECK: ext=0 dco_code=0 therm_low_bits=0 therm_high_bits=255",
        "CHECK: ext=512 dco_code=128 therm_low_bits=128 therm_high_bits=127",
        "CHECK: ext=1020 dco_code=255 therm_low_bits=255 therm_high_bits=0",
        "PASS: Sky130 structural top smoke",
    )
    missing = [line for line in expected_lines if line not in log_text]
    if missing:
        raise ValueError(f"Sky130 top smoke log is missing expected lines: {missing}")

    compile_sources = (
        "scripts/check_sky130_macros.sh",
        "rtl/IntegerPLL_B2TH.v",
        "rtl/IntegerPLL_MMD_Retimer.v",
        "rtl/IntegerPLL_Divider.v",
        "rtl/IntegerPLL_DLF.v",
        "rtl/IntegerPLL_DigitalCore.v",
        "rtl/IntegerPLL_Top.v",
        "sky130/IntegerPLL_BBPD_sky130.v",
        "sky130/IntegerPLL_DCO_sky130.v",
    )
    einvp_compile_sources = (
        "scripts/check_sky130_macros.sh",
        "sky130/IntegerPLL_DCO_einvp_sky130.v",
    )
    smoke_sources = (
        "scripts/check_sky130_macros.sh",
        "rtl/IntegerPLL_B2TH.v",
        "rtl/IntegerPLL_MMD_Retimer.v",
        "rtl/IntegerPLL_Divider.v",
        "rtl/IntegerPLL_DLF.v",
        "rtl/IntegerPLL_DigitalCore.v",
        "rtl/IntegerPLL_Top.v",
        "tb/tb_sky130_top_smoke.v",
    )
    compile_mtime = compile_path.stat().st_mtime
    einvp_compile_mtime = einvp_compile_path.stat().st_mtime
    log_mtime = log_path.stat().st_mtime
    stale = []
    for relpath in compile_sources:
        source_path = require_path(root, relpath)
        if source_path.stat().st_mtime > compile_mtime:
            stale.append(f"{compile_path} is older than {source_path}")
    for relpath in einvp_compile_sources:
        source_path = require_path(root, relpath)
        if source_path.stat().st_mtime > einvp_compile_mtime:
            stale.append(f"{einvp_compile_path} is older than {source_path}")
    for relpath in smoke_sources:
        source_path = require_path(root, relpath)
        if source_path.stat().st_mtime > log_mtime:
            stale.append(f"{log_path} is older than {source_path}")
    if stale:
        raise ValueError("; ".join(stale))

    return {
        "real_sky130_wrapper_compile": str(compile_path),
        "einvp_dco_candidate_compile": str(einvp_compile_path),
        "stubbed_top_control_smoke": str(smoke_path),
        "log": str(log_path),
        "checked_dco_codes": [0, 128, 255],
        "dlf_ext_codes": [0, 512, 1020],
        "dco_therm_width": 255,
    }


def check_objective_deliverable_evidence(root):
    require_text_fragments(
        root,
        "PLL_ARCHITECTURE.md",
        (
            "self-contained architecture description",
            "integer-N",
            "8-bit exported `DCO_CODE`",
            "`REF=29.286759 MHz`",
            "polarity and gain evidence",
            "full post-layout PLL lock signoff path",
        ),
    )
    require_text_fragments(
        root,
        "rtl/IntegerPLL_DigitalCore.v",
        (
            "input wire [7:0] MMDCLKDIV_RATIO",
            "output wire [7:0] DCO_CODE",
            "output wire [254:0] DCO_THERM",
            "parameter DCO_COARSE_BITS = 0",
            "localparam integer DCO_FINE_BITS = DCO_CODE_WIDTH - DCO_COARSE_BITS",
            ".RATIO_WIDTH(8)",
            ".DCO_CODE_WIDTH(DCO_FINE_BITS)",
            ".BIN_WIDTH(8)",
            ".THERM_WIDTH(255)",
            ".INVERT_OUTPUT(DCO_THERM_INVERT)",
        ),
    )
    require_text_fragments(
        root,
        "rtl/IntegerPLL_DLF.v",
        (
            "parameter DCO_CODE_WIDTH = 8",
            "localparam integer DCO_CODE_SHIFT = CODE_WIDTH - DCO_CODE_WIDTH",
        ),
    )
    require_text_fragments(
        root,
        "rtl/IntegerPLL_HardMacroTop_EINVP.v",
        (
            "module IntegerPLL_HardMacroTop_EINVP",
            "input wire [7:0] MMDCLKDIV_RATIO",
            "output wire [7:0] DCO_CODE",
            "IntegerPLL_BBPD phase_detector",
            "IntegerPLL_DigitalCore digital_core",
            "IntegerPLL_DCO_EINVP_COARSE oscillator",
            ".COARSEBINARY_CODE(COARSEBINARY_CODE)",
            ".COARSETHERMAL_CODE(coarse_ctrl)",
            ".DCO_THERM(dco_therm)",
        ),
    )
    require_text_fragments(
        root,
        "sky130/IntegerPLL_DCO_einvp_sky130.v",
        (
            "module IntegerPLL_DCO_EINVP",
            "input wire [254:0] DCO_THERM",
            "sky130_fd_sc_hd__nand2_1 osc_gate",
            "sky130_fd_sc_hd__inv_1 ring_inv",
            "sky130_fd_sc_hd__einvp_1 tune_load",
            "for (f = 0; f < 255; f = f + 1)",
        ),
    )
    require_text_fragments(
        root,
        "sky130/IntegerPLL_DCO_einvp_coarse_sky130.v",
        (
            "module IntegerPLL_DCO_EINVP_COARSE",
            "input wire [46:0] COARSETHERMAL_CODE",
            "wire [47:0] mirror_fwd",
            "sky130_fd_sc_hs__nand2_4 osc_gate",
            "sky130_fd_sc_hs__nand2_4 mirror_forward",
            "sky130_fd_sc_hs__nand2b_4 mirror_turn",
            "sky130_fd_sc_hs__nand2b_4 mirror_return",
            "sky130_fd_sc_hs__nand2_4 mirror_merge",
            "sky130_fd_sc_hs__buf_1 out_buf",
            ".A_N(tie_lo)",
            ".A(osc_node)",
            ".A_N(mirror_ret[i+1])",
            "for (f = 0; f < 90; f = f + 1)",
            "DCO_THERM_INDEX",
            "sky130_fd_sc_hs__nand2_1 tune_load",
        ),
    )
    require_text_absent(
        root,
        "sky130/IntegerPLL_DCO_einvp_coarse_sky130.v",
        (
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
        ),
    )
    require_text_fragments(
        root,
        "sky130/IntegerPLL_BBPD_sky130.v",
        (
            "module IntegerPLL_BBPD",
            "sky130_fd_sc_hd__dfrtp_1 up_ff",
            "sky130_fd_sc_hd__dfrtp_1 dn_ff",
            "output wire [1:0] BBPD",
        ),
    )

    hardtop = check_hard_macro_top_einvp_signoff(root)
    hardtop_spice = check_hard_macro_top_einvp_spice_interface(root)
    decoder = check_decoder(root)
    dco = check_dco_einvp_postlayout_candidate(root)
    pvt = check_dco_einvp_postlayout_pvt_endpoints(root)
    mixed = check_xyce_mixed_signal_gain_sweep(root)
    nominal_low = check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_low_lock_mpi16_klu(root)
    nominal_high = check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_high_lock_mpi16_klu(root)
    pvt_locks = {
        "ff_low": check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_low_lock_mpi16_klu(root),
        "ff_high": check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_high_lock_mpi16_klu(root),
        "ss_low": check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_low_lock_mpi16_klu(root),
        "ss_high": check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_high_lock_mpi16_klu(root),
    }

    if hardtop.get("design") != "IntegerPLL_HardMacroTop_EINVP":
        raise ValueError(f"deliverable hard top is wrong: {hardtop}")
    if hardtop.get("dco_macro") != "IntegerPLL_DCO_EINVP_COARSE":
        raise ValueError(f"deliverable DCO macro is wrong: {hardtop}")
    if hardtop_spice.get("dco_therm_connections") != 255:
        raise ValueError(f"deliverable SPICE wrapper does not connect 255 DCO controls: {hardtop_spice}")
    if decoder.get("codes") != 256 or decoder.get("therm_taps_per_code") != 255:
        raise ValueError(f"deliverable decoder coverage is incomplete: {decoder}")
    if dco.get("smoke_codes") != [0, 128, 255] or dco.get("calibration_codes") != [0, 64, 128, 192, 255]:
        raise ValueError(f"deliverable DCO code coverage is incomplete: {dco}")
    if float(dco.get("smoke_span_mhz", 0.0)) < 20.0:
        raise ValueError(f"deliverable DCO span is too small: {dco}")
    for corner, details in pvt.get("spans", {}).items():
        if details.get("span_mhz", 0.0) < 5.0:
            raise ValueError(f"deliverable DCO PVT endpoint span is too small for {corner}: {details}")

    nominal_lock_errors = {
        "low_start": nominal_low["tail_abs_error_mhz"],
        "high_start": nominal_high["tail_abs_error_mhz"],
    }
    if any(error > 0.5 for error in nominal_lock_errors.values()):
        raise ValueError(f"deliverable nominal lock-window errors are too high: {nominal_lock_errors}")
    pvt_lock_errors = {
        name: details["tail_abs_error_mhz"]
        for name, details in pvt_locks.items()
    }
    if any(error > 0.5 for error in pvt_lock_errors.values()):
        raise ValueError(f"deliverable PVT lock-window errors are too high: {pvt_lock_errors}")

    return {
        "architecture_markdown": "PLL_ARCHITECTURE.md",
        "sky130_top": hardtop["design"],
        "dco_macro": hardtop["dco_macro"],
        "dco_control_bits": 8,
        "divider_ratio_bits": 8,
        "thermometer_loads": 255,
        "decoder_codes": decoder["codes"],
        "einvp_tt_freq_range_mhz": [
            dco["smoke_freq_min_mhz"],
            dco["smoke_freq_max_mhz"],
        ],
        "einvp_tt_span_mhz": dco["smoke_span_mhz"],
        "einvp_pvt_endpoint_corners": sorted(pvt["spans"]),
        "nominal_lock_tail_errors_mhz": nominal_lock_errors,
        "pvt_rail_lock_tail_errors_mhz": pvt_lock_errors,
        "mixed_signal_gain_kp_values": mixed["kp_values"],
        "mixed_signal_kp8_low_exact_hit_cycle": mixed["kp8_low_exact_hit_cycle"],
    }


def check_dco_einvp_postlayout_candidate(root):
    summary_path = require_path(
        root,
        "build/spice_dco_postlayout_einvp_check/dco_einvp_postlayout_summary.json",
    )
    smoke_csv_path = require_path(
        root,
        "build/spice_dco_postlayout_einvp_check/dco_einvp_postlayout_smoke.csv",
    )
    tail_csv_path = require_path(
        root,
        "build/spice_dco_postlayout_einvp_check/dco_einvp_postlayout_highcode_tail.csv",
    )
    mid_csv_path = require_path(
        root,
        "build/spice_dco_postlayout_einvp_check/dco_einvp_postlayout_midcode.csv",
    )
    calibration_csv_path = require_path(
        root,
        "build/spice_dco_postlayout_einvp_check/dco_einvp_postlayout_5pt_calibration.csv",
    )
    raw_smoke_csv_path = require_path(
        root,
        "build/spice_dco_postlayout_einvp_smoke_mpi4/dco_postlayout_results.csv",
    )
    raw_mid_csv_path = require_path(
        root,
        "build/spice_dco_postlayout_einvp_code064_mpi4/dco_postlayout_results.csv",
    )
    raw_tail_csv_path = require_path(
        root,
        "build/spice_dco_postlayout_einvp_highcode_tail_mpi4/dco_postlayout_results.csv",
    )
    rcx_path = require_path(
        root,
        "openlane/IntegerPLL_DCO_EINVP/runs/librelane_signoff/rcx-magic/IntegerPLL_DCO_EINVP.rcx.spice",
    )

    summary = read_json(summary_path)
    if summary.get("status") != "pass":
        raise ValueError(f"EINVP post-layout summary is not pass: {summary.get('status')}")
    if summary.get("subckt_name") != "IntegerPLL_DCO_EINVP":
        raise ValueError(f"EINVP summary has wrong subckt: {summary.get('subckt_name')}")
    if summary.get("corner") != "tt":
        raise ValueError(f"EINVP summary has wrong corner: {summary.get('corner')}")
    if summary.get("smoke_codes") != [0, 128, 255]:
        raise ValueError(f"EINVP smoke codes are {summary.get('smoke_codes')}")
    if summary.get("tail_codes") != [192, 224, 240, 248, 255]:
        raise ValueError(f"EINVP tail codes are {summary.get('tail_codes')}")
    if summary.get("mid_codes") != [64]:
        raise ValueError(f"EINVP mid calibration codes are {summary.get('mid_codes')}")
    if summary.get("calibration_codes") != [0, 64, 128, 192, 255]:
        raise ValueError(f"EINVP 5-point calibration codes are {summary.get('calibration_codes')}")

    smoke_rows = read_csv(smoke_csv_path)
    tail_rows = read_csv(tail_csv_path)
    mid_rows = read_csv(mid_csv_path)
    calibration_rows = read_csv(calibration_csv_path)
    if [to_int(row, "code") for row in smoke_rows] != [0, 128, 255]:
        raise ValueError("EINVP smoke CSV codes are not 0/128/255")
    if [to_int(row, "code") for row in tail_rows] != [192, 224, 240, 248, 255]:
        raise ValueError("EINVP tail CSV codes are not 192/224/240/248/255")
    if [to_int(row, "code") for row in mid_rows] != [64]:
        raise ValueError("EINVP mid CSV code is not 64")
    if [to_int(row, "code") for row in calibration_rows] != [0, 64, 128, 192, 255]:
        raise ValueError("EINVP calibration CSV codes are not 0/64/128/192/255")
    for label, rows, min_step in (
        ("smoke", smoke_rows, 0.03),
        ("high-tail", tail_rows, 0.005),
        ("5-point calibration", calibration_rows, 0.03),
    ):
        for row in rows:
            if row.get("subckt_name") != "IntegerPLL_DCO_EINVP":
                raise ValueError(f"EINVP {label} row has wrong subckt: {row}")
            if row.get("corner") != "tt":
                raise ValueError(f"EINVP {label} row has wrong corner: {row}")
            if to_float(row, "freq_mhz") <= 0.0 or to_float(row, "period_s") <= 0.0:
                raise ValueError(f"EINVP {label} row has invalid frequency: {row}")
        for left, right in zip(rows, rows[1:]):
            code_delta = to_int(right, "code") - to_int(left, "code")
            freq_delta = to_float(right, "freq_mhz") - to_float(left, "freq_mhz")
            step = freq_delta / code_delta
            if step < min_step:
                raise ValueError(
                    f"EINVP {label} weak/non-monotonic segment "
                    f"{left['code']}->{right['code']}: {step:g} MHz/LSB"
                )

    smoke_span = float(summary.get("smoke_span_mhz", 0.0))
    tail_span = float(summary.get("tail_span_mhz", 0.0))
    calibration_span = float(summary.get("calibration_span_mhz", 0.0))
    code64_freq = float(summary.get("code64_freq_mhz", 0.0))
    if smoke_span < 20.0:
        raise ValueError(f"EINVP smoke span is too small: {smoke_span}")
    if tail_span < 5.0:
        raise ValueError(f"EINVP high-tail span is too small: {tail_span}")
    if calibration_span < 20.0:
        raise ValueError(f"EINVP 5-point span is too small: {calibration_span}")
    if not (55.0 <= code64_freq <= 56.0):
        raise ValueError(f"EINVP code64 frequency is unexpected: {summary}")
    if not (50.0 <= float(summary.get("smoke_freq_min_mhz", 0.0)) <= 52.0):
        raise ValueError(f"EINVP smoke minimum frequency is unexpected: {summary}")
    if not (72.0 <= float(summary.get("smoke_freq_max_mhz", 0.0)) <= 73.0):
        raise ValueError(f"EINVP smoke maximum frequency is unexpected: {summary}")

    summary_mtime = min(
        summary_path.stat().st_mtime,
        smoke_csv_path.stat().st_mtime,
        tail_csv_path.stat().st_mtime,
        mid_csv_path.stat().st_mtime,
        calibration_csv_path.stat().st_mtime,
    )
    for path in (
        raw_smoke_csv_path,
        raw_mid_csv_path,
        raw_tail_csv_path,
        root / "scripts/check_dco_einvp_postlayout.py",
        root / "scripts/spice_dco_postlayout.py",
        rcx_path,
    ):
        if path.stat().st_mtime > summary_mtime:
            raise ValueError(f"EINVP post-layout summary is older than {path}")

    return {
        "subckt_name": summary["subckt_name"],
        "corner": summary["corner"],
        "smoke_codes": summary["smoke_codes"],
        "smoke_freq_min_mhz": summary["smoke_freq_min_mhz"],
        "smoke_freq_max_mhz": summary["smoke_freq_max_mhz"],
        "smoke_span_mhz": smoke_span,
        "code64_freq_mhz": code64_freq,
        "calibration_codes": summary["calibration_codes"],
        "calibration_span_mhz": calibration_span,
        "tail_codes": summary["tail_codes"],
        "tail_span_mhz": tail_span,
        "summary": str(summary_path),
        "rcx_netlist": str(rcx_path),
    }


def check_dco_einvp_postlayout_pvt_endpoints(root):
    rcx_path = require_path(
        root,
        "openlane/IntegerPLL_DCO_EINVP/runs/librelane_signoff/rcx-magic/IntegerPLL_DCO_EINVP.rcx.spice",
    )
    relpaths = {
        "ff": "build/spice_dco_postlayout_einvp_pvt_ff_endpoints_mpi4/dco_postlayout_results.csv",
        "fs": "build/spice_dco_postlayout_einvp_pvt_fs_endpoints_mpi4/dco_postlayout_results.csv",
        "sf": "build/spice_dco_postlayout_einvp_pvt_sf_endpoints_mpi4/dco_postlayout_results.csv",
        "ss": "build/spice_dco_postlayout_einvp_pvt_ss_endpoints_mpi4/dco_postlayout_results.csv",
    }
    spans = {}
    total_elapsed_s = 0.0
    for corner, relpath in relpaths.items():
        csv_path = require_path(root, relpath)
        rows = sorted(read_csv(csv_path), key=lambda row: to_int(row, "code"))
        if [to_int(row, "code") for row in rows] != [0, 255]:
            raise ValueError(f"EINVP {corner} PVT endpoint CSV has wrong codes: {rows}")
        freqs = []
        for row in rows:
            if row.get("status") != "pass" or row.get("timed_out") != "no":
                raise ValueError(f"EINVP {corner} PVT endpoint row did not pass: {row}")
            if row.get("simulator") != "xyce" or to_int(row, "xyce_mpi_procs") != 4:
                raise ValueError(f"EINVP {corner} PVT endpoint row has wrong simulator/MPI setting: {row}")
            if row.get("corner") != corner or row.get("subckt_name") != "IntegerPLL_DCO_EINVP":
                raise ValueError(f"EINVP {corner} PVT endpoint row has wrong identity: {row}")
            code = to_int(row, "code")
            enabled_loads = to_int(row, "enabled_loads")
            expected_loads = 255 - code if to_int(row, "therm_invert") else code
            if enabled_loads != expected_loads:
                raise ValueError(f"EINVP {corner} code {code} has wrong load count: {row}")
            freq_mhz = to_float(row, "freq_mhz")
            if freq_mhz <= 0.0 or to_float(row, "period_s") <= 0.0:
                raise ValueError(f"EINVP {corner} PVT endpoint row has invalid frequency: {row}")
            freqs.append(freq_mhz)
            if row.get("elapsed_s", "") != "":
                total_elapsed_s += to_float(row, "elapsed_s")

            log_path = Path(row.get("log", "")).expanduser()
            if not log_path.is_file():
                raise ValueError(f"EINVP {corner} PVT endpoint row missing Xyce log: {row}")
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
            if "Timing summary of 4 processors" not in log_text:
                raise ValueError(f"EINVP {corner} PVT endpoint log does not record MPI4 timing: {log_path}")

        span_mhz = freqs[1] - freqs[0]
        if span_mhz < 5.0:
            raise ValueError(f"EINVP {corner} PVT endpoint span is too small: {span_mhz}")
        spans[corner] = {
            "freq_min_mhz": freqs[0],
            "freq_max_mhz": freqs[1],
            "span_mhz": span_mhz,
            "avg_step_mhz_per_lsb": span_mhz / 255.0,
        }
        for source in (
            root / "scripts/spice_dco_postlayout.py",
            rcx_path,
        ):
            if source.stat().st_mtime > csv_path.stat().st_mtime:
                raise ValueError(f"EINVP {corner} PVT endpoint CSV is older than {source}")

    return {
        "subckt_name": "IntegerPLL_DCO_EINVP",
        "corners": list(relpaths),
        "codes": [0, 255],
        "spans": spans,
        "total_elapsed_s": total_elapsed_s,
    }


def check_top_macro_assembly(root):
    summary_path = require_path(root, "build/top_macro_assembly/top_macro_assembly_summary.json")
    csv_path = require_path(root, "build/top_macro_assembly/top_macro_assembly_summary.csv")
    summary = read_json(summary_path)

    if summary.get("status") != "pass":
        raise ValueError(f"top macro assembly summary is not pass: {summary.get('status')}")
    if summary.get("macro_count") != 3:
        raise ValueError(f"top macro assembly macro count is {summary.get('macro_count')}")
    if abs(float(summary.get("total_macro_area_um2", 0.0)) - 306900.0) > 1e-6:
        raise ValueError(f"top macro assembly area is unexpected: {summary.get('total_macro_area_um2')}")

    macros = {row.get("block"): row for row in summary.get("macros", [])}
    expected = {
        "IntegerPLL_DigitalCore": {
            "size_um": [300.0, 300.0],
            "input_pins": 46,
            "output_pins": 362,
            "power_body_pins": 2,
            "total_pins": 410,
        },
        "IntegerPLL_DCO": {
            "size_um": [450.0, 450.0],
            "input_pins": 256,
            "output_pins": 1,
            "power_body_pins": 4,
            "total_pins": 261,
        },
        "IntegerPLL_BBPD": {
            "size_um": [120.0, 120.0],
            "input_pins": 3,
            "output_pins": 2,
            "power_body_pins": 4,
            "total_pins": 9,
        },
    }
    if set(macros) != set(expected):
        raise ValueError(f"top macro assembly blocks are {sorted(macros)}")

    for block, fields in expected.items():
        row = macros[block]
        if [float(value) for value in row.get("size_um", [])] != fields["size_um"]:
            raise ValueError(f"{block} size is {row.get('size_um')}")
        for key in ("input_pins", "output_pins", "power_body_pins", "total_pins"):
            if int(row.get(key, -1)) != fields[key]:
                raise ValueError(f"{block} {key} is {row.get(key)}")
        for key in ("lef", "gds", "def", "netlist", "sdc", "source"):
            path = Path(row.get(key, "")).expanduser()
            if not path.is_file():
                raise ValueError(f"{block} missing recorded {key}: {path}")

    expected_routes = {
        "bbpd_to_digital": "BBPD[1:0]",
        "digital_to_dco": "DCO_THERM[254:0]",
        "dco_to_digital_feedback": "PLLOUT",
        "digital_to_bbpd_feedback": "CLKDIV_RETIMED",
    }
    if summary.get("key_routes") != expected_routes:
        raise ValueError(f"top macro assembly routes are {summary.get('key_routes')}")

    checked_interconnects = summary.get("top_interconnect", {}).get("checked_interconnects", [])
    for needle in (
        "IntegerPLL_BBPD phase_detector",
        "IntegerPLL_DigitalCore #(",
        "IntegerPLL_DCO oscillator",
        ".DCO_THERM(dco_therm)",
    ):
        if needle not in checked_interconnects:
            raise ValueError(f"top macro assembly did not check interconnect {needle!r}")

    summary_mtime = min(summary_path.stat().st_mtime, csv_path.stat().st_mtime)
    for path_text in summary.get("source_files", []):
        path = Path(path_text).expanduser()
        if not path.is_file():
            raise ValueError(f"top macro assembly recorded missing source: {path}")
        if path.stat().st_mtime > summary_mtime:
            raise ValueError(f"top macro assembly summary is older than {path}")

    return {
        "macro_count": summary["macro_count"],
        "total_macro_area_um2": summary["total_macro_area_um2"],
        "digital_pins": macros["IntegerPLL_DigitalCore"]["total_pins"],
        "dco_pins": macros["IntegerPLL_DCO"]["total_pins"],
        "bbpd_pins": macros["IntegerPLL_BBPD"]["total_pins"],
        "summary": str(summary_path),
    }


def check_hard_macro_top(root):
    summary_path = require_path(root, "build/hard_macro_top/hard_macro_top_summary.json")
    csv_path = require_path(root, "build/hard_macro_top/hard_macro_top_placements.csv")
    summary = read_json(summary_path)

    if summary.get("status") != "pass":
        raise ValueError(f"hard macro top summary is not pass: {summary.get('status')}")
    config = summary.get("config", {})
    route = summary.get("route", {})
    if route.get("status") != "pass":
        raise ValueError(f"hard macro top route status is {route.get('status')}")
    if config.get("macro_count") != 3:
        raise ValueError(f"hard macro top macro count is {config.get('macro_count')}")
    if abs(float(config.get("total_macro_area_um2", 0.0)) - 306900.0) > 1e-6:
        raise ValueError(f"hard macro top macro area is {config.get('total_macro_area_um2')}")
    if float(config.get("dco_to_digital_channel_um", 0.0)) < 100.0:
        raise ValueError("hard macro top DCO-to-digital channel is too small")
    if float(config.get("bbpd_to_digital_channel_um", 0.0)) < 20.0:
        raise ValueError("hard macro top BBPD-to-digital channel is too small")

    expected_locations = {
        "phase_detector": ("IntegerPLL_BBPD", [315.0, 40.0]),
        "digital_core": ("IntegerPLL_DigitalCore", [235.0, 180.0]),
        "oscillator": ("IntegerPLL_DCO", [160.0, 620.0]),
    }
    rows = read_csv(csv_path)
    if len(rows) != 3:
        raise ValueError(f"hard macro top placement CSV has {len(rows)} rows")
    rows_by_instance = {row["instance"]: row for row in rows}
    if set(rows_by_instance) != set(expected_locations):
        raise ValueError(f"hard macro top placement instances are {sorted(rows_by_instance)}")
    for instance, (macro, location) in expected_locations.items():
        row = rows_by_instance[instance]
        if row["macro"] != macro:
            raise ValueError(f"{instance} macro is {row['macro']}")
        if [to_float(row, "x_um"), to_float(row, "y_um")] != location:
            raise ValueError(f"{instance} location is {[row['x_um'], row['y_um']]}")
        if row["orientation"] != "N":
            raise ValueError(f"{instance} orientation is {row['orientation']}")

    route_views = route.get("route_views", {})
    for relkey in (
        "final/def/IntegerPLL_HardMacroTop.def",
        "final/odb/IntegerPLL_HardMacroTop.odb",
        "final/nl/IntegerPLL_HardMacroTop.nl.v",
        "final/pnl/IntegerPLL_HardMacroTop.pnl.v",
        "final/sdc/IntegerPLL_HardMacroTop.sdc",
        "final/metrics.json",
        "detailed_route_log",
    ):
        path = Path(route_views.get(relkey, "")).expanduser()
        if not path.is_file():
            raise ValueError(f"hard macro top route view missing: {relkey} -> {path}")

    expected_power_connections = {
        "VPWR": ["phase_detector/VPWR", "digital_core/VPWR", "oscillator/VPWR"],
        "VGND": ["phase_detector/VGND", "digital_core/VGND", "oscillator/VGND"],
        "VPB": ["phase_detector/VPB", "oscillator/VPB"],
        "VNB": ["phase_detector/VNB", "oscillator/VNB"],
    }
    if route.get("power_connections") != expected_power_connections:
        raise ValueError(f"hard macro top power connections are {route.get('power_connections')}")

    routes = summary.get("key_routes", {})
    for key in (
        "bbpd_to_digital",
        "digital_to_dco",
        "dco_to_digital_feedback",
        "digital_to_bbpd_feedback",
        "body_bias",
    ):
        if key not in routes:
            raise ValueError(f"hard macro top missing key route {key}")

    summary_mtime = min(summary_path.stat().st_mtime, csv_path.stat().st_mtime)
    for path_text in sorted(set(config.get("source_files", []) + route.get("source_files", []))):
        path = Path(path_text).expanduser()
        if not path.is_file():
            raise ValueError(f"hard macro top recorded missing source: {path}")
        if path.stat().st_mtime > summary_mtime:
            raise ValueError(f"hard macro top summary is older than {path}")

    return {
        "macro_count": config["macro_count"],
        "total_macro_area_um2": config["total_macro_area_um2"],
        "dco_to_digital_channel_um": config["dco_to_digital_channel_um"],
        "bbpd_to_digital_channel_um": config["bbpd_to_digital_channel_um"],
        "stdcells": route.get("stdcells"),
        "macros": route.get("macros"),
        "wirelength": route.get("wirelength"),
        "vias": route.get("vias"),
        "summary": str(summary_path),
    }


def check_hard_macro_top_signoff(root):
    summary_path = require_path(root, "build/hard_macro_top/hard_macro_top_summary.json")
    csv_path = require_path(root, "build/hard_macro_top/hard_macro_top_placements.csv")
    summary = read_json(summary_path)

    if summary.get("status") != "pass":
        raise ValueError(f"hard macro top summary is not pass: {summary.get('status')}")
    signoff = summary.get("signoff", {})
    if signoff.get("status") != "pass":
        raise ValueError(f"hard macro top signoff status is {signoff.get('status')}")
    if signoff.get("macros") != 3:
        raise ValueError(f"hard macro top signoff macro count is {signoff.get('macros')}")

    signoff_views = signoff.get("signoff_views", {})
    required_views = (
        "final/def/IntegerPLL_HardMacroTop.def",
        "final/gds/IntegerPLL_HardMacroTop.gds",
        "final/klayout_gds/IntegerPLL_HardMacroTop.klayout.gds",
        "final/lef/IntegerPLL_HardMacroTop.lef",
        "final/mag/IntegerPLL_HardMacroTop.mag",
        "final/mag_gds/IntegerPLL_HardMacroTop.magic.gds",
        "final/nl/IntegerPLL_HardMacroTop.nl.v",
        "final/odb/IntegerPLL_HardMacroTop.odb",
        "final/pnl/IntegerPLL_HardMacroTop.pnl.v",
        "final/sdc/IntegerPLL_HardMacroTop.sdc",
        "final/sdf/nom_ff_n40C_1v95/IntegerPLL_HardMacroTop__nom_ff_n40C_1v95.sdf",
        "final/sdf/nom_ss_100C_1v60/IntegerPLL_HardMacroTop__nom_ss_100C_1v60.sdf",
        "final/sdf/nom_tt_025C_1v80/IntegerPLL_HardMacroTop__nom_tt_025C_1v80.sdf",
        "final/spef/max/IntegerPLL_HardMacroTop.max.spef",
        "final/spef/min/IntegerPLL_HardMacroTop.min.spef",
        "final/spef/nom/IntegerPLL_HardMacroTop.nom.spef",
        "final/spice/IntegerPLL_HardMacroTop.spice",
        "final/vh/IntegerPLL_HardMacroTop.vh",
        "final/json_h/IntegerPLL_HardMacroTop.h.json",
        "final/render/IntegerPLL_HardMacroTop.png",
        "final/metrics.csv",
        "final/metrics.json",
        "log/41-openroad-detailedrouting/openroad-detailedrouting.log",
        "log/51-openroad-rcx/max/rcx.log",
        "log/51-openroad-rcx/min/rcx.log",
        "log/51-openroad-rcx/nom/rcx.log",
        "log/57-klayout-xor/klayout-xor.log",
        "log/59-magic-drc/magic-drc.log",
        "log/60-klayout-drc/klayout-drc.log",
        "log/63-magic-spiceextraction/magic-spiceextraction.log",
        "log/65-netgen-lvs/netgen-lvs.log",
    )
    for relkey in required_views:
        path = Path(signoff_views.get(relkey, "")).expanduser()
        if not path.is_file():
            raise ValueError(f"hard macro top signoff view missing: {relkey} -> {path}")

    metrics_path = Path(signoff_views["final/metrics.json"]).expanduser()
    metrics = read_json(metrics_path)
    metric_failures = []
    for key in ZERO_METRICS:
        if key not in metrics:
            metric_failures.append(f"missing {key}")
        elif not is_zero(metrics[key]):
            metric_failures.append(f"{key}={metrics[key]}")
    if metric_failures:
        raise ValueError("; ".join(metric_failures))

    expected_power_connections = {
        "VPWR": ["phase_detector/VPWR", "digital_core/VPWR", "oscillator/VPWR"],
        "VGND": ["phase_detector/VGND", "digital_core/VGND", "oscillator/VGND"],
        "VPB": ["phase_detector/VPB", "oscillator/VPB"],
        "VNB": ["phase_detector/VNB", "oscillator/VNB"],
    }
    if signoff.get("power_connections") != expected_power_connections:
        raise ValueError(f"hard macro top signoff power connections are {signoff.get('power_connections')}")

    summary_mtime = min(summary_path.stat().st_mtime, csv_path.stat().st_mtime)
    source_files = summary.get("config", {}).get("source_files", []) + signoff.get("source_files", [])
    for path_text in sorted(set(source_files)):
        path = Path(path_text).expanduser()
        if not path.is_file():
            raise ValueError(f"hard macro top signoff recorded missing source: {path}")
        if path.stat().st_mtime > summary_mtime:
            raise ValueError(f"hard macro top signoff summary is older than {path}")

    return {
        "stdcells": signoff.get("stdcells"),
        "macros": signoff.get("macros"),
        "wirelength": signoff.get("wirelength"),
        "vias": signoff.get("vias"),
        "spef_corners": signoff.get("spef_corners"),
        "signoff_checks": signoff.get("signoff_checks"),
        "metrics": str(metrics_path),
    }


def check_hard_macro_top_spice_interface(root):
    summary_path = require_path(root, "build/hard_macro_top_spice/hard_macro_top_spice_summary.json")
    summary = read_json(summary_path)
    if summary.get("status") != "pass":
        raise ValueError(f"hard macro top SPICE summary is not pass: {summary.get('status')}")
    if summary.get("top_port_count") != 71:
        raise ValueError(f"hard macro top SPICE port count is {summary.get('top_port_count')}")
    if summary.get("bbpd_ports") != 9:
        raise ValueError(f"hard macro top BBPD SPICE port count is {summary.get('bbpd_ports')}")
    if summary.get("digital_core_ports") != 410:
        raise ValueError(f"hard macro top digital SPICE port count is {summary.get('digital_core_ports')}")
    if summary.get("dco_ports") != 261:
        raise ValueError(f"hard macro top DCO SPICE port count is {summary.get('dco_ports')}")
    if summary.get("dco_therm_connections") != 255:
        raise ValueError(f"hard macro top DCO thermometer connections are {summary.get('dco_therm_connections')}")
    if int(summary.get("antenna_dco_therm_connections", 0)) < 16:
        raise ValueError("hard macro top SPICE did not preserve antenna-repaired DCO thermometer nets")
    if int(summary.get("spef_d_nets", 0)) < 300:
        raise ValueError(f"hard macro top SPEF has too few nets: {summary.get('spef_d_nets')}")
    if int(summary.get("spef_cap_entries", 0)) < 9000:
        raise ValueError(f"hard macro top SPEF has too few cap entries: {summary.get('spef_cap_entries')}")
    if int(summary.get("spef_res_entries", 0)) < 1500:
        raise ValueError(f"hard macro top SPEF has too few resistor entries: {summary.get('spef_res_entries')}")

    xyce = summary.get("xyce_norun", {})
    if xyce.get("returncode") != 0:
        raise ValueError(f"hard macro top Xyce -norun return code is {xyce.get('returncode')}")
    log_path = Path(xyce.get("log", "")).expanduser()
    if not log_path.is_file():
        raise ValueError(f"hard macro top Xyce -norun log missing: {log_path}")
    if "Syntax and topology analysis complete" not in log_path.read_text(encoding="utf-8", errors="replace"):
        raise ValueError(f"hard macro top Xyce -norun log did not complete topology analysis: {log_path}")

    generated_deck = Path(summary.get("generated_deck", "")).expanduser()
    if not generated_deck.is_file():
        raise ValueError(f"hard macro top generated SPICE probe missing: {generated_deck}")

    summary_mtime = summary_path.stat().st_mtime
    for path_text in summary.get("source_files", []):
        path = Path(path_text).expanduser()
        if not path.is_file():
            raise ValueError(f"hard macro top SPICE recorded missing source: {path}")
        if path.stat().st_mtime > summary_mtime:
            raise ValueError(f"hard macro top SPICE summary is older than {path}")

    return {
        "top_port_count": summary["top_port_count"],
        "dco_therm_connections": summary["dco_therm_connections"],
        "antenna_dco_therm_connections": summary["antenna_dco_therm_connections"],
        "spef_d_nets": summary["spef_d_nets"],
        "spef_cap_entries": summary["spef_cap_entries"],
        "spef_res_entries": summary["spef_res_entries"],
        "xyce_norun": xyce.get("command"),
        "summary": str(summary_path),
    }


def check_hard_macro_top_einvp_signoff(root):
    summary_path = require_path(root, "build/hard_macro_top_einvp/hard_macro_top_einvp_summary.json")
    csv_path = require_path(root, "build/hard_macro_top_einvp/hard_macro_top_einvp_placements.csv")
    summary = read_json(summary_path)

    if summary.get("status") != "pass":
        raise ValueError(f"EINVP hard macro top summary is not pass: {summary.get('status')}")
    if summary.get("design") != "IntegerPLL_HardMacroTop_EINVP":
        raise ValueError(f"EINVP hard macro top design is {summary.get('design')}")
    if summary.get("dco_macro") != "IntegerPLL_DCO_EINVP_COARSE":
        raise ValueError(f"EINVP hard macro top DCO macro is {summary.get('dco_macro')}")

    config = summary.get("config", {})
    if config.get("macro_count") != 3:
        raise ValueError(f"EINVP hard macro top configured macro count is {config.get('macro_count')}")

    expected_rows = {
        "phase_detector": ("IntegerPLL_BBPD", 315.0, 40.0, 120.0, 120.0, "N"),
        "digital_core": ("IntegerPLL_DigitalCore", 235.0, 180.0, 300.0, 300.0, "N"),
        "oscillator": ("IntegerPLL_DCO_EINVP_COARSE", 160.0, 620.0, 260.0, 260.0, "N"),
    }
    rows = {row["instance"]: row for row in read_csv(csv_path)}
    if set(rows) != set(expected_rows):
        raise ValueError(f"EINVP hard macro top placement instances are {sorted(rows)}")
    for instance, (macro, x_um, y_um, width_um, height_um, orientation) in expected_rows.items():
        row = rows[instance]
        if row.get("macro") != macro:
            raise ValueError(f"{instance} macro is {row.get('macro')}")
        if row.get("orientation") != orientation:
            raise ValueError(f"{instance} orientation is {row.get('orientation')}")
        actual = (
            float(row["x_um"]),
            float(row["y_um"]),
            float(row["width_um"]),
            float(row["height_um"]),
        )
        if actual != (x_um, y_um, width_um, height_um):
            raise ValueError(f"{instance} placement/size is {actual}")

    signoff = summary.get("signoff", {})
    if signoff.get("status") != "pass":
        raise ValueError(f"EINVP hard macro top signoff status is {signoff.get('status')}")
    if int(signoff.get("stdcells", 0)) < 7000:
        raise ValueError(f"EINVP hard macro top stdcell count is {signoff.get('stdcells')}")
    if int(signoff.get("wirelength", 0)) < 150000:
        raise ValueError(f"EINVP hard macro top wirelength is {signoff.get('wirelength')}")
    if int(signoff.get("vias", 0)) < 1500:
        raise ValueError(f"EINVP hard macro top via count is {signoff.get('vias')}")

    placements = {row["instance"]: row for row in signoff.get("placements", [])}
    oscillator = placements.get("oscillator", {})
    if oscillator.get("macro") != "IntegerPLL_DCO_EINVP_COARSE" or oscillator.get("master") != "IntegerPLL_DCO_EINVP_COARSE":
        raise ValueError(f"EINVP hard macro top oscillator placement is {oscillator}")
    if oscillator.get("location_um") != [160.0, 620.0] or oscillator.get("orientation") != "N":
        raise ValueError(f"EINVP hard macro top oscillator placed unexpectedly: {oscillator}")

    views = signoff.get("views", {})
    required_views = (
        "final/def/IntegerPLL_HardMacroTop_EINVP.def",
        "final/gds/IntegerPLL_HardMacroTop_EINVP.gds",
        "final/lef/IntegerPLL_HardMacroTop_EINVP.lef",
        "final/metrics.json",
        "final/nl/IntegerPLL_HardMacroTop_EINVP.nl.v",
        "final/odb/IntegerPLL_HardMacroTop_EINVP.odb",
        "final/pnl/IntegerPLL_HardMacroTop_EINVP.pnl.v",
        "final/sdc/IntegerPLL_HardMacroTop_EINVP.sdc",
        "final/spef/nom/IntegerPLL_HardMacroTop_EINVP.nom.spef",
        "final/spice/IntegerPLL_HardMacroTop_EINVP.spice",
    )
    for relkey in required_views:
        path = Path(views.get(relkey, "")).expanduser()
        if not path.is_file():
            raise ValueError(f"EINVP hard macro top signoff view missing: {relkey} -> {path}")

    metrics_path = Path(views["final/metrics.json"]).expanduser()
    metrics = read_json(metrics_path)
    metric_failures = []
    for key in ZERO_METRICS:
        if key not in metrics:
            metric_failures.append(f"missing {key}")
        elif not is_zero(metrics[key]):
            metric_failures.append(f"{key}={metrics[key]}")
    if metric_failures:
        raise ValueError("; ".join(metric_failures))

    netlist_path = Path(views["final/nl/IntegerPLL_HardMacroTop_EINVP.nl.v"]).expanduser()
    netlist = netlist_path.read_text(encoding="ascii", errors="replace")
    if "IntegerPLL_DCO_EINVP_COARSE oscillator" not in netlist:
        raise ValueError("EINVP hard macro top netlist does not instantiate IntegerPLL_DCO_EINVP_COARSE oscillator")
    if "IntegerPLL_DCO oscillator" in netlist:
        raise ValueError("EINVP hard macro top netlist still instantiates the NAND-load DCO")

    summary_mtime = min(summary_path.stat().st_mtime, csv_path.stat().st_mtime)
    stale_inputs = list(config.get("source_files", [])) + [views[key] for key in required_views]
    for path_text in sorted(set(stale_inputs)):
        path = Path(path_text).expanduser()
        if not path.is_file():
            raise ValueError(f"EINVP hard macro top recorded missing source: {path}")
        if path.stat().st_mtime > summary_mtime:
            raise ValueError(f"EINVP hard macro top summary is older than {path}")

    return {
        "design": summary["design"],
        "dco_macro": summary["dco_macro"],
        "stdcells": signoff.get("stdcells"),
        "wirelength": signoff.get("wirelength"),
        "vias": signoff.get("vias"),
        "summary": str(summary_path),
    }


def check_hard_macro_top_einvp_spice_interface(root):
    summary_path = require_path(root, "build/hard_macro_top_einvp_spice/hard_macro_top_spice_summary.json")
    summary = read_json(summary_path)
    if summary.get("status") != "pass":
        raise ValueError(f"EINVP hard macro top SPICE summary is not pass: {summary.get('status')}")
    if summary.get("top") != "IntegerPLL_HardMacroTop_EINVP":
        raise ValueError(f"EINVP hard macro top SPICE top is {summary.get('top')}")
    if summary.get("dco_subckt") != "IntegerPLL_DCO_EINVP_COARSE":
        raise ValueError(f"EINVP hard macro top SPICE DCO subckt is {summary.get('dco_subckt')}")
    if summary.get("top_port_count") != 71:
        raise ValueError(f"EINVP hard macro top SPICE port count is {summary.get('top_port_count')}")
    if summary.get("bbpd_ports") != 9:
        raise ValueError(f"EINVP hard macro top BBPD SPICE port count is {summary.get('bbpd_ports')}")
    if summary.get("digital_core_ports") != 410:
        raise ValueError(f"EINVP hard macro top digital SPICE port count is {summary.get('digital_core_ports')}")
    if summary.get("dco_ports") != 265:
        raise ValueError(f"EINVP hard macro top DCO SPICE port count is {summary.get('dco_ports')}")
    if summary.get("dco_therm_connections") != 255:
        raise ValueError(f"EINVP hard macro top DCO thermometer connections are {summary.get('dco_therm_connections')}")
    if int(summary.get("antenna_dco_therm_connections", 0)) < 16:
        raise ValueError("EINVP hard macro top SPICE did not preserve antenna-repaired DCO thermometer nets")
    if int(summary.get("spef_d_nets", 0)) < 300:
        raise ValueError(f"EINVP hard macro top SPEF has too few nets: {summary.get('spef_d_nets')}")
    if int(summary.get("spef_cap_entries", 0)) < 9000:
        raise ValueError(f"EINVP hard macro top SPEF has too few cap entries: {summary.get('spef_cap_entries')}")
    if int(summary.get("spef_res_entries", 0)) < 1500:
        raise ValueError(f"EINVP hard macro top SPEF has too few resistor entries: {summary.get('spef_res_entries')}")

    xyce = summary.get("xyce_norun", {})
    if xyce.get("returncode") != 0:
        raise ValueError(f"EINVP hard macro top Xyce -norun return code is {xyce.get('returncode')}")
    log_path = Path(xyce.get("log", "")).expanduser()
    if not log_path.is_file():
        raise ValueError(f"EINVP hard macro top Xyce -norun log missing: {log_path}")
    if "Syntax and topology analysis complete" not in log_path.read_text(encoding="utf-8", errors="replace"):
        raise ValueError(f"EINVP hard macro top Xyce -norun log did not complete topology analysis: {log_path}")

    generated_deck = Path(summary.get("generated_deck", "")).expanduser()
    if not generated_deck.is_file():
        raise ValueError(f"EINVP hard macro top generated SPICE probe missing: {generated_deck}")

    for key in ("spice", "spef", "metrics"):
        path = Path(summary.get(key, "")).expanduser()
        if not path.is_file():
            raise ValueError(f"EINVP hard macro top SPICE {key} artifact missing: {path}")

    summary_mtime = summary_path.stat().st_mtime
    for path_text in summary.get("source_files", []):
        path = Path(path_text).expanduser()
        if not path.is_file():
            raise ValueError(f"EINVP hard macro top SPICE recorded missing source: {path}")
        if path.stat().st_mtime > summary_mtime:
            raise ValueError(f"EINVP hard macro top SPICE summary is older than {path}")

    return {
        "top": summary["top"],
        "dco_subckt": summary["dco_subckt"],
        "top_port_count": summary["top_port_count"],
        "dco_therm_connections": summary["dco_therm_connections"],
        "antenna_dco_therm_connections": summary["antenna_dco_therm_connections"],
        "spef_d_nets": summary["spef_d_nets"],
        "spef_cap_entries": summary["spef_cap_entries"],
        "spef_res_entries": summary["spef_res_entries"],
        "xyce_norun": xyce.get("command"),
        "summary": str(summary_path),
    }


def check_dco_summaries(root):
    tt_summary = read_json(require_path(root, "build/spice_dco_all_check/dco_sweep_summary.json"))
    if tt_summary.get("status") != "pass":
        raise ValueError("TT DCO sweep summary is not pass")
    if tt_summary.get("corners") != ["tt"]:
        raise ValueError(f"TT DCO sweep corners are {tt_summary.get('corners')}")
    if tt_summary.get("codes_per_corner") != 256 or tt_summary.get("total_rows_checked") != 256:
        raise ValueError(f"TT DCO sweep coverage is wrong: {tt_summary}")
    if float(tt_summary["global_span_mhz"]) < 30.0:
        raise ValueError(f"TT DCO span is too small: {tt_summary['global_span_mhz']} MHz")

    tt_rows = read_csv(require_path(root, "build/spice_dco_all_check/dco_sweep_summary.csv"))
    if len(tt_rows) != 1:
        raise ValueError("TT DCO summary should have one row")
    if to_float(tt_rows[0], "min_adjacent_step_mhz") < 0.05:
        raise ValueError("TT DCO minimum adjacent step is below 0.05 MHz")

    pvt_summary = read_json(require_path(root, "build/spice_dco_pvt_all_check/dco_sweep_summary.json"))
    if pvt_summary.get("status") != "pass":
        raise ValueError("PVT DCO sweep summary is not pass")
    if pvt_summary.get("corners") != list(EXPECTED_CORNERS):
        raise ValueError(f"PVT DCO corners are {pvt_summary.get('corners')}")
    if pvt_summary.get("codes_per_corner") != 256 or pvt_summary.get("total_rows_checked") != 1280:
        raise ValueError(f"PVT DCO sweep coverage is wrong: {pvt_summary}")

    pvt_rows = read_csv(require_path(root, "build/spice_dco_pvt_all_check/dco_sweep_summary.csv"))
    if {row["corner"] for row in pvt_rows} != set(EXPECTED_CORNERS):
        raise ValueError("PVT DCO summary rows do not cover all expected corners")
    for row in pvt_rows:
        if to_int(row, "codes_checked") != 256:
            raise ValueError(f"{row['corner']} does not cover 256 codes")
        if to_float(row, "span_mhz") < 20.0:
            raise ValueError(f"{row['corner']} DCO span is below 20 MHz")
        if to_float(row, "min_adjacent_step_mhz") < 0.05:
            raise ValueError(f"{row['corner']} minimum step is below 0.05 MHz")
        if to_int(row, "therm_invert") != 1:
            raise ValueError(f"{row['corner']} has unexpected therm_invert={row['therm_invert']}")

    return {
        "tt_span_mhz": tt_summary["global_span_mhz"],
        "tt_freq_min_mhz": tt_summary["global_freq_min_mhz"],
        "tt_freq_max_mhz": tt_summary["global_freq_max_mhz"],
        "pvt_span_mhz": pvt_summary["global_span_mhz"],
        "pvt_freq_min_mhz": pvt_summary["global_freq_min_mhz"],
        "pvt_freq_max_mhz": pvt_summary["global_freq_max_mhz"],
    }


def check_decoder(root):
    rows = read_csv(require_path(root, "build/spice_decoder_all_taps/dco_decoder_check.csv"))
    if len(rows) != 256:
        raise ValueError(f"decoder coverage has {len(rows)} rows, expected 256")
    require_all_pass(rows)
    for row in rows:
        code = to_int(row, "code")
        if to_int(row, "expected_checked_high") != 255 - code:
            raise ValueError(f"decoder expected high mismatch for code {code}")
        if to_int(row, "measured_checked_high") != 255 - code:
            raise ValueError(f"decoder measured high mismatch for code {code}")
        if row.get("therm_errors", "") not in ("", "0"):
            raise ValueError(f"decoder therm_errors for code {code}: {row['therm_errors']}")
    return {"codes": len(rows), "therm_taps_per_code": 255}


def check_filled_dco(root):
    summary = read_json(
        require_path(
            root,
            "build/spice_dco_postlayout_filled_calibration/filled_dco_calibration_summary.json",
        )
    )
    if summary.get("status") != "pass":
        raise ValueError("filled DCO calibration summary is not pass")
    if summary.get("codes") != [0, 64, 128, 192, 255]:
        raise ValueError(f"filled DCO calibration codes are {summary.get('codes')}")
    if float(summary["span_mhz"]) < 5.0:
        raise ValueError("filled DCO five-point span is below 5 MHz")
    if float(summary["min_segment_step_mhz_per_lsb"]) <= 0.005:
        raise ValueError("filled DCO minimum segment step is too small")

    rows = read_csv(
        require_path(root, "build/spice_dco_postlayout_filled_calibration/filled_dco_calibration.csv")
    )
    if [to_int(row, "code") for row in rows] != [0, 64, 128, 192, 255]:
        raise ValueError("filled DCO calibration CSV has unexpected code order")
    freqs = [to_float(row, "freq_mhz") for row in rows]
    if any(right <= left for left, right in zip(freqs, freqs[1:])):
        raise ValueError("filled DCO calibration frequencies are not strictly increasing")
    return {
        "codes": summary["codes"],
        "freq_min_mhz": summary["freq_min_mhz"],
        "freq_max_mhz": summary["freq_max_mhz"],
        "span_mhz": summary["span_mhz"],
        "avg_step_mhz_per_lsb": summary["avg_step_mhz_per_lsb"],
    }


def check_filled_dco_tt_9pt(root):
    summary = read_json(
        require_path(
            root,
            "build/spice_dco_postlayout_filled_tt_9pt_check/filled_dco_tt_9pt_summary.json",
        )
    )
    if summary.get("status") != "pass":
        raise ValueError("filled DCO TT 9-point summary is not pass")
    if summary.get("corner") != "tt":
        raise ValueError(f"filled DCO TT 9-point corner is {summary.get('corner')}")
    expected_codes = [0, 32, 64, 96, 128, 160, 192, 224, 255]
    if summary.get("codes") != expected_codes:
        raise ValueError(f"filled DCO TT 9-point codes are {summary.get('codes')}")
    if float(summary["endpoint_span_mhz"]) < 5.0:
        raise ValueError("filled DCO TT 9-point endpoint span is below 5 MHz")
    if float(summary["peak_span_mhz"]) < 6.0:
        raise ValueError("filled DCO TT 9-point peak span is below 6 MHz")
    min_step = float(summary["min_positive_segment_step_mhz_per_lsb"])
    max_step = float(summary["max_positive_segment_step_mhz_per_lsb"])
    if min_step < 0.02:
        raise ValueError(f"filled DCO TT 9-point positive minimum step is too small: {min_step}")
    if max_step > 0.04:
        raise ValueError(f"filled DCO TT 9-point positive maximum step is too large: {max_step}")

    negative_segments = summary.get("negative_segments", [])
    if len(negative_segments) > 1:
        raise ValueError(f"filled DCO TT 9-point has too many negative segments: {negative_segments}")
    for segment in negative_segments:
        if int(segment["from_code"]) < 224:
            raise ValueError(f"filled DCO TT 9-point negative segment is before high tail: {segment}")
        if float(segment["rolloff_mhz"]) > 0.5:
            raise ValueError(f"filled DCO TT 9-point high-code roll-off is too large: {segment}")

    rows = read_csv(
        require_path(root, "build/spice_dco_postlayout_filled_tt_9pt_check/filled_dco_tt_9pt.csv")
    )
    if len(rows) != len(expected_codes):
        raise ValueError(f"filled DCO TT 9-point CSV has {len(rows)} rows, expected {len(expected_codes)}")
    if [to_int(row, "code") for row in rows] != expected_codes:
        raise ValueError("filled DCO TT 9-point CSV has unexpected code order")
    if {row["corner"] for row in rows} != {"tt"}:
        raise ValueError("filled DCO TT 9-point CSV should only contain TT rows")
    for row in rows:
        code = to_int(row, "code")
        if to_int(row, "enabled_loads") != 255 - code:
            raise ValueError(f"filled DCO TT 9-point code {code} has wrong enabled load count")
        if to_float(row, "freq_mhz") <= 0.0:
            raise ValueError(f"filled DCO TT 9-point code {code} has invalid frequency")
    segment_rows = [row for row in rows if row.get("segment_step_mhz_per_lsb", "") != ""]
    if len(segment_rows) != len(expected_codes) - 1:
        raise ValueError("filled DCO TT 9-point CSV is missing segment metrics")
    allowed_classes = {"positive", "high_code_rolloff", "high_code_flat"}
    if any(row.get("segment_class") not in allowed_classes for row in segment_rows):
        raise ValueError("filled DCO TT 9-point CSV has unexpected segment class")

    return {
        "codes": summary["codes"],
        "finding": summary["finding"],
        "freq_code0_mhz": summary["freq_code0_mhz"],
        "freq_code255_mhz": summary["freq_code255_mhz"],
        "freq_max_code": summary["freq_max_code"],
        "freq_max_mhz": summary["freq_max_mhz"],
        "endpoint_span_mhz": summary["endpoint_span_mhz"],
        "peak_span_mhz": summary["peak_span_mhz"],
        "negative_segments": negative_segments,
    }


def check_filled_dco_highcode_tail(root):
    summary = read_json(
        require_path(
            root,
            "build/spice_dco_postlayout_filled_highcode_tail_check/filled_dco_highcode_tail_summary.json",
        )
    )
    if summary.get("status") != "pass":
        raise ValueError("filled DCO high-code tail summary is not pass")
    if summary.get("corner") != "tt":
        raise ValueError(f"filled DCO high-code tail corner is {summary.get('corner')}")
    expected_codes = [192, 208, 216, 224, 232, 240, 248, 250, 252, 254, 255]
    if summary.get("codes") != expected_codes:
        raise ValueError(f"filled DCO high-code tail codes are {summary.get('codes')}")
    if summary.get("finding") != "high_code_tail_rolloff":
        raise ValueError(f"filled DCO high-code tail finding is {summary.get('finding')}")
    if int(summary.get("peak_code", -1)) != 240:
        raise ValueError(f"filled DCO high-code tail peak code is {summary.get('peak_code')}")
    tail_rolloff = float(summary["tail_rolloff_mhz"])
    if tail_rolloff < 0.6 or tail_rolloff > 0.8:
        raise ValueError(f"filled DCO high-code tail roll-off is unexpected: {tail_rolloff}")
    first_negative = summary.get("first_tail_negative_segment", {})
    if int(first_negative.get("from_code", -1)) != 240 or int(first_negative.get("to_code", -1)) != 248:
        raise ValueError(f"filled DCO high-code tail first negative segment is {first_negative}")
    if int(summary.get("negative_segment_count", 0)) < 3:
        raise ValueError("filled DCO high-code tail should record multiple negative segments")
    min_step = float(summary["min_pre_tail_step_mhz_per_lsb"])
    if min_step < 0.02:
        raise ValueError(f"filled DCO high-code tail pre-tail minimum step is too small: {min_step}")

    rows = read_csv(
        require_path(
            root,
            "build/spice_dco_postlayout_filled_highcode_tail_check/filled_dco_highcode_tail.csv",
        )
    )
    if len(rows) != len(expected_codes):
        raise ValueError(f"filled DCO high-code tail CSV has {len(rows)} rows, expected {len(expected_codes)}")
    if [to_int(row, "code") for row in rows] != expected_codes:
        raise ValueError("filled DCO high-code tail CSV has unexpected code order")
    if {row["corner"] for row in rows} != {"tt"}:
        raise ValueError("filled DCO high-code tail CSV should only contain TT rows")
    for row in rows:
        code = to_int(row, "code")
        if to_int(row, "enabled_loads") != 255 - code:
            raise ValueError(f"filled DCO high-code tail code {code} has wrong enabled load count")
        if to_float(row, "freq_mhz") <= 0.0:
            raise ValueError(f"filled DCO high-code tail code {code} has invalid frequency")
    segment_classes = [row.get("segment_class", "") for row in rows[:-1]]
    if "rolloff" not in segment_classes:
        raise ValueError("filled DCO high-code tail CSV does not record roll-off segments")

    return {
        "codes": summary["codes"],
        "finding": summary["finding"],
        "peak_code": summary["peak_code"],
        "peak_freq_mhz": summary["peak_freq_mhz"],
        "freq_code255_mhz": summary["freq_code255_mhz"],
        "tail_rolloff_mhz": summary["tail_rolloff_mhz"],
        "first_tail_negative_segment": first_negative,
        "negative_segment_count": summary["negative_segment_count"],
    }


def check_filled_dco_local_gain(root):
    summary = read_json(
        require_path(
            root,
            "build/spice_dco_postlayout_filled_local_gain/filled_dco_local_gain_summary.json",
        )
    )
    if summary.get("status") != "pass":
        raise ValueError("filled DCO local-gain summary is not pass")
    if summary.get("corner") != "tt":
        raise ValueError(f"filled DCO local-gain corner is {summary.get('corner')}")
    if summary.get("codes") != [120, 128, 136]:
        raise ValueError(f"filled DCO local-gain codes are {summary.get('codes')}")
    if summary.get("center_code") != 128:
        raise ValueError(f"filled DCO local-gain center code is {summary.get('center_code')}")
    min_step = float(summary["min_segment_step_mhz_per_lsb"])
    max_step = float(summary["max_segment_step_mhz_per_lsb"])
    if min_step < 0.02:
        raise ValueError(f"filled DCO local minimum step is too small: {min_step}")
    if max_step > 0.04:
        raise ValueError(f"filled DCO local maximum step is too large: {max_step}")
    if float(summary["span_mhz"]) < 0.3:
        raise ValueError("filled DCO local span is too small")

    rows = read_csv(
        require_path(
            root,
            "build/spice_dco_postlayout_filled_local_gain/filled_dco_local_gain.csv",
        )
    )
    if len(rows) != 3:
        raise ValueError(f"filled DCO local-gain CSV has {len(rows)} rows, expected 3")
    if [to_int(row, "code") for row in rows] != [120, 128, 136]:
        raise ValueError("filled DCO local-gain CSV has unexpected code order")
    if {row["corner"] for row in rows} != {"tt"}:
        raise ValueError("filled DCO local-gain CSV should only contain TT rows")
    freqs = [to_float(row, "freq_mhz") for row in rows]
    if any(right <= left for left, right in zip(freqs, freqs[1:])):
        raise ValueError("filled DCO local-gain frequencies are not strictly increasing")
    segment_steps = [
        to_float(row, "segment_step_mhz_per_lsb")
        for row in rows
        if row.get("segment_step_mhz_per_lsb", "") != ""
    ]
    if len(segment_steps) != 2:
        raise ValueError("filled DCO local-gain CSV should contain two segment steps")
    if min(to_int(row, "xyce_mpi_procs") for row in rows) < 1:
        raise ValueError("filled DCO local-gain rows have invalid Xyce MPI process count")
    return {
        "corner": summary["corner"],
        "codes": summary["codes"],
        "center_freq_mhz": summary["center_freq_mhz"],
        "span_mhz": summary["span_mhz"],
        "avg_step_mhz_per_lsb": summary["avg_step_mhz_per_lsb"],
        "segment_steps_mhz_per_lsb": segment_steps,
        "min_xyce_mpi_procs": summary["min_xyce_mpi_procs"],
    }


def check_filled_dco_pvt_endpoints(root):
    summary = read_json(
        require_path(
            root,
            "build/spice_dco_postlayout_filled_pvt_endpoints/filled_dco_pvt_endpoint_summary.json",
        )
    )
    if summary.get("status") != "pass":
        raise ValueError("filled DCO PVT endpoint summary is not pass")
    expected_corners = ["ff", "fs", "sf", "ss"]
    if summary.get("corners") != expected_corners:
        raise ValueError(f"filled DCO PVT endpoint corners are {summary.get('corners')}")
    if summary.get("codes") != [0, 255]:
        raise ValueError(f"filled DCO PVT endpoint codes are {summary.get('codes')}")
    spans = summary.get("spans", {})
    missing = [corner for corner in expected_corners if corner not in spans]
    if missing:
        raise ValueError(f"filled DCO PVT endpoint summary is missing spans: {missing}")
    min_spans_mhz = {"ff": 5.0, "fs": 5.0, "sf": 5.0, "ss": 3.0}
    for corner in expected_corners:
        span = spans[corner]
        if float(span["span_mhz"]) < min_spans_mhz[corner]:
            raise ValueError(
                f"filled DCO {corner.upper()} endpoint span is below "
                f"{min_spans_mhz[corner]} MHz"
            )
        if float(span["freq_max_mhz"]) <= float(span["freq_min_mhz"]):
            raise ValueError(f"filled DCO {corner.upper()} endpoints are not monotonic")

    rows = read_csv(
        require_path(
            root,
            "build/spice_dco_postlayout_filled_pvt_endpoints/filled_dco_pvt_endpoints.csv",
        )
    )
    if len(rows) != 8:
        raise ValueError(f"filled DCO PVT endpoint CSV has {len(rows)} rows, expected 8")
    if {row["corner"] for row in rows} != set(expected_corners):
        raise ValueError("filled DCO PVT endpoint CSV does not cover all expected corners")
    for corner in expected_corners:
        corner_rows = sorted(
            [row for row in rows if row["corner"] == corner],
            key=lambda row: to_int(row, "code"),
        )
        codes = [to_int(row, "code") for row in corner_rows]
        if codes != [0, 255]:
            raise ValueError(f"filled DCO PVT endpoint CSV has {corner} codes {codes}")
        freqs = [to_float(row, "freq_mhz") for row in corner_rows]
        if freqs[1] <= freqs[0]:
            raise ValueError(f"filled DCO PVT endpoint CSV {corner} frequencies are not increasing")
    return {
        "corners": summary["corners"],
        "codes": summary["codes"],
        "spans": {
            corner: {
                "freq_min_mhz": spans[corner]["freq_min_mhz"],
                "freq_max_mhz": spans[corner]["freq_max_mhz"],
                "span_mhz": spans[corner]["span_mhz"],
                "avg_step_mhz_per_lsb": spans[corner]["avg_step_mhz_per_lsb"],
            }
            for corner in expected_corners
        },
    }


def check_bbpd(root):
    pvt_rows = read_csv(require_path(root, "build/spice_bbpd_postlayout_pvt/bbpd_postlayout_check.csv"))
    if len(pvt_rows) != 10:
        raise ValueError(f"BBPD PVT polarity coverage has {len(pvt_rows)} rows, expected 10")
    require_all_pass(pvt_rows)
    cases = {(row["corner"], row["case"]) for row in pvt_rows}
    expected_cases = {(corner, case) for corner in EXPECTED_CORNERS for case in ("ref_leads", "fb_leads")}
    if cases != expected_cases:
        raise ValueError("BBPD PVT polarity rows do not cover every corner/case")
    for row in pvt_rows:
        if row["case"] == "ref_leads" and row.get("expected") != "up":
            raise ValueError(f"BBPD ref_leads expected field is wrong in {row}")
        if row["case"] == "fb_leads" and row.get("expected") != "dn":
            raise ValueError(f"BBPD fb_leads expected field is wrong in {row}")

    deadzone_rows = read_csv(require_path(root, "build/spice_bbpd_deadzone_pvt/bbpd_deadzone_summary.csv"))
    if {row["corner"] for row in deadzone_rows} != set(EXPECTED_CORNERS):
        raise ValueError("BBPD dead-zone summary does not cover all expected corners")
    worst_fb_ps = 0.0
    worst_zero_ps = 0.0
    for row in deadzone_rows:
        if to_int(row, "failed_rows") != 0:
            raise ValueError(f"BBPD dead-zone has failed rows at {row['corner']}")
        if to_float(row, "min_ref_leads_correct_ps") > 2.0:
            raise ValueError(f"BBPD reference-leading threshold too high at {row['corner']}")
        fb_ps = to_float(row, "min_fb_leads_correct_ps")
        if fb_ps > 50.0:
            raise ValueError(f"BBPD feedback-leading threshold too high at {row['corner']}")
        zero_ps = abs(to_float(row, "zero_offset_width_diff_ps"))
        if zero_ps > 30.0:
            raise ValueError(f"BBPD zero-offset skew too large at {row['corner']}")
        worst_fb_ps = max(worst_fb_ps, fb_ps)
        worst_zero_ps = max(worst_zero_ps, zero_ps)
    return {
        "pvt_polarity_rows": len(pvt_rows),
        "worst_fb_threshold_ps": worst_fb_ps,
        "worst_zero_offset_skew_ps": worst_zero_ps,
    }


def check_loop_csv(root, relpath, expected_rows, expected_corners=None, dco_model=None):
    rows = read_csv(require_path(root, relpath))
    if len(rows) != expected_rows:
        raise ValueError(f"{relpath} has {len(rows)} rows, expected {expected_rows}")
    require_all_pass(rows)
    cases = {row["case"] for row in rows}
    if cases != {"low_start", "high_start"}:
        raise ValueError(f"{relpath} does not include both rail-start cases")
    if expected_corners is not None and {row["corner"] for row in rows} != set(expected_corners):
        raise ValueError(f"{relpath} does not cover expected corners")
    for row in rows:
        if row.get("timed_out") != "no":
            raise ValueError(f"{relpath} row timed out: {row}")
        if dco_model is not None and row.get("dco_model") != dco_model:
            raise ValueError(f"{relpath} row has unexpected DCO model: {row.get('dco_model')}")
        start = to_float(row, "code_start")
        end = to_float(row, "code_end")
        if row["case"] == "low_start" and end <= start:
            raise ValueError(f"{relpath} low_start did not move upward")
        if row["case"] == "high_start" and end >= start:
            raise ValueError(f"{relpath} high_start did not move downward")
        ferr = abs(to_float(row, "ferr_avg_mhz"))
        tol = to_float(row, "freq_tolerance_mhz")
        if ferr > tol:
            raise ValueError(f"{relpath} frequency error {ferr} exceeds tolerance {tol}")
    max_abs_ferr = max(abs(to_float(row, "ferr_avg_mhz")) for row in rows)
    return {
        "rows": len(rows),
        "corners": sorted({row["corner"] for row in rows}),
        "max_abs_ferr_mhz": max_abs_ferr,
    }


def check_gain_summaries(root):
    top_rows = read_csv(require_path(root, "build/pll_top_filled_dco_gain_sweep/pll_top_gain_summary.csv"))
    top_match = [
        row
        for row in top_rows
        if to_int(row, "ki") == 255 and to_int(row, "kp") == 32
    ]
    if len(top_match) != 1:
        raise ValueError("missing unique top-level filled-DCO KI=255 KP=32 gain row")
    top = top_match[0]
    if top.get("pass_both") != "1":
        raise ValueError("top-level KI=255 KP=32 gain row did not pass both rails")
    if to_float(top, "max_abs_error_code") > 8.0:
        raise ValueError("top-level KI=255 KP=32 exceeds eight final-code error")

    digital_rows = read_csv(require_path(root, "build/digital_loop_gain_sweep/digital_loop_gain_summary.csv"))
    digital_match = [
        row
        for row in digital_rows
        if to_int(row, "ki") == 255 and to_int(row, "kp") == 2
    ]
    if len(digital_match) != 1:
        raise ValueError("missing unique digital-loop KI=255 KP=2 gain row")
    digital = digital_match[0]
    if digital.get("pass_both") != "1":
        raise ValueError("digital-loop KI=255 KP=2 gain row did not pass both rails")
    if to_float(digital, "max_abs_error_code") > 0.0:
        raise ValueError("digital-loop KI=255 KP=2 should finish exactly in ideal bench")
    digital_fast_match = [
        row
        for row in digital_rows
        if to_int(row, "ki") == 255 and to_int(row, "kp") == 32
    ]
    if len(digital_fast_match) != 1:
        raise ValueError("missing unique digital-loop KI=255 KP=32 gain row")
    digital_fast = digital_fast_match[0]
    if digital_fast.get("pass_both") != "1":
        raise ValueError("digital-loop KI=255 KP=32 gain row did not pass both rails")
    if to_float(digital_fast, "max_abs_error_code") > 1.0:
        raise ValueError("digital-loop KI=255 KP=32 exceeds one final-code error")

    return {
        "top_ki": 255,
        "top_kp": 32,
        "top_max_lock_ns": to_int(top, "max_lock_ns"),
        "top_max_abs_error_code": to_float(top, "max_abs_error_code"),
        "digital_ki": 255,
        "digital_kp": 2,
        "digital_max_lock_ns": to_int(digital, "max_lock_ns"),
        "digital_fast_kp": 32,
        "digital_fast_max_lock_ns": to_int(digital_fast, "max_lock_ns"),
        "digital_fast_max_abs_error_code": to_float(digital_fast, "max_abs_error_code"),
    }


def check_xyce_mixed_signal_gain_sweep(root):
    summary_rows = read_csv(
        require_path(
            root,
            "build/xyce_pll_mixed_signal_gain_sweep/mixed_signal_gain_summary.csv",
        )
    )
    cycle_rows = read_csv(
        require_path(
            root,
            "build/xyce_pll_mixed_signal_gain_sweep/mixed_signal_gain_cycles.csv",
        )
    )
    if len(summary_rows) != 4:
        raise ValueError(f"mixed-signal gain summary has {len(summary_rows)} rows, expected 4")

    by_case = {row["case"]: row for row in summary_rows}
    expected_cases = {
        "ki160_kp0_low",
        "ki160_kp0_high",
        "ki160_kp8_low",
        "ki160_kp8_high",
    }
    if set(by_case) != expected_cases:
        raise ValueError(f"mixed-signal gain summary has unexpected cases: {sorted(by_case)}")

    cycle_counts = {}
    for row in cycle_rows:
        cycle_counts[row["case"]] = cycle_counts.get(row["case"], 0) + 1
    for case in expected_cases:
        if cycle_counts.get(case) != 10:
            raise ValueError(f"mixed-signal cycle CSV has {cycle_counts.get(case, 0)} rows for {case}, expected 10")

    for case, row in by_case.items():
        if row.get("driver_pass") != "1" or row.get("returncode") != "0":
            raise ValueError(f"mixed-signal gain row did not pass driver motion check: {row}")
        if to_int(row, "ki") != 160 or to_int(row, "cycles") != 10:
            raise ValueError(f"mixed-signal gain row has wrong KI/cycle setting: {row}")
        if to_int(row, "target_code") != 128 or to_int(row, "frac") != 6:
            raise ValueError(f"mixed-signal gain row has wrong target/FRAC setting: {row}")
        if to_int(row, "boost_shift") != 4 or to_int(row, "boost_after") != 2:
            raise ValueError(f"mixed-signal gain row has wrong boost setting: {row}")
        if to_int(row, "kp") not in (0, 8):
            raise ValueError(f"mixed-signal gain row has unexpected KP: {row}")
        log_path = Path(row["log_path"])
        if not log_path.is_absolute():
            log_path = root / log_path
        if not log_path.is_file():
            raise ValueError(f"mixed-signal gain row log is missing: {log_path}")

    kp0_low = by_case["ki160_kp0_low"]
    kp8_low = by_case["ki160_kp8_low"]
    kp0_high = by_case["ki160_kp0_high"]
    kp8_high = by_case["ki160_kp8_high"]

    if kp0_low.get("exact_hit") != "0" or kp0_low.get("crossed_target") != "0":
        raise ValueError(f"KP0 low-start row should not hit/cross target in this short mixed sweep: {kp0_low}")
    if kp8_low.get("exact_hit") != "1" or kp8_low.get("crossed_target") != "1":
        raise ValueError(f"KP8 low-start row should hit and cross target in this short mixed sweep: {kp8_low}")
    if to_int(kp8_low, "final_abs_error") >= to_int(kp0_low, "final_abs_error"):
        raise ValueError("KP8 low-start mixed row should improve final error versus KP0")
    if to_int(kp8_low, "first_exact_hit_cycle") != 9:
        raise ValueError(f"KP8 low-start exact-hit cycle changed unexpectedly: {kp8_low}")

    for row in (kp0_high, kp8_high):
        if row.get("crossed_target") != "1":
            raise ValueError(f"high-start mixed row should cross target: {row}")
        if row.get("exact_hit") != "0":
            raise ValueError(f"high-start mixed row should not be reported as exact lock: {row}")
        if to_int(row, "min_abs_error") > 1:
            raise ValueError(f"high-start mixed row did not pass near target: {row}")

    return {
        "rows": len(summary_rows),
        "ki": 160,
        "kp_values": sorted({to_int(row, "kp") for row in summary_rows}),
        "kp0_low_final_code": to_int(kp0_low, "final_code"),
        "kp8_low_final_code": to_int(kp8_low, "final_code"),
        "kp8_low_exact_hit_cycle": to_int(kp8_low, "first_exact_hit_cycle"),
        "kp0_high_final_code": to_int(kp0_high, "final_code"),
        "kp8_high_final_code": to_int(kp8_high, "final_code"),
    }


def check_filled_bbpd_sampled_lock(root):
    rows = read_csv(
        require_path(
            root,
            "build/spice_pll_filled_bbpd_sampled_xyce_lock_probe/sampled_gain_summary.csv",
        )
    )
    matching = [
        row
        for row in rows
        if row.get("simulator") == "xyce"
        and row.get("bbpd_impl") == "postlayout"
        and to_float(row, "dlf_step_lsb") == 17.5
        and to_float(row, "dlf_prop_lsb") == 4.0
        and to_float(row, "sample_delay_ps") == 150.0
        and to_float(row, "max_step_ps") == 1000.0
        and to_float(row, "initial_dco_phase_cycles") == 0.25
    ]
    if len(matching) != 1:
        raise ValueError("missing unique filled-BBPD sampled Xyce lock-probe row")
    row = matching[0]
    if row.get("pass_both") != "1":
        raise ValueError("filled-BBPD sampled Xyce lock probe did not pass both rails")
    if row.get("low_status") != "pass" or row.get("high_status") != "pass":
        raise ValueError(f"filled-BBPD sampled lock probe has bad rail status: {row}")
    if to_float(row, "max_abs_ferr_avg_mhz") > 0.75:
        raise ValueError("filled-BBPD sampled lock probe exceeds 0.75 MHz error")

    sweep_rows = read_csv(
        require_path(
            root,
            "build/spice_pll_filled_bbpd_sampled_xyce_lock_probe/sampled_gain_sweep.csv",
        )
    )
    require_all_pass(sweep_rows)
    if {row["case"] for row in sweep_rows} != {"low_start", "high_start"}:
        raise ValueError("filled-BBPD sampled lock probe does not cover both rails")
    return {
        "dlf_step_lsb": 17.5,
        "dlf_prop_lsb": 4.0,
        "sample_delay_ps": 150.0,
        "initial_dco_phase_cycles": 0.25,
        "low_end_code": to_float(row, "low_end_code"),
        "high_end_code": to_float(row, "high_end_code"),
        "max_abs_ferr_avg_mhz": to_float(row, "max_abs_ferr_avg_mhz"),
    }


def check_mapped_loop_gain_sweep(root):
    summary_rows = read_csv(
        require_path(root, "build/spice_pll_mapped_loop_gain_sweep/mapped_loop_gain_summary.csv")
    )
    detail_rows = read_csv(
        require_path(root, "build/spice_pll_mapped_loop_gain_sweep/mapped_loop_gain_sweep.csv")
    )
    expected_deltas = {0: 0.0, 4: 1.0, 8: 2.0, 16: 4.0, 32: 8.0}
    if len(summary_rows) != len(expected_deltas):
        raise ValueError(f"mapped-loop gain summary has {len(summary_rows)} rows")
    if len(detail_rows) != len(expected_deltas):
        raise ValueError(f"mapped-loop gain detail has {len(detail_rows)} rows")
    require_all_pass(summary_rows)
    require_all_pass(detail_rows)

    by_kp = {to_int(row, "kp"): row for row in summary_rows}
    if set(by_kp) != set(expected_deltas):
        raise ValueError(f"mapped-loop gain summary has unexpected KP set: {sorted(by_kp)}")
    detail_by_kp = {to_int(row, "kp"): row for row in detail_rows}
    if set(detail_by_kp) != set(expected_deltas):
        raise ValueError(f"mapped-loop gain detail has unexpected KP set: {sorted(detail_by_kp)}")

    deltas = []
    elapsed = {}
    startup_freqs = {}
    for kp, expected_delta in expected_deltas.items():
        row = by_kp[kp]
        detail = detail_by_kp[kp]
        if row.get("case") != "mid_start_inc" or detail.get("case") != "mid_start_inc":
            raise ValueError(f"mapped-loop gain row has wrong case: {row}")
        if to_int(row, "ki") != 255 or to_int(detail, "ki") != 255:
            raise ValueError(f"mapped-loop gain row has wrong KI: {row}")
        expected_mode = "no_motion" if kp == 0 else "motion"
        if row.get("check_mode") != expected_mode or detail.get("check_mode") != expected_mode:
            raise ValueError(f"mapped-loop gain row has wrong check mode: {row}")
        if detail.get("simulator") != "xyce" or to_int(detail, "xyce_mpi_procs") != 1:
            raise ValueError(f"mapped-loop gain row has wrong simulator: {detail}")
        if detail.get("bbpd_impl") != "postlayout" or detail.get("digital_scope") != "full":
            raise ValueError(f"mapped-loop gain row has wrong implementation scope: {detail}")
        if detail.get("dco_model") != "piecewise5_behavioral":
            raise ValueError(f"mapped-loop gain row has wrong DCO model: {detail}")
        if to_int(detail, "mapped_instance_count") < 900:
            raise ValueError(f"mapped-loop gain row has too few mapped instances: {detail}")
        if to_int(detail, "skipped_physical_only_cells") != 0:
            raise ValueError(f"mapped-loop gain row skipped unexpected cells: {detail}")
        if to_int(detail, "ndiv") != 2:
            raise ValueError(f"mapped-loop gain row has wrong divider: {detail}")
        if detail.get("timed_out") != "no" or to_int(detail, "returncode") != 0:
            raise ValueError(f"mapped-loop gain row did not finish cleanly: {detail}")
        if abs(to_float(detail, "start_meas_ns") - 79.0) > 1e-9:
            raise ValueError(f"mapped-loop gain row has wrong start window: {detail}")
        if abs(to_float(detail, "end_meas_ns") - 179.0) > 1e-9:
            raise ValueError(f"mapped-loop gain row has wrong end window: {detail}")
        if abs(to_float(row, "start_code") - 128.0) > 1e-9:
            raise ValueError(f"mapped-loop gain row has wrong start code: {row}")
        for key in ("response_delta_code", "end_delta_code"):
            if abs(to_float(row, key) - expected_delta) > 1e-9:
                raise ValueError(f"mapped-loop gain row has wrong {key}: {row}")
        if abs(to_float(row, "observed_min_code") - 128.0) > 1e-9:
            raise ValueError(f"mapped-loop gain row has wrong observed minimum: {row}")
        if abs(to_float(row, "observed_max_code") - (128.0 + expected_delta)) > 1e-9:
            raise ValueError(f"mapped-loop gain row has wrong observed maximum: {row}")
        startup_freq = to_float(row, "startup_freq_mhz")
        if not (49.0 <= startup_freq <= 50.2):
            raise ValueError(f"mapped-loop gain row has unexpected startup frequency: {row}")
        if not Path(row.get("waveform", "")).is_file():
            raise ValueError(f"mapped-loop gain row missing waveform: {row}")
        deltas.append(expected_delta)
        elapsed[kp] = to_float(row, "elapsed_s")
        startup_freqs[kp] = startup_freq

    if any(right < left for left, right in zip(deltas, deltas[1:])):
        raise ValueError(f"mapped-loop gain deltas are not monotonic: {deltas}")

    return {
        "case": "mid_start_inc",
        "ki": 255,
        "kp_values": sorted(expected_deltas),
        "response_delta_by_kp": {str(kp): expected_deltas[kp] for kp in sorted(expected_deltas)},
        "elapsed_s_by_kp": {str(kp): elapsed[kp] for kp in sorted(elapsed)},
        "startup_freq_mhz_by_kp": {str(kp): startup_freqs[kp] for kp in sorted(startup_freqs)},
    }


def check_mapped_loop_phase_sweep(root):
    summary_rows = read_csv(
        require_path(root, "build/spice_pll_mapped_loop_phase_sweep/mapped_loop_phase_summary.csv")
    )
    detail_rows = read_csv(
        require_path(root, "build/spice_pll_mapped_loop_phase_sweep/mapped_loop_phase_sweep.csv")
    )
    expected_phases = (0.0, 0.25, 0.5, 0.75)
    if len(summary_rows) != len(expected_phases):
        raise ValueError(f"mapped-loop phase summary has {len(summary_rows)} rows")
    if len(detail_rows) != 2 * len(expected_phases):
        raise ValueError(f"mapped-loop phase detail has {len(detail_rows)} rows")
    require_all_pass(detail_rows)

    by_phase = {to_float(row, "initial_dco_phase_cycles"): row for row in summary_rows}
    if set(by_phase) != set(expected_phases):
        raise ValueError(f"mapped-loop phase summary has unexpected phases: {sorted(by_phase)}")

    low_responses = {}
    high_responses = {}
    for phase in expected_phases:
        row = by_phase[phase]
        if row.get("low_status") != "pass" or row.get("high_status") != "pass":
            raise ValueError(f"mapped-loop phase row did not pass both rails: {row}")
        if to_int(row, "pass_both") != 1:
            raise ValueError(f"mapped-loop phase row has wrong pass_both flag: {row}")
        low_start = to_float(row, "low_start_code")
        low_response = to_float(row, "low_response_code")
        high_start = to_float(row, "high_start_code")
        high_response = to_float(row, "high_response_code")
        if abs(low_start) > 2.0 or low_response < 7.5:
            raise ValueError(f"mapped-loop low-start phase row lacks upward correction: {row}")
        if abs(high_start - 255.0) > 2.0 or high_response > 247.5:
            raise ValueError(f"mapped-loop high-start phase row lacks downward correction: {row}")
        low_responses[str(phase)] = low_response
        high_responses[str(phase)] = high_response

    seen = set()
    elapsed = {}
    for row in detail_rows:
        case = row.get("case")
        phase = to_float(row, "initial_dco_phase_cycles")
        if case not in {"low_start", "high_start"} or phase not in expected_phases:
            raise ValueError(f"mapped-loop phase detail has unexpected case/phase: {row}")
        pair = (case, phase)
        if pair in seen:
            raise ValueError(f"mapped-loop phase detail has duplicate case/phase: {row}")
        seen.add(pair)
        if row.get("simulator") != "xyce" or to_int(row, "xyce_mpi_procs") != 1:
            raise ValueError(f"mapped-loop phase row has wrong simulator: {row}")
        if row.get("bbpd_impl") != "postlayout" or row.get("digital_scope") != "full":
            raise ValueError(f"mapped-loop phase row has wrong implementation scope: {row}")
        if row.get("dco_model") != "piecewise5_behavioral":
            raise ValueError(f"mapped-loop phase row has wrong DCO model: {row}")
        if row.get("expected") not in {"increase", "decrease"}:
            raise ValueError(f"mapped-loop phase row has wrong expected direction: {row}")
        if to_int(row, "ki") != 255 or to_int(row, "kp") != 32 or to_int(row, "ndiv") != 2:
            raise ValueError(f"mapped-loop phase row has wrong loop setting: {row}")
        if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
            raise ValueError(f"mapped-loop phase row did not finish cleanly: {row}")
        if abs(to_float(row, "start_meas_ns") - 79.0) > 1e-9:
            raise ValueError(f"mapped-loop phase row has wrong start window: {row}")
        if abs(to_float(row, "end_meas_ns") - 179.0) > 1e-9:
            raise ValueError(f"mapped-loop phase row has wrong end window: {row}")
        if row.get("mapped_instance_count") not in ("", None):
            if to_int(row, "mapped_instance_count") < 900:
                raise ValueError(f"mapped-loop phase row has too few mapped instances: {row}")
            if to_int(row, "skipped_physical_only_cells") != 0:
                raise ValueError(f"mapped-loop phase row skipped unexpected cells: {row}")
        if not Path(row.get("waveform", "")).is_file():
            raise ValueError(f"mapped-loop phase row missing waveform: {row}")
        response = response_code(row)
        start = to_float(row, "start_code")
        if case == "low_start" and not (abs(start) <= 2.0 and response >= 7.5):
            raise ValueError(f"mapped-loop phase low-start row lacks upward response: {row}")
        if case == "high_start" and not (abs(start - 255.0) <= 2.0 and response <= 247.5):
            raise ValueError(f"mapped-loop phase high-start row lacks downward response: {row}")
        elapsed[pair] = to_float(row, "elapsed_s")

    if seen != {(case, phase) for phase in expected_phases for case in ("low_start", "high_start")}:
        raise ValueError(f"mapped-loop phase detail does not cover all case/phase pairs: {seen}")

    return {
        "rows": len(detail_rows),
        "summary_rows": len(summary_rows),
        "digital_scope": "full",
        "bbpd_impl": "postlayout",
        "dco_model": "piecewise5_behavioral",
        "ki": 255,
        "kp": 32,
        "phases": list(expected_phases),
        "low_response_code_by_phase": low_responses,
        "high_response_code_by_phase": high_responses,
        "max_elapsed_s": max(elapsed.values()),
    }


def check_mapped_loop_progress_1us(root):
    rows = read_csv(
        require_path(
            root,
            "build/spice_pll_mapped_loop_behavioral_acq_1us_kp32_mpi4_klu/mapped_loop_check.csv",
        )
    )
    if {row["case"] for row in rows} != {"low_start", "high_start"}:
        raise ValueError("mapped-loop 1 us progress probe does not cover both rails")
    require_all_pass(rows)

    details = {}
    for row in rows:
        case = row["case"]
        if row.get("simulator") != "xyce" or to_int(row, "xyce_mpi_procs") != 4:
            raise ValueError(f"mapped-loop 1 us row has wrong simulator/MPI setting: {row}")
        if "-linsolv KLU" not in row.get("xyce_command", ""):
            raise ValueError(f"mapped-loop 1 us row does not record KLU: {row}")
        if row.get("bbpd_impl") != "postlayout" or row.get("digital_scope") != "full":
            raise ValueError(f"mapped-loop 1 us row has wrong implementation scope: {row}")
        if row.get("dco_model") != "piecewise5_behavioral":
            raise ValueError(f"mapped-loop 1 us row has wrong DCO model: {row}")
        if row.get("check_mode") != "motion":
            raise ValueError(f"mapped-loop 1 us row has wrong check mode: {row}")
        if to_int(row, "mapped_instance_count") < 900:
            raise ValueError(f"mapped-loop 1 us row has too few mapped instances: {row}")
        if to_int(row, "skipped_physical_only_cells") != 0:
            raise ValueError(f"mapped-loop 1 us row skipped unexpected cells: {row}")
        if to_int(row, "ki") != 255 or to_int(row, "kp") != 32 or to_int(row, "ndiv") != 2:
            raise ValueError(f"mapped-loop 1 us row has wrong loop setting: {row}")
        if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
            raise ValueError(f"mapped-loop 1 us row did not finish cleanly: {row}")
        if abs(to_float(row, "start_meas_ns") - 79.0) > 1e-9:
            raise ValueError(f"mapped-loop 1 us row has wrong start window: {row}")
        if abs(to_float(row, "end_meas_ns") - 999.0) > 1e-9:
            raise ValueError(f"mapped-loop 1 us row has wrong end window: {row}")
        if not Path(row.get("waveform", "")).is_file():
            raise ValueError(f"mapped-loop 1 us row missing waveform: {row}")

        start_code = to_float(row, "start_code")
        end_code = to_float(row, "end_code")
        response = response_code(row)
        start_integ = to_float(row, "start_integ_code")
        end_integ = to_float(row, "end_integ_code")
        start_freq = to_float(row, "start_freq_mhz")
        end_freq = to_float(row, "end_freq_mhz")
        target_freq = to_float(row, "target_freq_mhz")
        start_abs_error = abs(start_freq - target_freq)
        end_abs_error = abs(end_freq - target_freq)
        if end_abs_error >= start_abs_error:
            raise ValueError(f"mapped-loop 1 us row did not reduce frequency error: {row}")

        if case == "low_start":
            if abs(start_code) > 2.0 or response < 8.5 or end_code < 8.5:
                raise ValueError(f"mapped-loop 1 us low-start row lacks code progress: {row}")
            if start_integ != 0.0 or end_integ < 1.5:
                raise ValueError(f"mapped-loop 1 us low-start row lacks integrator progress: {row}")
        else:
            if abs(start_code - 255.0) > 2.0 or response > 146.0 or end_code > 247.0:
                raise ValueError(f"mapped-loop 1 us high-start row lacks code progress: {row}")
            if start_integ != 255.0 or end_integ > 252.0:
                raise ValueError(f"mapped-loop 1 us high-start row lacks integrator progress: {row}")

        details[case] = {
            "start_code": start_code,
            "end_code": end_code,
            "response_code": response,
            "start_integ_code": start_integ,
            "end_integ_code": end_integ,
            "start_freq_mhz": start_freq,
            "end_freq_mhz": end_freq,
            "start_abs_error_mhz": start_abs_error,
            "end_abs_error_mhz": end_abs_error,
            "elapsed_s": to_float(row, "elapsed_s"),
        }

    return {
        "rows": len(rows),
        "digital_scope": "full",
        "bbpd_impl": "postlayout",
        "dco_model": "piecewise5_behavioral",
        "ki": 255,
        "kp": 32,
        "sim_time_ns": 1000,
        "cases": details,
        "max_final_abs_error_mhz": max(
            case_details["end_abs_error_mhz"] for case_details in details.values()
        ),
    }


def check_dlf_static_rows(root, relpath, kp, expected_static):
    static_rows = read_csv(require_path(root, relpath))
    if {row["case"] for row in static_rows} != {"hold_mid", "inc_mid", "dec_mid"}:
        raise ValueError(f"{relpath} does not cover hold/inc/dec")
    require_all_pass(static_rows)
    for row in static_rows:
        if to_int(row, "ki") != 255 or to_int(row, "kp") != kp:
            raise ValueError(f"DLF static row has wrong gain: {row}")
        if to_int(row, "measured_dco_code") != expected_static[row["case"]]:
            raise ValueError(f"DLF static row has wrong measured code: {row}")
    return static_rows


def dlf_response_code(row):
    return to_int(row, "response_code") if row.get("response_code") else to_int(row, "end_code")


def response_code(row):
    return to_float(row, "response_code") if row.get("response_code") else to_float(row, "end_code")


def count_spice_instances(path):
    return sum(
        1
        for line in path.read_text(encoding="ascii", errors="replace").splitlines()
        if line.startswith("X")
    )


def count_spef_caps(path):
    return sum(
        1
        for line in path.read_text(encoding="ascii", errors="replace").splitlines()
        if line.startswith("CSPEF_")
    )


def count_hardtop_spef_caps(path):
    return sum(
        1
        for line in path.read_text(encoding="ascii", errors="replace").splitlines()
        if line.startswith("CHTSPEF_")
    )


def count_hardtop_spef_resistors(path):
    return sum(
        1
        for line in path.read_text(encoding="ascii", errors="replace").splitlines()
        if line.startswith("RHTSPEF_")
    )


def count_spef_resistors(path):
    return sum(
        1
        for line in path.read_text(encoding="ascii", errors="replace").splitlines()
        if line.startswith("RSPEF_")
    )


def check_dlf_update_rows(root, relpath, kp):
    update_rows = read_csv(require_path(root, relpath))
    expected_cases = {"inc_mid", "dec_mid", "inc_overlap", "dec_overlap"}
    if {row["case"] for row in update_rows} != expected_cases:
        raise ValueError(f"{relpath} does not cover inc/dec and overlap cases")
    require_all_pass(update_rows)
    for row in update_rows:
        if row.get("simulator") != "xyce":
            raise ValueError(f"DLF update row is not Xyce: {row}")
        if to_int(row, "ki") != 255 or to_int(row, "kp") != kp:
            raise ValueError(f"DLF update row has wrong gain: {row}")
        start = to_int(row, "start_code")
        response = dlf_response_code(row)
        if row["case"].startswith("inc") and not response > start:
            raise ValueError("DLF update inc_mid did not increase code")
        if row["case"].startswith("dec") and not response < start:
            raise ValueError("DLF update dec_mid did not decrease code")
    return update_rows


def check_dlf_signoff_nl_rows(root, relpath):
    rows = check_dlf_update_rows(root, relpath, 32)
    build_dir = (root / "build/spice_dlf_update_signoff_nl_kp32_fast").resolve()
    instance_counts = {}
    for row in rows:
        if row.get("scope") != "cone":
            raise ValueError(f"signoff-netlist DLF row has wrong scope: {row}")
        if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
            raise ValueError(f"signoff-netlist DLF row did not finish cleanly: {row}")
        netlist_path = Path(row["netlist"]).expanduser().resolve()
        if not netlist_path.is_file():
            raise ValueError(f"missing signoff-netlist DLF deck: {netlist_path}")
        if build_dir not in netlist_path.parents:
            raise ValueError(f"signoff-netlist DLF deck is outside expected build dir: {netlist_path}")
        instance_count = count_spice_instances(netlist_path)
        if instance_count < 500:
            raise ValueError(
                f"signoff-netlist DLF cone is too small to be the final-netlist cone: {instance_count}"
            )
        instance_counts[row["case"]] = instance_count
    return rows, instance_counts


def check_dlf_signoff_spef_rows(root, relpath):
    rows = check_dlf_update_rows(root, relpath, 32)
    build_dir = (root / "build/spice_dlf_update_signoff_spef_kp32_fast").resolve()
    instance_counts = {}
    cap_counts = {}
    cap_totals_ff = {}
    for row in rows:
        if row.get("scope") != "cone":
            raise ValueError(f"SPEF DLF row has wrong scope: {row}")
        if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
            raise ValueError(f"SPEF DLF row did not finish cleanly: {row}")
        if row.get("spef_mode") != "lumped_cap":
            raise ValueError(f"SPEF DLF row has wrong SPEF mode: {row}")
        if to_int(row, "spef_cap_nets") < 500:
            raise ValueError(f"SPEF DLF row has too few modeled cap nets: {row}")
        if to_float(row, "spef_cap_total_ff") < 1000.0:
            raise ValueError(f"SPEF DLF row has too little modeled cap: {row}")
        netlist_path = Path(row["netlist"]).expanduser().resolve()
        if not netlist_path.is_file():
            raise ValueError(f"missing SPEF DLF deck: {netlist_path}")
        if build_dir not in netlist_path.parents:
            raise ValueError(f"SPEF DLF deck is outside expected build dir: {netlist_path}")
        instance_count = count_spice_instances(netlist_path)
        cap_count = count_spef_caps(netlist_path)
        if instance_count < 500:
            raise ValueError(f"SPEF DLF cone is too small: {instance_count}")
        if cap_count != to_int(row, "spef_cap_nets"):
            raise ValueError(f"SPEF cap count mismatch in {netlist_path}: {cap_count} vs {row}")
        instance_counts[row["case"]] = instance_count
        cap_counts[row["case"]] = cap_count
        cap_totals_ff[row["case"]] = to_float(row, "spef_cap_total_ff")
    return rows, instance_counts, cap_counts, cap_totals_ff


def check_dlf_signoff_spef_rc_rows(root, relpath):
    rows = check_dlf_update_rows(root, relpath, 32)
    build_dir = (root / "build/spice_dlf_update_signoff_spef_rc_kp32_fast").resolve()
    instance_counts = {}
    cap_counts = {}
    resistor_counts = {}
    pin_node_counts = {}
    cap_totals_ff = {}
    for row in rows:
        if row.get("scope") != "cone":
            raise ValueError(f"SPEF-RC DLF row has wrong scope: {row}")
        if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
            raise ValueError(f"SPEF-RC DLF row did not finish cleanly: {row}")
        if row.get("spef_mode") != "distributed_rc":
            raise ValueError(f"SPEF-RC DLF row has wrong SPEF mode: {row}")
        if to_int(row, "spef_pin_nodes") < 1500:
            raise ValueError(f"SPEF-RC DLF row has too few substituted pin nodes: {row}")
        if to_int(row, "spef_cap_nets") < 3000:
            raise ValueError(f"SPEF-RC DLF row has too few modeled cap nodes: {row}")
        if to_int(row, "spef_resistors") < 2000:
            raise ValueError(f"SPEF-RC DLF row has too few modeled resistors: {row}")
        if to_float(row, "spef_cap_total_ff") < 1000.0:
            raise ValueError(f"SPEF-RC DLF row has too little modeled cap: {row}")
        netlist_path = Path(row["netlist"]).expanduser().resolve()
        if not netlist_path.is_file():
            raise ValueError(f"missing SPEF-RC DLF deck: {netlist_path}")
        if build_dir not in netlist_path.parents:
            raise ValueError(f"SPEF-RC DLF deck is outside expected build dir: {netlist_path}")
        instance_count = count_spice_instances(netlist_path)
        cap_count = count_spef_caps(netlist_path)
        resistor_count = count_spef_resistors(netlist_path)
        if instance_count < 500:
            raise ValueError(f"SPEF-RC DLF cone is too small: {instance_count}")
        if cap_count != to_int(row, "spef_cap_nets"):
            raise ValueError(f"SPEF-RC cap count mismatch in {netlist_path}: {cap_count} vs {row}")
        if resistor_count != to_int(row, "spef_resistors"):
            raise ValueError(
                f"SPEF-RC resistor count mismatch in {netlist_path}: {resistor_count} vs {row}"
            )
        instance_counts[row["case"]] = instance_count
        cap_counts[row["case"]] = cap_count
        resistor_counts[row["case"]] = resistor_count
        pin_node_counts[row["case"]] = to_int(row, "spef_pin_nodes")
        cap_totals_ff[row["case"]] = to_float(row, "spef_cap_total_ff")
    return rows, instance_counts, cap_counts, resistor_counts, pin_node_counts, cap_totals_ff


def check_dlf_full_overlap_rows(root, relpath):
    rows = read_csv(require_path(root, relpath))
    if {row["case"] for row in rows} != {"inc_overlap", "dec_overlap"}:
        raise ValueError(f"{relpath} does not cover full-core overlap cases")
    require_all_pass(rows)
    for row in rows:
        if row.get("simulator") != "xyce":
            raise ValueError(f"full-core DLF row is not Xyce: {row}")
        if row.get("scope") != "full":
            raise ValueError(f"full-core DLF row has wrong scope: {row}")
        if to_int(row, "ki") != 255 or to_int(row, "kp") != 32:
            raise ValueError(f"full-core DLF row has wrong gain: {row}")
        start = to_int(row, "start_code")
        response = dlf_response_code(row)
        if row["case"] == "inc_overlap" and not response > start:
            raise ValueError("full-core inc_overlap did not increase code")
        if row["case"] == "dec_overlap" and not response < start:
            raise ValueError("full-core dec_overlap did not decrease code")
    return rows


def check_dlf_bbpd_rcx_rows(root, relpath, scope):
    rows = read_csv(require_path(root, relpath))
    if {row["case"] for row in rows} != {"inc_bbpd_rcx", "dec_bbpd_rcx"}:
        raise ValueError(f"{relpath} does not cover BBPD-RCX driven DLF cases")
    require_all_pass(rows)
    for row in rows:
        if row.get("simulator") != "xyce":
            raise ValueError(f"BBPD-RCX DLF row is not Xyce: {row}")
        if row.get("scope") != scope:
            raise ValueError(f"BBPD-RCX DLF row has wrong scope: {row}")
        if to_int(row, "ki") != 255 or to_int(row, "kp") != 32:
            raise ValueError(f"BBPD-RCX DLF row has wrong gain: {row}")
        start = to_int(row, "start_code")
        response = dlf_response_code(row)
        if row["case"] == "inc_bbpd_rcx" and not response > start:
            raise ValueError("BBPD-RCX inc case did not increase code")
        if row["case"] == "dec_bbpd_rcx" and not response < start:
            raise ValueError("BBPD-RCX dec case did not decrease code")
    return rows


def check_dlf_bbpd_rcx_signoff_spef_rc_rows(root, relpath):
    rows = check_dlf_bbpd_rcx_rows(root, relpath, "cone")
    build_dir = (root / "build/spice_bbpd_dlf_integration_signoff_spef_rc_kp32").resolve()
    instance_counts = {}
    cap_counts = {}
    resistor_counts = {}
    pin_node_counts = {}
    cap_totals_ff = {}
    for row in rows:
        if row.get("spef_mode") != "distributed_rc":
            raise ValueError(f"BBPD-RCX SPEF-RC DLF row has wrong SPEF mode: {row}")
        if to_int(row, "spef_pin_nodes") < 1500:
            raise ValueError(f"BBPD-RCX SPEF-RC row has too few substituted pin nodes: {row}")
        if to_int(row, "spef_cap_nets") < 3000:
            raise ValueError(f"BBPD-RCX SPEF-RC row has too few modeled cap nodes: {row}")
        if to_int(row, "spef_resistors") < 2000:
            raise ValueError(f"BBPD-RCX SPEF-RC row has too few modeled resistors: {row}")
        if to_float(row, "spef_cap_total_ff") < 1000.0:
            raise ValueError(f"BBPD-RCX SPEF-RC row has too little modeled cap: {row}")
        netlist_path = Path(row["netlist"]).expanduser().resolve()
        if not netlist_path.is_file():
            raise ValueError(f"missing BBPD-RCX SPEF-RC DLF deck: {netlist_path}")
        if build_dir not in netlist_path.parents:
            raise ValueError(
                f"BBPD-RCX SPEF-RC DLF deck is outside expected build dir: {netlist_path}"
            )
        instance_count = count_spice_instances(netlist_path)
        cap_count = count_spef_caps(netlist_path)
        resistor_count = count_spef_resistors(netlist_path)
        if instance_count < 541:
            raise ValueError(f"BBPD-RCX SPEF-RC DLF deck has too few X instances: {instance_count}")
        if cap_count != to_int(row, "spef_cap_nets"):
            raise ValueError(
                f"BBPD-RCX SPEF-RC cap count mismatch in {netlist_path}: {cap_count} vs {row}"
            )
        if resistor_count != to_int(row, "spef_resistors"):
            raise ValueError(
                f"BBPD-RCX SPEF-RC resistor count mismatch in {netlist_path}: "
                f"{resistor_count} vs {row}"
            )
        instance_counts[row["case"]] = instance_count
        cap_counts[row["case"]] = cap_count
        resistor_counts[row["case"]] = resistor_count
        pin_node_counts[row["case"]] = to_int(row, "spef_pin_nodes")
        cap_totals_ff[row["case"]] = to_float(row, "spef_cap_total_ff")
    return rows, instance_counts, cap_counts, resistor_counts, pin_node_counts, cap_totals_ff


def check_dlf_spice(root):
    static16_rows = check_dlf_static_rows(
        root,
        "build/spice_dlf_static_kp16/dlf_static_check.csv",
        16,
        {"hold_mid": 128, "inc_mid": 132, "dec_mid": 124},
    )
    update16_rows = check_dlf_update_rows(
        root,
        "build/spice_dlf_update_xyce_kp16/dlf_update_check.csv",
        16,
    )
    static32_rows = check_dlf_static_rows(
        root,
        "build/spice_dlf_static_kp32/dlf_static_check.csv",
        32,
        {"hold_mid": 128, "inc_mid": 136, "dec_mid": 120},
    )
    update32_rows = check_dlf_update_rows(
        root,
        "build/spice_dlf_update_xyce_kp32/dlf_update_check.csv",
        32,
    )
    full32_rows = check_dlf_full_overlap_rows(
        root,
        "build/spice_dlf_update_xyce_kp32_full_overlap/dlf_update_check.csv",
    )
    signoff_nl_rows, signoff_nl_instance_counts = check_dlf_signoff_nl_rows(
        root,
        "build/spice_dlf_update_signoff_nl_kp32_fast/dlf_update_check.csv",
    )
    (
        signoff_spef_rows,
        signoff_spef_instance_counts,
        signoff_spef_cap_counts,
        signoff_spef_cap_totals_ff,
    ) = check_dlf_signoff_spef_rows(
        root,
        "build/spice_dlf_update_signoff_spef_kp32_fast/dlf_update_check.csv",
    )
    (
        signoff_spef_rc_rows,
        signoff_spef_rc_instance_counts,
        signoff_spef_rc_cap_counts,
        signoff_spef_rc_resistor_counts,
        signoff_spef_rc_pin_node_counts,
        signoff_spef_rc_cap_totals_ff,
    ) = check_dlf_signoff_spef_rc_rows(
        root,
        "build/spice_dlf_update_signoff_spef_rc_kp32_fast/dlf_update_check.csv",
    )
    bbpd_rcx_rows = check_dlf_bbpd_rcx_rows(
        root,
        "build/spice_bbpd_dlf_integration_xyce_kp32/dlf_update_check.csv",
        "cone",
    )
    full_bbpd_rcx_rows = check_dlf_bbpd_rcx_rows(
        root,
        "build/spice_bbpd_dlf_integration_full_xyce_kp32/dlf_update_check.csv",
        "full",
    )
    (
        bbpd_rcx_signoff_spef_rc_rows,
        bbpd_rcx_signoff_spef_rc_instance_counts,
        bbpd_rcx_signoff_spef_rc_cap_counts,
        bbpd_rcx_signoff_spef_rc_resistor_counts,
        bbpd_rcx_signoff_spef_rc_pin_node_counts,
        bbpd_rcx_signoff_spef_rc_cap_totals_ff,
    ) = check_dlf_bbpd_rcx_signoff_spef_rc_rows(
        root,
        "build/spice_bbpd_dlf_integration_signoff_spef_rc_kp32/dlf_update_check.csv",
    )
    return {
        "ki": 255,
        "checked_kp": [16, 32],
        "kp16_static_rows": len(static16_rows),
        "kp16_update_rows": len(update16_rows),
        "kp32_static_rows": len(static32_rows),
        "kp32_update_rows": len(update32_rows),
        "kp32_full_core_overlap_rows": len(full32_rows),
        "kp32_signoff_nl_update_rows": len(signoff_nl_rows),
        "kp32_signoff_nl_cone_cells": signoff_nl_instance_counts,
        "kp32_signoff_spef_update_rows": len(signoff_spef_rows),
        "kp32_signoff_spef_cone_cells": signoff_spef_instance_counts,
        "kp32_signoff_spef_cap_nets": signoff_spef_cap_counts,
        "kp32_signoff_spef_cap_total_ff": signoff_spef_cap_totals_ff,
        "kp32_signoff_spef_rc_update_rows": len(signoff_spef_rc_rows),
        "kp32_signoff_spef_rc_cone_cells": signoff_spef_rc_instance_counts,
        "kp32_signoff_spef_rc_cap_nodes": signoff_spef_rc_cap_counts,
        "kp32_signoff_spef_rc_resistors": signoff_spef_rc_resistor_counts,
        "kp32_signoff_spef_rc_pin_nodes": signoff_spef_rc_pin_node_counts,
        "kp32_signoff_spef_rc_cap_total_ff": signoff_spef_rc_cap_totals_ff,
        "kp32_bbpd_rcx_integration_rows": len(bbpd_rcx_rows),
        "kp32_full_core_bbpd_rcx_integration_rows": len(full_bbpd_rcx_rows),
        "kp32_bbpd_rcx_signoff_spef_rc_rows": len(bbpd_rcx_signoff_spef_rc_rows),
        "kp32_bbpd_rcx_signoff_spef_rc_x_instances": bbpd_rcx_signoff_spef_rc_instance_counts,
        "kp32_bbpd_rcx_signoff_spef_rc_cap_nodes": bbpd_rcx_signoff_spef_rc_cap_counts,
        "kp32_bbpd_rcx_signoff_spef_rc_resistors": bbpd_rcx_signoff_spef_rc_resistor_counts,
        "kp32_bbpd_rcx_signoff_spef_rc_pin_nodes": bbpd_rcx_signoff_spef_rc_pin_node_counts,
        "kp32_bbpd_rcx_signoff_spef_rc_cap_total_ff": bbpd_rcx_signoff_spef_rc_cap_totals_ff,
    }


def check_mapped_loop_smoke(
    root,
    relpath="build/spice_pll_mapped_loop_smoke/mapped_loop_check.csv",
    expected_scope="full",
    min_instance_count=None,
    min_skipped_physical_only_cells=None,
    expected_mpi_procs=None,
    require_xyce_command=None,
    expected_ki=255,
    expected_kp=32,
    expected_ndiv=2,
    expected_dlf_frac_width=None,
    expected_phase=None,
    expected_start_meas_ns=None,
    expected_end_meas_ns=None,
    expected_enable_ns=None,
    expected_clear_width_ns=None,
    expected_code_observer_source=None,
    expected_hardtop_spef_mode=None,
    min_hardtop_spef_cap_nets=None,
    min_hardtop_spef_cap_total_ff=None,
    min_hardtop_spef_dco_therm_nets=None,
):
    rows = read_csv(
        require_path(root, relpath)
    )
    if {row["case"] for row in rows} != {"low_start", "high_start"}:
        raise ValueError("mapped loop smoke does not cover both rail-start cases")
    require_all_pass(rows)

    expected_phase = expected_phase or {"low_start": 0.0, "high_start": 0.25}
    response_codes = {}
    for row in rows:
        case = row["case"]
        if row.get("simulator") != "xyce":
            raise ValueError(f"mapped loop row is not Xyce: {row}")
        if expected_mpi_procs is not None and to_int(row, "xyce_mpi_procs") != expected_mpi_procs:
            raise ValueError(f"mapped loop row has wrong Xyce MPI process count: {row}")
        if require_xyce_command is not None and require_xyce_command not in row.get("xyce_command", ""):
            raise ValueError(f"mapped loop row does not record expected Xyce command: {row}")
        if row.get("bbpd_impl") != "postlayout" or row.get("digital_scope") != expected_scope:
            raise ValueError(f"mapped loop row has wrong implementation scope: {row}")
        if min_instance_count is not None:
            if to_int(row, "mapped_instance_count") < min_instance_count:
                raise ValueError(f"mapped loop row has too few mapped instances: {row}")
        if min_skipped_physical_only_cells is not None:
            if to_int(row, "skipped_physical_only_cells") < min_skipped_physical_only_cells:
                raise ValueError(f"mapped loop row did not skip expected physical-only cells: {row}")
        if row.get("dco_model") != "piecewise5_behavioral":
            raise ValueError(f"mapped loop row has wrong DCO model: {row}")
        if expected_code_observer_source is not None:
            if row.get("code_observer_source") != expected_code_observer_source:
                raise ValueError(f"mapped loop row has wrong code observer source: {row}")
        if expected_hardtop_spef_mode is not None:
            if row.get("hardtop_spef_mode") != expected_hardtop_spef_mode:
                raise ValueError(f"mapped loop row has wrong hard-top SPEF mode: {row}")
            if min_hardtop_spef_cap_nets is not None:
                if to_int(row, "hardtop_spef_cap_nets") < min_hardtop_spef_cap_nets:
                    raise ValueError(f"mapped loop row has too few hard-top SPEF cap nets: {row}")
            if min_hardtop_spef_cap_total_ff is not None:
                if to_float(row, "hardtop_spef_cap_total_ff") < min_hardtop_spef_cap_total_ff:
                    raise ValueError(f"mapped loop row has too little hard-top SPEF cap: {row}")
            if min_hardtop_spef_dco_therm_nets is not None:
                if to_int(row, "hardtop_spef_dco_therm_nets") < min_hardtop_spef_dco_therm_nets:
                    raise ValueError(f"mapped loop row has too few hard-top DCO thermometer nets: {row}")
            netlist_path = Path(row.get("netlist", "")).expanduser()
            if not netlist_path.is_file():
                raise ValueError(f"mapped loop row missing generated deck: {row}")
            cap_count = count_hardtop_spef_caps(netlist_path)
            if cap_count != to_int(row, "hardtop_spef_cap_nodes"):
                raise ValueError(f"hard-top SPEF cap count mismatch in {netlist_path}: {cap_count} vs {row}")
        if (
            to_int(row, "ki") != expected_ki
            or to_int(row, "kp") != expected_kp
            or to_int(row, "ndiv") != expected_ndiv
        ):
            raise ValueError(f"mapped loop row has wrong loop setting: {row}")
        if expected_dlf_frac_width is not None and to_int(row, "dlf_frac_width") != expected_dlf_frac_width:
            raise ValueError(f"mapped loop row has wrong DLF fractional width: {row}")
        if expected_start_meas_ns is not None and abs(to_float(row, "start_meas_ns") - expected_start_meas_ns) > 1e-9:
            raise ValueError(f"mapped loop row has wrong start window: {row}")
        if expected_end_meas_ns is not None and abs(to_float(row, "end_meas_ns") - expected_end_meas_ns) > 1e-9:
            raise ValueError(f"mapped loop row has wrong end window: {row}")
        if expected_enable_ns is not None and abs(to_float(row, "enable_ns") - expected_enable_ns) > 1e-9:
            raise ValueError(f"mapped loop row has wrong enable timing: {row}")
        if expected_clear_width_ns is not None and abs(to_float(row, "clear_width_ns") - expected_clear_width_ns) > 1e-9:
            raise ValueError(f"mapped loop row has wrong clear timing: {row}")
        if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
            raise ValueError(f"mapped loop row did not finish cleanly: {row}")
        phase = to_float(row, "initial_dco_phase_cycles")
        if abs(phase - expected_phase[case]) > 1e-9:
            raise ValueError(f"mapped loop row has unexpected initial phase: {row}")
        start = to_float(row, "start_code")
        response = response_code(row)
        if case == "low_start" and not (abs(start) <= 2.0 and response > start + 1.0):
            raise ValueError("mapped low-start smoke did not increase code")
        if case == "high_start" and not (abs(start - 255.0) <= 2.0 and response < start - 1.0):
            raise ValueError("mapped high-start smoke did not decrease code")
        response_codes[case] = response

    return {
        "rows": len(rows),
        "digital_scope": expected_scope,
        "bbpd_impl": "postlayout",
        "dco_model": "piecewise5_behavioral",
        "code_observer_source": expected_code_observer_source,
        "low_start_response_code": response_codes["low_start"],
        "high_start_response_code": response_codes["high_start"],
        "mapped_instance_count": (
            None
            if min_instance_count is None
            else min(to_int(row, "mapped_instance_count") for row in rows)
        ),
        "skipped_physical_only_cells": (
            None
            if min_skipped_physical_only_cells is None
            else min(to_int(row, "skipped_physical_only_cells") for row in rows)
        ),
        "hardtop_spef_mode": expected_hardtop_spef_mode,
        "hardtop_spef_cap_nets": (
            None
            if expected_hardtop_spef_mode is None
            else min(to_int(row, "hardtop_spef_cap_nets") for row in rows)
        ),
        "hardtop_spef_cap_total_ff": (
            None
            if expected_hardtop_spef_mode is None
            else min(to_float(row, "hardtop_spef_cap_total_ff") for row in rows)
        ),
    }


def check_einvp_hardtop_spef_behavioral_lock_row(
    root,
    relpath,
    *,
    expected_case,
    expected_scope,
    expected_phase,
    expected_end_meas_ns,
    expected_lock_start_ns,
    min_tail_rises,
    startup_freq_range,
):
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 1:
        raise ValueError(f"{relpath} expected 1 row, found {len(rows)}")
    require_all_pass(rows)
    row = rows[0]

    if row.get("case") != expected_case:
        raise ValueError(f"{relpath} has wrong case: {row}")
    if row.get("simulator") != "xyce" or to_int(row, "xyce_mpi_procs") != 16:
        raise ValueError(f"{relpath} has unexpected Xyce process count: {row}")
    if "-linsolv KLU" not in row.get("xyce_command", ""):
        raise ValueError(f"{relpath} does not record KLU: {row}")
    if row.get("bbpd_impl") != "postlayout" or row.get("digital_scope") != expected_scope:
        raise ValueError(f"{relpath} has wrong implementation scope: {row}")
    if row.get("dco_model") != "piecewise5_behavioral" or row.get("check_mode") != "lock_window":
        raise ValueError(f"{relpath} has wrong DCO/check mode: {row}")
    if row.get("code_observer_source") != "dco_therm":
        raise ValueError(f"{relpath} has wrong code observer: {row}")
    if to_int(row, "mapped_instance_count") < 2000:
        raise ValueError(f"{relpath} has too few mapped instances: {row}")
    if to_int(row, "skipped_physical_only_cells") != 4138:
        raise ValueError(f"{relpath} skipped unexpected cells: {row}")
    if to_int(row, "ki") != 160 or to_int(row, "kp") != 8 or to_int(row, "ndiv") != 2:
        raise ValueError(f"{relpath} has wrong loop setting: {row}")
    if to_int(row, "dlf_frac_width") != 6:
        raise ValueError(f"{relpath} has wrong DLF fractional width: {row}")
    if abs(to_float(row, "target_freq_mhz") - 60.174879350325796) > 1e-6:
        raise ValueError(f"{relpath} has wrong target frequency: {row}")
    if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
        raise ValueError(f"{relpath} did not finish cleanly: {row}")
    if abs(to_float(row, "initial_dco_phase_cycles") - expected_phase) > 1e-9:
        raise ValueError(f"{relpath} has unexpected initial phase: {row}")
    if abs(to_float(row, "enable_ns") - 85.0) > 1e-9 or abs(to_float(row, "clear_width_ns") - 60.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong enable/reset timing: {row}")
    if abs(to_float(row, "end_meas_ns") - expected_end_meas_ns) > 1e-9:
        raise ValueError(f"{relpath} has wrong end measurement time: {row}")
    if abs(to_float(row, "lock_meas_start_ns") - expected_lock_start_ns) > 1e-9:
        raise ValueError(f"{relpath} has wrong lock measurement start: {row}")
    if row.get("lock_code_check") != "window":
        raise ValueError(f"{relpath} has wrong lock code check: {row}")
    if to_float(row, "lock_min_code") != 112.0 or to_float(row, "lock_max_code") != 144.0:
        raise ValueError(f"{relpath} has wrong lock code window: {row}")

    if row.get("hardtop_spef_mode") != "lumped_cap":
        raise ValueError(f"{relpath} has wrong hard-top SPEF mode: {row}")
    if "IntegerPLL_HardMacroTop_EINVP" not in row.get("hardtop_spef_path", ""):
        raise ValueError(f"{relpath} does not use the EINVP hard-top SPEF: {row}")
    if to_int(row, "hardtop_spef_cap_nets") < 261:
        raise ValueError(f"{relpath} has too few hard-top SPEF nets: {row}")
    if to_int(row, "hardtop_spef_cap_nodes") < 261:
        raise ValueError(f"{relpath} has too few hard-top SPEF cap nodes: {row}")
    if to_int(row, "hardtop_spef_dco_therm_nets") < 255:
        raise ValueError(f"{relpath} has too few DCO thermometer nets: {row}")
    if to_float(row, "hardtop_spef_cap_total_ff") < 25000.0:
        raise ValueError(f"{relpath} has too little hard-top SPEF capacitance: {row}")

    netlist_path = Path(row.get("netlist", "")).expanduser()
    if not netlist_path.is_file():
        raise ValueError(f"{relpath} missing generated deck: {row}")
    cap_count = count_hardtop_spef_caps(netlist_path)
    if cap_count != to_int(row, "hardtop_spef_cap_nodes"):
        raise ValueError(f"{relpath} hard-top SPEF cap count mismatch: {cap_count} vs {row}")

    start_code = to_float(row, "start_code")
    end_code = to_float(row, "end_code")
    response = response_code(row)
    lock_min = to_float(row, "lock_observed_min_code")
    lock_max = to_float(row, "lock_observed_max_code")
    if expected_case == "low_start":
        if abs(start_code) > 0.5:
            raise ValueError(f"{relpath} did not start at low rail: {row}")
    else:
        if abs(start_code - 255.0) > 0.5:
            raise ValueError(f"{relpath} did not start at high rail: {row}")
    if not (112.0 <= end_code <= 144.0 and 112.0 <= response <= 144.0):
        raise ValueError(f"{relpath} did not end/respond inside lock window: {row}")
    if not (112.0 <= lock_min <= lock_max <= 144.0):
        raise ValueError(f"{relpath} lock window leaves expected code band: {row}")

    tail_rises = to_int(row, "tail_rise_count")
    tail_freq = to_float(row, "tail_freq_mhz")
    tail_error = to_float(row, "tail_abs_error_mhz")
    if tail_rises < min_tail_rises or tail_error > 1.0:
        raise ValueError(f"{relpath} lacks a good tail frequency window: {row}")
    startup_freq = to_float(row, "startup_freq_mhz")
    if not (startup_freq_range[0] <= startup_freq <= startup_freq_range[1]):
        raise ValueError(f"{relpath} has unexpected startup frequency: {row}")

    log_path = Path(row.get("log", "")).expanduser()
    if not log_path.is_file():
        raise ValueError(f"{relpath} missing Xyce log: {log_path}")
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    for required in (
        "Total Devices                                          28740",
        "Number of Unknowns = 95845",
        "Timing summary of 16 processors",
    ):
        if required not in log_text:
            raise ValueError(f"{relpath} log does not contain {required!r}")
    elapsed_s = xyce_elapsed_run_time_s(log_text)
    if elapsed_s is None or elapsed_s <= 0.0:
        raise ValueError(f"{relpath} log lacks elapsed runtime: {log_path}")

    return {
        "case": expected_case,
        "digital_scope": expected_scope,
        "mapped_instance_count": to_int(row, "mapped_instance_count"),
        "skipped_physical_only_cells": to_int(row, "skipped_physical_only_cells"),
        "hardtop_spef_cap_nets": to_int(row, "hardtop_spef_cap_nets"),
        "hardtop_spef_cap_total_ff": to_float(row, "hardtop_spef_cap_total_ff"),
        "start_code": start_code,
        "end_code": end_code,
        "response_code": response,
        "lock_observed_min_code": lock_min,
        "lock_observed_max_code": lock_max,
        "tail_rise_count": tail_rises,
        "tail_freq_mhz": tail_freq,
        "tail_abs_error_mhz": tail_error,
        "startup_freq_mhz": startup_freq,
        "elapsed_s": elapsed_s,
    }


def check_final_signoff_hardtop_einvp_spef_behavioral_lock_low_mpi16_klu(root):
    return check_einvp_hardtop_spef_behavioral_lock_row(
        root,
        "build/spice_pll_final_force127_hardtop_einvp_spef_therm_lock_low_760ns_mpi16_klu/mapped_loop_check.csv",
        expected_case="low_start",
        expected_scope="final_signoff_force127_hardtop_einvp_spef_therm_lock_low_diag",
        expected_phase=0.0,
        expected_end_meas_ns=759.0,
        expected_lock_start_ns=650.0,
        min_tail_rises=4,
        startup_freq_range=(54.0, 57.0),
    )


def check_final_signoff_hardtop_einvp_spef_behavioral_lock_high_mpi16_klu(root):
    return check_einvp_hardtop_spef_behavioral_lock_row(
        root,
        "build/spice_pll_final_force127_hardtop_einvp_spef_therm_lock_high_620ns_mpi16_klu/mapped_loop_check.csv",
        expected_case="high_start",
        expected_scope="final_signoff_force127_hardtop_einvp_spef_therm_lock_high_diag",
        expected_phase=0.5,
        expected_end_meas_ns=619.0,
        expected_lock_start_ns=500.0,
        min_tail_rises=5,
        startup_freq_range=(63.0, 66.0),
    )


def check_extracted_dco_startup_row(
    root,
    relpath,
    *,
    expected_mpi_procs,
    expected_scope="full",
    min_instance_count=900,
    expected_skipped_physical_only_cells=0,
    expected_ki=255,
    expected_kp=32,
    expected_ndiv=2,
    expected_dlf_frac_width=None,
    expected_initial_phase=0.0,
    expected_startup_meas_start_ns=15.0,
    expected_hardtop_spef_mode=None,
    min_hardtop_spef_cap_nets=None,
    min_hardtop_spef_cap_nodes=None,
    min_hardtop_spef_resistors=None,
    min_hardtop_spef_pin_substitutions=None,
    min_hardtop_spef_dco_therm_nets=None,
    min_hardtop_spef_cap_total_ff=None,
    require_xyce_command=None,
    require_log_text=None,
):
    rows = read_csv(
        require_path(
            root,
            relpath,
        )
    )
    if len(rows) != 1:
        raise ValueError(f"{relpath} expected 1 row, found {len(rows)}")
    require_all_pass(rows)

    row = rows[0]
    if row.get("case") != "low_start":
        raise ValueError(f"{relpath} has wrong case: {row}")
    if row.get("simulator") != "xyce" or to_int(row, "xyce_mpi_procs") != expected_mpi_procs:
        raise ValueError(f"{relpath} has unexpected Xyce process count: {row}")
    if require_xyce_command is not None and require_xyce_command not in row.get("xyce_command", ""):
        raise ValueError(f"{relpath} does not record expected Xyce command: {row}")
    if row.get("bbpd_impl") != "postlayout" or row.get("digital_scope") != expected_scope:
        raise ValueError(f"{relpath} has wrong implementation scope: {row}")
    if row.get("dco_model") != "postlayout_rcx" or row.get("check_mode") != "startup":
        raise ValueError(f"{relpath} has wrong DCO/check mode: {row}")
    if to_int(row, "mapped_instance_count") < min_instance_count:
        raise ValueError(f"{relpath} has too few mapped instances: {row}")
    if to_int(row, "skipped_physical_only_cells") != expected_skipped_physical_only_cells:
        raise ValueError(f"{relpath} skipped unexpected cells: {row}")
    if (
        to_int(row, "ki") != expected_ki
        or to_int(row, "kp") != expected_kp
        or to_int(row, "ndiv") != expected_ndiv
    ):
        raise ValueError(f"{relpath} has wrong loop setting: {row}")
    if expected_dlf_frac_width is not None and to_int(row, "dlf_frac_width") != expected_dlf_frac_width:
        raise ValueError(f"{relpath} has wrong DLF fractional width: {row}")
    if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
        raise ValueError(f"{relpath} did not finish cleanly: {row}")
    if abs(to_float(row, "initial_dco_phase_cycles") - expected_initial_phase) > 1e-9:
        raise ValueError(f"{relpath} has unexpected initial phase: {row}")
    if abs(to_float(row, "startup_meas_start_ns") - expected_startup_meas_start_ns) > 1e-9:
        raise ValueError(f"{relpath} has unexpected startup window: {row}")
    if expected_hardtop_spef_mode is not None:
        if row.get("hardtop_spef_mode") != expected_hardtop_spef_mode:
            raise ValueError(f"{relpath} has wrong hard-top SPEF mode: {row}")
        if min_hardtop_spef_cap_nets is not None:
            if to_int(row, "hardtop_spef_cap_nets") < min_hardtop_spef_cap_nets:
                raise ValueError(f"{relpath} has too few hard-top SPEF nets: {row}")
        if min_hardtop_spef_cap_nodes is not None:
            if to_int(row, "hardtop_spef_cap_nodes") < min_hardtop_spef_cap_nodes:
                raise ValueError(f"{relpath} has too few hard-top SPEF cap nodes: {row}")
        if min_hardtop_spef_resistors is not None:
            if to_int(row, "hardtop_spef_resistors") < min_hardtop_spef_resistors:
                raise ValueError(f"{relpath} has too few hard-top SPEF resistors: {row}")
        if min_hardtop_spef_pin_substitutions is not None:
            if to_int(row, "hardtop_spef_pin_substitutions") < min_hardtop_spef_pin_substitutions:
                raise ValueError(f"{relpath} has too few hard-top pin substitutions: {row}")
        if min_hardtop_spef_dco_therm_nets is not None:
            if to_int(row, "hardtop_spef_dco_therm_nets") < min_hardtop_spef_dco_therm_nets:
                raise ValueError(f"{relpath} has too few hard-top DCO thermometer nets: {row}")
        if min_hardtop_spef_cap_total_ff is not None:
            if to_float(row, "hardtop_spef_cap_total_ff") < min_hardtop_spef_cap_total_ff:
                raise ValueError(f"{relpath} has too little hard-top SPEF capacitance: {row}")
        netlist_path = Path(row.get("netlist", "")).expanduser()
        if not netlist_path.is_file():
            raise ValueError(f"{relpath} missing generated deck: {row}")
        cap_count = count_hardtop_spef_caps(netlist_path)
        if cap_count != to_int(row, "hardtop_spef_cap_nodes"):
            raise ValueError(f"{relpath} hard-top SPEF cap count mismatch: {cap_count} vs {row}")
        resistor_count = count_hardtop_spef_resistors(netlist_path)
        if resistor_count != to_int(row, "hardtop_spef_resistors"):
            raise ValueError(f"{relpath} hard-top SPEF resistor count mismatch: {resistor_count} vs {row}")
    startup_rises = to_int(row, "startup_rise_count")
    startup_period = to_float(row, "startup_period_ns")
    startup_freq = to_float(row, "startup_freq_mhz")
    if startup_rises < 2:
        raise ValueError(f"{relpath} has too few PLLOUT rises: {row}")
    if not (20.0 <= startup_period <= 23.0):
        raise ValueError(f"{relpath} has unexpected period: {row}")
    if not (45.0 <= startup_freq <= 48.0):
        raise ValueError(f"{relpath} has unexpected frequency: {row}")

    log_path = Path(row.get("log", "")).expanduser()
    if require_log_text is not None:
        if not log_path.is_file():
            raise ValueError(f"{relpath} missing Xyce log: {log_path}")
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        if require_log_text not in log_text:
            raise ValueError(f"{relpath} log does not contain {require_log_text!r}")

    return {
        "rows": len(rows),
        "digital_scope": expected_scope,
        "bbpd_impl": "postlayout",
        "dco_model": "postlayout_rcx",
        "xyce_mpi_procs": expected_mpi_procs,
        "mapped_instance_count": to_int(row, "mapped_instance_count"),
        "skipped_physical_only_cells": to_int(row, "skipped_physical_only_cells"),
        "hardtop_spef_mode": row.get("hardtop_spef_mode", ""),
        "hardtop_spef_cap_nets": row.get("hardtop_spef_cap_nets", ""),
        "hardtop_spef_cap_nodes": row.get("hardtop_spef_cap_nodes", ""),
        "hardtop_spef_resistors": row.get("hardtop_spef_resistors", ""),
        "hardtop_spef_pin_substitutions": row.get("hardtop_spef_pin_substitutions", ""),
        "hardtop_spef_cap_total_ff": row.get("hardtop_spef_cap_total_ff", ""),
        "startup_rise_count": startup_rises,
        "startup_period_ns": startup_period,
        "startup_freq_mhz": startup_freq,
    }


def check_extracted_dco_startup_smoke(root):
    return check_extracted_dco_startup_row(
        root,
        "build/spice_pll_mapped_loop_extracted_dco_startup_low_50ns_serial/mapped_loop_check.csv",
        expected_mpi_procs=1,
    )


def check_extracted_dco_startup_mpi_klu_smoke(root):
    return check_extracted_dco_startup_row(
        root,
        "build/spice_pll_mapped_loop_extracted_dco_startup_low_50ns_mpi4_klu/mapped_loop_check.csv",
        expected_mpi_procs=4,
        require_xyce_command="-linsolv KLU",
        require_log_text="Timing summary of 4 processors",
    )


def check_final_signoff_hardtop_spef_rc_extracted_dco_startup_mpi16_klu(root):
    return check_extracted_dco_startup_row(
        root,
        "build/spice_pll_final_force127_hardtop_spef_rc_extracted_dco_startup_low_50ns_mpi16_klu/mapped_loop_check.csv",
        expected_mpi_procs=16,
        expected_scope="final_signoff_force127_hardtop_spef_rc_extracted_dco_diag",
        min_instance_count=2000,
        expected_skipped_physical_only_cells=4138,
        expected_ki=160,
        expected_kp=8,
        expected_dlf_frac_width=6,
        expected_hardtop_spef_mode="distributed_rc",
        min_hardtop_spef_cap_nets=261,
        min_hardtop_spef_cap_nodes=1700,
        min_hardtop_spef_resistors=1600,
        min_hardtop_spef_pin_substitutions=260,
        min_hardtop_spef_dco_therm_nets=255,
        min_hardtop_spef_cap_total_ff=27000.0,
        require_xyce_command="-linsolv KLU",
        require_log_text="Timing summary of 16 processors",
    )


def check_final_signoff_hardtop_spef_rc_extracted_dco_motion_low_mpi16_klu(root):
    relpath = (
        "build/spice_pll_final_force127_hardtop_spef_rc_extracted_dco_motion_low_100ns_mpi16_klu/"
        "mapped_loop_check.csv"
    )
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 1:
        raise ValueError(f"{relpath} expected 1 row, found {len(rows)}")
    require_all_pass(rows)
    row = rows[0]

    if row.get("case") != "low_start":
        raise ValueError(f"{relpath} has wrong case: {row}")
    if row.get("simulator") != "xyce" or to_int(row, "xyce_mpi_procs") != 16:
        raise ValueError(f"{relpath} has unexpected Xyce process count: {row}")
    if "-linsolv KLU" not in row.get("xyce_command", ""):
        raise ValueError(f"{relpath} does not record KLU: {row}")
    if row.get("bbpd_impl") != "postlayout":
        raise ValueError(f"{relpath} has wrong BBPD implementation: {row}")
    if row.get("digital_scope") != "final_signoff_force127_hardtop_spef_rc_extracted_dco_motion_low_diag":
        raise ValueError(f"{relpath} has wrong digital scope: {row}")
    if row.get("dco_model") != "postlayout_rcx" or row.get("check_mode") != "motion":
        raise ValueError(f"{relpath} has wrong DCO/check mode: {row}")
    if to_int(row, "mapped_instance_count") < 2000:
        raise ValueError(f"{relpath} has too few mapped instances: {row}")
    if to_int(row, "skipped_physical_only_cells") != 4138:
        raise ValueError(f"{relpath} skipped unexpected cells: {row}")
    if to_int(row, "ki") != 160 or to_int(row, "kp") != 8 or to_int(row, "ndiv") != 2:
        raise ValueError(f"{relpath} has wrong loop setting: {row}")
    if to_int(row, "dlf_frac_width") != 6:
        raise ValueError(f"{relpath} has wrong DLF fractional width: {row}")
    if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
        raise ValueError(f"{relpath} did not finish cleanly: {row}")
    if abs(to_float(row, "initial_dco_phase_cycles")) > 1e-9:
        raise ValueError(f"{relpath} has unexpected initial phase: {row}")
    if abs(to_float(row, "start_meas_ns") - 84.0) > 1e-9 or abs(to_float(row, "end_meas_ns") - 99.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong measurement window: {row}")
    if abs(to_float(row, "enable_ns") - 85.0) > 1e-9 or abs(to_float(row, "clear_width_ns") - 60.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong enable/reset timing: {row}")

    if row.get("hardtop_spef_mode") != "distributed_rc":
        raise ValueError(f"{relpath} has wrong hard-top SPEF mode: {row}")
    if to_int(row, "hardtop_spef_cap_nets") < 261:
        raise ValueError(f"{relpath} has too few hard-top SPEF nets: {row}")
    if to_int(row, "hardtop_spef_cap_nodes") < 1700:
        raise ValueError(f"{relpath} has too few hard-top SPEF cap nodes: {row}")
    if to_int(row, "hardtop_spef_resistors") < 1600:
        raise ValueError(f"{relpath} has too few hard-top SPEF resistors: {row}")
    if to_int(row, "hardtop_spef_pin_substitutions") < 260:
        raise ValueError(f"{relpath} has too few hard-top pin substitutions: {row}")
    if to_int(row, "hardtop_spef_dco_therm_nets") < 255:
        raise ValueError(f"{relpath} has too few hard-top DCO thermometer nets: {row}")
    if to_float(row, "hardtop_spef_cap_total_ff") < 27000.0:
        raise ValueError(f"{relpath} has too little hard-top SPEF capacitance: {row}")

    netlist_path = Path(row.get("netlist", "")).expanduser()
    if not netlist_path.is_file():
        raise ValueError(f"{relpath} missing generated deck: {row}")
    cap_count = count_hardtop_spef_caps(netlist_path)
    if cap_count != to_int(row, "hardtop_spef_cap_nodes"):
        raise ValueError(f"{relpath} hard-top SPEF cap count mismatch: {cap_count} vs {row}")
    resistor_count = count_hardtop_spef_resistors(netlist_path)
    if resistor_count != to_int(row, "hardtop_spef_resistors"):
        raise ValueError(f"{relpath} hard-top SPEF resistor count mismatch: {resistor_count} vs {row}")

    start_code = to_float(row, "start_code")
    end_code = to_float(row, "end_code")
    response_code = to_float(row, "response_code")
    observed_min_code = to_float(row, "observed_min_code")
    observed_max_code = to_float(row, "observed_max_code")
    if abs(start_code) > 0.5 or observed_min_code > 0.5:
        raise ValueError(f"{relpath} did not start at low rail: {row}")
    if end_code < 2.0 or response_code < 2.0 or observed_max_code < 2.0:
        raise ValueError(f"{relpath} lacks low-start upward first motion: {row}")
    startup_rises = to_int(row, "startup_rise_count")
    startup_freq = to_float(row, "startup_freq_mhz")
    if startup_rises < 4 or not (45.0 <= startup_freq <= 48.0):
        raise ValueError(f"{relpath} has unexpected oscillator startup: {row}")

    log_path = Path(row.get("log", "")).expanduser()
    if not log_path.is_file():
        raise ValueError(f"{relpath} missing Xyce log: {log_path}")
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    for required in (
        "Total Devices                                          63443",
        "Number of Unknowns = 182651",
        "Timing summary of 16 processors",
    ):
        if required not in log_text:
            raise ValueError(f"{relpath} log does not contain {required!r}")

    elapsed_s = xyce_elapsed_run_time_s(log_text)
    if elapsed_s is None or elapsed_s <= 0.0:
        raise ValueError(f"{relpath} log lacks elapsed runtime: {log_path}")

    return {
        "rows": len(rows),
        "digital_scope": row.get("digital_scope"),
        "bbpd_impl": "postlayout",
        "dco_model": "postlayout_rcx",
        "xyce_mpi_procs": 16,
        "mapped_instance_count": to_int(row, "mapped_instance_count"),
        "skipped_physical_only_cells": to_int(row, "skipped_physical_only_cells"),
        "hardtop_spef_mode": row.get("hardtop_spef_mode", ""),
        "hardtop_spef_cap_nets": row.get("hardtop_spef_cap_nets", ""),
        "hardtop_spef_cap_nodes": row.get("hardtop_spef_cap_nodes", ""),
        "hardtop_spef_resistors": row.get("hardtop_spef_resistors", ""),
        "hardtop_spef_pin_substitutions": row.get("hardtop_spef_pin_substitutions", ""),
        "hardtop_spef_cap_total_ff": row.get("hardtop_spef_cap_total_ff", ""),
        "start_code": start_code,
        "end_code": end_code,
        "response_code": response_code,
        "startup_rise_count": startup_rises,
        "startup_freq_mhz": startup_freq,
        "elapsed_s": elapsed_s,
    }


def check_final_signoff_hardtop_spef_rc_extracted_dco_motion_high_mpi16_klu(root):
    relpath = (
        "build/spice_pll_final_force127_hardtop_spef_rc_extracted_dco_motion_high_100ns_mpi16_klu/"
        "mapped_loop_check.csv"
    )
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 1:
        raise ValueError(f"{relpath} expected 1 row, found {len(rows)}")
    require_all_pass(rows)
    row = rows[0]

    if row.get("case") != "high_start":
        raise ValueError(f"{relpath} has wrong case: {row}")
    if row.get("simulator") != "xyce" or to_int(row, "xyce_mpi_procs") != 16:
        raise ValueError(f"{relpath} has unexpected Xyce process count: {row}")
    if "-linsolv KLU" not in row.get("xyce_command", ""):
        raise ValueError(f"{relpath} does not record KLU: {row}")
    if row.get("bbpd_impl") != "postlayout":
        raise ValueError(f"{relpath} has wrong BBPD implementation: {row}")
    if row.get("digital_scope") != "final_signoff_force127_hardtop_spef_rc_extracted_dco_motion_high_diag":
        raise ValueError(f"{relpath} has wrong digital scope: {row}")
    if row.get("dco_model") != "postlayout_rcx" or row.get("check_mode") != "motion":
        raise ValueError(f"{relpath} has wrong DCO/check mode: {row}")
    if to_int(row, "mapped_instance_count") < 2000:
        raise ValueError(f"{relpath} has too few mapped instances: {row}")
    if to_int(row, "skipped_physical_only_cells") != 4138:
        raise ValueError(f"{relpath} skipped unexpected cells: {row}")
    if to_int(row, "ki") != 160 or to_int(row, "kp") != 8 or to_int(row, "ndiv") != 2:
        raise ValueError(f"{relpath} has wrong loop setting: {row}")
    if to_int(row, "dlf_frac_width") != 6:
        raise ValueError(f"{relpath} has wrong DLF fractional width: {row}")
    if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
        raise ValueError(f"{relpath} did not finish cleanly: {row}")
    if abs(to_float(row, "initial_dco_phase_cycles") - 0.5) > 1e-9:
        raise ValueError(f"{relpath} has unexpected initial phase: {row}")
    if abs(to_float(row, "start_meas_ns") - 84.0) > 1e-9 or abs(to_float(row, "end_meas_ns") - 99.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong measurement window: {row}")
    if abs(to_float(row, "enable_ns") - 85.0) > 1e-9 or abs(to_float(row, "clear_width_ns") - 60.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong enable/reset timing: {row}")

    if row.get("hardtop_spef_mode") != "distributed_rc":
        raise ValueError(f"{relpath} has wrong hard-top SPEF mode: {row}")
    if to_int(row, "hardtop_spef_cap_nets") < 261:
        raise ValueError(f"{relpath} has too few hard-top SPEF nets: {row}")
    if to_int(row, "hardtop_spef_cap_nodes") < 1700:
        raise ValueError(f"{relpath} has too few hard-top SPEF cap nodes: {row}")
    if to_int(row, "hardtop_spef_resistors") < 1600:
        raise ValueError(f"{relpath} has too few hard-top SPEF resistors: {row}")
    if to_int(row, "hardtop_spef_pin_substitutions") < 260:
        raise ValueError(f"{relpath} has too few hard-top pin substitutions: {row}")
    if to_int(row, "hardtop_spef_dco_therm_nets") < 255:
        raise ValueError(f"{relpath} has too few hard-top DCO thermometer nets: {row}")
    if to_float(row, "hardtop_spef_cap_total_ff") < 27000.0:
        raise ValueError(f"{relpath} has too little hard-top SPEF capacitance: {row}")

    netlist_path = Path(row.get("netlist", "")).expanduser()
    if not netlist_path.is_file():
        raise ValueError(f"{relpath} missing generated deck: {row}")
    cap_count = count_hardtop_spef_caps(netlist_path)
    if cap_count != to_int(row, "hardtop_spef_cap_nodes"):
        raise ValueError(f"{relpath} hard-top SPEF cap count mismatch: {cap_count} vs {row}")
    resistor_count = count_hardtop_spef_resistors(netlist_path)
    if resistor_count != to_int(row, "hardtop_spef_resistors"):
        raise ValueError(f"{relpath} hard-top SPEF resistor count mismatch: {resistor_count} vs {row}")

    start_code = to_float(row, "start_code")
    end_code = to_float(row, "end_code")
    response_code = to_float(row, "response_code")
    observed_min_code = to_float(row, "observed_min_code")
    observed_max_code = to_float(row, "observed_max_code")
    if abs(start_code - 255.0) > 0.5 or observed_max_code < 254.5:
        raise ValueError(f"{relpath} did not start at high rail: {row}")
    if end_code > 253.0 or response_code > 253.0 or observed_min_code > 253.0:
        raise ValueError(f"{relpath} lacks high-start downward first motion: {row}")
    startup_rises = to_int(row, "startup_rise_count")
    startup_freq = to_float(row, "startup_freq_mhz")
    if startup_rises < 4 or not (49.0 <= startup_freq <= 52.0):
        raise ValueError(f"{relpath} has unexpected oscillator startup: {row}")

    log_path = Path(row.get("log", "")).expanduser()
    if not log_path.is_file():
        raise ValueError(f"{relpath} missing Xyce log: {log_path}")
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    for required in (
        "Total Devices                                          63443",
        "Number of Unknowns = 182651",
        "Timing summary of 16 processors",
    ):
        if required not in log_text:
            raise ValueError(f"{relpath} log does not contain {required!r}")

    elapsed_s = xyce_elapsed_run_time_s(log_text)
    if elapsed_s is None or elapsed_s <= 0.0:
        raise ValueError(f"{relpath} log lacks elapsed runtime: {log_path}")

    return {
        "rows": len(rows),
        "digital_scope": row.get("digital_scope"),
        "bbpd_impl": "postlayout",
        "dco_model": "postlayout_rcx",
        "xyce_mpi_procs": 16,
        "mapped_instance_count": to_int(row, "mapped_instance_count"),
        "skipped_physical_only_cells": to_int(row, "skipped_physical_only_cells"),
        "hardtop_spef_mode": row.get("hardtop_spef_mode", ""),
        "hardtop_spef_cap_nets": row.get("hardtop_spef_cap_nets", ""),
        "hardtop_spef_cap_nodes": row.get("hardtop_spef_cap_nodes", ""),
        "hardtop_spef_resistors": row.get("hardtop_spef_resistors", ""),
        "hardtop_spef_pin_substitutions": row.get("hardtop_spef_pin_substitutions", ""),
        "hardtop_spef_cap_total_ff": row.get("hardtop_spef_cap_total_ff", ""),
        "start_code": start_code,
        "end_code": end_code,
        "response_code": response_code,
        "startup_rise_count": startup_rises,
        "startup_freq_mhz": startup_freq,
        "elapsed_s": elapsed_s,
    }


def check_einvp_hardtop_spef_rc_common(
    row,
    relpath,
    expected_scope,
    expected_target_freq_mhz=60.174879350325796,
):
    if row.get("simulator") != "xyce" or to_int(row, "xyce_mpi_procs") != 16:
        raise ValueError(f"{relpath} has unexpected Xyce process count: {row}")
    if "-linsolv KLU" not in row.get("xyce_command", ""):
        raise ValueError(f"{relpath} does not record KLU: {row}")
    if row.get("bbpd_impl") != "postlayout":
        raise ValueError(f"{relpath} has wrong BBPD implementation: {row}")
    if row.get("digital_scope") != expected_scope:
        raise ValueError(f"{relpath} has wrong digital scope: {row}")
    if row.get("dco_model") != "postlayout_rcx":
        raise ValueError(f"{relpath} has wrong DCO model: {row}")
    if row.get("code_observer_source") != "dco_therm":
        raise ValueError(f"{relpath} has wrong code observer: {row}")
    if to_int(row, "mapped_instance_count") < 2000:
        raise ValueError(f"{relpath} has too few mapped instances: {row}")
    if to_int(row, "skipped_physical_only_cells") != 4138:
        raise ValueError(f"{relpath} skipped unexpected cells: {row}")
    if to_int(row, "ki") != 160 or to_int(row, "kp") != 8 or to_int(row, "ndiv") != 2:
        raise ValueError(f"{relpath} has wrong loop setting: {row}")
    if to_int(row, "dlf_frac_width") != 6:
        raise ValueError(f"{relpath} has wrong DLF fractional width: {row}")
    if abs(to_float(row, "target_freq_mhz") - expected_target_freq_mhz) > 1e-6:
        raise ValueError(f"{relpath} has wrong target frequency: {row}")
    if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
        raise ValueError(f"{relpath} did not finish cleanly: {row}")

    if row.get("hardtop_spef_mode") != "distributed_rc":
        raise ValueError(f"{relpath} has wrong hard-top SPEF mode: {row}")
    if "IntegerPLL_HardMacroTop_EINVP" not in row.get("hardtop_spef_path", ""):
        raise ValueError(f"{relpath} does not use the EINVP hard-top SPEF: {row}")
    if to_int(row, "hardtop_spef_cap_nets") < 261:
        raise ValueError(f"{relpath} has too few hard-top SPEF nets: {row}")
    if to_int(row, "hardtop_spef_cap_nodes") < 1700:
        raise ValueError(f"{relpath} has too few hard-top SPEF cap nodes: {row}")
    if to_int(row, "hardtop_spef_resistors") < 1600:
        raise ValueError(f"{relpath} has too few hard-top SPEF resistors: {row}")
    if to_int(row, "hardtop_spef_pin_substitutions") < 260:
        raise ValueError(f"{relpath} has too few hard-top pin substitutions: {row}")
    if to_int(row, "hardtop_spef_dco_therm_nets") < 255:
        raise ValueError(f"{relpath} has too few hard-top DCO thermometer nets: {row}")
    if to_float(row, "hardtop_spef_cap_total_ff") < 25000.0:
        raise ValueError(f"{relpath} has too little hard-top SPEF capacitance: {row}")

    netlist_path = Path(row.get("netlist", "")).expanduser()
    if not netlist_path.is_file():
        raise ValueError(f"{relpath} missing generated deck: {row}")
    netlist_text = netlist_path.read_text(encoding="ascii", errors="replace")
    if "IntegerPLL_DCO_EINVP" not in netlist_text:
        raise ValueError(f"{relpath} generated deck does not instantiate IntegerPLL_DCO_EINVP")
    if "IntegerPLL_DCO.rcx.spice" in netlist_text:
        raise ValueError(f"{relpath} generated deck includes the NAND-load DCO RCX deck")
    cap_count = count_hardtop_spef_caps(netlist_path)
    if cap_count != to_int(row, "hardtop_spef_cap_nodes"):
        raise ValueError(f"{relpath} hard-top SPEF cap count mismatch: {cap_count} vs {row}")
    resistor_count = count_hardtop_spef_resistors(netlist_path)
    if resistor_count != to_int(row, "hardtop_spef_resistors"):
        raise ValueError(f"{relpath} hard-top SPEF resistor count mismatch: {resistor_count} vs {row}")

    log_path = Path(row.get("log", "")).expanduser()
    if not log_path.is_file():
        raise ValueError(f"{relpath} missing Xyce log: {log_path}")
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    for required in (
        "Total Devices                                          65871",
        "Number of Unknowns = 184445",
        "Timing summary of 16 processors",
    ):
        if required not in log_text:
            raise ValueError(f"{relpath} log does not contain {required!r}")

    elapsed_s = xyce_elapsed_run_time_s(log_text)
    if elapsed_s is None or elapsed_s <= 0.0:
        raise ValueError(f"{relpath} log lacks elapsed runtime: {log_path}")

    return {
        "mapped_instance_count": to_int(row, "mapped_instance_count"),
        "skipped_physical_only_cells": to_int(row, "skipped_physical_only_cells"),
        "hardtop_spef_cap_nets": row.get("hardtop_spef_cap_nets", ""),
        "hardtop_spef_cap_nodes": row.get("hardtop_spef_cap_nodes", ""),
        "hardtop_spef_resistors": row.get("hardtop_spef_resistors", ""),
        "hardtop_spef_pin_substitutions": row.get("hardtop_spef_pin_substitutions", ""),
        "hardtop_spef_cap_total_ff": row.get("hardtop_spef_cap_total_ff", ""),
        "elapsed_s": elapsed_s,
    }


def check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_pvt_midcode_hold_mpi16_klu(root):
    cases = {
        "ff": {
            "relpath": (
                "build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_midcode_hold_220ns_mpi16_klu/"
                "mapped_loop_check.csv"
            ),
            "scope": "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_midcode_hold_diag",
            "ref_mhz": 42.5,
            "target_freq_mhz": 85.0,
            "end_meas_ns": 219.0,
            "lock_meas_start_ns": 150.0,
            "tail_freq_min_mhz": 80.0,
            "tail_freq_max_mhz": 83.0,
            "min_tail_rises": 5,
        },
        "ss": {
            "relpath": (
                "build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_midcode_hold_200ns_mpi16_klu/"
                "mapped_loop_check.csv"
            ),
            "scope": "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_midcode_hold_diag",
            "ref_mhz": 20.0,
            "target_freq_mhz": 40.0,
            "end_meas_ns": 199.0,
            "lock_meas_start_ns": 80.0,
            "tail_freq_min_mhz": 38.0,
            "tail_freq_max_mhz": 40.0,
            "min_tail_rises": 4,
        },
    }
    rows_by_corner = {}
    source_paths = [
        root / "scripts/spice_pll_mapped_loop_check.py",
        root / "openlane/IntegerPLL_DCO_EINVP/runs/librelane_signoff/rcx-magic/IntegerPLL_DCO_EINVP.rcx.spice",
        root / "openlane/IntegerPLL_BBPD/runs/librelane_signoff/rcx-magic/IntegerPLL_BBPD.rcx.spice",
        root / "openlane/IntegerPLL_HardMacroTop_EINVP/runs/librelane_signoff/final/spef/nom/IntegerPLL_HardMacroTop_EINVP.nom.spef",
        root / "openlane/IntegerPLL_DigitalCore/runs/librelane_signoff_force127_s4a2/final/nl/IntegerPLL_DigitalCore.nl.v",
    ]
    for corner, expected in cases.items():
        relpath = expected["relpath"]
        csv_path = require_path(root, relpath)
        rows = read_csv(csv_path)
        if len(rows) != 1:
            raise ValueError(f"{relpath} expected 1 row, found {len(rows)}")
        require_all_pass(rows)
        row = rows[0]
        if row.get("simulator") != "xyce" or to_int(row, "xyce_mpi_procs") != 16:
            raise ValueError(f"{relpath} has unexpected Xyce process count: {row}")
        if "-linsolv KLU" not in row.get("xyce_command", ""):
            raise ValueError(f"{relpath} does not record KLU: {row}")
        if row.get("bbpd_impl") != "postlayout" or row.get("dco_model") != "postlayout_rcx":
            raise ValueError(f"{relpath} has wrong post-layout models: {row}")
        if row.get("digital_scope") != expected["scope"]:
            raise ValueError(f"{relpath} has wrong digital scope: {row}")
        if row.get("code_observer_source") != "dco_therm":
            raise ValueError(f"{relpath} has wrong code observer: {row}")
        if to_int(row, "mapped_instance_count") < 2000 or to_int(row, "skipped_physical_only_cells") != 4138:
            raise ValueError(f"{relpath} has wrong mapped-netlist coverage: {row}")
        if to_int(row, "ki") != 0 or to_int(row, "kp") != 0:
            raise ValueError(f"{relpath} is not a held-DLF calibration row: {row}")
        if to_int(row, "dlf_frac_width") != 6 or to_int(row, "ndiv") != 2:
            raise ValueError(f"{relpath} has wrong DLF/NDIV settings: {row}")
        if row.get("case") != "mid_start_inc" or row.get("check_mode") != "no_motion":
            raise ValueError(f"{relpath} has wrong case/check mode: {row}")
        if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
            raise ValueError(f"{relpath} did not finish cleanly: {row}")
        if abs(to_float(row, "ref_mhz") - expected["ref_mhz"]) > 1e-9:
            raise ValueError(f"{relpath} has wrong reference setting: {row}")
        if abs(to_float(row, "target_freq_mhz") - expected["target_freq_mhz"]) > 1e-9:
            raise ValueError(f"{relpath} has wrong target-frequency setting: {row}")
        if abs(to_float(row, "initial_dco_phase_cycles") - 0.25) > 1e-9:
            raise ValueError(f"{relpath} has wrong initial DCO phase: {row}")
        if abs(to_float(row, "enable_ns") - 85.0) > 1e-9 or abs(to_float(row, "clear_width_ns") - 60.0) > 1e-9:
            raise ValueError(f"{relpath} has wrong enable/reset timing: {row}")
        if abs(to_float(row, "start_meas_ns") - 84.0) > 1e-9 or abs(to_float(row, "end_meas_ns") - expected["end_meas_ns"]) > 1e-9:
            raise ValueError(f"{relpath} has wrong measurement window: {row}")
        if abs(to_float(row, "lock_meas_start_ns") - expected["lock_meas_start_ns"]) > 1e-9:
            raise ValueError(f"{relpath} has wrong tail measurement start: {row}")
        if row.get("lock_code_check") != "none":
            raise ValueError(f"{relpath} has wrong lock-code check: {row}")
        if row.get("hardtop_spef_mode") != "distributed_rc":
            raise ValueError(f"{relpath} has wrong hard-top SPEF mode: {row}")
        if "IntegerPLL_HardMacroTop_EINVP" not in row.get("hardtop_spef_path", ""):
            raise ValueError(f"{relpath} does not use the EINVP hard-top SPEF: {row}")
        if to_int(row, "hardtop_spef_cap_nets") < 261:
            raise ValueError(f"{relpath} has too few hard-top SPEF nets: {row}")
        if to_int(row, "hardtop_spef_cap_nodes") < 1700 or to_int(row, "hardtop_spef_resistors") < 1600:
            raise ValueError(f"{relpath} has too little distributed hard-top RC: {row}")
        if to_int(row, "hardtop_spef_pin_substitutions") < 260 or to_int(row, "hardtop_spef_dco_therm_nets") < 255:
            raise ValueError(f"{relpath} has incomplete hard-top pin/DCO thermometer mapping: {row}")
        if to_float(row, "hardtop_spef_cap_total_ff") < 25000.0:
            raise ValueError(f"{relpath} has too little hard-top SPEF capacitance: {row}")

        for key in (
            "start_code",
            "end_code",
            "observed_min_code",
            "observed_max_code",
            "response_code",
            "lock_observed_min_code",
            "lock_observed_max_code",
        ):
            if abs(to_float(row, key) - 128.0) > 0.5:
                raise ValueError(f"{relpath} does not hold code 128 in {key}: {row}")
        tail_rises = to_int(row, "tail_rise_count")
        tail_freq = to_float(row, "tail_freq_mhz")
        if tail_rises < expected["min_tail_rises"]:
            raise ValueError(f"{relpath} has too few tail rises: {row}")
        if not (expected["tail_freq_min_mhz"] <= tail_freq <= expected["tail_freq_max_mhz"]):
            raise ValueError(f"{relpath} has unexpected tail frequency: {row}")
        startup_freq = to_float(row, "startup_freq_mhz")
        if startup_freq <= 0.0:
            raise ValueError(f"{relpath} has invalid startup frequency: {row}")

        netlist_path = Path(row.get("netlist", "")).expanduser()
        if not netlist_path.is_file():
            raise ValueError(f"{relpath} missing generated deck: {row}")
        netlist_text = netlist_path.read_text(encoding="ascii", errors="replace")
        if f'sky130.lib.spice" {corner}' not in netlist_text:
            raise ValueError(f"{relpath} generated deck does not use {corner} corner")
        if "IntegerPLL_DCO_EINVP" not in netlist_text:
            raise ValueError(f"{relpath} generated deck does not instantiate IntegerPLL_DCO_EINVP")
        if "IntegerPLL_DCO.rcx.spice" in netlist_text:
            raise ValueError(f"{relpath} generated deck includes the NAND-load DCO RCX deck")

        log_path = Path(row.get("log", "")).expanduser()
        if not log_path.is_file():
            raise ValueError(f"{relpath} missing Xyce log: {log_path}")
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        for required in (
            "Total Devices                                          65871",
            "Number of Unknowns = 184445",
            "Timing summary of 16 processors",
        ):
            if required not in log_text:
                raise ValueError(f"{relpath} log does not contain {required!r}")
        elapsed_s = xyce_elapsed_run_time_s(log_text)
        if elapsed_s is None or elapsed_s <= 0.0:
            raise ValueError(f"{relpath} log lacks elapsed runtime: {log_path}")

        for source in source_paths:
            if require_path(root, str(source.relative_to(root))).stat().st_mtime > csv_path.stat().st_mtime:
                raise ValueError(f"{relpath} CSV is older than {source}")

        rows_by_corner[corner] = {
            "tail_freq_mhz": tail_freq,
            "startup_freq_mhz": startup_freq,
            "tail_rise_count": tail_rises,
            "elapsed_s": elapsed_s,
            "end_meas_ns": to_float(row, "end_meas_ns"),
        }

    if rows_by_corner["ff"]["tail_freq_mhz"] <= rows_by_corner["ss"]["tail_freq_mhz"]:
        raise ValueError(f"EINVP hard-top PVT midpoint frequencies are not ordered: {rows_by_corner}")
    return {
        "corners": ["ff", "ss"],
        "case": "mid_start_inc",
        "check_mode": "no_motion",
        "xyce_mpi_procs": 16,
        "hardtop_spef_mode": "distributed_rc",
        "midcode": 128,
        "rows": rows_by_corner,
        "freq_span_mhz": rows_by_corner["ff"]["tail_freq_mhz"] - rows_by_corner["ss"]["tail_freq_mhz"],
    }


def check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_pvt_midcode_lock_mpi16_klu(root):
    cases = {
        "ff": {
            "relpath": (
                "build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_midcode_lock_220ns_mpi16_klu/"
                "mapped_loop_check.csv"
            ),
            "scope": "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_midcode_lock_diag",
            "ref_mhz": 40.85637808531392,
            "target_freq_mhz": 81.71275617062784,
            "end_meas_ns": 219.0,
            "lock_meas_start_ns": 150.0,
            "startup_rise_min": 15,
            "startup_freq_min_mhz": 81.0,
            "startup_freq_max_mhz": 81.6,
            "tail_freq_min_mhz": 81.4,
            "tail_freq_max_mhz": 81.8,
            "end_code_min": 133.0,
            "end_code_max": 135.0,
            "observed_min_min": 124.0,
            "observed_max_max": 135.0,
            "response_min": 133.0,
            "response_max": 135.0,
        },
        "ss": {
            "relpath": (
                "build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_midcode_lock_240ns_mpi16_klu/"
                "mapped_loop_check.csv"
            ),
            "scope": "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_midcode_lock_diag",
            "ref_mhz": 19.42301870655616,
            "target_freq_mhz": 38.84603741311232,
            "end_meas_ns": 239.0,
            "lock_meas_start_ns": 100.0,
            "startup_rise_min": 7,
            "startup_freq_min_mhz": 38.4,
            "startup_freq_max_mhz": 38.8,
            "tail_freq_min_mhz": 38.7,
            "tail_freq_max_mhz": 39.0,
            "end_code_min": 125.0,
            "end_code_max": 127.0,
            "observed_min_min": 125.0,
            "observed_max_max": 129.0,
            "response_min": 127.0,
            "response_max": 129.0,
        },
    }
    rows_by_corner = {}
    source_paths = [
        root / "scripts/spice_pll_mapped_loop_check.py",
        root / "openlane/IntegerPLL_DCO_EINVP/runs/librelane_signoff/rcx-magic/IntegerPLL_DCO_EINVP.rcx.spice",
        root / "openlane/IntegerPLL_BBPD/runs/librelane_signoff/rcx-magic/IntegerPLL_BBPD.rcx.spice",
        root / "openlane/IntegerPLL_HardMacroTop_EINVP/runs/librelane_signoff/final/spef/nom/IntegerPLL_HardMacroTop_EINVP.nom.spef",
        root / "openlane/IntegerPLL_HardMacroTop_EINVP/runs/librelane_signoff/final/spice/IntegerPLL_HardMacroTop_EINVP.spice",
        root / "openlane/IntegerPLL_DigitalCore/runs/librelane_signoff_force127_s4a2/final/nl/IntegerPLL_DigitalCore.nl.v",
    ]
    for corner, expected in cases.items():
        relpath = expected["relpath"]
        csv_path = require_path(root, relpath)
        rows = read_csv(csv_path)
        if len(rows) != 1:
            raise ValueError(f"{relpath} expected 1 row, found {len(rows)}")
        require_all_pass(rows)
        row = rows[0]
        if row.get("simulator") != "xyce" or to_int(row, "xyce_mpi_procs") != 16:
            raise ValueError(f"{relpath} has unexpected Xyce process count: {row}")
        if "-linsolv KLU" not in row.get("xyce_command", ""):
            raise ValueError(f"{relpath} does not record KLU: {row}")
        if row.get("bbpd_impl") != "postlayout" or row.get("dco_model") != "postlayout_rcx":
            raise ValueError(f"{relpath} has wrong post-layout models: {row}")
        if row.get("digital_scope") != expected["scope"]:
            raise ValueError(f"{relpath} has wrong digital scope: {row}")
        if row.get("code_observer_source") != "dco_therm":
            raise ValueError(f"{relpath} has wrong code observer: {row}")
        if to_int(row, "mapped_instance_count") < 2000 or to_int(row, "skipped_physical_only_cells") != 4138:
            raise ValueError(f"{relpath} has wrong mapped-netlist coverage: {row}")
        if to_int(row, "ki") != 160 or to_int(row, "kp") != 8:
            raise ValueError(f"{relpath} has wrong DLF gain settings: {row}")
        if to_int(row, "dlf_frac_width") != 6 or to_int(row, "ndiv") != 2:
            raise ValueError(f"{relpath} has wrong DLF/NDIV settings: {row}")
        if row.get("case") != "mid_start_inc" or row.get("check_mode") != "lock_window":
            raise ValueError(f"{relpath} has wrong case/check mode: {row}")
        if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
            raise ValueError(f"{relpath} did not finish cleanly: {row}")
        if abs(to_float(row, "ref_mhz") - expected["ref_mhz"]) > 1e-9:
            raise ValueError(f"{relpath} has wrong reference setting: {row}")
        if abs(to_float(row, "target_freq_mhz") - expected["target_freq_mhz"]) > 1e-9:
            raise ValueError(f"{relpath} has wrong target-frequency setting: {row}")
        if abs(to_float(row, "initial_dco_phase_cycles") - 0.25) > 1e-9:
            raise ValueError(f"{relpath} has wrong initial DCO phase: {row}")
        if abs(to_float(row, "enable_ns") - 85.0) > 1e-9 or abs(to_float(row, "clear_width_ns") - 60.0) > 1e-9:
            raise ValueError(f"{relpath} has wrong enable/reset timing: {row}")
        if abs(to_float(row, "start_meas_ns") - 84.0) > 1e-9 or abs(to_float(row, "end_meas_ns") - expected["end_meas_ns"]) > 1e-9:
            raise ValueError(f"{relpath} has wrong measurement window: {row}")
        if abs(to_float(row, "lock_meas_start_ns") - expected["lock_meas_start_ns"]) > 1e-9:
            raise ValueError(f"{relpath} has wrong lock measurement start: {row}")
        if row.get("lock_code_check") != "window":
            raise ValueError(f"{relpath} has wrong lock-code check: {row}")
        if to_float(row, "lock_min_code") != 112.0 or to_float(row, "lock_max_code") != 144.0:
            raise ValueError(f"{relpath} has wrong lock code window: {row}")
        if abs(to_float(row, "lock_max_abs_ferr_mhz") - 1.0) > 1e-9:
            raise ValueError(f"{relpath} has wrong frequency-error limit: {row}")
        if row.get("hardtop_spef_mode") != "distributed_rc":
            raise ValueError(f"{relpath} has wrong hard-top SPEF mode: {row}")
        if "IntegerPLL_HardMacroTop_EINVP" not in row.get("hardtop_spef_path", ""):
            raise ValueError(f"{relpath} does not use the EINVP hard-top SPEF: {row}")
        if to_int(row, "hardtop_spef_cap_nets") < 261:
            raise ValueError(f"{relpath} has too few hard-top SPEF nets: {row}")
        if to_int(row, "hardtop_spef_cap_nodes") < 1700 or to_int(row, "hardtop_spef_resistors") < 1600:
            raise ValueError(f"{relpath} has too little distributed hard-top RC: {row}")
        if to_int(row, "hardtop_spef_pin_substitutions") < 260 or to_int(row, "hardtop_spef_dco_therm_nets") < 255:
            raise ValueError(f"{relpath} has incomplete hard-top pin/DCO thermometer mapping: {row}")
        if to_float(row, "hardtop_spef_cap_total_ff") < 25000.0:
            raise ValueError(f"{relpath} has too little hard-top SPEF capacitance: {row}")

        start_code = to_float(row, "start_code")
        end_code = to_float(row, "end_code")
        observed_min_code = to_float(row, "observed_min_code")
        observed_max_code = to_float(row, "observed_max_code")
        response_code = to_float(row, "response_code")
        lock_min = to_float(row, "lock_observed_min_code")
        lock_max = to_float(row, "lock_observed_max_code")
        if abs(start_code - 128.0) > 0.5:
            raise ValueError(f"{relpath} did not start at mid code: {row}")
        if not (expected["end_code_min"] <= end_code <= expected["end_code_max"]):
            raise ValueError(f"{relpath} has unexpected endpoint code: {row}")
        if not (expected["observed_min_min"] <= observed_min_code <= observed_max_code <= expected["observed_max_max"]):
            raise ValueError(f"{relpath} has unexpected code excursion: {row}")
        if not (expected["observed_min_min"] <= lock_min <= lock_max <= expected["observed_max_max"]):
            raise ValueError(f"{relpath} tail window leaves the expected code band: {row}")
        if not (expected["response_min"] <= response_code <= expected["response_max"]):
            raise ValueError(f"{relpath} has unexpected response code: {row}")
        if not (112.0 <= lock_min <= lock_max <= 144.0):
            raise ValueError(f"{relpath} leaves the configured lock code window: {row}")

        startup_rises = to_int(row, "startup_rise_count")
        startup_freq = to_float(row, "startup_freq_mhz")
        tail_rises = to_int(row, "tail_rise_count")
        tail_freq = to_float(row, "tail_freq_mhz")
        tail_error = to_float(row, "tail_abs_error_mhz")
        if startup_rises < expected["startup_rise_min"]:
            raise ValueError(f"{relpath} has too few startup rises: {row}")
        if not (expected["startup_freq_min_mhz"] <= startup_freq <= expected["startup_freq_max_mhz"]):
            raise ValueError(f"{relpath} has unexpected startup frequency: {row}")
        if tail_rises < 5:
            raise ValueError(f"{relpath} has too few tail rises: {row}")
        if not (expected["tail_freq_min_mhz"] <= tail_freq <= expected["tail_freq_max_mhz"]) or tail_error > 1.0:
            raise ValueError(f"{relpath} lacks a bounded tail frequency: {row}")

        netlist_path = Path(row.get("netlist", "")).expanduser()
        if not netlist_path.is_file():
            raise ValueError(f"{relpath} missing generated deck: {row}")
        netlist_text = netlist_path.read_text(encoding="ascii", errors="replace")
        if f'sky130.lib.spice" {corner}' not in netlist_text:
            raise ValueError(f"{relpath} generated deck does not use {corner} corner")
        if "IntegerPLL_DCO_EINVP" not in netlist_text:
            raise ValueError(f"{relpath} generated deck does not instantiate IntegerPLL_DCO_EINVP")
        if "IntegerPLL_DCO.rcx.spice" in netlist_text:
            raise ValueError(f"{relpath} generated deck includes the NAND-load DCO RCX deck")

        log_path = Path(row.get("log", "")).expanduser()
        if not log_path.is_file():
            raise ValueError(f"{relpath} missing Xyce log: {log_path}")
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        for required in (
            "Total Devices                                          65871",
            "Number of Unknowns = 184445",
            "Timing summary of 16 processors",
        ):
            if required not in log_text:
                raise ValueError(f"{relpath} log does not contain {required!r}")
        elapsed_s = xyce_elapsed_run_time_s(log_text)
        if elapsed_s is None or elapsed_s <= 0.0:
            raise ValueError(f"{relpath} log lacks elapsed runtime: {log_path}")

        for source in source_paths:
            if require_path(root, str(source.relative_to(root))).stat().st_mtime > csv_path.stat().st_mtime:
                raise ValueError(f"{relpath} CSV is older than {source}")

        rows_by_corner[corner] = {
            "ref_mhz": to_float(row, "ref_mhz"),
            "target_freq_mhz": to_float(row, "target_freq_mhz"),
            "startup_freq_mhz": startup_freq,
            "tail_freq_mhz": tail_freq,
            "tail_abs_error_mhz": tail_error,
            "tail_rise_count": tail_rises,
            "start_code": start_code,
            "end_code": end_code,
            "lock_observed_min_code": lock_min,
            "lock_observed_max_code": lock_max,
            "elapsed_s": elapsed_s,
        }

    if rows_by_corner["ff"]["tail_freq_mhz"] <= rows_by_corner["ss"]["tail_freq_mhz"]:
        raise ValueError(f"EINVP hard-top PVT midpoint lock frequencies are not ordered: {rows_by_corner}")
    return {
        "corners": ["ff", "ss"],
        "case": "mid_start_inc",
        "check_mode": "lock_window",
        "xyce_mpi_procs": 16,
        "hardtop_spef_mode": "distributed_rc",
        "ki": 160,
        "kp": 8,
        "dlf_frac_width": 6,
        "ndiv": 2,
        "rows": rows_by_corner,
        "freq_span_mhz": rows_by_corner["ff"]["tail_freq_mhz"] - rows_by_corner["ss"]["tail_freq_mhz"],
    }


def check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_low_lock_mpi16_klu(root):
    relpath = (
        "build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_low_lock_700ns_mpi16_klu/"
        "mapped_loop_check.csv"
    )
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 1:
        raise ValueError(f"{relpath} expected 1 row, found {len(rows)}")
    require_all_pass(rows)
    row = rows[0]
    common = check_einvp_hardtop_spef_rc_common(
        row,
        relpath,
        "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_low_lock_diag",
        expected_target_freq_mhz=81.71275617062784,
    )

    if row.get("case") != "low_start" or row.get("check_mode") != "lock_window":
        raise ValueError(f"{relpath} has wrong case/check mode: {row}")
    if abs(to_float(row, "ref_mhz") - 40.85637808531392) > 1e-9:
        raise ValueError(f"{relpath} has wrong FF calibrated reference: {row}")
    if abs(to_float(row, "initial_dco_phase_cycles")) > 1e-9:
        raise ValueError(f"{relpath} has unexpected initial phase: {row}")
    if abs(to_float(row, "enable_ns") - 85.0) > 1e-9 or abs(to_float(row, "clear_width_ns") - 60.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong enable/reset timing: {row}")
    if abs(to_float(row, "start_meas_ns") - 84.0) > 1e-9 or abs(to_float(row, "end_meas_ns") - 699.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong measurement window: {row}")
    if abs(to_float(row, "lock_meas_start_ns") - 580.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong lock measurement start: {row}")
    if row.get("lock_code_check") != "window":
        raise ValueError(f"{relpath} has wrong lock-code check: {row}")
    if abs(to_float(row, "lock_min_code") - 112.0) > 1e-9 or abs(to_float(row, "lock_max_code") - 144.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong lock code window: {row}")
    if abs(to_float(row, "lock_max_abs_ferr_mhz") - 1.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong lock frequency-error limit: {row}")

    start_code = to_float(row, "start_code")
    end_code = to_float(row, "end_code")
    observed_min_code = to_float(row, "observed_min_code")
    observed_max_code = to_float(row, "observed_max_code")
    response_code = to_float(row, "response_code")
    lock_min = to_float(row, "lock_observed_min_code")
    lock_max = to_float(row, "lock_observed_max_code")
    if abs(start_code) > 0.5 or observed_min_code > 0.5:
        raise ValueError(f"{relpath} did not start at the low rail: {row}")
    if not (120.0 <= end_code <= 124.0):
        raise ValueError(f"{relpath} has unexpected endpoint code: {row}")
    if not (126.0 <= response_code <= 130.0):
        raise ValueError(f"{relpath} has unexpected response code: {row}")
    if observed_max_code < 127.0:
        raise ValueError(f"{relpath} did not reach the expected high side of the lock band: {row}")
    if not (120.0 <= lock_min <= lock_max <= 130.0):
        raise ValueError(f"{relpath} tail window leaves the expected FF low-start lock band: {row}")

    startup_rises = to_int(row, "startup_rise_count")
    startup_freq = to_float(row, "startup_freq_mhz")
    tail_rises = to_int(row, "tail_rise_count")
    tail_freq = to_float(row, "tail_freq_mhz")
    tail_error = to_float(row, "tail_abs_error_mhz")
    if startup_rises < 50 or not (75.0 <= startup_freq <= 78.5):
        raise ValueError(f"{relpath} has unexpected startup frequency: {row}")
    if tail_rises < 8 or not (81.3 <= tail_freq <= 81.7) or tail_error > 0.5:
        raise ValueError(f"{relpath} lacks expected FF low-start tail frequency: {row}")

    netlist_path = Path(row.get("netlist", "")).expanduser()
    netlist_text = netlist_path.read_text(encoding="ascii", errors="replace")
    if 'sky130.lib.spice" ff' not in netlist_text:
        raise ValueError(f"{relpath} generated deck does not use the FF corner")

    source_paths = [
        root / "scripts/spice_pll_mapped_loop_check.py",
        root / "openlane/IntegerPLL_DCO_EINVP/runs/librelane_signoff/rcx-magic/IntegerPLL_DCO_EINVP.rcx.spice",
        root / "openlane/IntegerPLL_BBPD/runs/librelane_signoff/rcx-magic/IntegerPLL_BBPD.rcx.spice",
        root / "openlane/IntegerPLL_HardMacroTop_EINVP/runs/librelane_signoff/final/spef/nom/IntegerPLL_HardMacroTop_EINVP.nom.spef",
        root / "openlane/IntegerPLL_HardMacroTop_EINVP/runs/librelane_signoff/final/spice/IntegerPLL_HardMacroTop_EINVP.spice",
        root / "openlane/IntegerPLL_DigitalCore/runs/librelane_signoff_force127_s4a2/final/nl/IntegerPLL_DigitalCore.nl.v",
    ]
    csv_path = require_path(root, relpath)
    for source in source_paths:
        if require_path(root, str(source.relative_to(root))).stat().st_mtime > csv_path.stat().st_mtime:
            raise ValueError(f"{relpath} CSV is older than {source}")

    return {
        **common,
        "corner": "ff",
        "case": row["case"],
        "check_mode": row["check_mode"],
        "ref_mhz": to_float(row, "ref_mhz"),
        "target_freq_mhz": to_float(row, "target_freq_mhz"),
        "start_code": start_code,
        "end_code": end_code,
        "response_code": response_code,
        "lock_observed_min_code": lock_min,
        "lock_observed_max_code": lock_max,
        "tail_rise_count": tail_rises,
        "tail_freq_mhz": tail_freq,
        "tail_abs_error_mhz": tail_error,
        "startup_freq_mhz": startup_freq,
        "elapsed_s": to_float(row, "elapsed_s"),
    }


def check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_high_lock_mpi16_klu(root):
    relpath = (
        "build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_high_lock_700ns_mpi16_klu/"
        "mapped_loop_check.csv"
    )
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 1:
        raise ValueError(f"{relpath} expected 1 row, found {len(rows)}")
    require_all_pass(rows)
    row = rows[0]
    common = check_einvp_hardtop_spef_rc_common(
        row,
        relpath,
        "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_high_lock_diag",
        expected_target_freq_mhz=81.71275617062784,
    )

    if row.get("case") != "high_start" or row.get("check_mode") != "lock_window":
        raise ValueError(f"{relpath} has wrong case/check mode: {row}")
    if abs(to_float(row, "ref_mhz") - 40.85637808531392) > 1e-9:
        raise ValueError(f"{relpath} has wrong FF calibrated reference: {row}")
    if abs(to_float(row, "initial_dco_phase_cycles") - 0.5) > 1e-9:
        raise ValueError(f"{relpath} has unexpected initial phase: {row}")
    if abs(to_float(row, "enable_ns") - 85.0) > 1e-9 or abs(to_float(row, "clear_width_ns") - 60.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong enable/reset timing: {row}")
    if abs(to_float(row, "start_meas_ns") - 84.0) > 1e-9 or abs(to_float(row, "end_meas_ns") - 699.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong measurement window: {row}")
    if abs(to_float(row, "lock_meas_start_ns") - 580.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong lock measurement start: {row}")
    if row.get("lock_code_check") != "window":
        raise ValueError(f"{relpath} has wrong lock-code check: {row}")
    if abs(to_float(row, "lock_min_code") - 112.0) > 1e-9 or abs(to_float(row, "lock_max_code") - 144.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong lock code window: {row}")
    if abs(to_float(row, "lock_max_abs_ferr_mhz") - 1.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong lock frequency-error limit: {row}")

    start_code = to_float(row, "start_code")
    end_code = to_float(row, "end_code")
    observed_min_code = to_float(row, "observed_min_code")
    observed_max_code = to_float(row, "observed_max_code")
    response_code = to_float(row, "response_code")
    lock_min = to_float(row, "lock_observed_min_code")
    lock_max = to_float(row, "lock_observed_max_code")
    if start_code < 254.5 or observed_max_code < 254.5:
        raise ValueError(f"{relpath} did not start at the high rail: {row}")
    if not (126.0 <= end_code <= 128.0):
        raise ValueError(f"{relpath} has unexpected endpoint code: {row}")
    if not (126.0 <= response_code <= 128.0):
        raise ValueError(f"{relpath} has unexpected response code: {row}")
    if observed_min_code > 128.0:
        raise ValueError(f"{relpath} did not reach the expected low side of the lock band: {row}")
    if not (126.0 <= lock_min <= lock_max <= 134.0):
        raise ValueError(f"{relpath} tail window leaves the expected FF high-start lock band: {row}")

    startup_rises = to_int(row, "startup_rise_count")
    startup_freq = to_float(row, "startup_freq_mhz")
    tail_rises = to_int(row, "tail_rise_count")
    tail_freq = to_float(row, "tail_freq_mhz")
    tail_error = to_float(row, "tail_abs_error_mhz")
    if startup_rises < 55 or not (85.0 <= startup_freq <= 89.0):
        raise ValueError(f"{relpath} has unexpected startup frequency: {row}")
    if tail_rises < 8 or not (81.8 <= tail_freq <= 82.3) or tail_error > 0.6:
        raise ValueError(f"{relpath} lacks expected FF high-start tail frequency: {row}")

    netlist_path = Path(row.get("netlist", "")).expanduser()
    netlist_text = netlist_path.read_text(encoding="ascii", errors="replace")
    if 'sky130.lib.spice" ff' not in netlist_text:
        raise ValueError(f"{relpath} generated deck does not use the FF corner")

    source_paths = [
        root / "scripts/spice_pll_mapped_loop_check.py",
        root / "openlane/IntegerPLL_DCO_EINVP/runs/librelane_signoff/rcx-magic/IntegerPLL_DCO_EINVP.rcx.spice",
        root / "openlane/IntegerPLL_BBPD/runs/librelane_signoff/rcx-magic/IntegerPLL_BBPD.rcx.spice",
        root / "openlane/IntegerPLL_HardMacroTop_EINVP/runs/librelane_signoff/final/spef/nom/IntegerPLL_HardMacroTop_EINVP.nom.spef",
        root / "openlane/IntegerPLL_HardMacroTop_EINVP/runs/librelane_signoff/final/spice/IntegerPLL_HardMacroTop_EINVP.spice",
        root / "openlane/IntegerPLL_DigitalCore/runs/librelane_signoff_force127_s4a2/final/nl/IntegerPLL_DigitalCore.nl.v",
    ]
    csv_path = require_path(root, relpath)
    for source in source_paths:
        if require_path(root, str(source.relative_to(root))).stat().st_mtime > csv_path.stat().st_mtime:
            raise ValueError(f"{relpath} CSV is older than {source}")

    return {
        **common,
        "corner": "ff",
        "case": row["case"],
        "check_mode": row["check_mode"],
        "ref_mhz": to_float(row, "ref_mhz"),
        "target_freq_mhz": to_float(row, "target_freq_mhz"),
        "start_code": start_code,
        "end_code": end_code,
        "response_code": response_code,
        "lock_observed_min_code": lock_min,
        "lock_observed_max_code": lock_max,
        "tail_rise_count": tail_rises,
        "tail_freq_mhz": tail_freq,
        "tail_abs_error_mhz": tail_error,
        "startup_freq_mhz": startup_freq,
        "elapsed_s": to_float(row, "elapsed_s"),
    }


def check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_low_lock_mpi16_klu(root):
    relpath = (
        "build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_low_lock_1400ns_mpi16_klu/"
        "mapped_loop_check.csv"
    )
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 1:
        raise ValueError(f"{relpath} expected 1 row, found {len(rows)}")
    require_all_pass(rows)
    row = rows[0]
    common = check_einvp_hardtop_spef_rc_common(
        row,
        relpath,
        "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_low_lock_diag",
        expected_target_freq_mhz=38.84603741311232,
    )

    if row.get("case") != "low_start" or row.get("check_mode") != "lock_window":
        raise ValueError(f"{relpath} has wrong case/check mode: {row}")
    if abs(to_float(row, "ref_mhz") - 19.42301870655616) > 1e-9:
        raise ValueError(f"{relpath} has wrong SS calibrated reference: {row}")
    if abs(to_float(row, "initial_dco_phase_cycles")) > 1e-9:
        raise ValueError(f"{relpath} has unexpected initial phase: {row}")
    if abs(to_float(row, "enable_ns") - 85.0) > 1e-9 or abs(to_float(row, "clear_width_ns") - 60.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong enable/reset timing: {row}")
    if abs(to_float(row, "start_meas_ns") - 84.0) > 1e-9 or abs(to_float(row, "end_meas_ns") - 1399.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong measurement window: {row}")
    if abs(to_float(row, "lock_meas_start_ns") - 1160.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong lock measurement start: {row}")
    if row.get("lock_code_check") != "window":
        raise ValueError(f"{relpath} has wrong lock-code check: {row}")
    if abs(to_float(row, "lock_min_code") - 112.0) > 1e-9 or abs(to_float(row, "lock_max_code") - 144.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong lock code window: {row}")
    if abs(to_float(row, "lock_max_abs_ferr_mhz") - 1.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong lock frequency-error limit: {row}")

    start_code = to_float(row, "start_code")
    end_code = to_float(row, "end_code")
    observed_min_code = to_float(row, "observed_min_code")
    observed_max_code = to_float(row, "observed_max_code")
    response_code = to_float(row, "response_code")
    lock_min = to_float(row, "lock_observed_min_code")
    lock_max = to_float(row, "lock_observed_max_code")
    if abs(start_code) > 0.5 or observed_min_code > 0.5:
        raise ValueError(f"{relpath} did not start at the low rail: {row}")
    if not (120.0 <= end_code <= 124.0):
        raise ValueError(f"{relpath} has unexpected endpoint code: {row}")
    if not (126.0 <= response_code <= 130.0):
        raise ValueError(f"{relpath} has unexpected response code: {row}")
    if observed_max_code < 127.0:
        raise ValueError(f"{relpath} did not reach the expected high side of the lock band: {row}")
    if not (120.0 <= lock_min <= lock_max <= 130.0):
        raise ValueError(f"{relpath} tail window leaves the expected SS low-start lock band: {row}")

    startup_rises = to_int(row, "startup_rise_count")
    startup_freq = to_float(row, "startup_freq_mhz")
    tail_rises = to_int(row, "tail_rise_count")
    tail_freq = to_float(row, "tail_freq_mhz")
    tail_error = to_float(row, "tail_abs_error_mhz")
    if startup_rises < 45 or not (36.5 <= startup_freq <= 37.6):
        raise ValueError(f"{relpath} has unexpected startup frequency: {row}")
    if tail_rises < 8 or not (38.6 <= tail_freq <= 39.0) or tail_error > 0.2:
        raise ValueError(f"{relpath} lacks expected SS low-start tail frequency: {row}")

    netlist_path = Path(row.get("netlist", "")).expanduser()
    netlist_text = netlist_path.read_text(encoding="ascii", errors="replace")
    if 'sky130.lib.spice" ss' not in netlist_text:
        raise ValueError(f"{relpath} generated deck does not use the SS corner")

    source_paths = [
        root / "scripts/spice_pll_mapped_loop_check.py",
        root / "openlane/IntegerPLL_DCO_EINVP/runs/librelane_signoff/rcx-magic/IntegerPLL_DCO_EINVP.rcx.spice",
        root / "openlane/IntegerPLL_BBPD/runs/librelane_signoff/rcx-magic/IntegerPLL_BBPD.rcx.spice",
        root / "openlane/IntegerPLL_HardMacroTop_EINVP/runs/librelane_signoff/final/spef/nom/IntegerPLL_HardMacroTop_EINVP.nom.spef",
        root / "openlane/IntegerPLL_HardMacroTop_EINVP/runs/librelane_signoff/final/spice/IntegerPLL_HardMacroTop_EINVP.spice",
        root / "openlane/IntegerPLL_DigitalCore/runs/librelane_signoff_force127_s4a2/final/nl/IntegerPLL_DigitalCore.nl.v",
    ]
    csv_path = require_path(root, relpath)
    for source in source_paths:
        if require_path(root, str(source.relative_to(root))).stat().st_mtime > csv_path.stat().st_mtime:
            raise ValueError(f"{relpath} CSV is older than {source}")

    return {
        **common,
        "corner": "ss",
        "case": row["case"],
        "check_mode": row["check_mode"],
        "ref_mhz": to_float(row, "ref_mhz"),
        "target_freq_mhz": to_float(row, "target_freq_mhz"),
        "start_code": start_code,
        "end_code": end_code,
        "response_code": response_code,
        "lock_observed_min_code": lock_min,
        "lock_observed_max_code": lock_max,
        "tail_rise_count": tail_rises,
        "tail_freq_mhz": tail_freq,
        "tail_abs_error_mhz": tail_error,
        "startup_freq_mhz": startup_freq,
        "elapsed_s": to_float(row, "elapsed_s"),
    }


def check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_high_lock_mpi16_klu(root):
    relpath = (
        "build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_high_lock_1400ns_mpi16_klu/"
        "mapped_loop_check.csv"
    )
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 1:
        raise ValueError(f"{relpath} expected 1 row, found {len(rows)}")
    require_all_pass(rows)
    row = rows[0]
    common = check_einvp_hardtop_spef_rc_common(
        row,
        relpath,
        "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_high_lock_diag",
        expected_target_freq_mhz=38.84603741311232,
    )

    if row.get("case") != "high_start" or row.get("check_mode") != "lock_window":
        raise ValueError(f"{relpath} has wrong case/check mode: {row}")
    if abs(to_float(row, "ref_mhz") - 19.42301870655616) > 1e-9:
        raise ValueError(f"{relpath} has wrong SS calibrated reference: {row}")
    if abs(to_float(row, "initial_dco_phase_cycles") - 0.5) > 1e-9:
        raise ValueError(f"{relpath} has unexpected initial phase: {row}")
    if abs(to_float(row, "enable_ns") - 85.0) > 1e-9 or abs(to_float(row, "clear_width_ns") - 60.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong enable/reset timing: {row}")
    if abs(to_float(row, "start_meas_ns") - 84.0) > 1e-9 or abs(to_float(row, "end_meas_ns") - 1399.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong measurement window: {row}")
    if abs(to_float(row, "lock_meas_start_ns") - 1160.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong lock measurement start: {row}")
    if row.get("lock_code_check") != "window":
        raise ValueError(f"{relpath} has wrong lock-code check: {row}")
    if abs(to_float(row, "lock_min_code") - 112.0) > 1e-9 or abs(to_float(row, "lock_max_code") - 144.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong lock code window: {row}")
    if abs(to_float(row, "lock_max_abs_ferr_mhz") - 1.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong lock frequency-error limit: {row}")

    start_code = to_float(row, "start_code")
    end_code = to_float(row, "end_code")
    observed_min_code = to_float(row, "observed_min_code")
    observed_max_code = to_float(row, "observed_max_code")
    response_code = to_float(row, "response_code")
    lock_min = to_float(row, "lock_observed_min_code")
    lock_max = to_float(row, "lock_observed_max_code")
    if start_code < 254.5 or observed_max_code < 254.5:
        raise ValueError(f"{relpath} did not start at the high rail: {row}")
    if not (126.0 <= end_code <= 128.0):
        raise ValueError(f"{relpath} has unexpected endpoint code: {row}")
    if not (126.0 <= response_code <= 128.0):
        raise ValueError(f"{relpath} has unexpected response code: {row}")
    if observed_min_code > 128.0:
        raise ValueError(f"{relpath} did not reach the expected low side of the lock band: {row}")
    if not (126.0 <= lock_min <= lock_max <= 134.0):
        raise ValueError(f"{relpath} tail window leaves the expected SS high-start lock band: {row}")

    startup_rises = to_int(row, "startup_rise_count")
    startup_freq = to_float(row, "startup_freq_mhz")
    tail_rises = to_int(row, "tail_rise_count")
    tail_freq = to_float(row, "tail_freq_mhz")
    tail_error = to_float(row, "tail_abs_error_mhz")
    if startup_rises < 50 or not (40.0 <= startup_freq <= 41.5):
        raise ValueError(f"{relpath} has unexpected startup frequency: {row}")
    if tail_rises < 8 or not (38.8 <= tail_freq <= 39.2) or tail_error > 0.3:
        raise ValueError(f"{relpath} lacks expected SS high-start tail frequency: {row}")

    netlist_path = Path(row.get("netlist", "")).expanduser()
    netlist_text = netlist_path.read_text(encoding="ascii", errors="replace")
    if 'sky130.lib.spice" ss' not in netlist_text:
        raise ValueError(f"{relpath} generated deck does not use the SS corner")

    source_paths = [
        root / "scripts/spice_pll_mapped_loop_check.py",
        root / "openlane/IntegerPLL_DCO_EINVP/runs/librelane_signoff/rcx-magic/IntegerPLL_DCO_EINVP.rcx.spice",
        root / "openlane/IntegerPLL_BBPD/runs/librelane_signoff/rcx-magic/IntegerPLL_BBPD.rcx.spice",
        root / "openlane/IntegerPLL_HardMacroTop_EINVP/runs/librelane_signoff/final/spef/nom/IntegerPLL_HardMacroTop_EINVP.nom.spef",
        root / "openlane/IntegerPLL_HardMacroTop_EINVP/runs/librelane_signoff/final/spice/IntegerPLL_HardMacroTop_EINVP.spice",
        root / "openlane/IntegerPLL_DigitalCore/runs/librelane_signoff_force127_s4a2/final/nl/IntegerPLL_DigitalCore.nl.v",
    ]
    csv_path = require_path(root, relpath)
    for source in source_paths:
        if require_path(root, str(source.relative_to(root))).stat().st_mtime > csv_path.stat().st_mtime:
            raise ValueError(f"{relpath} CSV is older than {source}")

    return {
        **common,
        "corner": "ss",
        "case": row["case"],
        "check_mode": row["check_mode"],
        "ref_mhz": to_float(row, "ref_mhz"),
        "target_freq_mhz": to_float(row, "target_freq_mhz"),
        "start_code": start_code,
        "end_code": end_code,
        "response_code": response_code,
        "lock_observed_min_code": lock_min,
        "lock_observed_max_code": lock_max,
        "tail_rise_count": tail_rises,
        "tail_freq_mhz": tail_freq,
        "tail_abs_error_mhz": tail_error,
        "startup_freq_mhz": startup_freq,
        "elapsed_s": to_float(row, "elapsed_s"),
    }


def check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_startup_mpi16_klu(root):
    relpath = (
        "build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_startup_low_50ns_mpi16_klu/"
        "mapped_loop_check.csv"
    )
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 1:
        raise ValueError(f"{relpath} expected 1 row, found {len(rows)}")
    require_all_pass(rows)
    row = rows[0]
    common = check_einvp_hardtop_spef_rc_common(
        row,
        relpath,
        "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_diag",
    )

    if row.get("case") != "low_start" or row.get("check_mode") != "startup":
        raise ValueError(f"{relpath} has wrong case/check mode: {row}")
    if abs(to_float(row, "initial_dco_phase_cycles")) > 1e-9:
        raise ValueError(f"{relpath} has unexpected initial phase: {row}")
    if abs(to_float(row, "enable_ns") - 85.0) > 1e-9 or abs(to_float(row, "clear_width_ns") - 60.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong enable/reset timing: {row}")
    if abs(to_float(row, "end_meas_ns") - 50.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong end measurement time: {row}")
    if abs(to_float(row, "start_code")) > 0.5 or abs(to_float(row, "end_code")) > 0.5:
        raise ValueError(f"{relpath} did not remain at the low startup code: {row}")
    startup_rises = to_int(row, "startup_rise_count")
    startup_freq = to_float(row, "startup_freq_mhz")
    if startup_rises < 2 or not (49.0 <= startup_freq <= 52.0):
        raise ValueError(f"{relpath} has unexpected EINVP low-code startup: {row}")

    return {
        **common,
        "case": row["case"],
        "check_mode": row["check_mode"],
        "startup_rise_count": startup_rises,
        "startup_freq_mhz": startup_freq,
    }


def check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_motion_low_mpi16_klu(root):
    relpath = (
        "build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_motion_low_early_en_90ns_mpi16_klu/"
        "mapped_loop_check.csv"
    )
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 1:
        raise ValueError(f"{relpath} expected 1 row, found {len(rows)}")
    require_all_pass(rows)
    row = rows[0]
    common = check_einvp_hardtop_spef_rc_common(
        row,
        relpath,
        "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_motion_low_early_en_diag",
    )

    if row.get("case") != "low_start" or row.get("check_mode") != "motion":
        raise ValueError(f"{relpath} has wrong case/check mode: {row}")
    if abs(to_float(row, "initial_dco_phase_cycles")) > 1e-9:
        raise ValueError(f"{relpath} has unexpected initial phase: {row}")
    if abs(to_float(row, "start_meas_ns") - 39.0) > 1e-9 or abs(to_float(row, "end_meas_ns") - 89.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong measurement window: {row}")
    if abs(to_float(row, "enable_ns") - 40.0) > 1e-9 or abs(to_float(row, "clear_width_ns") - 20.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong early-enable timing: {row}")

    start_code = to_float(row, "start_code")
    end_code = to_float(row, "end_code")
    response_code = to_float(row, "response_code")
    observed_min_code = to_float(row, "observed_min_code")
    observed_max_code = to_float(row, "observed_max_code")
    if abs(start_code) > 0.5 or observed_min_code > 0.5:
        raise ValueError(f"{relpath} did not start at low rail: {row}")
    if end_code < 2.0 or response_code < 2.0 or observed_max_code < 2.0:
        raise ValueError(f"{relpath} lacks EINVP low-start upward first motion: {row}")
    startup_rises = to_int(row, "startup_rise_count")
    startup_freq = to_float(row, "startup_freq_mhz")
    if startup_rises < 4 or not (49.0 <= startup_freq <= 52.0):
        raise ValueError(f"{relpath} has unexpected EINVP low-code startup: {row}")

    return {
        **common,
        "case": row["case"],
        "check_mode": row["check_mode"],
        "start_code": start_code,
        "end_code": end_code,
        "response_code": response_code,
        "startup_rise_count": startup_rises,
        "startup_freq_mhz": startup_freq,
    }


def check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_motion_high_mpi16_klu(root):
    relpath = (
        "build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_motion_high_early_en_90ns_mpi16_klu/"
        "mapped_loop_check.csv"
    )
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 1:
        raise ValueError(f"{relpath} expected 1 row, found {len(rows)}")
    require_all_pass(rows)
    row = rows[0]
    common = check_einvp_hardtop_spef_rc_common(
        row,
        relpath,
        "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_motion_high_early_en_diag",
    )

    if row.get("case") != "high_start" or row.get("check_mode") != "motion":
        raise ValueError(f"{relpath} has wrong case/check mode: {row}")
    if abs(to_float(row, "initial_dco_phase_cycles") - 0.5) > 1e-9:
        raise ValueError(f"{relpath} has unexpected initial phase: {row}")
    if abs(to_float(row, "start_meas_ns") - 39.0) > 1e-9 or abs(to_float(row, "end_meas_ns") - 89.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong measurement window: {row}")
    if abs(to_float(row, "enable_ns") - 40.0) > 1e-9 or abs(to_float(row, "clear_width_ns") - 20.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong early-enable timing: {row}")

    start_code = to_float(row, "start_code")
    end_code = to_float(row, "end_code")
    response_code = to_float(row, "response_code")
    observed_min_code = to_float(row, "observed_min_code")
    observed_max_code = to_float(row, "observed_max_code")
    if abs(start_code - 255.0) > 0.5 or observed_max_code < 254.5:
        raise ValueError(f"{relpath} did not start at high rail: {row}")
    if end_code > 244.0 or response_code > 244.0 or observed_min_code > 244.0:
        raise ValueError(f"{relpath} lacks EINVP high-start downward first motion: {row}")
    startup_rises = to_int(row, "startup_rise_count")
    startup_freq = to_float(row, "startup_freq_mhz")
    if startup_rises < 5 or not (60.0 <= startup_freq <= 75.0):
        raise ValueError(f"{relpath} has unexpected EINVP high-code startup: {row}")

    return {
        **common,
        "case": row["case"],
        "check_mode": row["check_mode"],
        "start_code": start_code,
        "end_code": end_code,
        "response_code": response_code,
        "startup_rise_count": startup_rises,
        "startup_freq_mhz": startup_freq,
    }


def check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_midcode_lock_mpi16_klu(root):
    relpath = (
        "build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_midcode_loaded_ref_lock_220ns_mpi16_klu/"
        "mapped_loop_check.csv"
    )
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 1:
        raise ValueError(f"{relpath} expected 1 row, found {len(rows)}")
    require_all_pass(rows)
    row = rows[0]
    common = check_einvp_hardtop_spef_rc_common(
        row,
        relpath,
        "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_midcode_loaded_ref_diag",
        expected_target_freq_mhz=58.57351844172986,
    )

    if row.get("case") != "mid_start_inc" or row.get("check_mode") != "lock_window":
        raise ValueError(f"{relpath} has wrong case/check mode: {row}")
    if abs(to_float(row, "initial_dco_phase_cycles") - 0.25) > 1e-9:
        raise ValueError(f"{relpath} has unexpected initial phase: {row}")
    if abs(to_float(row, "enable_ns") - 85.0) > 1e-9 or abs(to_float(row, "clear_width_ns") - 60.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong enable/reset timing: {row}")
    if abs(to_float(row, "start_meas_ns") - 84.0) > 1e-9 or abs(to_float(row, "end_meas_ns") - 219.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong measurement window: {row}")
    if abs(to_float(row, "lock_meas_start_ns") - 150.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong lock measurement start: {row}")
    if row.get("lock_code_check") != "window":
        raise ValueError(f"{relpath} has wrong lock-code check: {row}")
    if to_float(row, "lock_min_code") != 112.0 or to_float(row, "lock_max_code") != 144.0:
        raise ValueError(f"{relpath} has wrong lock code window: {row}")
    if abs(to_float(row, "ref_mhz") - 29.28675922086493) > 1e-9:
        raise ValueError(f"{relpath} has wrong hard-top-loaded reference: {row}")
    if abs(to_float(row, "target_freq_mhz") - 58.57351844172986) > 1e-9:
        raise ValueError(f"{relpath} has wrong hard-top-loaded target: {row}")
    if abs(to_float(row, "lock_max_abs_ferr_mhz") - 0.5) > 1e-9:
        raise ValueError(f"{relpath} has wrong frequency-error limit: {row}")

    start_code = to_float(row, "start_code")
    end_code = to_float(row, "end_code")
    observed_min_code = to_float(row, "observed_min_code")
    observed_max_code = to_float(row, "observed_max_code")
    response_code = to_float(row, "response_code")
    lock_min = to_float(row, "lock_observed_min_code")
    lock_max = to_float(row, "lock_observed_max_code")
    if abs(start_code - 128.0) > 0.5:
        raise ValueError(f"{relpath} did not start at mid code: {row}")
    if not (125.0 <= end_code <= 128.0):
        raise ValueError(f"{relpath} has unexpected endpoint code: {row}")
    if not (125.0 <= observed_min_code <= observed_max_code <= 128.0):
        raise ValueError(f"{relpath} leaves the expected mid-code band: {row}")
    if not (125.0 <= lock_min <= lock_max <= 128.0):
        raise ValueError(f"{relpath} tail window leaves the expected mid-code band: {row}")
    if abs(response_code - 128.0) > 0.5:
        raise ValueError(f"{relpath} changed expected response code: {row}")

    startup_rises = to_int(row, "startup_rise_count")
    startup_freq = to_float(row, "startup_freq_mhz")
    tail_rises = to_int(row, "tail_rise_count")
    tail_freq = to_float(row, "tail_freq_mhz")
    tail_error = to_float(row, "tail_abs_error_mhz")
    if startup_rises < 10 or not (58.0 <= startup_freq <= 59.0):
        raise ValueError(f"{relpath} has unexpected startup frequency: {row}")
    if tail_rises < 4 or not (58.5 <= tail_freq <= 58.7) or tail_error > 0.5:
        raise ValueError(f"{relpath} lacks a bounded tail frequency: {row}")

    return {
        **common,
        "case": row["case"],
        "check_mode": row["check_mode"],
        "ref_mhz": to_float(row, "ref_mhz"),
        "target_freq_mhz": to_float(row, "target_freq_mhz"),
        "start_code": start_code,
        "end_code": end_code,
        "response_code": response_code,
        "lock_observed_min_code": lock_min,
        "lock_observed_max_code": lock_max,
        "tail_rise_count": tail_rises,
        "tail_freq_mhz": tail_freq,
        "tail_abs_error_mhz": tail_error,
        "startup_freq_mhz": startup_freq,
    }


def check_final_signoff_hardtop_einvp_spef_rc_corner_midcode_lock_mpi16_klu(root):
    cases = {
        "min": {
            "relpath": (
                "build/spice_pll_final_force127_hardtop_einvp_spef_rc_min_extracted_dco_midcode_loaded_ref_lock_220ns_mpi16_klu/"
                "mapped_loop_check.csv"
            ),
            "scope": "final_signoff_force127_hardtop_einvp_spef_rc_min_extracted_dco_midcode_loaded_ref_diag",
            "spef_path_fragment": "/spef/min/IntegerPLL_HardMacroTop_EINVP.min.spef",
            "cap_nodes": 1668,
            "resistors": 1551,
            "cap_total_ff": 23096.023,
            "total_devices": "Total Devices                                          65719",
            "unknowns": "Number of Unknowns = 184369",
            "startup_freq_min_mhz": 58.2,
            "startup_freq_max_mhz": 58.5,
            "tail_freq_min_mhz": 58.45,
            "tail_freq_max_mhz": 58.55,
        },
        "max": {
            "relpath": (
                "build/spice_pll_final_force127_hardtop_einvp_spef_rc_max_extracted_dco_midcode_loaded_ref_lock_220ns_mpi16_klu/"
                "mapped_loop_check.csv"
            ),
            "scope": "final_signoff_force127_hardtop_einvp_spef_rc_max_extracted_dco_midcode_loaded_ref_diag",
            "spef_path_fragment": "/spef/max/IntegerPLL_HardMacroTop_EINVP.max.spef",
            "cap_nodes": 1905,
            "resistors": 1798,
            "cap_total_ff": 27119.190,
            "total_devices": "Total Devices                                          66203",
            "unknowns": "Number of Unknowns = 184616",
            "startup_freq_min_mhz": 58.2,
            "startup_freq_max_mhz": 58.5,
            "tail_freq_min_mhz": 58.50,
            "tail_freq_max_mhz": 58.60,
        },
    }
    rows_by_corner = {}
    source_paths = [
        root / "scripts/spice_pll_mapped_loop_check.py",
        root / "openlane/IntegerPLL_DCO_EINVP/runs/librelane_signoff/rcx-magic/IntegerPLL_DCO_EINVP.rcx.spice",
        root / "openlane/IntegerPLL_BBPD/runs/librelane_signoff/rcx-magic/IntegerPLL_BBPD.rcx.spice",
        root / "openlane/IntegerPLL_HardMacroTop_EINVP/runs/librelane_signoff/final/spice/IntegerPLL_HardMacroTop_EINVP.spice",
        root / "openlane/IntegerPLL_DigitalCore/runs/librelane_signoff_force127_s4a2/final/nl/IntegerPLL_DigitalCore.nl.v",
    ]
    for corner, expected in cases.items():
        relpath = expected["relpath"]
        csv_path = require_path(root, relpath)
        rows = read_csv(csv_path)
        if len(rows) != 1:
            raise ValueError(f"{relpath} expected 1 row, found {len(rows)}")
        require_all_pass(rows)
        row = rows[0]
        if row.get("simulator") != "xyce" or to_int(row, "xyce_mpi_procs") != 16:
            raise ValueError(f"{relpath} has unexpected Xyce process count: {row}")
        if "-linsolv KLU" not in row.get("xyce_command", ""):
            raise ValueError(f"{relpath} does not record KLU: {row}")
        if row.get("bbpd_impl") != "postlayout" or row.get("dco_model") != "postlayout_rcx":
            raise ValueError(f"{relpath} has wrong post-layout models: {row}")
        if row.get("digital_scope") != expected["scope"]:
            raise ValueError(f"{relpath} has wrong digital scope: {row}")
        if row.get("code_observer_source") != "dco_therm":
            raise ValueError(f"{relpath} has wrong code observer: {row}")
        if to_int(row, "mapped_instance_count") < 2000 or to_int(row, "skipped_physical_only_cells") != 4138:
            raise ValueError(f"{relpath} has wrong mapped-netlist coverage: {row}")
        if to_int(row, "ki") != 160 or to_int(row, "kp") != 8:
            raise ValueError(f"{relpath} has wrong DLF gain settings: {row}")
        if to_int(row, "dlf_frac_width") != 6 or to_int(row, "ndiv") != 2:
            raise ValueError(f"{relpath} has wrong DLF/NDIV settings: {row}")
        if row.get("case") != "mid_start_inc" or row.get("check_mode") != "lock_window":
            raise ValueError(f"{relpath} has wrong case/check mode: {row}")
        if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
            raise ValueError(f"{relpath} did not finish cleanly: {row}")
        if abs(to_float(row, "ref_mhz") - 29.28675922086493) > 1e-9:
            raise ValueError(f"{relpath} has wrong hard-top-loaded reference: {row}")
        if abs(to_float(row, "target_freq_mhz") - 58.57351844172986) > 1e-9:
            raise ValueError(f"{relpath} has wrong hard-top-loaded target: {row}")
        if abs(to_float(row, "initial_dco_phase_cycles") - 0.25) > 1e-9:
            raise ValueError(f"{relpath} has wrong initial DCO phase: {row}")
        if abs(to_float(row, "enable_ns") - 85.0) > 1e-9 or abs(to_float(row, "clear_width_ns") - 60.0) > 1e-9:
            raise ValueError(f"{relpath} has wrong enable/reset timing: {row}")
        if abs(to_float(row, "start_meas_ns") - 84.0) > 1e-9 or abs(to_float(row, "end_meas_ns") - 219.0) > 1e-9:
            raise ValueError(f"{relpath} has wrong measurement window: {row}")
        if abs(to_float(row, "lock_meas_start_ns") - 150.0) > 1e-9:
            raise ValueError(f"{relpath} has wrong lock measurement start: {row}")
        if row.get("lock_code_check") != "window":
            raise ValueError(f"{relpath} has wrong lock-code check: {row}")
        if to_float(row, "lock_min_code") != 112.0 or to_float(row, "lock_max_code") != 144.0:
            raise ValueError(f"{relpath} has wrong lock code window: {row}")
        if abs(to_float(row, "lock_max_abs_ferr_mhz") - 0.75) > 1e-9:
            raise ValueError(f"{relpath} has wrong frequency-error limit: {row}")

        if row.get("hardtop_spef_mode") != "distributed_rc":
            raise ValueError(f"{relpath} has wrong hard-top SPEF mode: {row}")
        if expected["spef_path_fragment"] not in row.get("hardtop_spef_path", ""):
            raise ValueError(f"{relpath} does not use the {corner} E hard-top SPEF: {row}")
        if to_int(row, "hardtop_spef_cap_nets") != 261:
            raise ValueError(f"{relpath} has wrong hard-top SPEF net count: {row}")
        if to_int(row, "hardtop_spef_cap_nodes") != expected["cap_nodes"]:
            raise ValueError(f"{relpath} has wrong hard-top SPEF cap-node count: {row}")
        if to_int(row, "hardtop_spef_resistors") != expected["resistors"]:
            raise ValueError(f"{relpath} has wrong hard-top SPEF resistor count: {row}")
        if to_int(row, "hardtop_spef_pin_substitutions") != 260 or to_int(row, "hardtop_spef_dco_therm_nets") != 255:
            raise ValueError(f"{relpath} has incomplete hard-top pin/DCO thermometer mapping: {row}")
        if abs(to_float(row, "hardtop_spef_cap_total_ff") - expected["cap_total_ff"]) > 0.001:
            raise ValueError(f"{relpath} has wrong hard-top SPEF capacitance: {row}")

        start_code = to_float(row, "start_code")
        end_code = to_float(row, "end_code")
        observed_min_code = to_float(row, "observed_min_code")
        observed_max_code = to_float(row, "observed_max_code")
        response_code = to_float(row, "response_code")
        lock_min = to_float(row, "lock_observed_min_code")
        lock_max = to_float(row, "lock_observed_max_code")
        if abs(start_code - 128.0) > 0.5 or abs(end_code - 125.0) > 0.5:
            raise ValueError(f"{relpath} has unexpected mid-code endpoint: {row}")
        if not (125.0 <= observed_min_code <= observed_max_code <= 128.0):
            raise ValueError(f"{relpath} leaves the expected code band: {row}")
        if not (125.0 <= lock_min <= lock_max <= 128.0):
            raise ValueError(f"{relpath} tail window leaves the expected code band: {row}")
        if abs(response_code - 128.0) > 0.5:
            raise ValueError(f"{relpath} has unexpected response code: {row}")

        startup_rises = to_int(row, "startup_rise_count")
        startup_freq = to_float(row, "startup_freq_mhz")
        tail_rises = to_int(row, "tail_rise_count")
        tail_freq = to_float(row, "tail_freq_mhz")
        tail_error = to_float(row, "tail_abs_error_mhz")
        if startup_rises < 10:
            raise ValueError(f"{relpath} has too few startup rises: {row}")
        if not (expected["startup_freq_min_mhz"] <= startup_freq <= expected["startup_freq_max_mhz"]):
            raise ValueError(f"{relpath} has unexpected startup frequency: {row}")
        if tail_rises < 4:
            raise ValueError(f"{relpath} has too few tail rises: {row}")
        if not (expected["tail_freq_min_mhz"] <= tail_freq <= expected["tail_freq_max_mhz"]) or tail_error > 0.1:
            raise ValueError(f"{relpath} lacks a bounded tail frequency: {row}")

        netlist_path = Path(row.get("netlist", "")).expanduser()
        if not netlist_path.is_file():
            raise ValueError(f"{relpath} missing generated deck: {row}")
        netlist_text = netlist_path.read_text(encoding="ascii", errors="replace")
        if "IntegerPLL_DCO_EINVP" not in netlist_text:
            raise ValueError(f"{relpath} generated deck does not instantiate IntegerPLL_DCO_EINVP")
        if "IntegerPLL_DCO.rcx.spice" in netlist_text:
            raise ValueError(f"{relpath} generated deck includes the NAND-load DCO RCX deck")
        cap_count = count_hardtop_spef_caps(netlist_path)
        if cap_count != expected["cap_nodes"]:
            raise ValueError(f"{relpath} hard-top SPEF cap count mismatch: {cap_count} vs {expected['cap_nodes']}")
        resistor_count = count_hardtop_spef_resistors(netlist_path)
        if resistor_count != expected["resistors"]:
            raise ValueError(f"{relpath} hard-top SPEF resistor count mismatch: {resistor_count} vs {expected['resistors']}")

        log_path = Path(row.get("log", "")).expanduser()
        if not log_path.is_file():
            raise ValueError(f"{relpath} missing Xyce log: {log_path}")
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        for required in (
            expected["total_devices"],
            expected["unknowns"],
            "Timing summary of 16 processors",
        ):
            if required not in log_text:
                raise ValueError(f"{relpath} log does not contain {required!r}")
        elapsed_s = xyce_elapsed_run_time_s(log_text)
        if elapsed_s is None or elapsed_s <= 0.0:
            raise ValueError(f"{relpath} log lacks elapsed runtime: {log_path}")

        corner_spef = root / f"openlane/IntegerPLL_HardMacroTop_EINVP/runs/librelane_signoff/final/spef/{corner}/IntegerPLL_HardMacroTop_EINVP.{corner}.spef"
        for source in [*source_paths, corner_spef]:
            if require_path(root, str(source.relative_to(root))).stat().st_mtime > csv_path.stat().st_mtime:
                raise ValueError(f"{relpath} CSV is older than {source}")

        rows_by_corner[corner] = {
            "cap_nodes": to_int(row, "hardtop_spef_cap_nodes"),
            "resistors": to_int(row, "hardtop_spef_resistors"),
            "cap_total_ff": to_float(row, "hardtop_spef_cap_total_ff"),
            "startup_freq_mhz": startup_freq,
            "tail_freq_mhz": tail_freq,
            "tail_abs_error_mhz": tail_error,
            "tail_rise_count": tail_rises,
            "start_code": start_code,
            "end_code": end_code,
            "lock_observed_min_code": lock_min,
            "lock_observed_max_code": lock_max,
            "elapsed_s": elapsed_s,
        }

    if rows_by_corner["max"]["cap_total_ff"] <= rows_by_corner["min"]["cap_total_ff"]:
        raise ValueError(f"EINVP hard-top RC corner capacitance is not ordered: {rows_by_corner}")
    return {
        "corners": ["min", "max"],
        "case": "mid_start_inc",
        "check_mode": "lock_window",
        "xyce_mpi_procs": 16,
        "hardtop_spef_mode": "distributed_rc",
        "ki": 160,
        "kp": 8,
        "dlf_frac_width": 6,
        "ndiv": 2,
        "rows": rows_by_corner,
        "cap_span_ff": rows_by_corner["max"]["cap_total_ff"] - rows_by_corner["min"]["cap_total_ff"],
    }


def check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_low_progress_mpi16_klu(root):
    relpath = (
        "build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_low_loaded_ref_progress_360ns_mpi16_klu/"
        "mapped_loop_check.csv"
    )
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 1:
        raise ValueError(f"{relpath} expected 1 row, found {len(rows)}")
    require_all_pass(rows)
    row = rows[0]
    common = check_einvp_hardtop_spef_rc_common(
        row,
        relpath,
        "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_low_loaded_ref_progress_diag",
        expected_target_freq_mhz=58.57351844172986,
    )

    if row.get("case") != "low_start" or row.get("check_mode") != "motion":
        raise ValueError(f"{relpath} has wrong case/check mode: {row}")
    if abs(to_float(row, "initial_dco_phase_cycles")) > 1e-9:
        raise ValueError(f"{relpath} has unexpected initial phase: {row}")
    if abs(to_float(row, "enable_ns") - 85.0) > 1e-9 or abs(to_float(row, "clear_width_ns") - 60.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong enable/reset timing: {row}")
    if abs(to_float(row, "start_meas_ns") - 84.0) > 1e-9 or abs(to_float(row, "end_meas_ns") - 359.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong measurement window: {row}")
    if abs(to_float(row, "lock_meas_start_ns") - 280.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong tail measurement start: {row}")
    if abs(to_float(row, "ref_mhz") - 29.28675922086493) > 1e-9:
        raise ValueError(f"{relpath} has wrong hard-top-loaded reference: {row}")

    start_code = to_float(row, "start_code")
    end_code = to_float(row, "end_code")
    observed_min_code = to_float(row, "observed_min_code")
    observed_max_code = to_float(row, "observed_max_code")
    response_code = to_float(row, "response_code")
    lock_min = to_float(row, "lock_observed_min_code")
    lock_max = to_float(row, "lock_observed_max_code")
    if abs(start_code) > 0.5 or observed_min_code > 0.5:
        raise ValueError(f"{relpath} did not start at the low rail: {row}")
    if end_code < 60.0 or response_code < 60.0 or observed_max_code < 60.0:
        raise ValueError(f"{relpath} lacks substantial low-rail escape: {row}")
    if not (40.0 <= lock_min <= lock_max <= 64.0):
        raise ValueError(f"{relpath} has unexpected late-window code progress: {row}")

    startup_rises = to_int(row, "startup_rise_count")
    startup_freq = to_float(row, "startup_freq_mhz")
    tail_rises = to_int(row, "tail_rise_count")
    tail_freq = to_float(row, "tail_freq_mhz")
    tail_error = to_float(row, "tail_abs_error_mhz")
    if startup_rises < 18 or not (51.0 <= startup_freq <= 52.5):
        raise ValueError(f"{relpath} has unexpected startup frequency: {row}")
    if tail_rises < 4 or not (53.0 <= tail_freq <= 54.5) or tail_error > 5.0:
        raise ValueError(f"{relpath} lacks expected low-progress tail frequency: {row}")

    return {
        **common,
        "case": row["case"],
        "check_mode": row["check_mode"],
        "ref_mhz": to_float(row, "ref_mhz"),
        "target_freq_mhz": to_float(row, "target_freq_mhz"),
        "start_code": start_code,
        "end_code": end_code,
        "response_code": response_code,
        "lock_observed_min_code": lock_min,
        "lock_observed_max_code": lock_max,
        "tail_rise_count": tail_rises,
        "tail_freq_mhz": tail_freq,
        "tail_abs_error_mhz": tail_error,
        "startup_freq_mhz": startup_freq,
    }


def check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_high_progress_mpi16_klu(root):
    relpath = (
        "build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_high_loaded_ref_progress_360ns_mpi16_klu/"
        "mapped_loop_check.csv"
    )
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 1:
        raise ValueError(f"{relpath} expected 1 row, found {len(rows)}")
    require_all_pass(rows)
    row = rows[0]
    common = check_einvp_hardtop_spef_rc_common(
        row,
        relpath,
        "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_high_loaded_ref_progress_diag",
        expected_target_freq_mhz=58.57351844172986,
    )

    if row.get("case") != "high_start" or row.get("check_mode") != "motion":
        raise ValueError(f"{relpath} has wrong case/check mode: {row}")
    if abs(to_float(row, "initial_dco_phase_cycles") - 0.5) > 1e-9:
        raise ValueError(f"{relpath} has unexpected initial phase: {row}")
    if abs(to_float(row, "enable_ns") - 85.0) > 1e-9 or abs(to_float(row, "clear_width_ns") - 60.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong enable/reset timing: {row}")
    if abs(to_float(row, "start_meas_ns") - 84.0) > 1e-9 or abs(to_float(row, "end_meas_ns") - 359.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong measurement window: {row}")
    if abs(to_float(row, "lock_meas_start_ns") - 280.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong tail measurement start: {row}")
    if abs(to_float(row, "ref_mhz") - 29.28675922086493) > 1e-9:
        raise ValueError(f"{relpath} has wrong hard-top-loaded reference: {row}")

    start_code = to_float(row, "start_code")
    end_code = to_float(row, "end_code")
    observed_min_code = to_float(row, "observed_min_code")
    observed_max_code = to_float(row, "observed_max_code")
    response_code = to_float(row, "response_code")
    lock_min = to_float(row, "lock_observed_min_code")
    lock_max = to_float(row, "lock_observed_max_code")
    if start_code < 254.5 or observed_max_code < 254.5:
        raise ValueError(f"{relpath} did not start at the high rail: {row}")
    if not (160.0 <= end_code <= 180.0) or not (160.0 <= response_code <= 180.0):
        raise ValueError(f"{relpath} lacks expected high-rail escape: {row}")
    if not (160.0 <= observed_min_code <= 180.0):
        raise ValueError(f"{relpath} has unexpected minimum code progress: {row}")
    if not (168.0 <= lock_min <= lock_max <= 196.0):
        raise ValueError(f"{relpath} has unexpected late-window code progress: {row}")

    startup_rises = to_int(row, "startup_rise_count")
    startup_freq = to_float(row, "startup_freq_mhz")
    tail_rises = to_int(row, "tail_rise_count")
    tail_freq = to_float(row, "tail_freq_mhz")
    tail_error = to_float(row, "tail_abs_error_mhz")
    if startup_rises < 18 or not (64.5 <= startup_freq <= 67.0):
        raise ValueError(f"{relpath} has unexpected startup frequency: {row}")
    if tail_rises < 4 or not (62.0 <= tail_freq <= 64.0) or tail_error > 5.0:
        raise ValueError(f"{relpath} lacks expected high-progress tail frequency: {row}")

    return {
        **common,
        "case": row["case"],
        "check_mode": row["check_mode"],
        "ref_mhz": to_float(row, "ref_mhz"),
        "target_freq_mhz": to_float(row, "target_freq_mhz"),
        "start_code": start_code,
        "end_code": end_code,
        "response_code": response_code,
        "lock_observed_min_code": lock_min,
        "lock_observed_max_code": lock_max,
        "tail_rise_count": tail_rises,
        "tail_freq_mhz": tail_freq,
        "tail_abs_error_mhz": tail_error,
        "startup_freq_mhz": startup_freq,
    }


def check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_high_lock_mpi16_klu(root):
    relpath = (
        "build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_high_loaded_ref_lock_760ns_mpi16_klu/"
        "mapped_loop_check.csv"
    )
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 1:
        raise ValueError(f"{relpath} expected 1 row, found {len(rows)}")
    require_all_pass(rows)
    row = rows[0]
    common = check_einvp_hardtop_spef_rc_common(
        row,
        relpath,
        "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_high_loaded_ref_lock_diag",
        expected_target_freq_mhz=58.57351844172986,
    )

    if row.get("case") != "high_start" or row.get("check_mode") != "lock_window":
        raise ValueError(f"{relpath} has wrong case/check mode: {row}")
    if abs(to_float(row, "initial_dco_phase_cycles") - 0.5) > 1e-9:
        raise ValueError(f"{relpath} has unexpected initial phase: {row}")
    if abs(to_float(row, "enable_ns") - 85.0) > 1e-9 or abs(to_float(row, "clear_width_ns") - 60.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong enable/reset timing: {row}")
    if abs(to_float(row, "start_meas_ns") - 84.0) > 1e-9 or abs(to_float(row, "end_meas_ns") - 759.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong measurement window: {row}")
    if abs(to_float(row, "lock_meas_start_ns") - 650.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong lock measurement start: {row}")
    if abs(to_float(row, "lock_min_code") - 112.0) > 1e-9 or abs(to_float(row, "lock_max_code") - 144.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong lock code window: {row}")
    if abs(to_float(row, "lock_max_abs_ferr_mhz") - 1.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong lock frequency-error limit: {row}")
    if abs(to_float(row, "ref_mhz") - 29.28675922086493) > 1e-9:
        raise ValueError(f"{relpath} has wrong hard-top-loaded reference: {row}")

    start_code = to_float(row, "start_code")
    end_code = to_float(row, "end_code")
    observed_min_code = to_float(row, "observed_min_code")
    observed_max_code = to_float(row, "observed_max_code")
    response_code = to_float(row, "response_code")
    lock_min = to_float(row, "lock_observed_min_code")
    lock_max = to_float(row, "lock_observed_max_code")
    if start_code < 254.5 or observed_max_code < 254.5:
        raise ValueError(f"{relpath} did not start at the high rail: {row}")
    if not (126.0 <= end_code <= 136.0):
        raise ValueError(f"{relpath} has unexpected endpoint code: {row}")
    if not (124.0 <= response_code <= 132.0):
        raise ValueError(f"{relpath} has unexpected response code: {row}")
    if not (124.0 <= observed_min_code <= 132.0):
        raise ValueError(f"{relpath} has unexpected minimum code: {row}")
    if not (124.0 <= lock_min <= lock_max <= 136.0):
        raise ValueError(f"{relpath} tail window leaves the expected high-lock band: {row}")

    startup_rises = to_int(row, "startup_rise_count")
    startup_freq = to_float(row, "startup_freq_mhz")
    tail_rises = to_int(row, "tail_rise_count")
    tail_freq = to_float(row, "tail_freq_mhz")
    tail_error = to_float(row, "tail_abs_error_mhz")
    if startup_rises < 40 or not (61.0 <= startup_freq <= 63.0):
        raise ValueError(f"{relpath} has unexpected startup frequency: {row}")
    if tail_rises < 5 or not (58.6 <= tail_freq <= 59.0) or tail_error > 0.5:
        raise ValueError(f"{relpath} lacks expected high-lock tail frequency: {row}")

    return {
        **common,
        "case": row["case"],
        "check_mode": row["check_mode"],
        "ref_mhz": to_float(row, "ref_mhz"),
        "target_freq_mhz": to_float(row, "target_freq_mhz"),
        "start_code": start_code,
        "end_code": end_code,
        "response_code": response_code,
        "lock_observed_min_code": lock_min,
        "lock_observed_max_code": lock_max,
        "tail_rise_count": tail_rises,
        "tail_freq_mhz": tail_freq,
        "tail_abs_error_mhz": tail_error,
        "startup_freq_mhz": startup_freq,
    }


def check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_low_lock_mpi16_klu(root):
    relpath = (
        "build/spice_pll_final_force127_hardtop_einvp_spef_rc_extracted_dco_low_loaded_ref_lock_900ns_mpi16_klu/"
        "mapped_loop_check.csv"
    )
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 1:
        raise ValueError(f"{relpath} expected 1 row, found {len(rows)}")
    require_all_pass(rows)
    row = rows[0]
    common = check_einvp_hardtop_spef_rc_common(
        row,
        relpath,
        "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_low_loaded_ref_lock_diag",
        expected_target_freq_mhz=58.57351844172986,
    )

    if row.get("case") != "low_start" or row.get("check_mode") != "lock_window":
        raise ValueError(f"{relpath} has wrong case/check mode: {row}")
    if abs(to_float(row, "initial_dco_phase_cycles")) > 1e-9:
        raise ValueError(f"{relpath} has unexpected initial phase: {row}")
    if abs(to_float(row, "enable_ns") - 85.0) > 1e-9 or abs(to_float(row, "clear_width_ns") - 60.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong enable/reset timing: {row}")
    if abs(to_float(row, "start_meas_ns") - 84.0) > 1e-9 or abs(to_float(row, "end_meas_ns") - 899.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong measurement window: {row}")
    if abs(to_float(row, "lock_meas_start_ns") - 760.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong lock measurement start: {row}")
    if abs(to_float(row, "lock_min_code") - 112.0) > 1e-9 or abs(to_float(row, "lock_max_code") - 144.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong lock code window: {row}")
    if abs(to_float(row, "lock_max_abs_ferr_mhz") - 1.0) > 1e-9:
        raise ValueError(f"{relpath} has wrong lock frequency-error limit: {row}")
    if abs(to_float(row, "ref_mhz") - 29.28675922086493) > 1e-9:
        raise ValueError(f"{relpath} has wrong hard-top-loaded reference: {row}")

    start_code = to_float(row, "start_code")
    end_code = to_float(row, "end_code")
    observed_min_code = to_float(row, "observed_min_code")
    observed_max_code = to_float(row, "observed_max_code")
    response_code = to_float(row, "response_code")
    lock_min = to_float(row, "lock_observed_min_code")
    lock_max = to_float(row, "lock_observed_max_code")
    if abs(start_code) > 0.5 or observed_min_code > 0.5:
        raise ValueError(f"{relpath} did not start at the low rail: {row}")
    if not (120.0 <= end_code <= 130.0):
        raise ValueError(f"{relpath} has unexpected endpoint code: {row}")
    if not (126.0 <= response_code <= 130.0):
        raise ValueError(f"{relpath} has unexpected response code: {row}")
    if observed_max_code < 127.0:
        raise ValueError(f"{relpath} did not reach the expected high side of the lock band: {row}")
    if not (120.0 <= lock_min <= lock_max <= 130.0):
        raise ValueError(f"{relpath} tail window leaves the expected low-lock band: {row}")

    startup_rises = to_int(row, "startup_rise_count")
    startup_freq = to_float(row, "startup_freq_mhz")
    tail_rises = to_int(row, "tail_rise_count")
    tail_freq = to_float(row, "tail_freq_mhz")
    tail_error = to_float(row, "tail_abs_error_mhz")
    if startup_rises < 40 or not (54.5 <= startup_freq <= 56.5):
        raise ValueError(f"{relpath} has unexpected startup frequency: {row}")
    if tail_rises < 6 or not (58.3 <= tail_freq <= 58.7) or tail_error > 0.5:
        raise ValueError(f"{relpath} lacks expected low-lock tail frequency: {row}")

    return {
        **common,
        "case": row["case"],
        "check_mode": row["check_mode"],
        "ref_mhz": to_float(row, "ref_mhz"),
        "target_freq_mhz": to_float(row, "target_freq_mhz"),
        "start_code": start_code,
        "end_code": end_code,
        "response_code": response_code,
        "lock_observed_min_code": lock_min,
        "lock_observed_max_code": lock_max,
        "tail_rise_count": tail_rises,
        "tail_freq_mhz": tail_freq,
        "tail_abs_error_mhz": tail_error,
        "startup_freq_mhz": startup_freq,
    }


def waveform_code_stability(path, start_ns, end_ns, stable_low, stable_high):
    waveform_path = Path(path).expanduser()
    if not waveform_path.is_file():
        raise ValueError(f"missing Xyce waveform: {waveform_path}")

    header = None
    time_index = None
    code_index = None
    intervals = []
    interval_start_ns = None
    interval_end_ns = None
    sample_count = 0
    for line in waveform_path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0].lower() == "index":
            header = [part.lower() for part in parts]
            try:
                time_index = header.index("time")
                code_index = header.index("v(code)")
            except ValueError as exc:
                raise ValueError(f"waveform lacks TIME/V(CODE): {waveform_path}") from exc
            continue
        if header is None or len(parts) < len(header):
            continue
        try:
            time_ns = float(parts[time_index]) * 1.0e9
            code = float(parts[code_index])
        except ValueError:
            continue
        if start_ns > time_ns or time_ns > end_ns:
            continue
        sample_count += 1
        if stable_low <= code <= stable_high:
            if interval_start_ns is None:
                interval_start_ns = time_ns
            interval_end_ns = time_ns
        elif interval_start_ns is not None:
            intervals.append((interval_start_ns, interval_end_ns))
            interval_start_ns = None
            interval_end_ns = None
    if interval_start_ns is not None:
        intervals.append((interval_start_ns, interval_end_ns))
    if sample_count == 0:
        raise ValueError(f"waveform has no code samples in {start_ns:g}-{end_ns:g} ns")

    best = None
    for interval in intervals:
        dwell_ns = interval[1] - interval[0]
        if best is None or dwell_ns > best["dwell_ns"]:
            best = {
                "start_ns": interval[0],
                "end_ns": interval[1],
                "dwell_ns": dwell_ns,
            }
    return best


def waveform_signal_frequency(path, signal, start_ns, end_ns, threshold):
    waveform_path = Path(path).expanduser()
    if not waveform_path.is_file():
        raise ValueError(f"missing Xyce waveform: {waveform_path}")

    signal_name = signal.lower()
    header = None
    time_index = None
    signal_index = None
    prev_time_ns = None
    prev_value = None
    crossings_ns = []
    sample_count = 0
    with waveform_path.open(encoding="utf-8", errors="replace") as waveform_file:
        for line in waveform_file:
            parts = line.split()
            if not parts:
                continue
            if parts[0].lower() == "index":
                header = [part.lower() for part in parts]
                try:
                    time_index = header.index("time")
                    signal_index = header.index(signal_name)
                except ValueError as exc:
                    raise ValueError(f"waveform lacks TIME/{signal}: {waveform_path}") from exc
                continue
            if header is None or len(parts) < len(header):
                continue
            try:
                time_ns = float(parts[time_index]) * 1.0e9
                value = float(parts[signal_index])
            except ValueError:
                continue

            if start_ns <= time_ns <= end_ns:
                sample_count += 1
            if prev_time_ns is not None and prev_value < threshold <= value:
                if time_ns == prev_time_ns:
                    crossing_ns = time_ns
                else:
                    crossing_ns = prev_time_ns + (
                        (threshold - prev_value) / (value - prev_value)
                    ) * (time_ns - prev_time_ns)
                if start_ns <= crossing_ns <= end_ns:
                    crossings_ns.append(crossing_ns)

            prev_time_ns = time_ns
            prev_value = value

    if header is None:
        raise ValueError(f"waveform lacks header: {waveform_path}")
    if sample_count == 0:
        raise ValueError(f"waveform has no {signal} samples in {start_ns:g}-{end_ns:g} ns")
    if len(crossings_ns) < 2:
        raise ValueError(
            f"waveform has only {len(crossings_ns)} {signal} rising crossings "
            f"in {start_ns:g}-{end_ns:g} ns"
        )

    period_ns = (crossings_ns[-1] - crossings_ns[0]) / (len(crossings_ns) - 1)
    return {
        "signal": signal,
        "threshold": threshold,
        "start_ns": start_ns,
        "end_ns": end_ns,
        "sample_count": sample_count,
        "rising_crossings": len(crossings_ns),
        "first_crossing_ns": crossings_ns[0],
        "last_crossing_ns": crossings_ns[-1],
        "period_ns": period_ns,
        "frequency_mhz": 1000.0 / period_ns,
    }


def check_extracted_dco_motion_rows(
    root,
    cases,
    *,
    expected_mpi_procs,
    require_xyce_command=None,
    require_log_text=None,
):
    details = {}
    for case_name, spec in cases.items():
        rows = read_csv(require_path(root, spec["relpath"]))
        if len(rows) != 1:
            raise ValueError(f"{case_name} extracted DCO motion smoke expected 1 row")
        require_all_pass(rows)
        row = rows[0]
        if row.get("case") != case_name:
            raise ValueError(f"extracted DCO motion row has wrong case: {row}")
        if row.get("simulator") != "xyce" or to_int(row, "xyce_mpi_procs") != expected_mpi_procs:
            raise ValueError(f"extracted DCO motion row has unexpected Xyce process count: {row}")
        if require_xyce_command is not None and require_xyce_command not in row.get("xyce_command", ""):
            raise ValueError(f"extracted DCO motion row does not record expected Xyce command: {row}")
        if row.get("bbpd_impl") != "postlayout" or row.get("digital_scope") != "full":
            raise ValueError(f"extracted DCO motion row has wrong implementation scope: {row}")
        if row.get("dco_model") != "postlayout_rcx" or row.get("check_mode") != "motion":
            raise ValueError(f"extracted DCO motion row has wrong DCO/check mode: {row}")
        if row.get("expected") != spec["expected"]:
            raise ValueError(f"extracted DCO motion row has wrong expected direction: {row}")
        if to_int(row, "mapped_instance_count") < 900:
            raise ValueError(f"extracted DCO motion row has too few mapped instances: {row}")
        if to_int(row, "skipped_physical_only_cells") != 0:
            raise ValueError(f"extracted DCO motion row skipped unexpected cells: {row}")
        if to_int(row, "ki") != 255 or to_int(row, "kp") != 32 or to_int(row, "ndiv") != 2:
            raise ValueError(f"extracted DCO motion row has wrong loop setting: {row}")
        if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
            raise ValueError(f"extracted DCO motion row did not finish cleanly: {row}")
        if require_log_text is not None:
            log_path = Path(row.get("log", "")).expanduser()
            if not log_path.is_file():
                raise ValueError(f"extracted DCO motion row missing Xyce log: {log_path}")
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
            if require_log_text not in log_text:
                raise ValueError(f"extracted DCO motion log does not contain {require_log_text!r}")
        if abs(to_float(row, "start_meas_ns") - 79.0) > 1e-9:
            raise ValueError(f"extracted DCO motion row has wrong start window: {row}")
        if abs(to_float(row, "end_meas_ns") - 179.0) > 1e-9:
            raise ValueError(f"extracted DCO motion row has wrong end window: {row}")
        start_code = to_float(row, "start_code")
        end_code = to_float(row, "end_code")
        response = to_float(row, "response_code")
        if abs(start_code - spec["start"]) > 2.0:
            raise ValueError(f"extracted DCO motion row has wrong start code: {row}")
        if spec["expected"] == "increase":
            if response <= start_code + spec["response_limit"]:
                raise ValueError(f"extracted DCO low-start row did not increase: {row}")
        else:
            if response >= spec["response_limit"]:
                raise ValueError(f"extracted DCO high-start row did not decrease: {row}")

        stability = waveform_code_stability(
            row["waveform"],
            79.0,
            179.0,
            spec["stable_low"],
            spec["stable_high"],
        )
        if stability is None or stability["dwell_ns"] < spec["stable_min_dwell_ns"]:
            raise ValueError(
                f"extracted DCO {case_name} waveform lacks at least "
                f"{spec['stable_min_dwell_ns']:g} ns at code "
                f"{spec['stable_low']:g}-{spec['stable_high']:g}"
            )
        details[case_name] = {
            "start_code": start_code,
            "end_code": end_code,
            "response_code": response,
            "stable_code_start_ns": stability["start_ns"],
            "stable_code_end_ns": stability["end_ns"],
            "stable_code_dwell_ns": stability["dwell_ns"],
            "startup_rise_count": to_int(row, "startup_rise_count"),
            "startup_freq_mhz": to_float(row, "startup_freq_mhz"),
        }

    return {
        "rows": len(cases),
        "digital_scope": "full",
        "bbpd_impl": "postlayout",
        "dco_model": "postlayout_rcx",
        "xyce_mpi_procs": expected_mpi_procs,
        "cases": details,
    }


def extracted_dco_motion_case_specs(*, relpath_prefix, relpath_suffix):
    return {
        "low_start": {
            "relpath": (
                f"{relpath_prefix}spice_pll_mapped_loop_extracted_dco_motion_low_180ns_{relpath_suffix}/"
                "mapped_loop_check.csv"
            ),
            "expected": "increase",
            "start": 0.0,
            "response_limit": 1.0,
            "stable_low": 7.5,
            "stable_high": 8.5,
            "stable_min_dwell_ns": 20.0,
        },
        "high_start": {
            "relpath": (
                f"{relpath_prefix}spice_pll_mapped_loop_extracted_dco_motion_high_180ns_{relpath_suffix}/"
                "mapped_loop_check.csv"
            ),
            "expected": "decrease",
            "start": 255.0,
            "response_limit": 253.0,
            "stable_low": 246.5,
            "stable_high": 247.5,
            "stable_min_dwell_ns": 20.0,
        },
    }


def check_extracted_dco_motion_smoke(root):
    return check_extracted_dco_motion_rows(
        root,
        extracted_dco_motion_case_specs(
            relpath_prefix="build/",
            relpath_suffix="serial",
        ),
        expected_mpi_procs=1,
    )


def check_extracted_dco_motion_mpi_klu_smoke(root):
    return check_extracted_dco_motion_rows(
        root,
        extracted_dco_motion_case_specs(
            relpath_prefix="build/",
            relpath_suffix="mpi4_klu",
        ),
        expected_mpi_procs=4,
        require_xyce_command="-linsolv KLU",
        require_log_text="Timing summary of 4 processors",
    )


def check_extracted_dco_low_trend_mpi_klu(root):
    relpath = (
        "build/spice_pll_mapped_loop_extracted_dco_trend_low_260ns_mpi4_klu/"
        "mapped_loop_check.csv"
    )
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 1:
        raise ValueError("extracted DCO low-start trend expected 1 row")
    require_all_pass(rows)
    row = rows[0]

    if row.get("case") != "low_start":
        raise ValueError(f"extracted DCO trend row has wrong case: {row}")
    if row.get("simulator") != "xyce" or to_int(row, "xyce_mpi_procs") != 4:
        raise ValueError(f"extracted DCO trend row is not MPI4 Xyce: {row}")
    if "-linsolv KLU" not in row.get("xyce_command", ""):
        raise ValueError(f"extracted DCO trend row does not record KLU: {row}")
    if row.get("bbpd_impl") != "postlayout" or row.get("digital_scope") != "full":
        raise ValueError(f"extracted DCO trend row has wrong implementation scope: {row}")
    if row.get("dco_model") != "postlayout_rcx" or row.get("check_mode") != "motion":
        raise ValueError(f"extracted DCO trend row has wrong DCO/check mode: {row}")
    if row.get("expected") != "increase":
        raise ValueError(f"extracted DCO trend row has wrong expected direction: {row}")
    if to_int(row, "mapped_instance_count") < 900:
        raise ValueError(f"extracted DCO trend row has too few mapped instances: {row}")
    if to_int(row, "skipped_physical_only_cells") != 0:
        raise ValueError(f"extracted DCO trend row skipped unexpected cells: {row}")
    if to_int(row, "ki") != 255 or to_int(row, "kp") != 32 or to_int(row, "ndiv") != 2:
        raise ValueError(f"extracted DCO trend row has wrong loop setting: {row}")
    if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
        raise ValueError(f"extracted DCO trend row did not finish cleanly: {row}")
    if abs(to_float(row, "start_meas_ns") - 79.0) > 1e-9:
        raise ValueError(f"extracted DCO trend row has wrong start window: {row}")
    if abs(to_float(row, "end_meas_ns") - 259.0) > 1e-9:
        raise ValueError(f"extracted DCO trend row has wrong end window: {row}")

    start_code = to_float(row, "start_code")
    end_code = to_float(row, "end_code")
    response = to_float(row, "response_code")
    start_integ = to_float(row, "start_integ_code")
    end_integ = to_float(row, "end_integ_code")
    max_integ = to_float(row, "observed_max_integ_code")
    startup_rises = to_int(row, "startup_rise_count")
    startup_freq = to_float(row, "startup_freq_mhz")

    if abs(start_code) > 2.0:
        raise ValueError(f"extracted DCO trend row has wrong start code: {row}")
    if response < 7.5 or end_code < 7.5:
        raise ValueError(f"extracted DCO trend row lacks low-start visible correction: {row}")
    if start_integ != 0.0 or end_integ < 0.25 or max_integ < 0.25:
        raise ValueError(f"extracted DCO trend row lacks low-start integrator accumulation: {row}")
    if startup_rises < 10 or not (45.0 <= startup_freq <= 48.0):
        raise ValueError(f"extracted DCO trend row has unexpected oscillator startup: {row}")

    stability = waveform_code_stability(row["waveform"], 79.0, 259.0, 7.5, 8.5)
    if stability is None or stability["dwell_ns"] < 100.0:
        raise ValueError("extracted DCO trend waveform lacks sustained low-start code-8 dwell")

    log_path = Path(row.get("log", "")).expanduser()
    if not log_path.is_file():
        raise ValueError(f"extracted DCO trend row missing Xyce log: {log_path}")
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    if "Timing summary of 4 processors" not in log_text:
        raise ValueError("extracted DCO trend log does not record 4-processor timing")

    return {
        "rows": len(rows),
        "digital_scope": "full",
        "bbpd_impl": "postlayout",
        "dco_model": "postlayout_rcx",
        "xyce_mpi_procs": 4,
        "start_code": start_code,
        "end_code": end_code,
        "response_code": response,
        "start_integ_code": start_integ,
        "end_integ_code": end_integ,
        "observed_max_integ_code": max_integ,
        "stable_code_dwell_ns": stability["dwell_ns"],
        "startup_rise_count": startup_rises,
        "startup_freq_mhz": startup_freq,
    }


def check_extracted_dco_high_trend_mpi_klu(root):
    relpath = (
        "build/spice_pll_mapped_loop_extracted_dco_trend_high_260ns_mpi4_klu/"
        "mapped_loop_check.csv"
    )
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 1:
        raise ValueError("extracted DCO high-start trend expected 1 row")
    require_all_pass(rows)
    row = rows[0]

    if row.get("case") != "high_start":
        raise ValueError(f"extracted DCO high trend row has wrong case: {row}")
    if row.get("simulator") != "xyce" or to_int(row, "xyce_mpi_procs") != 4:
        raise ValueError(f"extracted DCO high trend row is not MPI4 Xyce: {row}")
    if "-linsolv KLU" not in row.get("xyce_command", ""):
        raise ValueError(f"extracted DCO high trend row does not record KLU: {row}")
    if row.get("bbpd_impl") != "postlayout" or row.get("digital_scope") != "full":
        raise ValueError(f"extracted DCO high trend row has wrong implementation scope: {row}")
    if row.get("dco_model") != "postlayout_rcx" or row.get("check_mode") != "motion":
        raise ValueError(f"extracted DCO high trend row has wrong DCO/check mode: {row}")
    if row.get("expected") != "decrease":
        raise ValueError(f"extracted DCO high trend row has wrong expected direction: {row}")
    if to_int(row, "mapped_instance_count") < 900:
        raise ValueError(f"extracted DCO high trend row has too few mapped instances: {row}")
    if to_int(row, "skipped_physical_only_cells") != 0:
        raise ValueError(f"extracted DCO high trend row skipped unexpected cells: {row}")
    if to_int(row, "ki") != 255 or to_int(row, "kp") != 32 or to_int(row, "ndiv") != 2:
        raise ValueError(f"extracted DCO high trend row has wrong loop setting: {row}")
    if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
        raise ValueError(f"extracted DCO high trend row did not finish cleanly: {row}")
    if abs(to_float(row, "start_meas_ns") - 79.0) > 1e-9:
        raise ValueError(f"extracted DCO high trend row has wrong start window: {row}")
    if abs(to_float(row, "end_meas_ns") - 259.0) > 1e-9:
        raise ValueError(f"extracted DCO high trend row has wrong end window: {row}")

    start_code = to_float(row, "start_code")
    end_code = to_float(row, "end_code")
    response = to_float(row, "response_code")
    start_integ = to_float(row, "start_integ_code")
    end_integ = to_float(row, "end_integ_code")
    min_integ = to_float(row, "observed_min_integ_code")
    startup_rises = to_int(row, "startup_rise_count")
    startup_freq = to_float(row, "startup_freq_mhz")

    if abs(start_code - 255.0) > 2.0:
        raise ValueError(f"extracted DCO high trend row has wrong start code: {row}")
    if response > 253.0 or end_code > 247.0:
        raise ValueError(f"extracted DCO high trend row lacks high-start visible correction: {row}")
    if start_integ != 255.0 or end_integ > 254.75 or min_integ > 254.0:
        raise ValueError(f"extracted DCO high trend row lacks high-start integrator accumulation: {row}")
    if startup_rises < 10 or not (50.0 <= startup_freq <= 54.0):
        raise ValueError(f"extracted DCO high trend row has unexpected oscillator startup: {row}")

    stability = waveform_code_stability(row["waveform"], 79.0, 259.0, 245.5, 247.5)
    if stability is None or stability["dwell_ns"] < 50.0:
        raise ValueError("extracted DCO high trend waveform lacks sustained code-246/247 dwell")

    log_path = Path(row.get("log", "")).expanduser()
    if not log_path.is_file():
        raise ValueError(f"extracted DCO high trend row missing Xyce log: {log_path}")
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    if "Timing summary of 4 processors" not in log_text:
        raise ValueError("extracted DCO high trend log does not record 4-processor timing")

    return {
        "rows": len(rows),
        "digital_scope": "full",
        "bbpd_impl": "postlayout",
        "dco_model": "postlayout_rcx",
        "xyce_mpi_procs": 4,
        "start_code": start_code,
        "end_code": end_code,
        "response_code": response,
        "start_integ_code": start_integ,
        "end_integ_code": end_integ,
        "observed_min_integ_code": min_integ,
        "stable_code_dwell_ns": stability["dwell_ns"],
        "startup_rise_count": startup_rises,
        "startup_freq_mhz": startup_freq,
    }


def check_frac6_extracted_dco_trend_mpi16_klu(root):
    specs = (
        {
            "name": "low_start",
            "relpath": "build/spice_pll_mapped_loop_frac6_extracted_dco_trend_low_260ns_mpi16_klu/mapped_loop_check.csv",
            "baseline_relpath": "build/spice_pll_mapped_loop_frac6_extracted_dco_trend_low_260ns_mpi4_klu/mapped_loop_check.csv",
            "expected": "increase",
            "stable_band": (7.5, 9.5),
            "min_dwell_ns": 100.0,
            "startup_freq_range": (45.0, 48.0),
        },
        {
            "name": "high_start",
            "relpath": "build/spice_pll_mapped_loop_frac6_extracted_dco_trend_high_260ns_mpi16_klu/mapped_loop_check.csv",
            "baseline_relpath": "build/spice_pll_mapped_loop_frac6_extracted_dco_trend_high_260ns_mpi4_klu/mapped_loop_check.csv",
            "expected": "decrease",
            "stable_band": (245.5, 247.5),
            "min_dwell_ns": 50.0,
            "startup_freq_range": (50.0, 54.0),
        },
    )

    cases = {}
    elapsed_speedups = {}
    for spec in specs:
        rows = read_csv(require_path(root, spec["relpath"]))
        if len(rows) != 1:
            raise ValueError(f"FRAC6 MPI16 extracted-DCO trend {spec['name']} expected 1 row")
        require_all_pass(rows)
        row = rows[0]
        baseline_row = read_csv(require_path(root, spec["baseline_relpath"]))[0]

        if row.get("case") != spec["name"]:
            raise ValueError(f"FRAC6 MPI16 trend row has wrong case: {row}")
        if row.get("simulator") != "xyce" or to_int(row, "xyce_mpi_procs") != 16:
            raise ValueError(f"FRAC6 MPI16 trend row has wrong simulator/MPI setting: {row}")
        if "-linsolv KLU" not in row.get("xyce_command", ""):
            raise ValueError(f"FRAC6 MPI16 trend row does not record KLU: {row}")
        if row.get("bbpd_impl") != "postlayout" or row.get("digital_scope") != "full":
            raise ValueError(f"FRAC6 MPI16 trend row has wrong implementation scope: {row}")
        if row.get("dco_model") != "postlayout_rcx" or row.get("check_mode") != "motion":
            raise ValueError(f"FRAC6 MPI16 trend row has wrong DCO/check mode: {row}")
        if row.get("expected") != spec["expected"]:
            raise ValueError(f"FRAC6 MPI16 trend row has wrong expected direction: {row}")
        if to_int(row, "mapped_instance_count") < 880:
            raise ValueError(f"FRAC6 MPI16 trend row has too few mapped instances: {row}")
        if to_int(row, "skipped_physical_only_cells") != 0:
            raise ValueError(f"FRAC6 MPI16 trend row skipped unexpected cells: {row}")
        if (
            to_int(row, "ki") != 255
            or to_int(row, "kp") != 32
            or to_int(row, "dlf_frac_width") != 6
            or to_int(row, "ndiv") != 2
        ):
            raise ValueError(f"FRAC6 MPI16 trend row has wrong loop setting: {row}")
        if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
            raise ValueError(f"FRAC6 MPI16 trend row did not finish cleanly: {row}")
        if abs(to_float(row, "start_meas_ns") - 79.0) > 1e-9:
            raise ValueError(f"FRAC6 MPI16 trend row has wrong start window: {row}")
        if abs(to_float(row, "end_meas_ns") - 259.0) > 1e-9:
            raise ValueError(f"FRAC6 MPI16 trend row has wrong end window: {row}")

        start_code = to_float(row, "start_code")
        end_code = to_float(row, "end_code")
        response = to_float(row, "response_code")
        start_integ = to_float(row, "start_integ_code")
        end_integ = to_float(row, "end_integ_code")
        startup_rises = to_int(row, "startup_rise_count")
        startup_freq = to_float(row, "startup_freq_mhz")
        elapsed_s = to_float(row, "elapsed_s")
        baseline_elapsed_s = to_float(baseline_row, "elapsed_s")

        if spec["expected"] == "increase":
            if abs(start_code) > 2.0 or response < 8.5 or end_code < 8.5:
                raise ValueError(f"FRAC6 MPI16 low trend lacks visible correction: {row}")
            if start_integ != 0.0 or end_integ < 1.5:
                raise ValueError(f"FRAC6 MPI16 low trend lacks integrator accumulation: {row}")
        else:
            if abs(start_code - 255.0) > 2.0 or response > 247.0 or end_code > 247.0:
                raise ValueError(f"FRAC6 MPI16 high trend lacks visible correction: {row}")
            if start_integ != 255.0 or end_integ > 254.0:
                raise ValueError(f"FRAC6 MPI16 high trend lacks integrator accumulation: {row}")

        freq_low, freq_high = spec["startup_freq_range"]
        if startup_rises < 10 or not (freq_low <= startup_freq <= freq_high):
            raise ValueError(f"FRAC6 MPI16 trend row has unexpected oscillator startup: {row}")

        stability = waveform_code_stability(
            row["waveform"],
            79.0,
            259.0,
            spec["stable_band"][0],
            spec["stable_band"][1],
        )
        if stability is None or stability["dwell_ns"] < spec["min_dwell_ns"]:
            raise ValueError(f"FRAC6 MPI16 trend waveform lacks sustained code dwell: {row}")

        log_path = Path(row.get("log", "")).expanduser()
        if not log_path.is_file():
            raise ValueError(f"FRAC6 MPI16 trend row missing Xyce log: {log_path}")
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        if "Timing summary of 16 processors" not in log_text:
            raise ValueError("FRAC6 MPI16 trend log does not record 16-processor timing")

        for key in ("end_code", "response_code", "start_integ_code", "end_integ_code"):
            if abs(to_float(row, key) - to_float(baseline_row, key)) > 1e-6:
                raise ValueError(f"FRAC6 MPI16 trend {key} differs from MPI4 baseline: {row}")
        if elapsed_s >= baseline_elapsed_s:
            raise ValueError(f"FRAC6 MPI16 trend did not improve elapsed time: {row}")

        cases[spec["name"]] = {
            "start_code": start_code,
            "end_code": end_code,
            "response_code": response,
            "start_integ_code": start_integ,
            "end_integ_code": end_integ,
            "stable_code_dwell_ns": stability["dwell_ns"],
            "startup_rise_count": startup_rises,
            "startup_freq_mhz": startup_freq,
            "elapsed_s": elapsed_s,
            "baseline_mpi4_elapsed_s": baseline_elapsed_s,
        }
        elapsed_speedups[spec["name"]] = baseline_elapsed_s / elapsed_s

    return {
        "rows": len(specs),
        "digital_scope": "full",
        "bbpd_impl": "postlayout",
        "dco_model": "postlayout_rcx",
        "xyce_mpi_procs": 16,
        "ki": 255,
        "kp": 32,
        "dlf_frac_width": 6,
        "cases": cases,
        "elapsed_speedup_vs_mpi4": elapsed_speedups,
    }


def check_frac6_extracted_dco_progress_500ns_mpi16_klu(root):
    relpath = (
        "build/spice_pll_mapped_loop_frac6_extracted_dco_progress_500ns_mpi16_klu/"
        "mapped_loop_check.csv"
    )
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 2:
        raise ValueError("FRAC6 MPI16 extracted-DCO 500 ns progress check expected 2 rows")
    require_all_pass(rows)
    by_case = {row["case"]: row for row in rows}
    if set(by_case) != {"low_start", "high_start"}:
        raise ValueError(f"FRAC6 500 ns progress rows have unexpected cases: {sorted(by_case)}")

    specs = {
        "low_start": {
            "expected": "increase",
            "phase": 0.0,
            "start_code": 0.0,
            "end_code_range": (14.5, 15.5),
            "response_range": (14.5, 15.5),
            "start_integ": 0.0,
            "end_integ_range": (7.5, 8.0),
            "observed_min_range": (-0.1, 0.1),
            "observed_max_range": (14.5, 15.5),
            "startup_freq_range": (45.0, 47.0),
            "tail_freq_range": (45.0, 47.0),
            "tail_rises_min": 17,
            "stable_band": (7.5, 15.5),
            "final_band": (14.5, 15.5),
        },
        "high_start": {
            "expected": "decrease",
            "phase": 0.25,
            "start_code": 255.0,
            "end_code_range": (239.5, 240.5),
            "response_range": (239.5, 240.5),
            "start_integ": 255.0,
            "end_integ_range": (247.5, 248.5),
            "observed_min_range": (239.5, 240.5),
            "observed_max_range": (254.5, 255.5),
            "startup_freq_range": (51.5, 53.5),
            "tail_freq_range": (52.0, 54.0),
            "tail_rises_min": 20,
            "stable_band": (239.5, 247.5),
            "final_band": (239.5, 240.5),
        },
    }

    cases = {}
    for case, spec in specs.items():
        row = by_case[case]
        if row.get("simulator") != "xyce" or to_int(row, "xyce_mpi_procs") != 16:
            raise ValueError(f"FRAC6 500 ns progress row has wrong simulator/MPI setting: {row}")
        if "-linsolv KLU" not in row.get("xyce_command", ""):
            raise ValueError(f"FRAC6 500 ns progress row does not record KLU: {row}")
        if row.get("bbpd_impl") != "postlayout" or row.get("digital_scope") != "full":
            raise ValueError(f"FRAC6 500 ns progress row has wrong implementation scope: {row}")
        if row.get("dco_model") != "postlayout_rcx" or row.get("check_mode") != "motion":
            raise ValueError(f"FRAC6 500 ns progress row has wrong DCO/check mode: {row}")
        if row.get("expected") != spec["expected"]:
            raise ValueError(f"FRAC6 500 ns progress row has wrong expected direction: {row}")
        if to_int(row, "mapped_instance_count") < 880:
            raise ValueError(f"FRAC6 500 ns progress row has too few mapped instances: {row}")
        if to_int(row, "skipped_physical_only_cells") != 0:
            raise ValueError(f"FRAC6 500 ns progress row skipped unexpected cells: {row}")
        if (
            to_int(row, "ki") != 255
            or to_int(row, "kp") != 32
            or to_int(row, "dlf_frac_width") != 6
            or to_int(row, "ndiv") != 2
        ):
            raise ValueError(f"FRAC6 500 ns progress row has wrong loop setting: {row}")
        if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
            raise ValueError(f"FRAC6 500 ns progress row did not finish cleanly: {row}")
        if abs(to_float(row, "start_meas_ns") - 79.0) > 1e-9:
            raise ValueError(f"FRAC6 500 ns progress row has wrong start window: {row}")
        if abs(to_float(row, "end_meas_ns") - 499.0) > 1e-9:
            raise ValueError(f"FRAC6 500 ns progress row has wrong end window: {row}")
        if abs(to_float(row, "initial_dco_phase_cycles") - spec["phase"]) > 1e-9:
            raise ValueError(f"FRAC6 500 ns progress row has wrong initial phase: {row}")
        if abs(to_float(row, "enable_ns") - 80.0) > 1e-9:
            raise ValueError(f"FRAC6 500 ns progress row has wrong enable timing: {row}")
        if abs(to_float(row, "clear_width_ns") - 60.0) > 1e-9:
            raise ValueError(f"FRAC6 500 ns progress row has wrong clear timing: {row}")

        start_code = to_float(row, "start_code")
        end_code = to_float(row, "end_code")
        response = to_float(row, "response_code")
        observed_min_code = to_float(row, "observed_min_code")
        observed_max_code = to_float(row, "observed_max_code")
        start_integ = to_float(row, "start_integ_code")
        end_integ = to_float(row, "end_integ_code")
        startup_rises = to_int(row, "startup_rise_count")
        startup_freq = to_float(row, "startup_freq_mhz")
        tail_rises = to_int(row, "tail_rise_count")
        tail_freq = to_float(row, "tail_freq_mhz")
        tail_abs_error = to_float(row, "tail_abs_error_mhz")
        elapsed_s = to_float(row, "elapsed_s")

        if abs(start_code - spec["start_code"]) > 1.0:
            raise ValueError(f"FRAC6 500 ns progress row has wrong start code: {row}")
        end_low, end_high = spec["end_code_range"]
        if not (end_low <= end_code <= end_high):
            raise ValueError(f"FRAC6 500 ns progress row has unexpected end code: {row}")
        response_low, response_high = spec["response_range"]
        if not (response_low <= response <= response_high):
            raise ValueError(f"FRAC6 500 ns progress row has unexpected response code: {row}")
        if start_integ != spec["start_integ"]:
            raise ValueError(f"FRAC6 500 ns progress row has wrong integrator start: {row}")
        integ_low, integ_high = spec["end_integ_range"]
        if not (integ_low <= end_integ <= integ_high):
            raise ValueError(f"FRAC6 500 ns progress row has wrong integrator endpoint: {row}")
        obs_min_low, obs_min_high = spec["observed_min_range"]
        obs_max_low, obs_max_high = spec["observed_max_range"]
        if not (obs_min_low <= observed_min_code <= obs_min_high):
            raise ValueError(f"FRAC6 500 ns progress row has wrong observed minimum: {row}")
        if not (obs_max_low <= observed_max_code <= obs_max_high):
            raise ValueError(f"FRAC6 500 ns progress row has wrong observed maximum: {row}")
        startup_low, startup_high = spec["startup_freq_range"]
        if startup_rises < 20 or not (startup_low <= startup_freq <= startup_high):
            raise ValueError(f"FRAC6 500 ns progress row has unexpected startup frequency: {row}")
        tail_low, tail_high = spec["tail_freq_range"]
        if tail_rises < spec["tail_rises_min"] or not (tail_low <= tail_freq <= tail_high):
            raise ValueError(f"FRAC6 500 ns progress row has unexpected tail frequency: {row}")
        if tail_abs_error < 3.0:
            raise ValueError(f"FRAC6 500 ns progress row unexpectedly looks like a lock row: {row}")
        if elapsed_s <= 0.0 or elapsed_s > 2500.0:
            raise ValueError(f"FRAC6 500 ns progress row has unexpected elapsed time: {row}")

        stable = waveform_code_stability(
            row["waveform"],
            299.0,
            499.0,
            spec["stable_band"][0],
            spec["stable_band"][1],
        )
        if stable is None or stable["dwell_ns"] < 190.0:
            raise ValueError(f"FRAC6 500 ns progress waveform lacks sustained progress dwell: {row}")
        final = waveform_code_stability(
            row["waveform"],
            299.0,
            499.0,
            spec["final_band"][0],
            spec["final_band"][1],
        )
        if final is None or final["dwell_ns"] < 15.0:
            raise ValueError(f"FRAC6 500 ns progress waveform lacks final-code dwell: {row}")

        log_path = Path(row.get("log", "")).expanduser()
        if not log_path.is_file():
            raise ValueError(f"FRAC6 500 ns progress row missing Xyce log: {log_path}")
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        if "Timing summary of 16 processors" not in log_text:
            raise ValueError("FRAC6 500 ns progress log does not record 16-processor timing")

        cases[case] = {
            "start_code": start_code,
            "end_code": end_code,
            "response_code": response,
            "start_integ_code": start_integ,
            "end_integ_code": end_integ,
            "startup_rise_count": startup_rises,
            "startup_freq_mhz": startup_freq,
            "tail_rise_count": tail_rises,
            "tail_freq_mhz": tail_freq,
            "tail_abs_error_mhz": tail_abs_error,
            "progress_dwell_ns": stable["dwell_ns"],
            "final_code_dwell_ns": final["dwell_ns"],
            "elapsed_s": elapsed_s,
        }

    return {
        "rows": len(rows),
        "digital_scope": "full",
        "bbpd_impl": "postlayout",
        "dco_model": "postlayout_rcx",
        "xyce_mpi_procs": 16,
        "ki": 255,
        "kp": 32,
        "dlf_frac_width": 6,
        "sim_time_ns": 500,
        "cases": cases,
        "max_tail_abs_error_mhz": max(details["tail_abs_error_mhz"] for details in cases.values()),
    }


def check_frac6_extracted_dco_midcode_lock_mpi16_klu(root):
    relpath = (
        "build/spice_pll_mapped_loop_frac6_extracted_dco_midcode_lock_220ns_mpi16_klu/"
        "mapped_loop_check.csv"
    )
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 1:
        raise ValueError("FRAC6 MPI16 extracted-DCO mid-code lock check expected 1 row")
    require_all_pass(rows)
    row = rows[0]

    if row.get("case") != "mid_start_inc":
        raise ValueError(f"FRAC6 mid-code lock row has wrong case: {row}")
    if row.get("simulator") != "xyce" or to_int(row, "xyce_mpi_procs") != 16:
        raise ValueError(f"FRAC6 mid-code lock row has wrong simulator/MPI setting: {row}")
    if "-linsolv KLU" not in row.get("xyce_command", ""):
        raise ValueError(f"FRAC6 mid-code lock row does not record KLU: {row}")
    if row.get("bbpd_impl") != "postlayout" or row.get("digital_scope") != "full":
        raise ValueError(f"FRAC6 mid-code lock row has wrong implementation scope: {row}")
    if row.get("dco_model") != "postlayout_rcx" or row.get("check_mode") != "lock_window":
        raise ValueError(f"FRAC6 mid-code lock row has wrong DCO/check mode: {row}")
    if to_int(row, "mapped_instance_count") < 880:
        raise ValueError(f"FRAC6 mid-code lock row has too few mapped instances: {row}")
    if to_int(row, "skipped_physical_only_cells") != 0:
        raise ValueError(f"FRAC6 mid-code lock row skipped unexpected cells: {row}")
    if (
        to_int(row, "ki") != 255
        or to_int(row, "kp") != 32
        or to_int(row, "dlf_frac_width") != 6
        or to_int(row, "ndiv") != 2
    ):
        raise ValueError(f"FRAC6 mid-code lock row has wrong loop setting: {row}")
    if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
        raise ValueError(f"FRAC6 mid-code lock row did not finish cleanly: {row}")

    start_code = to_float(row, "start_code")
    end_code = to_float(row, "end_code")
    observed_min_code = to_float(row, "observed_min_code")
    observed_max_code = to_float(row, "observed_max_code")
    start_integ = to_float(row, "start_integ_code")
    end_integ = to_float(row, "end_integ_code")
    target_freq = to_float(row, "target_freq_mhz")
    tail_rises = to_int(row, "tail_rise_count")
    tail_freq = to_float(row, "tail_freq_mhz")
    tail_abs_error = to_float(row, "tail_abs_error_mhz")

    if abs(start_code - 128.0) > 1.0:
        raise ValueError(f"FRAC6 mid-code lock row has wrong start code: {row}")
    if not (136.0 <= end_code <= 138.0):
        raise ValueError(f"FRAC6 mid-code lock row has unexpected endpoint code: {row}")
    if observed_min_code < 127.0 or observed_max_code > 140.0:
        raise ValueError(f"FRAC6 mid-code lock row exceeded configured code band: {row}")
    if start_integ != 128.0 or not (129.5 <= end_integ <= 130.0):
        raise ValueError(f"FRAC6 mid-code lock row has unexpected integrator movement: {row}")
    if tail_rises < 4 or tail_abs_error > 0.1:
        raise ValueError(f"FRAC6 mid-code lock row lacks near-target tail frequency: {row}")
    if abs(target_freq - 49.762117807733404) > 1.0e-6:
        raise ValueError(f"FRAC6 mid-code lock row has unexpected target frequency: {row}")
    if not (49.6 <= tail_freq <= 49.9):
        raise ValueError(f"FRAC6 mid-code lock row has unexpected tail frequency: {row}")

    stability = waveform_code_stability(row["waveform"], 139.0, 219.0, 135.5, 137.5)
    if stability is None or stability["dwell_ns"] < 70.0:
        raise ValueError("FRAC6 mid-code lock waveform lacks sustained tail code dwell")

    log_path = Path(row.get("log", "")).expanduser()
    if not log_path.is_file():
        raise ValueError(f"FRAC6 mid-code lock row missing Xyce log: {log_path}")
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    if "Timing summary of 16 processors" not in log_text:
        raise ValueError("FRAC6 mid-code lock log does not record 16-processor timing")

    return {
        "rows": len(rows),
        "digital_scope": "full",
        "bbpd_impl": "postlayout",
        "dco_model": "postlayout_rcx",
        "xyce_mpi_procs": 16,
        "ki": 255,
        "kp": 32,
        "dlf_frac_width": 6,
        "start_code": start_code,
        "end_code": end_code,
        "observed_min_code": observed_min_code,
        "observed_max_code": observed_max_code,
        "start_integ_code": start_integ,
        "end_integ_code": end_integ,
        "target_freq_mhz": target_freq,
        "tail_freq_mhz": tail_freq,
        "tail_abs_error_mhz": tail_abs_error,
        "tail_rise_count": tail_rises,
        "stable_code_dwell_ns": stability["dwell_ns"],
    }


def check_frac6_extracted_dco_near_high_lock_en85_mpi16_klu(root):
    relpath = (
        "build/spice_pll_mapped_loop_frac6_extracted_dco_near_high_lock_en85_380ns_mpi16_klu/"
        "mapped_loop_check.csv"
    )
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 1:
        raise ValueError("FRAC6 MPI16 extracted-DCO enable-85 high-side lock check expected 1 row")
    require_all_pass(rows)
    row = rows[0]

    if row.get("case") != "near_high_dec":
        raise ValueError(f"FRAC6 enable-85 high-side lock row has wrong case: {row}")
    if row.get("simulator") != "xyce" or to_int(row, "xyce_mpi_procs") != 16:
        raise ValueError(f"FRAC6 enable-85 high-side lock row has wrong simulator/MPI setting: {row}")
    if "-linsolv KLU" not in row.get("xyce_command", ""):
        raise ValueError(f"FRAC6 enable-85 high-side lock row does not record KLU: {row}")
    if row.get("bbpd_impl") != "postlayout" or row.get("digital_scope") != "full":
        raise ValueError(f"FRAC6 enable-85 high-side lock row has wrong implementation scope: {row}")
    if row.get("dco_model") != "postlayout_rcx" or row.get("check_mode") != "lock_window":
        raise ValueError(f"FRAC6 enable-85 high-side lock row has wrong DCO/check mode: {row}")
    if row.get("expected") != "decrease" or row.get("lock_require_motion") != "yes":
        raise ValueError(f"FRAC6 enable-85 high-side lock row has wrong direction requirement: {row}")
    if to_int(row, "mapped_instance_count") < 880:
        raise ValueError(f"FRAC6 enable-85 high-side lock row has too few mapped instances: {row}")
    if to_int(row, "skipped_physical_only_cells") != 0:
        raise ValueError(f"FRAC6 enable-85 high-side lock row skipped unexpected cells: {row}")
    if (
        to_int(row, "ki") != 255
        or to_int(row, "kp") != 32
        or to_int(row, "dlf_frac_width") != 6
        or to_int(row, "ndiv") != 2
    ):
        raise ValueError(f"FRAC6 enable-85 high-side lock row has wrong loop setting: {row}")
    if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
        raise ValueError(f"FRAC6 enable-85 high-side lock row did not finish cleanly: {row}")
    if abs(to_float(row, "start_meas_ns") - 84.0) > 1e-9:
        raise ValueError(f"FRAC6 enable-85 high-side lock row has wrong start window: {row}")
    if abs(to_float(row, "end_meas_ns") - 379.0) > 1e-9:
        raise ValueError(f"FRAC6 enable-85 high-side lock row has wrong end window: {row}")
    if abs(to_float(row, "lock_meas_start_ns") - 299.0) > 1e-9:
        raise ValueError(f"FRAC6 enable-85 high-side lock row has wrong lock window start: {row}")
    if abs(to_float(row, "enable_ns") - 85.0) > 1e-9:
        raise ValueError(f"FRAC6 enable-85 high-side lock row has wrong enable timing: {row}")
    if abs(to_float(row, "clear_width_ns") - 60.0) > 1e-9:
        raise ValueError(f"FRAC6 enable-85 high-side lock row has wrong clear timing: {row}")

    start_code = to_float(row, "start_code")
    end_code = to_float(row, "end_code")
    observed_min_code = to_float(row, "observed_min_code")
    observed_max_code = to_float(row, "observed_max_code")
    response = to_float(row, "response_code")
    start_integ = to_float(row, "start_integ_code")
    end_integ = to_float(row, "end_integ_code")
    target_freq = to_float(row, "target_freq_mhz")
    tail_rises = to_int(row, "tail_rise_count")
    tail_freq = to_float(row, "tail_freq_mhz")
    tail_abs_error = to_float(row, "tail_abs_error_mhz")

    if abs(start_code - 160.0) > 1.0:
        raise ValueError(f"FRAC6 enable-85 high-side lock row has wrong start code: {row}")
    if not (145.0 <= end_code <= 147.0):
        raise ValueError(f"FRAC6 enable-85 high-side lock row has unexpected endpoint code: {row}")
    if not (128.0 <= observed_min_code <= 131.0) or observed_max_code > 161.0:
        raise ValueError(f"FRAC6 enable-85 high-side lock row exceeded configured code band: {row}")
    if response >= start_code or response > 131.0:
        raise ValueError(f"FRAC6 enable-85 high-side lock row lacks downward response: {row}")
    if start_integ != 160.0 or not (153.5 <= end_integ <= 154.5):
        raise ValueError(f"FRAC6 enable-85 high-side lock row has unexpected integrator movement: {row}")
    if tail_rises < 4 or tail_abs_error > 0.25:
        raise ValueError(f"FRAC6 enable-85 high-side lock row lacks near-target tail frequency: {row}")
    if abs(target_freq - 49.762117807733404) > 1.0e-6:
        raise ValueError(f"FRAC6 enable-85 high-side lock row has unexpected target frequency: {row}")
    if not (49.9 <= tail_freq <= 50.1):
        raise ValueError(f"FRAC6 enable-85 high-side lock row has unexpected tail frequency: {row}")

    lock_band_stability = waveform_code_stability(row["waveform"], 299.0, 379.0, 128.0, 161.0)
    if lock_band_stability is None or lock_band_stability["dwell_ns"] < 70.0:
        raise ValueError("FRAC6 enable-85 high-side lock waveform lacks configured-band dwell")
    tail_code_stability = waveform_code_stability(row["waveform"], 299.0, 379.0, 145.5, 148.5)
    if tail_code_stability is None or tail_code_stability["dwell_ns"] < 45.0:
        raise ValueError("FRAC6 enable-85 high-side lock waveform lacks final tail-code dwell")

    log_path = Path(row.get("log", "")).expanduser()
    if not log_path.is_file():
        raise ValueError(f"FRAC6 enable-85 high-side lock row missing Xyce log: {log_path}")
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    if "Timing summary of 16 processors" not in log_text:
        raise ValueError("FRAC6 enable-85 high-side lock log does not record 16-processor timing")

    return {
        "rows": len(rows),
        "digital_scope": "full",
        "bbpd_impl": "postlayout",
        "dco_model": "postlayout_rcx",
        "xyce_mpi_procs": 16,
        "ki": 255,
        "kp": 32,
        "dlf_frac_width": 6,
        "enable_ns": to_float(row, "enable_ns"),
        "clear_width_ns": to_float(row, "clear_width_ns"),
        "start_code": start_code,
        "end_code": end_code,
        "response_code": response,
        "observed_min_code": observed_min_code,
        "observed_max_code": observed_max_code,
        "start_integ_code": start_integ,
        "end_integ_code": end_integ,
        "target_freq_mhz": target_freq,
        "tail_freq_mhz": tail_freq,
        "tail_abs_error_mhz": tail_abs_error,
        "tail_rise_count": tail_rises,
        "lock_band_dwell_ns": lock_band_stability["dwell_ns"],
        "tail_code_dwell_ns": tail_code_stability["dwell_ns"],
    }


def check_frac6_force127_final_signoff_extracted_dco_lock_820ns_mpi16_klu(root):
    relpath = (
        "build/spice_pll_final_force127_extracted_dco_lock_820ns_mpi16_klu/"
        "mapped_loop_check.csv"
    )
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 2:
        raise ValueError("force127 final-signoff-netlist lock check expected 2 rows")
    require_all_pass(rows)
    by_case = {row["case"]: row for row in rows}
    if set(by_case) != {"low_start", "high_start"}:
        raise ValueError(
            f"force127 final-signoff lock rows have unexpected cases: {sorted(by_case)}"
        )

    specs = {
        "low_start": {
            "expected": "increase",
            "phase": 0.0,
            "start_code": 0.0,
            "end_range": (127.5, 128.5),
            "lock_range": (122.0, 128.0),
        },
        "high_start": {
            "expected": "decrease",
            "phase": 0.5,
            "start_code": 255.0,
            "end_range": (131.5, 132.5),
            "lock_range": (126.0, 132.0),
        },
    }

    cases = {}
    for case, spec in specs.items():
        row = by_case[case]
        if row.get("simulator") != "xyce" or to_int(row, "xyce_mpi_procs") != 16:
            raise ValueError(
                f"force127 final-signoff lock row has wrong simulator/MPI setting: {row}"
            )
        if "-linsolv KLU" not in row.get("xyce_command", ""):
            raise ValueError(f"force127 final-signoff lock row does not record KLU: {row}")
        if row.get("bbpd_impl") != "postlayout":
            raise ValueError(f"force127 final-signoff lock row has wrong BBPD impl: {row}")
        if row.get("digital_scope") != "final_signoff_force127_functional":
            raise ValueError(f"force127 final-signoff lock row has wrong digital scope: {row}")
        if row.get("dco_model") != "postlayout_rcx" or row.get("check_mode") != "lock_window":
            raise ValueError(f"force127 final-signoff lock row has wrong DCO/check mode: {row}")
        if row.get("expected") != spec["expected"]:
            raise ValueError(f"force127 final-signoff lock row has wrong direction: {row}")
        if to_int(row, "mapped_instance_count") != 2020:
            raise ValueError(f"force127 final-signoff lock row has wrong functional cell count: {row}")
        if to_int(row, "skipped_physical_only_cells") != 4138:
            raise ValueError(f"force127 final-signoff lock row skipped wrong physical-only count: {row}")
        if (
            to_int(row, "ki") != 160
            or to_int(row, "kp") != 8
            or to_int(row, "dlf_frac_width") != 6
            or to_int(row, "ndiv") != 2
        ):
            raise ValueError(f"force127 final-signoff lock row has wrong loop setting: {row}")
        if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
            raise ValueError(f"force127 final-signoff lock row did not finish cleanly: {row}")
        if abs(to_float(row, "initial_dco_phase_cycles") - spec["phase"]) > 1e-9:
            raise ValueError(f"force127 final-signoff lock row has wrong initial phase: {row}")
        if abs(to_float(row, "enable_ns") - 85.0) > 1e-9:
            raise ValueError(f"force127 final-signoff lock row has wrong enable timing: {row}")
        if abs(to_float(row, "clear_width_ns") - 60.0) > 1e-9:
            raise ValueError(f"force127 final-signoff lock row has wrong clear timing: {row}")
        if abs(to_float(row, "start_meas_ns") - 84.0) > 1e-9:
            raise ValueError(f"force127 final-signoff lock row has wrong start window: {row}")
        if abs(to_float(row, "end_meas_ns") - 819.0) > 1e-9:
            raise ValueError(f"force127 final-signoff lock row has wrong end window: {row}")
        if abs(to_float(row, "lock_meas_start_ns") - 700.0) > 1e-9:
            raise ValueError(f"force127 final-signoff lock row has wrong lock start: {row}")
        if row.get("lock_code_check") != "window":
            raise ValueError(f"force127 final-signoff lock row has wrong code-check mode: {row}")
        if to_float(row, "lock_min_code") != 112.0 or to_float(row, "lock_max_code") != 144.0:
            raise ValueError(f"force127 final-signoff lock row has wrong lock bounds: {row}")
        if to_float(row, "lock_max_abs_ferr_mhz") != 0.8:
            raise ValueError(f"force127 final-signoff lock row has wrong frequency bound: {row}")

        start_code = to_float(row, "start_code")
        end_code = to_float(row, "end_code")
        observed_min_code = to_float(row, "observed_min_code")
        observed_max_code = to_float(row, "observed_max_code")
        lock_observed_min_code = to_float(row, "lock_observed_min_code")
        lock_observed_max_code = to_float(row, "lock_observed_max_code")
        target_freq = to_float(row, "target_freq_mhz")
        tail_rises = to_int(row, "tail_rise_count")
        tail_freq = to_float(row, "tail_freq_mhz")
        tail_abs_error = to_float(row, "tail_abs_error_mhz")
        if row.get("elapsed_s", ""):
            elapsed_s = to_float(row, "elapsed_s")
        elif row.get("resumed") == "yes":
            elapsed_s = None
        else:
            raise ValueError(f"force127 final-signoff lock row lacks elapsed time: {row}")

        if abs(start_code - spec["start_code"]) > 1.0:
            raise ValueError(f"force127 final-signoff lock row has wrong start code: {row}")
        end_low, end_high = spec["end_range"]
        if not (end_low <= end_code <= end_high):
            raise ValueError(f"force127 final-signoff lock row has wrong endpoint: {row}")
        if not (112.0 <= lock_observed_min_code <= lock_observed_max_code <= 144.0):
            raise ValueError(f"force127 final-signoff lock row exceeded lock window: {row}")
        expected_lock_low, expected_lock_high = spec["lock_range"]
        if (
            abs(lock_observed_min_code - expected_lock_low) > 0.5
            or abs(lock_observed_max_code - expected_lock_high) > 0.5
        ):
            raise ValueError(f"force127 final-signoff lock row changed expected lock range: {row}")
        if case == "low_start" and (observed_min_code > 1.0 or observed_max_code < 127.5):
            raise ValueError(f"force127 final-signoff low-start lacks rail-to-mid motion: {row}")
        if case == "high_start" and (observed_max_code < 254.0 or observed_min_code > 126.5):
            raise ValueError(f"force127 final-signoff high-start lacks rail-to-mid motion: {row}")
        if abs(target_freq - 49.762117807733404) > 1.0e-6:
            raise ValueError(f"force127 final-signoff lock row has unexpected target frequency: {row}")
        if tail_rises < 5 or tail_abs_error > 0.8:
            raise ValueError(f"force127 final-signoff lock row lacks bounded tail frequency: {row}")
        if not (49.3 <= tail_freq <= 49.6):
            raise ValueError(f"force127 final-signoff lock row has unexpected tail frequency: {row}")
        stability = waveform_code_stability(row["waveform"], 700.0, 819.0, 112.0, 144.0)
        if stability is None or stability["dwell_ns"] < 110.0:
            raise ValueError(
                f"force127 final-signoff lock waveform lacks sustained tail-window dwell: {row}"
            )

        log_path = Path(row.get("log", "")).expanduser()
        if not log_path.is_file():
            raise ValueError(f"force127 final-signoff lock row missing Xyce log: {log_path}")
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        if "Timing summary of 16 processors" not in log_text:
            raise ValueError("force127 final-signoff lock log does not record 16-processor timing")
        if elapsed_s is None:
            elapsed_s = xyce_elapsed_run_time_s(log_text)
        if elapsed_s is None or elapsed_s <= 0.0 or elapsed_s > 9000.0:
            raise ValueError(f"force127 final-signoff lock row has unexpected elapsed time: {row}")

        cases[case] = {
            "start_code": start_code,
            "end_code": end_code,
            "observed_min_code": observed_min_code,
            "observed_max_code": observed_max_code,
            "lock_observed_min_code": lock_observed_min_code,
            "lock_observed_max_code": lock_observed_max_code,
            "target_freq_mhz": target_freq,
            "tail_freq_mhz": tail_freq,
            "tail_abs_error_mhz": tail_abs_error,
            "tail_rise_count": tail_rises,
            "tail_code_dwell_ns": stability["dwell_ns"],
            "elapsed_s": elapsed_s,
        }

    return {
        "rows": len(rows),
        "digital_scope": "final_signoff_force127_functional",
        "mapped_instance_count": 2020,
        "skipped_physical_only_cells": 4138,
        "bbpd_impl": "postlayout",
        "dco_model": "postlayout_rcx",
        "xyce_mpi_procs": 16,
        "ki": 160,
        "kp": 8,
        "dlf_frac_width": 6,
        "sim_time_ns": 820,
        "cases": cases,
        "max_tail_abs_error_mhz": max(details["tail_abs_error_mhz"] for details in cases.values()),
    }


def check_extracted_dco_midcode_inc_mpi_klu(root):
    relpath = (
        "build/spice_pll_mapped_loop_extracted_dco_midcode_inc_180ns_mpi4_klu/"
        "mapped_loop_check.csv"
    )
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 1:
        raise ValueError("extracted DCO mid-code increase expected 1 row")
    require_all_pass(rows)
    row = rows[0]

    if row.get("case") != "mid_start_inc":
        raise ValueError(f"extracted DCO mid-code row has wrong case: {row}")
    if row.get("simulator") != "xyce" or to_int(row, "xyce_mpi_procs") != 4:
        raise ValueError(f"extracted DCO mid-code row is not MPI4 Xyce: {row}")
    if "-linsolv KLU" not in row.get("xyce_command", ""):
        raise ValueError(f"extracted DCO mid-code row does not record KLU: {row}")
    if row.get("bbpd_impl") != "postlayout" or row.get("digital_scope") != "full":
        raise ValueError(f"extracted DCO mid-code row has wrong implementation scope: {row}")
    if row.get("dco_model") != "postlayout_rcx" or row.get("check_mode") != "motion":
        raise ValueError(f"extracted DCO mid-code row has wrong DCO/check mode: {row}")
    if row.get("expected") != "increase":
        raise ValueError(f"extracted DCO mid-code row has wrong expected direction: {row}")
    if to_int(row, "mapped_instance_count") < 900:
        raise ValueError(f"extracted DCO mid-code row has too few mapped instances: {row}")
    if to_int(row, "skipped_physical_only_cells") != 0:
        raise ValueError(f"extracted DCO mid-code row skipped unexpected cells: {row}")
    if to_int(row, "ki") != 255 or to_int(row, "kp") != 32 or to_int(row, "ndiv") != 2:
        raise ValueError(f"extracted DCO mid-code row has wrong loop setting: {row}")
    if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
        raise ValueError(f"extracted DCO mid-code row did not finish cleanly: {row}")
    if abs(to_float(row, "start_meas_ns") - 79.0) > 1e-9:
        raise ValueError(f"extracted DCO mid-code row has wrong start window: {row}")
    if abs(to_float(row, "end_meas_ns") - 179.0) > 1e-9:
        raise ValueError(f"extracted DCO mid-code row has wrong end window: {row}")

    start_code = to_float(row, "start_code")
    end_code = to_float(row, "end_code")
    response = to_float(row, "response_code")
    min_code = to_float(row, "observed_min_code")
    max_code = to_float(row, "observed_max_code")
    start_integ = to_float(row, "start_integ_code")
    end_integ = to_float(row, "end_integ_code")
    min_integ = to_float(row, "observed_min_integ_code")
    max_integ = to_float(row, "observed_max_integ_code")
    startup_rises = to_int(row, "startup_rise_count")
    startup_freq = to_float(row, "startup_freq_mhz")

    if abs(start_code - 128.0) > 0.5 or min_code < 127.5:
        raise ValueError(f"extracted DCO mid-code row has wrong start code: {row}")
    if response < 135.5 or end_code < 135.5 or max_code < 135.5:
        raise ValueError(f"extracted DCO mid-code row lacks visible upward response: {row}")
    if any(abs(value - 128.0) > 1e-9 for value in (start_integ, end_integ, min_integ, max_integ)):
        raise ValueError(f"extracted DCO mid-code row changed integrator unexpectedly: {row}")
    if startup_rises < 8 or not (48.0 <= startup_freq <= 50.0):
        raise ValueError(f"extracted DCO mid-code row has unexpected oscillator startup: {row}")

    stability = waveform_code_stability(row["waveform"], 79.0, 179.0, 135.5, 136.5)
    if stability is None or stability["dwell_ns"] < 40.0:
        raise ValueError("extracted DCO mid-code waveform lacks sustained code-136 dwell")

    log_path = Path(row.get("log", "")).expanduser()
    if not log_path.is_file():
        raise ValueError(f"extracted DCO mid-code row missing Xyce log: {log_path}")
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    if "Timing summary of 4 processors" not in log_text:
        raise ValueError("extracted DCO mid-code log does not record 4-processor timing")

    return {
        "rows": len(rows),
        "digital_scope": "full",
        "bbpd_impl": "postlayout",
        "dco_model": "postlayout_rcx",
        "xyce_mpi_procs": 4,
        "start_code": start_code,
        "end_code": end_code,
        "response_code": response,
        "start_integ_code": start_integ,
        "end_integ_code": end_integ,
        "stable_code_dwell_ns": stability["dwell_ns"],
        "startup_rise_count": startup_rises,
        "startup_freq_mhz": startup_freq,
    }


def check_extracted_dco_midcode_kp0_hold_mpi_klu(root):
    relpath = (
        "build/spice_pll_mapped_loop_extracted_dco_midcode_inc_kp0_hold_180ns_mpi4_klu/"
        "mapped_loop_check.csv"
    )
    rows = read_csv(require_path(root, relpath))
    if len(rows) != 1:
        raise ValueError("extracted DCO mid-code KP0 hold expected 1 row")
    require_all_pass(rows)
    row = rows[0]

    if row.get("case") != "mid_start_inc":
        raise ValueError(f"extracted DCO KP0 hold row has wrong case: {row}")
    if row.get("simulator") != "xyce" or to_int(row, "xyce_mpi_procs") != 4:
        raise ValueError(f"extracted DCO KP0 hold row is not MPI4 Xyce: {row}")
    if "-linsolv KLU" not in row.get("xyce_command", ""):
        raise ValueError(f"extracted DCO KP0 hold row does not record KLU: {row}")
    if row.get("bbpd_impl") != "postlayout" or row.get("digital_scope") != "full":
        raise ValueError(f"extracted DCO KP0 hold row has wrong implementation scope: {row}")
    if row.get("dco_model") != "postlayout_rcx" or row.get("check_mode") != "no_motion":
        raise ValueError(f"extracted DCO KP0 hold row has wrong DCO/check mode: {row}")
    if row.get("expected") != "increase":
        raise ValueError(f"extracted DCO KP0 hold row has wrong expected direction: {row}")
    if to_int(row, "mapped_instance_count") < 900:
        raise ValueError(f"extracted DCO KP0 hold row has too few mapped instances: {row}")
    if to_int(row, "skipped_physical_only_cells") != 0:
        raise ValueError(f"extracted DCO KP0 hold row skipped unexpected cells: {row}")
    if to_int(row, "ki") != 255 or to_int(row, "kp") != 0 or to_int(row, "ndiv") != 2:
        raise ValueError(f"extracted DCO KP0 hold row has wrong loop setting: {row}")
    if row.get("timed_out") != "no" or to_int(row, "returncode") != 0:
        raise ValueError(f"extracted DCO KP0 hold row did not finish cleanly: {row}")
    if abs(to_float(row, "start_meas_ns") - 79.0) > 1e-9:
        raise ValueError(f"extracted DCO KP0 hold row has wrong start window: {row}")
    if abs(to_float(row, "end_meas_ns") - 179.0) > 1e-9:
        raise ValueError(f"extracted DCO KP0 hold row has wrong end window: {row}")

    start_code = to_float(row, "start_code")
    end_code = to_float(row, "end_code")
    response = to_float(row, "response_code")
    min_code = to_float(row, "observed_min_code")
    max_code = to_float(row, "observed_max_code")
    start_integ = to_float(row, "start_integ_code")
    end_integ = to_float(row, "end_integ_code")
    min_integ = to_float(row, "observed_min_integ_code")
    max_integ = to_float(row, "observed_max_integ_code")
    startup_rises = to_int(row, "startup_rise_count")
    startup_freq = to_float(row, "startup_freq_mhz")

    for label, value in (
        ("start_code", start_code),
        ("end_code", end_code),
        ("response_code", response),
        ("observed_min_code", min_code),
        ("observed_max_code", max_code),
        ("start_integ_code", start_integ),
        ("end_integ_code", end_integ),
        ("observed_min_integ_code", min_integ),
        ("observed_max_integ_code", max_integ),
    ):
        if abs(value - 128.0) > 1e-9:
            raise ValueError(f"extracted DCO KP0 hold row has unexpected {label}: {row}")
    if startup_rises < 8 or not (48.0 <= startup_freq <= 50.0):
        raise ValueError(f"extracted DCO KP0 hold row has unexpected oscillator startup: {row}")

    stability = waveform_code_stability(row["waveform"], 79.0, 179.0, 127.5, 128.5)
    if stability is None or stability["dwell_ns"] < 95.0:
        raise ValueError("extracted DCO KP0 hold waveform lacks sustained code-128 dwell")

    log_path = Path(row.get("log", "")).expanduser()
    if not log_path.is_file():
        raise ValueError(f"extracted DCO KP0 hold row missing Xyce log: {log_path}")
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    if "Timing summary of 4 processors" not in log_text:
        raise ValueError("extracted DCO KP0 hold log does not record 4-processor timing")

    return {
        "rows": len(rows),
        "digital_scope": "full",
        "bbpd_impl": "postlayout",
        "dco_model": "postlayout_rcx",
        "xyce_mpi_procs": 4,
        "ki": 255,
        "kp": 0,
        "start_code": start_code,
        "end_code": end_code,
        "response_code": response,
        "start_integ_code": start_integ,
        "end_integ_code": end_integ,
        "stable_code_dwell_ns": stability["dwell_ns"],
        "startup_rise_count": startup_rises,
        "startup_freq_mhz": startup_freq,
    }


def check_extracted_dco_midcode_frequency_contrast_mpi_klu(root):
    kp32_details = check_extracted_dco_midcode_inc_mpi_klu(root)
    kp0_details = check_extracted_dco_midcode_kp0_hold_mpi_klu(root)
    kp32_relpath = (
        "build/spice_pll_mapped_loop_extracted_dco_midcode_inc_180ns_mpi4_klu/"
        "mapped_loop_check.csv"
    )
    kp0_relpath = (
        "build/spice_pll_mapped_loop_extracted_dco_midcode_inc_kp0_hold_180ns_mpi4_klu/"
        "mapped_loop_check.csv"
    )
    kp32_row = read_csv(require_path(root, kp32_relpath))[0]
    kp0_row = read_csv(require_path(root, kp0_relpath))[0]

    tail_start_ns = 119.0
    tail_end_ns = 179.0
    threshold = 0.9
    kp32_freq = waveform_signal_frequency(
        kp32_row["waveform"],
        "v(pllout)",
        tail_start_ns,
        tail_end_ns,
        threshold,
    )
    kp0_freq = waveform_signal_frequency(
        kp0_row["waveform"],
        "v(pllout)",
        tail_start_ns,
        tail_end_ns,
        threshold,
    )
    freq_delta = kp32_freq["frequency_mhz"] - kp0_freq["frequency_mhz"]

    if not (49.60 <= kp32_freq["frequency_mhz"] <= 49.85):
        raise ValueError(f"KP32 extracted-DCO mid-code tail frequency is unexpected: {kp32_freq}")
    if not (49.35 <= kp0_freq["frequency_mhz"] <= 49.60):
        raise ValueError(f"KP0 extracted-DCO mid-code tail frequency is unexpected: {kp0_freq}")
    if not (0.15 <= freq_delta <= 0.35):
        raise ValueError(
            "extracted-DCO mid-code KP32/KP0 tail-frequency contrast is unexpected: "
            f"{freq_delta:g} MHz"
        )

    return {
        "rows": 2,
        "digital_scope": "full",
        "bbpd_impl": "postlayout",
        "dco_model": "postlayout_rcx",
        "xyce_mpi_procs": 4,
        "tail_window_ns": [tail_start_ns, tail_end_ns],
        "threshold_v": threshold,
        "kp32_response_code": kp32_details["response_code"],
        "kp0_response_code": kp0_details["response_code"],
        "kp32_tail_freq_mhz": kp32_freq["frequency_mhz"],
        "kp0_tail_freq_mhz": kp0_freq["frequency_mhz"],
        "tail_freq_delta_mhz": freq_delta,
        "kp32_rising_crossings": kp32_freq["rising_crossings"],
        "kp0_rising_crossings": kp0_freq["rising_crossings"],
    }


def check_finite_numbers(records):
    def walk(value):
        if isinstance(value, float):
            if not math.isfinite(value):
                raise ValueError("summary contains non-finite float")
        elif isinstance(value, dict):
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    walk(records)


def main():
    parser = argparse.ArgumentParser(description="Check promoted Sky130 PLL validation artifacts.")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
        help="OpenPLL repository root.",
    )
    parser.add_argument(
        "--out-dir",
        default="build/sky130_pll_validation",
        help="Directory for validation summary artifacts.",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    out_dir = (root / args.out_dir).resolve() if not Path(args.out_dir).is_absolute() else Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    checks = [
        (
            "signoff_digital_core",
            lambda: check_signoff_block(
                root,
                "IntegerPLL_DigitalCore",
                "openlane/IntegerPLL_DigitalCore/runs/librelane_signoff_force127_s4a2",
                require_spef=False,
                require_rcx=False,
                source_relpaths=(
                    "rtl/IntegerPLL_B2TH.v",
                    "rtl/IntegerPLL_MMD_Retimer.v",
                    "rtl/IntegerPLL_Divider.v",
                    "rtl/IntegerPLL_DLF.v",
                    "rtl/IntegerPLL_DigitalCore.v",
                    "openlane/IntegerPLL_DigitalCore/config_force127_s4a2.json",
                    "openlane/IntegerPLL_DigitalCore/pnr.sdc",
                ),
            ),
        ),
        (
            "signoff_dco_macro",
            lambda: check_signoff_block(
                root,
                "IntegerPLL_DCO",
                "openlane/IntegerPLL_DCO/runs/librelane_signoff",
                require_spef=False,
                source_relpaths=(
                    "sky130/IntegerPLL_DCO_sky130.v",
                    "openlane/IntegerPLL_DCO/config.json",
                    "openlane/IntegerPLL_DCO/no_clock.sdc",
                ),
            ),
        ),
        (
            "signoff_dco_einvp_candidate",
            lambda: check_signoff_block(
                root,
                "IntegerPLL_DCO_EINVP",
                "openlane/IntegerPLL_DCO_EINVP/runs/librelane_signoff",
                require_spef=False,
                source_relpaths=(
                    "sky130/IntegerPLL_DCO_einvp_sky130.v",
                    "openlane/IntegerPLL_DCO_EINVP/config.json",
                    "openlane/IntegerPLL_DCO_EINVP/no_clock.sdc",
                ),
            ),
        ),
        (
            "signoff_bbpd_macro",
            lambda: check_signoff_block(
                root,
                "IntegerPLL_BBPD",
                "openlane/IntegerPLL_BBPD/runs/librelane_signoff",
                require_spef=False,
                source_relpaths=(
                    "sky130/IntegerPLL_BBPD_sky130.v",
                    "openlane/IntegerPLL_BBPD/config.json",
                    "openlane/IntegerPLL_BBPD/async_false_paths.sdc",
                ),
            ),
        ),
        ("sky130_structural_top_smoke", lambda: check_sky130_top_smoke(root)),
        ("top_macro_assembly", lambda: check_top_macro_assembly(root)),
        ("hard_macro_top_route", lambda: check_hard_macro_top(root)),
        ("hard_macro_top_signoff", lambda: check_hard_macro_top_signoff(root)),
        ("hard_macro_top_extracted_spice_interface", lambda: check_hard_macro_top_spice_interface(root)),
        ("hard_macro_top_einvp_signoff", lambda: check_hard_macro_top_einvp_signoff(root)),
        ("hard_macro_top_einvp_extracted_spice_interface", lambda: check_hard_macro_top_einvp_spice_interface(root)),
        ("dco_all_code_spice", lambda: check_dco_summaries(root)),
        ("dco_decoder_all_code_all_taps_spice", lambda: check_decoder(root)),
        ("filled_dco_rcx_five_point", lambda: check_filled_dco(root)),
        ("filled_dco_rcx_tt_9pt", lambda: check_filled_dco_tt_9pt(root)),
        ("filled_dco_rcx_highcode_tail", lambda: check_filled_dco_highcode_tail(root)),
        ("filled_dco_einvp_candidate_rcx", lambda: check_dco_einvp_postlayout_candidate(root)),
        ("filled_dco_einvp_candidate_pvt_endpoints", lambda: check_dco_einvp_postlayout_pvt_endpoints(root)),
        ("filled_dco_rcx_local_gain", lambda: check_filled_dco_local_gain(root)),
        ("filled_dco_rcx_pvt_endpoints", lambda: check_filled_dco_pvt_endpoints(root)),
        ("bbpd_filled_rcx_pvt", lambda: check_bbpd(root)),
        (
            "pll_loop_nofill_dco_surrogate",
            lambda: check_loop_csv(
                root,
                "build/spice_pll_loop/pll_loop_check.csv",
                expected_rows=2,
                expected_corners=("tt",),
                dco_model="linear",
            ),
        ),
        (
            "pll_loop_filled_dco_surrogate",
            lambda: check_loop_csv(
                root,
                "build/spice_pll_loop_filled_dco/pll_loop_check.csv",
                expected_rows=2,
                expected_corners=("tt",),
                dco_model="piecewise5",
            ),
        ),
        (
            "pll_loop_pvt_surrogate",
            lambda: check_loop_csv(
                root,
                "build/spice_pll_loop_pvt/pll_loop_check.csv",
                expected_rows=10,
                expected_corners=EXPECTED_CORNERS,
                dco_model="linear",
            ),
        ),
        ("gain_tuning_rtl", lambda: check_gain_summaries(root)),
        ("xyce_cinterface_mixed_signal_gain_sweep", lambda: check_xyce_mixed_signal_gain_sweep(root)),
        ("filled_bbpd_sampled_xyce_lock_probe", lambda: check_filled_bbpd_sampled_lock(root)),
        ("dlf_strong_p_transistor_spice", lambda: check_dlf_spice(root)),
        ("mapped_core_bbpd_loop_smoke", lambda: check_mapped_loop_smoke(root)),
        ("mapped_core_bbpd_loop_gain_sweep", lambda: check_mapped_loop_gain_sweep(root)),
        ("mapped_core_bbpd_loop_phase_sweep", lambda: check_mapped_loop_phase_sweep(root)),
        ("mapped_core_bbpd_loop_progress_1us", lambda: check_mapped_loop_progress_1us(root)),
        ("extracted_dco_startup_smoke", lambda: check_extracted_dco_startup_smoke(root)),
        ("extracted_dco_startup_mpi4_klu_smoke", lambda: check_extracted_dco_startup_mpi_klu_smoke(root)),
        ("extracted_dco_first_correction_smoke", lambda: check_extracted_dco_motion_smoke(root)),
        ("extracted_dco_first_correction_mpi4_klu_smoke", lambda: check_extracted_dco_motion_mpi_klu_smoke(root)),
        ("extracted_dco_low_integrator_trend_mpi4_klu", lambda: check_extracted_dco_low_trend_mpi_klu(root)),
        ("extracted_dco_high_integrator_trend_mpi4_klu", lambda: check_extracted_dco_high_trend_mpi_klu(root)),
        ("frac6_extracted_dco_integrator_trend_mpi16_klu", lambda: check_frac6_extracted_dco_trend_mpi16_klu(root)),
        ("frac6_extracted_dco_progress_500ns_mpi16_klu", lambda: check_frac6_extracted_dco_progress_500ns_mpi16_klu(root)),
        ("frac6_extracted_dco_midcode_lock_window_mpi16_klu", lambda: check_frac6_extracted_dco_midcode_lock_mpi16_klu(root)),
        (
            "frac6_extracted_dco_near_high_lock_window_en85_mpi16_klu",
            lambda: check_frac6_extracted_dco_near_high_lock_en85_mpi16_klu(root),
        ),
        (
            "frac6_force127_final_signoff_extracted_dco_lock_820ns_mpi16_klu",
            lambda: check_frac6_force127_final_signoff_extracted_dco_lock_820ns_mpi16_klu(root),
        ),
        ("extracted_dco_midcode_proportional_response_mpi4_klu", lambda: check_extracted_dco_midcode_inc_mpi_klu(root)),
        ("extracted_dco_midcode_kp0_hold_mpi4_klu", lambda: check_extracted_dco_midcode_kp0_hold_mpi_klu(root)),
        (
            "extracted_dco_midcode_frequency_contrast_mpi4_klu",
            lambda: check_extracted_dco_midcode_frequency_contrast_mpi_klu(root),
        ),
        (
            "final_signoff_functional_bbpd_loop_smoke",
            lambda: check_mapped_loop_smoke(
                root,
                relpath="build/spice_pll_mapped_loop_signoff_nl_smoke/mapped_loop_check.csv",
                expected_scope="final_signoff_functional",
                min_instance_count=1600,
                min_skipped_physical_only_cells=4000,
            ),
        ),
        (
            "final_signoff_force127_hardtop_spef_therm_bbpd_loop_smoke_mpi4_klu",
            lambda: check_mapped_loop_smoke(
                root,
                relpath="build/spice_pll_final_force127_hardtop_spef_therm_smoke_mpi4_klu/mapped_loop_check.csv",
                expected_scope="final_signoff_force127_hardtop_spef_therm",
                min_instance_count=2000,
                min_skipped_physical_only_cells=4100,
                expected_mpi_procs=4,
                require_xyce_command="Xyce -linsolv KLU",
                expected_ki=160,
                expected_kp=8,
                expected_dlf_frac_width=6,
                expected_phase={"low_start": 0.0, "high_start": 0.5},
                expected_start_meas_ns=84.0,
                expected_end_meas_ns=219.0,
                expected_enable_ns=85.0,
                expected_clear_width_ns=60.0,
                expected_code_observer_source="dco_therm",
                expected_hardtop_spef_mode="lumped_cap",
                min_hardtop_spef_cap_nets=260,
                min_hardtop_spef_cap_total_ff=20000.0,
                min_hardtop_spef_dco_therm_nets=255,
            ),
        ),
        (
            "final_signoff_force127_hardtop_spef_rc_extracted_dco_startup_mpi16_klu",
            lambda: check_final_signoff_hardtop_spef_rc_extracted_dco_startup_mpi16_klu(root),
        ),
        (
            "final_signoff_force127_hardtop_spef_rc_extracted_dco_motion_low_mpi16_klu",
            lambda: check_final_signoff_hardtop_spef_rc_extracted_dco_motion_low_mpi16_klu(root),
        ),
        (
            "final_signoff_force127_hardtop_spef_rc_extracted_dco_motion_high_mpi16_klu",
            lambda: check_final_signoff_hardtop_spef_rc_extracted_dco_motion_high_mpi16_klu(root),
        ),
        (
            "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_startup_mpi16_klu",
            lambda: check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_startup_mpi16_klu(root),
        ),
        (
            "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_motion_low_mpi16_klu",
            lambda: check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_motion_low_mpi16_klu(root),
        ),
        (
            "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_motion_high_mpi16_klu",
            lambda: check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_motion_high_mpi16_klu(root),
        ),
        (
            "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_midcode_lock_mpi16_klu",
            lambda: check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_midcode_lock_mpi16_klu(root),
        ),
        (
            "final_signoff_force127_hardtop_einvp_spef_rc_corner_midcode_lock_mpi16_klu",
            lambda: check_final_signoff_hardtop_einvp_spef_rc_corner_midcode_lock_mpi16_klu(root),
        ),
        (
            "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_midcode_hold_mpi16_klu",
            lambda: check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_pvt_midcode_hold_mpi16_klu(root),
        ),
        (
            "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_midcode_lock_mpi16_klu",
            lambda: check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_pvt_midcode_lock_mpi16_klu(root),
        ),
        (
            "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_low_lock_mpi16_klu",
            lambda: check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_low_lock_mpi16_klu(root),
        ),
        (
            "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_high_lock_mpi16_klu",
            lambda: check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_pvt_ff_high_lock_mpi16_klu(root),
        ),
        (
            "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_low_lock_mpi16_klu",
            lambda: check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_low_lock_mpi16_klu(root),
        ),
        (
            "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_high_lock_mpi16_klu",
            lambda: check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_pvt_ss_high_lock_mpi16_klu(root),
        ),
        (
            "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_low_progress_mpi16_klu",
            lambda: check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_low_progress_mpi16_klu(root),
        ),
        (
            "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_high_progress_mpi16_klu",
            lambda: check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_high_progress_mpi16_klu(root),
        ),
        (
            "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_low_lock_mpi16_klu",
            lambda: check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_low_lock_mpi16_klu(root),
        ),
        (
            "final_signoff_force127_hardtop_einvp_spef_rc_extracted_dco_high_lock_mpi16_klu",
            lambda: check_final_signoff_hardtop_einvp_spef_rc_extracted_dco_high_lock_mpi16_klu(root),
        ),
        (
            "final_signoff_force127_hardtop_einvp_spef_behavioral_lock_low_mpi16_klu",
            lambda: check_final_signoff_hardtop_einvp_spef_behavioral_lock_low_mpi16_klu(root),
        ),
        (
            "final_signoff_force127_hardtop_einvp_spef_behavioral_lock_high_mpi16_klu",
            lambda: check_final_signoff_hardtop_einvp_spef_behavioral_lock_high_mpi16_klu(root),
        ),
        ("objective_deliverable_evidence", lambda: check_objective_deliverable_evidence(root)),
    ]

    records = []
    failures = []
    for name, func in checks:
        try:
            details = func()
            records.append({"name": name, "status": "pass", "details": details})
            print(f"PASS {name}: {details}")
        except Exception as exc:  # noqa: BLE001 - keep checker failure aggregation simple.
            failures.append(f"{name}: {exc}")
            records.append({"name": name, "status": "fail", "details": str(exc)})
            print(f"FAIL {name}: {exc}", file=sys.stderr)

    summary = {
        "status": "fail" if failures else "pass",
        "checks": records,
        "limitations": [
            "Targeted TT extracted closed-loop lock windows and FF/SS rail-start extracted-loop lock windows are available, including final-signoff functional-netlist runs, but full all-corner extracted PVT closed-loop PLL signoff is not yet available.",
            "The signed-off NAND-load DCO RCX evidence is a five-point TT smoke/calibration, a TT 9-point characterization that records high-end roll-off, a focused high-code tail characterization that localizes the TT peak at code 240, a TT local-gain smoke near code 128, and FF/FS/SF/SS endpoint smoke; it is not a 256-code PVT filled sweep. A separately hardened EINVP-load DCO candidate has TT filled-RCX monotonic measured 5-point calibration, focused high-tail codes, and FF/FS/SF/SS endpoint smoke, and it now has a parallel signed-off hard-macro top with extracted-SPICE interface, calibrated behavioral low/high lock windows, distributed-RC startup, early low/high extracted-DCO first-motion coverage, a hard-top-loaded mid-code extracted-DCO lock-window diagnostic across nominal/min/max E hard-top SPEF, FF/SS hard-top-loaded mid-code extracted-DCO lock-window diagnostics, FF/SS low/high rail extracted-DCO PVT lock-window diagnostics, hard-top-loaded low/high extracted-DCO progress diagnostics, and low/high extracted-DCO rail-start lock-window evidence, but it is not yet a full all-corner PVT loop-transient signoff path.",
            "The filled-BBPD sampled Xyce lock probe is a fixed-aperture surrogate with behavioral filled-DCO calibration, not a full extracted PLL simulation.",
            "The mapped-core BBPD loop smoke, phase sweep, and 1 us progress probe use phase-selected initial conditions and a behavioral filled-DCO model; the 1 us probe reduces but does not close frequency error. The extracted-DCO startup, first-correction, integrator-trend, FRAC=6 500 ns rail-start progress, mid-code gain-contrast, FRAC=6 mid-code lock-window, and phase-selected enable-85 high-side lock-window checks prove oscillator startup, directional code/gain response, rail-start progress, and bounded near-lock windows in the coupled mapped deck, but not rail-start acquisition or full lock; the final signoff netlist smokes omit physical-only tap/fill/decap/antenna diode cells, the NAND hard-top SPEF smoke uses lumped top-level loop-net capacitance, the EINVP hard-top has calibrated behavioral low/high lock windows with lumped top-level loop-net capacitance, and distributed hard-top RC is currently covered by startup plus low/high extracted-DCO first-motion diagnostics for the NAND top and by startup, early low/high first-motion, hard-top-loaded mid-code extracted-DCO lock-window across nominal/min/max E hard-top SPEF, FF/SS hard-top-loaded mid-code hold calibration and lock-window diagnostics, FF/SS low/high rail extracted-DCO PVT lock-window diagnostics, hard-top-loaded low/high extracted-DCO progress diagnostics, and low/high rail-start extracted-DCO lock-window diagnostics for the EINVP top.",
            "The hard-macro top extracted-SPICE interface check proves wrapper connectivity, nominal SPEF size, and Xyce syntax/topology setup, but it keeps the three macros abstract and is not a closed-loop extracted transient.",
        ],
    }
    check_finite_numbers(summary)

    summary_json = out_dir / "sky130_pll_validation_summary.json"
    summary_csv = out_dir / "sky130_pll_validation_summary.csv"
    summary_json.write_text(json.dumps(summary, indent=2) + "\n", encoding="ascii")
    with summary_csv.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=("name", "status", "details"))
        writer.writeheader()
        for record in records:
            writer.writerow(
                {
                    "name": record["name"],
                    "status": record["status"],
                    "details": json.dumps(record["details"], sort_keys=True),
                }
            )

    print(f"wrote {summary_csv}")
    print(f"wrote {summary_json}")
    if failures:
        print("Sky130 PLL validation check failed:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    print(f"Sky130 PLL validation artifact check pass: {len(records)} checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
