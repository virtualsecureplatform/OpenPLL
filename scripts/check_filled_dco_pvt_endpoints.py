#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import json
import sys
from pathlib import Path


DEFAULT_RESULT_CSVS = (
    "build/spice_dco_postlayout_filled_pvt_ff_code000_55ns/dco_postlayout_results.csv",
    "build/spice_dco_postlayout_filled_pvt_ff_code255_55ns/dco_postlayout_results.csv",
    "build/spice_dco_postlayout_filled_pvt_fs_endpoints_80ns_mpi4/dco_postlayout_results.csv",
    "build/spice_dco_postlayout_filled_pvt_sf_endpoints_110ns_mpi4/dco_postlayout_results.csv",
    "build/spice_dco_postlayout_filled_pvt_ss_code000_120ns_mpi4/dco_postlayout_results.csv",
    "build/spice_dco_postlayout_filled_pvt_ss_code255_95ns_mpi4/dco_postlayout_results.csv",
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
        raise ValueError(f"row from {row.get('_source_csv', '<unknown>')} has invalid {name}") from exc


def float_field(row, name):
    try:
        return float(row[name])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"row from {row.get('_source_csv', '<unknown>')} has invalid {name}") from exc


def optional_float_field(row, name):
    value = row.get(name, "")
    if value == "":
        return ""
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"row from {row.get('_source_csv', '<unknown>')} has invalid {name}") from exc


def canonical_rows(rows, expected_corners, expected_codes):
    by_key = {}
    for row in rows:
        corner = row.get("corner", "")
        code = int_field(row, "code")
        if corner not in expected_corners or code not in expected_codes:
            continue
        by_key.setdefault((corner, code), []).append(row)

    missing = [
        (corner, code)
        for corner in expected_corners
        for code in expected_codes
        if (corner, code) not in by_key
    ]
    if missing:
        raise ValueError(f"missing filled-DCO PVT endpoint rows: {missing}")

    result = []
    for corner in expected_corners:
        for code in expected_codes:
            candidates = by_key[(corner, code)]
            passing = [
                row
                for row in candidates
                if row.get("status") == "pass"
                and row.get("timed_out") == "no"
                and row.get("simulator") == "xyce"
            ]
            if not passing:
                sources = ", ".join(row.get("_source_csv", "<unknown>") for row in candidates)
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


def check_monotonic(rows, expected_corners, min_span_mhz):
    spans = {}
    for corner in expected_corners:
        corner_rows = [row for row in rows if row["corner"] == corner]
        corner_rows.sort(key=lambda row: row["code"])
        for left, right in zip(corner_rows, corner_rows[1:]):
            if right["freq_mhz"] <= left["freq_mhz"]:
                raise ValueError(
                    f"filled-DCO PVT endpoints are non-monotonic at {corner}: "
                    f"code {left['code']} {left['freq_mhz']} MHz, "
                    f"code {right['code']} {right['freq_mhz']} MHz"
                )
        span_mhz = corner_rows[-1]["freq_mhz"] - corner_rows[0]["freq_mhz"]
        if span_mhz < min_span_mhz:
            raise ValueError(
                f"filled-DCO PVT endpoint span at {corner} is {span_mhz:.6f} MHz, "
                f"below {min_span_mhz:.6f} MHz"
            )
        spans[corner] = {
            "freq_min_mhz": corner_rows[0]["freq_mhz"],
            "freq_max_mhz": corner_rows[-1]["freq_mhz"],
            "span_mhz": span_mhz,
            "avg_step_mhz_per_lsb": span_mhz / (corner_rows[-1]["code"] - corner_rows[0]["code"]),
        }
    return spans


def write_csv(path, rows):
    fieldnames = (
        "corner",
        "code",
        "enabled_loads",
        "freq_mhz",
        "period_s",
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
        description="Check filled signoff DCO RCX PVT endpoint rows."
    )
    parser.add_argument(
        "--result-csv",
        action="append",
        dest="result_csvs",
        help="Input dco_postlayout_results.csv path. Defaults to promoted FF/FS/SF/SS endpoint runs.",
    )
    parser.add_argument("--corners", default="ff,fs,sf,ss")
    parser.add_argument("--codes", default="0,255")
    parser.add_argument("--min-span-mhz", type=float, default=3.0)
    parser.add_argument(
        "--out-dir",
        default="build/spice_dco_postlayout_filled_pvt_endpoints",
        help="Directory for consolidated endpoint CSV and summary JSON.",
    )
    args = parser.parse_args()

    expected_corners = [corner.strip() for corner in args.corners.split(",") if corner.strip()]
    expected_codes = parse_codes(args.codes)
    if not expected_corners or len(expected_codes) < 2:
        raise ValueError("at least one corner and two endpoint codes are required")

    csv_paths = args.result_csvs or list(DEFAULT_RESULT_CSVS)
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rows = canonical_rows(read_rows(csv_paths), expected_corners, expected_codes)
    spans = check_monotonic(rows, expected_corners, args.min_span_mhz)
    summary = {
        "status": "pass",
        "corners": expected_corners,
        "codes": expected_codes,
        "min_span_mhz": args.min_span_mhz,
        "spans": spans,
        "endpoint_csv": str(out_dir / "filled_dco_pvt_endpoints.csv"),
        "summary_json": str(out_dir / "filled_dco_pvt_endpoint_summary.json"),
    }

    write_csv(out_dir / "filled_dco_pvt_endpoints.csv", rows)
    (out_dir / "filled_dco_pvt_endpoint_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )

    span_text = ", ".join(
        f"{corner}: {data['freq_min_mhz']:.6f}..{data['freq_max_mhz']:.6f} MHz "
        f"span={data['span_mhz']:.6f} MHz"
        for corner, data in spans.items()
    )
    print(f"filled DCO PVT endpoint pass: {span_text}")
    print(f"wrote {summary['endpoint_csv']}")
    print(f"wrote {summary['summary_json']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
