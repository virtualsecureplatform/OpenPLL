#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Promote measured extracted-DCO rows to a modern-PDK mode manifest."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from sky130_modern_targets import TARGETS_MHZ


PDK_VERSION = "1689ac3f2dc763876eaf967227c7dfe831b031ae"


def parse_setting(text: str) -> tuple[int, int, int]:
    target, coarse, code = (int(part, 0) for part in text.split(":"))
    if target not in TARGETS_MHZ or not 0 <= coarse <= 47 or not 4 <= code <= 251:
        raise ValueError(f"invalid target:coarse:code setting {text!r}")
    return target, coarse, code


def checked_row(row: dict[str, str]) -> float:
    if row.get("status") != "pass" or row.get("corner") != "tt":
        raise ValueError(f"unqualified extracted-DCO row: {row}")
    period = float(row["period_s"])
    duty = float(row["duty_ratio"])
    if not 0.35 <= duty <= 0.65:
        raise ValueError(f"DCO duty ratio out of range: {row}")
    if max(float(row["rise_time_s"]), float(row["fall_time_s"])) > period * 0.25:
        raise ValueError(f"DCO edge time out of range: {row}")
    return float(row["freq_mhz"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", action="append", type=Path, required=True)
    parser.add_argument("--setting", action="append", required=True,
                        help="Target MHz:coarse code:fine code, repeated five times.")
    parser.add_argument("--strong-load-count", type=int, required=True)
    parser.add_argument("--out", type=Path,
                        default=Path("sky130/modern_25mhz_targets.json"))
    parser.add_argument("--out-csv", type=Path,
                        default=Path("build/modern_25mhz/dco_measurements.csv"))
    args = parser.parse_args()
    if not 0 <= args.strong_load_count <= 255:
        raise ValueError("strong load count must be in 0..255")
    settings = [parse_setting(text) for text in args.setting]
    if {target for target, _, _ in settings} != set(TARGETS_MHZ) or len(settings) != 5:
        raise ValueError("exactly one setting is required for each target")

    measured: dict[tuple[int, int], float] = {}
    measured_rows: dict[tuple[int, int], dict[str, str]] = {}
    fieldnames = None
    for path in args.csv:
        with path.open(newline="", encoding="ascii") as handle:
            reader = csv.DictReader(handle)
            if fieldnames is None:
                fieldnames = reader.fieldnames
            elif reader.fieldnames != fieldnames:
                raise ValueError(f"inconsistent extracted-DCO CSV columns in {path}")
            for row in reader:
                if row.get("status") != "pass" or row.get("corner") != "tt":
                    continue
                key = int(row["coarse_code"]), int(row["code"])
                freq = checked_row(row)
                if key in measured and abs(measured[key] - freq) > 0.05:
                    raise ValueError(f"conflicting measurements for coarse/code {key}")
                measured[key] = freq
                measured_rows[key] = row

    targets = {}
    for target, coarse, code in sorted(settings):
        try:
            f0 = measured[coarse, 0]
            fcode = measured[coarse, code]
            f255 = measured[coarse, 255]
        except KeyError as exc:
            raise ValueError(f"missing extracted endpoint or target row for {target} MHz") from exc
        if not f0 < fcode < f255 or abs(fcode - target) > 2.0:
            raise ValueError(f"{target} MHz target lacks monotonic, accurate extracted evidence")
        targets[str(target)] = {
            "ndiv": target // 25,
            "coarse_code": coarse,
            "target_code": code,
            "ki": 16,
            "kp": 4,
            "f0_mhz": round(f0, 9),
            "f_target_mhz": round(fcode, 9),
            "f255_mhz": round(f255, 9),
        }
    manifest = {
        "pdk_version": PDK_VERSION,
        "dco_strong_load_count": args.strong_load_count,
        "dco_run_tag": f"modern_k{args.strong_load_count:03d}",
        "targets": targets,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="ascii")
    args.out_csv.parent.mkdir(parents=True, exist_ok=True)
    with args.out_csv.open("w", newline="", encoding="ascii") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for key in sorted(measured_rows):
            writer.writerow(measured_rows[key])
    print(args.out)
    print(args.out_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
