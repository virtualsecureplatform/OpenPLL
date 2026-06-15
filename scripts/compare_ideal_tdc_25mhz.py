#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compare tuned BBPD and ideal-TDC control for the 25 MHz configured PLL."""

from __future__ import annotations

import argparse
import csv
import json
from dataclasses import dataclass
from pathlib import Path

from simulate_bbpll_jitter import Gain, simulate_case


@dataclass(frozen=True)
class Mode:
    target_mhz: float
    ndiv: int
    init_code: int
    bbpd_gain: Gain
    table: dict[int, float]


MODES = (
    Mode(100.0, 4, 93, Gain(16, 8), {0: 98.609, 128: 100.515, 255: 101.817}),
    Mode(
        250.0,
        10,
        234,
        Gain(16, 8),
        {0: 231.778, 128: 243.384, 192: 249.187, 224: 249.756, 234: 249.813, 255: 250.488},
    ),
    Mode(
        300.0,
        12,
        90,
        Gain(16, 2),
        {0: 285.172, 64: 295.760, 96: 301.054, 128: 304.371, 160: 308.390, 255: 320.321},
    ),
    Mode(
        400.0,
        16,
        76,
        Gain(1, 4),
        {0: 385.207, 32: 390.628, 64: 397.373, 96: 404.357, 128: 411.194, 192: 425.984, 255: 438.705},
    ),
    Mode(500.0, 20, 121, Gain(16, 5), {0: 468.489, 128: 501.912, 255: 546.363}),
)


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


def worst_phase_summary(
    mode: Mode,
    *,
    detector: str,
    gain: Gain,
    frac: int,
    cycles: int,
    discard_cycles: int,
    phases_ps: list[float],
    bbpd_deadband_ps: float,
    tdc_lsb_ps: float,
    tdc_max_code: int,
) -> dict[str, object]:
    phase_rows = []
    for phase_ps in phases_ps:
        summary, _ = simulate_case(
            table=mode.table,
            target_mhz=mode.target_mhz,
            ref_mhz=25.0,
            ndiv=mode.ndiv,
            init_code=mode.init_code,
            gain=gain,
            frac=frac,
            cycles=cycles,
            discard_cycles=discard_cycles,
            phase_ps=phase_ps,
            bbpd_deadband_ps=bbpd_deadband_ps,
            bbpd_pos_deadband_ps=None,
            bbpd_neg_deadband_ps=None,
            detector=detector,
            tdc_lsb_ps=tdc_lsb_ps,
            tdc_max_code=tdc_max_code,
            phase_wrap_cycles=0.5,
            boost_shift=0,
            boost_after=3,
            collect_rows=False,
        )
        phase_rows.append(summary)

    worst_tie = max(float(row["tie_rms_ps"]) for row in phase_rows)
    worst_period = max(float(row["period_jitter_rms_ps"]) for row in phase_rows)
    worst_c2c = max(float(row["cycle_to_cycle_rms_ps"]) for row in phase_rows)
    worst_phase = max(float(row["phase_error_rms_ps"]) for row in phase_rows)
    tie_row = max(phase_rows, key=lambda row: float(row["tie_rms_ps"]))
    period_row = max(phase_rows, key=lambda row: float(row["period_jitter_rms_ps"]))
    max_code_span = max(int(row["dco_code_span"]) for row in phase_rows)
    max_non_hold_density = max(float(row["non_hold_density"]) for row in phase_rows)

    return {
        "target_mhz": mode.target_mhz,
        "detector": detector,
        "ki": gain.ki,
        "kp": gain.kp,
        "frac": frac,
        "tdc_lsb_ps": tdc_lsb_ps if detector == "tdc" else "",
        "tdc_max_code": tdc_max_code if detector == "tdc" else "",
        "cycles": cycles,
        "discard_cycles": discard_cycles,
        "worst_tie_rms_ps": worst_tie,
        "worst_period_jitter_rms_ps": worst_period,
        "worst_c2c_rms_ps": worst_c2c,
        "worst_phase_error_rms_ps": worst_phase,
        "tie_worst_start_ps": tie_row["phase_start_ps"],
        "period_worst_start_ps": period_row["phase_start_ps"],
        "max_code_span": max_code_span,
        "max_non_hold_density": max_non_hold_density,
        "fdco_mean_mhz_at_worst_tie": tie_row["fdco_mean_mhz"],
    }


def pct_improvement(old: float, new: float) -> float:
    return 100.0 * (old - new) / old if old else 0.0


def candidate_row(
    label: str,
    baseline: dict[str, object],
    candidate: dict[str, object],
) -> dict[str, object]:
    base_tie = float(baseline["worst_tie_rms_ps"])
    base_period = float(baseline["worst_period_jitter_rms_ps"])
    return {
        "target_mhz": baseline["target_mhz"],
        "selection": label,
        "baseline_gain": f"{baseline['ki']}:{baseline['kp']}",
        "tdc_gain": f"{candidate['ki']}:{candidate['kp']}",
        "tdc_lsb_ps": candidate["tdc_lsb_ps"],
        "tdc_max_code": candidate["tdc_max_code"],
        "baseline_tie_rms_ps": base_tie,
        "tdc_tie_rms_ps": candidate["worst_tie_rms_ps"],
        "tie_improvement_pct": pct_improvement(base_tie, float(candidate["worst_tie_rms_ps"])),
        "baseline_period_jitter_rms_ps": base_period,
        "tdc_period_jitter_rms_ps": candidate["worst_period_jitter_rms_ps"],
        "period_improvement_pct": pct_improvement(base_period, float(candidate["worst_period_jitter_rms_ps"])),
        "baseline_c2c_rms_ps": baseline["worst_c2c_rms_ps"],
        "tdc_c2c_rms_ps": candidate["worst_c2c_rms_ps"],
        "baseline_code_span": baseline["max_code_span"],
        "tdc_code_span": candidate["max_code_span"],
        "baseline_non_hold_density": baseline["max_non_hold_density"],
        "tdc_non_hold_density": candidate["max_non_hold_density"],
        "verify_cycles": candidate["cycles"],
        "discard_cycles": candidate["discard_cycles"],
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="ascii")
        return
    with path.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--search-cycles", type=int, default=20000)
    parser.add_argument("--verify-cycles", type=int, default=80000)
    parser.add_argument("--discard-cycles", type=int, default=4000)
    parser.add_argument("--verify-discard-cycles", type=int, default=10000)
    parser.add_argument("--phase-ps-values", type=parse_float_list, default=parse_float_list("-100,0,100"))
    parser.add_argument("--tdc-lsb-ps-values", type=parse_float_list, default=parse_float_list("5,10,20,40"))
    parser.add_argument("--tdc-max-code-values", type=parse_int_list, default=parse_int_list("4,8,16"))
    parser.add_argument("--ki-values", type=parse_int_list, default=parse_int_list("0,1,2,4,8,16"))
    parser.add_argument("--kp-values", type=parse_int_list, default=parse_int_list("0,1,2,4"))
    parser.add_argument("--frac", type=int, default=8)
    parser.add_argument("--bbpd-deadband-ps", type=float, default=40.0)
    parser.add_argument("--out-dir", type=Path, default=Path("build/jitter_compare_25mhz_ideal_tdc"))
    args = parser.parse_args()

    if args.search_cycles <= args.discard_cycles:
        raise ValueError("--search-cycles must exceed --discard-cycles")
    if args.verify_cycles <= args.verify_discard_cycles:
        raise ValueError("--verify-cycles must exceed --verify-discard-cycles")

    search_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    verified_rows: list[dict[str, object]] = []

    for mode in MODES:
        baseline_search = worst_phase_summary(
            mode,
            detector="bbpd",
            gain=mode.bbpd_gain,
            frac=args.frac,
            cycles=args.search_cycles,
            discard_cycles=args.discard_cycles,
            phases_ps=args.phase_ps_values,
            bbpd_deadband_ps=args.bbpd_deadband_ps,
            tdc_lsb_ps=10.0,
            tdc_max_code=8,
        )
        candidates = []
        for tdc_lsb_ps in args.tdc_lsb_ps_values:
            for tdc_max_code in args.tdc_max_code_values:
                for ki in args.ki_values:
                    for kp in args.kp_values:
                        if ki == 0 and kp == 0:
                            continue
                        row = worst_phase_summary(
                            mode,
                            detector="tdc",
                            gain=Gain(ki, kp),
                            frac=args.frac,
                            cycles=args.search_cycles,
                            discard_cycles=args.discard_cycles,
                            phases_ps=args.phase_ps_values,
                            bbpd_deadband_ps=args.bbpd_deadband_ps,
                            tdc_lsb_ps=tdc_lsb_ps,
                            tdc_max_code=tdc_max_code,
                        )
                        candidates.append(row)
                        search_rows.append(row)

        eligible = [
            row
            for row in candidates
            if float(row["worst_tie_rms_ps"]) <= float(baseline_search["worst_tie_rms_ps"])
            and float(row["worst_period_jitter_rms_ps"])
            <= float(baseline_search["worst_period_jitter_rms_ps"])
        ]
        selected = {
            "best_tie": min(candidates, key=lambda row: float(row["worst_tie_rms_ps"])),
            "best_period": min(candidates, key=lambda row: float(row["worst_period_jitter_rms_ps"])),
        }
        if eligible:
            selected["best_both"] = min(
                eligible,
                key=lambda row: (
                    float(row["worst_period_jitter_rms_ps"]),
                    float(row["worst_tie_rms_ps"]),
                ),
            )

        baseline_verify = worst_phase_summary(
            mode,
            detector="bbpd",
            gain=mode.bbpd_gain,
            frac=args.frac,
            cycles=args.verify_cycles,
            discard_cycles=args.verify_discard_cycles,
            phases_ps=args.phase_ps_values,
            bbpd_deadband_ps=args.bbpd_deadband_ps,
            tdc_lsb_ps=10.0,
            tdc_max_code=8,
        )
        verified_rows.append(baseline_verify)
        seen = set()
        for label, row in selected.items():
            key = (int(row["ki"]), int(row["kp"]), float(row["tdc_lsb_ps"]), int(row["tdc_max_code"]))
            if key in seen:
                continue
            seen.add(key)
            verify = worst_phase_summary(
                mode,
                detector="tdc",
                gain=Gain(key[0], key[1]),
                frac=args.frac,
                cycles=args.verify_cycles,
                discard_cycles=args.verify_discard_cycles,
                phases_ps=args.phase_ps_values,
                bbpd_deadband_ps=args.bbpd_deadband_ps,
                tdc_lsb_ps=key[2],
                tdc_max_code=key[3],
            )
            verified_rows.append(verify)
            summary_rows.append(candidate_row(label, baseline_verify, verify))

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_dir / "tdc_search_rows.csv", search_rows)
    write_csv(args.out_dir / "tdc_verified_rows.csv", verified_rows)
    write_csv(args.out_dir / "tdc_compare_summary.csv", summary_rows)
    (args.out_dir / "tdc_compare_summary.json").write_text(
        json.dumps(summary_rows, indent=2) + "\n",
        encoding="ascii",
    )

    print(json.dumps(summary_rows, indent=2))
    print(f"wrote {args.out_dir / 'tdc_compare_summary.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
