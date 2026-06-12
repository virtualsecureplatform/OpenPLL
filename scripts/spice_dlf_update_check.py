#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import concurrent.futures
import csv
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from xyce_utils import add_xyce_arguments, validate_xyce_arguments, xyce_simulator_command


RE_FLOAT = r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"
INSTANCE_START_RE = re.compile(
    r"^\s*(sky130_fd_sc_hd__[A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\s*\((.*)$"
)
PIN_RE = re.compile(r"\.([A-Za-z0-9_]+)\s*\(\s*(.*?)\s*\)", re.DOTALL)
OUTPUT_PINS = {"X", "Y", "Q", "Q_N", "SUM", "COUT"}
SUPPLY_NETS = {
    "VPWR": "VPWR",
    "VPB": "VPWR",
    "VGND": "VGND",
    "VNB": "VGND",
}
SPEF_CAP_UNIT_TO_F = {
    "F": 1.0,
    "PF": 1e-12,
    "NF": 1e-9,
    "FF": 1e-15,
}

CASES = {
    "inc_mid": {
        "bbpd": 0b10,
        "start_dlf": 512,
        "expected": "increase",
    },
    "dec_mid": {
        "bbpd": 0b01,
        "start_dlf": 512,
        "expected": "decrease",
    },
    "inc_overlap": {
        "bbpd_first": 0b10,
        "start_dlf": 512,
        "expected": "increase",
    },
    "dec_overlap": {
        "bbpd_first": 0b01,
        "start_dlf": 512,
        "expected": "decrease",
    },
    "inc_bbpd_rcx": {
        "bbpd_rcx": "ref_leads",
        "ref_delay_ns": 31.0,
        "div_delay_ns": 34.0,
        "start_dlf": 512,
        "expected": "increase",
    },
    "dec_bbpd_rcx": {
        "bbpd_rcx": "fb_leads",
        "ref_delay_ns": 34.0,
        "div_delay_ns": 31.0,
        "start_dlf": 512,
        "expected": "decrease",
    },
}


def sanitize_net(name):
    name = name.strip()
    if name.startswith("\\"):
        name = name[1:].strip()
    name = name.replace("[", "_").replace("]", "")
    name = re.sub(r"[^A-Za-z0-9_]+", "_", name)
    name = name.strip("_")
    if not name:
        return "NC"
    if name[0].isdigit():
        name = f"n_{name}"
    return name


def bit_net(name, index):
    return sanitize_net(f"{name}[{index}]")


def decode_spef_name(name, name_map):
    if ":" in name:
        base, suffix = name.split(":", 1)
        if base.startswith("*"):
            base = name_map.get(base, base)
        name = f"{base}:{suffix}"
    elif name.startswith("*"):
        name = name_map.get(name, name)
    name = name.replace("\\", "")
    return name


def spef_spice_node(name, name_map):
    decoded = decode_spef_name(name, name_map)
    if ":" not in decoded:
        return sanitize_net(decoded)
    base, suffix = decoded.split(":", 1)
    return f"SPEF_{sanitize_net(base)}_{sanitize_net(suffix)}"


def spef_instance_pin(name, name_map):
    decoded = decode_spef_name(name, name_map)
    if ":" not in decoded:
        return None
    instance_name, pin = decoded.split(":", 1)
    return instance_name, pin


def parse_spef_header(lines):
    name_map = {}
    cap_unit_f = 1e-12
    res_unit_ohm = 1.0
    in_name_map = False
    for line in lines:
        stripped = line.strip()
        if stripped == "*NAME_MAP":
            in_name_map = True
            continue
        if in_name_map:
            parts = stripped.split(maxsplit=1)
            if len(parts) == 2 and parts[0].startswith("*") and parts[0][1:].isdigit():
                name_map[parts[0]] = parts[1]
                continue
            if stripped.startswith("*"):
                in_name_map = False
        if stripped.startswith("*C_UNIT"):
            parts = stripped.split()
            if len(parts) >= 3:
                unit = parts[2].upper()
                if unit not in SPEF_CAP_UNIT_TO_F:
                    raise ValueError(f"unsupported SPEF capacitance unit {unit!r}")
                cap_unit_f = float(parts[1]) * SPEF_CAP_UNIT_TO_F[unit]
        elif stripped.startswith("*R_UNIT"):
            parts = stripped.split()
            if len(parts) >= 3:
                if parts[2].upper() != "OHM":
                    raise ValueError(f"unsupported SPEF resistance unit {parts[2]!r}")
                res_unit_ohm = float(parts[1])

    return name_map, cap_unit_f, res_unit_ohm


def parse_spef_lumped_caps(spef_path, candidate_nets):
    lines = Path(spef_path).read_text(encoding="ascii", errors="replace").splitlines()
    name_map, cap_unit_f, _ = parse_spef_header(lines)

    caps = {}
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("*D_NET"):
            continue
        parts = stripped.split()
        if len(parts) < 3:
            continue
        net = sanitize_net(decode_spef_name(parts[1], name_map))
        if net not in candidate_nets or net in SUPPLY_NETS:
            continue
        cap_f = float(parts[2]) * cap_unit_f
        if cap_f <= 0:
            continue
        caps[net] = caps.get(net, 0.0) + cap_f
    return caps


def parse_spef_distributed_rc(spef_path, candidate_nets):
    lines = Path(spef_path).read_text(encoding="ascii", errors="replace").splitlines()
    name_map, cap_unit_f, res_unit_ohm = parse_spef_header(lines)
    pin_nodes = {}
    cap_values = {}
    resistor_lines = []
    current_net = None
    current_mode = None
    resistor_index = 0

    def add_cap(node, cap_f):
        if cap_f <= 0:
            return
        cap_values[node] = cap_values.get(node, 0.0) + cap_f

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("*D_NET"):
            parts = stripped.split()
            current_net = None
            current_mode = None
            if len(parts) >= 3:
                net = sanitize_net(decode_spef_name(parts[1], name_map))
                if net in candidate_nets and net not in SUPPLY_NETS:
                    current_net = net
            continue
        if current_net is None:
            continue
        if stripped == "*END":
            current_net = None
            current_mode = None
            continue
        if stripped == "*CONN":
            current_mode = "conn"
            continue
        if stripped == "*CAP":
            current_mode = "cap"
            continue
        if stripped == "*RES":
            current_mode = "res"
            continue

        parts = stripped.split()
        if current_mode == "conn" and len(parts) >= 3 and parts[0] == "*I":
            instance_pin = spef_instance_pin(parts[1], name_map)
            if instance_pin is not None:
                pin_nodes[instance_pin] = spef_spice_node(parts[1], name_map)
        elif current_mode == "cap" and len(parts) >= 3:
            cap_f = float(parts[-1]) * cap_unit_f
            node = spef_spice_node(parts[1], name_map)
            # Coupling entries are grounded at the current-net endpoint. This
            # preserves the current net's reported capacitance without adding
            # external neighbor nets to the reduced cone.
            add_cap(node, cap_f)
        elif current_mode == "res" and len(parts) >= 4:
            node_a = spef_spice_node(parts[1], name_map)
            node_b = spef_spice_node(parts[2], name_map)
            resistance = float(parts[3]) * res_unit_ohm
            if resistance <= 0:
                continue
            resistor_lines.append(
                f"RSPEF_{resistor_index:05d} {node_a} {node_b} {resistance:.9g}"
            )
            resistor_index += 1

    cap_lines = [
        f"CSPEF_{index:05d} {node} VGND {cap_f:.9e}"
        for index, (node, cap_f) in enumerate(sorted(cap_values.items()))
    ]
    return {
        "pin_nodes": pin_nodes,
        "cap_lines": cap_lines,
        "resistor_lines": resistor_lines,
        "cap_total_f": sum(cap_values.values()),
    }


def instance_net_names(instances):
    return {
        net
        for instance in instances
        for net in instance["conns"].values()
        if net not in SUPPLY_NETS
    }


def parse_subckt_ports(cell_spice_path):
    ports = {}
    for line in Path(cell_spice_path).read_text(encoding="utf-8").splitlines():
        if not line.startswith(".subckt "):
            continue
        parts = line.split()
        if len(parts) >= 3 and parts[1].startswith("sky130_fd_sc_hd__"):
            ports[parts[1]] = parts[2:]
    return ports


def parse_named_subckt_ports(spice_path, subckt_name):
    header = []
    in_header = False
    for line in Path(spice_path).read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines():
        stripped = line.strip()
        if stripped.startswith(f".subckt {subckt_name}"):
            header.append(stripped)
            in_header = True
            continue
        if in_header:
            if stripped.startswith("+"):
                header.append(stripped)
                continue
            break
    if not header:
        raise ValueError(f"subckt {subckt_name!r} not found in {spice_path}")

    tokens = []
    for index, line in enumerate(header):
        if index == 0:
            tokens.extend(line.split()[2:])
        else:
            tokens.extend(line[1:].split())
    return tokens


def parse_instances(verilog_text):
    instances = []
    current = None
    for line in verilog_text.splitlines():
        if current is None:
            match = INSTANCE_START_RE.match(line)
            if match is None:
                continue
            current = {
                "type": match.group(1),
                "name": match.group(2),
                "body_lines": [match.group(3)],
            }
        else:
            current["body_lines"].append(line)

        if ");" not in line:
            continue

        body = "\n".join(current["body_lines"]).rsplit(");", 1)[0]
        conns = {}
        for pin_match in PIN_RE.finditer(body):
            conns[pin_match.group(1)] = sanitize_net(pin_match.group(2))
        instances.append(
            {
                "type": current["type"],
                "name": current["name"],
                "conns": conns,
            }
        )
        current = None
    return instances


def output_pins(instance):
    return [pin for pin in instance["conns"] if pin in OUTPUT_PINS]


def input_pins(instance):
    return [
        pin
        for pin in instance["conns"]
        if pin not in OUTPUT_PINS and pin not in SUPPLY_NETS
    ]


def extract_cone(instances, output_nets, input_nets):
    drivers = {}
    for instance in instances:
        for pin in output_pins(instance):
            drivers[instance["conns"][pin]] = instance

    needed = set()
    stack = list(output_nets)
    while stack:
        net = stack.pop()
        if net in input_nets:
            continue
        driver = drivers.get(net)
        if driver is None:
            raise ValueError(f"no driver found for required DLF net {net}")
        if driver["index"] in needed:
            continue
        needed.add(driver["index"])
        for pin in input_pins(driver):
            stack.append(driver["conns"][pin])

    return [instance for instance in instances if instance["index"] in needed]


def spice_instance_lines(instances, subckt_ports, pin_node_map=None):
    pin_node_map = pin_node_map or {}
    lines = []
    missing = {}
    for instance in instances:
        cell_type = instance["type"]
        conns = instance["conns"]
        if cell_type not in subckt_ports:
            missing.setdefault(cell_type, 0)
            missing[cell_type] += 1
            continue

        nets = []
        for port in subckt_ports[cell_type]:
            if port in SUPPLY_NETS:
                nets.append(SUPPLY_NETS[port])
            elif (instance["name"], port) in pin_node_map:
                nets.append(pin_node_map[(instance["name"], port)])
            elif port in conns:
                nets.append(conns[port])
            else:
                nets.append(f"NC_{sanitize_net(instance['name'])}_{port}")
        lines.append(f"X{sanitize_net(instance['name'])} {' '.join(nets)} {cell_type}")

    if missing:
        missing_text = ", ".join(
            f"{cell_type} ({count})" for cell_type, count in sorted(missing.items())
        )
        raise ValueError(f"missing Sky130 SPICE subckt definitions: {missing_text}")
    return lines


def spef_lumped_cap_lines(spef_caps):
    if not spef_caps:
        return []
    lines = [
        "* Lumped post-route SPEF capacitances.",
    ]
    for index, (net, cap_f) in enumerate(sorted(spef_caps.items())):
        lines.append(f"CSPEF_{index:05d} {net} VGND {cap_f:.9e}")
    return lines


def spef_distributed_rc_lines(spef_rc):
    if not spef_rc:
        return []
    return [
        "* Distributed post-route SPEF RC.",
        *spef_rc["cap_lines"],
        *spef_rc["resistor_lines"],
    ]


def measure_value(log_text, name):
    for pattern in (
        rf"^\s*{name}\s*=\s*{RE_FLOAT}",
        rf"^\s*{name}\s*:\s*{RE_FLOAT}",
    ):
        match = re.search(pattern, log_text, re.IGNORECASE | re.MULTILINE)
        if match:
            return float(match.group(1))
    return None


def source_bit_lines(prefix, width, value):
    return [
        f"V{sanitize_net(prefix).upper()}{index} {bit_net(prefix, index)} 0 "
        f"{'{VDD}' if ((value >> index) & 1) else '0'}"
        for index in range(width)
    ]


def pwl_source_line(name, node, points):
    values = " ".join(f"{time_ns:g}n {value}" for time_ns, value in points)
    return f"V{name} {node} 0 PWL({values})"


def bbpd_source_lines(case, args):
    if "bbpd_rcx" in case:
        return []
    if "bbpd" in case:
        first = case["bbpd"]
    else:
        first = case["bbpd_first"]

    first_start_ns = max(
        args.clear_start_ns + args.clear_width_ns + 0.5,
        args.enable_ns + 0.5,
    )
    both_start_ns = first_start_ns + 1.5
    overlap_end_ns = args.enable_ns + args.clock_half_ns + 0.5
    fall_done_ns = overlap_end_ns + 0.05
    lines = []
    for index in range(2):
        first_active = ((first >> index) & 1) != 0
        both_active = True
        if first_active:
            points = [
                (0.0, "0"),
                (first_start_ns, "0"),
                (first_start_ns + 0.05, "{VDD}"),
                (overlap_end_ns, "{VDD}" if both_active else "0"),
                (fall_done_ns, "0"),
            ]
        else:
            points = [
                (0.0, "0"),
                (both_start_ns, "0"),
                (both_start_ns + 0.05, "{VDD}"),
                (overlap_end_ns, "{VDD}" if both_active else "0"),
                (fall_done_ns, "0"),
            ]
        lines.append(
            pwl_source_line(
                f"{sanitize_net('BBPD').upper()}{index}",
                bit_net("BBPD", index),
                points,
            )
        )
    return lines


def bbpd_rcx_lines(case, args):
    if "bbpd_rcx" not in case:
        return []

    rcx_path = Path(args.bbpd_rcx_netlist).expanduser().resolve()
    if not rcx_path.exists():
        raise FileNotFoundError(rcx_path)

    ports = parse_named_subckt_ports(rcx_path, args.bbpd_subckt)
    port_nets = {
        "BBPD[0]": bit_net("BBPD", 0),
        "BBPD[1]": bit_net("BBPD", 1),
        "CLKDIVR": "CLKDIVR_BBPD",
        "REF": "REF_BBPD",
        "RESET_N": "BBPD_RESET_N",
        "VGND": "VGND",
        "VNB": "VNB",
        "VPB": "VPB",
        "VPWR": "VPWR",
    }
    missing = [port for port in ports if port not in port_nets]
    if missing:
        raise ValueError(
            f"{args.bbpd_subckt} has unsupported ports: {', '.join(missing)}"
        )

    nodes = " ".join(port_nets[port] for port in ports)
    return [
        f"* Filled post-layout BBPD RCX source, polarity={case['bbpd_rcx']}.",
        "VREFBBPD REF_BBPD 0 "
        f"PULSE(0 {{VDD}} {case['ref_delay_ns']:g}n 20p 20p 2n 100n)",
        "VCLKBBPD CLKDIVR_BBPD 0 "
        f"PULSE(0 {{VDD}} {case['div_delay_ns']:g}n 20p 20p 2n 100n)",
        f"XBBPD {nodes} {args.bbpd_subckt}",
        ".ic v(BBPD_1)=0 v(BBPD_0)=0 "
        "v(XBBPD.up_ff.q)=0 v(XBBPD.dn_ff.q)=0 "
        "v(XBBPD.up_delay_0.x)=0 v(XBBPD.up_delay_1.x)=0 "
        "v(XBBPD.dn_delay_0.x)=0 v(XBBPD.dn_delay_1.x)=0 "
        "v(XBBPD.dn_ff.reset_b)=0",
    ]


def dco_code_meas_lines(prefix, when_ns):
    return [
        f".meas tran {prefix}_dco_code_{index} FIND v({bit_net('DCO_CODE', index)}) AT={when_ns:g}n"
        for index in range(8)
    ]


def measured_code(log_text, prefix, threshold):
    code = 0
    missing = []
    values = {}
    for index in range(8):
        name = f"{prefix}_dco_code_{index}"
        value = measure_value(log_text, name)
        values[index] = value
        if value is None:
            missing.append(index)
        elif value > threshold:
            code |= 1 << index
    return code, values, missing


def parse_xyce_code_extrema(waveform_path, start_ns, end_ns, threshold):
    if not waveform_path.exists():
        return None

    with waveform_path.open(encoding="utf-8", errors="replace") as waveform_file:
        header_line = waveform_file.readline()
        if not header_line:
            return None
        header = header_line.split()
        columns = {name: index for index, name in enumerate(header)}
        try:
            time_index = columns["TIME"]
            code_indices = [
                columns[f"V(DCO_CODE_{index})"]
                for index in range(8)
            ]
        except KeyError:
            return None

        min_code = None
        max_code = None
        samples = 0
        for line in waveform_file:
            parts = line.split()
            if len(parts) != len(header):
                continue
            try:
                time_ns = float(parts[time_index]) * 1e9
            except ValueError:
                continue
            if time_ns < start_ns or time_ns > end_ns:
                continue
            code = 0
            valid = True
            for index, column in enumerate(code_indices):
                try:
                    value = float(parts[column])
                except ValueError:
                    valid = False
                    break
                if value > threshold:
                    code |= 1 << index
            if not valid:
                continue
            samples += 1
            min_code = code if min_code is None else min(min_code, code)
            max_code = code if max_code is None else max(max_code, code)

    if samples == 0:
        return None
    return min_code, max_code, samples


def xyce_output_base(netlist_path):
    return netlist_path.with_suffix("")


def xyce_waveform_path(netlist_path):
    return Path(f"{xyce_output_base(netlist_path)}.prn")


def end_measure_ns(case, args):
    if "bbpd_first" in case or "bbpd_rcx" in case:
        return args.enable_ns + 4 * args.clock_half_ns + 2 * args.pllo_half_ns + 2.0
    return args.sim_time_ns - args.step_ps * 1e-3


def digital_core_netlist(case_name, args, instances, subckt_ports):
    case = CASES[case_name]
    pdk_root = Path(args.pdk_root).expanduser().resolve()
    pdk_dir = pdk_root / args.pdk
    model_path = pdk_dir / "libs.tech" / "ngspice" / "sky130.lib.spice"
    cell_path = (
        pdk_dir
        / "libs.ref"
        / args.std_cell_library
        / "spice"
        / f"{args.std_cell_library}.spice"
    )

    if not model_path.exists():
        raise FileNotFoundError(model_path)
    if not cell_path.exists():
        raise FileNotFoundError(cell_path)
    rcx_path = None
    if "bbpd_rcx" in case:
        rcx_path = Path(args.bbpd_rcx_netlist).expanduser().resolve()
        if not rcx_path.exists():
            raise FileNotFoundError(rcx_path)

    start_meas_ns = args.enable_ns - args.step_ps * 1e-3
    end_meas_ns = end_measure_ns(case, args)
    include_lines = [f'.include "{cell_path}"']
    if rcx_path is not None:
        include_lines.append(f'.include "{rcx_path}"')
    supply_lines = [
        "VVPWR VPWR 0 {VDD}",
        "VVGND VGND 0 0",
    ]
    if rcx_path is not None:
        supply_lines.extend(
            [
                "VVPB VPB 0 {VDD}",
                "VVNB VNB 0 0",
            ]
        )
    lines = [
        f"* OpenPLL synthesized Sky130 DLF update SPICE smoke, case={case_name}",
        f"* simulator={args.simulator}",
        f'.lib "{model_path}" {args.corner}',
        *include_lines,
        ".param VDD=1.8",
        *supply_lines,
        f"VRESET RESET_N 0 PULSE(0 {{VDD}} {args.reset_release_ns:g}n 50p 50p 1u 2u)",
        f"VDLFCLK CLKDIV_RETIMED 0 PULSE(0 {{VDD}} {args.clock_start_ns:g}n 50p 50p {args.clock_half_ns:g}n {2 * args.clock_half_ns:g}n)",
        f"VPLLOUT PLLOUT 0 PULSE(0 {{VDD}} {args.pllo_start_ns:g}n 50p 50p {args.pllo_half_ns:g}n {2 * args.pllo_half_ns:g}n)",
        f"VDLFEN DLF_En 0 PULSE(0 {{VDD}} {args.enable_ns:g}n 50p 50p 1u 2u)",
        f"VDLFCLEAR DLF_Clear 0 PULSE(0 {{VDD}} {args.clear_start_ns:g}n 50p 50p {args.clear_width_ns:g}n 2u)",
        "BBBPDRESET BBPD_RESET_N 0 "
        "V={v(RESET_N)*v(DLF_En)*(VDD-v(DLF_Clear))/(VDD*VDD)}",
        "VDLFOVERRIDE DLF_Ext_Override 0 0",
        "VDLFINPOL DLF_IN_POL 0 {VDD}",
        "",
        "* Static control words.",
        *bbpd_source_lines(case, args),
        *bbpd_rcx_lines(case, args),
        *source_bit_lines("DLF_Ext_Data", 10, case["start_dlf"]),
        *source_bit_lines("DLF_KI", 8, args.ki),
        *source_bit_lines("DLF_KP", 8, args.kp),
        *source_bit_lines("COARSEBINARY_CODE", 4, 5),
        *source_bit_lines("MMDCLKDIV_RATIO", 8, args.mmd_ratio),
        "",
        "* Full synthesized Sky130 digital core mapped netlist.",
        *spice_instance_lines(instances, subckt_ports, args.spef_pin_nodes),
        "",
        *spef_lumped_cap_lines(args.spef_caps),
        *spef_distributed_rc_lines(args.spef_rc),
        "",
        f".tran {args.step_ps:g}p {args.sim_time_ns:g}n uic",
        *dco_code_meas_lines("start", start_meas_ns),
        *dco_code_meas_lines("end", end_meas_ns),
        ".end",
        "",
    ]
    if args.simulator == "ngspice":
        lines.insert(
            4,
            ".option method=gear reltol=1e-3 abstol=1e-15 chgtol=1e-16"
            + (
                f" num_threads={args.ngspice_threads}"
                if args.ngspice_threads > 0
                else ""
            ),
        )
        insert_at = lines.index(f".tran {args.step_ps:g}p {args.sim_time_ns:g}n uic")
        save_lines = [
            ".save v(PLLOUT) v(CLKDIV_RETIMED) v(RESET_N) v(DLF_Clear) v(DLF_En)",
            *[f".save v({bit_net('DCO_CODE', index)})" for index in range(8)],
        ]
        lines[insert_at:insert_at] = save_lines
    else:
        insert_at = lines.index(f".tran {args.step_ps:g}p {args.sim_time_ns:g}n uic")
        print_nodes = [
            "PLLOUT",
            "CLKDIV_RETIMED",
            "RESET_N",
            "DLF_Clear",
            "DLF_En",
            "BBPD_RESET_N",
            *[bit_net("BBPD", index) for index in range(2)],
            *[bit_net("DCO_CODE", index) for index in range(8)],
        ]
        if args.print_internal_debug:
            print_nodes.extend(
                [
                    "clkdiv_sampled",
                    "clkdiv_sampled_d",
                    "bbpd_up_event_toggle",
                    "bbpd_up_event_sync",
                    "bbpd_up_event_consumed",
                    "bbpd_dn_event_toggle",
                    "bbpd_dn_event_sync",
                    "bbpd_dn_event_consumed",
                    "bbpd_seen_1",
                    "bbpd_seen_0",
                    "bbpd_decision_1",
                    "bbpd_decision_0",
                    "loop_filter_integ_acc__18",
                    "loop_filter_integ_acc__17",
                    "loop_filter_integ_acc__16",
                    "loop_filter_integ_acc__15",
                    "loop_filter_integ_acc__14",
                    "loop_filter_integ_acc__13",
                    "loop_filter_integ_acc__12",
                    "loop_filter_integ_acc__11",
                    "loop_filter_integ_acc__10",
                    "loop_filter_integ_acc__9",
                    "loop_filter_integ_acc__8",
                ]
            )
        if rcx_path is not None:
            print_nodes[5:5] = ["REF_BBPD", "CLKDIVR_BBPD"]
        lines.insert(
            insert_at,
            ".print tran " + " ".join(f"v({node})" for node in print_nodes),
        )
    return "\n".join(lines)


def simulator_command(args, netlist_path):
    if args.simulator == "ngspice":
        return [args.ngspice, "-b", str(netlist_path)]
    if args.simulator == "xyce":
        return xyce_simulator_command(args, netlist_path, xyce_output_base(netlist_path))
    raise ValueError(f"unsupported simulator: {args.simulator}")


def run_spice(args, netlist_path, build_dir):
    start = time.monotonic()
    env = os.environ.copy()
    if args.simulator == "ngspice" and args.ngspice_threads > 0:
        env["OMP_NUM_THREADS"] = str(args.ngspice_threads)
    proc = subprocess.Popen(
        simulator_command(args, netlist_path),
        cwd=build_dir,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    timed_out = False
    try:
        stdout, _ = proc.communicate(timeout=args.timeout_s)
    except subprocess.TimeoutExpired:
        timed_out = True
        proc.kill()
        stdout, _ = proc.communicate()
    elapsed_s = time.monotonic() - start
    if timed_out:
        stdout += (
            f"\nOpenPLL timeout: killed {args.simulator} after {args.timeout_s:.1f} s "
            f"for {netlist_path.name}\n"
        )
    return proc.returncode, timed_out, elapsed_s, stdout


def run_one(case_name, args, build_dir, instances, subckt_ports):
    netlist_path = build_dir / f"dlf_update_{case_name}.spice"
    log_path = build_dir / f"dlf_update_{case_name}.log"
    netlist_path.write_text(
        digital_core_netlist(case_name, args, instances, subckt_ports),
        encoding="ascii",
    )
    returncode, timed_out, elapsed_s, log_text = run_spice(args, netlist_path, build_dir)
    log_path.write_text(log_text, encoding="utf-8")

    start_code, _, start_missing = measured_code(log_text, "start", args.threshold)
    end_code, _, end_missing = measured_code(log_text, "end", args.threshold)
    response_start_ns = args.enable_ns
    response_end_ns = end_measure_ns(CASES[case_name], args)
    extrema = None
    if args.simulator == "xyce":
        extrema = parse_xyce_code_extrema(
            xyce_waveform_path(netlist_path),
            response_start_ns,
            response_end_ns,
            args.threshold,
        )
    if extrema is None:
        observed_min_code = None if end_missing else end_code
        observed_max_code = None if end_missing else end_code
        observed_samples = 0
    else:
        observed_min_code, observed_max_code, observed_samples = extrema
    expected = CASES[case_name]["expected"]
    if expected == "increase":
        response_code = observed_max_code
        moved = response_code is not None and response_code > start_code
    else:
        response_code = observed_min_code
        moved = response_code is not None and response_code < start_code
    ok = (
        returncode == 0
        and not timed_out
        and not start_missing
        and not end_missing
        and moved
    )

    return {
        "simulator": args.simulator,
        "xyce_mpi_procs": args.xyce_mpi_procs if args.simulator == "xyce" else "",
        "case": case_name,
        "status": "pass" if ok else "fail",
        "expected": expected,
        "scope": args.scope,
        "ki": args.ki,
        "kp": args.kp,
        "mmd_ratio": args.mmd_ratio,
        "spef": str(args.spef_path) if args.spef_path else "",
        "spef_mode": args.active_spef_mode,
        "spef_cap_nets": args.spef_cap_count,
        "spef_pin_nodes": len(args.spef_pin_nodes),
        "spef_resistors": args.spef_resistor_count,
        "spef_cap_total_ff": f"{args.spef_cap_total_f * 1e15:.3f}",
        "returncode": returncode,
        "timed_out": "yes" if timed_out else "no",
        "elapsed_s": f"{elapsed_s:.3f}",
        "start_meas_ns": f"{args.enable_ns - args.step_ps * 1e-3:.3f}",
        "end_meas_ns": f"{end_measure_ns(CASES[case_name], args):.3f}",
        "response_start_ns": f"{response_start_ns:.3f}",
        "response_end_ns": f"{response_end_ns:.3f}",
        "start_code": "" if start_missing else start_code,
        "end_code": "" if end_missing else end_code,
        "observed_min_code": "" if observed_min_code is None else observed_min_code,
        "observed_max_code": "" if observed_max_code is None else observed_max_code,
        "response_code": "" if response_code is None else response_code,
        "observed_samples": observed_samples,
        "missing_start_bits": ",".join(str(bit) for bit in start_missing),
        "missing_end_bits": ",".join(str(bit) for bit in end_missing),
        "netlist": str(netlist_path),
        "log": str(log_path),
        "waveform": str(xyce_waveform_path(netlist_path)) if args.simulator == "xyce" else "",
    }


def parse_cases(text):
    cases = [item.strip() for item in text.split(",") if item.strip()]
    for case_name in cases:
        if case_name not in CASES:
            raise ValueError(f"unknown DLF update case: {case_name}")
    return cases


def parse_timeout(value):
    if value in (None, "none", "None", "0", "0.0"):
        return None
    timeout = float(value)
    if timeout <= 0:
        raise ValueError("--timeout-s must be positive, 0, or 'none'")
    return timeout


def main():
    root_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description="Run synthesized Sky130 DLF update SPICE smoke checks.")
    parser.add_argument("--cases", default="inc_mid,dec_mid")
    parser.add_argument(
        "--mapped-verilog",
        default=str(root_dir / "build" / "synth" / "IntegerPLL_DigitalCore_sky130.v"),
    )
    parser.add_argument("--pdk-root", default=os.environ.get("PDK_ROOT", "~/.volare"))
    parser.add_argument("--pdk", default=os.environ.get("PDK", "sky130A"))
    parser.add_argument(
        "--std-cell-library",
        default=os.environ.get("STD_CELL_LIBRARY", "sky130_fd_sc_hd"),
    )
    parser.add_argument("--corner", default="tt")
    parser.add_argument("--ki", type=int, default=255)
    parser.add_argument("--kp", type=int, default=4)
    parser.add_argument("--mmd-ratio", type=int, default=2)
    parser.add_argument(
        "--spef",
        default="",
        help=(
            "Optional OpenROAD SPEF. When supplied, total post-route "
            "capacitance for modeled nets is added as lumped capacitors."
        ),
    )
    parser.add_argument(
        "--spef-mode",
        choices=("lumped_cap", "distributed_rc"),
        default="lumped_cap",
        help=(
            "SPEF insertion mode. distributed_rc substitutes cell pin nodes "
            "and inserts modeled SPEF resistors plus grounded capacitances."
        ),
    )
    parser.add_argument(
        "--scope",
        choices=("cone", "full"),
        default="cone",
        help="Use the extracted DCO-code update cone or the full mapped digital-core netlist.",
    )
    parser.add_argument("--threshold", type=float, default=0.9)
    parser.add_argument("--reset-release-ns", type=float, default=5.0)
    parser.add_argument("--clock-start-ns", type=float, default=8.0)
    parser.add_argument("--clock-half-ns", type=float, default=1.0)
    parser.add_argument("--pllo-start-ns", type=float, default=7.5)
    parser.add_argument("--pllo-half-ns", type=float, default=0.5)
    parser.add_argument("--clear-start-ns", type=float, default=20.0)
    parser.add_argument("--clear-width-ns", type=float, default=30.0)
    parser.add_argument("--enable-ns", type=float, default=70.0)
    parser.add_argument("--sim-time-ns", type=float, default=220.0)
    parser.add_argument("--step-ps", type=float, default=100.0)
    parser.add_argument("--timeout-s", default="180")
    parser.add_argument("--ngspice", default=shutil.which("ngspice") or "ngspice")
    parser.add_argument(
        "--simulator",
        choices=("ngspice", "xyce"),
        default="ngspice",
        help="Circuit simulator for the generated DLF update deck.",
    )
    add_xyce_arguments(parser)
    parser.add_argument(
        "--bbpd-rcx-netlist",
        default=str(
            root_dir
            / "openlane"
            / "IntegerPLL_BBPD"
            / "runs"
            / "librelane_signoff"
            / "rcx-magic"
            / "IntegerPLL_BBPD.rcx.spice"
        ),
        help="Filled BBPD RCX deck used by inc_bbpd_rcx/dec_bbpd_rcx cases.",
    )
    parser.add_argument("--bbpd-subckt", default="IntegerPLL_BBPD")
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help=(
            "Run independent DLF update cases in parallel; "
            "one simulator process per case."
        ),
    )
    parser.add_argument("--print-internal-debug", action="store_true")
    parser.add_argument(
        "--ngspice-threads",
        type=int,
        default=int(os.environ.get("NGSPICE_THREADS", "0")),
        help=(
            "Set ngspice OpenMP threads via .option num_threads and "
            "OMP_NUM_THREADS; 0 leaves default."
        ),
    )
    parser.add_argument(
        "--build-dir",
        default=str(root_dir / "build" / "spice_dlf_update"),
    )
    args = parser.parse_args()
    args.timeout_s = parse_timeout(args.timeout_s)
    if args.ki < 0 or args.ki > 255 or args.kp < 0 or args.kp > 255:
        raise ValueError("--ki and --kp must be 8-bit values")
    if args.mmd_ratio < 2 or args.mmd_ratio > 255:
        raise ValueError("--mmd-ratio must be in 2..255")
    if args.ngspice_threads < 0:
        raise ValueError("--ngspice-threads must be non-negative")
    validate_xyce_arguments(args)
    if args.jobs < 1:
        raise ValueError("--jobs must be positive")
    args.spef_path = Path(args.spef).expanduser().resolve() if args.spef else None
    if args.spef_path is not None and not args.spef_path.exists():
        raise FileNotFoundError(f"missing SPEF file: {args.spef_path}")

    mapped_verilog = Path(args.mapped_verilog).expanduser().resolve()
    if not mapped_verilog.exists():
        raise FileNotFoundError(
            f"missing mapped Verilog netlist: {mapped_verilog}. Run make synth first."
        )

    pdk_dir = Path(args.pdk_root).expanduser().resolve() / args.pdk
    cell_spice_path = (
        pdk_dir
        / "libs.ref"
        / args.std_cell_library
        / "spice"
        / f"{args.std_cell_library}.spice"
    )
    subckt_ports = parse_subckt_ports(cell_spice_path)
    all_instances = parse_instances(mapped_verilog.read_text(encoding="utf-8"))
    if not all_instances:
        raise ValueError(f"no Sky130 cell instances found in {mapped_verilog}")
    for index, instance in enumerate(all_instances):
        instance["index"] = index

    if args.scope == "cone":
        input_nets = (
            {
                "PLLOUT",
                "RESET_N",
                "DLF_En",
                "DLF_Clear",
                "DLF_Ext_Override",
                "DLF_IN_POL",
                "CLKDIV_RETIMED",
            }
            | {bit_net("BBPD", index) for index in range(2)}
            | {bit_net("DLF_Ext_Data", index) for index in range(10)}
            | {bit_net("DLF_KI", index) for index in range(8)}
            | {bit_net("DLF_KP", index) for index in range(8)}
            | {bit_net("MMDCLKDIV_RATIO", index) for index in range(8)}
            | {bit_net("COARSEBINARY_CODE", index) for index in range(4)}
        )
        output_nets = {bit_net("DCO_CODE", index) for index in range(8)}
        instances = extract_cone(all_instances, output_nets, input_nets)
        print(
            f"extracted {len(instances)} DLF/DCO-code cone cells from "
            f"{len(all_instances)} mapped digital-core cells",
            flush=True,
        )
    else:
        instances = all_instances
        print(
            f"using all {len(instances)} mapped digital-core cells",
            flush=True,
        )
    args.spef_caps = {}
    args.spef_rc = {}
    args.spef_pin_nodes = {}
    args.spef_cap_count = 0
    args.spef_resistor_count = 0
    args.spef_cap_total_f = 0.0
    args.active_spef_mode = ""
    if args.spef_path is not None and args.spef_mode == "lumped_cap":
        args.spef_caps = parse_spef_lumped_caps(
            args.spef_path,
            instance_net_names(instances),
        )
        args.spef_cap_count = len(args.spef_caps)
        args.spef_cap_total_f = sum(args.spef_caps.values())
        args.active_spef_mode = "lumped_cap" if args.spef_caps else ""
        print(
            f"added lumped SPEF capacitance on {len(args.spef_caps)} modeled nets "
            f"({sum(args.spef_caps.values()) * 1e15:.3f} fF total)",
            flush=True,
        )
    elif args.spef_path is not None:
        args.spef_rc = parse_spef_distributed_rc(
            args.spef_path,
            instance_net_names(instances),
        )
        args.spef_pin_nodes = args.spef_rc["pin_nodes"]
        args.spef_cap_count = len(args.spef_rc["cap_lines"])
        args.spef_resistor_count = len(args.spef_rc["resistor_lines"])
        args.spef_cap_total_f = args.spef_rc["cap_total_f"]
        args.active_spef_mode = "distributed_rc" if args.spef_rc else ""
        print(
            f"added distributed SPEF RC with {len(args.spef_pin_nodes)} pin nodes, "
            f"{args.spef_cap_count} grounded caps, {args.spef_resistor_count} resistors "
            f"({args.spef_cap_total_f * 1e15:.3f} fF total)",
            flush=True,
        )

    build_dir = Path(args.build_dir).expanduser().resolve()
    build_dir.mkdir(parents=True, exist_ok=True)
    case_names = parse_cases(args.cases)
    if args.jobs == 1 or len(case_names) == 1:
        rows = [
            run_one(case_name, args, build_dir, instances, subckt_ports)
            for case_name in case_names
        ]
    else:
        rows_by_case = {}
        worker_count = min(args.jobs, len(case_names))
        print(
            f"running {len(case_names)} DLF SPICE cases with {worker_count} workers",
            flush=True,
        )
        with concurrent.futures.ThreadPoolExecutor(
            max_workers=worker_count
        ) as executor:
            futures = {
                executor.submit(
                    run_one,
                    case_name,
                    args,
                    build_dir,
                    instances,
                    subckt_ports,
                ): case_name
                for case_name in case_names
            }
            for future in concurrent.futures.as_completed(futures):
                case_name = futures[future]
                rows_by_case[case_name] = future.result()
        rows = [rows_by_case[case_name] for case_name in case_names]

    csv_path = build_dir / "dlf_update_check.csv"
    with csv_path.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    for row in rows:
        print(
            f"case={row['case']} status={row['status']} "
            f"code={row['start_code']}->{row['end_code']} "
            f"response={row['response_code']} "
            f"timeout={row['timed_out']} elapsed_s={row['elapsed_s']}"
        )
    print(f"wrote {csv_path}")

    failed = [row for row in rows if row["status"] != "pass"]
    if failed:
        print(f"{len(failed)} synthesized DLF SPICE update checks failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
