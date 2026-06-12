#!/usr/bin/env python3
"""Run a focused Xyce C-interface mixed-signal PLL gain sweep."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
import re
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def resolve_repo_path(path: Path) -> Path:
    path = path.expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def artifact_path_text(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def parse_int_list(text: str) -> list[int]:
    values: list[int] = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        values.append(int(item, 0))
    if not values:
        raise argparse.ArgumentTypeError("expected at least one integer")
    return values


def parse_key_values(line: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for token in line.strip().split():
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        result[key] = value
    return result


def parse_driver_output(text: str) -> tuple[list[dict[str, str]], dict[str, str]]:
    cycle_header: list[str] | None = None
    cycles: list[dict[str, str]] = []
    summary: dict[str, str] = {}

    for line in text.splitlines():
        line = line.strip()
        if line.startswith("cycle,"):
            cycle_header = line.split(",")
        elif cycle_header is not None and re.match(r"^\d+,", line):
            values = line.split(",")
            if len(values) == len(cycle_header):
                cycles.append(dict(zip(cycle_header, values)))
        elif line.startswith("xyce_pll_mixed_signal_smoke="):
            summary = parse_key_values(line)

    return cycles, summary


def bool_text(value: bool) -> str:
    return "1" if value else "0"


def run_case(args, deck: Path, ki: int, kp: int, init_code: int) -> tuple[dict[str, str], list[dict[str, str]]]:
    expect = "increase" if init_code < args.target_code else "decrease"
    side = "low" if expect == "increase" else "high"
    case = f"ki{ki}_kp{kp}_{side}"
    log_path = args.build_dir / f"{case}.log"

    cmd = [
        str(args.driver),
        str(deck),
        "--init-code",
        str(init_code),
        "--target-code",
        str(args.target_code),
        "--cycles",
        str(args.cycles),
        "--ki",
        str(ki),
        "--kp",
        str(kp),
        "--frac",
        str(args.frac),
        "--boost-shift",
        str(args.boost_shift),
        "--boost-after",
        str(args.boost_after),
        "--ndiv",
        str(args.ndiv),
        "--expect",
        expect,
        "--min-motion",
        str(args.min_motion),
        "--tol-code",
        str(args.tol_code),
        "--f0-mhz",
        f"{args.f0_mhz:g}",
        "--f64-mhz",
        f"{args.f64_mhz:g}",
        "--f128-mhz",
        f"{args.f128_mhz:g}",
        "--f192-mhz",
        f"{args.f192_mhz:g}",
        "--f255-mhz",
        f"{args.f255_mhz:g}",
        "--coarse-code",
        str(args.coarse_code),
        "--dco-coarse-step-mhz",
        f"{args.dco_coarse_step_mhz:g}",
        "--phase-wrap-cycles",
        f"{args.phase_wrap_cycles:g}",
    ]

    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=args.timeout_s,
            check=False,
        )
        output = proc.stdout
        returncode = proc.returncode
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + f"\nOpenPLL timeout after {args.timeout_s:.1f} s\n"
        returncode = 124

    log_path.write_text(output, encoding="utf-8", errors="replace")
    cycles, summary = parse_driver_output(output)

    codes = [int(row["dco_code"]) for row in cycles]
    final_code = int(summary.get("final_code", codes[-1] if codes else init_code))
    min_abs_error = int(summary.get("min_abs_error", min((abs(code - args.target_code) for code in codes), default=abs(init_code - args.target_code))))
    driver_pass = summary.get("xyce_pll_mixed_signal_smoke") == "pass"
    exact_hit_cycles = [
        int(row["cycle"])
        for row in cycles
        if int(row["dco_code"]) == args.target_code
    ]
    tol_hit_cycles = [
        int(row["cycle"])
        for row in cycles
        if abs(int(row["dco_code"]) - args.target_code) <= args.tol_code
    ]
    crossed_target = bool(codes) and (
        (expect == "increase" and max(codes) >= args.target_code)
        or (expect == "decrease" and min(codes) <= args.target_code)
    )

    row = {
        "case": case,
        "ki": str(ki),
        "kp": str(kp),
        "init_code": str(init_code),
        "target_code": str(args.target_code),
        "expect": expect,
        "cycles": str(args.cycles),
        "frac": str(args.frac),
        "boost_shift": str(args.boost_shift),
        "boost_after": str(args.boost_after),
        "f0_mhz": f"{args.f0_mhz:g}",
        "f64_mhz": f"{args.f64_mhz:g}",
        "f128_mhz": f"{args.f128_mhz:g}",
        "f192_mhz": f"{args.f192_mhz:g}",
        "f255_mhz": f"{args.f255_mhz:g}",
        "coarse_code": str(args.coarse_code),
        "dco_coarse_step_mhz": f"{args.dco_coarse_step_mhz:g}",
        "phase_wrap_cycles": f"{args.phase_wrap_cycles:g}",
        "returncode": str(returncode),
        "driver_pass": bool_text(returncode == 0 and driver_pass),
        "final_code": str(final_code),
        "final_abs_error": str(abs(final_code - args.target_code)),
        "min_abs_error": str(min_abs_error),
        "exact_hit": bool_text(bool(exact_hit_cycles)),
        "first_exact_hit_cycle": str(exact_hit_cycles[0]) if exact_hit_cycles else "",
        "tol_hit": bool_text(bool(tol_hit_cycles)),
        "first_tol_hit_cycle": str(tol_hit_cycles[0]) if tol_hit_cycles else "",
        "crossed_target": bool_text(crossed_target),
        "expected_decisions": summary.get("expected_decisions", ""),
        "log_path": artifact_path_text(log_path),
    }

    detail_rows: list[dict[str, str]] = []
    for cycle in cycles:
        detail = dict(cycle)
        detail.update(
            {
                "case": case,
                "ki": str(ki),
                "kp": str(kp),
                "init_code": str(init_code),
                "expect": expect,
            }
        )
        detail_rows.append(detail)

    print(
        f"{case}: pass={row['driver_pass']} final={final_code} "
        f"min_abs_error={min_abs_error} exact_hit={row['exact_hit']} "
        f"crossed={row['crossed_target']} decisions={row['expected_decisions']}",
        flush=True,
    )
    return row, detail_rows


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--driver",
        type=Path,
        default=ROOT / "build" / "xyce_cinterface_smoke_mpi" / "xyce_pll_mixed_signal_smoke",
    )
    parser.add_argument(
        "--deck",
        type=Path,
        default=None,
        help="Generated YADC/YDAC deck path. Defaults to BUILD_DIR/pll_bbpd_yadc_ydac.cir.",
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=ROOT / "build" / "xyce_pll_mixed_signal_gain_sweep",
    )
    parser.add_argument("--ki-values", type=parse_int_list, default=parse_int_list("160"))
    parser.add_argument("--kp-values", type=parse_int_list, default=parse_int_list("0,8"))
    parser.add_argument("--init-codes", type=parse_int_list, default=parse_int_list("96,160"))
    parser.add_argument("--target-code", type=int, default=128)
    parser.add_argument("--cycles", type=int, default=10)
    parser.add_argument("--frac", type=int, default=6)
    parser.add_argument("--boost-shift", type=int, default=4)
    parser.add_argument("--boost-after", type=int, default=2)
    parser.add_argument("--ndiv", type=int, default=2)
    parser.add_argument("--min-motion", type=int, default=4)
    parser.add_argument("--tol-code", type=int, default=24)
    parser.add_argument("--f0-mhz", type=float, default=50.955942)
    parser.add_argument("--f64-mhz", type=float, default=55.205750)
    parser.add_argument("--f128-mhz", type=float, default=60.174879)
    parser.add_argument("--f192-mhz", type=float, default=66.031451)
    parser.add_argument("--f255-mhz", type=float, default=72.479371)
    parser.add_argument(
        "--coarse-code",
        type=int,
        default=0,
        help="Static independent DCO coarse-band code for the driver DCO model.",
    )
    parser.add_argument(
        "--dco-coarse-step-mhz",
        type=float,
        default=0.0,
        help="Frequency offset per independent coarse-band code step.",
    )
    parser.add_argument(
        "--phase-wrap-cycles",
        type=float,
        default=0.45,
        help="Driver phase wrap threshold in reference cycles; 0 disables wrapping.",
    )
    parser.add_argument("--step-ps", type=float, default=5.0)
    parser.add_argument("--sim-time-ns", type=float, default=400.0)
    parser.add_argument("--timeout-s", type=float, default=90.0)
    parser.add_argument("--skip-deck-generation", action="store_true")
    args = parser.parse_args()

    args.driver = resolve_repo_path(args.driver)
    args.build_dir = resolve_repo_path(args.build_dir)
    if args.deck is None:
        args.deck = args.build_dir / "pll_bbpd_yadc_ydac.cir"
    else:
        args.deck = resolve_repo_path(args.deck)
    args.build_dir.mkdir(parents=True, exist_ok=True)

    if not args.driver.exists():
        raise FileNotFoundError(args.driver)

    if not args.skip_deck_generation:
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "xyce_bbpd_cinterface_smoke.py"),
                "--out",
                str(args.deck),
                "--step-ps",
                f"{args.step_ps:g}",
                "--sim-time-ns",
                f"{args.sim_time_ns:g}",
            ],
            cwd=ROOT,
            check=True,
        )
    elif not args.deck.exists():
        raise FileNotFoundError(args.deck)

    summary_rows: list[dict[str, str]] = []
    detail_rows: list[dict[str, str]] = []
    for ki in args.ki_values:
        for kp in args.kp_values:
            for init_code in args.init_codes:
                row, details = run_case(args, args.deck, ki, kp, init_code)
                summary_rows.append(row)
                detail_rows.extend(details)

    summary_fields = [
        "case",
        "ki",
        "kp",
        "init_code",
        "target_code",
        "expect",
        "cycles",
        "frac",
        "boost_shift",
        "boost_after",
        "f0_mhz",
        "f64_mhz",
        "f128_mhz",
        "f192_mhz",
        "f255_mhz",
        "coarse_code",
        "dco_coarse_step_mhz",
        "phase_wrap_cycles",
        "returncode",
        "driver_pass",
        "final_code",
        "final_abs_error",
        "min_abs_error",
        "exact_hit",
        "first_exact_hit_cycle",
        "tol_hit",
        "first_tol_hit_cycle",
        "crossed_target",
        "expected_decisions",
        "log_path",
    ]
    detail_fields = [
        "case",
        "ki",
        "kp",
        "init_code",
        "expect",
        "cycle",
        "ref_ns",
        "div_ns",
        "phase_ps",
        "up_ps",
        "dn_ps",
        "decision",
        "dco_code",
        "fdco_mhz",
    ]

    summary_path = args.build_dir / "mixed_signal_gain_summary.csv"
    detail_path = args.build_dir / "mixed_signal_gain_cycles.csv"
    write_csv(summary_path, summary_rows, summary_fields)
    write_csv(detail_path, detail_rows, detail_fields)
    print(summary_path)
    print(detail_path)

    if not all(row["driver_pass"] == "1" for row in summary_rows):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
