#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check the EINVP-DCO hard-macro top integration path."""

import argparse
import csv
import json
import re
import sys
from pathlib import Path


DESIGN = "IntegerPLL_HardMacroTop_EINVP"
CONFIG_REL = "openlane/IntegerPLL_HardMacroTop_EINVP/config.json"
RTL_REL = "rtl/IntegerPLL_HardMacroTop_EINVP.v"
SDC_REL = "openlane/IntegerPLL_HardMacroTop_EINVP/async_macro_top.sdc"
RUN_DIR_REL = "openlane/IntegerPLL_HardMacroTop_EINVP/runs/librelane_signoff"

EXPECTED = {
    "IntegerPLL_BBPD": {
        "instance": "phase_detector",
        "size_um": [120.0, 120.0],
        "location_um": [315.0, 40.0],
        "orientation": "N",
    },
    "IntegerPLL_DigitalCore": {
        "instance": "digital_core",
        "size_um": [300.0, 300.0],
        "location_um": [235.0, 180.0],
        "orientation": "N",
    },
    "IntegerPLL_DCO_EINVP": {
        "instance": "oscillator",
        "size_um": [450.0, 450.0],
        "location_um": [160.0, 620.0],
        "orientation": "N",
    },
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
    text = path.read_text(encoding="ascii")
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
    rtl_path = require_file(root / RTL_REL)
    sdc_path = require_file(root / SDC_REL)
    config_dir = config_path.parent
    config = json.loads(config_path.read_text(encoding="ascii"))
    failures = []

    if config.get("DESIGN_NAME") != DESIGN:
        failures.append(f"unexpected DESIGN_NAME={config.get('DESIGN_NAME')}")
    if config.get("VERILOG_FILES") != ["dir::../../rtl/IntegerPLL_HardMacroTop_EINVP.v"]:
        failures.append("unexpected VERILOG_FILES")
    if config.get("CLOCK_PORT") is not None:
        failures.append("CLOCK_PORT should be null")
    if config.get("PNR_SDC_FILE") != "dir::async_macro_top.sdc":
        failures.append("unexpected PNR_SDC_FILE")
    if config.get("SIGNOFF_SDC_FILE") != "dir::async_macro_top.sdc":
        failures.append("unexpected SIGNOFF_SDC_FILE")

    rtl_text = rtl_path.read_text(encoding="ascii")
    for needle in (
        "module IntegerPLL_HardMacroTop_EINVP",
        "IntegerPLL_BBPD phase_detector",
        "IntegerPLL_DigitalCore digital_core",
        "IntegerPLL_DCO_EINVP oscillator",
        "assign bbpd_reset_n = RESET_N && DLF_En && !DLF_Clear;",
        ".DCO_THERM(dco_therm)",
        ".PLLOUT(PLLOUT)",
    ):
        if needle not in rtl_text:
            failures.append(f"RTL missing {needle!r}")

    macros = config.get("MACROS", {})
    if set(macros) != set(EXPECTED):
        failures.append(f"unexpected macro set: {sorted(macros)}")

    source_files = [str(config_path), str(rtl_path), str(sdc_path)]
    rows = []
    for macro_name, expected in EXPECTED.items():
        entry = macros.get(macro_name, {})
        instance_name = expected["instance"]
        instances = entry.get("instances", {})
        if set(instances) != {instance_name}:
            failures.append(f"{macro_name} should have only instance {instance_name}")
            continue
        instance = instances[instance_name]
        if [float(v) for v in instance.get("location", [])] != expected["location_um"]:
            failures.append(f"{instance_name} has wrong location")
        if instance.get("orientation") != expected["orientation"]:
            failures.append(f"{instance_name} has wrong orientation")

        for view in ("gds", "lef", "vh", "pnl", "spice"):
            paths = list(iter_paths(config_dir, entry.get(view, [])))
            if len(paths) != 1:
                failures.append(f"{macro_name} {view} should have one path")
                continue
            try:
                require_file(paths[0])
                source_files.append(str(paths[0]))
            except ValueError as exc:
                failures.append(str(exc))
            if view == "lef":
                try:
                    lef_macro, lef_size = parse_lef_size(paths[0])
                    if lef_macro != macro_name:
                        failures.append(f"{paths[0]} defines {lef_macro} instead of {macro_name}")
                    if lef_size != expected["size_um"]:
                        failures.append(f"{macro_name} LEF size {lef_size} != {expected['size_um']}")
                except ValueError as exc:
                    failures.append(str(exc))

        rows.append(
            {
                "macro": macro_name,
                "instance": instance_name,
                "x_um": expected["location_um"][0],
                "y_um": expected["location_um"][1],
                "width_um": expected["size_um"][0],
                "height_um": expected["size_um"][1],
                "orientation": expected["orientation"],
            }
        )

    if failures:
        raise ValueError("; ".join(failures))

    return {
        "config": str(config_path),
        "rtl": str(rtl_path),
        "sdc": str(sdc_path),
        "macro_count": len(EXPECTED),
        "macro_rows": rows,
        "source_files": sorted(set(source_files)),
        "total_macro_area_um2": sum(row["width_um"] * row["height_um"] for row in rows),
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
    placements = []
    for macro_name, expected in EXPECTED.items():
        instance_name = expected["instance"]
        component = components.get(instance_name)
        if component is None:
            raise ValueError(f"final DEF missing component {instance_name}")
        if component["master"] != macro_name:
            raise ValueError(f"{instance_name} master {component['master']} != {macro_name}")
        if component["orientation"] != expected["orientation"]:
            raise ValueError(f"{instance_name} orientation {component['orientation']} != {expected['orientation']}")
        observed = component["location_um"]
        if any(abs(a - b) > 0.001 for a, b in zip(observed, expected["location_um"])):
            raise ValueError(f"{instance_name} location {observed} != {expected['location_um']}")
        placements.append({"instance": instance_name, "macro": macro_name, **component})

    netlist = (run_dir / f"final/nl/{DESIGN}.nl.v").read_text(encoding="ascii", errors="replace")
    if "IntegerPLL_DCO_EINVP oscillator" not in netlist:
        raise ValueError("final netlist does not instantiate IntegerPLL_DCO_EINVP oscillator")
    if "IntegerPLL_DCO oscillator" in netlist:
        raise ValueError("final netlist still instantiates the NAND-load DCO")

    signoff_mtime = metrics_path.stat().st_mtime
    stale = []
    for source in config_summary["source_files"]:
        path = Path(source)
        if path.is_file() and path.stat().st_mtime > signoff_mtime:
            stale.append(f"{metrics_path} is older than {path}")
    if stale:
        raise ValueError("; ".join(stale))

    return {
        "status": "pass",
        "run_dir": str(run_dir),
        "final_dir": str(final_dir),
        "placements": placements,
        "stdcells": metrics.get("design__instance__count__stdcell"),
        "macros": metrics.get("design__instance__count__macro"),
        "wirelength": metrics.get("route__wirelength"),
        "vias": metrics.get("route__vias"),
        "views": paths,
    }


def write_outputs(summary, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "hard_macro_top_einvp_summary.json"
    csv_path = out_dir / "hard_macro_top_einvp_placements.csv"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="ascii")
    with csv_path.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=("macro", "instance", "x_um", "y_um", "width_um", "height_um", "orientation"))
        writer.writeheader()
        for row in summary["config"]["macro_rows"]:
            writer.writerow(row)
    return json_path, csv_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--out-dir", default="build/hard_macro_top_einvp")
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
        "dco_macro": "IntegerPLL_DCO_EINVP",
    }
    json_path, csv_path = write_outputs(summary, out_dir)
    print(
        "hard macro top EINVP pass: "
        f"macro_count={config_summary['macro_count']} "
        f"signoff_status={signoff_summary['status']} "
        f"area={config_summary['total_macro_area_um2']:.3f} um^2"
    )
    print(f"wrote {json_path}")
    print(f"wrote {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
