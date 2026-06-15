#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compute deterministic PLL jitter metrics from mixed-signal cycle logs."""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
from collections import Counter
from pathlib import Path


SUMMARY_RE = re.compile(r"^xyce_pll_mixed_signal_smoke=(\w+)\s+(.*)$")


def to_float(value: str, default: float = math.nan) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def to_int(value: str, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def stats(values: list[float]) -> dict[str, float]:
    if not values:
        return {
            "mean": math.nan,
            "rms": math.nan,
            "min": math.nan,
            "max": math.nan,
            "p2p": math.nan,
        }
    mean = sum(values) / len(values)
    rms = math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))
    low = min(values)
    high = max(values)
    return {
        "mean": mean,
        "rms": rms,
        "min": low,
        "max": high,
        "p2p": high - low,
    }


def linfit_tie_ps(periods_ps: list[float]) -> dict[str, float]:
    if len(periods_ps) < 2:
        return {
            "tie_rms_ps": math.nan,
            "tie_p2p_ps": math.nan,
            "fit_period_ps": math.nan,
        }
    edge_times = []
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
    return {
        "tie_rms_ps": tie_stat["rms"],
        "tie_p2p_ps": tie_stat["p2p"],
        "fit_period_ps": slope,
    }


def parse_summary_tokens(text: str) -> dict[str, str]:
    for line in text.splitlines():
        match = SUMMARY_RE.match(line.strip())
        if not match:
            continue
        result = {"driver_status": match.group(1)}
        for token in match.group(2).split():
            if "=" in token:
                key, value = token.split("=", 1)
                result[key] = value
        return result
    return {}


def read_driver_log(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    header: list[str] | None = None
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line.startswith("cycle,ref_ns,div_ns,"):
            header = line.split(",")
            continue
        if header and re.match(r"^[0-9]+,", line):
            values = line.split(",")
            if len(values) == len(header):
                row = dict(zip(header, values))
                row.setdefault("case", path.stem)
                rows.append(row)
    return rows


def read_cycle_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="ascii") as csv_file:
        return list(csv.DictReader(csv_file))


def analyze_case(
    case: str,
    rows: list[dict[str, str]],
    target_mhz: float,
    ref_mhz: float,
    tail_cycles: int,
) -> dict[str, object]:
    if not rows:
        raise ValueError(f"{case}: no rows")
    rows = sorted(rows, key=lambda row: to_int(row.get("cycle", "0")))
    if tail_cycles > 0:
        tail = rows[-tail_cycles:]
    else:
        tail = rows
    multiplier = int(round(target_mhz / ref_mhz)) if ref_mhz > 0 else 1
    period_target_ps = 1.0e6 / target_mhz

    periods_ps: list[float] = []
    for row in tail:
        fdco_mhz = to_float(row.get("fdco_mhz", ""))
        if not math.isfinite(fdco_mhz) or fdco_mhz <= 0.0:
            continue
        periods_ps.extend([1.0e6 / fdco_mhz] * multiplier)

    period_errors_ps = [period - period_target_ps for period in periods_ps]
    c2c_ps = [
        periods_ps[index] - periods_ps[index - 1]
        for index in range(1, len(periods_ps))
    ]
    phase_ps = [to_float(row.get("phase_ps", "")) for row in tail]
    phase_ps = [value for value in phase_ps if math.isfinite(value)]
    fdco_values = [
        to_float(row.get("fdco_mhz", ""))
        for row in tail
        if math.isfinite(to_float(row.get("fdco_mhz", "")))
    ]
    dco_codes = [to_int(row.get("dco_code", "0")) for row in tail]
    decisions = [row.get("decision", "hold") for row in tail]
    counts = Counter(decisions)
    code_counts = Counter(dco_codes)
    decision_transitions = sum(
        1 for prev, cur in zip(decisions, decisions[1:]) if prev != cur
    )
    non_hold = counts["increase"] + counts["decrease"]

    period_stat = stats(period_errors_ps)
    c2c_stat = stats(c2c_ps)
    phase_stat = stats(phase_ps)
    fdco_stat = stats(fdco_values)
    tie_stat = linfit_tie_ps(periods_ps)

    return {
        "case": case,
        "target_mhz": target_mhz,
        "ref_mhz": ref_mhz,
        "multiplier": multiplier,
        "analyzed_ref_cycles": len(tail),
        "expanded_output_cycles": len(periods_ps),
        "target_period_ps": period_target_ps,
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
        "dco_code_min": min(dco_codes),
        "dco_code_max": max(dco_codes),
        "dco_code_span": max(dco_codes) - min(dco_codes),
        "dco_code_hist": " ".join(
            f"{code}:{count}" for code, count in sorted(code_counts.items())
        ),
        "increase_count": counts["increase"],
        "decrease_count": counts["decrease"],
        "hold_count": counts["hold"],
        "non_hold_density": non_hold / len(tail),
        "up_down_density": (counts["increase"] + counts["decrease"]) / len(tail),
        "decision_transition_density": decision_transitions / max(1, len(tail) - 1),
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        return
    fields = list(rows[0])
    with path.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--target-mhz", type=float, default=math.nan)
    parser.add_argument("--ref-mhz", type=float, default=25.0)
    parser.add_argument("--tail-cycles", type=int, default=128)
    parser.add_argument("--out-csv", type=Path, default=Path("build/pll_jitter_25mhz_500m/jitter_summary.csv"))
    parser.add_argument("--out-json", type=Path, default=Path("build/pll_jitter_25mhz_500m/jitter_summary.json"))
    args = parser.parse_args()

    summaries: list[dict[str, object]] = []
    for path in args.inputs:
        path = path.expanduser()
        if not path.is_file():
            raise FileNotFoundError(path)
        if path.suffix == ".csv":
            rows = read_cycle_csv(path)
            groups: dict[str, list[dict[str, str]]] = {}
            for row in rows:
                groups.setdefault(row.get("case", path.stem), []).append(row)
            for case, group in sorted(groups.items()):
                target_mhz = to_float(group[0].get("target_mhz", ""), args.target_mhz)
                ref_mhz = args.ref_mhz
                summaries.append(analyze_case(case, group, target_mhz, ref_mhz, args.tail_cycles))
        else:
            text = path.read_text(encoding="utf-8", errors="replace")
            meta = parse_summary_tokens(text)
            rows = read_driver_log(path)
            target_mhz = to_float(meta.get("target_mhz", ""), args.target_mhz)
            ref_mhz = to_float(meta.get("ref_mhz", ""), args.ref_mhz)
            if not math.isfinite(target_mhz):
                raise ValueError(f"{path}: target MHz missing; pass --target-mhz")
            summary = analyze_case(path.stem, rows, target_mhz, ref_mhz, args.tail_cycles)
            summary.update(
                {
                    "driver_status": meta.get("driver_status", ""),
                    "driver_final_code": to_int(meta.get("final_code", "")),
                    "driver_expected_decisions": to_int(meta.get("expected_decisions", "")),
                    "source": str(path),
                }
            )
            summaries.append(summary)

    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    write_csv(args.out_csv, summaries)
    args.out_json.write_text(json.dumps(summaries, indent=2) + "\n", encoding="ascii")
    print(json.dumps(summaries, indent=2))
    print(f"wrote {args.out_csv}")
    print(f"wrote {args.out_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
