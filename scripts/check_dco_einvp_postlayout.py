#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import json
import sys
from pathlib import Path


DEFAULT_SMOKE_CSV = (
    "build/spice_dco_postlayout_einvp_smoke_mpi4/dco_postlayout_results.csv"
)
DEFAULT_TAIL_CSV = (
    "build/spice_dco_postlayout_einvp_highcode_tail_mpi4/dco_postlayout_results.csv"
)
DEFAULT_MID_CSV = (
    "build/spice_dco_postlayout_einvp_code064_mpi4/dco_postlayout_results.csv"
)
SMOKE_CODES = (0, 128, 255)
TAIL_CODES = (192, 224, 240, 248, 255)
MID_CODES = (64,)
CALIBRATION_CODES = (0, 64, 128, 192, 255)


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
    if row.get(name, "") == "":
        return ""
    return float_field(row, name)


def canonical_rows(rows, expected_codes, subckt_name, corner):
    by_code = {}
    for row in rows:
        if row.get("corner", corner) != corner:
            continue
        if row.get("subckt_name", subckt_name) != subckt_name:
            continue
        code = int_field(row, "code")
        if code in expected_codes:
            by_code.setdefault(code, []).append(row)

    missing = [code for code in expected_codes if code not in by_code]
    if missing:
        raise ValueError(f"missing {subckt_name} rows for codes: {missing}")

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
            raise ValueError(f"no passing non-timeout Xyce row for code {code}; sources: {sources}")
        passing.sort(key=lambda row: row.get("_source_csv", ""))
        row = passing[0]
        therm_invert = int_field(row, "therm_invert")
        enabled_loads = int_field(row, "enabled_loads")
        expected_loads = 255 - code if therm_invert else code
        if enabled_loads != expected_loads:
            raise ValueError(f"code {code} enabled_loads={enabled_loads}, expected {expected_loads}")
        freq_mhz = float_field(row, "freq_mhz")
        period_s = float_field(row, "period_s")
        if freq_mhz <= 0.0 or period_s <= 0.0:
            raise ValueError(f"code {code} has invalid frequency/period")
        result.append(
            {
                "corner": row.get("corner", corner),
                "subckt_name": row.get("subckt_name", subckt_name),
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


def add_segment_metrics(rows, min_step_mhz_per_lsb, label):
    for row in rows:
        row["segment_step_mhz_per_lsb"] = ""
        row["segment_span_mhz"] = ""

    for left, right in zip(rows, rows[1:]):
        code_delta = right["code"] - left["code"]
        freq_delta = right["freq_mhz"] - left["freq_mhz"]
        if code_delta <= 0:
            raise ValueError(f"{label} codes are not strictly increasing")
        step = freq_delta / code_delta
        if step < min_step_mhz_per_lsb:
            raise ValueError(
                f"{label} non-monotonic or weak segment: code {left['code']} "
                f"{left['freq_mhz']:.9f} MHz to code {right['code']} "
                f"{right['freq_mhz']:.9f} MHz, step {step:.9f} MHz/LSB"
            )
        left["segment_step_mhz_per_lsb"] = step
        left["segment_span_mhz"] = freq_delta
    return rows


def write_csv(path, rows):
    fieldnames = (
        "corner",
        "subckt_name",
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
        description="Check filled-RCX post-layout evidence for the EINVP DCO candidate."
    )
    parser.add_argument("--smoke-csv", default=DEFAULT_SMOKE_CSV)
    parser.add_argument("--tail-csv", default=DEFAULT_TAIL_CSV)
    parser.add_argument("--mid-csv", default=DEFAULT_MID_CSV)
    parser.add_argument("--subckt-name", default="IntegerPLL_DCO_EINVP")
    parser.add_argument("--corner", default="tt")
    parser.add_argument("--min-smoke-step-mhz-per-lsb", type=float, default=0.03)
    parser.add_argument("--min-tail-step-mhz-per-lsb", type=float, default=0.005)
    parser.add_argument("--min-calibration-step-mhz-per-lsb", type=float, default=0.03)
    parser.add_argument(
        "--out-dir",
        default="build/spice_dco_postlayout_einvp_check",
        help="Directory for consolidated candidate CSV and summary JSON.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    smoke_rows = add_segment_metrics(
        canonical_rows(
            read_rows([args.smoke_csv]),
            SMOKE_CODES,
            args.subckt_name,
            args.corner,
        ),
        args.min_smoke_step_mhz_per_lsb,
        "EINVP smoke",
    )
    tail_rows = add_segment_metrics(
        canonical_rows(
            read_rows([args.smoke_csv, args.tail_csv]),
            TAIL_CODES,
            args.subckt_name,
            args.corner,
        ),
        args.min_tail_step_mhz_per_lsb,
        "EINVP high-tail",
    )
    mid_rows = canonical_rows(
        read_rows([args.mid_csv]),
        MID_CODES,
        args.subckt_name,
        args.corner,
    )
    calibration_rows = add_segment_metrics(
        canonical_rows(
            read_rows([args.smoke_csv, args.mid_csv, args.tail_csv]),
            CALIBRATION_CODES,
            args.subckt_name,
            args.corner,
        ),
        args.min_calibration_step_mhz_per_lsb,
        "EINVP 5-point calibration",
    )

    smoke_span = smoke_rows[-1]["freq_mhz"] - smoke_rows[0]["freq_mhz"]
    tail_span = tail_rows[-1]["freq_mhz"] - tail_rows[0]["freq_mhz"]
    calibration_span = calibration_rows[-1]["freq_mhz"] - calibration_rows[0]["freq_mhz"]
    summary = {
        "status": "pass",
        "subckt_name": args.subckt_name,
        "corner": args.corner,
        "smoke_codes": [row["code"] for row in smoke_rows],
        "smoke_freq_min_mhz": smoke_rows[0]["freq_mhz"],
        "smoke_freq_max_mhz": smoke_rows[-1]["freq_mhz"],
        "smoke_span_mhz": smoke_span,
        "tail_codes": [row["code"] for row in tail_rows],
        "tail_freq_min_mhz": tail_rows[0]["freq_mhz"],
        "tail_freq_max_mhz": tail_rows[-1]["freq_mhz"],
        "tail_span_mhz": tail_span,
        "mid_codes": [row["code"] for row in mid_rows],
        "code64_freq_mhz": mid_rows[0]["freq_mhz"],
        "calibration_codes": [row["code"] for row in calibration_rows],
        "calibration_freq_min_mhz": calibration_rows[0]["freq_mhz"],
        "calibration_freq_max_mhz": calibration_rows[-1]["freq_mhz"],
        "calibration_span_mhz": calibration_span,
        "smoke_csv": str(out_dir / "dco_einvp_postlayout_smoke.csv"),
        "tail_csv": str(out_dir / "dco_einvp_postlayout_highcode_tail.csv"),
        "mid_csv": str(out_dir / "dco_einvp_postlayout_midcode.csv"),
        "calibration_csv": str(out_dir / "dco_einvp_postlayout_5pt_calibration.csv"),
        "summary_json": str(out_dir / "dco_einvp_postlayout_summary.json"),
    }

    write_csv(out_dir / "dco_einvp_postlayout_smoke.csv", smoke_rows)
    write_csv(out_dir / "dco_einvp_postlayout_highcode_tail.csv", tail_rows)
    write_csv(out_dir / "dco_einvp_postlayout_midcode.csv", mid_rows)
    write_csv(out_dir / "dco_einvp_postlayout_5pt_calibration.csv", calibration_rows)
    (out_dir / "dco_einvp_postlayout_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    print(
        "EINVP DCO post-layout pass: "
        f"smoke {summary['smoke_freq_min_mhz']:.6f}..{summary['smoke_freq_max_mhz']:.6f} MHz "
        f"(span {summary['smoke_span_mhz']:.6f} MHz), "
        f"code64 {summary['code64_freq_mhz']:.6f} MHz, "
        f"5pt span {summary['calibration_span_mhz']:.6f} MHz, "
        f"tail span {summary['tail_span_mhz']:.6f} MHz"
    )
    print(f"wrote {summary['summary_json']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
