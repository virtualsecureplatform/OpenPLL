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


def parse_int_list(text):
    values = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        value = int(item, 0)
        if value < 0 or value > 255:
            raise ValueError(f"gain value out of 8-bit range: {value}")
        values.append(value)
    if not values:
        raise ValueError("empty gain list")
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


def response_delta(row):
    start = to_float(row.get("start_code"))
    response = to_float(row.get("response_code"))
    if start is None or response is None:
        return None
    if row.get("expected") == "decrease":
        return start - response
    return response - start


def run_combo(root, args, case_name, kp):
    combo_name = f"{case_name}_kp{value_slug(kp)}"
    combo_dir = args.build_dir / combo_name
    combo_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = combo_dir / "gain_sweep_stdout.log"
    check_mode = "no_motion" if args.kp0_no_motion and kp == 0 else args.check_mode

    cmd = [
        sys.executable,
        str(root / "scripts" / "spice_pll_mapped_loop_check.py"),
        "--cases",
        case_name,
        "--mapped-verilog",
        str(args.mapped_verilog),
        "--digital-scope",
        args.digital_scope,
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
        "--dco-impl",
        args.dco_impl,
        "--dco-rcx-netlist",
        str(args.dco_rcx_netlist),
        "--dco-subckt",
        args.dco_subckt,
        "--ki",
        str(args.ki),
        "--kp",
        str(kp),
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
        str(args.initial_dco_phase_cycles),
        "--reset-release-ns",
        str(args.reset_release_ns),
        "--supply-ramp-delay-ns",
        str(args.supply_ramp_delay_ns),
        "--supply-ramp-ns",
        str(args.supply_ramp_ns),
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
        "--check-mode",
        check_mode,
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
    if args.tran_uic:
        cmd.append("--tran-uic")
    else:
        cmd.append("--no-tran-uic")
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
                "digital_scope": args.digital_scope,
                "dco_model": "piecewise5_behavioral"
                if args.dco_impl == "behavioral"
                else "postlayout_rcx",
                "expected": "",
                "check_mode": check_mode,
                "ki": args.ki,
                "kp": kp,
                "ndiv": args.ndiv,
                "initial_dco_phase_cycles": args.initial_dco_phase_cycles,
                "returncode": proc.returncode,
                "timed_out": "",
                "elapsed_s": "",
                "start_code": "",
                "end_code": "",
                "observed_min_code": "",
                "observed_max_code": "",
                "response_code": "",
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
        row["sweep_check_mode"] = check_mode
        delta = response_delta(row)
        row["response_delta_code"] = "" if delta is None else delta
    return rows


def summarize(rows):
    summary = []
    for row in rows:
        start = to_float(row.get("start_code"))
        end = to_float(row.get("end_code"))
        response = to_float(row.get("response_code"))
        delta = response_delta(row)
        end_delta = None
        if start is not None and end is not None:
            end_delta = start - end if row.get("expected") == "decrease" else end - start
        summary.append(
            {
                "case": row.get("case", ""),
                "ki": row.get("ki", ""),
                "kp": row.get("kp", ""),
                "check_mode": row.get("check_mode", ""),
                "status": row.get("status", ""),
                "expected": row.get("expected", ""),
                "start_code": row.get("start_code", ""),
                "end_code": row.get("end_code", ""),
                "response_code": row.get("response_code", ""),
                "response_delta_code": "" if delta is None else delta,
                "end_delta_code": "" if end_delta is None else end_delta,
                "observed_min_code": row.get("observed_min_code", ""),
                "observed_max_code": row.get("observed_max_code", ""),
                "start_integ_code": row.get("start_integ_code", ""),
                "end_integ_code": row.get("end_integ_code", ""),
                "startup_freq_mhz": row.get("startup_freq_mhz", ""),
                "elapsed_s": row.get("elapsed_s", ""),
                "sweep_combo": row.get("sweep_combo", ""),
                "sweep_build_dir": row.get("sweep_build_dir", ""),
                "waveform": row.get("waveform", ""),
            }
        )
    return sorted(
        summary,
        key=lambda row: (
            row["case"],
            int(float(row["kp"])) if row["kp"] not in ("", None) else -1,
        ),
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
        description="Sweep DLF_KP in the mapped-core PLL loop smoke."
    )
    parser.add_argument("--cases", default="mid_start_inc")
    parser.add_argument("--kp-values", default="0,4,8,16,32")
    parser.add_argument(
        "--mapped-verilog",
        default=str(root / "build" / "synth" / "IntegerPLL_DigitalCore_sky130.v"),
    )
    parser.add_argument("--digital-scope", default="full")
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
    parser.add_argument("--dco-impl", choices=("behavioral", "postlayout"), default="behavioral")
    parser.add_argument(
        "--dco-rcx-netlist",
        default=str(
            root
            / "openlane"
            / "IntegerPLL_DCO"
            / "runs"
            / "librelane_signoff"
            / "rcx-magic"
            / "IntegerPLL_DCO.rcx.spice"
        ),
    )
    parser.add_argument("--dco-subckt", default="IntegerPLL_DCO")
    parser.add_argument("--ki", type=int, default=255)
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
    parser.add_argument("--initial-dco-phase-cycles", type=float, default=0.0)
    parser.add_argument("--reset-release-ns", type=float, default=5.0)
    parser.add_argument("--supply-ramp-delay-ns", type=float, default=0.0)
    parser.add_argument("--supply-ramp-ns", type=float, default=0.0)
    parser.add_argument("--clear-start-ns", type=float, default=10.0)
    parser.add_argument("--clear-width-ns", type=float, default=60.0)
    parser.add_argument("--enable-ns", type=float, default=80.0)
    parser.add_argument("--start-meas-ns", type=float, default=79.0)
    parser.add_argument("--end-meas-ns", type=float, default=179.0)
    parser.add_argument("--sim-time-ns", type=float, default=180.0)
    parser.add_argument("--step-ps", type=float, default=1000.0)
    parser.add_argument("--max-step-ps", type=float, default=1000.0)
    parser.add_argument("--tran-uic", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--start-code-tolerance", type=float, default=2.0)
    parser.add_argument("--min-code-motion", type=float, default=0.1)
    parser.add_argument(
        "--check-mode",
        choices=("motion", "no_motion"),
        default="motion",
        help="Mode used for nonzero-KP rows.",
    )
    parser.add_argument(
        "--kp0-no-motion",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use no_motion mode for KP=0 rows.",
    )
    parser.add_argument("--timeout-s", default="900")
    parser.add_argument("--print-internal-debug", action="store_true")
    parser.add_argument("--resume", action="store_true")
    add_xyce_arguments(parser)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--require-monotonic", action="store_true")
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=root / "build" / "spice_pll_mapped_loop_gain_sweep",
    )
    args = parser.parse_args()
    args.mapped_verilog = Path(args.mapped_verilog).expanduser().resolve()
    args.pdk_root = Path(args.pdk_root).expanduser().resolve()
    args.bbpd_rcx_netlist = Path(args.bbpd_rcx_netlist).expanduser().resolve()
    args.dco_rcx_netlist = Path(args.dco_rcx_netlist).expanduser().resolve()
    args.build_dir = args.build_dir.expanduser().resolve()

    if args.ki < 0 or args.ki > 255:
        raise ValueError("--ki must be an 8-bit value")
    if args.ndiv < 2 or args.ndiv > 255:
        raise ValueError("--ndiv must be in 2..255")
    if args.jobs < 1:
        raise ValueError("--jobs must be positive")
    validate_xyce_arguments(args)
    case_names = parse_cases(args.cases)
    kp_values = parse_int_list(args.kp_values)
    combos = [(case_name, kp) for case_name in case_names for kp in kp_values]

    print(f"running {len(combos)} mapped-loop gain cases with jobs={args.jobs}", flush=True)
    all_rows = []
    if args.jobs == 1:
        for case_name, kp in combos:
            all_rows.extend(run_combo(root, args, case_name, kp))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
            future_map = {
                executor.submit(run_combo, root, args, case_name, kp): (case_name, kp)
                for case_name, kp in combos
            }
            for future in concurrent.futures.as_completed(future_map):
                all_rows.extend(future.result())

    all_rows.sort(
        key=lambda row: (
            row.get("case", ""),
            int(float(row.get("kp", -1))) if row.get("kp", "") != "" else -1,
        )
    )
    summary_rows = summarize(all_rows)

    detail_path = args.build_dir / "mapped_loop_gain_sweep.csv"
    summary_path = args.build_dir / "mapped_loop_gain_summary.csv"
    write_csv(detail_path, all_rows)
    write_csv(summary_path, summary_rows)

    for row in summary_rows:
        print(
            f"case={row['case']} kp={row['kp']} {row['status']} "
            f"code={row['start_code']}->{row['end_code']} "
            f"response={row['response_code']} delta={row['response_delta_code']} "
            f"mode={row['check_mode']}"
        )
    print(f"wrote {detail_path}")
    print(f"wrote {summary_path}")

    if args.require_monotonic:
        for case_name in case_names:
            case_rows = [row for row in summary_rows if row["case"] == case_name]
            deltas = [to_float(row["response_delta_code"]) for row in case_rows]
            if any(delta is None for delta in deltas):
                return 1
            if any(right < left for left, right in zip(deltas, deltas[1:])):
                return 1
            if any(row["status"] != "pass" for row in case_rows):
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
