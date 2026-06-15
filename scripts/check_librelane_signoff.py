#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check the LibreLane signoff artifacts and zero-violation metrics."""

import argparse
import json
from pathlib import Path
import sys


REQUIRED_ZERO_METRICS = [
    "route__drc_errors",
    "antenna__violating__nets",
    "antenna__violating__pins",
    "route__antenna_violation__count",
    "design__power_grid_violation__count",
    "timing__setup__wns",
    "timing__setup__tns",
    "timing__hold__wns",
    "timing__hold__tns",
    "timing__setup_vio__count",
    "timing__hold_vio__count",
    "design__max_slew_violation__count",
    "design__max_cap_violation__count",
    "design__max_fanout_violation__count",
    "design__violations",
    "magic__drc_error__count",
    "klayout__drc_error__count",
    "design__xor_difference__count",
    "magic__illegal_overlap__count",
    "design__lvs_error__count",
    "design__lvs_device_difference__count",
    "design__lvs_net_difference__count",
    "design__lvs_property_fail__count",
    "design__lvs_unmatched_device__count",
    "design__lvs_unmatched_net__count",
    "design__lvs_unmatched_pin__count",
]


REQUIRED_VIEW_TEMPLATES = [
    "def/{design}.def",
    "gds/{design}.gds",
    "klayout_gds/{design}.klayout.gds",
    "lef/{design}.lef",
    "mag/{design}.mag",
    "mag_gds/{design}.magic.gds",
    "nl/{design}.nl.v",
    "odb/{design}.odb",
    "pnl/{design}.pnl.v",
    "sdc/{design}.sdc",
    "spef/max/{design}.max.spef",
    "spef/min/{design}.min.spef",
    "spef/nom/{design}.nom.spef",
    "spice/{design}.spice",
    "vh/{design}.vh",
]

DEFAULT_SOURCE_FILES = [
    "rtl/IntegerPLL_B2TH.v",
    "rtl/IntegerPLL_MMD_Retimer.v",
    "rtl/IntegerPLL_Divider.v",
    "rtl/IntegerPLL_DLF.v",
    "rtl/IntegerPLL_DigitalCore.v",
    "openlane/IntegerPLL_DigitalCore/config.json",
    "openlane/IntegerPLL_DigitalCore/pnr.sdc",
]


def is_zero(value):
    return value in (0, 0.0, "0")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--final-dir",
        default="openlane/IntegerPLL_DigitalCore/runs/librelane_signoff/final",
        help="LibreLane final view directory to check",
    )
    parser.add_argument(
        "--design-name",
        default="IntegerPLL_DigitalCore",
        help="Design name used for required final view filenames.",
    )
    parser.add_argument(
        "--source-file",
        action="append",
        dest="source_files",
        help=(
            "Source path, relative to the repository root, used for stale-artifact "
            "checks. May be repeated; defaults to the standard digital-core RTL, "
            "config.json, and SDC set."
        ),
    )
    parser.add_argument(
        "--skip-magic-streamout",
        action="store_true",
        help="Do not require final Magic .mag or Magic-generated GDS views.",
    )
    parser.add_argument(
        "--skip-xor",
        action="store_true",
        help="Do not require the Magic-vs-KLayout XOR metric.",
    )
    args = parser.parse_args()

    final_dir = Path(args.final_dir)
    metrics_path = final_dir / "metrics.json"
    if not metrics_path.is_file():
        print(f"missing metrics file: {metrics_path}", file=sys.stderr)
        return 1

    metrics = json.loads(metrics_path.read_text())

    failures = []
    required_views = [
        template.format(design=args.design_name) for template in REQUIRED_VIEW_TEMPLATES
    ]
    if args.skip_magic_streamout:
        required_views = [
            relpath
            for relpath in required_views
            if not (relpath.startswith("mag/") or relpath.startswith("mag_gds/"))
        ]
    for relpath in required_views:
        path = final_dir / relpath
        if not path.is_file():
            failures.append(f"missing view: {path}")

    required_zero_metrics = list(REQUIRED_ZERO_METRICS)
    if args.skip_xor:
        required_zero_metrics = [
            key for key in required_zero_metrics if key != "design__xor_difference__count"
        ]
    for key in required_zero_metrics:
        if key not in metrics:
            failures.append(f"missing metric: {key}")
            continue
        if not is_zero(metrics[key]):
            failures.append(f"{key}={metrics[key]}")

    root = Path(__file__).resolve().parents[1]
    metrics_mtime = metrics_path.stat().st_mtime
    source_files = args.source_files or DEFAULT_SOURCE_FILES
    for relpath in source_files:
        source_path = root / relpath
        if not source_path.is_file():
            failures.append(f"missing source file: {source_path}")
            continue
        if source_path.stat().st_mtime > metrics_mtime:
            failures.append(f"stale signoff: {metrics_path} is older than {source_path}")

    if failures:
        print("LibreLane signoff check failed:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1

    print("PASS: LibreLane signoff views present and zero-violation metrics")
    print(
        "summary: "
        f"stdcells={metrics.get('design__instance__count__stdcell')} "
        f"util={metrics.get('design__instance__utilization')} "
        f"wirelength={metrics.get('route__wirelength')} "
        f"vias={metrics.get('route__vias')} "
        f"setup_ws={metrics.get('timing__setup__ws')} "
        f"hold_ws={metrics.get('timing__hold__ws')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
