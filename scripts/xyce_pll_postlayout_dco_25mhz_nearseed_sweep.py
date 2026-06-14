#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run direct extracted-DCO near-seed code-update smokes for 25 MHz targets."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import subprocess
import sys
import time

from sky130_pdk import default_pdk_root


ROOT = Path(__file__).resolve().parents[1]

SUMMARY_RE = re.compile(r"^xyce_pll_postlayout_dco_mixed_signal_smoke=(\w+)\s+(.*)$")

TARGETS = {
    100: {
        "coarse_code": 20,
        "target_code": 93,
        "ndiv": 4,
        "freq_tol_mhz": 25.0,
        "min_pllout_rises": 3,
        "cosim_step_ns": 0.1,
    },
    250: {
        "coarse_code": 6,
        "target_code": 234,
        "ndiv": 10,
        "freq_tol_mhz": 25.0,
        "min_pllout_rises": 6,
        "cosim_step_ns": 0.1,
    },
    300: {
        "coarse_code": 4,
        "target_code": 90,
        "ndiv": 12,
        "freq_tol_mhz": 25.0,
        "min_pllout_rises": 8,
        "cosim_step_ns": 0.1,
    },
    400: {
        "coarse_code": 2,
        "target_code": 76,
        "ndiv": 16,
        "freq_tol_mhz": 25.0,
        "min_pllout_rises": 8,
        "cosim_step_ns": 0.1,
    },
}


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


def parse_targets(text: str) -> list[int]:
    result = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        target = int(item, 0)
        if target not in TARGETS:
            raise argparse.ArgumentTypeError(
                f"unsupported target {target}; expected one of {sorted(TARGETS)}"
            )
        if target not in result:
            result.append(target)
    if not result:
        raise argparse.ArgumentTypeError("expected at least one target")
    return result


def parse_sides(text: str) -> list[str]:
    result = []
    for item in text.split(","):
        item = item.strip().lower()
        if not item:
            continue
        if item not in ("low", "high"):
            raise argparse.ArgumentTypeError("sides must be low, high, or low,high")
        if item not in result:
            result.append(item)
    if not result:
        raise argparse.ArgumentTypeError("expected at least one side")
    return result


def parse_summary_line(text: str) -> dict[str, str]:
    for line in text.splitlines():
        match = SUMMARY_RE.match(line.strip())
        if not match:
            continue
        values = {"status": match.group(1)}
        for token in match.group(2).split():
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            values[key] = value
        return values
    return {}


def parse_measure_line(text: str) -> dict[str, str]:
    header: list[str] | None = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("measure,start_ns,"):
            header = line.split(",")
            continue
        if header is not None and line.startswith("measure,"):
            values = line.split(",")
            if len(values) == len(header):
                return dict(zip(header, values))
    return {}


def print_driver_excerpt(text: str) -> None:
    for line in text.splitlines():
        if (
            line.startswith("cycle,")
            or re.match(r"^\d+,", line)
            or line.startswith("measure,")
            or line.startswith("xyce_pll_postlayout_dco_mixed_signal_smoke=")
        ):
            print(line, flush=True)


def side_init_code(target_code: int, side: str, offset: int) -> int:
    if side == "low":
        return max(0, target_code - offset)
    return min(255, target_code + offset)


def side_expect(side: str) -> str:
    return "increase" if side == "low" else "decrease"


def case_initial_divider_count(args: argparse.Namespace, ndiv: int, side: str) -> int:
    if args.initial_divider_count is not None:
        return args.initial_divider_count
    return 0 if side == "low" else ndiv - 1


def case_clock_phase_offset(args: argparse.Namespace, side: str) -> float:
    if args.clock_phase_offset is not None:
        return args.clock_phase_offset
    return args.low_clock_phase_offset if side == "low" else args.high_clock_phase_offset


def completed_pass(
    log_path: Path,
    args: argparse.Namespace,
    target_mhz: int,
    target_code: int,
    init_code: int,
    expect: str,
) -> tuple[dict[str, str], dict[str, str]] | None:
    if not log_path.exists():
        return None
    text = log_path.read_text(encoding="utf-8", errors="replace")
    summary = parse_summary_line(text)
    if summary.get("status") != "pass":
        return None
    checks = {
        "expect": expect,
        "start_code": str(init_code),
        "target_code": str(target_code),
        "target_mhz": f"{float(target_mhz):.3f}",
    }
    if any(summary.get(key) != value for key, value in checks.items()):
        return None
    try:
        final_abs_error = int(summary["final_abs_error"])
        expected_decisions = int(summary["expected_decisions"])
        freq_abs_error = float(summary["freq_abs_error_mhz"])
        freq_tol = float(summary["freq_tol_mhz"])
        pllout_rises = int(summary["pllout_rises"])
    except (KeyError, ValueError):
        return None
    if final_abs_error > args.tol_code:
        return None
    if expected_decisions < args.min_expected_decisions:
        return None
    if freq_abs_error > freq_tol:
        return None
    if pllout_rises < TARGETS[target_mhz]["min_pllout_rises"]:
        return None
    return summary, parse_measure_line(text)


def target_paths(
    build_dir: Path,
    target_mhz: int,
    coarse_code: int,
    target_code: int,
    side: str,
) -> tuple[Path, Path]:
    deck = build_dir / f"target{target_mhz}_c{coarse_code:02d}.cir"
    log = (
        build_dir
        / f"target{target_mhz}_c{coarse_code:02d}_code{target_code:03d}_nearseed_{side}.log"
    )
    return deck, log


def generate_deck(
    args: argparse.Namespace,
    coarse_code: int,
    clock_phase_offset: float,
    deck: Path,
) -> None:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "xyce_pll_postlayout_dco_cinterface_deck.py"),
        "--pdk-root",
        str(args.pdk_root),
        "--pdk",
        args.pdk,
        "--out",
        str(deck),
        "--ref-mhz",
        f"{args.ref_mhz:g}",
        "--dco-subckt",
        args.dco_subckt,
        "--dco-rcx-netlist",
        str(args.dco_rcx_netlist),
        "--coarse-code",
        str(coarse_code),
        "--sim-time-ns",
        f"{args.sim_time_ns:g}",
        "--step-ps",
        f"{args.step_ps:g}",
        "--max-step-ps",
        f"{args.max_step_ps:g}",
        "--clock-sharpness",
        f"{args.clock_sharpness:g}",
        "--clock-phase-offset",
        f"{clock_phase_offset:g}",
        "--reset-release-ns",
        f"{args.reset_release_ns:g}",
        "--ref-source",
        args.ref_source,
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)


def run_case(args: argparse.Namespace, target_mhz: int, side: str) -> dict[str, str]:
    cfg = TARGETS[target_mhz]
    coarse_code = int(cfg["coarse_code"])
    target_code = int(cfg["target_code"])
    ndiv = int(cfg["ndiv"])
    init_code = side_init_code(target_code, side, args.init_offset)
    expect = side_expect(side)
    initial_divider_count = case_initial_divider_count(args, ndiv, side)
    clock_phase_offset = case_clock_phase_offset(args, side)
    deck, log = target_paths(args.build_dir, target_mhz, coarse_code, target_code, side)
    generate_deck(args, coarse_code, clock_phase_offset, deck)

    resumed = False
    completed = (
        completed_pass(log, args, target_mhz, target_code, init_code, expect)
        if args.resume
        else None
    )
    if completed is not None:
        summary, measure = completed
        resumed = True
        print(
            f"target{target_mhz}_c{coarse_code:02d}_code{target_code:03d}_{side}: resumed pass",
            flush=True,
        )
    else:
        cmd = [
            str(args.driver),
            str(deck),
            "--init-code",
            str(init_code),
            "--target-code",
            str(target_code),
            "--cycles",
            str(args.cycles),
            "--ki",
            str(args.ki),
            "--kp",
            str(args.kp),
            "--frac",
            str(args.frac),
            "--ref-mhz",
            f"{args.ref_mhz:g}",
            "--ndiv",
            str(ndiv),
            "--target-mhz",
            str(target_mhz),
            "--freq-tol-mhz",
            f"{float(cfg['freq_tol_mhz']):g}",
            "--measure-cycles",
            str(args.measure_cycles),
            "--measure-settle-ns",
            f"{args.measure_settle_ns:g}",
            "--min-pllout-rises",
            str(int(cfg["min_pllout_rises"])),
            "--expect",
            expect,
            "--min-motion",
            str(args.min_motion),
            "--tol-code",
            str(args.tol_code),
            "--start-ns",
            f"{args.start_ns:g}",
            "--cosim-step-ns",
            f"{float(cfg['cosim_step_ns']):g}",
            "--divider-latency-ps",
            f"{args.divider_latency_ps:g}",
            "--initial-divider-count",
            str(initial_divider_count),
            "--no-warmup-divider",
            "--prop-rail-guard",
        ]
        start = time.monotonic()
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
        elapsed_s = time.monotonic() - start
        log.write_text(output, encoding="utf-8", errors="replace")
        print_driver_excerpt(output)
        summary = parse_summary_line(output)
        measure = parse_measure_line(output)
        if returncode != 0 or summary.get("status") != "pass":
            if not args.keep_going:
                raise RuntimeError(
                    f"target {target_mhz} MHz {side} near-seed direct-RCX failed; "
                    f"see {artifact_path_text(log)}"
                )
        summary["elapsed_s"] = f"{elapsed_s:.3f}"

    return {
        "target_mhz": str(target_mhz),
        "ref_mhz": f"{args.ref_mhz:.6f}",
        "multiplier": str(int(cfg["ndiv"])),
        "coarse_code": str(coarse_code),
        "target_code": str(target_code),
        "side": side,
        "expect": expect,
        "init_code": str(init_code),
        "status": summary.get("status", ""),
        "final_code": summary.get("final_code", ""),
        "expected_decisions": summary.get("expected_decisions", ""),
        "min_abs_error": summary.get("min_abs_error", ""),
        "final_abs_error": summary.get("final_abs_error", ""),
        "tol_code": str(args.tol_code),
        "measured_mhz": summary.get("measured_mhz", measure.get("measured_mhz", "")),
        "target_freq_mhz": summary.get("target_mhz", measure.get("target_mhz", "")),
        "freq_abs_error_mhz": summary.get(
            "freq_abs_error_mhz", measure.get("freq_abs_error_mhz", "")
        ),
        "freq_tol_mhz": f"{float(cfg['freq_tol_mhz']):g}",
        "pllout_rises": summary.get("pllout_rises", measure.get("pllout_rises", "")),
        "cycles": str(args.cycles),
        "ki": str(args.ki),
        "kp": str(args.kp),
        "frac": str(args.frac),
        "initial_divider_count": str(initial_divider_count),
        "clock_phase_offset": f"{clock_phase_offset:g}",
        "resumed": "1" if resumed else "0",
        "elapsed_s": summary.get("elapsed_s", ""),
        "deck": artifact_path_text(deck),
        "log": artifact_path_text(log),
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
        "target_mhz",
        "ref_mhz",
        "multiplier",
        "coarse_code",
        "target_code",
        "side",
        "expect",
        "init_code",
        "status",
        "final_code",
        "expected_decisions",
        "min_abs_error",
        "final_abs_error",
        "tol_code",
        "measured_mhz",
        "target_freq_mhz",
        "freq_abs_error_mhz",
        "freq_tol_mhz",
        "pllout_rises",
        "cycles",
        "ki",
        "kp",
        "frac",
        "initial_divider_count",
        "clock_phase_offset",
        "resumed",
        "elapsed_s",
        "deck",
        "log",
    ]
    with path.open("w", encoding="ascii", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def validate_args(args: argparse.Namespace) -> None:
    if not args.driver.exists():
        raise FileNotFoundError(args.driver)
    model_path = args.pdk_root / args.pdk / "libs.tech" / "ngspice" / "sky130.lib.spice"
    if not model_path.exists():
        raise FileNotFoundError(model_path)
    if not args.dco_rcx_netlist.exists():
        raise FileNotFoundError(args.dco_rcx_netlist)
    if args.init_offset <= 0:
        raise ValueError("--init-offset must be positive")
    if args.cycles <= 0:
        raise ValueError("--cycles must be positive")
    if args.measure_cycles <= 0:
        raise ValueError("--measure-cycles must be positive")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--driver",
        type=Path,
        default=ROOT
        / "build"
        / "xyce_cinterface_smoke_mpi"
        / "xyce_pll_postlayout_dco_mixed_signal_smoke",
    )
    parser.add_argument("--pdk-root", type=Path, default=Path(default_pdk_root()))
    parser.add_argument("--pdk", default="sky130A")
    parser.add_argument("--targets-mhz", type=parse_targets, default=parse_targets("100,250,300,400"))
    parser.add_argument("--sides", type=parse_sides, default=parse_sides("low,high"))
    parser.add_argument("--ref-mhz", type=float, default=25.0)
    parser.add_argument("--dco-subckt", default="IntegerPLL_DCO_EINVP_COARSE")
    parser.add_argument(
        "--dco-rcx-netlist",
        type=Path,
        default=ROOT
        / "openlane"
        / "IntegerPLL_DCO_EINVP_COARSE"
        / "runs"
        / "librelane_signoff"
        / "rcx-magic"
        / "IntegerPLL_DCO_EINVP_COARSE.rcx.spice",
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=ROOT / "build" / "xyce_pll_postlayout_dco_mixed_25mhz_coarse",
    )
    parser.add_argument("--init-offset", type=int, default=4)
    parser.add_argument("--cycles", type=int, default=2)
    parser.add_argument("--ki", type=int, default=16)
    parser.add_argument("--kp", type=int, default=4)
    parser.add_argument("--frac", type=int, default=2)
    parser.add_argument("--min-motion", type=int, default=1)
    parser.add_argument("--min-expected-decisions", type=int, default=1)
    parser.add_argument("--tol-code", type=int, default=4)
    parser.add_argument("--measure-cycles", type=int, default=1)
    parser.add_argument("--measure-settle-ns", type=float, default=5.0)
    parser.add_argument("--start-ns", type=float, default=8.0)
    parser.add_argument("--divider-latency-ps", type=float, default=50.0)
    parser.add_argument(
        "--initial-divider-count",
        type=int,
        default=None,
        help="Override divider seed for all cases; default is 0 for low and NDIV-1 for high.",
    )
    parser.add_argument("--sim-time-ns", type=float, default=160.0)
    parser.add_argument("--step-ps", type=float, default=20.0)
    parser.add_argument("--max-step-ps", type=float, default=100.0)
    parser.add_argument("--clock-sharpness", type=float, default=80.0)
    parser.add_argument(
        "--clock-phase-offset",
        type=float,
        default=None,
        help="Override REF phase for all cases; defaults are side-specific.",
    )
    parser.add_argument("--low-clock-phase-offset", type=float, default=-0.25)
    parser.add_argument("--high-clock-phase-offset", type=float, default=0.25)
    parser.add_argument("--reset-release-ns", type=float, default=1.0)
    parser.add_argument("--ref-source", choices=("pulse", "sine"), default="pulse")
    parser.add_argument("--timeout-s", type=float, default=1200.0)
    parser.add_argument("--summary-stem", default="pll_postlayout_dco_25mhz_nearseed_summary")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--keep-going", action="store_true")
    args = parser.parse_args()

    args.driver = resolve_repo_path(args.driver)
    args.pdk_root = args.pdk_root.expanduser().resolve()
    args.dco_rcx_netlist = resolve_repo_path(args.dco_rcx_netlist)
    args.build_dir = resolve_repo_path(args.build_dir)
    args.build_dir.mkdir(parents=True, exist_ok=True)
    validate_args(args)

    rows = []
    for target in args.targets_mhz:
        for side in args.sides:
            rows.append(run_case(args, target, side))

    status = "pass" if all(row["status"] == "pass" for row in rows) else "fail"
    csv_path = args.build_dir / f"{args.summary_stem}.csv"
    json_path = args.build_dir / f"{args.summary_stem}.json"
    write_csv(csv_path, rows)
    output = {
        "status": status,
        "ref_mhz": args.ref_mhz,
        "targets_mhz": args.targets_mhz,
        "sides": args.sides,
        "summary_csv": artifact_path_text(csv_path),
        "target_results": rows,
    }
    json_path.write_text(json.dumps(output, indent=2) + "\n", encoding="ascii")
    print(json.dumps(output, indent=2))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
