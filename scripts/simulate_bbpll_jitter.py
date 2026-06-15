#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Simulate deterministic PLL control jitter with an ideal BBPD or TDC.

This is a fast sampled model for loop-gain and detector selection. It
intentionally excludes device noise, supply noise, and extracted interconnect
effects; those require transistor-level transient/noise simulation or silicon
measurement.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path


DEFAULT_DCO_TABLE = {
    0: 468.488964,
    64: 485.200510,
    128: 501.912055,
    192: 524.312777,
    255: 546.363489,
}


@dataclass(frozen=True)
class Gain:
    ki: int
    kp: int


@dataclass
class DlfModel:
    init_code: int
    ki: int
    kp: int
    frac: int
    code_width: int = 10
    dco_code_width: int = 8
    boost_shift: int = 0
    boost_after: int = 3

    def __post_init__(self) -> None:
        self.code_shift = self.code_width - self.dco_code_width
        self.max_code = (1 << self.code_width) - 1
        self.max_acc = self.max_code << self.frac
        self.acc = (self.init_code << self.code_shift) << self.frac
        self.dco_code = self.init_code
        self.loop_code = self.init_code << self.code_shift
        self.last_dir = 0
        self.same_dir_count = 0

    def update(self, detector_code: int) -> None:
        direction = 1 if detector_code > 0 else -1 if detector_code < 0 else 0
        if direction == 0:
            self.same_dir_count = 0
            self.last_dir = 0
            self.loop_code = int(self.acc >> self.frac)
            self.dco_code = clamp_int(self.loop_code >> self.code_shift, 0, 255)
            return

        if direction == self.last_dir:
            self.same_dir_count += 1
        else:
            self.last_dir = direction
            self.same_dir_count = 1

        ki_eff = self.ki
        if self.boost_shift > 0 and self.same_dir_count >= self.boost_after:
            ki_eff <<= self.boost_shift

        self.acc = clamp_int(self.acc + detector_code * ki_eff, 0, self.max_acc)
        integ_code = int(self.acc >> self.frac)
        self.loop_code = clamp_int(integ_code + detector_code * self.kp, 0, self.max_code)
        self.dco_code = clamp_int(self.loop_code >> self.code_shift, 0, 255)


def clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def parse_gain_list(text: str) -> list[Gain]:
    gains = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise argparse.ArgumentTypeError(f"gain must be KI:KP, got {item!r}")
        ki_text, kp_text = item.split(":", 1)
        gains.append(Gain(int(ki_text, 0), int(kp_text, 0)))
    if not gains:
        raise argparse.ArgumentTypeError("at least one gain is required")
    return gains


def parse_float_list(text: str) -> list[float]:
    values = [float(item.strip()) for item in text.split(",") if item.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one value is required")
    return values


def parse_dco_table(text: str) -> dict[int, float]:
    table: dict[int, float] = {}
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        if ":" not in item:
            raise argparse.ArgumentTypeError(f"DCO point must be CODE:MHz, got {item!r}")
        code_text, freq_text = item.split(":", 1)
        code = int(code_text, 0)
        if code < 0 or code > 255:
            raise argparse.ArgumentTypeError(f"DCO code out of range: {code}")
        table[code] = float(freq_text)
    if len(table) < 2:
        raise argparse.ArgumentTypeError("at least two DCO table points are required")
    return table


def dco_freq_mhz(table: dict[int, float], code: int) -> float:
    code = clamp_int(code, 0, 255)
    points = sorted(table.items())
    if code <= points[0][0]:
        return points[0][1]
    if code >= points[-1][0]:
        return points[-1][1]
    for (code0, freq0), (code1, freq1) in zip(points, points[1:]):
        if code0 <= code <= code1:
            if code1 == code0:
                return freq0
            frac = (code - code0) / (code1 - code0)
            return freq0 + frac * (freq1 - freq0)
    return points[-1][1]


def wrap_phase_s(phase_s: float, period_s: float, wrap_cycles: float) -> float:
    if wrap_cycles <= 0.0:
        return phase_s
    limit_s = wrap_cycles * period_s
    while phase_s > limit_s:
        phase_s -= period_s
    while phase_s < -limit_s:
        phase_s += period_s
    return phase_s


def stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {"mean": math.nan, "rms": math.nan, "min": math.nan, "max": math.nan, "p2p": math.nan}
    mean = sum(values) / len(values)
    rms = math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))
    low = min(values)
    high = max(values)
    return {"mean": mean, "rms": rms, "min": low, "max": high, "p2p": high - low}


def linfit_tie_ps(periods_ps: list[float]) -> dict[str, float]:
    if len(periods_ps) < 2:
        return {"tie_rms_ps": math.nan, "tie_p2p_ps": math.nan, "fit_period_ps": math.nan}
    edge_times: list[float] = []
    acc = 0.0
    for period in periods_ps:
        acc += period
        edge_times.append(acc)
    n = len(edge_times)
    x_mean = (n - 1) / 2.0
    y_mean = sum(edge_times) / n
    denom = sum((idx - x_mean) ** 2 for idx in range(n))
    slope = sum((idx - x_mean) * (edge_times[idx] - y_mean) for idx in range(n)) / denom
    intercept = y_mean - slope * x_mean
    tie = [edge_times[idx] - (intercept + slope * idx) for idx in range(n)]
    tie_stat = stats(tie)
    return {"tie_rms_ps": tie_stat["rms"], "tie_p2p_ps": tie_stat["p2p"], "fit_period_ps": slope}


def decision_name(decision: int) -> str:
    if decision > 0:
        return "increase"
    if decision < 0:
        return "decrease"
    return "hold"


def quantize_tdc_code(phase_ps: float, tdc_lsb_ps: float, tdc_max_code: int) -> int:
    if tdc_lsb_ps <= 0.0:
        raise ValueError("tdc_lsb_ps must be positive")
    if phase_ps == 0.0:
        return 0
    magnitude = int(math.floor(abs(phase_ps) / tdc_lsb_ps + 0.5))
    if tdc_max_code > 0:
        magnitude = min(magnitude, tdc_max_code)
    if magnitude == 0:
        return 0
    return magnitude if phase_ps > 0.0 else -magnitude


def simulate_case(
    *,
    table: dict[int, float],
    target_mhz: float,
    ref_mhz: float,
    ndiv: int,
    init_code: int,
    gain: Gain,
    frac: int,
    cycles: int,
    discard_cycles: int,
    phase_ps: float,
    bbpd_deadband_ps: float,
    bbpd_pos_deadband_ps: float | None,
    bbpd_neg_deadband_ps: float | None,
    detector: str = "bbpd",
    tdc_lsb_ps: float = 10.0,
    tdc_max_code: int = 8,
    phase_wrap_cycles: float,
    boost_shift: int,
    boost_after: int,
    collect_rows: bool = True,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    dlf = DlfModel(
        init_code=init_code,
        ki=gain.ki,
        kp=gain.kp,
        frac=frac,
        boost_shift=boost_shift,
        boost_after=boost_after,
    )
    tref_s = 1.0 / (ref_mhz * 1.0e6)
    target_period_ps = 1.0e6 / target_mhz
    phase_s = wrap_phase_s(phase_ps * 1.0e-12, tref_s, phase_wrap_cycles)
    pos_deadband_ps = bbpd_deadband_ps if bbpd_pos_deadband_ps is None else bbpd_pos_deadband_ps
    neg_deadband_ps = bbpd_deadband_ps if bbpd_neg_deadband_ps is None else bbpd_neg_deadband_ps
    pos_deadband_s = pos_deadband_ps * 1.0e-12
    neg_deadband_s = neg_deadband_ps * 1.0e-12
    if detector not in ("bbpd", "tdc"):
        raise ValueError(f"unsupported detector: {detector}")

    rows: list[dict[str, object]] = []
    period_errors_ps: list[float] = []
    periods_ps: list[float] = []
    c2c_ps: list[float] = []
    phase_values_ps: list[float] = []
    fdco_values_mhz: list[float] = []
    dco_codes: list[int] = []
    decisions: list[str] = []
    detector_codes: list[int] = []
    previous_period_ps = math.nan

    for cycle in range(cycles):
        code_used = dlf.dco_code
        loop_code_used = dlf.loop_code
        fdco_mhz = dco_freq_mhz(table, code_used)
        period_ps = 1.0e6 / fdco_mhz

        phase_now_ps = phase_s * 1.0e12
        if detector == "bbpd":
            if phase_s > pos_deadband_s:
                detector_code = 1
            elif phase_s < -neg_deadband_s:
                detector_code = -1
            else:
                detector_code = 0
        else:
            detector_code = quantize_tdc_code(phase_now_ps, tdc_lsb_ps, tdc_max_code)

        if collect_rows:
            row = {
                "case": "",
                "cycle": cycle,
                "ref_ns": cycle * tref_s * 1.0e9,
                "div_ns": cycle * tref_s * 1.0e9 + phase_s * 1.0e9,
                "phase_ps": phase_now_ps,
                "detector_code": detector_code,
                "decision": decision_name(detector_code),
                "dco_code": code_used,
                "loop_code": loop_code_used,
                "fdco_mhz": fdco_mhz,
                "period_ps": period_ps,
            }
            rows.append(row)

        if cycle >= discard_cycles:
            fdco_values_mhz.append(fdco_mhz)
            dco_codes.append(code_used)
            decisions.append(decision_name(detector_code))
            detector_codes.append(detector_code)
            phase_values_ps.append(phase_now_ps)
            for _ in range(ndiv):
                periods_ps.append(period_ps)
                period_errors_ps.append(period_ps - target_period_ps)
                if math.isfinite(previous_period_ps):
                    c2c_ps.append(period_ps - previous_period_ps)
                previous_period_ps = period_ps

        dlf.update(detector_code)
        phase_s = wrap_phase_s(
            phase_s + (float(ndiv) / (fdco_mhz * 1.0e6)) - tref_s,
            tref_s,
            phase_wrap_cycles,
        )

    counts = Counter(decisions)
    code_counts = Counter(dco_codes)
    period_stat = stats(period_errors_ps)
    c2c_stat = stats(c2c_ps)
    phase_stat = stats(phase_values_ps)
    fdco_stat = stats(fdco_values_mhz)
    detector_code_stat = stats([float(code) for code in detector_codes])
    tie_stat = linfit_tie_ps(periods_ps)
    decision_transitions = sum(1 for prev, cur in zip(decisions, decisions[1:]) if prev != cur)

    summary: dict[str, object] = {
        "target_mhz": target_mhz,
        "ref_mhz": ref_mhz,
        "ndiv": ndiv,
        "init_code": init_code,
        "ki": gain.ki,
        "kp": gain.kp,
        "frac": frac,
        "detector": detector,
        "phase_start_ps": phase_ps,
        "bbpd_deadband_ps": bbpd_deadband_ps,
        "bbpd_pos_deadband_ps": pos_deadband_ps,
        "bbpd_neg_deadband_ps": neg_deadband_ps,
        "tdc_lsb_ps": tdc_lsb_ps if detector == "tdc" else "",
        "tdc_max_code": tdc_max_code if detector == "tdc" else "",
        "cycles": cycles,
        "discard_cycles": discard_cycles,
        "analyzed_ref_cycles": max(0, cycles - discard_cycles),
        "expanded_output_cycles": len(periods_ps),
        "target_period_ps": target_period_ps,
        "mean_period_error_ps": period_stat["mean"],
        "period_jitter_rms_ps": period_stat["rms"],
        "period_jitter_p2p_ps": period_stat["p2p"],
        "cycle_to_cycle_rms_ps": c2c_stat["rms"],
        "cycle_to_cycle_p2p_ps": c2c_stat["p2p"],
        "tie_rms_ps": tie_stat["tie_rms_ps"],
        "tie_p2p_ps": tie_stat["tie_p2p_ps"],
        "fit_period_ps": tie_stat["fit_period_ps"],
        "phase_error_rms_ps": phase_stat["rms"],
        "phase_error_p2p_ps": phase_stat["p2p"],
        "fdco_mean_mhz": fdco_stat["mean"],
        "fdco_p2p_mhz": fdco_stat["p2p"],
        "dco_code_min": min(dco_codes) if dco_codes else math.nan,
        "dco_code_max": max(dco_codes) if dco_codes else math.nan,
        "dco_code_span": (max(dco_codes) - min(dco_codes)) if dco_codes else math.nan,
        "dco_code_hist": " ".join(f"{code}:{count}" for code, count in sorted(code_counts.items())),
        "detector_code_rms": detector_code_stat["rms"],
        "detector_code_p2p": detector_code_stat["p2p"],
        "increase_count": counts["increase"],
        "decrease_count": counts["decrease"],
        "hold_count": counts["hold"],
        "non_hold_density": (counts["increase"] + counts["decrease"]) / max(1, len(decisions)),
        "decision_transition_density": decision_transitions / max(1, len(decisions) - 1),
    }
    return summary, rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0])
    with path.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-mhz", type=float, default=500.0)
    parser.add_argument("--ref-mhz", type=float, default=25.0)
    parser.add_argument("--ndiv", type=int, default=20)
    parser.add_argument("--init-code", type=int, default=121)
    parser.add_argument("--frac-values", type=parse_float_list, default=[8.0])
    parser.add_argument(
        "--gains",
        type=parse_gain_list,
        default=parse_gain_list("4:0,8:0,16:0,16:1,16:2,16:4,32:1,32:2,64:4"),
        help="Comma-separated KI:KP pairs.",
    )
    parser.add_argument("--cycles", type=int, default=100000)
    parser.add_argument("--discard-cycles", type=int, default=10000)
    parser.add_argument("--phase-ps-values", type=parse_float_list, default=[0.0, 100.0, -100.0])
    parser.add_argument(
        "--detector",
        choices=("bbpd", "tdc"),
        default="bbpd",
        help="Phase detector model.",
    )
    parser.add_argument("--bbpd-deadband-ps", type=float, default=40.0)
    parser.add_argument(
        "--bbpd-pos-deadband-ps",
        type=float,
        default=None,
        help="Positive-phase REF-leading BBPD threshold. Defaults to --bbpd-deadband-ps.",
    )
    parser.add_argument(
        "--bbpd-neg-deadband-ps",
        type=float,
        default=None,
        help="Negative-phase feedback-leading BBPD threshold magnitude. Defaults to --bbpd-deadband-ps.",
    )
    parser.add_argument("--phase-wrap-cycles", type=float, default=0.5)
    parser.add_argument("--tdc-lsb-ps", type=float, default=10.0)
    parser.add_argument(
        "--tdc-max-code",
        type=int,
        default=8,
        help="Maximum absolute TDC output code. Use 0 for no saturation.",
    )
    parser.add_argument("--boost-shift", type=int, default=0)
    parser.add_argument("--boost-after", type=int, default=3)
    parser.add_argument(
        "--dco-table",
        type=parse_dco_table,
        default=DEFAULT_DCO_TABLE,
        help="Comma-separated CODE:MHz DCO calibration points.",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("build/pll_jitter_25mhz_500m/ideal_bbpd"),
    )
    parser.add_argument("--detail-limit", type=int, default=3)
    args = parser.parse_args()

    if args.ndiv <= 0 or args.target_mhz <= 0.0 or args.ref_mhz <= 0.0:
        raise ValueError("target/ref/ndiv must be positive")
    if args.cycles <= args.discard_cycles or args.discard_cycles < 0:
        raise ValueError("--cycles must be greater than --discard-cycles")

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, object]] = []
    detail_count = 0

    for frac_value in args.frac_values:
        frac = int(frac_value)
        for gain in args.gains:
            for phase_ps in args.phase_ps_values:
                summary, rows = simulate_case(
                    table=args.dco_table,
                    target_mhz=args.target_mhz,
                    ref_mhz=args.ref_mhz,
                    ndiv=args.ndiv,
                    init_code=args.init_code,
                    gain=gain,
                    frac=frac,
                    cycles=args.cycles,
                    discard_cycles=args.discard_cycles,
                    phase_ps=phase_ps,
                    bbpd_deadband_ps=args.bbpd_deadband_ps,
                    bbpd_pos_deadband_ps=args.bbpd_pos_deadband_ps,
                    bbpd_neg_deadband_ps=args.bbpd_neg_deadband_ps,
                    detector=args.detector,
                    tdc_lsb_ps=args.tdc_lsb_ps,
                    tdc_max_code=args.tdc_max_code,
                    phase_wrap_cycles=args.phase_wrap_cycles,
                    boost_shift=args.boost_shift,
                    boost_after=args.boost_after,
                    collect_rows=detail_count < args.detail_limit,
                )
                case = (
                    f"target{args.target_mhz:.0f}m_{args.detector}_frac{frac}"
                    f"_ki{gain.ki}_kp{gain.kp}_phase{phase_ps:+.0f}ps"
                )
                summary["case"] = case
                for row in rows:
                    row["case"] = case
                summaries.append(summary)
                if detail_count < args.detail_limit:
                    write_csv(out_dir / f"{case}_cycles.csv", rows)
                    detail_count += 1

    summaries.sort(
        key=lambda row: (
            int(row["frac"]),
            float(row["tie_rms_ps"]),
            float(row["tie_p2p_ps"]),
            float(row["period_jitter_rms_ps"]),
        )
    )
    summary_csv = out_dir / f"ideal_{args.detector}_jitter_summary.csv"
    summary_json = out_dir / f"ideal_{args.detector}_jitter_summary.json"
    write_csv(summary_csv, summaries)
    summary_json.write_text(json.dumps(summaries, indent=2) + "\n", encoding="ascii")

    print(json.dumps(summaries[: min(10, len(summaries))], indent=2))
    print(f"wrote {summary_csv}")
    print(f"wrote {summary_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
