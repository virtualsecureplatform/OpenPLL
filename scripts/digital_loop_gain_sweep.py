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
    r"min_abs_error_code=(?P<min_abs_error_code>\d+)\s+ref_mhz=(?P<ref_mhz>[-+0-9.]+)"
)


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
    output = build_dir / "tb_digital_loop_acq.vvp"
    cmd = [
        "iverilog",
        "-g2012",
        "-Wall",
        f"-Ptb_digital_loop_acq.DLF_FRAC_WIDTH={args.dlf_frac_width}",
        f"-Ptb_digital_loop_acq.DLF_ACQ_BOOST_SHIFT={args.dlf_acq_boost_shift}",
        f"-Ptb_digital_loop_acq.DLF_ACQ_BOOST_AFTER={args.dlf_acq_boost_after}",
        f"-Ptb_digital_loop_acq.DLF_ACQ_RAIL_BOOST={int(args.dlf_acq_rail_boost)}",
        f"-Ptb_digital_loop_acq.DLF_ACQ_FORCE_RAIL_CODE={args.dlf_acq_force_rail_code}",
        f"-Ptb_digital_loop_acq.DLF_UPDATE_ON_PLLOUT={int(args.dlf_update_on_pllout)}",
        f"-Ptb_digital_loop_acq.DLF_PROP_RAIL_GUARD={int(args.dlf_prop_rail_guard)}",
        "-o",
        str(output),
        str(root / "rtl" / "IntegerPLL_B2TH.v"),
        str(root / "rtl" / "IntegerPLL_MMD_Retimer.v"),
        str(root / "rtl" / "IntegerPLL_Divider.v"),
        str(root / "rtl" / "IntegerPLL_DLF.v"),
        str(root / "rtl" / "IntegerPLL_DigitalCore.v"),
        str(root / "tb" / "tb_digital_loop_acq.v"),
    ]
    subprocess.run(cmd, check=True)
    return output


def run_combo(vvp_path, args, ki, kp):
    cmd = [
        "vvp",
        str(vvp_path),
        f"+KI={ki}",
        f"+KP={kp}",
        f"+TARGET_CODE={args.target_code}",
        f"+TOL_CODE={args.tol_code}",
        f"+RUN_NS={args.run_ns}",
        f"+LOW_INIT={args.low_init}",
        f"+HIGH_INIT={args.high_init}",
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
        output += f"\nOpenPLL timeout: digital gain sweep killed KI={ki} KP={kp} after {args.timeout_s:.1f} s\n"

    rows = []
    for line in output.splitlines():
        match = RESULT_RE.match(line.strip())
        if not match:
            continue
        row = match.groupdict()
        row.update(
            {
                "ki": int(row["ki"]),
                "kp": int(row["kp"]),
                "dlf_frac_width": args.dlf_frac_width,
                "dlf_acq_boost_shift": args.dlf_acq_boost_shift,
                "dlf_acq_boost_after": args.dlf_acq_boost_after,
                "dlf_acq_rail_boost": int(args.dlf_acq_rail_boost),
                "dlf_acq_force_rail_code": args.dlf_acq_force_rail_code,
                "dlf_update_on_pllout": int(args.dlf_update_on_pllout),
                "dlf_prop_rail_guard": int(args.dlf_prop_rail_guard),
                "pass": int(row["pass"]),
                "init_dlf": int(row["init_dlf"]),
                "start_code": int(row["start_code"]),
                "final_code": int(row["final_code"]),
                "target_code": int(row["target_code"]),
                "tol_code": int(row["tol_code"]),
                "run_ns": int(row["run_ns"]),
                "lock_ns": int(row["lock_ns"]),
                "min_abs_error_code": int(row["min_abs_error_code"]),
                "ref_mhz": float(row["ref_mhz"]),
                "abs_error_code": abs(int(row["final_code"]) - int(row["target_code"])),
                "returncode": returncode,
                "timed_out": int(timed_out),
            }
        )
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
                        "init_dlf": "",
                        "start_code": "",
                        "final_code": "",
                        "target_code": args.target_code,
                        "tol_code": args.tol_code,
                        "run_ns": args.run_ns,
                        "lock_ns": "",
                        "min_abs_error_code": "",
                        "ref_mhz": "",
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
                "ki": row["ki"],
                "kp": row["kp"],
                "low_pass": 0,
                "high_pass": 0,
                "low_final_code": "",
                "high_final_code": "",
                "low_lock_ns": "",
                "high_lock_ns": "",
                "max_lock_ns": "",
                "max_abs_error_code": 999999,
            },
        )
        if row["case"] == "low-start":
            combo["low_pass"] = row["pass"]
            combo["low_final_code"] = row["final_code"]
            combo["low_lock_ns"] = row["lock_ns"]
        elif row["case"] == "high-start":
            combo["high_pass"] = row["pass"]
            combo["high_final_code"] = row["final_code"]
            combo["high_lock_ns"] = row["lock_ns"]
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

    summary = []
    for combo in combos.values():
        combo["pass_both"] = int(combo["low_pass"] and combo["high_pass"])
        if combo["max_abs_error_code"] == 999999:
            combo["max_abs_error_code"] = ""
        summary.append(combo)
    summary.sort(key=lambda row: (row["ki"], row["kp"]))
    return summary


def write_csv(path, rows, fieldnames):
    with path.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Sweep real RTL DLF_KI/KP acquisition settings.")
    parser.add_argument("--ki-values", default="64,96,128,192,255")
    parser.add_argument("--kp-values", default="0,1,2,4,8,16,32")
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
    parser.add_argument("--target-code", type=int, default=128)
    parser.add_argument("--tol-code", type=int, default=32)
    parser.add_argument("--run-ns", type=int, default=200000)
    parser.add_argument("--timeout-s", type=float, default=60.0)
    parser.add_argument("--low-init", type=int, default=0)
    parser.add_argument("--high-init", type=int, default=1020)
    parser.add_argument(
        "--build-dir",
        default=str(Path(__file__).resolve().parents[1] / "build" / "digital_loop_gain_sweep"),
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    build_dir = Path(args.build_dir).expanduser().resolve()
    build_dir.mkdir(parents=True, exist_ok=True)
    if args.dlf_frac_width < 0 or args.dlf_frac_width > 12:
        raise ValueError("--dlf-frac-width must be in 0..12")
    if args.dlf_acq_boost_shift < 0 or args.dlf_acq_boost_shift > 8:
        raise ValueError("--dlf-acq-boost-shift must be in 0..8")
    if args.dlf_acq_boost_after < 1 or args.dlf_acq_boost_after > 15:
        raise ValueError("--dlf-acq-boost-after must be in 1..15")
    if args.dlf_acq_force_rail_code < 0 or args.dlf_acq_force_rail_code > 127:
        raise ValueError("--dlf-acq-force-rail-code must be in 0..127")

    vvp_path = compile_testbench(root, build_dir, args)

    all_rows = []
    logs_dir = build_dir / "logs"
    logs_dir.mkdir(exist_ok=True)
    for ki in parse_ints(args.ki_values):
        for kp in parse_ints(args.kp_values):
            rows, log_text = run_combo(vvp_path, args, ki, kp)
            (logs_dir / f"ki{ki}_kp{kp}.log").write_text(log_text, encoding="utf-8")
            all_rows.extend(rows)

    summary = summarize(all_rows)
    rows_path = build_dir / "digital_loop_gain_sweep.csv"
    summary_path = build_dir / "digital_loop_gain_summary.csv"
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
            "init_dlf",
            "start_code",
            "final_code",
            "target_code",
            "tol_code",
            "run_ns",
            "lock_ns",
            "min_abs_error_code",
            "ref_mhz",
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
            "low_pass",
            "high_pass",
            "pass_both",
            "low_final_code",
            "high_final_code",
            "low_lock_ns",
            "high_lock_ns",
            "max_lock_ns",
            "max_abs_error_code",
        ],
    )

    passing = [row for row in summary if row["pass_both"]]
    if passing:
        exact = [row for row in passing if row["max_abs_error_code"] == 0]
        recommended_pool = exact if exact else passing
        recommended = min(
            recommended_pool,
            key=lambda row: (
                row["max_lock_ns"] if row["max_lock_ns"] != "" else 999999999,
                row["max_abs_error_code"],
                row["ki"] + row["kp"],
                row["ki"],
                row["kp"],
            ),
        )
        fastest = min(
            passing,
            key=lambda row: (
                row["max_lock_ns"] if row["max_lock_ns"] != "" else 999999999,
                row["max_abs_error_code"],
                row["ki"] + row["kp"],
                row["ki"],
                row["kp"],
            ),
        )
        lowest_gain = min(
            passing,
            key=lambda row: (
                row["ki"] + row["kp"],
                row["max_lock_ns"] if row["max_lock_ns"] != "" else 999999999,
                row["max_abs_error_code"],
                row["ki"],
                row["kp"],
            ),
        )
        print(
            f"recommended DLF_KI={recommended['ki']} DLF_KP={recommended['kp']} "
            f"max_lock_ns={recommended['max_lock_ns']} "
            f"max_abs_error_code={recommended['max_abs_error_code']}"
        )
        print(
            f"fastest within tolerance DLF_KI={fastest['ki']} DLF_KP={fastest['kp']} "
            f"max_lock_ns={fastest['max_lock_ns']} "
            f"max_abs_error_code={fastest['max_abs_error_code']}"
        )
        print(
            f"lowest-gain passing DLF_KI={lowest_gain['ki']} DLF_KP={lowest_gain['kp']} "
            f"max_lock_ns={lowest_gain['max_lock_ns']} "
            f"max_abs_error_code={lowest_gain['max_abs_error_code']}"
        )
    print(f"wrote {rows_path}")
    print(f"wrote {summary_path}")

    if not passing:
        print("no KI/KP combination passed both low-start and high-start acquisition", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
