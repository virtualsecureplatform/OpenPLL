#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import json
import sys
from pathlib import Path


DEFAULT_INPUTS = (
    ("nand2", "build/spice_dco_tail_loadstyle_nand2/dco_sweep.csv"),
    ("einvp", "build/spice_dco_tail_loadstyle_einvp/dco_sweep.csv"),
)


def int_field(row, name):
    try:
        return int(row[name])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid {name} in row {row}") from exc


def float_field(row, name):
    try:
        return float(row[name])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid {name} in row {row}") from exc


def parse_inputs(items):
    if not items:
        return [(name, Path(path)) for name, path in DEFAULT_INPUTS]
    parsed = []
    for item in items:
        if "=" not in item:
            raise ValueError("--input must be formatted as name=path")
        name, path = item.split("=", 1)
        name = name.strip()
        if not name:
            raise ValueError("--input name is empty")
        parsed.append((name, Path(path).expanduser()))
    return parsed


def parse_codes(text):
    codes = []
    for item in text.split(","):
        item = item.strip()
        if item:
            codes.append(int(item, 0))
    if codes != sorted(set(codes)):
        raise ValueError("--expected-codes must be strictly increasing and unique")
    return codes


def read_csv(path):
    with path.open(newline="", encoding="ascii") as csv_file:
        return list(csv.DictReader(csv_file))


def summarize_candidate(name, path, expected_codes, corner):
    rows = [
        row
        for row in read_csv(path)
        if row.get("corner", "") == corner and int_field(row, "code") in expected_codes
    ]
    rows.sort(key=lambda row: int_field(row, "code"))
    codes = [int_field(row, "code") for row in rows]
    if codes != expected_codes:
        raise ValueError(f"{name} codes are {codes}, expected {expected_codes}")
    failed = [row for row in rows if row.get("status") != "pass"]
    if failed:
        raise ValueError(f"{name} has failed rows: {failed[:3]}")

    freqs = [float_field(row, "freq_mhz") for row in rows]
    steps = [right - left for left, right in zip(freqs, freqs[1:])]
    nonmonotonic = [
        (rows[index]["code"], rows[index + 1]["code"], step)
        for index, step in enumerate(steps)
        if step <= 0.0
    ]
    if nonmonotonic:
        raise ValueError(f"{name} has non-monotonic steps: {nonmonotonic[:3]}")

    for row in rows:
        code = int_field(row, "code")
        if int_field(row, "therm_invert") != 1:
            raise ValueError(f"{name} code {code} does not use therm_invert=1")
        if int_field(row, "enabled_loads") != 255 - code:
            raise ValueError(f"{name} code {code} has wrong enabled load count")

    return {
        "name": name,
        "corner": corner,
        "codes": codes,
        "freq_min_mhz": min(freqs),
        "freq_max_mhz": max(freqs),
        "span_mhz": max(freqs) - min(freqs),
        "min_step_mhz": min(steps),
        "max_step_mhz": max(steps),
        "source_csv": str(path.resolve()),
    }


def write_csv(path, rows):
    fieldnames = (
        "name",
        "corner",
        "codes",
        "freq_min_mhz",
        "freq_max_mhz",
        "span_mhz",
        "min_step_mhz",
        "max_step_mhz",
        "source_csv",
    )
    with path.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description="Compare pre-layout DCO load-cell candidates.")
    parser.add_argument(
        "--input",
        action="append",
        help="Candidate CSV formatted as name=path. Defaults to nand2 and einvp tail sweeps.",
    )
    parser.add_argument("--corner", default="tt")
    parser.add_argument("--expected-codes", default="192,208,216,224,232,240,248,250,252,254,255")
    parser.add_argument("--baseline", default="nand2")
    parser.add_argument("--candidate", default="einvp")
    parser.add_argument("--min-candidate-span-mhz", type=float, default=40.0)
    parser.add_argument("--min-candidate-span-ratio", type=float, default=3.0)
    parser.add_argument(
        "--candidate-5pt-csv",
        default="build/spice_dco_loadstyle_einvp_5pt/dco_sweep.csv",
        help="Representative full-range candidate sweep CSV.",
    )
    parser.add_argument("--candidate-5pt-codes", default="0,64,128,192,255")
    parser.add_argument("--min-candidate-5pt-span-mhz", type=float, default=100.0)
    parser.add_argument(
        "--out-dir",
        default="build/dco_loadstyle_candidates",
        help="Directory for load-style comparison CSV and summary JSON.",
    )
    args = parser.parse_args()

    expected_codes = parse_codes(args.expected_codes)
    inputs = parse_inputs(args.input)
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    summaries = [
        summarize_candidate(name, path.expanduser().resolve(), expected_codes, args.corner)
        for name, path in inputs
    ]
    by_name = {row["name"]: row for row in summaries}
    if args.baseline not in by_name:
        raise ValueError(f"missing baseline candidate {args.baseline!r}")
    if args.candidate not in by_name:
        raise ValueError(f"missing candidate {args.candidate!r}")
    baseline = by_name[args.baseline]
    candidate = by_name[args.candidate]
    span_ratio = candidate["span_mhz"] / baseline["span_mhz"]
    if candidate["span_mhz"] < args.min_candidate_span_mhz:
        raise ValueError(
            f"{args.candidate} span {candidate['span_mhz']:.6f} MHz is below "
            f"{args.min_candidate_span_mhz:.6f} MHz"
        )
    if span_ratio < args.min_candidate_span_ratio:
        raise ValueError(
            f"{args.candidate}/{args.baseline} span ratio {span_ratio:.6f} is below "
            f"{args.min_candidate_span_ratio:.6f}"
        )
    candidate_5pt = summarize_candidate(
        f"{args.candidate}_5pt",
        Path(args.candidate_5pt_csv).expanduser().resolve(),
        parse_codes(args.candidate_5pt_codes),
        args.corner,
    )
    if candidate_5pt["span_mhz"] < args.min_candidate_5pt_span_mhz:
        raise ValueError(
            f"{args.candidate} 5-point span {candidate_5pt['span_mhz']:.6f} MHz is below "
            f"{args.min_candidate_5pt_span_mhz:.6f} MHz"
        )

    summary = {
        "status": "pass",
        "corner": args.corner,
        "codes": expected_codes,
        "baseline": args.baseline,
        "candidate": args.candidate,
        "candidate_span_ratio": span_ratio,
        "candidate_5pt": candidate_5pt,
        "candidates": summaries,
        "comparison_csv": str(out_dir / "dco_loadstyle_candidate_summary.csv"),
        "summary_json": str(out_dir / "dco_loadstyle_candidate_summary.json"),
    }
    write_csv(out_dir / "dco_loadstyle_candidate_summary.csv", summaries)
    (out_dir / "dco_loadstyle_candidate_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="ascii"
    )

    print(
        "DCO load-style candidate comparison pass: "
        f"{args.candidate} span={candidate['span_mhz']:.6f} MHz, "
        f"{args.baseline} span={baseline['span_mhz']:.6f} MHz, "
        f"ratio={span_ratio:.3f}, "
        f"5pt_span={candidate_5pt['span_mhz']:.6f} MHz"
    )
    print(f"wrote {summary['comparison_csv']}")
    print(f"wrote {summary['summary_json']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
