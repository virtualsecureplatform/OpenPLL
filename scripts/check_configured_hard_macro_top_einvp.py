#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check the configured 25 MHz EINVP hard-macro wrapper."""

import argparse
import csv
import json
import re
import sys
from pathlib import Path


DESIGN = "IntegerPLL_HardMacroTop_EINVP_25MHzConfigured"
MACRO = "IntegerPLL_HardMacroTop_EINVP"
INSTANCE = "hard_macro"
CONFIG_REL = f"openlane/{DESIGN}/config.json"
SDC_REL = f"openlane/{DESIGN}/async_configured_top.sdc"
PIN_ORDER_REL = f"openlane/{DESIGN}/pin_order.cfg"
RUN_DIR_REL = f"openlane/{DESIGN}/runs/librelane_signoff"

EXPECTED_RTL = [
    "dir::../../rtl/IntegerPLL_25MHzModeConfig.v",
    "dir::../../rtl/IntegerPLL_25MHzModeController.v",
    "dir::../../rtl/IntegerPLL_HardMacroTop_EINVP_25MHzConfigured.v",
]

EXPECTED_MACRO = {
    "macro": MACRO,
    "instance": INSTANCE,
    "size_um": [850.0, 1120.0],
    "location_um": [120.0, 120.0],
    "orientation": "N",
}

ZERO_METRICS = (
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
)


def require_file(path):
    if not path.is_file():
        raise ValueError(f"missing file: {path}")
    if path.stat().st_size <= 0:
        raise ValueError(f"empty file: {path}")
    return path


def is_zero(value):
    return value in (0, 0.0, "0")


def resolve_config_path(config_dir, value):
    if value.startswith("dir::"):
        return (config_dir / value[5:]).resolve()
    return Path(value).expanduser().resolve()


def iter_paths(config_dir, value):
    if isinstance(value, list):
        for item in value:
            yield from iter_paths(config_dir, item)
    elif isinstance(value, dict):
        for child in value.values():
            yield from iter_paths(config_dir, child)
    else:
        yield resolve_config_path(config_dir, value)


def parse_lef_size(path):
    text = path.read_text(encoding="ascii", errors="replace")
    macro = re.search(r"^MACRO\s+(\S+)\s*$", text, re.MULTILINE)
    size = re.search(r"^\s+SIZE\s+([0-9.]+)\s+BY\s+([0-9.]+)\s+;", text, re.MULTILINE)
    if not macro or not size:
        raise ValueError(f"could not parse LEF macro/size from {path}")
    return macro.group(1), [float(size.group(1)), float(size.group(2))]


def parse_def_components(path):
    text = path.read_text(encoding="ascii", errors="replace")
    units_match = re.search(r"UNITS\s+DISTANCE\s+MICRONS\s+([0-9]+)\s+;", text)
    if not units_match:
        raise ValueError(f"could not parse DEF units from {path}")
    units = float(units_match.group(1))
    result = {}
    component_re = re.compile(r"^\s*-\s+(\S+)\s+(\S+)(.*?);", re.MULTILINE | re.DOTALL)
    place_re = re.compile(r"\+\s+(FIXED|PLACED)\s+\(\s+(-?[0-9]+)\s+(-?[0-9]+)\s+\)\s+(\S+)")
    for match in component_re.finditer(text):
        place = place_re.search(match.group(3))
        if not place:
            continue
        result[match.group(1)] = {
            "master": match.group(2),
            "status": place.group(1),
            "location_um": [int(place.group(2)) / units, int(place.group(3)) / units],
            "orientation": place.group(4),
        }
    return result


def check_config(root):
    config_path = require_file(root / CONFIG_REL)
    sdc_path = require_file(root / SDC_REL)
    pin_order_path = require_file(root / PIN_ORDER_REL)
    rtl_paths = [
        require_file(resolve_config_path(config_path.parent, path))
        for path in EXPECTED_RTL
    ]
    config = json.loads(config_path.read_text(encoding="ascii"))
    failures = []

    if config.get("DESIGN_NAME") != DESIGN:
        failures.append(f"unexpected DESIGN_NAME={config.get('DESIGN_NAME')}")
    if config.get("VERILOG_FILES") != EXPECTED_RTL:
        failures.append("unexpected VERILOG_FILES")
    if config.get("CLOCK_PORT") is not None:
        failures.append("CLOCK_PORT should be null")
    if config.get("EXTRA_EXCLUDED_CELLS") != ["sky130_fd_sc_hd__o21ai_0"]:
        failures.append("unexpected EXTRA_EXCLUDED_CELLS")
    if config.get("RUN_POST_GPL_DESIGN_REPAIR") is not True:
        failures.append("RUN_POST_GPL_DESIGN_REPAIR should be true")
    if config.get("RUN_POST_GRT_DESIGN_REPAIR") is not False:
        failures.append("RUN_POST_GRT_DESIGN_REPAIR should be false")
    if config.get("PNR_SDC_FILE") != "dir::async_configured_top.sdc":
        failures.append("unexpected PNR_SDC_FILE")
    if config.get("SIGNOFF_SDC_FILE") != "dir::async_configured_top.sdc":
        failures.append("unexpected SIGNOFF_SDC_FILE")
    if config.get("IO_PIN_ORDER_CFG") != "dir::pin_order.cfg":
        failures.append("unexpected IO_PIN_ORDER_CFG")
    if config.get("ERRORS_ON_UNMATCHED_IO") != "both":
        failures.append("ERRORS_ON_UNMATCHED_IO should be both")

    wrapper_text = rtl_paths[-1].read_text(encoding="ascii", errors="replace")
    for needle in (
        "module IntegerPLL_HardMacroTop_EINVP_25MHzConfigured",
        "IntegerPLL_25MHzModeController",
        "IntegerPLL_HardMacroTop_EINVP hard_macro",
        ".PLL_ENABLE(PLL_ENABLE)",
        "input wire [4:0] FEEDBACK_DIVIDER",
        ".FEEDBACK_DIVIDER(FEEDBACK_DIVIDER)",
        ".CONFIG_VALID(CONFIG_VALID)",
        ".COARSEBINARY_CODE(coarse_code)",
        ".MMDCLKDIV_RATIO(mmd_ratio)",
    ):
        if needle not in wrapper_text:
            failures.append(f"wrapper RTL missing {needle!r}")

    macros = config.get("MACROS", {})
    if set(macros) != {MACRO}:
        failures.append(f"unexpected macro set: {sorted(macros)}")
    macro_entry = macros.get(MACRO, {})
    instances = macro_entry.get("instances", {})
    if set(instances) != {INSTANCE}:
        failures.append(f"{MACRO} should have only instance {INSTANCE}")
    else:
        instance = instances[INSTANCE]
        if [float(v) for v in instance.get("location", [])] != EXPECTED_MACRO["location_um"]:
            failures.append(f"{INSTANCE} has wrong location")
        if instance.get("orientation") != EXPECTED_MACRO["orientation"]:
            failures.append(f"{INSTANCE} has wrong orientation")

    source_files = [str(config_path), str(sdc_path), str(pin_order_path)]
    source_files.extend(str(path) for path in rtl_paths)
    for view in ("gds", "lef", "vh", "pnl", "spice"):
        paths = list(iter_paths(config_path.parent, macro_entry.get(view, [])))
        if len(paths) != 1:
            failures.append(f"{MACRO} {view} should have one path")
            continue
        try:
            require_file(paths[0])
            source_files.append(str(paths[0]))
        except ValueError as exc:
            failures.append(str(exc))
        if view == "lef":
            try:
                lef_macro, lef_size = parse_lef_size(paths[0])
                if lef_macro != MACRO:
                    failures.append(f"{paths[0]} defines {lef_macro} instead of {MACRO}")
                if lef_size != EXPECTED_MACRO["size_um"]:
                    failures.append(f"{MACRO} LEF size {lef_size} != {EXPECTED_MACRO['size_um']}")
            except ValueError as exc:
                failures.append(str(exc))

    if failures:
        raise ValueError("; ".join(failures))

    return {
        "config": str(config_path),
        "sdc": str(sdc_path),
        "pin_order": str(pin_order_path),
        "rtl": [str(path) for path in rtl_paths],
        "macro_count": 1,
        "macro_rows": [
            {
                "macro": MACRO,
                "instance": INSTANCE,
                "x_um": EXPECTED_MACRO["location_um"][0],
                "y_um": EXPECTED_MACRO["location_um"][1],
                "width_um": EXPECTED_MACRO["size_um"][0],
                "height_um": EXPECTED_MACRO["size_um"][1],
                "orientation": EXPECTED_MACRO["orientation"],
            }
        ],
        "source_files": sorted(set(source_files)),
        "total_macro_area_um2": EXPECTED_MACRO["size_um"][0] * EXPECTED_MACRO["size_um"][1],
    }


def check_signoff(root, config_summary, require_signoff):
    run_dir = root / RUN_DIR_REL
    final_dir = run_dir / "final"
    if not require_signoff and not final_dir.exists():
        return {"status": "not_run", "run_dir": str(run_dir)}

    required = [
        f"final/def/{DESIGN}.def",
        f"final/gds/{DESIGN}.gds",
        f"final/lef/{DESIGN}.lef",
        f"final/nl/{DESIGN}.nl.v",
        f"final/odb/{DESIGN}.odb",
        f"final/pnl/{DESIGN}.pnl.v",
        f"final/sdc/{DESIGN}.sdc",
        f"final/spef/max/{DESIGN}.max.spef",
        f"final/spef/min/{DESIGN}.min.spef",
        f"final/spef/nom/{DESIGN}.nom.spef",
        f"final/spice/{DESIGN}.spice",
        "final/metrics.json",
    ]
    paths = {}
    failures = []
    for relpath in required:
        path = run_dir / relpath
        try:
            require_file(path)
            paths[relpath] = str(path)
        except ValueError as exc:
            failures.append(str(exc))
    if failures:
        raise ValueError("; ".join(failures))

    metrics_path = run_dir / "final/metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="ascii"))
    metric_failures = []
    for key in ZERO_METRICS:
        if key not in metrics:
            metric_failures.append(f"missing {key}")
        elif not is_zero(metrics[key]):
            metric_failures.append(f"{key}={metrics[key]}")
    if metric_failures:
        raise ValueError("; ".join(metric_failures))

    components = parse_def_components(run_dir / f"final/def/{DESIGN}.def")
    component = components.get(INSTANCE)
    if component is None:
        raise ValueError(f"final DEF missing component {INSTANCE}")
    if component["master"] != MACRO:
        raise ValueError(f"{INSTANCE} master {component['master']} != {MACRO}")
    if component["orientation"] != EXPECTED_MACRO["orientation"]:
        raise ValueError(f"{INSTANCE} orientation {component['orientation']} != {EXPECTED_MACRO['orientation']}")
    observed = component["location_um"]
    if any(abs(a - b) > 0.001 for a, b in zip(observed, EXPECTED_MACRO["location_um"])):
        raise ValueError(f"{INSTANCE} location {observed} != {EXPECTED_MACRO['location_um']}")

    netlist = (run_dir / f"final/nl/{DESIGN}.nl.v").read_text(encoding="ascii", errors="replace")
    for needle in (
        "IntegerPLL_HardMacroTop_EINVP hard_macro",
        ".COARSEBINARY_CODE(",
        ".DLF_Ext_Data(",
        ".MMDCLKDIV_RATIO(",
        "FEEDBACK_DIVIDER[",
        "CONFIG_VALID",
        "TARGET_MHZ[",
        "TRACKING",
    ):
        if needle not in netlist:
            raise ValueError(f"final netlist missing {needle!r}")
    if "sky130_fd_sc_hd__o21ai_0" in netlist:
        raise ValueError("final netlist uses KLayout-DRC-failing sky130_fd_sc_hd__o21ai_0")

    signoff_mtime = metrics_path.stat().st_mtime
    stale = []
    for source in config_summary["source_files"]:
        path = Path(source)
        if path.is_file() and path.stat().st_mtime > signoff_mtime:
            stale.append(f"{metrics_path} is older than {path}")
    if stale:
        raise ValueError("; ".join(stale))

    placement = {"instance": INSTANCE, "macro": MACRO, **component}
    return {
        "status": "pass",
        "run_dir": str(run_dir),
        "final_dir": str(final_dir),
        "placements": [placement],
        "stdcells": metrics.get("design__instance__count__stdcell"),
        "macros": metrics.get("design__instance__count__macro"),
        "wirelength": metrics.get("route__wirelength"),
        "vias": metrics.get("route__vias"),
        "views": paths,
    }


def write_outputs(summary, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "configured_hard_macro_top_einvp_summary.json"
    csv_path = out_dir / "configured_hard_macro_top_einvp_placements.csv"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="ascii")
    with csv_path.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=("macro", "instance", "x_um", "y_um", "width_um", "height_um", "orientation"),
        )
        writer.writeheader()
        for row in summary["config"]["macro_rows"]:
            writer.writerow(row)
    return json_path, csv_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--out-dir", default="build/configured_hard_macro_top_einvp")
    parser.add_argument("--require-signoff", action="store_true")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    out_dir = root / args.out_dir if not Path(args.out_dir).is_absolute() else Path(args.out_dir)
    config_summary = check_config(root)
    signoff_summary = check_signoff(root, config_summary, args.require_signoff)
    summary = {
        "status": "pass",
        "design": DESIGN,
        "config": config_summary,
        "signoff": signoff_summary,
        "embedded_macro": MACRO,
    }
    json_path, csv_path = write_outputs(summary, out_dir)
    print(
        "configured hard macro top EINVP pass: "
        f"macro_count={config_summary['macro_count']} "
        f"signoff_status={signoff_summary['status']} "
        f"area={config_summary['total_macro_area_um2']:.3f} um^2"
    )
    print(f"wrote {json_path}")
    print(f"wrote {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
