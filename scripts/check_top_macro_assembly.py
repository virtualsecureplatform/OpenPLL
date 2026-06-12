#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check that signed-off Sky130 PLL macros form a consistent top assembly.

This is a fast physical-view/interface check, not a routed full-chip signoff.
It verifies that the signed-off digital core, DCO, and BBPD macro views are
present and that their LEF pin interfaces match the structural top-level RTL
interconnect needed for a later hard-macro top integration run.
"""

import argparse
import csv
import json
import re
from pathlib import Path


def bus(name, width):
    return [f"{name}[{index}]" for index in range(width)]


EXPECTED = {
    "IntegerPLL_DigitalCore": {
        "lef": "openlane/IntegerPLL_DigitalCore/runs/librelane_signoff_force127_s4a2/final/lef/IntegerPLL_DigitalCore.lef",
        "gds": "openlane/IntegerPLL_DigitalCore/runs/librelane_signoff_force127_s4a2/final/gds/IntegerPLL_DigitalCore.gds",
        "def": "openlane/IntegerPLL_DigitalCore/runs/librelane_signoff_force127_s4a2/final/def/IntegerPLL_DigitalCore.def",
        "nl": "openlane/IntegerPLL_DigitalCore/runs/librelane_signoff_force127_s4a2/final/nl/IntegerPLL_DigitalCore.nl.v",
        "sdc": "openlane/IntegerPLL_DigitalCore/runs/librelane_signoff_force127_s4a2/final/sdc/IntegerPLL_DigitalCore.sdc",
        "source": "rtl/IntegerPLL_DigitalCore.v",
        "inputs": (
            ["PLLOUT", "RESET_N", "DLF_En", "DLF_Clear", "DLF_Ext_Override", "DLF_IN_POL"]
            + bus("BBPD", 2)
            + bus("DLF_Ext_Data", 10)
            + bus("DLF_KI", 8)
            + bus("DLF_KP", 8)
            + bus("COARSEBINARY_CODE", 4)
            + bus("MMDCLKDIV_RATIO", 8)
        ),
        "outputs": (
            ["CLKDIV_RETIMED", "PLLOUT_DIV"]
            + bus("COARSETHERMAL_CODE", 15)
            + bus("Medium_BINARY_CODE", 5)
            + bus("Fine_BINARY_CODE", 5)
            + bus("Medium_CAPS_CTRL", 31)
            + bus("Fine_CAPS_CTRL", 31)
            + bus("DCO_CODE", 8)
            + bus("DCO_THERM", 255)
            + bus("DLF_CODE", 10)
        ),
        "power": {"VPWR": "POWER", "VGND": "GROUND"},
        "expected_size": [300.0, 300.0],
    },
    "IntegerPLL_DCO": {
        "lef": "openlane/IntegerPLL_DCO/runs/librelane_signoff/final/lef/IntegerPLL_DCO.lef",
        "gds": "openlane/IntegerPLL_DCO/runs/librelane_signoff/final/gds/IntegerPLL_DCO.gds",
        "def": "openlane/IntegerPLL_DCO/runs/librelane_signoff/final/def/IntegerPLL_DCO.def",
        "nl": "openlane/IntegerPLL_DCO/runs/librelane_signoff/final/nl/IntegerPLL_DCO.nl.v",
        "sdc": "openlane/IntegerPLL_DCO/runs/librelane_signoff/final/sdc/IntegerPLL_DCO.sdc",
        "source": "sky130/IntegerPLL_DCO_sky130.v",
        "inputs": ["RESET_N"] + bus("DCO_THERM", 255),
        "outputs": ["PLLOUT"],
        "power": {"VPWR": "POWER", "VGND": "GROUND", "VPB": "SIGNAL", "VNB": "SIGNAL"},
        "expected_size": [450.0, 450.0],
    },
    "IntegerPLL_BBPD": {
        "lef": "openlane/IntegerPLL_BBPD/runs/librelane_signoff/final/lef/IntegerPLL_BBPD.lef",
        "gds": "openlane/IntegerPLL_BBPD/runs/librelane_signoff/final/gds/IntegerPLL_BBPD.gds",
        "def": "openlane/IntegerPLL_BBPD/runs/librelane_signoff/final/def/IntegerPLL_BBPD.def",
        "nl": "openlane/IntegerPLL_BBPD/runs/librelane_signoff/final/nl/IntegerPLL_BBPD.nl.v",
        "sdc": "openlane/IntegerPLL_BBPD/runs/librelane_signoff/final/sdc/IntegerPLL_BBPD.sdc",
        "source": "sky130/IntegerPLL_BBPD_sky130.v",
        "inputs": ["REF", "CLKDIVR", "RESET_N"],
        "outputs": bus("BBPD", 2),
        "power": {"VPWR": "POWER", "VGND": "GROUND", "VPB": "SIGNAL", "VNB": "SIGNAL"},
        "expected_size": [120.0, 120.0],
    },
}


TOP_REQUIRED_TEXT = (
    "IntegerPLL_BBPD phase_detector",
    "IntegerPLL_DigitalCore #(",
    "IntegerPLL_DCO oscillator",
    "assign bbpd_reset_n = RESET_N && DLF_En && !DLF_Clear;",
    ".CLKDIVR(CLKDIV_RETIMED)",
    ".BBPD(BBPD_CODE)",
    ".DCO_THERM(dco_therm)",
    ".PLLOUT(PLLOUT)",
)


def require_file(root, relpath):
    path = root / relpath
    if not path.is_file():
        raise ValueError(f"missing file: {path}")
    if path.stat().st_size <= 0:
        raise ValueError(f"empty file: {path}")
    return path


def parse_lef(path):
    text = path.read_text(encoding="ascii")
    macro_match = re.search(r"^MACRO\s+(\S+)\s*$", text, re.MULTILINE)
    size_match = re.search(
        r"^\s+SIZE\s+([0-9.]+)\s+BY\s+([0-9.]+)\s+;",
        text,
        re.MULTILINE,
    )
    if not macro_match or not size_match:
        raise ValueError(f"could not parse LEF macro/size from {path}")

    pins = {}
    pin_re = re.compile(r"^  PIN (.+?)\n(.*?)^  END \1\s*$", re.MULTILINE | re.DOTALL)
    for match in pin_re.finditer(text):
        name = match.group(1)
        body = match.group(2)
        direction = re.search(r"^\s+DIRECTION\s+(\S+)\s+;", body, re.MULTILINE)
        use = re.search(r"^\s+USE\s+(\S+)\s+;", body, re.MULTILINE)
        pins[name] = {
            "direction": direction.group(1) if direction else None,
            "use": use.group(1) if use else None,
        }

    return {
        "macro": macro_match.group(1),
        "size": [float(size_match.group(1)), float(size_match.group(2))],
        "pins": pins,
    }


def check_direction(block, lef, names, expected_direction):
    failures = []
    for name in names:
        pin = lef["pins"].get(name)
        if pin is None:
            failures.append(f"{block} missing LEF pin {name}")
        elif pin["direction"] != expected_direction:
            failures.append(
                f"{block} LEF pin {name} direction {pin['direction']} != {expected_direction}"
            )
    return failures


def check_macro(root, block, cfg):
    paths = {key: require_file(root, relpath) for key, relpath in cfg.items() if key in {"lef", "gds", "def", "nl", "sdc", "source"}}
    lef = parse_lef(paths["lef"])
    failures = []
    if lef["macro"] != block:
        failures.append(f"{paths['lef']} contains macro {lef['macro']} instead of {block}")

    expected_size = cfg["expected_size"]
    if any(abs(observed - expected) > 1e-6 for observed, expected in zip(lef["size"], expected_size)):
        failures.append(f"{block} LEF size {lef['size']} != expected {expected_size}")

    failures.extend(check_direction(block, lef, cfg["inputs"], "INPUT"))
    failures.extend(check_direction(block, lef, cfg["outputs"], "OUTPUT"))
    for name, expected_use in cfg["power"].items():
        pin = lef["pins"].get(name)
        if pin is None:
            failures.append(f"{block} missing power/body LEF pin {name}")
        elif pin["direction"] != "INOUT":
            failures.append(f"{block} power/body pin {name} direction {pin['direction']} != INOUT")
        elif pin["use"] != expected_use:
            failures.append(f"{block} power/body pin {name} use {pin['use']} != {expected_use}")

    expected_pin_count = len(cfg["inputs"]) + len(cfg["outputs"]) + len(cfg["power"])
    if len(lef["pins"]) != expected_pin_count:
        failures.append(f"{block} LEF pin count {len(lef['pins'])} != {expected_pin_count}")

    netlist_text = paths["nl"].read_text(encoding="ascii", errors="replace")
    if f"module {block}" not in netlist_text:
        failures.append(f"{paths['nl']} does not define module {block}")

    if failures:
        raise ValueError("; ".join(failures))

    return {
        "block": block,
        "size_um": lef["size"],
        "area_um2": lef["size"][0] * lef["size"][1],
        "input_pins": len(cfg["inputs"]),
        "output_pins": len(cfg["outputs"]),
        "power_body_pins": len(cfg["power"]),
        "total_pins": len(lef["pins"]),
        "lef": str(paths["lef"]),
        "gds": str(paths["gds"]),
        "def": str(paths["def"]),
        "netlist": str(paths["nl"]),
        "sdc": str(paths["sdc"]),
        "source": str(paths["source"]),
    }


def check_top_text(root):
    top_path = require_file(root, "rtl/IntegerPLL_Top.v")
    text = top_path.read_text(encoding="ascii")
    missing = [needle for needle in TOP_REQUIRED_TEXT if needle not in text]
    if missing:
        raise ValueError(f"IntegerPLL_Top is missing expected macro interconnect text: {missing}")
    return {
        "top_rtl": str(top_path),
        "checked_interconnects": list(TOP_REQUIRED_TEXT),
    }


def check_macro_assembly(root):
    macro_rows = [check_macro(root, block, cfg) for block, cfg in EXPECTED.items()]
    top = check_top_text(root)
    total_area = sum(row["area_um2"] for row in macro_rows)
    source_files = sorted(
        {
            top["top_rtl"],
            str((root / "Makefile").resolve()),
            str((root / "scripts/check_top_macro_assembly.py").resolve()),
            *[row["source"] for row in macro_rows],
            *[row["lef"] for row in macro_rows],
            *[row["gds"] for row in macro_rows],
            *[row["def"] for row in macro_rows],
            *[row["netlist"] for row in macro_rows],
            *[row["sdc"] for row in macro_rows],
        }
    )
    return {
        "status": "pass",
        "macro_count": len(macro_rows),
        "macros": macro_rows,
        "top_interconnect": top,
        "total_macro_area_um2": total_area,
        "key_routes": {
            "bbpd_to_digital": "BBPD[1:0]",
            "digital_to_dco": "DCO_THERM[254:0]",
            "dco_to_digital_feedback": "PLLOUT",
            "digital_to_bbpd_feedback": "CLKDIV_RETIMED",
        },
        "source_files": source_files,
    }


def write_outputs(summary, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "top_macro_assembly_summary.json"
    csv_path = out_dir / "top_macro_assembly_summary.csv"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="ascii")
    with csv_path.open("w", newline="", encoding="ascii") as csv_file:
        fieldnames = (
            "block",
            "width_um",
            "height_um",
            "area_um2",
            "input_pins",
            "output_pins",
            "power_body_pins",
            "total_pins",
            "lef",
            "gds",
            "def",
            "netlist",
            "sdc",
        )
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        for row in summary["macros"]:
            writer.writerow(
                {
                    "block": row["block"],
                    "width_um": row["size_um"][0],
                    "height_um": row["size_um"][1],
                    "area_um2": row["area_um2"],
                    "input_pins": row["input_pins"],
                    "output_pins": row["output_pins"],
                    "power_body_pins": row["power_body_pins"],
                    "total_pins": row["total_pins"],
                    "lef": row["lef"],
                    "gds": row["gds"],
                    "def": row["def"],
                    "netlist": row["netlist"],
                    "sdc": row["sdc"],
                }
            )
    return json_path, csv_path


def main():
    parser = argparse.ArgumentParser(description="Check Sky130 PLL top macro assembly views.")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
        help="OpenPLL repository root.",
    )
    parser.add_argument(
        "--out-dir",
        default="build/top_macro_assembly",
        help="Output directory for JSON/CSV summary artifacts.",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    out_dir = root / args.out_dir if not Path(args.out_dir).is_absolute() else Path(args.out_dir)
    summary = check_macro_assembly(root)
    json_path, csv_path = write_outputs(summary, out_dir)
    print(f"top macro assembly pass: {summary['macro_count']} macros, area={summary['total_macro_area_um2']:.3f} um^2")
    print(f"wrote {json_path}")
    print(f"wrote {csv_path}")


if __name__ == "__main__":
    main()
