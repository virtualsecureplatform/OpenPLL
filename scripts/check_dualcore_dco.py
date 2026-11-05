#!/usr/bin/env python3
"""Verify the isolated two-core DCO's selection and intentional drivers."""
import argparse
import hashlib
import json
from pathlib import Path

from check_parallel_dco import validate as validate_core


TOP = "IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALCORE"
FAST = "IntegerPLL_DCO_EINVP_COARSE_V5_TURN10"
SLOW = "IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8"


def bit(module, name):
    bits = module["netnames"][name]["bits"]
    if len(bits) != 1:
        raise ValueError(f"{name} is not a single net")
    return bits[0]


def component(module, prefix, top, report):
    cells = {name[len(prefix) + 1:]: cell
             for name, cell in module["cells"].items()
             if name.startswith(prefix + ".")}
    nets = {name[len(prefix) + 1:]: value
            for name, value in module["netnames"].items()
            if name.startswith(prefix + ".")}
    ports = {
        bus: {"bits": [bit(module, f"{prefix}.{bus}[{i}]")
                        for i in range(width)]}
        for bus, width in (("COARSETHERMAL_CODE", 47), ("DCO_THERM", 255))
    }
    warnings = [line.replace(f"{TOP}.\\{prefix}.", f"{top}.\\")
                for line in report.splitlines()
                if line.startswith("Warning:") and f"{TOP}.\\{prefix}." in line]
    if len(warnings) != 7:
        raise ValueError(f"{prefix} has {len(warnings)} driver warnings, expected 7")
    subreport = "\n".join(warnings) + "\nFound and reported 7 problems.\n"
    return validate_core({"modules": {top: {"cells": cells,
                                              "netnames": nets,
                                              "ports": ports}}}, subreport, top)


def validate(netlist, report):
    module = netlist["modules"][TOP]
    cells = module["cells"]
    coarse = module["ports"]["COARSETHERMAL_CODE"]["bits"]
    therm = module["ports"]["DCO_THERM"]["bits"]
    out = module["ports"]["PLLOUT"]["bits"]
    if len(coarse) != 47 or len(therm) != 255 or len(out) != 1:
        raise ValueError("top-level DCO port widths are invalid")

    sel = cells["select_lower_band"]
    remap = cells["remap_slow_first"]
    mux = cells["output_select"]
    fast_out = cells["fast_core.out_buf"]["connections"]["X"]
    slow_out = cells["slow_core.out_buf"]["connections"]["X"]
    if (sel["type"] != "sky130_fd_sc_hd__and2b_1"
            or sel["connections"] != {"A_N": [coarse[1]], "B": [coarse[0]],
                                       "X": mux["connections"]["S"]}
            or remap["type"] != "sky130_fd_sc_hd__and2_4"
            or remap["connections"]["A"] != [coarse[0]]
            or remap["connections"]["B"] != [coarse[1]]
            or mux["type"] != "sky130_fd_sc_hd__mux2_1"
            or mux["connections"] != {"A0": fast_out, "A1": slow_out,
                                      "S": sel["connections"]["X"], "X": out}):
        raise ValueError("two-core output selection or coarse decode is invalid")
    for i in range(47):
        if bit(module, f"fast_core.COARSETHERMAL_CODE[{i}]") != coarse[i]:
            raise ValueError(f"fast-core coarse bit {i} is miswired")
        expected = remap["connections"]["X"][0] if i == 0 else coarse[i]
        if bit(module, f"slow_core.COARSETHERMAL_CODE[{i}]") != expected:
            raise ValueError(f"slow-core coarse bit {i} is miswired")
    for prefix in ("fast_core", "slow_core"):
        for i in range(255):
            if bit(module, f"{prefix}.DCO_THERM[{i}]") != therm[i]:
                raise ValueError(f"{prefix} fine bit {i} is miswired")

    warnings = [line for line in report.splitlines() if line.startswith("Warning:")]
    if (len(warnings) != 14 or "Found and reported 14 problems." not in report
            or "ERROR:" in report):
        raise ValueError("unexpected synthesis diagnostics")
    fast = component(module, "fast_core", FAST, report)
    slow = component(module, "slow_core", SLOW, report)
    if fast["independent_fine_loads"] != 255 or slow["independent_fine_loads"] != 255:
        raise ValueError("both cores require all 255 fine loads")
    return {"passed": True, "scope": "experimental_layout_only",
            "top": TOP, "cores": {"fast": fast, "slow": slow},
            "intentional_driver_warnings": 14}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("netlist", type=Path)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = validate(json.loads(args.netlist.read_text()), args.report.read_text())
    result["sha256"] = {str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in (args.netlist, args.report, Path(__file__))}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(f"PASS: {TOP} has two isolated, correctly selected DCO cores")


if __name__ == "__main__":
    main()
