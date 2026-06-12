#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check routed hard-macro top integration artifacts for the Sky130 PLL."""

import argparse
import csv
import json
import re
from pathlib import Path


EXPECTED = {
    "IntegerPLL_BBPD": {
        "instance": "phase_detector",
        "size_um": [120.0, 120.0],
        "location_um": [315.0, 40.0],
        "orientation": "N",
        "required_views": ("gds", "lef", "vh", "pnl", "spice"),
    },
    "IntegerPLL_DigitalCore": {
        "instance": "digital_core",
        "size_um": [300.0, 300.0],
        "location_um": [235.0, 180.0],
        "orientation": "N",
        "required_views": ("gds", "lef", "vh", "pnl", "spice"),
    },
    "IntegerPLL_DCO": {
        "instance": "oscillator",
        "size_um": [450.0, 450.0],
        "location_um": [160.0, 620.0],
        "orientation": "N",
        "required_views": ("gds", "lef", "vh", "pnl", "spice"),
    },
}

REQUIRED_TOP_TEXT = (
    "module IntegerPLL_HardMacroTop",
    "IntegerPLL_BBPD phase_detector",
    "IntegerPLL_DigitalCore digital_core",
    "IntegerPLL_DCO oscillator",
    "assign bbpd_reset_n = RESET_N && DLF_En && !DLF_Clear;",
    ".CLKDIVR(CLKDIV_RETIMED)",
    ".BBPD(BBPD_CODE)",
    ".DCO_THERM(dco_therm)",
    ".PLLOUT(PLLOUT)",
)

REQUIRED_ROUTE_VIEWS = (
    "final/def/IntegerPLL_HardMacroTop.def",
    "final/odb/IntegerPLL_HardMacroTop.odb",
    "final/nl/IntegerPLL_HardMacroTop.nl.v",
    "final/pnl/IntegerPLL_HardMacroTop.pnl.v",
    "final/sdc/IntegerPLL_HardMacroTop.sdc",
    "final/metrics.json",
)

ZERO_METRICS = (
    "route__drc_errors",
    "antenna__violating__nets",
    "antenna__violating__pins",
    "route__antenna_violation__count",
    "design__power_grid_violation__count",
    "design__violations",
)

REQUIRED_SIGNOFF_VIEWS = (
    "final/def/IntegerPLL_HardMacroTop.def",
    "final/gds/IntegerPLL_HardMacroTop.gds",
    "final/klayout_gds/IntegerPLL_HardMacroTop.klayout.gds",
    "final/lef/IntegerPLL_HardMacroTop.lef",
    "final/mag/IntegerPLL_HardMacroTop.mag",
    "final/mag_gds/IntegerPLL_HardMacroTop.magic.gds",
    "final/nl/IntegerPLL_HardMacroTop.nl.v",
    "final/odb/IntegerPLL_HardMacroTop.odb",
    "final/pnl/IntegerPLL_HardMacroTop.pnl.v",
    "final/sdc/IntegerPLL_HardMacroTop.sdc",
    "final/sdf/nom_ff_n40C_1v95/IntegerPLL_HardMacroTop__nom_ff_n40C_1v95.sdf",
    "final/sdf/nom_ss_100C_1v60/IntegerPLL_HardMacroTop__nom_ss_100C_1v60.sdf",
    "final/sdf/nom_tt_025C_1v80/IntegerPLL_HardMacroTop__nom_tt_025C_1v80.sdf",
    "final/spef/max/IntegerPLL_HardMacroTop.max.spef",
    "final/spef/min/IntegerPLL_HardMacroTop.min.spef",
    "final/spef/nom/IntegerPLL_HardMacroTop.nom.spef",
    "final/spice/IntegerPLL_HardMacroTop.spice",
    "final/vh/IntegerPLL_HardMacroTop.vh",
    "final/json_h/IntegerPLL_HardMacroTop.h.json",
    "final/render/IntegerPLL_HardMacroTop.png",
    "final/metrics.csv",
    "final/metrics.json",
)

REQUIRED_SIGNOFF_LOGS = (
    "41-openroad-detailedrouting/openroad-detailedrouting.log",
    "51-openroad-rcx/max/rcx.log",
    "51-openroad-rcx/min/rcx.log",
    "51-openroad-rcx/nom/rcx.log",
    "57-klayout-xor/klayout-xor.log",
    "59-magic-drc/magic-drc.log",
    "60-klayout-drc/klayout-drc.log",
    "63-magic-spiceextraction/magic-spiceextraction.log",
    "65-netgen-lvs/netgen-lvs.log",
)

SIGNOFF_ZERO_METRICS = (
    *ZERO_METRICS,
    "timing__setup__wns",
    "timing__setup__tns",
    "timing__hold__wns",
    "timing__hold__tns",
    "timing__setup_vio__count",
    "timing__hold_vio__count",
    "design__max_slew_violation__count",
    "design__max_cap_violation__count",
    "design__max_fanout_violation__count",
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

POWER_CHECKS = {
    "VPWR": (
        ("phase_detector", "VPWR"),
        ("digital_core", "VPWR"),
        ("oscillator", "VPWR"),
    ),
    "VGND": (
        ("phase_detector", "VGND"),
        ("digital_core", "VGND"),
        ("oscillator", "VGND"),
    ),
    "VPB": (
        ("phase_detector", "VPB"),
        ("oscillator", "VPB"),
    ),
    "VNB": (
        ("phase_detector", "VNB"),
        ("oscillator", "VNB"),
    ),
}


def require_file(path):
    if not path.is_file():
        raise ValueError(f"missing file: {path}")
    if path.stat().st_size <= 0:
        raise ValueError(f"empty file: {path}")
    return path


def is_zero(value):
    return value in (0, 0.0, "0")


def resolve_config_path(config_dir, value):
    if not isinstance(value, str):
        raise ValueError(f"expected path string, got {value!r}")
    if value.startswith("dir::"):
        return (config_dir / value[5:]).resolve()
    return Path(value).expanduser().resolve()


def iter_view_paths(config_dir, value):
    if isinstance(value, list):
        for item in value:
            yield resolve_config_path(config_dir, item)
    elif isinstance(value, dict):
        for paths in value.values():
            yield from iter_view_paths(config_dir, paths)
    else:
        yield resolve_config_path(config_dir, value)


def parse_lef_size(path):
    text = path.read_text(encoding="ascii")
    macro_match = re.search(r"^MACRO\s+(\S+)\s*$", text, re.MULTILINE)
    size_match = re.search(
        r"^\s+SIZE\s+([0-9.]+)\s+BY\s+([0-9.]+)\s+;",
        text,
        re.MULTILINE,
    )
    if not macro_match or not size_match:
        raise ValueError(f"could not parse macro size from {path}")
    return {
        "macro": macro_match.group(1),
        "size_um": [float(size_match.group(1)), float(size_match.group(2))],
    }


def parse_def_components(path):
    text = path.read_text(encoding="ascii", errors="replace")
    units_match = re.search(r"UNITS\s+DISTANCE\s+MICRONS\s+([0-9]+)\s+;", text)
    if not units_match:
        raise ValueError(f"could not parse DEF units from {path}")
    units = float(units_match.group(1))
    components = {}
    component_re = re.compile(r"^\s*-\s+(\S+)\s+(\S+)(.*?);", re.MULTILINE | re.DOTALL)
    place_re = re.compile(
        r"\+\s+(FIXED|PLACED)\s+\(\s+(-?[0-9]+)\s+(-?[0-9]+)\s+\)\s+(\S+)"
    )
    for match in component_re.finditer(text):
        name, master, body = match.group(1), match.group(2), match.group(3)
        place = place_re.search(body)
        if not place:
            continue
        components[name] = {
            "master": master,
            "status": place.group(1),
            "location_um": [int(place.group(2)) / units, int(place.group(3)) / units],
            "orientation": place.group(4),
        }
    return components


def def_net_has_connection(def_text, net_name, instance_name, pin_name):
    entries = re.findall(
        rf"(?ms)^\s*-\s+{re.escape(net_name)}\b(.*?);",
        def_text,
    )
    needle = f"( {instance_name} {pin_name} )"
    return any(needle in entry for entry in entries)


def box(location, size):
    x, y = location
    w, h = size
    return [x, y, x + w, y + h]


def gap_between(a, b):
    x_gap = max(b[0] - a[2], a[0] - b[2], 0.0)
    y_gap = max(b[1] - a[3], a[1] - b[3], 0.0)
    return max(x_gap, y_gap)


def boxes_overlap(a, b):
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def check_zero_metrics(metrics, keys, require_keys):
    failures = []
    for key in keys:
        if key not in metrics:
            if require_keys:
                failures.append(f"missing {key}")
            continue
        if not is_zero(metrics[key]):
            failures.append(f"{key}={metrics[key]}")
    if failures:
        raise ValueError("; ".join(failures))


def check_final_macro_connections(run_dir):
    def_path = run_dir / "final/def/IntegerPLL_HardMacroTop.def"
    def_text = def_path.read_text(encoding="ascii", errors="replace")
    components = parse_def_components(def_path)
    placement_rows = []
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
        expected_location = expected["location_um"]
        if any(abs(a - b) > 0.001 for a, b in zip(observed, expected_location)):
            raise ValueError(f"{instance_name} DEF location {observed} != {expected_location}")
        placement_rows.append(
            {
                "macro": macro_name,
                "instance": instance_name,
                "x_um": observed[0],
                "y_um": observed[1],
                "orientation": component["orientation"],
                "placement_status": component["status"],
            }
        )

    checked_power_connections = {}
    for net_name, pins in POWER_CHECKS.items():
        checked_power_connections[net_name] = []
        for instance_name, pin_name in pins:
            if not def_net_has_connection(def_text, net_name, instance_name, pin_name):
                raise ValueError(f"final DEF net {net_name} missing ({instance_name} {pin_name})")
            checked_power_connections[net_name].append(f"{instance_name}/{pin_name}")

    netlist_text = (run_dir / "final/nl/IntegerPLL_HardMacroTop.nl.v").read_text(
        encoding="ascii",
        errors="replace",
    )
    for macro_name, expected in EXPECTED.items():
        instance_name = expected["instance"]
        if macro_name not in netlist_text or instance_name not in netlist_text:
            raise ValueError(f"final netlist missing {macro_name}/{instance_name}")

    return placement_rows, checked_power_connections


def check_config(root):
    config_path = require_file(root / "openlane/IntegerPLL_HardMacroTop/config.json")
    config_dir = config_path.parent
    config = json.loads(config_path.read_text(encoding="ascii"))
    rtl_path = require_file(root / "rtl/IntegerPLL_HardMacroTop.v")
    sdc_path = require_file(root / "openlane/IntegerPLL_HardMacroTop/async_macro_top.sdc")

    failures = []
    if config.get("DESIGN_NAME") != "IntegerPLL_HardMacroTop":
        failures.append(f"unexpected DESIGN_NAME={config.get('DESIGN_NAME')}")
    if config.get("CLOCK_PORT") is not None:
        failures.append("hard macro top CLOCK_PORT should be null")
    if "USE_POWER_PINS" not in config.get("VERILOG_DEFINES", []):
        failures.append("missing USE_POWER_PINS define")
    if config.get("PNR_SDC_FILE") != "dir::async_macro_top.sdc":
        failures.append("unexpected PNR_SDC_FILE")
    if config.get("SIGNOFF_SDC_FILE") != "dir::async_macro_top.sdc":
        failures.append("unexpected SIGNOFF_SDC_FILE")

    die = [float(value) for value in config.get("DIE_AREA", [])]
    if die != [0.0, 0.0, 850.0, 1120.0]:
        failures.append(f"unexpected DIE_AREA={config.get('DIE_AREA')}")
    if config.get("PDN_CONNECT_MACROS_TO_GRID") is not True:
        failures.append("PDN_CONNECT_MACROS_TO_GRID should be true")
    expected_pdn = {
        "phase_detector VPWR VGND VPWR VGND",
        "digital_core VPWR VGND VPWR VGND",
        "oscillator VPWR VGND VPWR VGND",
    }
    if set(config.get("PDN_MACRO_CONNECTIONS", [])) != expected_pdn:
        failures.append("PDN_MACRO_CONNECTIONS do not match expected macro hooks")

    rtl_text = rtl_path.read_text(encoding="ascii")
    missing_top = [needle for needle in REQUIRED_TOP_TEXT if needle not in rtl_text]
    if missing_top:
        failures.append(f"hard macro top RTL missing expected text: {missing_top}")
    if "#(" in re.sub(r"module\s+IntegerPLL_HardMacroTop\s*\(", "", rtl_text):
        failures.append("hard macro top should not parameterize signed-off macro instances")

    macros = config.get("MACROS", {})
    if set(macros) != set(EXPECTED):
        failures.append(f"unexpected macro set: {sorted(macros)}")

    rows = []
    boxes = {}
    source_files = [str(config_path), str(rtl_path), str(sdc_path)]
    for macro_name, expected in EXPECTED.items():
        entry = macros.get(macro_name, {})
        instance_name = expected["instance"]
        instances = entry.get("instances", {})
        instance = instances.get(instance_name)
        if instance is None or set(instances) != {instance_name}:
            failures.append(f"{macro_name} should have only instance {instance_name}")
            continue
        location = [float(value) for value in instance.get("location", [])]
        if location != expected["location_um"]:
            failures.append(f"{instance_name} location {location} != {expected['location_um']}")
        if instance.get("orientation") != expected["orientation"]:
            failures.append(f"{instance_name} orientation {instance.get('orientation')} != {expected['orientation']}")

        view_paths = {}
        for view in expected["required_views"]:
            if view not in entry:
                failures.append(f"{macro_name} missing {view} view")
                continue
            paths = list(iter_view_paths(config_dir, entry[view]))
            if not paths:
                failures.append(f"{macro_name} empty {view} view list")
            for path in paths:
                try:
                    require_file(path)
                except ValueError as exc:
                    failures.append(str(exc))
            view_paths[view] = [str(path) for path in paths]
            source_files.extend(str(path) for path in paths)

        lef_paths = [Path(path) for path in view_paths.get("lef", [])]
        if len(lef_paths) == 1:
            try:
                lef = parse_lef_size(lef_paths[0])
                if lef["macro"] != macro_name:
                    failures.append(f"{lef_paths[0]} defines {lef['macro']} instead of {macro_name}")
                if lef["size_um"] != expected["size_um"]:
                    failures.append(f"{macro_name} LEF size {lef['size_um']} != {expected['size_um']}")
            except ValueError as exc:
                failures.append(str(exc))

        placed_box = box(expected["location_um"], expected["size_um"])
        boxes[instance_name] = placed_box
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

    for left_name, left_box in boxes.items():
        for right_name, right_box in boxes.items():
            if left_name >= right_name:
                continue
            if boxes_overlap(left_box, right_box):
                failures.append(f"macro boxes overlap: {left_name} and {right_name}")

    if not failures and die:
        for name, macro_box in boxes.items():
            if macro_box[0] < die[0] or macro_box[1] < die[1] or macro_box[2] > die[2] or macro_box[3] > die[3]:
                failures.append(f"{name} is outside DIE_AREA")

    if not failures:
        dco_gap = boxes["oscillator"][1] - boxes["digital_core"][3]
        bbpd_gap = boxes["digital_core"][1] - boxes["phase_detector"][3]
        dco_center = (boxes["oscillator"][0] + boxes["oscillator"][2]) / 2.0
        digital_center = (boxes["digital_core"][0] + boxes["digital_core"][2]) / 2.0
        if dco_gap < 100.0:
            failures.append(f"thermometer bus channel too small: {dco_gap} um")
        if bbpd_gap < 20.0:
            failures.append(f"BBPD-to-digital channel too small: {bbpd_gap} um")
        if abs(dco_center - digital_center) > 1e-6:
            failures.append("DCO and digital core should be center-aligned")

    if failures:
        raise ValueError("; ".join(failures))

    return {
        "config": str(config_path),
        "rtl": str(rtl_path),
        "sdc": str(sdc_path),
        "die_area_um": die,
        "macro_count": len(EXPECTED),
        "macro_rows": rows,
        "total_macro_area_um2": sum(row["width_um"] * row["height_um"] for row in rows),
        "dco_to_digital_channel_um": boxes["oscillator"][1] - boxes["digital_core"][3],
        "bbpd_to_digital_channel_um": boxes["digital_core"][1] - boxes["phase_detector"][3],
        "source_files": sorted(set(source_files)),
    }


def check_route(root, config_summary, require_route):
    route_dir = root / "openlane/IntegerPLL_HardMacroTop/runs/librelane_route"
    final_dir = route_dir / "final"
    if not require_route and not final_dir.exists():
        return {"status": "not_run", "run_dir": str(route_dir)}

    failures = []
    paths = {}
    for relpath in REQUIRED_ROUTE_VIEWS:
        path = route_dir / relpath
        try:
            require_file(path)
            paths[relpath] = str(path)
        except ValueError as exc:
            failures.append(str(exc))

    detailed_route_steps = sorted(route_dir.glob("*-openroad-detailedrouting"))
    if not detailed_route_steps:
        failures.append("missing OpenROAD.DetailedRouting step directory")
    else:
        detailed_log = detailed_route_steps[-1] / "openroad-detailedrouting.log"
        try:
            require_file(detailed_log)
            paths["detailed_route_log"] = str(detailed_log)
        except ValueError as exc:
            failures.append(str(exc))

    if failures:
        raise ValueError("; ".join(failures))

    metrics_path = route_dir / "final/metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="ascii"))
    check_zero_metrics(metrics, ZERO_METRICS, require_keys=False)
    placement_rows, checked_power_connections = check_final_macro_connections(route_dir)

    source_files = list(config_summary["source_files"]) + [
        *(str(path) for path in paths.values()),
        str(metrics_path),
    ]
    route_mtime = metrics_path.stat().st_mtime
    stale = []
    for source in config_summary["source_files"]:
        path = Path(source)
        if path.is_file() and path.stat().st_mtime > route_mtime:
            stale.append(f"{metrics_path} is older than {path}")
    if stale:
        raise ValueError("; ".join(stale))

    return {
        "status": "pass",
        "run_dir": str(route_dir),
        "final_dir": str(final_dir),
        "route_views": paths,
        "placements": placement_rows,
        "power_connections": checked_power_connections,
        "stdcells": metrics.get("design__instance__count__stdcell"),
        "macros": metrics.get("design__instance__count__macro", len(EXPECTED)),
        "wirelength": metrics.get("route__wirelength"),
        "vias": metrics.get("route__vias"),
        "source_files": sorted(set(source_files)),
    }


def check_signoff(root, config_summary, require_signoff):
    signoff_dir = root / "openlane/IntegerPLL_HardMacroTop/runs/librelane_signoff"
    final_dir = signoff_dir / "final"
    if not require_signoff and not final_dir.exists():
        return {"status": "not_run", "run_dir": str(signoff_dir)}

    failures = []
    paths = {}
    for relpath in REQUIRED_SIGNOFF_VIEWS:
        path = signoff_dir / relpath
        try:
            require_file(path)
            paths[relpath] = str(path)
        except ValueError as exc:
            failures.append(str(exc))
    for relpath in REQUIRED_SIGNOFF_LOGS:
        path = signoff_dir / relpath
        try:
            require_file(path)
            paths[f"log/{relpath}"] = str(path)
        except ValueError as exc:
            failures.append(str(exc))

    if failures:
        raise ValueError("; ".join(failures))

    metrics_path = signoff_dir / "final/metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="ascii"))
    check_zero_metrics(metrics, SIGNOFF_ZERO_METRICS, require_keys=True)
    placement_rows, checked_power_connections = check_final_macro_connections(signoff_dir)

    source_files = list(config_summary["source_files"]) + [
        *(str(path) for path in paths.values()),
        str(metrics_path),
    ]
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
        "run_dir": str(signoff_dir),
        "final_dir": str(final_dir),
        "signoff_views": paths,
        "placements": placement_rows,
        "power_connections": checked_power_connections,
        "stdcells": metrics.get("design__instance__count__stdcell"),
        "macros": metrics.get("design__instance__count__macro", len(EXPECTED)),
        "wirelength": metrics.get("route__wirelength"),
        "vias": metrics.get("route__vias"),
        "spef_corners": ["max", "min", "nom"],
        "signoff_checks": [
            "openroad_rcx",
            "magic_streamout",
            "klayout_streamout",
            "klayout_xor",
            "magic_drc",
            "klayout_drc",
            "magic_spice_extraction",
            "netgen_lvs",
        ],
        "source_files": sorted(set(source_files)),
    }


def write_outputs(summary, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "hard_macro_top_summary.json"
    csv_path = out_dir / "hard_macro_top_placements.csv"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="ascii")
    with csv_path.open("w", newline="", encoding="ascii") as csv_file:
        fieldnames = ("macro", "instance", "x_um", "y_um", "width_um", "height_um", "orientation")
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary["config"]["macro_rows"]:
            writer.writerow(row)
    return json_path, csv_path


def check_hard_macro_top(root, require_route=True, require_signoff=False):
    config_summary = check_config(root)
    route_summary = check_route(root, config_summary, require_route=require_route)
    signoff_summary = check_signoff(root, config_summary, require_signoff=require_signoff)
    status = (
        "pass"
        if route_summary["status"] in ("pass", "not_run")
        and signoff_summary["status"] in ("pass", "not_run")
        else "fail"
    )
    return {
        "status": status,
        "config": config_summary,
        "route": route_summary,
        "signoff": signoff_summary,
        "key_routes": {
            "bbpd_to_digital": "BBPD_CODE[1:0]",
            "digital_to_dco": "dco_therm[254:0]",
            "dco_to_digital_feedback": "PLLOUT",
            "digital_to_bbpd_feedback": "CLKDIV_RETIMED",
            "body_bias": "VPB/VNB routed as top-level signal nets to DCO and BBPD",
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Check Sky130 PLL hard-macro top integration.")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
        help="OpenPLL repository root.",
    )
    parser.add_argument(
        "--out-dir",
        default="build/hard_macro_top",
        help="Output directory for JSON/CSV summary artifacts.",
    )
    parser.add_argument(
        "--allow-unrouted",
        action="store_true",
        help="Only check the RTL/config if routed Librelane artifacts are absent.",
    )
    parser.add_argument(
        "--require-signoff",
        action="store_true",
        help="Require full Librelane signoff artifacts for the hard-macro top.",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    out_dir = root / args.out_dir if not Path(args.out_dir).is_absolute() else Path(args.out_dir)
    summary = check_hard_macro_top(
        root,
        require_route=not args.allow_unrouted,
        require_signoff=args.require_signoff,
    )
    json_path, csv_path = write_outputs(summary, out_dir)
    route_status = summary["route"]["status"]
    signoff_status = summary["signoff"]["status"]
    print(
        "hard macro top pass: "
        f"{summary['config']['macro_count']} macros, "
        f"route_status={route_status}, "
        f"signoff_status={signoff_status}, "
        f"area={summary['config']['total_macro_area_um2']:.3f} um^2"
    )
    print(f"wrote {json_path}")
    print(f"wrote {csv_path}")


if __name__ == "__main__":
    main()
