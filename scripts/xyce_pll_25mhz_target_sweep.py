#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check 25 MHz-reference PLL target modes with measured mirror-coarse DCO bands."""

from __future__ import annotations

import argparse
import csv
import json
import math
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


def parse_float_list(text: str) -> list[float]:
    values = [float(item.strip()) for item in text.split(",") if item.strip()]
    if not values:
        raise argparse.ArgumentTypeError("expected at least one float")
    return values


def parse_int_list(text: str) -> list[int]:
    values = [int(item.strip(), 0) for item in text.split(",") if item.strip()]
    if not values:
        raise argparse.ArgumentTypeError("expected at least one integer")
    return values


def optional_float(text: str | None) -> float | None:
    if text is None or text == "":
        return None
    return float(text)


def format_optional(value: object) -> str:
    if value is None:
        return ""
    return f"{float(value):.6f}"


def init_codes_for_target(args: argparse.Namespace, target_code: int) -> list[int]:
    if args.init_offsets is None:
        return args.init_codes
    codes = []
    for offset in args.init_offsets:
        code = max(0, min(255, target_code + offset))
        if code != target_code and code not in codes:
            codes.append(code)
    if not codes:
        raise ValueError(f"no non-target initial codes for target code {target_code}")
    return codes


def read_dco_rows(paths: list[Path]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in paths:
        with path.open(newline="", encoding="ascii") as csv_file:
            for row in csv.DictReader(csv_file):
                if row.get("status") != "pass":
                    continue
                period_s = optional_float(row.get("period_s"))
                rise_time_s = optional_float(row.get("rise_time_s"))
                fall_time_s = optional_float(row.get("fall_time_s"))
                rows.append(
                    {
                        "corner": row["corner"],
                        "topology": row.get("topology", ""),
                        "coarse_code": int(row.get("coarse_code") or 0),
                        "selected_tap": row.get("selected_tap", ""),
                        "code": int(row["code"]),
                        "freq_mhz": float(row["freq_mhz"]),
                        "period_s": period_s,
                        "duty_ratio": optional_float(row.get("duty_ratio")),
                        "rise_time_s": rise_time_s,
                        "fall_time_s": fall_time_s,
                        "rise_period_fraction": (
                            rise_time_s / period_s
                            if period_s and rise_time_s is not None
                            else None
                        ),
                        "fall_period_fraction": (
                            fall_time_s / period_s
                            if period_s and fall_time_s is not None
                            else None
                        ),
                        "source_csv": str(path),
                    }
                )
    if not rows:
        raise ValueError("no passing DCO rows found")
    return rows


def estimate_freq_at_code(points: list[tuple[int, float]], code: float) -> float:
    ordered = sorted(set(points))
    if len(ordered) < 2:
        raise ValueError("at least two measured DCO rows are required per coarse band")
    for (code0, freq0), (code1, freq1) in zip(ordered, ordered[1:]):
        if freq1 <= freq0:
            raise ValueError(
                f"non-monotonic DCO band near codes {code0}..{code1}: "
                f"{freq0:.6f} >= {freq1:.6f} MHz"
            )
    if code < ordered[0][0]:
        code0, freq0 = ordered[0]
        code1, freq1 = ordered[1]
        frac = (code - code0) / (code1 - code0)
        return freq0 + frac * (freq1 - freq0)
    if code > ordered[-1][0]:
        code0, freq0 = ordered[-2]
        code1, freq1 = ordered[-1]
        frac = (code - code0) / (code1 - code0)
        return freq0 + frac * (freq1 - freq0)
    for (code0, freq0), (code1, freq1) in zip(ordered, ordered[1:]):
        if code0 <= code <= code1:
            frac = 0.0 if code1 == code0 else (code - code0) / (code1 - code0)
            return freq0 + frac * (freq1 - freq0)
    return ordered[-1][1]


def band_table(rows: list[dict[str, object]], coarse_code: int) -> dict[str, float]:
    points = [
        (int(row["code"]), float(row["freq_mhz"]))
        for row in rows
        if int(row["coarse_code"]) == coarse_code
    ]
    return {
        "f0_mhz": estimate_freq_at_code(points, 0),
        "f64_mhz": estimate_freq_at_code(points, 64),
        "f128_mhz": estimate_freq_at_code(points, 128),
        "f192_mhz": estimate_freq_at_code(points, 192),
        "f255_mhz": estimate_freq_at_code(points, 255),
    }


def freq_from_table(table: dict[str, float], code: int) -> float:
    points = [
        (0, table["f0_mhz"]),
        (64, table["f64_mhz"]),
        (128, table["f128_mhz"]),
        (192, table["f192_mhz"]),
        (255, table["f255_mhz"]),
    ]
    return estimate_freq_at_code(points, code)


def waveform_failure(row: dict[str, object], args: argparse.Namespace) -> str:
    duty = row["duty_ratio"]
    rise_fraction = row["rise_period_fraction"]
    fall_fraction = row["fall_period_fraction"]
    if duty is None or rise_fraction is None or fall_fraction is None:
        return "missing waveform measurements"
    if float(duty) < args.min_duty_ratio or float(duty) > args.max_duty_ratio:
        return f"duty {float(duty):.4f} outside {args.min_duty_ratio:.4f}..{args.max_duty_ratio:.4f}"
    if float(rise_fraction) > args.max_edge_period_fraction:
        return (
            f"rise/period {float(rise_fraction):.4f} exceeds "
            f"{args.max_edge_period_fraction:.4f}"
        )
    if float(fall_fraction) > args.max_edge_period_fraction:
        return (
            f"fall/period {float(fall_fraction):.4f} exceeds "
            f"{args.max_edge_period_fraction:.4f}"
        )
    return ""


def target_candidates(
    rows: list[dict[str, object]],
    target_mhz: float,
    args: argparse.Namespace,
) -> list[dict[str, object]]:
    by_band: dict[tuple[str, int], list[dict[str, object]]] = {}
    for row in rows:
        by_band.setdefault((str(row["corner"]), int(row["coarse_code"])), []).append(row)

    candidates: list[dict[str, object]] = []
    for (corner, coarse_code), band_rows in by_band.items():
        for row in band_rows:
            freq_error = abs(float(row["freq_mhz"]) - target_mhz)
            if freq_error > args.prefer_measured_within_mhz:
                continue
            direct_waveform_failure = waveform_failure(row, args)
            if args.require_waveform_quality and direct_waveform_failure:
                continue
            candidates.append(
                {
                    "corner": corner,
                    "coarse_code": coarse_code,
                    "selected_tap": row["selected_tap"],
                    "selection": "measured",
                    "code_est": float(row["code"]),
                    "target_code": int(row["code"]),
                    "low_code": int(row["code"]),
                    "low_freq_mhz": float(row["freq_mhz"]),
                    "high_code": int(row["code"]),
                    "high_freq_mhz": float(row["freq_mhz"]),
                    "low_duty_ratio": row["duty_ratio"],
                    "high_duty_ratio": row["duty_ratio"],
                    "low_rise_period_fraction": row["rise_period_fraction"],
                    "high_rise_period_fraction": row["rise_period_fraction"],
                    "low_fall_period_fraction": row["fall_period_fraction"],
                    "high_fall_period_fraction": row["fall_period_fraction"],
                    "low_waveform_failure": direct_waveform_failure,
                    "high_waveform_failure": direct_waveform_failure,
                    "code_mid_distance": abs(float(row["code"]) - 128.0),
                    "freq_error_mhz": freq_error,
                }
            )

        ordered = sorted(band_rows, key=lambda row: float(row["freq_mhz"]))
        for low, high in zip(ordered, ordered[1:]):
            low_freq = float(low["freq_mhz"])
            high_freq = float(high["freq_mhz"])
            if low_freq <= target_mhz <= high_freq:
                low_waveform_failure = waveform_failure(low, args)
                high_waveform_failure = waveform_failure(high, args)
                if args.require_waveform_quality and (
                    low_waveform_failure or high_waveform_failure
                ):
                    continue
                frac = 0.0 if high_freq == low_freq else (target_mhz - low_freq) / (high_freq - low_freq)
                code_est = int(low["code"]) + frac * (int(high["code"]) - int(low["code"]))
                candidates.append(
                    {
                        "corner": corner,
                        "coarse_code": coarse_code,
                        "selected_tap": low["selected_tap"] or high["selected_tap"],
                        "selection": "interpolated",
                        "code_est": code_est,
                        "target_code": int(round(code_est)),
                        "low_code": int(low["code"]),
                        "low_freq_mhz": low_freq,
                        "high_code": int(high["code"]),
                        "high_freq_mhz": high_freq,
                        "low_duty_ratio": low["duty_ratio"],
                        "high_duty_ratio": high["duty_ratio"],
                        "low_rise_period_fraction": low["rise_period_fraction"],
                        "high_rise_period_fraction": high["rise_period_fraction"],
                        "low_fall_period_fraction": low["fall_period_fraction"],
                        "high_fall_period_fraction": high["fall_period_fraction"],
                        "low_waveform_failure": low_waveform_failure,
                        "high_waveform_failure": high_waveform_failure,
                        "code_mid_distance": abs(code_est - 128.0),
                        "freq_error_mhz": 0.0,
                    }
                )
    candidates.sort(
        key=lambda row: (
            0 if row.get("selection") == "measured" else 1,
            float(row["freq_error_mhz"]),
            float(row["code_mid_distance"]),
            int(row["coarse_code"]),
        )
    )
    return candidates


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


def int_from_summary(summary: dict[str, str], key: str, default: int) -> int:
    try:
        return int(summary.get(key, default))
    except ValueError:
        return default


def run_case(
    args: argparse.Namespace,
    deck: Path,
    target: dict[str, object],
    table: dict[str, float],
    ki: int,
    kp: int,
    init_code: int,
) -> tuple[dict[str, str], list[dict[str, str]]]:
    target_code = int(target["target_code"])
    expect = "increase" if init_code < target_code else "decrease"
    side = "low" if expect == "increase" else "high"
    target_tag = f"{float(target['target_mhz']):.0f}m"
    case = (
        f"target{target_tag}_c{int(target['coarse_code']):02d}_"
        f"code{target_code:03d}_ki{ki}_kp{kp}_{side}"
    )
    log_path = args.build_dir / f"{case}.log"
    min_motion = min(args.min_motion, max(1, abs(init_code - target_code)))

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
        str(ki),
        "--kp",
        str(kp),
        "--frac",
        str(args.frac),
        "--boost-shift",
        str(args.boost_shift),
        "--boost-after",
        str(args.boost_after),
        "--track-decay-shift",
        str(args.track_decay_shift),
        "--ndiv",
        str(int(target["multiplier"])),
        "--expect",
        expect,
        "--min-motion",
        str(min_motion),
        "--tol-code",
        str(args.tol_code),
        "--f0-mhz",
        f"{table['f0_mhz']:.12g}",
        "--f64-mhz",
        f"{table['f64_mhz']:.12g}",
        "--f128-mhz",
        f"{table['f128_mhz']:.12g}",
        "--f192-mhz",
        f"{table['f192_mhz']:.12g}",
        "--f255-mhz",
        f"{table['f255_mhz']:.12g}",
        "--coarse-code",
        str(int(target["coarse_code"])),
        "--dco-coarse-step-mhz",
        "0",
        "--phase-wrap-cycles",
        f"{args.phase_wrap_cycles:g}",
        "--ref-mhz",
        f"{args.ref_mhz:g}",
        "--target-mhz",
        f"{float(target['target_mhz']):g}",
    ]

    resumed = False
    if args.resume and log_path.exists():
        output = log_path.read_text(encoding="utf-8", errors="replace")
        cycles, summary = parse_driver_output(output)
        if cycles and summary.get("xyce_pll_mixed_signal_smoke") in {"pass", "fail"}:
            returncode = 0 if summary.get("xyce_pll_mixed_signal_smoke") == "pass" else 1
            resumed = True
        else:
            output = ""
            returncode = 1
    else:
        output = ""
        returncode = 1

    if not resumed:
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
    min_abs_error = int(
        summary.get(
            "min_abs_error",
            min((abs(code - target_code) for code in codes), default=abs(init_code - target_code)),
        )
    )
    exact_hit_cycles = [int(row["cycle"]) for row in cycles if int(row["dco_code"]) == target_code]
    tol_hit_cycles = [
        int(row["cycle"])
        for row in cycles
        if abs(int(row["dco_code"]) - target_code) <= args.tol_code
    ]
    crossed_target = bool(codes) and (
        (expect == "increase" and max(codes) >= target_code)
        or (expect == "decrease" and min(codes) <= target_code)
    )
    final_abs_error = abs(final_code - target_code)
    final_freq_mhz = freq_from_table(table, final_code)
    final_freq_abs_error_mhz = abs(final_freq_mhz - float(target["target_mhz"]))
    late_codes = codes[-args.late_window_cycles :] if codes else []
    late_freq_errors = [
        abs(freq_from_table(table, code) - float(target["target_mhz"]))
        for code in late_codes
    ]
    late_max_freq_abs_error_mhz = max(late_freq_errors, default=math.inf)
    late_avg_freq_mhz = (
        sum(freq_from_table(table, code) for code in late_codes) / len(late_codes)
        if late_codes
        else math.nan
    )
    late_min_code = min(late_codes) if late_codes else None
    late_max_code = max(late_codes) if late_codes else None
    late_code_span = (late_max_code - late_min_code) if late_codes else None
    completed = bool(cycles) and summary.get("xyce_pll_mixed_signal_smoke") in {"pass", "fail"}
    driver_pass = returncode == 0 and summary.get("xyce_pll_mixed_signal_smoke") == "pass"
    expected_decisions = int_from_summary(summary, "expected_decisions", 0)
    if args.init_offsets is None:
        target_pass = driver_pass and bool(tol_hit_cycles) and min_abs_error <= args.tol_code
    else:
        target_pass = (
            completed
            and expected_decisions >= args.min_expected_decisions
            and bool(tol_hit_cycles)
            and final_freq_abs_error_mhz <= args.freq_tol_mhz
            and late_max_freq_abs_error_mhz <= args.freq_tol_mhz
            and late_code_span is not None
            and late_code_span <= args.max_late_code_span
        )

    row = {
        "case": case,
        "target_mhz": f"{float(target['target_mhz']):.6f}",
        "ref_mhz": f"{args.ref_mhz:.6f}",
        "multiplier": str(int(target["multiplier"])),
        "coarse_code": str(int(target["coarse_code"])),
        "selected_tap": str(target["selected_tap"]),
        "selection": str(target["selection"]),
        "target_code_est": f"{float(target['code_est']):.3f}",
        "target_code": str(target_code),
        "ki": str(ki),
        "kp": str(kp),
        "frac": str(args.frac),
        "boost_shift": str(args.boost_shift),
        "boost_after": str(args.boost_after),
        "track_decay_shift": str(args.track_decay_shift),
        "init_code": str(init_code),
        "expect": expect,
        "cycles": str(args.cycles),
        "min_motion": str(min_motion),
        "tol_code": str(args.tol_code),
        "f0_mhz": f"{table['f0_mhz']:.6f}",
        "f64_mhz": f"{table['f64_mhz']:.6f}",
        "f128_mhz": f"{table['f128_mhz']:.6f}",
        "f192_mhz": f"{table['f192_mhz']:.6f}",
        "f255_mhz": f"{table['f255_mhz']:.6f}",
        "returncode": str(returncode),
        "driver_pass": bool_text(driver_pass),
        "target_pass": bool_text(target_pass),
        "final_code": str(final_code),
        "final_freq_mhz": f"{final_freq_mhz:.6f}",
        "final_freq_abs_error_mhz": f"{final_freq_abs_error_mhz:.6f}",
        "late_window_cycles": str(args.late_window_cycles),
        "late_avg_freq_mhz": f"{late_avg_freq_mhz:.6f}" if late_codes else "",
        "late_max_freq_abs_error_mhz": (
            f"{late_max_freq_abs_error_mhz:.6f}" if late_codes else ""
        ),
        "late_min_code": str(late_min_code) if late_min_code is not None else "",
        "late_max_code": str(late_max_code) if late_max_code is not None else "",
        "late_code_span": str(late_code_span) if late_code_span is not None else "",
        "max_late_code_span": str(args.max_late_code_span),
        "freq_tol_mhz": f"{args.freq_tol_mhz:.6f}",
        "final_abs_error": str(final_abs_error),
        "min_abs_error": str(min_abs_error),
        "exact_hit": bool_text(bool(exact_hit_cycles)),
        "first_exact_hit_cycle": str(exact_hit_cycles[0]) if exact_hit_cycles else "",
        "tol_hit": bool_text(bool(tol_hit_cycles)),
        "first_tol_hit_cycle": str(tol_hit_cycles[0]) if tol_hit_cycles else "",
        "crossed_target": bool_text(crossed_target),
        "expected_decisions": str(expected_decisions),
        "min_expected_decisions": str(args.min_expected_decisions),
        "resumed": bool_text(resumed),
        "log_path": artifact_path_text(log_path),
    }

    detail_rows: list[dict[str, str]] = []
    for cycle in cycles:
        detail = dict(cycle)
        detail.update(
            {
                "case": case,
                "target_mhz": row["target_mhz"],
                "coarse_code": row["coarse_code"],
                "target_code": row["target_code"],
                "ki": str(ki),
                "kp": str(kp),
                "init_code": str(init_code),
                "expect": expect,
            }
        )
        detail_rows.append(detail)

    print(
        f"{case}: pass={row['target_pass']} final={final_code} "
        f"final_freq_err={row['final_freq_abs_error_mhz']} "
        f"late_max_freq_err={row['late_max_freq_abs_error_mhz']} "
        f"late_span={row['late_code_span']} tol_hit={row['tol_hit']} "
        f"decisions={row['expected_decisions']}",
        flush=True,
    )
    return row, detail_rows


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="ascii", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--driver",
        type=Path,
        default=ROOT / "build" / "xyce_cinterface_smoke_mpi" / "xyce_pll_mixed_signal_smoke",
    )
    parser.add_argument(
        "--dco-csv",
        type=Path,
        action="append",
        required=True,
        help="Input mirror-coarse dco_sweep.csv. Pass multiple times to combine probes.",
    )
    parser.add_argument(
        "--deck",
        type=Path,
        default=None,
        help="Generated BBPD YADC/YDAC deck. Defaults to BUILD_DIR/pll_bbpd_yadc_ydac.cir.",
    )
    parser.add_argument("--build-dir", type=Path, default=ROOT / "build" / "xyce_pll_25mhz_target_sweep")
    parser.add_argument("--ref-mhz", type=float, default=25.0)
    parser.add_argument("--targets-mhz", type=parse_float_list, default=parse_float_list("100,250,300,400"))
    parser.add_argument("--ki-values", type=parse_int_list, default=parse_int_list("192"))
    parser.add_argument("--kp-values", type=parse_int_list, default=parse_int_list("8"))
    parser.add_argument("--init-codes", type=parse_int_list, default=parse_int_list("0,255"))
    parser.add_argument(
        "--init-offsets",
        type=parse_int_list,
        default=None,
        help="Target-relative initial code offsets, for example -32,32. Overrides --init-codes.",
    )
    parser.add_argument("--cycles", type=int, default=32)
    parser.add_argument("--frac", type=int, default=2)
    parser.add_argument("--boost-shift", type=int, default=0)
    parser.add_argument("--boost-after", type=int, default=1)
    parser.add_argument("--track-decay-shift", type=int, default=0)
    parser.add_argument("--min-motion", type=int, default=4)
    parser.add_argument("--tol-code", type=int, default=16)
    parser.add_argument(
        "--late-window-cycles",
        type=int,
        default=8,
        help="Number of final update cycles used for configured tracking boundedness checks.",
    )
    parser.add_argument(
        "--max-late-code-span",
        type=int,
        default=16,
        help="Maximum allowed DCO-code span inside the late configured-tracking window.",
    )
    parser.add_argument(
        "--min-expected-decisions",
        type=int,
        default=1,
        help="Minimum BBPD decisions in the expected initial direction for configured tracking.",
    )
    parser.add_argument(
        "--freq-tol-mhz",
        type=float,
        default=2.0,
        help="Allowed final modeled output-frequency error for target-relative configured-mode checks.",
    )
    parser.add_argument("--phase-wrap-cycles", type=float, default=0.45)
    parser.add_argument(
        "--prefer-measured-within-mhz",
        type=float,
        default=0.5,
        help="Prefer a directly measured DCO code within this frequency error before interpolation.",
    )
    parser.add_argument("--step-ps", type=float, default=5.0)
    parser.add_argument("--sim-time-ns", type=float, default=None)
    parser.add_argument("--timeout-s", type=float, default=120.0)
    parser.add_argument(
        "--require-waveform-quality",
        action="store_true",
        help="Require selected DCO bracket rows to pass duty-cycle and edge-rate limits.",
    )
    parser.add_argument(
        "--min-duty-ratio",
        type=float,
        default=0.35,
        help="Minimum allowed DCO PLLOUT duty ratio when waveform quality is required.",
    )
    parser.add_argument(
        "--max-duty-ratio",
        type=float,
        default=0.65,
        help="Maximum allowed DCO PLLOUT duty ratio when waveform quality is required.",
    )
    parser.add_argument(
        "--max-edge-period-fraction",
        type=float,
        default=0.25,
        help="Maximum allowed 20%%-80%% rise/fall time divided by period.",
    )
    parser.add_argument("--skip-deck-generation", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Reuse existing completed case logs.")
    args = parser.parse_args()

    args.driver = resolve_repo_path(args.driver)
    args.dco_csv = [resolve_repo_path(path) for path in args.dco_csv]
    args.build_dir = resolve_repo_path(args.build_dir)
    args.build_dir.mkdir(parents=True, exist_ok=True)
    args.deck = args.build_dir / "pll_bbpd_yadc_ydac.cir" if args.deck is None else resolve_repo_path(args.deck)

    if not args.driver.exists():
        raise FileNotFoundError(args.driver)
    if args.ref_mhz <= 0.0:
        raise ValueError("--ref-mhz must be positive")
    if args.cycles <= 0:
        raise ValueError("--cycles must be positive")
    if args.late_window_cycles <= 0:
        raise ValueError("--late-window-cycles must be positive")
    if args.max_late_code_span < 0:
        raise ValueError("--max-late-code-span must be non-negative")
    if args.min_expected_decisions < 0:
        raise ValueError("--min-expected-decisions must be non-negative")

    rows = read_dco_rows(args.dco_csv)
    targets: list[dict[str, object]] = []
    for target_mhz in args.targets_mhz:
        multiplier = target_mhz / args.ref_mhz
        multiplier_int = int(round(multiplier))
        if not math.isclose(multiplier, multiplier_int, rel_tol=0.0, abs_tol=1.0e-9):
            raise ValueError(f"target {target_mhz:g} MHz is not an integer multiple of {args.ref_mhz:g} MHz")
        candidates = target_candidates(rows, target_mhz, args)
        if not candidates:
            raise ValueError(f"no measured coarse DCO band brackets {target_mhz:g} MHz")
        best = candidates[0]
        best["target_mhz"] = target_mhz
        best["multiplier"] = multiplier_int
        best["candidate_count"] = len(candidates)
        targets.append(best)

    if not args.skip_deck_generation:
        sim_time_ns = args.sim_time_ns
        if sim_time_ns is None:
            ref_period_ns = 1000.0 / args.ref_mhz
            sim_time_ns = 20.0 + (args.cycles + 2) * ref_period_ns + 10.0
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "xyce_bbpd_cinterface_smoke.py"),
                "--out",
                str(args.deck),
                "--step-ps",
                f"{args.step_ps:g}",
                "--sim-time-ns",
                f"{sim_time_ns:g}",
            ],
            cwd=ROOT,
            check=True,
        )
    elif not args.deck.exists():
        raise FileNotFoundError(args.deck)

    summary_rows: list[dict[str, str]] = []
    detail_rows: list[dict[str, str]] = []
    for target in targets:
        table = band_table(rows, int(target["coarse_code"]))
        init_codes = init_codes_for_target(args, int(target["target_code"]))
        for ki in args.ki_values:
            for kp in args.kp_values:
                for init_code in init_codes:
                    row, details = run_case(args, args.deck, target, table, ki, kp, init_code)
                    summary_rows.append(row)
                    detail_rows.extend(details)

    by_target_gain: dict[tuple[str, str, str], set[str]] = {}
    for row in summary_rows:
        if row["target_pass"] != "1":
            continue
        key = (row["target_mhz"], row["ki"], row["kp"])
        by_target_gain.setdefault(key, set()).add(row["expect"])

    target_results = []
    common_gains: set[tuple[str, str]] | None = None
    for target in targets:
        target_mhz_text = f"{float(target['target_mhz']):.6f}"
        passing_gains = sorted(
            (ki, kp)
            for (mhz, ki, kp), sides in by_target_gain.items()
            if mhz == target_mhz_text and {"increase", "decrease"}.issubset(sides)
        )
        if common_gains is None:
            common_gains = set(passing_gains)
        else:
            common_gains &= set(passing_gains)
        target_results.append(
            {
                "target_mhz": target_mhz_text,
                "multiplier": str(int(target["multiplier"])),
                "coarse_code": str(int(target["coarse_code"])),
                "selected_tap": str(target["selected_tap"]),
                "selection": str(target["selection"]),
                "target_code_est": f"{float(target['code_est']):.3f}",
                "target_code": str(int(target["target_code"])),
                "candidate_count": str(int(target["candidate_count"])),
                "low_duty_ratio": format_optional(target["low_duty_ratio"]),
                "high_duty_ratio": format_optional(target["high_duty_ratio"]),
                "low_rise_period_fraction": format_optional(target["low_rise_period_fraction"]),
                "high_rise_period_fraction": format_optional(target["high_rise_period_fraction"]),
                "low_fall_period_fraction": format_optional(target["low_fall_period_fraction"]),
                "high_fall_period_fraction": format_optional(target["high_fall_period_fraction"]),
                "passing_gain_count": str(len(passing_gains)),
                "passing_gains": ";".join(f"ki{ki}_kp{kp}" for ki, kp in passing_gains),
                "status": "pass" if passing_gains else "fail",
            }
        )

    summary_fields = [
        "case",
        "target_mhz",
        "ref_mhz",
        "multiplier",
        "coarse_code",
        "selected_tap",
        "selection",
        "target_code_est",
        "target_code",
        "ki",
        "kp",
        "frac",
        "boost_shift",
        "boost_after",
        "track_decay_shift",
        "init_code",
        "expect",
        "cycles",
        "min_motion",
        "tol_code",
        "f0_mhz",
        "f64_mhz",
        "f128_mhz",
        "f192_mhz",
        "f255_mhz",
        "returncode",
        "driver_pass",
        "target_pass",
        "final_code",
        "final_freq_mhz",
        "final_freq_abs_error_mhz",
        "late_window_cycles",
        "late_avg_freq_mhz",
        "late_max_freq_abs_error_mhz",
        "late_min_code",
        "late_max_code",
        "late_code_span",
        "max_late_code_span",
        "freq_tol_mhz",
        "final_abs_error",
        "min_abs_error",
        "exact_hit",
        "first_exact_hit_cycle",
        "tol_hit",
        "first_tol_hit_cycle",
        "crossed_target",
        "expected_decisions",
        "min_expected_decisions",
        "resumed",
        "log_path",
    ]
    detail_fields = [
        "case",
        "target_mhz",
        "coarse_code",
        "target_code",
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
    target_fields = [
        "target_mhz",
        "multiplier",
        "coarse_code",
        "selected_tap",
        "selection",
        "target_code_est",
        "target_code",
        "candidate_count",
        "low_duty_ratio",
        "high_duty_ratio",
        "low_rise_period_fraction",
        "high_rise_period_fraction",
        "low_fall_period_fraction",
        "high_fall_period_fraction",
        "passing_gain_count",
        "passing_gains",
        "status",
    ]

    summary_csv = args.build_dir / "pll_25mhz_target_summary.csv"
    detail_csv = args.build_dir / "pll_25mhz_target_cycles.csv"
    target_csv = args.build_dir / "pll_25mhz_target_results.csv"
    summary_json = args.build_dir / "pll_25mhz_target_summary.json"
    write_csv(summary_csv, summary_rows, summary_fields)
    write_csv(detail_csv, detail_rows, detail_fields)
    write_csv(target_csv, target_results, target_fields)

    common_gain_list = sorted(common_gains or set())
    overall_status = "pass" if all(row["status"] == "pass" for row in target_results) else "fail"
    output = {
        "status": overall_status,
        "ref_mhz": args.ref_mhz,
        "targets_mhz": args.targets_mhz,
        "require_waveform_quality": args.require_waveform_quality,
        "min_duty_ratio": args.min_duty_ratio,
        "max_duty_ratio": args.max_duty_ratio,
        "max_edge_period_fraction": args.max_edge_period_fraction,
        "common_passing_gains": [f"ki{ki}_kp{kp}" for ki, kp in common_gain_list],
        "summary_csv": artifact_path_text(summary_csv),
        "detail_csv": artifact_path_text(detail_csv),
        "target_csv": artifact_path_text(target_csv),
        "target_results": target_results,
    }
    summary_json.write_text(json.dumps(output, indent=2) + "\n", encoding="ascii")
    print(json.dumps(output, indent=2))
    return 0 if overall_status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
