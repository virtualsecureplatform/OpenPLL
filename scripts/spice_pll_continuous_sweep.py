#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import concurrent.futures
import csv
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
    "ref_mhz": 9.95242356154668,
    "ndiv": 5,
}


def parse_float_list(text):
    values = []
    for item in text.split(","):
        item = item.strip()
        if item:
            values.append(float(item))
    if not values:
        raise ValueError("empty float list")
    return values


def value_slug(value):
    text = f"{value:g}"
    return text.replace("-", "m").replace(".", "p")


def read_csv(path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="ascii") as csv_file:
        return list(csv.DictReader(csv_file))


def to_float(value):
    if value in ("", None):
        return None
    return float(value)


def run_combo(root, args, code_slew, clock_sharpness, loop_sign, initial_phase):
    combo_name = (
        f"slew{value_slug(code_slew)}_"
        f"sharp{value_slug(clock_sharpness)}_"
        f"sign{value_slug(loop_sign)}_"
        f"phase{value_slug(initial_phase)}"
    )
    combo_dir = args.build_dir / combo_name
    combo_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = combo_dir / "sweep_stdout.log"

    cmd = [
        sys.executable,
        str(root / "scripts" / "spice_pll_loop_check.py"),
        "--loop-model",
        "continuous",
        "--dco-model",
        "piecewise5",
        "--corner",
        args.corner,
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
        "--ref-mhz",
        str(args.ref_mhz),
        "--ndiv",
        str(args.ndiv),
        "--code-slew-lsb-per-us",
        str(code_slew),
        "--loop-current-sign",
        str(loop_sign),
        "--clock-sharpness",
        str(clock_sharpness),
        "--initial-dco-phase-cycles",
        str(initial_phase),
        "--sim-time-us",
        str(args.sim_time_us),
        "--step-ps",
        str(args.step_ps),
        "--max-step-ps",
        str(args.max_step_ps),
        "--timeout-s",
        str(args.timeout_s),
        "--lock-tolerance-mhz",
        str(args.lock_tolerance_mhz),
        "--code-tolerance",
        str(args.code_tolerance),
        "--min-code-motion",
        str(args.min_code_motion),
        "--simulator",
        args.simulator,
        "--ngspice",
        args.ngspice,
        "--xyce",
        args.xyce,
        "--xyce-mpi-procs",
        str(args.xyce_mpi_procs),
        "--xyce-mpi-launcher",
        args.xyce_mpi_launcher,
        "--ngspice-threads",
        str(args.ngspice_threads),
        "--build-dir",
        str(combo_dir),
    ]
    if args.bbpd_impl:
        cmd.extend(["--bbpd-impl", args.bbpd_impl])
    if args.bbpd_rcx_netlist:
        cmd.extend(["--bbpd-rcx-netlist", str(args.bbpd_rcx_netlist)])
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

    rows = read_csv(combo_dir / "pll_loop_check.csv")
    for row in rows:
        row["sweep_combo"] = combo_name
        row["sweep_returncode"] = proc.returncode
        row["sweep_stdout_log"] = str(stdout_path)
        row["sweep_build_dir"] = str(combo_dir)

    if not rows:
        rows.append(
            {
                "corner": args.corner,
                "case": "missing_csv",
                "status": "fail",
                "simulator": args.simulator,
                "xyce_mpi_procs": args.xyce_mpi_procs if args.simulator == "xyce" else "",
                "bbpd_impl": args.bbpd_impl,
                "loop_model": "continuous",
                "code_slew_lsb_per_us": code_slew,
                "loop_current_sign": loop_sign,
                "clock_sharpness": clock_sharpness,
                "max_step_ps": args.max_step_ps,
                "initial_dco_phase_cycles": initial_phase,
                "ref_mhz": args.ref_mhz,
                "ndiv": args.ndiv,
                "sweep_combo": combo_name,
                "sweep_returncode": proc.returncode,
                "sweep_stdout_log": str(stdout_path),
                "sweep_build_dir": str(combo_dir),
            }
        )
    return rows


def summarize(rows):
    combos = {}
    for row in rows:
        combo_name = row["sweep_combo"]
        combo = combos.setdefault(
            combo_name,
            {
                "sweep_combo": combo_name,
                "code_slew_lsb_per_us": row.get("code_slew_lsb_per_us", ""),
                "loop_current_sign": row.get("loop_current_sign", ""),
                "clock_sharpness": row.get("clock_sharpness", ""),
                "max_step_ps": row.get("max_step_ps", ""),
                "initial_dco_phase_cycles": row.get("initial_dco_phase_cycles", ""),
                "simulator": row.get("simulator", ""),
                "bbpd_impl": row.get("bbpd_impl", ""),
                "low_status": "missing",
                "high_status": "missing",
                "low_end_code": "",
                "high_end_code": "",
                "low_freq_avg_mhz": "",
                "high_freq_avg_mhz": "",
                "low_ferr_avg_mhz": "",
                "high_ferr_avg_mhz": "",
                "target_code": row.get("target_code", ""),
                "pass_both": 0,
                "max_abs_ferr_avg_mhz": "",
            },
        )
        if row.get("case") == "low_start":
            prefix = "low"
        elif row.get("case") == "high_start":
            prefix = "high"
        else:
            continue
        combo[f"{prefix}_status"] = row.get("status", "")
        combo[f"{prefix}_end_code"] = row.get("code_end", "")
        combo[f"{prefix}_freq_avg_mhz"] = row.get("freq_avg_mhz", "")
        combo[f"{prefix}_ferr_avg_mhz"] = row.get("ferr_avg_mhz", "")
        if not combo["target_code"]:
            combo["target_code"] = row.get("target_code", "")

    for combo in combos.values():
        combo["pass_both"] = int(combo["low_status"] == "pass" and combo["high_status"] == "pass")
        ferr_values = [
            abs(value)
            for value in (
                to_float(combo["low_ferr_avg_mhz"]),
                to_float(combo["high_ferr_avg_mhz"]),
            )
            if value is not None
        ]
        if ferr_values:
            combo["max_abs_ferr_avg_mhz"] = max(ferr_values)

    return sorted(
        combos.values(),
        key=lambda row: (
            -int(row["pass_both"]),
            row["max_abs_ferr_avg_mhz"] if row["max_abs_ferr_avg_mhz"] != "" else 1e99,
            float(row["code_slew_lsb_per_us"]),
            float(row["clock_sharpness"]),
            float(row["initial_dco_phase_cycles"]),
        ),
    )


def write_csv(path, rows, fieldnames=None):
    if fieldnames is None:
        names = []
        for row in rows:
            for key in row:
                if key not in names:
                    names.append(key)
        fieldnames = names
    with path.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Sweep continuous PLL-loop SPICE surrogate gain and phase settings."
    )
    parser.add_argument("--code-slew-lsb-per-us-values", default="16,24")
    parser.add_argument("--clock-sharpness-values", default="500")
    parser.add_argument("--loop-current-sign-values", default="1")
    parser.add_argument("--initial-dco-phase-cycles-values", default="0")
    parser.add_argument("--sim-time-us", type=float, default=40.0)
    parser.add_argument("--step-ps", type=float, default=100.0)
    parser.add_argument("--max-step-ps", type=float, default=0.0)
    parser.add_argument("--timeout-s", default="120")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--simulator", choices=("ngspice", "xyce"), default="xyce")
    parser.add_argument("--ngspice", default="ngspice")
    add_xyce_arguments(parser, default="Xyce")
    parser.add_argument("--ngspice-threads", type=int, default=0)
    parser.add_argument("--bbpd-impl", choices=("stdcell", "postlayout"), default="postlayout")
    parser.add_argument(
        "--bbpd-rcx-netlist",
        default="openlane/IntegerPLL_BBPD/runs/librelane_signoff/rcx-magic/IntegerPLL_BBPD.rcx.spice",
    )
    parser.add_argument("--lock-tolerance-mhz", type=float, default=0.75)
    parser.add_argument("--code-tolerance", type=float, default=32.0)
    parser.add_argument("--min-code-motion", type=float, default=16.0)
    parser.add_argument("--corner", default="tt")
    parser.add_argument("--f0-mhz", type=float, default=FILLED_DCO_DEFAULTS["f0_mhz"])
    parser.add_argument("--f64-mhz", type=float, default=FILLED_DCO_DEFAULTS["f64_mhz"])
    parser.add_argument("--f128-mhz", type=float, default=FILLED_DCO_DEFAULTS["f128_mhz"])
    parser.add_argument("--f192-mhz", type=float, default=FILLED_DCO_DEFAULTS["f192_mhz"])
    parser.add_argument("--f255-mhz", type=float, default=FILLED_DCO_DEFAULTS["f255_mhz"])
    parser.add_argument("--ref-mhz", type=float, default=FILLED_DCO_DEFAULTS["ref_mhz"])
    parser.add_argument("--ndiv", type=int, default=FILLED_DCO_DEFAULTS["ndiv"])
    parser.add_argument(
        "--build-dir",
        default=str(Path(__file__).resolve().parents[1] / "build" / "spice_pll_continuous_sweep"),
    )
    parser.add_argument(
        "--require-pass",
        action="store_true",
        help="Exit nonzero unless at least one parameter combination passes both rails.",
    )
    args = parser.parse_args()

    if args.jobs < 1:
        raise ValueError("--jobs must be at least 1")
    if args.ngspice_threads < 0:
        raise ValueError("--ngspice-threads must be non-negative")
    validate_xyce_arguments(args)
    if args.max_step_ps < 0:
        raise ValueError("--max-step-ps must be non-negative")

    root = Path(__file__).resolve().parents[1]
    args.build_dir = Path(args.build_dir).expanduser().resolve()
    args.bbpd_rcx_netlist = Path(args.bbpd_rcx_netlist).expanduser()
    args.build_dir.mkdir(parents=True, exist_ok=True)

    combos = [
        (code_slew, clock_sharpness, loop_sign, initial_phase)
        for code_slew in parse_float_list(args.code_slew_lsb_per_us_values)
        for clock_sharpness in parse_float_list(args.clock_sharpness_values)
        for loop_sign in parse_float_list(args.loop_current_sign_values)
        for initial_phase in parse_float_list(args.initial_dco_phase_cycles_values)
    ]

    all_rows = []
    if args.jobs == 1:
        for combo in combos:
            all_rows.extend(run_combo(root, args, *combo))
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
            futures = [executor.submit(run_combo, root, args, *combo) for combo in combos]
            for future in concurrent.futures.as_completed(futures):
                all_rows.extend(future.result())

    summary = summarize(all_rows)
    rows_path = args.build_dir / "continuous_sweep.csv"
    summary_path = args.build_dir / "continuous_summary.csv"
    write_csv(rows_path, all_rows)
    write_csv(
        summary_path,
        summary,
        [
            "sweep_combo",
            "code_slew_lsb_per_us",
            "loop_current_sign",
            "clock_sharpness",
            "max_step_ps",
            "initial_dco_phase_cycles",
            "simulator",
            "bbpd_impl",
            "low_status",
            "high_status",
            "low_end_code",
            "high_end_code",
            "low_freq_avg_mhz",
            "high_freq_avg_mhz",
            "low_ferr_avg_mhz",
            "high_ferr_avg_mhz",
            "target_code",
            "pass_both",
            "max_abs_ferr_avg_mhz",
        ],
    )

    for row in summary:
        print(
            f"slew={row['code_slew_lsb_per_us']} "
            f"sharp={row['clock_sharpness']} "
            f"sign={row['loop_current_sign']} "
            f"phase={row['initial_dco_phase_cycles']} "
            f"pass_both={row['pass_both']} "
            f"low={row['low_status']}:{row['low_end_code']} "
            f"high={row['high_status']}:{row['high_end_code']} "
            f"max_abs_ferr_mhz={row['max_abs_ferr_avg_mhz']}"
        )
    print(f"wrote {rows_path}")
    print(f"wrote {summary_path}")

    if args.require_pass and not any(row["pass_both"] for row in summary):
        print("no continuous-loop gain setting passed both rails", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
