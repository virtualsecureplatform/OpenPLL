#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check simulator-facing extracted SPICE evidence for the hard-macro PLL top."""

import argparse
import json
import subprocess
from pathlib import Path


DEFAULT_TOP = "IntegerPLL_HardMacroTop"
DEFAULT_DCO_SUBCKT = "IntegerPLL_DCO"
DEFAULT_SPICE_REL = "openlane/IntegerPLL_HardMacroTop/runs/librelane_signoff/final/spice/IntegerPLL_HardMacroTop.spice"
DEFAULT_SPEF_REL = "openlane/IntegerPLL_HardMacroTop/runs/librelane_signoff/final/spef/nom/IntegerPLL_HardMacroTop.nom.spef"
DEFAULT_METRICS_REL = "openlane/IntegerPLL_HardMacroTop/runs/librelane_signoff/final/metrics.json"


def require_file(path):
    if not path.is_file():
        raise ValueError(f"missing file: {path}")
    if path.stat().st_size <= 0:
        raise ValueError(f"empty file: {path}")
    return path


def bit_net(name, index):
    return f"{name}[{index}]"


def expected_top_ports(coarse_binary_width):
    return [
        bit_net("BBPD_CODE", 0),
        bit_net("BBPD_CODE", 1),
        "CLKDIV_RETIMED",
        *(bit_net("COARSEBINARY_CODE", index) for index in range(coarse_binary_width)),
        *(bit_net("DCO_CODE", index) for index in range(8)),
        *(bit_net("DLF_CODE", index) for index in range(10)),
        "DLF_Clear",
        "DLF_En",
        *(bit_net("DLF_Ext_Data", index) for index in range(10)),
        "DLF_Ext_Override",
        "DLF_IN_POL",
        *(bit_net("DLF_KI", index) for index in range(8)),
        *(bit_net("DLF_KP", index) for index in range(5)),
        *(bit_net("MMDCLKDIV_RATIO", index) for index in range(8)),
        "PLLOUT",
        "PLLOUT_DIV",
        "REF",
        "RESET_N",
        "VGND",
        "VNB",
        "VPB",
        "VPWR",
    ]


def iter_spice_statements(path):
    current = ""
    for line in path.read_text(encoding="ascii", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("*"):
            continue
        if stripped.startswith("+"):
            current += " " + stripped[1:].strip()
            continue
        if current:
            yield current
        current = stripped
    if current:
        yield current


def parse_spice(path):
    subckts = {}
    instances = {}
    for statement in iter_spice_statements(path):
        tokens = statement.split()
        if not tokens:
            continue
        if tokens[0].lower() == ".subckt" and len(tokens) >= 2:
            subckts[tokens[1]] = tokens[2:]
        elif tokens[0].startswith("X") and len(tokens) >= 2:
            instances[tokens[0]] = {
                "subckt": tokens[-1],
                "nodes": tokens[1:-1],
            }
    return subckts, instances


def instance_port_map(subckts, instances, instance_name, subckt_name):
    if subckt_name not in subckts:
        raise ValueError(f"missing subckt {subckt_name}")
    instance = instances.get(instance_name)
    if instance is None:
        raise ValueError(f"missing instance {instance_name}")
    if instance["subckt"] != subckt_name:
        raise ValueError(f"{instance_name} subckt {instance['subckt']} != {subckt_name}")
    ports = subckts[subckt_name]
    nodes = instance["nodes"]
    if len(ports) != len(nodes):
        raise ValueError(f"{instance_name} has {len(nodes)} nodes for {len(ports)} ports")
    return dict(zip(ports, nodes))


def reset_gate_port_map(subckts, instances):
    instance = instances.get("X_0_")
    if instance is None:
        raise ValueError("missing instance X_0_")
    if instance["subckt"] not in {"sky130_fd_sc_hd__and3b_1", "sky130_fd_sc_hd__and3b_2"}:
        raise ValueError(f"unexpected reset-gate cell {instance['subckt']}")
    return instance_port_map(subckts, instances, "X_0_", instance["subckt"]), instance["subckt"]


def parse_spef_counts(path):
    name_map = {}
    d_nets = 0
    caps = 0
    resistors = 0
    in_cap = False
    in_res = False
    for line in path.read_text(encoding="ascii", errors="replace").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        parts = stripped.split(maxsplit=1)
        if len(parts) == 2 and parts[0].startswith("*") and parts[0][1:].isdigit():
            name_map[parts[0]] = parts[1]
        if stripped.startswith("*D_NET"):
            d_nets += 1
            in_cap = False
            in_res = False
        elif stripped.startswith("*CAP"):
            in_cap = True
            in_res = False
        elif stripped.startswith("*RES"):
            in_res = True
            in_cap = False
        elif stripped.startswith("*END"):
            in_cap = False
            in_res = False
        elif not stripped.startswith("*"):
            if in_cap:
                caps += 1
            if in_res:
                resistors += 1
    return {
        "name_map_entries": len(name_map),
        "d_nets": d_nets,
        "cap_entries": caps,
        "res_entries": resistors,
        "names": set(name_map.values()),
    }


def dco_interface(dco_subckt):
    if dco_subckt == "IntegerPLL_DCO_EINVP_COARSE":
        return {
            "coarse_binary_width": 6,
            "coarse_thermal_width": 47,
        }
    return {
        "coarse_binary_width": 6,
        "coarse_thermal_width": 0,
    }


def check_spice_interface(spice_path, spef_path, top, dco_subckt):
    subckts, instances = parse_spice(spice_path)
    interface = dco_interface(dco_subckt)

    top_ports = subckts.get(top)
    expected_ports = expected_top_ports(interface["coarse_binary_width"])
    if top_ports != expected_ports:
        raise ValueError("hard-top extracted SPICE top ports do not match expected wrapper interface")

    bbpd_map = instance_port_map(subckts, instances, "Xphase_detector", "IntegerPLL_BBPD")
    digital_map = instance_port_map(subckts, instances, "Xdigital_core", "IntegerPLL_DigitalCore")
    dco_map = instance_port_map(subckts, instances, "Xoscillator", dco_subckt)
    reset_gate, reset_gate_subckt = reset_gate_port_map(subckts, instances)

    expected_bbpd = {
        "BBPD[0]": "BBPD_CODE[0]",
        "BBPD[1]": "BBPD_CODE[1]",
        "CLKDIVR": "CLKDIV_RETIMED",
        "REF": "REF",
        "RESET_N": "_0_/X",
        "VGND": "VGND",
        "VNB": "VNB",
        "VPB": "VPB",
        "VPWR": "VPWR",
    }
    if bbpd_map != expected_bbpd:
        raise ValueError(f"unexpected BBPD extracted-SPICE mapping: {bbpd_map}")

    expected_reset_gate = {
        "A_N": "DLF_Clear",
        "B": "RESET_N",
        "C": "DLF_En",
        "VGND": "VGND",
        "VNB": "VGND",
        "VPB": "VPWR",
        "VPWR": "VPWR",
        "X": "_0_/X",
    }
    if reset_gate != expected_reset_gate:
        raise ValueError(f"unexpected BBPD reset-gate mapping: {reset_gate}")

    scalar_checks = {
        "CLKDIV_RETIMED": "CLKDIV_RETIMED",
        "DLF_Clear": "DLF_Clear",
        "DLF_En": "DLF_En",
        "DLF_Ext_Override": "DLF_Ext_Override",
        "DLF_IN_POL": "DLF_IN_POL",
        "PLLOUT": "PLLOUT",
        "PLLOUT_DIV": "PLLOUT_DIV",
        "RESET_N": "RESET_N",
        "VGND": "VGND",
        "VPWR": "VPWR",
    }
    for port, expected_node in scalar_checks.items():
        if digital_map.get(port) != expected_node:
            raise ValueError(f"digital core {port} maps to {digital_map.get(port)}")
    for port in ("PLLOUT", "RESET_N", "VGND", "VNB", "VPB", "VPWR"):
        if dco_map.get(port) != port:
            raise ValueError(f"DCO {port} maps to {dco_map.get(port)}")

    for index in range(2):
        port = bit_net("BBPD", index)
        expected = bit_net("BBPD_CODE", index)
        if digital_map.get(port) != expected:
            raise ValueError(f"digital core {port} maps to {digital_map.get(port)}")
    for prefix, width in (
        ("COARSEBINARY_CODE", interface["coarse_binary_width"]),
        ("DCO_CODE", 8),
        ("DLF_Ext_Data", 10),
        ("DLF_KI", 8),
        ("DLF_KP", 5),
        ("MMDCLKDIV_RATIO", 8),
    ):
        for index in range(width):
            port = bit_net(prefix, index)
            if digital_map.get(port) != port:
                raise ValueError(f"digital core {port} maps to {digital_map.get(port)}")

    coarse_thermal_connections = 0
    for index in range(interface["coarse_thermal_width"]):
        port = bit_net("COARSETHERMAL_CODE", index)
        digital_node = digital_map.get(port)
        dco_node = dco_map.get(port)
        if digital_node is None or dco_node is None:
            raise ValueError(f"missing DCO coarse thermometer port {port}")
        if digital_node != dco_node:
            raise ValueError(f"{port} maps to {digital_node} at digital core and {dco_node} at DCO")
        coarse_thermal_connections += 1

    antenna_dco_nets = []
    for index in range(255):
        port = bit_net("DCO_THERM", index)
        digital_node = digital_map.get(port)
        dco_node = dco_map.get(port)
        if digital_node is None or dco_node is None:
            raise ValueError(f"missing DCO thermometer port {port}")
        if digital_node != dco_node:
            raise ValueError(f"{port} maps to {digital_node} at digital core and {dco_node} at DCO")
        if digital_node.startswith("ANTENNA_"):
            antenna_dco_nets.append(port)
    spef = parse_spef_counts(spef_path)
    if spef["d_nets"] < 300 or spef["cap_entries"] < 9000 or spef["res_entries"] < 1400:
        spef_counts = {
            "d_nets": spef["d_nets"],
            "cap_entries": spef["cap_entries"],
            "res_entries": spef["res_entries"],
            "name_map_entries": spef["name_map_entries"],
        }
        raise ValueError(f"hard-top SPEF is unexpectedly small: {spef_counts}")
    key_spef_names = {
        "BBPD_CODE[0]",
        "BBPD_CODE[1]",
        "CLKDIV_RETIMED",
        "DCO_CODE[0]",
        "DCO_CODE[7]",
        "PLLOUT",
        "PLLOUT_DIV",
        "REF",
        "RESET_N",
    }
    missing_spef_names = sorted(key_spef_names - spef["names"])
    if missing_spef_names:
        raise ValueError(f"hard-top SPEF missing key names: {missing_spef_names}")

    return {
        "top_port_count": len(top_ports),
        "bbpd_ports": len(bbpd_map),
        "digital_core_ports": len(digital_map),
        "dco_ports": len(dco_map),
        "dco_subckt": dco_subckt,
        "reset_gate_subckt": reset_gate_subckt,
        "dco_coarse_therm_connections": coarse_thermal_connections,
        "dco_therm_connections": 255,
        "antenna_dco_therm_connections": len(antenna_dco_nets),
        "spef_d_nets": spef["d_nets"],
        "spef_cap_entries": spef["cap_entries"],
        "spef_res_entries": spef["res_entries"],
    }


def syntax_deck(spice_path, top_ports, top):
    body = []
    for line in spice_path.read_text(encoding="ascii", errors="replace").splitlines():
        if line.strip().lower() == ".end":
            continue
        body.append(line)

    source_lines = []
    top_nodes = []
    high_pins = {"VPWR", "VPB", "RESET_N", "DLF_En", "DLF_IN_POL"}
    for index, port in enumerate(top_ports):
        node = f"TOP_{index}"
        top_nodes.append(node)
        voltage = "1.8" if port in high_pins else "0"
        source_lines.append(f"VDRV{index:03d} {node} 0 {voltage}")

    return "\n".join(
        [
            *body,
            "",
            "* OpenPLL extracted hard-macro top Xyce syntax/topology probe.",
            *source_lines,
            "XTOP " + " ".join(top_nodes) + f" {top}",
            ".tran 1p 1p",
            ".end",
            "",
        ]
    )


def run_xyce_norun(xyce, deck_path, log_path, timeout_s):
    proc = subprocess.run(
        [xyce, "-norun", str(deck_path)],
        cwd=deck_path.parent,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout_s,
        check=False,
    )
    log_path.write_text(proc.stdout, encoding="utf-8")
    if proc.returncode != 0:
        raise ValueError(f"Xyce -norun failed with code {proc.returncode}; see {log_path}")
    if "Syntax and topology analysis complete" not in proc.stdout:
        raise ValueError(f"Xyce -norun log did not report topology completion: {log_path}")
    return {
        "command": " ".join([xyce, "-norun", str(deck_path)]),
        "returncode": proc.returncode,
        "log": str(log_path),
    }


def resolve_path(root, path_text):
    path = Path(path_text).expanduser()
    if not path.is_absolute():
        path = root / path
    return path


def check_hard_macro_top_spice(
    root,
    out_dir,
    xyce,
    timeout_s,
    spice_rel,
    spef_rel,
    metrics_rel,
    top,
    dco_subckt,
):
    spice_path = require_file(resolve_path(root, spice_rel))
    spef_path = require_file(resolve_path(root, spef_rel))
    metrics_path = require_file(resolve_path(root, metrics_rel))

    summary = check_spice_interface(spice_path, spef_path, top, dco_subckt)
    top_ports = parse_spice(spice_path)[0][top]

    out_dir.mkdir(parents=True, exist_ok=True)
    deck_path = out_dir / "hard_macro_top_spice_norun.spice"
    log_path = out_dir / "hard_macro_top_spice_norun.log"
    deck_path.write_text(syntax_deck(spice_path, top_ports, top), encoding="ascii")
    xyce_summary = run_xyce_norun(xyce, deck_path, log_path, timeout_s)

    return {
        "status": "pass",
        "top": top,
        "spice": str(spice_path),
        "spef": str(spef_path),
        "metrics": str(metrics_path),
        "generated_deck": str(deck_path),
        "xyce_norun": xyce_summary,
        **summary,
        "source_files": [str(spice_path), str(spef_path), str(metrics_path), str(deck_path), str(log_path)],
    }


def main():
    parser = argparse.ArgumentParser(description="Check extracted-SPICE hard-macro top interface evidence.")
    parser.add_argument(
        "--root",
        default=str(Path(__file__).resolve().parents[1]),
        help="OpenPLL repository root.",
    )
    parser.add_argument(
        "--out-dir",
        default="build/hard_macro_top_spice",
        help="Output directory for generated deck/log/summary.",
    )
    parser.add_argument("--top", default=DEFAULT_TOP, help="Extracted SPICE top subckt name.")
    parser.add_argument("--dco-subckt", default=DEFAULT_DCO_SUBCKT, help="Expected oscillator macro subckt name.")
    parser.add_argument("--spice", default=DEFAULT_SPICE_REL, help="Extracted hard-top SPICE path.")
    parser.add_argument("--spef", default=DEFAULT_SPEF_REL, help="Nominal hard-top SPEF path.")
    parser.add_argument("--metrics", default=DEFAULT_METRICS_REL, help="Hard-top metrics JSON path.")
    parser.add_argument("--xyce", default="Xyce", help="Xyce executable for syntax/topology check.")
    parser.add_argument("--timeout-s", type=float, default=120.0)
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = root / out_dir

    summary = check_hard_macro_top_spice(
        root,
        out_dir,
        args.xyce,
        args.timeout_s,
        args.spice,
        args.spef,
        args.metrics,
        args.top,
        args.dco_subckt,
    )
    json_path = out_dir / "hard_macro_top_spice_summary.json"
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="ascii")
    print(
        "hard macro top extracted SPICE pass: "
        f"{summary['top_port_count']} top ports, "
        f"{summary['dco_therm_connections']} DCO thermometer connections, "
        f"{summary['spef_cap_entries']} SPEF caps, "
        f"{summary['spef_res_entries']} SPEF resistors"
    )
    print(f"wrote {json_path}")


if __name__ == "__main__":
    main()
