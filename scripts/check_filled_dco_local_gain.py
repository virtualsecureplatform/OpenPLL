#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import json
import sys
from pathlib import Path


DEFAULT_RESULT_CSVS = (
    "build/spice_dco_postlayout_filled_local_gain_mpi4/dco_postlayout_results.csv",
)


def parse_codes(text):
    codes = []
    for item in text.split(","):
        item = item.strip()
        if item:
            codes.append(int(item, 0))
    return codes


def read_rows(csv_paths):
    rows = []
    for csv_path in csv_paths:
        path = Path(csv_path).expanduser().resolve()
        if not path.exists():
            raise FileNotFoundError(path)
        with path.open(newline="", encoding="utf-8") as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                row["_source_csv"] = str(path)
                rows.append(row)
    return rows


def int_field(row, name):
    try:
        return int(row[name])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            f"row from {row.get('_source_csv', '<unknown>')} has invalid {name}"
        ) from exc


def float_field(row, name):
    try:
        return float(row[name])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(
            f"row from {row.get('_source_csv', '<unknown>')} has invalid {name}"
        ) from exc


def optional_float_field(row, name):
    value = row.get(name, "")
    if value == "":
        return ""
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"row from {row.get('_source_csv', '<unknown>')} has invalid {name}"
        ) from exc


def canonical_rows(rows, corner, expected_codes):
    by_code = {}
    for row in rows:
        if row.get("corner", "") != corner:
            continue
        code = int_field(row, "code")
        if code in expected_codes:
            by_code.setdefault(code, []).append(row)

    missing = [code for code in expected_codes if code not in by_code]
    if missing:
        raise ValueError(f"missing filled-DCO local-gain rows for codes: {missing}")

    result = []
    for code in expected_codes:
        candidates = by_code[code]
        passing = [
            row
            for row in candidates
            if row.get("status") == "pass"
            and row.get("timed_out") == "no"
            and row.get("simulator") == "xyce"
        ]
        if not passing:
            sources = ", ".join(
                row.get("_source_csv", "<unknown>") for row in candidates
            )
            raise ValueError(
                f"no passing non-timeout Xyce row for {corner} code {code}; "
                f"sources: {sources}"
            )
        passing.sort(key=lambda row: row.get("_source_csv", ""))
        row = passing[0]
        therm_invert = int_field(row, "therm_invert")
        enabled_loads = int_field(row, "enabled_loads")
        expected_loads = 255 - code if therm_invert else code
        if enabled_loads != expected_loads:
            raise ValueError(
                f"{corner} code {code} enabled_loads={enabled_loads}, "
                f"expected {expected_loads}"
            )
        freq_mhz = float_field(row, "freq_mhz")
        period_s = float_field(row, "period_s")
        if freq_mhz <= 0.0 or period_s <= 0.0:
            raise ValueError(f"{corner} code {code} has invalid frequency/period")
        result.append(
            {
                "corner": corner,
                "code": code,
                "enabled_loads": enabled_loads,
                "freq_mhz": freq_mhz,
                "period_s": period_s,
                "xyce_mpi_procs": int_field(row, "xyce_mpi_procs"),
                "elapsed_s": optional_float_field(row, "elapsed_s"),
                "waveform": row.get("waveform", ""),
                "netlist": row.get("netlist", ""),
                "log": row.get("log", ""),
                "source_csv": row["_source_csv"],
            }
        )
    return result


def add_segment_metrics(rows, min_step_mhz_per_lsb, max_step_mhz_per_lsb):
    for row in rows:
        row["segment_step_mhz_per_lsb"] = ""
        row["segment_span_mhz"] = ""

    segment_steps = []
    for left, right in zip(rows, rows[1:]):
        code_delta = right["code"] - left["code"]
        freq_delta = right["freq_mhz"] - left["freq_mhz"]
        if code_delta <= 0:
            raise ValueError("local-gain codes are not strictly increasing")
        if freq_delta <= 0.0:
            raise ValueError(
                f"filled-DCO local gain is non-monotonic: code {left['code']} "
                f"{left['freq_mhz']} MHz, code {right['code']} {right['freq_mhz']} MHz"
            )
        step = freq_delta / code_delta
        if step < min_step_mhz_per_lsb:
            raise ValueError(
                f"filled-DCO local step {left['code']}->{right['code']} is "
                f"{step:.9f} MHz/LSB, below {min_step_mhz_per_lsb:.9f}"
            )
        if step > max_step_mhz_per_lsb:
            raise ValueError(
                f"filled-DCO local step {left['code']}->{right['code']} is "
                f"{step:.9f} MHz/LSB, above {max_step_mhz_per_lsb:.9f}"
            )
        left["segment_step_mhz_per_lsb"] = step
        left["segment_span_mhz"] = freq_delta
        segment_steps.append(step)
    return rows, segment_steps


def write_csv(path, rows):
    fieldnames = (
        "corner",
        "code",
        "enabled_loads",
        "freq_mhz",
        "period_s",
        "segment_step_mhz_per_lsb",
        "segment_span_mhz",
        "xyce_mpi_procs",
        "elapsed_s",
        "waveform",
        "netlist",
        "log",
        "source_csv",
    )
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Check filled signoff DCO RCX local gain around the lock code."
    )
    parser.add_argument(
        "--result-csv",
        action="append",
        dest="result_csvs",
        help="Input dco_postlayout_results.csv path. Defaults to promoted local-gain run.",
    )
    parser.add_argument("--corner", default="tt")
    parser.add_argument("--codes", default="120,128,136")
    parser.add_argument("--center-code", type=int, default=128)
    parser.add_argument("--min-step-mhz-per-lsb", type=float, default=0.02)
    parser.add_argument("--max-step-mhz-per-lsb", type=float, default=0.04)
    parser.add_argument(
        "--out-dir",
        default="build/spice_dco_postlayout_filled_local_gain",
        help="Directory for consolidated local-gain CSV and summary JSON.",
    )
    args = parser.parse_args()

    expected_codes = parse_codes(args.codes)
    if len(expected_codes) < 3:
        raise ValueError("at least three local-gain codes are required")
    if expected_codes != sorted(expected_codes):
        raise ValueError("--codes must be strictly increasing")
    if args.center_code not in expected_codes:
        raise ValueError("--center-code must be one of --codes")

    csv_paths = args.result_csvs or list(DEFAULT_RESULT_CSVS)
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = canonical_rows(read_rows(csv_paths), args.corner, expected_codes)
    rows, segment_steps = add_segment_metrics(
        rows, args.min_step_mhz_per_lsb, args.max_step_mhz_per_lsb
    )
    span_mhz = rows[-1]["freq_mhz"] - rows[0]["freq_mhz"]
    avg_step_mhz = span_mhz / (rows[-1]["code"] - rows[0]["code"])
    center_row = next(row for row in rows if row["code"] == args.center_code)
    summary = {
        "status": "pass",
        "corner": args.corner,
        "codes": [row["code"] for row in rows],
        "center_code": args.center_code,
        "center_freq_mhz": center_row["freq_mhz"],
        "freq_min_mhz": rows[0]["freq_mhz"],
        "freq_max_mhz": rows[-1]["freq_mhz"],
        "span_mhz": span_mhz,
        "avg_step_mhz_per_lsb": avg_step_mhz,
        "min_segment_step_mhz_per_lsb": min(segment_steps),
        "max_segment_step_mhz_per_lsb": max(segment_steps),
        "min_step_mhz_per_lsb": args.min_step_mhz_per_lsb,
        "max_step_mhz_per_lsb": args.max_step_mhz_per_lsb,
        "min_xyce_mpi_procs": min(row["xyce_mpi_procs"] for row in rows),
        "local_gain_csv": str(out_dir / "filled_dco_local_gain.csv"),
        "summary_json": str(out_dir / "filled_dco_local_gain_summary.json"),
    }

    write_csv(out_dir / "filled_dco_local_gain.csv", rows)
    (out_dir / "filled_dco_local_gain_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )

    print(
        "filled DCO local gain pass: "
        f"code {rows[0]['code']}..{rows[-1]['code']} "
        f"{rows[0]['freq_mhz']:.6f}..{rows[-1]['freq_mhz']:.6f} MHz, "
        f"avg_step={avg_step_mhz:.6f} MHz/LSB"
    )
    print(f"wrote {summary['local_gain_csv']}")
    print(f"wrote {summary['summary_json']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
