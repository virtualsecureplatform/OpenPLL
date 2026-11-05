#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Exercise the synthesized experimental 450 MHz wrapper's control wiring."""
import argparse
import hashlib
import json
from pathlib import Path

TOP = "IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_OSC8_C1LOAD64_REMAP_DBUF_GUARD"


def validate(netlist, fast_zero_alias=False):
    module = netlist["modules"][TOP]
    cells = module["cells"]
    cores = {name: cells[name]["connections"] for name in ("fast_core", "slow_core")}
    cases = 0
    for coarse in range(48):
        for fine in (0, 8, 73, 247, 255):
            values = {"0": 0, "1": 1}
            for port, value in (("COARSETHERMAL_CODE", (1 << coarse) - 1),
                                ("DCO_THERM", (1 << fine) - 1),
                                ("RESET_N", 1), ("VPWR", 1), ("VPB", 1),
                                ("VGND", 0), ("VNB", 0)):
                for i, bit in enumerate(module["ports"][port]["bits"]):
                    values[bit] = (value >> i) & 1
            for name, output in (("fast_core", 0), ("slow_core", 1)):
                values[cores[name]["PLLOUT"][0]] = output
            pending = {name: cell for name, cell in cells.items() if name not in cores}
            while pending:
                advanced = []
                for name, cell in pending.items():
                    c = cell["connections"]
                    inputs = {p: bits[0] for p, bits in c.items()
                              if p not in ("X", "VPWR", "VGND", "VPB", "VNB")}
                    if not all(bit in values for bit in inputs.values()):
                        continue
                    v = {p: values[bit] for p, bit in inputs.items()}
                    kind = cell["type"]
                    if kind in ("sky130_fd_sc_hd__buf_1", "sky130_fd_sc_hd__buf_8"):
                        out = v["A"]
                    elif kind == "sky130_fd_sc_hd__and2b_1":
                        out = (1 - v["A_N"]) & v["B"]
                    elif kind == "sky130_fd_sc_hd__and2_4":
                        out = v["A"] & v["B"]
                    elif kind == "sky130_fd_sc_hd__or2_1":
                        out = v["A"] | v["B"]
                    elif kind == "sky130_fd_sc_hd__or2b_4":
                        out = v["A"] | (1 - v["B_N"])
                    elif kind == "sky130_fd_sc_hd__mux2_1":
                        out = v["A1"] if v["S"] else v["A0"]
                    else:
                        raise ValueError(f"unsupported wrapper cell {name}: {kind}")
                    values[c["X"][0]] = out
                    advanced.append(name)
                if not advanced:
                    raise ValueError("unresolved or cyclic wrapper controls")
                for name in advanced:
                    del pending[name]
            expected_coarse = [int(i < max(0, coarse - 1)) for i in range(47)]
            expected_fine = [int(i < fine) for i in range(255)]
            for name, ports in cores.items():
                mapped_coarse = ([int(i < (1 if coarse == 0 else max(0, coarse - 1)))
                                  for i in range(47)]
                                 if name == "fast_core" and fast_zero_alias else expected_coarse)
                for port, expected in (("COARSETHERMAL_CODE", mapped_coarse),
                                       ("DCO_THERM", expected_fine), ("RESET_N", [1])):
                    actual = [values[bit] for bit in ports[port]]
                    if actual != expected:
                        raise ValueError(f"{name}/{port} miswired at coarse={coarse}, fine={fine}")
            selected = values[module["ports"]["PLLOUT"]["bits"][0]]
            if selected != int(coarse in (1, 2, 4, 5)):
                raise ValueError(f"wrong output selection at coarse={coarse}")
            cases += 1
    return {"passed": True, "cases": cases, "fast_zero_alias": fast_zero_alias,
            "scope": "synthesized control forwarding and macro selection; excludes oscillator behavior"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("netlist", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fast-zero-alias", action="store_true")
    args = parser.parse_args()
    args.output.unlink(missing_ok=True)
    result = validate(json.loads(args.netlist.read_text()), args.fast_zero_alias)
    result["netlist_sha256"] = hashlib.sha256(args.netlist.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
