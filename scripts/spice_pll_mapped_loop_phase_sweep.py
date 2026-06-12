#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import concurrent.futures
import csv
import os
import subprocess
import sys
from pathlib import Path

from xyce_utils import add_xyce_arguments, validate_xyce_arguments


FILLED_DCO_DEFAULTS = {
    "f0_mhz": 46.25672588520797,
    "f64_mhz": 47.95039109460694,
    "f128_mhz": 49.762117807733404,
    "f192_mhz": 51.61843654151962,
    "f255_mhz": 52.34983089216307,
}


def parse_float_list(text):
    values = []
    for item in text.split(","):
        item = item.strip()
        if item:
            values.append(float(item))
    if not values:
        raise ValueError("empty phase list")
    return values


def parse_cases(text):
    cases = [item.strip() for item in text.split(",") if item.strip()]
    known_cases = ("low_start", "high_start", "mid_start_inc", "mid_start_dec")
    unknown = [case for case in cases if case not in known_cases]
    if unknown:
        raise ValueError(f"unknown mapped-loop case(s): {', '.join(unknown)}")
    if not cases:
        raise ValueError("empty case list")
    return cases


def value_slug(value):
    return f"{value:g}".replace("-", "m").replace(".", "p")


def read_csv(path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="ascii") as csv_file:
        return list(csv.DictReader(csv_file))


def to_float(value):
    if value in ("", None):
        return None
    return float(value)


def run_combo(root, args, case_name, initial_phase):
    combo_name = f"{case_name}_phase{value_slug(initial_phase)}"
    combo_dir = args.build_dir / combo_name
    combo_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = combo_dir / "phase_sweep_stdout.log"

    cmd = [
        sys.executable,
        str(root / "scripts" / "spice_pll_mapped_loop_check.py"),
        "--cases",
        case_name,
        "--mapped-verilog",
        str(args.mapped_verilog),
        "--pdk-root",
        str(args.pdk_root),
        "--pdk",
        args.pdk,
        "--std-cell-library",
        args.std_cell_library,
        "--corner",
        args.corner,
        "--bbpd-rcx-netlist",
        str(args.bbpd_rcx_netlist),
        "--bbpd-subckt",
        args.bbpd_subckt,
        "--ki",
        str(args.ki),
        "--kp",
        str(args.kp),
        "--dlf-code-width",
        str(args.dlf_code_width),
        "--dlf-frac-width",
        str(args.dlf_frac_width),
        "--ndiv",
        str(args.ndiv),
        "--f0-mhz",
        str(args.f0_mhz),
        "--f64-mhz",
        str(args.f64_mhz),
        "--f128-mhz",
        str(args.f128_mhz),
        "--f192-mhz",
        str(args.f192_mhz),
        "--f255-mhz",
        str(args.f255_mhz),
        "--threshold",
        str(args.threshold),
        "--code-sharpness",
        str(args.code_sharpness),
        "--clock-sharpness",
        str(args.clock_sharpness),
        "--initial-dco-phase-cycles",
        str(initial_phase),
        "--reset-release-ns",
        str(args.reset_release_ns),
        "--clear-start-ns",
        str(args.clear_start_ns),
        "--clear-width-ns",
        str(args.clear_width_ns),
        "--enable-ns",
        str(args.enable_ns),
        "--start-meas-ns",
        str(args.start_meas_ns),
        "--end-meas-ns",
        str(args.end_meas_ns),
        "--sim-time-ns",
        str(args.sim_time_ns),
        "--step-ps",
        str(args.step_ps),
        "--max-step-ps",
        str(args.max_step_ps),
        "--start-code-tolerance",
        str(args.start_code_tolerance),
        "--min-code-motion",
        str(args.min_code_motion),
        "--timeout-s",
        str(args.timeout_s),
        "--simulator",
        "xyce",
        "--xyce",
        args.xyce,
        "--xyce-mpi-procs",
        str(args.xyce_mpi_procs),
        "--xyce-mpi-launcher",
        args.xyce_mpi_launcher,
        "--build-dir",
        str(combo_dir),
    ]
    if args.ref_mhz is not None:
        cmd.extend(["--ref-mhz", str(args.ref_mhz)])
    if args.print_internal_debug:
        cmd.append("--print-internal-debug")
    if args.resume:
        cmd.append("--resume")

    proc = subprocess.run(
        cmd,
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    stdout_path.write_text(proc.stdout, encoding="utf-8")

    rows = read_csv(combo_dir / "mapped_loop_check.csv")
    if not rows:
        rows = [
            {
                "case": case_name,
                "status": "fail",
                "simulator": "xyce",
                "xyce_mpi_procs": args.xyce_mpi_procs,
                "bbpd_impl": "postlayout",
                "digital_scope": "full",
                "dco_model": "piecewise5_behavioral",
                "expected": "",
                "ki": args.ki,
                "kp": args.kp,
                "dlf_code_width": args.dlf_code_width,
                "dlf_frac_width": args.dlf_frac_width,
                "ndiv": args.ndiv,
                "initial_dco_phase_cycles": initial_phase,
                "returncode": proc.returncode,
                "timed_out": "",
                "elapsed_s": "",
                "start_code": "",
                "end_code": "",
                "observed_min_code": "",
                "observed_max_code": "",
                "response_code": "",
                "start_freq_mhz": "",
                "end_freq_mhz": "",
                "netlist": "",
                "log": "",
                "waveform": "",
            }
        ]

    for row in rows:
        row["sweep_combo"] = combo_name
        row["sweep_returncode"] = proc.returncode
        row["sweep_stdout_log"] = str(stdout_path)
        row["sweep_build_dir"] = str(combo_dir)
    return rows


def summarize(rows):
    by_phase = {}
    for row in rows:
        phase = row.get("initial_dco_phase_cycles", "")
        entry = by_phase.setdefault(
            phase,
            {
                "initial_dco_phase_cycles": phase,
                "low_status": "missing",
                "high_status": "missing",
                "low_start_code": "",
                "low_end_code": "",
                "low_response_code": "",
                "low_observed_min_code": "",
                "low_observed_max_code": "",
                "high_start_code": "",
                "high_end_code": "",
                "high_response_code": "",
                "high_observed_min_code": "",
                "high_observed_max_code": "",
                "low_elapsed_s": "",
                "high_elapsed_s": "",
                "pass_both": 0,
            },
        )
        if row.get("case") == "low_start":
            prefix = "low"
        elif row.get("case") == "high_start":
            prefix = "high"
        else:
            continue
        entry[f"{prefix}_status"] = row.get("status", "")
        entry[f"{prefix}_start_code"] = row.get("start_code", "")
        entry[f"{prefix}_end_code"] = row.get("end_code", "")
        entry[f"{prefix}_response_code"] = row.get("response_code", "")
        entry[f"{prefix}_observed_min_code"] = row.get("observed_min_code", "")
        entry[f"{prefix}_observed_max_code"] = row.get("observed_max_code", "")
        entry[f"{prefix}_elapsed_s"] = row.get("elapsed_s", "")

    for entry in by_phase.values():
        entry["pass_both"] = int(
            entry["low_status"] == "pass" and entry["high_status"] == "pass"
        )

    return sorted(
        by_phase.values(),
        key=lambda row: to_float(row["initial_dco_phase_cycles"]),
    )


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        raise ValueError(f"no rows to write to {path}")
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Sweep initial DCO phase for the mapped-core PLL loop smoke."
    )
    parser.add_argument("--cases", default="low_start,high_start")
    parser.add_argument("--initial-dco-phase-cycles-values", default="0,0.25,0.5,0.75")
    parser.add_argument(
        "--mapped-verilog",
        default=str(root / "build" / "synth" / "IntegerPLL_DigitalCore_sky130.v"),
    )
    parser.add_argument("--pdk-root", default=os.environ.get("PDK_ROOT", "~/.volare"))
    parser.add_argument("--pdk", default=os.environ.get("PDK", "sky130A"))
    parser.add_argument(
        "--std-cell-library",
        default=os.environ.get("STD_CELL_LIBRARY", "sky130_fd_sc_hd"),
    )
    parser.add_argument("--corner", default="tt")
    parser.add_argument(
        "--bbpd-rcx-netlist",
        default=str(
            root
            / "openlane"
            / "IntegerPLL_BBPD"
            / "runs"
            / "librelane_signoff"
            / "rcx-magic"
            / "IntegerPLL_BBPD.rcx.spice"
        ),
    )
    parser.add_argument("--bbpd-subckt", default="IntegerPLL_BBPD")
    parser.add_argument("--ki", type=int, default=255)
    parser.add_argument("--kp", type=int, default=32)
    parser.add_argument("--dlf-code-width", type=int, default=10)
    parser.add_argument("--dlf-frac-width", type=int, default=8)
    parser.add_argument("--ndiv", type=int, default=2)
    parser.add_argument("--ref-mhz", type=float, default=None)
    parser.add_argument("--f0-mhz", type=float, default=FILLED_DCO_DEFAULTS["f0_mhz"])
    parser.add_argument("--f64-mhz", type=float, default=FILLED_DCO_DEFAULTS["f64_mhz"])
    parser.add_argument("--f128-mhz", type=float, default=FILLED_DCO_DEFAULTS["f128_mhz"])
    parser.add_argument("--f192-mhz", type=float, default=FILLED_DCO_DEFAULTS["f192_mhz"])
    parser.add_argument("--f255-mhz", type=float, default=FILLED_DCO_DEFAULTS["f255_mhz"])
    parser.add_argument("--threshold", type=float, default=0.9)
    parser.add_argument("--code-sharpness", type=float, default=20.0)
    parser.add_argument("--clock-sharpness", type=float, default=500.0)
    parser.add_argument("--reset-release-ns", type=float, default=5.0)
    parser.add_argument("--clear-start-ns", type=float, default=10.0)
    parser.add_argument("--clear-width-ns", type=float, default=60.0)
    parser.add_argument("--enable-ns", type=float, default=80.0)
    parser.add_argument("--start-meas-ns", type=float, default=79.0)
    parser.add_argument("--end-meas-ns", type=float, default=129.0)
    parser.add_argument("--sim-time-ns", type=float, default=130.0)
    parser.add_argument("--step-ps", type=float, default=1000.0)
    parser.add_argument("--max-step-ps", type=float, default=1000.0)
    parser.add_argument("--start-code-tolerance", type=float, default=2.0)
    parser.add_argument("--min-code-motion", type=float, default=1.0)
    parser.add_argument("--timeout-s", default="900")
    parser.add_argument("--print-internal-debug", action="store_true")
    add_xyce_arguments(parser)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse matching existing per-phase mapped-loop deck/log/waveform files.",
    )
    parser.add_argument("--require-all-pass", action="store_true")
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=root / "build" / "spice_pll_mapped_loop_phase_sweep",
    )
    args = parser.parse_args()
    args.mapped_verilog = Path(args.mapped_verilog).expanduser().resolve()
    args.pdk_root = Path(args.pdk_root).expanduser().resolve()
    args.bbpd_rcx_netlist = Path(args.bbpd_rcx_netlist).expanduser().resolve()
    args.build_dir = args.build_dir.expanduser().resolve()

    if args.jobs < 1:
        raise ValueError("--jobs must be positive")
    if args.dlf_code_width != 10:
        raise ValueError("--dlf-code-width must remain 10 for the current mapped loop deck")
    if args.dlf_frac_width < 0 or args.dlf_frac_width > 12:
        raise ValueError("--dlf-frac-width must be in 0..12")
    validate_xyce_arguments(args)
    case_names = parse_cases(args.cases)
    phase_values = parse_float_list(args.initial_dco_phase_cycles_values)
    combos = [(case_name, phase) for phase in phase_values for case_name in case_names]

    print(
        f"running {len(combos)} mapped-loop phase cases with jobs={args.jobs}",
        flush=True,
    )
    all_rows = []
    if args.jobs == 1:
        for case_name, phase in combos:
            all_rows.extend(run_combo(root, args, case_name, phase))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
            future_map = {
                executor.submit(run_combo, root, args, case_name, phase): (
                    case_name,
                    phase,
                )
                for case_name, phase in combos
            }
            for future in concurrent.futures.as_completed(future_map):
                all_rows.extend(future.result())

    all_rows.sort(
        key=lambda row: (
            to_float(row.get("initial_dco_phase_cycles", "")),
            row.get("case", ""),
        )
    )
    summary_rows = summarize(all_rows)

    detail_path = args.build_dir / "mapped_loop_phase_sweep.csv"
    summary_path = args.build_dir / "mapped_loop_phase_summary.csv"
    write_csv(detail_path, all_rows)
    write_csv(summary_path, summary_rows)

    for row in summary_rows:
        print(
            f"phase={row['initial_dco_phase_cycles']} "
            f"low={row['low_status']}:{row['low_start_code']}->{row['low_end_code']}"
            f" response={row['low_response_code']} "
            f"high={row['high_status']}:{row['high_start_code']}->{row['high_end_code']}"
            f" response={row['high_response_code']} "
            f"pass_both={row['pass_both']}"
        )
    print(f"wrote {detail_path}")
    print(f"wrote {summary_path}")

    if args.require_all_pass and not all(row["status"] == "pass" for row in all_rows):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
