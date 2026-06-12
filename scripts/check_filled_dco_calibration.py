#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import json
import sys
from pathlib import Path


DEFAULT_RESULT_CSVS = (
    "build/spice_dco_postlayout_filled_xyce_70p5/dco_postlayout_results.csv",
    "build/spice_dco_postlayout_filled_xyce_85_code64/dco_postlayout_results.csv",
    "build/spice_dco_postlayout_filled_xyce_75/dco_postlayout_results.csv",
    "build/spice_dco_postlayout_filled_xyce_110_code192/dco_postlayout_results.csv",
    "build/spice_dco_postlayout_filled_xyce_160/dco_postlayout_results.csv",
)

EXPECTED_CODES = (0, 64, 128, 192, 255)


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
        raise ValueError(f"row from {row.get('_source_csv', '<unknown>')} has invalid {name}") from exc


def float_field(row, name):
    try:
        return float(row[name])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"row from {row.get('_source_csv', '<unknown>')} has invalid {name}") from exc


def canonical_rows(rows):
    by_code = {}
    for row in rows:
        code = int_field(row, "code")
        if code not in EXPECTED_CODES:
            continue
        by_code.setdefault(code, []).append(row)

    missing = [code for code in EXPECTED_CODES if code not in by_code]
    if missing:
        raise ValueError(f"missing filled-DCO calibration rows for codes: {missing}")

    result = []
    for code in EXPECTED_CODES:
        candidates = by_code[code]
        passing = [
            row
            for row in candidates
            if row.get("status") == "pass"
            and row.get("timed_out") == "no"
            and row.get("simulator") == "xyce"
        ]
        if not passing:
            sources = ", ".join(row.get("_source_csv", "<unknown>") for row in candidates)
            raise ValueError(f"no passing non-timeout Xyce row for code {code}; sources: {sources}")
        if len(passing) > 1:
            passing.sort(key=lambda row: row.get("_source_csv", ""))
        row = passing[0]
        therm_invert = int_field(row, "therm_invert")
        enabled_loads = int_field(row, "enabled_loads")
        expected_loads = 255 - code if therm_invert else code
        if enabled_loads != expected_loads:
            raise ValueError(
                f"code {code} enabled_loads={enabled_loads}, expected {expected_loads}"
            )
        freq_mhz = float_field(row, "freq_mhz")
        period_s = float_field(row, "period_s")
        if freq_mhz <= 0.0 or period_s <= 0.0:
            raise ValueError(f"code {code} has invalid frequency/period")
        result.append(
            {
                "code": code,
                "enabled_loads": enabled_loads,
                "freq_mhz": freq_mhz,
                "period_s": period_s,
                "waveform": row.get("waveform", ""),
                "netlist": row.get("netlist", ""),
                "log": row.get("log", ""),
                "source_csv": row["_source_csv"],
            }
        )
    return result


def add_segment_metrics(rows):
    for row in rows:
        row["segment_step_mhz_per_lsb"] = ""
        row["segment_span_mhz"] = ""
    for left, right in zip(rows, rows[1:]):
        code_delta = right["code"] - left["code"]
        freq_delta = right["freq_mhz"] - left["freq_mhz"]
        if code_delta <= 0:
            raise ValueError("calibration codes are not strictly increasing")
        if freq_delta <= 0:
            raise ValueError(
                f"filled-DCO calibration is non-monotonic: code {left['code']} "
                f"{left['freq_mhz']} MHz, code {right['code']} {right['freq_mhz']} MHz"
            )
        left["segment_step_mhz_per_lsb"] = freq_delta / code_delta
        left["segment_span_mhz"] = freq_delta
    return rows


def write_csv(path, rows):
    fieldnames = [
        "code",
        "enabled_loads",
        "freq_mhz",
        "period_s",
        "segment_step_mhz_per_lsb",
        "segment_span_mhz",
        "waveform",
        "netlist",
        "log",
        "source_csv",
    ]
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Check and consolidate filled signoff DCO RCX calibration rows."
    )
    parser.add_argument(
        "--result-csv",
        action="append",
        dest="result_csvs",
        help="Input dco_postlayout_results.csv path. Defaults to canonical five-point filled runs.",
    )
    parser.add_argument(
        "--out-dir",
        default="build/spice_dco_postlayout_filled_calibration",
        help="Directory for consolidated calibration CSV and summary JSON.",
    )
    args = parser.parse_args()

    csv_paths = args.result_csvs or list(DEFAULT_RESULT_CSVS)
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = add_segment_metrics(canonical_rows(read_rows(csv_paths)))
    span_mhz = rows[-1]["freq_mhz"] - rows[0]["freq_mhz"]
    avg_step_mhz = span_mhz / (rows[-1]["code"] - rows[0]["code"])
    segment_steps = [
        row["segment_step_mhz_per_lsb"]
        for row in rows
        if row["segment_step_mhz_per_lsb"] != ""
    ]
    summary = {
        "status": "pass",
        "codes": [row["code"] for row in rows],
        "freq_min_mhz": rows[0]["freq_mhz"],
        "freq_max_mhz": rows[-1]["freq_mhz"],
        "span_mhz": span_mhz,
        "avg_step_mhz_per_lsb": avg_step_mhz,
        "min_segment_step_mhz_per_lsb": min(segment_steps),
        "max_segment_step_mhz_per_lsb": max(segment_steps),
        "calibration_csv": str(out_dir / "filled_dco_calibration.csv"),
        "summary_json": str(out_dir / "filled_dco_calibration_summary.json"),
    }

    write_csv(out_dir / "filled_dco_calibration.csv", rows)
    (out_dir / "filled_dco_calibration_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )

    print(
        "filled DCO calibration pass: "
        f"{summary['freq_min_mhz']:.6f}..{summary['freq_max_mhz']:.6f} MHz, "
        f"span={summary['span_mhz']:.6f} MHz, "
        f"avg_step={summary['avg_step_mhz_per_lsb']:.6f} MHz/LSB"
    )
    print(f"wrote {summary['calibration_csv']}")
    print(f"wrote {summary['summary_json']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
