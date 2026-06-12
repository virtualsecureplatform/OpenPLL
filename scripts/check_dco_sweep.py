#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import json
import statistics
import sys
from pathlib import Path


def parse_int_set(text):
    if text == "all":
        return set(range(256))
    values = set()
    for item in text.split(","):
        item = item.strip()
        if item:
            values.add(int(item, 0))
    return values


def parse_corner_set(text):
    return {item.strip() for item in text.split(",") if item.strip()}


def as_int(row, name):
    try:
        return int(row[name])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid {name} in row: {row}") from exc


def as_float(row, name):
    try:
        return float(row[name])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid {name} in row: {row}") from exc


def enabled_load_count(code, therm_invert):
    return 255 - code if therm_invert else code


def read_rows(path):
    with path.open(newline="", encoding="ascii") as csv_file:
        return list(csv.DictReader(csv_file))


def check_rows(rows, expected_codes, expected_corners, min_span_mhz, min_step_mhz):
    if not rows:
        raise ValueError("DCO sweep CSV has no rows")

    present_corners = {row.get("corner", "") for row in rows}
    missing_corners = sorted(expected_corners - present_corners)
    if missing_corners:
        raise ValueError(f"missing expected corners: {missing_corners}")

    failed_rows = [row for row in rows if row.get("status") != "pass"]
    if failed_rows:
        examples = ", ".join(f"{row.get('corner')}:{row.get('code')}" for row in failed_rows[:8])
        raise ValueError(f"{len(failed_rows)} DCO sweep rows failed; examples: {examples}")

    by_corner = {}
    for row in rows:
        corner = row["corner"]
        code = as_int(row, "code")
        therm_invert = as_int(row, "therm_invert")
        if therm_invert not in (0, 1):
            raise ValueError(f"{corner}:{code} has invalid therm_invert={therm_invert}")
        expected_loads = enabled_load_count(code, bool(therm_invert))
        loads = as_int(row, "enabled_loads")
        if loads != expected_loads:
            raise ValueError(
                f"{corner}:{code} enabled_loads={loads}, expected {expected_loads}"
            )
        period_s = as_float(row, "period_s")
        freq_hz = as_float(row, "freq_hz")
        freq_mhz = as_float(row, "freq_mhz")
        if period_s <= 0 or freq_hz <= 0 or freq_mhz <= 0:
            raise ValueError(f"{corner}:{code} has non-positive period/frequency")
        by_corner.setdefault(corner, []).append(
            {
                "corner": corner,
                "code": code,
                "therm_invert": therm_invert,
                "enabled_loads": loads,
                "period_s": period_s,
                "freq_hz": freq_hz,
                "freq_mhz": freq_mhz,
            }
        )

    summary_rows = []
    global_min = None
    global_max = None
    for corner in sorted(expected_corners):
        corner_rows = sorted(by_corner.get(corner, []), key=lambda row: row["code"])
        present_codes = {row["code"] for row in corner_rows}
        missing_codes = sorted(expected_codes - present_codes)
        if missing_codes:
            preview = missing_codes[:16]
            suffix = "..." if len(missing_codes) > len(preview) else ""
            raise ValueError(f"{corner} missing expected codes: {preview}{suffix}")

        code_to_row = {row["code"]: row for row in corner_rows}
        ordered = [code_to_row[code] for code in sorted(expected_codes)]
        if len(ordered) >= 2:
            therm_values = {row["therm_invert"] for row in ordered}
            if len(therm_values) != 1:
                raise ValueError(f"{corner} mixes therm_invert values: {sorted(therm_values)}")
            therm_invert = bool(next(iter(therm_values)))
            steps = []
            for left, right in zip(ordered, ordered[1:]):
                delta = right["freq_mhz"] - left["freq_mhz"]
                expected_positive = therm_invert
                if expected_positive and delta <= 0:
                    raise ValueError(
                        f"{corner} non-monotonic: code {left['code']} "
                        f"{left['freq_mhz']} MHz -> code {right['code']} {right['freq_mhz']} MHz"
                    )
                if not expected_positive and delta >= 0:
                    raise ValueError(
                        f"{corner} non-monotonic: code {left['code']} "
                        f"{left['freq_mhz']} MHz -> code {right['code']} {right['freq_mhz']} MHz"
                    )
                steps.append(abs(delta))
        else:
            steps = []

        freqs = [row["freq_mhz"] for row in ordered]
        freq_min = min(freqs)
        freq_max = max(freqs)
        span = freq_max - freq_min
        if span < min_span_mhz:
            raise ValueError(f"{corner} span {span:.6f} MHz below {min_span_mhz:.6f} MHz")
        if steps and min(steps) < min_step_mhz:
            raise ValueError(
                f"{corner} min adjacent step {min(steps):.6f} MHz below {min_step_mhz:.6f} MHz"
            )

        global_min = freq_min if global_min is None else min(global_min, freq_min)
        global_max = freq_max if global_max is None else max(global_max, freq_max)
        summary_rows.append(
            {
                "corner": corner,
                "codes_checked": len(ordered),
                "freq_min_mhz": freq_min,
                "freq_max_mhz": freq_max,
                "span_mhz": span,
                "min_adjacent_step_mhz": min(steps) if steps else "",
                "max_adjacent_step_mhz": max(steps) if steps else "",
                "mean_adjacent_step_mhz": statistics.fmean(steps) if steps else "",
                "therm_invert": ordered[0]["therm_invert"],
            }
        )

    return summary_rows, {
        "status": "pass",
        "corners": sorted(expected_corners),
        "codes_per_corner": len(expected_codes),
        "total_rows_checked": len(expected_corners) * len(expected_codes),
        "global_freq_min_mhz": global_min,
        "global_freq_max_mhz": global_max,
        "global_span_mhz": None if global_min is None else global_max - global_min,
    }


def write_csv(path, rows):
    fieldnames = [
        "corner",
        "codes_checked",
        "freq_min_mhz",
        "freq_max_mhz",
        "span_mhz",
        "min_adjacent_step_mhz",
        "max_adjacent_step_mhz",
        "mean_adjacent_step_mhz",
        "therm_invert",
    ]
    with path.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Check measured DCO SPICE sweep coverage.")
    parser.add_argument("--csv", required=True, help="Input dco_sweep.csv path.")
    parser.add_argument("--expected-codes", default="all")
    parser.add_argument("--expected-corners", default="tt")
    parser.add_argument("--min-span-mhz", type=float, default=1.0)
    parser.add_argument("--min-step-mhz", type=float, default=0.0)
    parser.add_argument(
        "--out-dir",
        default="build/dco_sweep_check",
        help="Directory for summary CSV and JSON artifacts.",
    )
    args = parser.parse_args()

    expected_codes = parse_int_set(args.expected_codes)
    expected_corners = parse_corner_set(args.expected_corners)
    if not expected_codes:
        raise ValueError("--expected-codes is empty")
    if not expected_corners:
        raise ValueError("--expected-corners is empty")

    csv_path = Path(args.csv).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_rows, summary = check_rows(
        read_rows(csv_path),
        expected_codes=expected_codes,
        expected_corners=expected_corners,
        min_span_mhz=args.min_span_mhz,
        min_step_mhz=args.min_step_mhz,
    )
    summary["input_csv"] = str(csv_path)
    summary["summary_csv"] = str(out_dir / "dco_sweep_summary.csv")
    summary["summary_json"] = str(out_dir / "dco_sweep_summary.json")
    write_csv(out_dir / "dco_sweep_summary.csv", summary_rows)
    (out_dir / "dco_sweep_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="ascii"
    )

    print(
        "DCO sweep check pass: "
        f"{summary['total_rows_checked']} rows, "
        f"{summary['global_freq_min_mhz']:.6f}..{summary['global_freq_max_mhz']:.6f} MHz"
    )
    print(f"wrote {summary['summary_csv']}")
    print(f"wrote {summary['summary_json']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
