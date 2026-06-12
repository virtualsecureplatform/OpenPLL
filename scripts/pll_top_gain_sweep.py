#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import re
import subprocess
import sys
from pathlib import Path


RESULT_RE = re.compile(
    r"^RESULT:\s+case=(?P<case>\S+)\s+pass=(?P<pass>[01])\s+"
    r"ki=(?P<ki>\d+)\s+kp=(?P<kp>\d+)\s+init_dlf=(?P<init_dlf>\d+)\s+"
    r"start_code=(?P<start_code>\d+)\s+final_code=(?P<final_code>\d+)\s+"
    r"target_code=(?P<target_code>\d+)\s+tol_code=(?P<tol_code>\d+)\s+"
    r"run_ns=(?P<run_ns>\d+)\s+lock_ns=(?P<lock_ns>-?\d+)\s+"
    r"min_abs_error_code=(?P<min_abs_error_code>\d+)\s+"
    r"ref_mhz=(?P<ref_mhz>[-+0-9.]+)\s+mmd_ratio=(?P<mmd_ratio>\d+)\s+"
    r"pllo_edges=(?P<pllo_edges>\d+)\s+clkdiv_edges=(?P<clkdiv_edges>\d+)\s+"
    r"bbpd_inc=(?P<bbpd_inc>\d+)\s+bbpd_dec=(?P<bbpd_dec>\d+)\s+"
    r"bbpd_idle=(?P<bbpd_idle>\d+)"
)


FILLED_DCO_DEFAULTS = {
    "ref_half_ps": 80382,
    "mmd_ratio": 8,
    "target_code": 128,
    "tol_code": 16,
    "run_ns": 220000,
    "f0_mhz": 46.25672588520797,
    "f64_mhz": 47.95039109460694,
    "f128_mhz": 49.762117807733404,
    "f192_mhz": 51.61843654151962,
    "f255_mhz": 52.34983089216307,
}


def parse_ints(text):
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


def compile_testbench(root, build_dir, args):
    output = build_dir / "tb_pll_top_acq_model.vvp"
    cmd = [
        "iverilog",
        "-g2012",
        "-Wall",
        f"-Ptb_pll_top_acq_model.DLF_FRAC_WIDTH={args.dlf_frac_width}",
        f"-Ptb_pll_top_acq_model.DLF_ACQ_BOOST_SHIFT={args.dlf_acq_boost_shift}",
        f"-Ptb_pll_top_acq_model.DLF_ACQ_BOOST_AFTER={args.dlf_acq_boost_after}",
        f"-Ptb_pll_top_acq_model.DLF_ACQ_RAIL_BOOST={int(args.dlf_acq_rail_boost)}",
        f"-Ptb_pll_top_acq_model.DLF_ACQ_FORCE_RAIL_CODE={args.dlf_acq_force_rail_code}",
        f"-Ptb_pll_top_acq_model.DLF_UPDATE_ON_PLLOUT={int(args.dlf_update_on_pllout)}",
        f"-Ptb_pll_top_acq_model.DLF_PROP_RAIL_GUARD={int(args.dlf_prop_rail_guard)}",
        f"-Ptb_pll_top_acq_model.DCO_COARSE_BITS={args.dco_coarse_bits}",
        "-o",
        str(output),
        str(root / "rtl" / "IntegerPLL_B2TH.v"),
        str(root / "rtl" / "IntegerPLL_MMD_Retimer.v"),
        str(root / "rtl" / "IntegerPLL_Divider.v"),
        str(root / "rtl" / "IntegerPLL_DLF.v"),
        str(root / "rtl" / "IntegerPLL_DigitalCore.v"),
        str(root / "rtl" / "IntegerPLL_Top.v"),
        str(root / "models" / "IntegerPLL_BBPD_model.v"),
        str(root / "models" / "IntegerPLL_DCO_model.v"),
        str(root / "tb" / "tb_pll_top_acq_model.v"),
    ]
    subprocess.run(cmd, check=True)
    return output


def run_combo(vvp_path, args, ki, kp):
    cmd = [
        "vvp",
        str(vvp_path),
        f"+KI={ki}",
        f"+KP={kp}",
        f"+RUN_NS={args.run_ns}",
        f"+TARGET_CODE={args.target_code}",
        f"+TOL_CODE={args.tol_code}",
        f"+LOW_INIT={args.low_init}",
        f"+HIGH_INIT={args.high_init}",
        f"+MMD_RATIO={args.mmd_ratio}",
        f"+REF_HALF_PS={args.ref_half_ps}",
        f"+COARSE_CODE={args.coarse_code}",
        "+DCO_USE_PIECEWISE5=1",
        f"+DCO_F0_MHZ={args.f0_mhz}",
        f"+DCO_F64_MHZ={args.f64_mhz}",
        f"+DCO_F128_MHZ={args.f128_mhz}",
        f"+DCO_F192_MHZ={args.f192_mhz}",
        f"+DCO_F255_MHZ={args.f255_mhz}",
        f"+DCO_COARSE_STEP_MHZ={args.dco_coarse_step_mhz}",
        "+ALLOW_FAIL=1",
    ]
    timed_out = False
    try:
        proc = subprocess.run(
            cmd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=args.timeout_s,
            check=False,
        )
        output = proc.stdout
        returncode = proc.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        output = exc.stdout or ""
        returncode = -9
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        output += f"\nOpenPLL timeout: PLL top gain sweep killed KI={ki} KP={kp} after {args.timeout_s:.1f} s\n"

    rows = []
    for line in output.splitlines():
        match = RESULT_RE.match(line.strip())
        if not match:
            continue
        row = match.groupdict()
        int_fields = (
            "pass",
            "ki",
            "kp",
            "init_dlf",
            "start_code",
            "final_code",
            "target_code",
            "tol_code",
            "run_ns",
            "lock_ns",
            "min_abs_error_code",
            "mmd_ratio",
            "pllo_edges",
            "clkdiv_edges",
            "bbpd_inc",
            "bbpd_dec",
            "bbpd_idle",
        )
        for field in int_fields:
            row[field] = int(row[field])
        row["dlf_frac_width"] = args.dlf_frac_width
        row["dlf_acq_boost_shift"] = args.dlf_acq_boost_shift
        row["dlf_acq_boost_after"] = args.dlf_acq_boost_after
        row["dlf_acq_rail_boost"] = int(args.dlf_acq_rail_boost)
        row["dlf_acq_force_rail_code"] = args.dlf_acq_force_rail_code
        row["dlf_update_on_pllout"] = int(args.dlf_update_on_pllout)
        row["dlf_prop_rail_guard"] = int(args.dlf_prop_rail_guard)
        row["dco_coarse_bits"] = args.dco_coarse_bits
        row["coarse_code"] = args.coarse_code
        row["dco_coarse_step_mhz"] = args.dco_coarse_step_mhz
        row["ref_mhz"] = float(row["ref_mhz"])
        row["abs_error_code"] = abs(row["final_code"] - row["target_code"])
        row["returncode"] = returncode
        row["timed_out"] = int(timed_out)
        rows.append(row)

    if len(rows) != 2:
        for case_name in ("low-start", "high-start"):
            if not any(row.get("case") == case_name for row in rows):
                rows.append(
                    {
                        "case": case_name,
                        "pass": 0,
                        "ki": ki,
                        "kp": kp,
                        "dlf_frac_width": args.dlf_frac_width,
                        "dlf_acq_boost_shift": args.dlf_acq_boost_shift,
                        "dlf_acq_boost_after": args.dlf_acq_boost_after,
                        "dlf_acq_rail_boost": int(args.dlf_acq_rail_boost),
                        "dlf_acq_force_rail_code": args.dlf_acq_force_rail_code,
                        "dlf_update_on_pllout": int(args.dlf_update_on_pllout),
                        "dlf_prop_rail_guard": int(args.dlf_prop_rail_guard),
                        "dco_coarse_bits": args.dco_coarse_bits,
                        "coarse_code": args.coarse_code,
                        "dco_coarse_step_mhz": args.dco_coarse_step_mhz,
                        "init_dlf": "",
                        "start_code": "",
                        "final_code": "",
                        "target_code": args.target_code,
                        "tol_code": args.tol_code,
                        "run_ns": args.run_ns,
                        "lock_ns": "",
                        "min_abs_error_code": "",
                        "ref_mhz": "",
                        "mmd_ratio": args.mmd_ratio,
                        "pllo_edges": "",
                        "clkdiv_edges": "",
                        "bbpd_inc": "",
                        "bbpd_dec": "",
                        "bbpd_idle": "",
                        "abs_error_code": "",
                        "returncode": returncode,
                        "timed_out": int(timed_out),
                    }
                )
    return rows, output


def summarize(rows):
    combos = {}
    for row in rows:
        key = (
            row["dlf_frac_width"],
            row["dlf_acq_rail_boost"],
            row["dlf_acq_force_rail_code"],
            row["dlf_update_on_pllout"],
            row["dlf_prop_rail_guard"],
            row["dco_coarse_bits"],
            row["coarse_code"],
            row["dco_coarse_step_mhz"],
            row["ki"],
            row["kp"],
        )
        combo = combos.setdefault(
            key,
            {
                "dlf_frac_width": row["dlf_frac_width"],
                "dlf_acq_boost_shift": row["dlf_acq_boost_shift"],
                "dlf_acq_boost_after": row["dlf_acq_boost_after"],
                "dlf_acq_rail_boost": row["dlf_acq_rail_boost"],
                "dlf_acq_force_rail_code": row["dlf_acq_force_rail_code"],
                "dlf_update_on_pllout": row["dlf_update_on_pllout"],
                "dlf_prop_rail_guard": row["dlf_prop_rail_guard"],
                "dco_coarse_bits": row["dco_coarse_bits"],
                "coarse_code": row["coarse_code"],
                "dco_coarse_step_mhz": row["dco_coarse_step_mhz"],
                "ki": row["ki"],
                "kp": row["kp"],
                "low_pass": 0,
                "high_pass": 0,
                "low_final_code": "",
                "high_final_code": "",
                "low_lock_ns": "",
                "high_lock_ns": "",
                "low_min_abs_error_code": "",
                "high_min_abs_error_code": "",
                "max_lock_ns": "",
                "max_abs_error_code": 999999,
                "total_bbpd_inc": 0,
                "total_bbpd_dec": 0,
                "total_bbpd_idle": 0,
            },
        )
        if row["case"] == "low-start":
            prefix = "low"
        elif row["case"] == "high-start":
            prefix = "high"
        else:
            continue

        combo[f"{prefix}_pass"] = row["pass"]
        combo[f"{prefix}_final_code"] = row["final_code"]
        combo[f"{prefix}_lock_ns"] = row["lock_ns"]
        combo[f"{prefix}_min_abs_error_code"] = row["min_abs_error_code"]
        if row["lock_ns"] != "" and row["lock_ns"] >= 0:
            combo["max_lock_ns"] = max(
                0 if combo["max_lock_ns"] == "" else combo["max_lock_ns"],
                row["lock_ns"],
            )
        if row["abs_error_code"] != "":
            combo["max_abs_error_code"] = max(
                0 if combo["max_abs_error_code"] == 999999 else combo["max_abs_error_code"],
                row["abs_error_code"],
            )
        for field in ("bbpd_inc", "bbpd_dec", "bbpd_idle"):
            if row[field] != "":
                combo[f"total_{field}"] += row[field]

    summary = []
    for combo in combos.values():
        combo["pass_both"] = int(combo["low_pass"] and combo["high_pass"])
        if combo["max_abs_error_code"] == 999999:
            combo["max_abs_error_code"] = ""
        summary.append(combo)
    summary.sort(
        key=lambda row: (
            -row["pass_both"],
            row["max_abs_error_code"] if row["max_abs_error_code"] != "" else 999999,
            row["max_lock_ns"] if row["max_lock_ns"] != "" else 999999999,
            row["ki"],
            row["kp"],
        )
    )
    return summary


def write_csv(path, rows, fieldnames):
    with path.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Sweep top-level RTL PLL behavioral acquisition gain settings."
    )
    parser.add_argument("--ki-values", default="255")
    parser.add_argument("--kp-values", default="4,8,16,32")
    parser.add_argument("--dlf-frac-width", type=int, default=8)
    parser.add_argument("--dlf-acq-boost-shift", type=int, default=0)
    parser.add_argument("--dlf-acq-boost-after", type=int, default=3)
    parser.add_argument(
        "--dlf-acq-rail-boost",
        action="store_true",
        help="Apply the acquisition boost immediately while the filter is in a DCO rail-escape region.",
    )
    parser.add_argument(
        "--dlf-acq-force-rail-code",
        type=int,
        default=0,
        help="Force inward acquisition while the 8-bit DCO code is within this many codes of either rail.",
    )
    parser.add_argument(
        "--dlf-update-on-pllout",
        action="store_true",
        help="Clock the loop filter from PLLOUT and advance it on sampled divider-update pulses.",
    )
    parser.add_argument(
        "--dlf-prop-rail-guard",
        action="store_true",
        help="Invert outward BBPD decisions when the proportional term would drive the exported DCO code to rail.",
    )
    parser.add_argument(
        "--dco-coarse-bits",
        type=int,
        default=0,
        help="Legacy packed mode: number of high DCO_CODE bits supplied by COARSEBINARY_CODE; use 0 for full-width fine control.",
    )
    parser.add_argument(
        "--coarse-code",
        type=int,
        default=5,
        help="Independent COARSEBINARY_CODE value used by coarse-band behavioral runs.",
    )
    parser.add_argument(
        "--dco-coarse-step-mhz",
        type=float,
        default=0.0,
        help="Frequency offset per independent COARSEBINARY_CODE step in the behavioral DCO model.",
    )
    parser.add_argument("--target-code", type=int, default=FILLED_DCO_DEFAULTS["target_code"])
    parser.add_argument("--tol-code", type=int, default=FILLED_DCO_DEFAULTS["tol_code"])
    parser.add_argument("--run-ns", type=int, default=FILLED_DCO_DEFAULTS["run_ns"])
    parser.add_argument("--timeout-s", type=float, default=60.0)
    parser.add_argument("--low-init", type=int, default=0)
    parser.add_argument("--high-init", type=int, default=1020)
    parser.add_argument("--mmd-ratio", type=int, default=FILLED_DCO_DEFAULTS["mmd_ratio"])
    parser.add_argument("--ref-half-ps", type=int, default=FILLED_DCO_DEFAULTS["ref_half_ps"])
    parser.add_argument("--f0-mhz", type=float, default=FILLED_DCO_DEFAULTS["f0_mhz"])
    parser.add_argument("--f64-mhz", type=float, default=FILLED_DCO_DEFAULTS["f64_mhz"])
    parser.add_argument("--f128-mhz", type=float, default=FILLED_DCO_DEFAULTS["f128_mhz"])
    parser.add_argument("--f192-mhz", type=float, default=FILLED_DCO_DEFAULTS["f192_mhz"])
    parser.add_argument("--f255-mhz", type=float, default=FILLED_DCO_DEFAULTS["f255_mhz"])
    parser.add_argument(
        "--build-dir",
        default=str(Path(__file__).resolve().parents[1] / "build" / "pll_top_filled_dco_gain_sweep"),
    )
    args = parser.parse_args()
    if args.dlf_frac_width < 0 or args.dlf_frac_width > 12:
        raise ValueError("--dlf-frac-width must be in 0..12")
    if args.dlf_acq_boost_shift < 0 or args.dlf_acq_boost_shift > 8:
        raise ValueError("--dlf-acq-boost-shift must be in 0..8")
    if args.dlf_acq_boost_after < 1 or args.dlf_acq_boost_after > 15:
        raise ValueError("--dlf-acq-boost-after must be in 1..15")
    if args.dlf_acq_force_rail_code < 0 or args.dlf_acq_force_rail_code > 127:
        raise ValueError("--dlf-acq-force-rail-code must be in 0..127")
    if args.dco_coarse_bits < 0 or args.dco_coarse_bits > 4:
        raise ValueError("--dco-coarse-bits must be in 0..4")
    if args.coarse_code < 0 or args.coarse_code > 15:
        raise ValueError("--coarse-code must be in 0..15")
    if args.dco_coarse_step_mhz < 0.0:
        raise ValueError("--dco-coarse-step-mhz must be non-negative")

    root = Path(__file__).resolve().parents[1]
    build_dir = Path(args.build_dir).expanduser().resolve()
    build_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = build_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    vvp_path = compile_testbench(root, build_dir, args)

    all_rows = []
    for ki in parse_ints(args.ki_values):
        for kp in parse_ints(args.kp_values):
            rows, log_text = run_combo(vvp_path, args, ki, kp)
            (logs_dir / f"ki{ki}_kp{kp}.log").write_text(log_text, encoding="utf-8")
            all_rows.extend(rows)

    summary = summarize(all_rows)
    rows_path = build_dir / "pll_top_gain_sweep.csv"
    summary_path = build_dir / "pll_top_gain_summary.csv"
    write_csv(
        rows_path,
        all_rows,
        [
            "case",
            "pass",
            "ki",
            "kp",
            "dlf_frac_width",
            "dlf_acq_boost_shift",
            "dlf_acq_boost_after",
            "dlf_acq_rail_boost",
            "dlf_acq_force_rail_code",
            "dlf_update_on_pllout",
            "dlf_prop_rail_guard",
            "dco_coarse_bits",
            "coarse_code",
            "dco_coarse_step_mhz",
            "init_dlf",
            "start_code",
            "final_code",
            "target_code",
            "tol_code",
            "run_ns",
            "lock_ns",
            "min_abs_error_code",
            "ref_mhz",
            "mmd_ratio",
            "pllo_edges",
            "clkdiv_edges",
            "bbpd_inc",
            "bbpd_dec",
            "bbpd_idle",
            "abs_error_code",
            "returncode",
            "timed_out",
        ],
    )
    write_csv(
        summary_path,
        summary,
        [
            "ki",
            "kp",
            "dlf_frac_width",
            "dlf_acq_boost_shift",
            "dlf_acq_boost_after",
            "dlf_acq_rail_boost",
            "dlf_acq_force_rail_code",
            "dlf_update_on_pllout",
            "dlf_prop_rail_guard",
            "dco_coarse_bits",
            "coarse_code",
            "dco_coarse_step_mhz",
            "low_pass",
            "high_pass",
            "pass_both",
            "low_final_code",
            "high_final_code",
            "low_lock_ns",
            "high_lock_ns",
            "low_min_abs_error_code",
            "high_min_abs_error_code",
            "max_lock_ns",
            "max_abs_error_code",
            "total_bbpd_inc",
            "total_bbpd_dec",
            "total_bbpd_idle",
        ],
    )

    for row in summary:
        print(
            f"KI={row['ki']} KP={row['kp']} pass_both={row['pass_both']} "
            f"final={row['low_final_code']}/{row['high_final_code']} "
            f"lock_ns={row['low_lock_ns']}/{row['high_lock_ns']} "
            f"max_abs_error={row['max_abs_error_code']}"
        )
    print(f"wrote {rows_path}")
    print(f"wrote {summary_path}")

    if not any(row["pass_both"] for row in summary):
        print("no top-level RTL gain setting passed both rails", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
