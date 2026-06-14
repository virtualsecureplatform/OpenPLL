#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import json
from pathlib import Path


def parse_float_list(text):
    values = []
    for item in text.split(","):
        item = item.strip()
        if item:
            values.append(float(item))
    if not values:
        raise ValueError("empty list")
    return values


def read_rows(paths):
    rows = []
    for path in paths:
        with path.open(newline="", encoding="ascii") as csv_file:
            for row in csv.DictReader(csv_file):
                if row.get("status") != "pass":
                    continue
                period_s = optional_float(row.get("period_s"))
                rise_time_s = optional_float(row.get("rise_time_s"))
                fall_time_s = optional_float(row.get("fall_time_s"))
                rows.append(
                    {
                        "source_csv": str(path),
                        "corner": row["corner"],
                        "topology": row.get("topology", ""),
                        "coarse_code": int(row.get("coarse_code") or 0),
                        "selected_tap": row.get("selected_tap", ""),
                        "code": int(row["code"]),
                        "freq_mhz": float(row["freq_mhz"]),
                        "period_s": period_s,
                        "duty_ratio": optional_float(row.get("duty_ratio")),
                        "rise_time_s": rise_time_s,
                        "fall_time_s": fall_time_s,
                        "rise_period_fraction": (
                            rise_time_s / period_s
                            if period_s and rise_time_s is not None
                            else None
                        ),
                        "fall_period_fraction": (
                            fall_time_s / period_s
                            if period_s and fall_time_s is not None
                            else None
                        ),
                    }
                )
    return rows


def optional_float(text):
    if text is None or text == "":
        return None
    return float(text)


def format_optional(value):
    if value is None:
        return ""
    return f"{value:.6f}"


def waveform_failure(row, args):
    duty = row["duty_ratio"]
    rise_fraction = row["rise_period_fraction"]
    fall_fraction = row["fall_period_fraction"]
    if duty is None or rise_fraction is None or fall_fraction is None:
        return "missing waveform measurements"
    if duty < args.min_duty_ratio or duty > args.max_duty_ratio:
        return f"duty {duty:.4f} outside {args.min_duty_ratio:.4f}..{args.max_duty_ratio:.4f}"
    if rise_fraction > args.max_edge_period_fraction:
        return (
            f"rise/period {rise_fraction:.4f} exceeds "
            f"{args.max_edge_period_fraction:.4f}"
        )
    if fall_fraction > args.max_edge_period_fraction:
        return (
            f"fall/period {fall_fraction:.4f} exceeds "
            f"{args.max_edge_period_fraction:.4f}"
        )
    return ""


def target_candidates(rows, target_mhz, args):
    candidates = []
    by_band = {}
    for row in rows:
        by_band.setdefault((row["corner"], row["coarse_code"]), []).append(row)

    for (corner, coarse_code), band_rows in by_band.items():
        ordered = sorted(band_rows, key=lambda row: row["freq_mhz"])
        for low, high in zip(ordered, ordered[1:]):
            low_freq = low["freq_mhz"]
            high_freq = high["freq_mhz"]
            if low_freq <= target_mhz <= high_freq:
                low_waveform_failure = waveform_failure(low, args)
                high_waveform_failure = waveform_failure(high, args)
                if args.require_waveform_quality and (
                    low_waveform_failure or high_waveform_failure
                ):
                    continue
                frac = 0.0 if high_freq == low_freq else (target_mhz - low_freq) / (high_freq - low_freq)
                code_est = low["code"] + frac * (high["code"] - low["code"])
                candidates.append(
                    {
                        "corner": corner,
                        "coarse_code": coarse_code,
                        "selected_tap": low["selected_tap"] or high["selected_tap"],
                        "code_est": code_est,
                        "low_code": low["code"],
                        "low_freq_mhz": low_freq,
                        "high_code": high["code"],
                        "high_freq_mhz": high_freq,
                        "low_duty_ratio": low["duty_ratio"],
                        "high_duty_ratio": high["duty_ratio"],
                        "low_rise_period_fraction": low["rise_period_fraction"],
                        "high_rise_period_fraction": high["rise_period_fraction"],
                        "low_fall_period_fraction": low["fall_period_fraction"],
                        "high_fall_period_fraction": high["fall_period_fraction"],
                        "low_waveform_failure": low_waveform_failure,
                        "high_waveform_failure": high_waveform_failure,
                        "code_mid_distance": abs(code_est - 128.0),
                    }
                )
    candidates.sort(key=lambda row: (row["code_mid_distance"], row["coarse_code"]))
    return candidates


def write_csv(path, rows):
    fieldnames = [
        "status",
        "target_mhz",
        "multiplier",
        "corner",
        "coarse_code",
        "selected_tap",
        "code_est",
        "low_code",
        "low_freq_mhz",
        "high_code",
        "high_freq_mhz",
        "low_duty_ratio",
        "high_duty_ratio",
        "low_rise_period_fraction",
        "high_rise_period_fraction",
        "low_fall_period_fraction",
        "high_fall_period_fraction",
        "candidate_count",
    ]
    with path.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(
        description="Check that measured coarse-DCO bands bracket target frequencies."
    )
    parser.add_argument(
        "--csv",
        action="append",
        required=True,
        help="Input dco_sweep.csv. Pass multiple times to combine probe runs.",
    )
    parser.add_argument("--ref-mhz", type=float, default=25.0)
    parser.add_argument("--targets-mhz", default="100,250,300,400,500")
    parser.add_argument(
        "--require-waveform-quality",
        action="store_true",
        help="Require bracketing endpoint rows to pass duty-cycle and edge-rate limits.",
    )
    parser.add_argument(
        "--min-duty-ratio",
        type=float,
        default=0.35,
        help="Minimum allowed PLLOUT duty ratio for waveform-qualified target brackets.",
    )
    parser.add_argument(
        "--max-duty-ratio",
        type=float,
        default=0.65,
        help="Maximum allowed PLLOUT duty ratio for waveform-qualified target brackets.",
    )
    parser.add_argument(
        "--max-edge-period-fraction",
        type=float,
        default=0.25,
        help="Maximum allowed 20%%-80%% rise/fall time divided by period.",
    )
    parser.add_argument(
        "--out-dir",
        default="build/dco_coarse_target_check",
        help="Directory for summary CSV/JSON artifacts.",
    )
    args = parser.parse_args()

    csv_paths = [Path(path).expanduser().resolve() for path in args.csv]
    targets_mhz = parse_float_list(args.targets_mhz)
    rows = read_rows(csv_paths)
    if not rows:
        raise ValueError("no passing DCO rows found")

    summary_rows = []
    missing = []
    for target_mhz in targets_mhz:
        candidates = target_candidates(rows, target_mhz, args)
        if not candidates:
            missing.append(target_mhz)
            summary_rows.append(
                {
                    "status": "fail",
                    "target_mhz": target_mhz,
                    "multiplier": target_mhz / args.ref_mhz,
                    "corner": "",
                    "coarse_code": "",
                    "selected_tap": "",
                    "code_est": "",
                    "low_code": "",
                    "low_freq_mhz": "",
                    "high_code": "",
                    "high_freq_mhz": "",
                    "low_duty_ratio": "",
                    "high_duty_ratio": "",
                    "low_rise_period_fraction": "",
                    "high_rise_period_fraction": "",
                    "low_fall_period_fraction": "",
                    "high_fall_period_fraction": "",
                    "candidate_count": 0,
                }
            )
            continue
        best = candidates[0]
        summary_rows.append(
            {
                "status": "pass",
                "target_mhz": target_mhz,
                "multiplier": target_mhz / args.ref_mhz,
                "corner": best["corner"],
                "coarse_code": best["coarse_code"],
                "selected_tap": best["selected_tap"],
                "code_est": f"{best['code_est']:.3f}",
                "low_code": best["low_code"],
                "low_freq_mhz": f"{best['low_freq_mhz']:.6f}",
                "high_code": best["high_code"],
                "high_freq_mhz": f"{best['high_freq_mhz']:.6f}",
                "low_duty_ratio": format_optional(best["low_duty_ratio"]),
                "high_duty_ratio": format_optional(best["high_duty_ratio"]),
                "low_rise_period_fraction": format_optional(best["low_rise_period_fraction"]),
                "high_rise_period_fraction": format_optional(best["high_rise_period_fraction"]),
                "low_fall_period_fraction": format_optional(best["low_fall_period_fraction"]),
                "high_fall_period_fraction": format_optional(best["high_fall_period_fraction"]),
                "candidate_count": len(candidates),
            }
        )

    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_csv = out_dir / "dco_coarse_target_summary.csv"
    summary_json = out_dir / "dco_coarse_target_summary.json"
    write_csv(summary_csv, summary_rows)
    summary = {
        "status": "fail" if missing else "pass",
        "ref_mhz": args.ref_mhz,
        "targets_mhz": targets_mhz,
        "require_waveform_quality": args.require_waveform_quality,
        "min_duty_ratio": args.min_duty_ratio,
        "max_duty_ratio": args.max_duty_ratio,
        "max_edge_period_fraction": args.max_edge_period_fraction,
        "missing_targets_mhz": missing,
        "input_csv": [str(path) for path in csv_paths],
        "summary_csv": str(summary_csv),
        "summary_json": str(summary_json),
        "rows": summary_rows,
    }
    summary_json.write_text(json.dumps(summary, indent=2), encoding="ascii")

    print(json.dumps(summary, indent=2))
    if missing:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
