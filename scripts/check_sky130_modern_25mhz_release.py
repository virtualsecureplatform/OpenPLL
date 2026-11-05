#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Audit the separate modern-Ciel TT five-mode PLL evidence."""

from __future__ import annotations

import csv
import json
import re
import subprocess
import sys
from pathlib import Path

from sky130_modern_targets import TARGETS_MHZ, load_target_presets
from dco_calibration import measure
from pll_verification import load_spec
from pvt_release_gate import check_pvt_grid


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build" / "modern_25mhz"
MANIFEST = ROOT / "sky130" / "modern_25mhz_targets.json"
PDK_VERSION = "1689ac3f2dc763876eaf967227c7dfe831b031ae"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def read_json(path: Path) -> dict:
    require(path.is_file(), f"missing release evidence: {path}")
    data = json.loads(path.read_text(encoding="ascii"))
    require(isinstance(data, dict), f"invalid JSON summary: {path}")
    return data


def evidence_path(value: str) -> Path:
    if value.startswith("/work/OpenPLL/"):
        return ROOT / value.removeprefix("/work/OpenPLL/")
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def require_current(output: Path, inputs: list[Path], label: str) -> None:
    require(output.is_file(), f"missing {label}: {output}")
    for source in inputs:
        require(source.is_file(), f"missing {label} input: {source}")
        require(output.stat().st_mtime_ns >= source.stat().st_mtime_ns,
                f"stale {label}: {output} predates {source}")


def check_dco(data: dict) -> list[dict]:
    spec = load_spec()
    rows: dict[tuple[int, int], dict[str, str]] = {}
    rcx = (ROOT / "openlane" / "IntegerPLL_DCO_EINVP_COARSE" / "runs"
           / data["dco_run_tag"] / "rcx-magic"
           / "IntegerPLL_DCO_EINVP_COARSE.rcx.spice")
    require(rcx.is_file(), f"missing characterized DCO extraction: {rcx}")
    measurements = BUILD / "dco_measurements.csv"
    require_current(measurements, [rcx], "DCO measurements")
    with measurements.open(newline="", encoding="ascii") as handle:
        for row in csv.DictReader(handle):
            if row.get("corner") != "tt" or row.get("status") != "pass":
                continue
            require(row.get("simulator") == "xyce", "DCO evidence is not from Xyce")
            require(row.get("subckt_name") == "IntegerPLL_DCO_EINVP_COARSE", "wrong DCO subcircuit")
            rows[int(row["coarse_code"]), int(row["code"])] = row

    results = []
    for target in TARGETS_MHZ:
        mode = data["targets"][str(target)]
        coarse, code = mode["coarse_code"], mode["target_code"]
        codes = [0, code - 8, code, code + 8, 255]
        require(len(set(codes)) == 5 and min(codes) >= 0 and max(codes) <= 255,
                f"{target} MHz seed lacks eight-code measurement margin")
        frequencies = []
        for measured_code in codes:
            row = rows.get((coarse, measured_code))
            require(row is not None, f"missing TT DCO row C{coarse}/code{measured_code}")
            deck = evidence_path(row["netlist"])
            log = evidence_path(row["log"])
            require_current(deck, [rcx], f"TT DCO deck C{coarse}/code{measured_code}")
            require_current(log, [deck, ROOT / "scripts" / "spice_dco_postlayout.py"],
                            f"TT DCO log C{coarse}/code{measured_code}")
            require_current(measurements, [log], "DCO measurements")
            require(f"/runs/{data['dco_run_tag']}/rcx-magic/IntegerPLL_DCO_EINVP_COARSE.rcx.spice"
                    in deck.read_text(encoding="ascii"),
                    f"TT DCO deck C{coarse}/code{measured_code} uses the wrong extraction")
            period = float(row["period_s"])
            duty = float(row["duty_ratio"])
            require(0.35 <= duty <= 0.65, f"{target} MHz duty ratio failed at code{measured_code}")
            require(max(float(row["rise_time_s"]), float(row["fall_time_s"])) <= period * 0.25,
                    f"{target} MHz edge time failed at code{measured_code}")
            frequencies.append(float(row["freq_mhz"]))
        require(all(a < b for a, b in zip(frequencies, frequencies[1:])),
                f"{target} MHz measured fine tuning is not monotonic")
        require(abs(frequencies[2] - target) <= 2.0,
                f"{target} MHz extracted DCO exceeds 2 MHz error")
        for observed, field in ((frequencies[0], "f0_mhz"),
                                (frequencies[2], "f_target_mhz"),
                                (frequencies[4], "f255_mhz")):
            require(abs(observed - float(mode[field])) < 0.05,
                    f"{target} MHz manifest {field} differs from measured CSV")
        target_waveform = evidence_path(rows[coarse, code]["waveform"])
        require_current(target_waveform, [rcx], f"TT DCO waveform C{coarse}/code{code}")
        window = measure(target_waveform, 12, 70, 1.8, min_periods=3)
        error_ppm = abs(window["mhz"] / target - 1) * 1e6
        results.append({"target_mhz": target, "coarse_code": coarse,
                        "target_code": code, "freq_mhz": frequencies[2],
                        "window_12_70_mhz": window["mhz"],
                        "window_periods": window["periods"],
                        "window_half_difference_mhz": window["half_window_difference_mhz"],
                        "window_frequency_error_ppm": error_ppm,
                        "approved_window_frequency_passed": (
                            window["periods"] >= 8 and
                            error_ppm <= spec["frequency_error_ppm"]),
                        "status": "pass"})
    return results


def check_physical(data: dict) -> None:
    dco_source = (ROOT / "sky130" / "IntegerPLL_DCO_einvp_coarse_modern_sky130.v").read_text(encoding="ascii")
    require(f"localparam integer STRONG_LOAD_COUNT = {data['dco_strong_load_count']};" in dco_source,
            "DCO source load count differs from target manifest")
    dco_netlist = (ROOT / "openlane" / "IntegerPLL_DCO_EINVP_COARSE" / "runs"
                   / data["dco_run_tag"] / "final" / "nl"
                   / "IntegerPLL_DCO_EINVP_COARSE.nl.v").read_text(encoding="ascii")
    require(len(re.findall(r"\bsky130_fd_sc_hd__nand2_2\s", dco_netlist)) == 16
            and len(re.findall(r"\bsky130_fd_sc_hd__nand2_1\s", dco_netlist)) == 239,
            "modern physical DCO does not have 16 strong and 239 normal loads")
    dco_config = read_json(ROOT / "openlane" / "IntegerPLL_DCO_EINVP_COARSE" / "config_modern.json")
    hardtop_config = read_json(ROOT / "openlane" / "IntegerPLL_HardMacroTop_EINVP" / "config_modern.json")
    configured_config = read_json(ROOT / "openlane" / "IntegerPLL_HardMacroTop_EINVP_25MHzConfigured" / "config_modern.json")
    require(dco_config["VERILOG_FILES"] == ["dir::../../sky130/IntegerPLL_DCO_einvp_coarse_modern_sky130.v"],
            "modern DCO config uses the wrong source")
    for view in ("gds", "lef", "vh", "pnl", "spice"):
        path = hardtop_config["MACROS"]["IntegerPLL_DCO_EINVP_COARSE"][view][0]
        require(f"/runs/{data['dco_run_tag']}/" in path,
                f"modern hard top {view} does not use the characterized DCO run")
        configured_view = configured_config["MACROS"]["IntegerPLL_HardMacroTop_EINVP"][view][0]
        require("/runs/modern_signoff/" in configured_view,
                f"configured {view} does not use the modern hard top")
    require("dir::../../rtl/IntegerPLL_25MHzModeConfig_modern.v" in configured_config["VERILOG_FILES"],
            "configured physical design does not use modern presets")
    for design, run_tag, source_files in (
        ("IntegerPLL_DCO_EINVP_COARSE", data["dco_run_tag"],
         ["sky130/IntegerPLL_DCO_einvp_coarse_modern_sky130.v",
          "openlane/IntegerPLL_DCO_EINVP_COARSE/config_modern.json"]),
        ("IntegerPLL_HardMacroTop_EINVP", "modern_signoff",
         ["rtl/IntegerPLL_HardMacroTop_EINVP.v",
          "openlane/IntegerPLL_HardMacroTop_EINVP/config_modern.json"]),
        ("IntegerPLL_HardMacroTop_EINVP_25MHzConfigured", "modern_signoff",
         ["rtl/IntegerPLL_25MHzModeConfig_modern.v",
          "rtl/IntegerPLL_HardMacroTop_EINVP_25MHzConfigured.v",
          "openlane/IntegerPLL_HardMacroTop_EINVP_25MHzConfigured/config_modern.json"]),
    ):
        command = [sys.executable, str(ROOT / "scripts" / "check_librelane_signoff.py"),
                   "--design-name", design,
                   "--final-dir", str(ROOT / "openlane" / design / "runs" / run_tag / "final")]
        if design == "IntegerPLL_DCO_EINVP_COARSE":
            command += ["--skip-magic-streamout", "--skip-xor"]
        for source_file in source_files:
            command += ["--source-file", source_file]
        subprocess.run(command, cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    for path in (
        BUILD / "hardtop" / "hard_macro_top_einvp_summary.json",
        BUILD / "hardtop_spice" / "hard_macro_top_spice_summary.json",
        BUILD / "configured" / "configured_hard_macro_top_einvp_summary.json",
    ):
        summary = read_json(path)
        require(summary.get("status") == "pass", f"physical summary failed: {path}")
        if "signoff" in summary:
            require(summary["signoff"].get("status") == "pass", f"physical signoff failed: {path}")
    require_current(BUILD / "hardtop" / "hard_macro_top_einvp_summary.json",
                    [ROOT / "openlane" / "IntegerPLL_HardMacroTop_EINVP" / "runs"
                     / "modern_signoff" / "final" / "metrics.json"], "hard-top summary")
    require_current(BUILD / "configured" / "configured_hard_macro_top_einvp_summary.json",
                    [ROOT / "openlane" / "IntegerPLL_HardMacroTop_EINVP_25MHzConfigured"
                     / "runs" / "modern_signoff" / "final" / "metrics.json"],
                    "configured summary")


def check_behavioral(data: dict) -> None:
    log_path = ROOT / "build" / "check_modern" / "configured_behavioral.log"
    require_current(log_path, [MANIFEST,
                               ROOT / "rtl" / "IntegerPLL_25MHzModeConfig_modern.v",
                               ROOT / "rtl" / "IntegerPLL_25MHzModeController.v",
                               ROOT / "rtl" / "IntegerPLL_DigitalCore.v",
                               ROOT / "rtl" / "IntegerPLL_Top.v",
                               ROOT / "models" / "IntegerPLL_DCO_25MHzCoarse_modern_model.v",
                               ROOT / "tb" / "tb_pll_25mhz_configured_behavioral_modern.v"],
                    "behavioral result")
    log = log_path.read_text(encoding="ascii")
    require("PASS: 25 MHz configured behavioral PLL tracking" in log,
            "modern behavioral tracking did not pass")
    for target in TARGETS_MHZ:
        mode = data["targets"][str(target)]
        pattern = rf"RESULT: feedback_divider={mode['ndiv']} target_mhz={target} .*coarse={mode['coarse_code']} target_code={mode['target_code']} "
        require(re.search(pattern, log) is not None, f"missing {target} MHz behavioral row")


def check_tracking(data: dict) -> None:
    summary_path = BUILD / "tracking" / "pll_25mhz_target_summary.json"
    require_current(summary_path, [BUILD / "dco_measurements.csv", MANIFEST,
                                   ROOT / "scripts" / "xyce_pll_25mhz_target_sweep.py",
                                   ROOT / "build" / "xyce_cinterface_smoke_mpi"
                                   / "xyce_pll_mixed_signal_smoke"], "tracking summary")
    summary = read_json(summary_path)
    require(summary.get("status") == "pass", "configured mixed-signal tracking failed")
    by_target = {int(float(row["target_mhz"])): row for row in summary["target_results"]}
    for target in TARGETS_MHZ:
        row, mode = by_target[target], data["targets"][str(target)]
        require(row["status"] == "pass" and int(row["coarse_code"]) == mode["coarse_code"]
                and int(row["target_code"]) == mode["target_code"],
                f"{target} MHz configured tracking preset or status failed")
        require("ki16_kp4" in row["passing_gains"], f"{target} MHz configured tracking gain failed")


def check_direct(data: dict) -> None:
    rcx = (ROOT / "openlane" / "IntegerPLL_DCO_EINVP_COARSE" / "runs"
           / data["dco_run_tag"] / "rcx-magic"
           / "IntegerPLL_DCO_EINVP_COARSE.rcx.spice")
    for target in TARGETS_MHZ:
        mode = data["targets"][str(target)]
        hold_path = BUILD / f"hold_{target}" / "pll_postlayout_dco_25mhz_hold_summary.json"
        near_path = BUILD / f"nearseed_{target}" / "pll_postlayout_dco_25mhz_nearseed_summary.json"
        hold = read_json(hold_path)
        near = read_json(near_path)
        require(hold.get("status") == "pass" and near.get("status") == "pass",
                f"{target} MHz direct-RCX hold or near-seed run failed")
        require(len(hold["target_results"]) == 1 and len(near["target_results"]) == 2,
                f"{target} MHz direct-RCX case count is wrong")
        hold_row = hold["target_results"][0]
        require(near["target_results"][0]["deck"] != near["target_results"][1]["deck"],
                f"{target} MHz low/high direct-RCX decks are not separate")
        for row in (hold_row, *near["target_results"]):
            deck = evidence_path(row["deck"])
            log = evidence_path(row["log"])
            require_current(deck, [rcx], f"{target} MHz direct-RCX deck")
            sweep_script = ("xyce_pll_postlayout_dco_25mhz_hold_sweep.py" if row is hold_row
                            else "xyce_pll_postlayout_dco_25mhz_nearseed_sweep.py")
            require_current(log, [deck, MANIFEST, ROOT / "scripts" / sweep_script,
                                  ROOT / "scripts" / "xyce_pll_postlayout_dco_cinterface_deck.py",
                                  ROOT / "build" / "xyce_cinterface_smoke_mpi"
                                  / "xyce_pll_postlayout_dco_mixed_signal_smoke"],
                            f"{target} MHz direct-RCX log")
            summary_path = hold_path if row is hold_row else near_path
            require_current(summary_path, [log], f"{target} MHz direct-RCX summary")
            require(f"/runs/{data['dco_run_tag']}/rcx-magic/IntegerPLL_DCO_EINVP_COARSE.rcx.spice"
                    in deck.read_text(encoding="ascii"),
                    f"{target} MHz direct-RCX deck uses the wrong extraction")
        require(hold_row["status"] == "pass" and int(hold_row["coarse_code"]) == mode["coarse_code"]
                and int(hold_row["target_code"]) == mode["target_code"]
                and int(hold_row["final_code"]) == mode["target_code"],
                f"{target} MHz direct-RCX hold code failed")
        by_side = {row["side"]: row for row in near["target_results"]}
        require(set(by_side) == {"low", "high"}, f"{target} MHz missing near-seed side")
        for side, expect, offset in (("low", "increase", -4), ("high", "decrease", 4)):
            row = by_side[side]
            require(row["status"] == "pass" and row["expect"] == expect
                    and int(row["coarse_code"]) == mode["coarse_code"]
                    and int(row["target_code"]) == mode["target_code"]
                    and int(row["init_code"]) == mode["target_code"] + offset
                    and int(row["expected_decisions"]) >= 1
                    and int(row["final_abs_error"]) <= 4,
                    f"{target} MHz {side} near-seed correction failed")


def main() -> int:
    path = BUILD / "check_summary.json"
    path.unlink(missing_ok=True)
    spec = load_spec()
    require(tuple(spec["modes_mhz"]) == TARGETS_MHZ,
            "release audit target list differs from approved engineering requirements")
    data = read_json(MANIFEST)
    require(data.get("pdk_version") == PDK_VERSION, "wrong modern Ciel PDK pin")
    defaults = {target: {"coarse_code": 0, "target_code": 128, "ndiv": target // 25}
                for target in TARGETS_MHZ}
    load_target_presets(MANIFEST, defaults)
    subprocess.run([sys.executable, str(ROOT / "scripts" / "generate_modern_25mhz.py"), "--check"],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    dco_results = check_dco(data)
    check_physical(data)
    check_behavioral(data)
    check_tracking(data)
    check_direct(data)
    approved_window_frequency_all_passed = all(
        row["approved_window_frequency_passed"] for row in dco_results)
    rcx = (ROOT / "openlane" / "IntegerPLL_DCO_EINVP_COARSE" / "runs"
           / data["dco_run_tag"] / "rcx-magic"
           / "IntegerPLL_DCO_EINVP_COARSE.rcx.spice")
    pvt = check_pvt_grid(BUILD / "pvt_qualification", load_spec(), rcx,
                         "IntegerPLL_DCO_EINVP_COARSE")
    release_passed = approved_window_frequency_all_passed and pvt["passed"]
    output = {"status": "pass" if release_passed else "fail",
              "scoped_near_seed_status": "pass", "pdk_version": PDK_VERSION,
              "dco_strong_load_count": data["dco_strong_load_count"],
              "targets": dco_results,
              "approved_window_frequency_all_passed": approved_window_frequency_all_passed,
              "pvt_qualification": pvt,
              "scope": "TT configured near-seed, full-window frequency, and extracted-DCO PVT; not arbitrary-start PLL lock"}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(output, indent=2) + "\n", encoding="ascii")
    print(path)
    return 0 if release_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
