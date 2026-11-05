#!/usr/bin/env python3
"""Check synthesized flat 450 MHz candidate wiring and retained DCO banks."""
import argparse
import hashlib
import json
from pathlib import Path


TOP = "IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_FLATDUAL_OSC8_C1LOAD64_REMAP"


def validate(netlist):
    module = netlist["modules"][TOP]
    cells = module["cells"]
    nets = module["netnames"]
    ports = module["ports"]
    coarse = ports["COARSETHERMAL_CODE"]["bits"]
    fine = ports["DCO_THERM"]["bits"]
    if len(coarse) != 47 or len(fine) != 255 or len(ports["PLLOUT"]["bits"]) != 1:
        raise ValueError("invalid wrapper port widths")

    def net(name):
        bits = nets[name]["bits"]
        if len(bits) != 1:
            raise ValueError(f"{name} is not one bit")
        return bits[0]

    for label, low, high in (("first", 0, 1), ("second", 1, 2),
                             ("fourth", 3, 4), ("fifth", 4, 5)):
        cell = cells[f"select_{label}_lower_band"]
        c = cell["connections"]
        if (cell["type"] != "sky130_fd_sc_hd__and2b_1"
                or c["A_N"] != [coarse[high]] or c["B"] != [coarse[low]]):
            raise ValueError(f"{label} slow-band selection is miswired")
    for name, a, b in (
        ("combine_first_two_lower_bands", "first_lower_select", "second_lower_select"),
        ("combine_last_two_lower_bands", "fourth_lower_select", "fifth_lower_select"),
        ("combine_lower_bands", "first_two_lower_select", "last_two_lower_select"),
    ):
        cell = cells[name]
        c = cell["connections"]
        if cell["type"] != "sky130_fd_sc_hd__or2_1" or {c["A"][0], c["B"][0]} != {net(a), net(b)}:
            raise ValueError(f"{name} is miswired")
    for name, low, high in (("remap_slow_first", 0, 1),
                            ("remap_slow_second", 1, 2)):
        cell = cells[name]
        c = cell["connections"]
        if (cell["type"] != "sky130_fd_sc_hd__and2_4"
                or {c["A"][0], c["B"][0]} != {coarse[low], coarse[high]}):
            raise ValueError(f"{name} is miswired")
    fast_alias = cells["remap_fast_zero_to_first"]
    if (fast_alias["type"] != "sky130_fd_sc_hd__or2b_2"
            or fast_alias["connections"]["A"] != [coarse[1]]
            or fast_alias["connections"]["B_N"] != [coarse[0]]):
        raise ValueError("fast coarse-zero alias is miswired")
    mux = cells["output_select"]
    c = mux["connections"]
    if (mux["type"] != "sky130_fd_sc_hd__mux2_1"
            or c != {"A0": cells["fast_core.out_buf"]["connections"]["X"],
                     "A1": cells["slow_core.out_buf"]["connections"]["X"],
                     "S": [net("lower_band_select")],
                     "X": ports["PLLOUT"]["bits"]}):
        raise ValueError("output mux is miswired")

    for i in range(47):
        expected_fast = (fast_alias["connections"]["X"][0] if i == 0
                         else coarse[i + 1] if i < 46 else "0")
        expected_slow = (cells["remap_slow_first"]["connections"]["X"][0] if i == 0
                         else cells["remap_slow_second"]["connections"]["X"][0] if i == 1
                         else coarse[i + 1] if i < 46 else "0")
        if net(f"fast_core.COARSETHERMAL_CODE[{i}]") != expected_fast:
            raise ValueError(f"fast coarse bit {i} is miswired")
        if net(f"slow_core.COARSETHERMAL_CODE[{i}]") != expected_slow:
            raise ValueError(f"slow coarse bit {i} is miswired")
    for prefix in ("fast_core", "slow_core"):
        for port in ("RESET_N", "VPWR", "VGND", "VPB", "VNB"):
            if net(f"{prefix}.{port}") != ports[port]["bits"][0]:
                raise ValueError(f"{prefix} {port} is miswired")
        loads = {name: cell for name, cell in cells.items()
                 if name.startswith(f"{prefix}.gen_dco_load[")}
        if len(loads) != 255:
            raise ValueError(f"{prefix} has {len(loads)} fine loads, expected 255")
        for i in range(255):
            if net(f"{prefix}.DCO_THERM[{i}]") != fine[i]:
                raise ValueError(f"{prefix} fine bit {i} is miswired")
            matches = [cell for name, cell in loads.items()
                       if name.startswith(f"{prefix}.gen_dco_load[{i}].")]
            if (len(matches) != 1 or matches[0]["type"] != "sky130_fd_sc_hd__einvp_1"
                    or matches[0]["connections"]["TE"] != [fine[i]]):
                raise ValueError(f"{prefix} fine load {i} is miswired")
    fixed = [name for name in cells if name.startswith("slow_core.gen_c1_load[")]
    boosts = [name for name in cells if name.startswith("fast_core.gen_osc_boost[")]
    if len(fixed) != 64 or len(boosts) != 4:
        raise ValueError(f"wrong core variant: fixed={len(fixed)}, boost={len(boosts)}")
    return {"passed": True, "fine_loads_per_core": 255,
            "slow_fixed_loads": len(fixed), "fast_oscillator_boosts": len(boosts),
            "scope": "synthesized wiring and cell count; excludes oscillation and PVT"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("netlist", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.unlink(missing_ok=True)
    result = validate(json.loads(args.netlist.read_text()))
    result["netlist_sha256"] = hashlib.sha256(args.netlist.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
