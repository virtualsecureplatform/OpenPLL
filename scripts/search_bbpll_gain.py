#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Search BBPLL tracking gains after high-gain acquisition.

This uses the same ideal-BBPD deterministic model as simulate_bbpll_jitter.py,
but starts with an acquisition gain and switches to candidate tracking gains
when a simple BBPD/code-window lock detector fires.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, deque
from pathlib import Path

from simulate_bbpll_jitter import (
    DEFAULT_DCO_TABLE,
    DlfModel,
    Gain,
    dco_freq_mhz,
    decision_name,
    linfit_tie_ps,
    parse_dco_table,
    parse_float_list,
    parse_gain_list,
    stats,
    wrap_phase_s,
)


def parse_int_list(text: str) -> list[int]:
    values = [int(item.strip(), 0) for item in text.split(",") if item.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one integer is required")
    return values


def parse_gain(text: str) -> Gain:
    gains = parse_gain_list(text)
    if len(gains) != 1:
        raise argparse.ArgumentTypeError("expected exactly one KI:KP gain")
    return gains[0]


def decision_value(name: str) -> int:
    if name == "increase":
        return 1
    if name == "decrease":
        return -1
    return 0


def lock_detected(
    decision_window: deque[int],
    code_window: deque[int],
    *,
    lock_window: int,
    lock_code_span: int,
    lock_decision_imbalance: int,
    require_both_dirs: bool,
) -> bool:
    if len(decision_window) < lock_window or len(code_window) < lock_window:
        return False
    if max(code_window) - min(code_window) > lock_code_span:
        return False
    ups = sum(1 for value in decision_window if value > 0)
    dns = sum(1 for value in decision_window if value < 0)
    if require_both_dirs and (ups == 0 or dns == 0):
        return False
    return abs(ups - dns) <= lock_decision_imbalance


def analyze_rows(
    rows: list[dict[str, object]],
    *,
    target_mhz: float,
    ref_mhz: float,
    ndiv: int,
    analysis_start_cycle: int,
) -> dict[str, object]:
    metric_rows = [row for row in rows if int(row["cycle"]) >= analysis_start_cycle]
    target_period_ps = 1.0e6 / target_mhz
    periods_ps: list[float] = []
    period_errors_ps: list[float] = []
    c2c_ps: list[float] = []
    phase_values_ps: list[float] = []
    fdco_values_mhz: list[float] = []
    dco_codes: list[int] = []
    decisions: list[str] = []
    previous_period_ps = math.nan

    for row in metric_rows:
        period_ps = float(row["period_ps"])
        fdco_values_mhz.append(float(row["fdco_mhz"]))
        dco_codes.append(int(row["dco_code"]))
        decisions.append(str(row["decision"]))
        phase_values_ps.append(float(row["phase_ps"]))
        for _ in range(ndiv):
            periods_ps.append(period_ps)
            period_errors_ps.append(period_ps - target_period_ps)
            if math.isfinite(previous_period_ps):
                c2c_ps.append(period_ps - previous_period_ps)
            previous_period_ps = period_ps

    counts = Counter(decisions)
    code_counts = Counter(dco_codes)
    decision_transitions = sum(1 for prev, cur in zip(decisions, decisions[1:]) if prev != cur)
    period_stat = stats(period_errors_ps)
    c2c_stat = stats(c2c_ps)
    phase_stat = stats(phase_values_ps)
    fdco_stat = stats(fdco_values_mhz)
    tie_stat = linfit_tie_ps(periods_ps)

    return {
        "ref_mhz": ref_mhz,
        "target_period_ps": target_period_ps,
        "analysis_start_cycle": analysis_start_cycle,
        "analyzed_ref_cycles": len(metric_rows),
        "expanded_output_cycles": len(periods_ps),
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
        "increase_count": counts["increase"],
        "decrease_count": counts["decrease"],
        "hold_count": counts["hold"],
        "non_hold_density": (counts["increase"] + counts["decrease"]) / max(1, len(decisions)),
        "decision_transition_density": decision_transitions / max(1, len(decisions) - 1),
    }


def simulate_scheduled_case(
    *,
    table: dict[int, float],
    target_mhz: float,
    ref_mhz: float,
    ndiv: int,
    init_code: int,
    phase_ps: float,
    frac: int,
    acquire_gain: Gain,
    track_gain: Gain,
    cycles: int,
    bbpd_deadband_ps: float,
    bbpd_pos_deadband_ps: float | None,
    bbpd_neg_deadband_ps: float | None,
    phase_wrap_cycles: float,
    lock_min_cycle: int,
    lock_window: int,
    lock_code_span: int,
    lock_decision_imbalance: int,
    lock_require_both_dirs: bool,
    switch_settle_cycles: int,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    dlf = DlfModel(init_code=init_code, ki=acquire_gain.ki, kp=acquire_gain.kp, frac=frac)
    tref_s = 1.0 / (ref_mhz * 1.0e6)
    phase_s = wrap_phase_s(phase_ps * 1.0e-12, tref_s, phase_wrap_cycles)
    pos_deadband_ps = bbpd_deadband_ps if bbpd_pos_deadband_ps is None else bbpd_pos_deadband_ps
    neg_deadband_ps = bbpd_deadband_ps if bbpd_neg_deadband_ps is None else bbpd_neg_deadband_ps
    pos_deadband_s = pos_deadband_ps * 1.0e-12
    neg_deadband_s = neg_deadband_ps * 1.0e-12
    decision_window: deque[int] = deque(maxlen=lock_window)
    code_window: deque[int] = deque(maxlen=lock_window)
    rows: list[dict[str, object]] = []
    switch_cycle: int | None = None

    for cycle in range(cycles):
        if (
            switch_cycle is None
            and cycle >= lock_min_cycle
            and lock_detected(
                decision_window,
                code_window,
                lock_window=lock_window,
                lock_code_span=lock_code_span,
                lock_decision_imbalance=lock_decision_imbalance,
                require_both_dirs=lock_require_both_dirs,
            )
        ):
            switch_cycle = cycle
            dlf.ki = track_gain.ki
            dlf.kp = track_gain.kp
            dlf.same_dir_count = 0
            dlf.last_dir = 0

        code_used = dlf.dco_code
        loop_code_used = dlf.loop_code
        fdco_mhz = dco_freq_mhz(table, code_used)
        period_ps = 1.0e6 / fdco_mhz
        if phase_s > pos_deadband_s:
            decision = 1
        elif phase_s < -neg_deadband_s:
            decision = -1
        else:
            decision = 0

        mode = "track" if switch_cycle is not None else "acquire"
        rows.append(
            {
                "case": "",
                "cycle": cycle,
                "mode": mode,
                "ref_ns": cycle * tref_s * 1.0e9,
                "div_ns": cycle * tref_s * 1.0e9 + phase_s * 1.0e9,
                "phase_ps": phase_s * 1.0e12,
                "decision": decision_name(decision),
                "dco_code": code_used,
                "loop_code": loop_code_used,
                "fdco_mhz": fdco_mhz,
                "period_ps": period_ps,
            }
        )

        decision_window.append(decision)
        code_window.append(code_used)
        dlf.update(decision)
        phase_s = wrap_phase_s(
            phase_s + (float(ndiv) / (fdco_mhz * 1.0e6)) - tref_s,
            tref_s,
            phase_wrap_cycles,
        )

    if switch_cycle is None:
        analysis_start_cycle = cycles
        status = "no_lock"
    else:
        analysis_start_cycle = min(cycles, switch_cycle + switch_settle_cycles)
        status = "pass" if analysis_start_cycle < cycles else "no_track_window"

    summary = analyze_rows(
        rows,
        target_mhz=target_mhz,
        ref_mhz=ref_mhz,
        ndiv=ndiv,
        analysis_start_cycle=analysis_start_cycle,
    )
    summary.update(
        {
            "status": status,
            "target_mhz": target_mhz,
            "ndiv": ndiv,
            "init_code": init_code,
            "frac": frac,
            "phase_start_ps": phase_ps,
            "bbpd_deadband_ps": bbpd_deadband_ps,
            "bbpd_pos_deadband_ps": pos_deadband_ps,
            "bbpd_neg_deadband_ps": neg_deadband_ps,
            "acq_ki": acquire_gain.ki,
            "acq_kp": acquire_gain.kp,
            "track_ki": track_gain.ki,
            "track_kp": track_gain.kp,
            "cycles": cycles,
            "switch_cycle": "" if switch_cycle is None else switch_cycle,
            "switch_settle_cycles": switch_settle_cycles,
            "lock_min_cycle": lock_min_cycle,
            "lock_window": lock_window,
            "lock_code_span": lock_code_span,
            "lock_decision_imbalance": lock_decision_imbalance,
            "lock_require_both_dirs": int(lock_require_both_dirs),
        }
    )
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
    parser.add_argument("--frac", type=int, default=8)
    parser.add_argument("--init-codes", type=parse_int_list, default=[117, 121, 125])
    parser.add_argument("--phase-ps-values", type=parse_float_list, default=[-200.0, 0.0, 200.0])
    parser.add_argument("--acquire-gain", type=parse_gain, default=Gain(16, 4))
    parser.add_argument(
        "--track-gains",
        type=parse_gain_list,
        default=parse_gain_list("4:1,8:1,16:1,16:2,16:4,32:1,32:2,64:1,64:2"),
    )
    parser.add_argument("--cycles", type=int, default=120000)
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
    parser.add_argument("--lock-min-cycle", type=int, default=256)
    parser.add_argument("--lock-window", type=int, default=128)
    parser.add_argument("--lock-code-span", type=int, default=4)
    parser.add_argument("--lock-decision-imbalance", type=int, default=32)
    parser.add_argument("--lock-require-both-dirs", action="store_true")
    parser.add_argument("--switch-settle-cycles", type=int, default=4096)
    parser.add_argument("--dco-table", type=parse_dco_table, default=DEFAULT_DCO_TABLE)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("build/pll_jitter_25mhz_500m/scheduled_gain"),
    )
    parser.add_argument("--detail-limit", type=int, default=6)
    args = parser.parse_args()

    if args.cycles <= 0 or args.switch_settle_cycles < 0:
        raise ValueError("cycles must be positive and switch settle must be non-negative")
    if args.lock_window <= 0:
        raise ValueError("lock window must be positive")

    summaries: list[dict[str, object]] = []
    detail_count = 0
    args.out_dir.mkdir(parents=True, exist_ok=True)

    for track_gain in args.track_gains:
        for init_code in args.init_codes:
            for phase_ps in args.phase_ps_values:
                summary, rows = simulate_scheduled_case(
                    table=args.dco_table,
                    target_mhz=args.target_mhz,
                    ref_mhz=args.ref_mhz,
                    ndiv=args.ndiv,
                    init_code=init_code,
                    phase_ps=phase_ps,
                    frac=args.frac,
                    acquire_gain=args.acquire_gain,
                    track_gain=track_gain,
                    cycles=args.cycles,
                    bbpd_deadband_ps=args.bbpd_deadband_ps,
                    bbpd_pos_deadband_ps=args.bbpd_pos_deadband_ps,
                    bbpd_neg_deadband_ps=args.bbpd_neg_deadband_ps,
                    phase_wrap_cycles=args.phase_wrap_cycles,
                    lock_min_cycle=args.lock_min_cycle,
                    lock_window=args.lock_window,
                    lock_code_span=args.lock_code_span,
                    lock_decision_imbalance=args.lock_decision_imbalance,
                    lock_require_both_dirs=args.lock_require_both_dirs,
                    switch_settle_cycles=args.switch_settle_cycles,
                )
                case = (
                    f"target{args.target_mhz:.0f}m_frac{args.frac}_"
                    f"acq{args.acquire_gain.ki}x{args.acquire_gain.kp}_"
                    f"trk{track_gain.ki}x{track_gain.kp}_"
                    f"init{init_code}_phase{phase_ps:+.0f}ps"
                )
                summary["case"] = case
                for row in rows:
                    row["case"] = case
                summaries.append(summary)
                if detail_count < args.detail_limit:
                    write_csv(args.out_dir / f"{case}_cycles.csv", rows)
                    detail_count += 1

    summaries.sort(
        key=lambda row: (
            row["status"] != "pass",
            float(row["tie_rms_ps"]) if math.isfinite(float(row["tie_rms_ps"])) else math.inf,
            float(row["period_jitter_rms_ps"]) if math.isfinite(float(row["period_jitter_rms_ps"])) else math.inf,
        )
    )
    summary_csv = args.out_dir / "scheduled_gain_jitter_summary.csv"
    summary_json = args.out_dir / "scheduled_gain_jitter_summary.json"
    write_csv(summary_csv, summaries)
    summary_json.write_text(json.dumps(summaries, indent=2) + "\n", encoding="ascii")

    print(json.dumps(summaries[: min(12, len(summaries))], indent=2))
    print(f"wrote {summary_csv}")
    print(f"wrote {summary_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
