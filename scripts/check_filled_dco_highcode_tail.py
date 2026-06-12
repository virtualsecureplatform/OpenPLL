#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import json
import sys
from pathlib import Path


DEFAULT_RESULT_CSVS = (
    "build/spice_dco_postlayout_filled_xyce_110_code192/dco_postlayout_results.csv",
    "build/spice_dco_postlayout_filled_tt_9pt_mpi4/dco_postlayout_results.csv",
    "build/spice_dco_postlayout_filled_highcode_probe_mpi4/dco_postlayout_results.csv",
    "build/spice_dco_postlayout_filled_tail_probe_mpi4/dco_postlayout_results.csv",
)


def parse_codes(text):
    codes = []
    for item in text.split(","):
        item = item.strip()
        if item:
            codes.append(int(item, 0))
    if codes != sorted(set(codes)):
        raise ValueError("--codes must be strictly increasing and unique")
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
        raise ValueError(f"row from {row.get('_source_csv', '<unknown>')} has invalid {name}") from exc


def float_field(row, name):
    try:
        return float(row[name])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"row from {row.get('_source_csv', '<unknown>')} has invalid {name}") from exc


def optional_int_field(row, name):
    value = row.get(name, "")
    if value == "":
        return ""
    return int_field(row, name)


def optional_float_field(row, name):
    value = row.get(name, "")
    if value == "":
        return ""
    return float_field(row, name)


def canonical_rows(rows, corner, expected_codes):
    by_code = {}
    for row in rows:
        if row.get("corner", corner) != corner:
            continue
        code = int_field(row, "code")
        if code in expected_codes:
            by_code.setdefault(code, []).append(row)

    missing = [code for code in expected_codes if code not in by_code]
    if missing:
        raise ValueError(f"missing filled-DCO high-code rows for codes: {missing}")

    result = []
    for code in expected_codes:
        passing = [
            row
            for row in by_code[code]
            if row.get("status") == "pass"
            and row.get("timed_out") == "no"
            and row.get("simulator") == "xyce"
        ]
        if not passing:
            sources = ", ".join(row.get("_source_csv", "<unknown>") for row in by_code[code])
            raise ValueError(f"no passing non-timeout Xyce row for {corner} code {code}; sources: {sources}")
        passing.sort(key=lambda row: row.get("_source_csv", ""))
        row = passing[0]
        therm_invert = int_field(row, "therm_invert")
        enabled_loads = int_field(row, "enabled_loads")
        expected_loads = 255 - code if therm_invert else code
        if enabled_loads != expected_loads:
            raise ValueError(f"{corner} code {code} enabled_loads={enabled_loads}, expected {expected_loads}")
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
                "xyce_mpi_procs": optional_int_field(row, "xyce_mpi_procs"),
                "elapsed_s": optional_float_field(row, "elapsed_s"),
                "waveform": row.get("waveform", ""),
                "netlist": row.get("netlist", ""),
                "log": row.get("log", ""),
                "source_csv": row["_source_csv"],
            }
        )
    return result


def add_segment_metrics(rows):
    positive_segments = []
    negative_segments = []
    for row in rows:
        row["segment_step_mhz_per_lsb"] = ""
        row["segment_span_mhz"] = ""
        row["segment_class"] = ""

    for left, right in zip(rows, rows[1:]):
        code_delta = right["code"] - left["code"]
        freq_delta = right["freq_mhz"] - left["freq_mhz"]
        if code_delta <= 0:
            raise ValueError("high-code tail codes are not strictly increasing")
        step = freq_delta / code_delta
        left["segment_step_mhz_per_lsb"] = step
        left["segment_span_mhz"] = freq_delta
        if freq_delta >= 0.0:
            left["segment_class"] = "positive"
            positive_segments.append((left, right, step, freq_delta))
        else:
            left["segment_class"] = "rolloff"
            negative_segments.append((left, right, step, freq_delta))
    return rows, positive_segments, negative_segments


def write_csv(path, rows):
    fieldnames = (
        "corner",
        "code",
        "enabled_loads",
        "freq_mhz",
        "period_s",
        "segment_step_mhz_per_lsb",
        "segment_span_mhz",
        "segment_class",
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
    parser = argparse.ArgumentParser(description="Characterize filled signoff DCO RCX high-code tail.")
    parser.add_argument(
        "--result-csv",
        action="append",
        dest="result_csvs",
        help="Input dco_postlayout_results.csv path. Defaults to promoted high-code probe runs.",
    )
    parser.add_argument("--corner", default="tt")
    parser.add_argument("--codes", default="192,208,216,224,232,240,248,250,252,254,255")
    parser.add_argument("--min-pre-tail-step-mhz-per-lsb", type=float, default=0.02)
    parser.add_argument("--tail-start-code", type=int, default=240)
    parser.add_argument("--min-tail-rolloff-mhz", type=float, default=0.4)
    parser.add_argument(
        "--out-dir",
        default="build/spice_dco_postlayout_filled_highcode_tail_check",
        help="Directory for consolidated high-code tail CSV and summary JSON.",
    )
    args = parser.parse_args()

    expected_codes = parse_codes(args.codes)
    csv_paths = args.result_csvs or list(DEFAULT_RESULT_CSVS)
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = canonical_rows(read_rows(csv_paths), args.corner, expected_codes)
    rows, positive_segments, negative_segments = add_segment_metrics(rows)

    peak_row = max(rows, key=lambda row: row["freq_mhz"])
    endpoint_row = rows[-1]
    first_tail_negative = next(
        (
            {
                "from_code": left["code"],
                "to_code": right["code"],
                "from_freq_mhz": left["freq_mhz"],
                "to_freq_mhz": right["freq_mhz"],
                "span_mhz": freq_delta,
                "step_mhz_per_lsb": step,
            }
            for left, right, step, freq_delta in negative_segments
            if left["code"] >= args.tail_start_code
        ),
        None,
    )

    pre_tail_steps = [
        step
        for left, right, step, _freq_delta in positive_segments
        if right["code"] <= args.tail_start_code
    ]
    if not pre_tail_steps:
        raise ValueError("no positive pre-tail high-code segments found")
    if min(pre_tail_steps) < args.min_pre_tail_step_mhz_per_lsb:
        raise ValueError(
            f"minimum pre-tail step {min(pre_tail_steps):.9f} MHz/LSB is below "
            f"{args.min_pre_tail_step_mhz_per_lsb:.9f}"
        )
    if peak_row["code"] < args.tail_start_code:
        raise ValueError(f"high-code tail peak occurs too early: code {peak_row['code']}")
    if first_tail_negative is None:
        raise ValueError(f"no roll-off segment found at or above code {args.tail_start_code}")
    tail_rolloff_mhz = peak_row["freq_mhz"] - endpoint_row["freq_mhz"]
    if tail_rolloff_mhz < args.min_tail_rolloff_mhz:
        raise ValueError(
            f"tail roll-off {tail_rolloff_mhz:.9f} MHz is below "
            f"{args.min_tail_rolloff_mhz:.9f}"
        )

    summary = {
        "status": "pass",
        "corner": args.corner,
        "codes": [row["code"] for row in rows],
        "finding": "high_code_tail_rolloff",
        "tail_start_code": args.tail_start_code,
        "freq_code192_mhz": rows[0]["freq_mhz"],
        "freq_code255_mhz": endpoint_row["freq_mhz"],
        "peak_code": peak_row["code"],
        "peak_freq_mhz": peak_row["freq_mhz"],
        "tail_rolloff_mhz": tail_rolloff_mhz,
        "first_tail_negative_segment": first_tail_negative,
        "min_pre_tail_step_mhz_per_lsb": min(pre_tail_steps),
        "max_pre_tail_step_mhz_per_lsb": max(pre_tail_steps),
        "negative_segment_count": len(negative_segments),
        "tail_csv": str(out_dir / "filled_dco_highcode_tail.csv"),
        "summary_json": str(out_dir / "filled_dco_highcode_tail_summary.json"),
    }

    write_csv(out_dir / "filled_dco_highcode_tail.csv", rows)
    (out_dir / "filled_dco_highcode_tail_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )

    print(
        "filled DCO high-code tail characterization pass: "
        f"peak=code{summary['peak_code']} {summary['peak_freq_mhz']:.6f} MHz, "
        f"code255={summary['freq_code255_mhz']:.6f} MHz, "
        f"tail_rolloff={summary['tail_rolloff_mhz']:.6f} MHz"
    )
    print(f"wrote {summary['tail_csv']}")
    print(f"wrote {summary['summary_json']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
