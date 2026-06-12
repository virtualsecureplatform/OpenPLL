#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import concurrent.futures
import csv
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from spice_dlf_update_check import (
    bit_net,
    decode_spef_name,
    parse_instances,
    parse_named_subckt_ports,
    parse_spef_header,
    parse_spef_lumped_caps,
    parse_subckt_ports,
    sanitize_net,
    spef_instance_pin,
    spef_spice_node,
    source_bit_lines,
    spice_instance_lines,
)
from check_hard_macro_top_spice import instance_port_map, parse_spice
from xyce_utils import add_xyce_arguments, validate_xyce_arguments, xyce_simulator_command


CASES = {
    "low_start": {
        "start_dlf": 0,
        "expected": "increase",
        "expected_start_code": 0,
    },
    "high_start": {
        "start_dlf": 1020,
        "expected": "decrease",
        "expected_start_code": 255,
    },
    "mid_start_inc": {
        "start_dlf": 512,
        "expected": "increase",
        "expected_start_code": 128,
    },
    "mid_start_dec": {
        "start_dlf": 512,
        "expected": "decrease",
        "expected_start_code": 128,
    },
    "near_high_dec": {
        "start_dlf": 640,
        "expected": "decrease",
        "expected_start_code": 160,
    },
}

FILLED_DCO_DEFAULTS = {
    "f0_mhz": 46.25672588520797,
    "f64_mhz": 47.95039109460694,
    "f128_mhz": 49.762117807733404,
    "f192_mhz": 51.61843654151962,
    "f255_mhz": 52.34983089216307,
}

PHYSICAL_ONLY_CELL_PREFIXES = (
    "decap",
    "diode",
    "fill",
    "tap",
    "tapvgnd",
    "tapvgnd2",
    "tapvpwrvgnd",
)
VECTOR_ALIAS_WIDTHS = {
    "DCO_CODE": 8,
    "DCO_THERM": 255,
}
ASSIGN_RE = re.compile(r"^\s*assign\s+(.+?)\s*=\s*(.+?)\s*;\s*$")


def physical_only_cell(cell_type):
    if "__" not in cell_type:
        return False
    return cell_type.split("__", 1)[1].startswith(PHYSICAL_ONLY_CELL_PREFIXES)


def parse_vector_aliases(verilog_text):
    aliases = {}
    for line in verilog_text.splitlines():
        match = ASSIGN_RE.match(line)
        if match is None:
            continue
        lhs = match.group(1).strip()
        rhs = match.group(2).strip()
        if any(ch in rhs for ch in "{}:,"):
            continue
        lhs_name = lhs.lstrip("\\").strip()
        rhs_name = rhs.lstrip("\\").strip()
        width = VECTOR_ALIAS_WIDTHS.get(lhs_name)
        if width is None:
            continue
        for index in range(width):
            aliases[bit_net(lhs_name, index)] = bit_net(rhs_name, index)

    resolved = {}
    for net, target in aliases.items():
        seen = {net}
        while target in aliases and target not in seen:
            seen.add(target)
            target = aliases[target]
        resolved[net] = target
    return resolved


def aliased_net(args, net):
    return getattr(args, "net_aliases", {}).get(net, net)


def case_initial_dco_phase_cycles(case_name, args):
    override = getattr(args, f"{case_name}_initial_dco_phase_cycles", None)
    if override is not None:
        return override
    return args.initial_dco_phase_cycles


def xyce_output_base(netlist_path):
    return netlist_path.with_suffix("")


def xyce_waveform_path(netlist_path):
    return Path(f"{xyce_output_base(netlist_path)}.prn")


def reusable_log(log_path):
    if not log_path.exists():
        return False
    text = log_path.read_text(encoding="utf-8", errors="replace")
    return "OpenPLL timeout:" not in text


def parse_xyce_waveform(waveform_path):
    if not waveform_path.exists():
        return []

    header = None
    rows = []
    for line in waveform_path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        if parts[0].lower() == "index":
            header = [part.lower() for part in parts]
            continue
        if header is None or len(parts) < len(header):
            continue
        try:
            values = [float(part) for part in parts[: len(header)]]
        except ValueError:
            continue
        rows.append(dict(zip(header, values)))
    return rows


def xyce_sample(rows, key, time_s):
    if not rows:
        return None
    key = key.lower()
    if key not in rows[0]:
        return None

    prev = rows[0]
    if time_s <= prev["time"]:
        return prev[key]
    for row in rows[1:]:
        if time_s <= row["time"]:
            dt = row["time"] - prev["time"]
            if dt <= 0:
                return row[key]
            frac = (time_s - prev["time"]) / dt
            return prev[key] + frac * (row[key] - prev[key])
        prev = row
    return rows[-1][key]


def xyce_window_extrema(rows, key, start_s, end_s):
    if not rows:
        return None, None
    key = key.lower()
    if key not in rows[0]:
        return None, None

    values = []
    start_value = xyce_sample(rows, key, start_s)
    end_value = xyce_sample(rows, key, end_s)
    if start_value is not None:
        values.append(start_value)
    if end_value is not None:
        values.append(end_value)
    for row in rows:
        if start_s <= row["time"] <= end_s:
            values.append(row[key])
    if not values:
        return None, None
    return min(values), max(values)


def xyce_sample_binary_bus(rows, bit_keys, time_s, threshold):
    if not rows:
        return None
    value = 0
    for bit_index, key in enumerate(bit_keys):
        sample = xyce_sample(rows, key, time_s)
        if sample is None:
            return None
        if sample >= threshold:
            value |= 1 << bit_index
    return value


def xyce_window_binary_bus_extrema(rows, bit_keys, start_s, end_s, threshold):
    if not rows:
        return None, None

    values = []
    for time_s in (start_s, end_s):
        value = xyce_sample_binary_bus(rows, bit_keys, time_s, threshold)
        if value is not None:
            values.append(value)

    for row in rows:
        if not (start_s <= row["time"] <= end_s):
            continue
        value = 0
        for bit_index, key in enumerate(bit_keys):
            if key not in row:
                return None, None
            if row[key] >= threshold:
                value |= 1 << bit_index
        values.append(value)

    if not values:
        return None, None
    return min(values), max(values)


def integrator_code_keys(args):
    return [
        f"v(loop_filter_integ_acc__{index})"
        for index in range(args.dlf_frac_width, args.dlf_frac_width + args.dlf_code_width)
    ]


def integrator_debug_nodes(args):
    return [
        f"loop_filter_integ_acc__{index}"
        for index in range(
            args.dlf_frac_width + args.dlf_code_width,
            args.dlf_frac_width - 1,
            -1,
        )
    ]


def dco_units_from_integrator_code(value):
    if value is None:
        return None
    return value / 4.0


def xyce_rising_crossings(rows, key, threshold, start_s, end_s):
    key = key.lower()
    crossings = []
    prev = None
    for row in rows:
        if key not in row:
            continue
        value = row[key]
        time_s = row["time"]
        if prev is not None:
            prev_time_s, prev_value = prev
            if prev_value < threshold <= value and value != prev_value:
                frac = (threshold - prev_value) / (value - prev_value)
                crossing_s = prev_time_s + frac * (time_s - prev_time_s)
                if start_s <= crossing_s <= end_s:
                    crossings.append(crossing_s)
        prev = (time_s, value)
    return crossings


def crossing_frequency_mhz(crossings):
    if len(crossings) < 2:
        return None, None
    period_s = (crossings[-1] - crossings[0]) / (len(crossings) - 1)
    if period_s <= 0.0:
        return period_s, None
    return period_s, 1.0 / period_s / 1.0e6


def dco_binary_code_terms(args):
    return [
        (
            f"{1 << index}*0.5*"
            f"(1+tanh({args.code_sharpness:g}*"
            f"(v({aliased_net(args, bit_net('DCO_CODE', index))})-{args.threshold:g})))"
        )
        for index in range(8)
    ]


def dco_therm_observer_node(args, index):
    return getattr(args, "hardtop_dco_therm_receiver_nodes", {}).get(
        index,
        aliased_net(args, bit_net("DCO_THERM", index)),
    )


def dco_therm_code_terms(args):
    if not args.dco_therm_invert:
        return [
            (
                "0.5*"
                f"(1+tanh({args.code_sharpness:g}*"
                f"(v({dco_therm_observer_node(args, index)})-{args.threshold:g})))"
            )
            for index in range(255)
        ]
    return [
        (
            "0.5*"
            f"(1-tanh({args.code_sharpness:g}*"
            f"(v({dco_therm_observer_node(args, index)})-{args.threshold:g})))"
        )
        for index in range(255)
    ]


def code_observer_source(args):
    if args.code_observer_source != "auto":
        return args.code_observer_source
    if args.hardtop_spef_mode == "distributed_rc":
        return "dco_therm"
    return "dco_therm" if args.dco_impl == "postlayout" else "dco_code"


def dco_code_observer_lines(args):
    source = code_observer_source(args)
    terms = dco_therm_code_terms(args) if source == "dco_therm" else dco_binary_code_terms(args)
    chunk_size = 24
    chunk_nodes = []
    lines = [f"* CODE observer source: {source}."]
    for chunk_index in range(0, len(terms), chunk_size):
        node = f"CODE_SUM_{len(chunk_nodes)}"
        chunk_nodes.append(node)
        lines.append(
            f"B{node} {node} 0 V={{{'+'.join(terms[chunk_index:chunk_index + chunk_size])}}}"
        )
    expr = "+".join(f"v({node})" for node in chunk_nodes)
    lines.extend([
        f"BCODE_RAW CODE_RAW 0 V={{{expr}}}",
        "BCODE CODE 0 V={min(255,max(0,v(CODE_RAW)))}",
    ])
    return [
        *lines,
    ]


def dco_model_lines(args):
    return [
        *dco_code_observer_lines(args),
        "* Smooth blends across measured filled-RCX DCO calibration points.",
        "BDCO_BLEND64 DCO_BLEND64 0 V={0.5*(1+tanh(10*(v(CODE)-64)))}",
        "BDCO_BLEND128 DCO_BLEND128 0 V={0.5*(1+tanh(10*(v(CODE)-128)))}",
        "BDCO_BLEND192 DCO_BLEND192 0 V={0.5*(1+tanh(10*(v(CODE)-192)))}",
        "BDCO_FREQ_HZ DCO_FREQ_HZ 0 V={"
        "(1-v(DCO_BLEND64))*(DCO_F0 + (DCO_F64-DCO_F0)*v(CODE)/64)"
        " + v(DCO_BLEND64)*(1-v(DCO_BLEND128))"
        "*(DCO_F64 + (DCO_F128-DCO_F64)*(v(CODE)-64)/64)"
        " + v(DCO_BLEND128)*(1-v(DCO_BLEND192))"
        "*(DCO_F128 + (DCO_F192-DCO_F128)*(v(CODE)-128)/64)"
        " + v(DCO_BLEND192)*(DCO_F192 + (DCO_F255-DCO_F192)*(v(CODE)-192)/63)"
        "}",
        "BFREQ FREQ_MHZ 0 V={v(DCO_FREQ_HZ)/1e6}",
        "BTARGET TARGET_MHZ 0 V={FREF*NDIV/1e6}",
        "BFERR FERR_MHZ 0 V={v(FREQ_MHZ)-v(TARGET_MHZ)}",
    ]


def wrapped_instance(name, ports, subckt_name, width=8):
    tokens = list(ports) + [subckt_name]
    lines = [f"{name} " + " ".join(tokens[:width])]
    for index in range(width, len(tokens), width):
        lines.append("+ " + " ".join(tokens[index : index + width]))
    return lines


def wrapped_directive(keyword, tokens, width=6):
    if not tokens:
        return []
    lines = [f"{keyword} " + " ".join(tokens[:width])]
    for index in range(width, len(tokens), width):
        lines.append("+ " + " ".join(tokens[index : index + width]))
    return lines


def dco_therm_ic_lines(case, args):
    if not args.init_dco_therm:
        return []
    start_code = case["expected_start_code"]
    tokens = []
    for index in range(255):
        value = "1.8" if index >= start_code else "0"
        tokens.append(f"v({aliased_net(args, bit_net('DCO_THERM', index))})={value}")
    return [
        "* Seed extracted-DCO thermometer input capacitances for UIC startup.",
        *wrapped_directive(".ic", tokens),
    ]


def macro_pin_node(args, instance_name, port, fallback):
    return getattr(args, "hardtop_macro_pin_nodes", {}).get(
        (instance_name, port),
        fallback,
    )


def pllout_source_node(args):
    return macro_pin_node(args, "oscillator", "PLLOUT", "PLLOUT")


def ref_source_node(args):
    return "REF"


def bbpd_output_node(args, index):
    return macro_pin_node(
        args,
        "phase_detector",
        f"BBPD[{index}]",
        bit_net("BBPD", index),
    )


def empty_hardtop_spef_state(args):
    args.hardtop_spef_caps = {}
    args.hardtop_spef_rc = None
    args.hardtop_spef_path = None
    args.hardtop_spef_cap_count = 0
    args.hardtop_spef_cap_node_count = 0
    args.hardtop_spef_resistor_count = 0
    args.hardtop_spef_pin_substitutions = 0
    args.hardtop_spef_dco_therm_count = 0
    args.hardtop_spef_cap_total_f = 0.0
    args.hardtop_digital_pin_node_map = {}
    args.hardtop_macro_pin_nodes = {}
    args.hardtop_dco_therm_receiver_nodes = {}


def hardtop_loop_endpoint_spec(args):
    spice_path = Path(args.hardtop_spice).expanduser().resolve()
    if not spice_path.exists():
        raise FileNotFoundError(f"missing hard-top extracted SPICE: {spice_path}")

    subckts, instances = parse_spice(spice_path)
    digital_map = instance_port_map(
        subckts,
        instances,
        "Xdigital_core",
        "IntegerPLL_DigitalCore",
    )
    dco_map = instance_port_map(subckts, instances, "Xoscillator", args.dco_subckt)

    signals = {}
    dco_therm_groups = []

    def add_signal(name, *, digital_port=None, digital_net=None, macro_ports=()):
        signals[sanitize_net(name)] = {
            "digital_port": digital_port,
            "digital_net": digital_net,
            "macro_ports": tuple(macro_ports),
        }

    add_signal(
        "BBPD_CODE[0]",
        digital_port="BBPD[0]",
        digital_net=bit_net("BBPD", 0),
        macro_ports=(("phase_detector", "BBPD[0]"),),
    )
    add_signal(
        "BBPD_CODE[1]",
        digital_port="BBPD[1]",
        digital_net=bit_net("BBPD", 1),
        macro_ports=(("phase_detector", "BBPD[1]"),),
    )
    add_signal(
        "CLKDIV_RETIMED",
        digital_port="CLKDIV_RETIMED",
        digital_net="CLKDIV_RETIMED",
        macro_ports=(("phase_detector", "CLKDIVR"),),
    )
    add_signal(
        "PLLOUT",
        digital_port="PLLOUT",
        digital_net="PLLOUT",
        macro_ports=(("oscillator", "PLLOUT"),),
    )
    add_signal(
        "PLLOUT_DIV",
        digital_port="PLLOUT_DIV",
        digital_net="PLLOUT_DIV",
    )
    add_signal(
        "REF",
        macro_ports=(("phase_detector", "REF"),),
    )

    for index in range(255):
        port = f"DCO_THERM[{index}]"
        digital_node = digital_map.get(port)
        dco_node = dco_map.get(port)
        if digital_node is None or dco_node is None:
            raise ValueError(f"hard-top extracted SPICE missing {port}")
        if digital_node != dco_node:
            raise ValueError(
                f"hard-top extracted SPICE maps {port} to "
                f"{digital_node} and {dco_node}"
            )
        entry = {
            "digital_port": port,
            "digital_net": aliased_net(args, bit_net("DCO_THERM", index)),
            "macro_ports": (("oscillator", port),),
            "dco_therm_index": index,
        }
        spef_nets = {
            sanitize_net(f"dco_therm[{index}]"),
            sanitize_net(digital_node),
        }
        for spef_net in spef_nets:
            signals[spef_net] = entry
        dco_therm_groups.append(spef_nets)

    return signals, dco_therm_groups


def hardtop_loop_spef_node_map(args):
    signals, dco_therm_groups = hardtop_loop_endpoint_spec(args)
    net_map = {
        bit_net("BBPD_CODE", 0): bit_net("BBPD", 0),
        bit_net("BBPD_CODE", 1): bit_net("BBPD", 1),
        "CLKDIV_RETIMED": "CLKDIV_RETIMED",
        "PLLOUT": "PLLOUT",
        "PLLOUT_DIV": "PLLOUT_DIV",
        "REF": "REF",
        sanitize_net("_0_/X"): "BBPD_RESET_N",
    }
    for spef_net, signal in signals.items():
        digital_net = signal.get("digital_net")
        if digital_net is not None:
            net_map[spef_net] = digital_net
    return net_map, dco_therm_groups


def load_hardtop_spef_lumped_caps(args):
    spef_path = Path(args.hardtop_spef).expanduser().resolve()
    if not spef_path.exists():
        raise FileNotFoundError(f"missing hard-top SPEF: {spef_path}")

    net_map, dco_therm_groups = hardtop_loop_spef_node_map(args)
    top_caps = parse_spef_lumped_caps(spef_path, set(net_map))
    missing_dco_therm = [
        index
        for index, spef_nets in enumerate(dco_therm_groups)
        if not any(spef_net in top_caps for spef_net in spef_nets)
    ]
    if missing_dco_therm:
        preview = ", ".join(str(index) for index in missing_dco_therm[:8])
        raise ValueError(
            "hard-top SPEF is missing DCO thermometer nets used by the "
            f"extracted wrapper: DCO_THERM[{preview}]"
        )
    covered_dco_therm = len(dco_therm_groups) - len(missing_dco_therm)

    deck_caps = {}
    for top_net, cap_f in top_caps.items():
        deck_node = net_map[top_net]
        deck_caps[deck_node] = deck_caps.get(deck_node, 0.0) + cap_f
    return {
        "caps": deck_caps,
        "source_cap_count": len(top_caps),
        "cap_node_count": len(deck_caps),
        "dco_therm_count": covered_dco_therm,
        "total_f": sum(top_caps.values()),
        "path": spef_path,
    }


def hardtop_spef_lumped_cap_lines(args):
    caps = getattr(args, "hardtop_spef_caps", {})
    if not caps:
        return []
    lines = ["* Lumped hard-macro-top SPEF loop/inter-macro capacitances."]
    for index, (net, cap_f) in enumerate(sorted(caps.items())):
        lines.append(f"CHTSPEF_{index:05d} {net} VGND {cap_f:.9e}")
    return lines


def parse_hardtop_spef_distributed_rc(spef_path, signals):
    lines = Path(spef_path).read_text(encoding="ascii", errors="replace").splitlines()
    name_map, cap_unit_f, res_unit_ohm = parse_spef_header(lines)
    candidate_nets = set(signals)
    pin_nodes = {}
    cap_values = {}
    resistor_lines = []
    parsed_nets = set()
    current = None
    current_mode = None
    resistor_index = 0

    def add_cap(node, cap_f):
        if cap_f <= 0.0:
            return
        cap_values[node] = cap_values.get(node, 0.0) + cap_f

    def finalize_current():
        nonlocal resistor_index
        if current is None:
            return
        current_nodes = set(current["pin_nodes"])
        for node_a, node_b, _ in current["resistors"]:
            current_nodes.add(node_a)
            current_nodes.add(node_b)

        for nodes, cap_f in current["caps"]:
            node = nodes[0]
            if len(nodes) > 1:
                node = next((item for item in nodes if item in current_nodes), node)
            add_cap(node, cap_f)

        for node_a, node_b, resistance in current["resistors"]:
            if resistance <= 0.0:
                continue
            resistor_lines.append(
                "RHTSPEF_"
                f"{resistor_index:05d} "
                f"{node_a} "
                f"{node_b} "
                f"{resistance:.9g}"
            )
            resistor_index += 1

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("*D_NET"):
            finalize_current()
            parts = stripped.split()
            current = None
            current_mode = None
            if len(parts) >= 3:
                net = sanitize_net(decode_spef_name(parts[1], name_map))
                if net in candidate_nets:
                    current = {
                        "net": net,
                        "pin_nodes": set(),
                        "caps": [],
                        "resistors": [],
                    }
                    parsed_nets.add(net)
            continue
        if current is None:
            continue
        if stripped == "*END":
            finalize_current()
            current = None
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
                pin_node = spef_spice_node(parts[1], name_map)
                pin_nodes[instance_pin] = pin_node
                current["pin_nodes"].add(pin_node)
        elif current_mode == "cap" and len(parts) >= 3:
            nodes = tuple(spef_spice_node(part, name_map) for part in parts[1:-1])
            current["caps"].append((nodes, float(parts[-1]) * cap_unit_f))
        elif current_mode == "res" and len(parts) >= 4:
            resistance = float(parts[3]) * res_unit_ohm
            current["resistors"].append(
                (
                    spef_spice_node(parts[1], name_map),
                    spef_spice_node(parts[2], name_map),
                    resistance,
                )
            )
    finalize_current()

    cap_lines = [
        f"CHTSPEF_RC_{index:05d} {node} VGND {cap_f:.9e}"
        for index, (node, cap_f) in enumerate(sorted(cap_values.items()))
    ]
    return {
        "parsed_nets": parsed_nets,
        "pin_nodes": pin_nodes,
        "cap_lines": cap_lines,
        "resistor_lines": resistor_lines,
        "cap_total_f": sum(cap_values.values()),
    }


def load_hardtop_spef_distributed_rc(args, instances):
    spef_path = Path(args.hardtop_spef).expanduser().resolve()
    if not spef_path.exists():
        raise FileNotFoundError(f"missing hard-top SPEF: {spef_path}")

    signals, dco_therm_groups = hardtop_loop_endpoint_spec(args)
    spef_rc = parse_hardtop_spef_distributed_rc(spef_path, signals)
    missing_dco_therm = [
        index
        for index, spef_nets in enumerate(dco_therm_groups)
        if not any(spef_net in spef_rc["parsed_nets"] for spef_net in spef_nets)
    ]
    if missing_dco_therm:
        preview = ", ".join(str(index) for index in missing_dco_therm[:8])
        raise ValueError(
            "hard-top distributed SPEF is missing DCO thermometer nets used by "
            f"the extracted wrapper: DCO_THERM[{preview}]"
        )

    digital_net_to_pin_node = {}
    dco_therm_receiver_nodes = {}
    for spef_net in spef_rc["parsed_nets"]:
        signal = signals[spef_net]
        digital_port = signal.get("digital_port")
        digital_net = signal.get("digital_net")
        if digital_port is not None and digital_net is not None:
            pin_node = spef_rc["pin_nodes"].get(("digital_core", digital_port))
            if pin_node is None:
                raise ValueError(f"hard-top SPEF missing digital_core:{digital_port}")
            digital_net_to_pin_node[digital_net] = pin_node
        for instance_name, port in signal.get("macro_ports", ()):
            pin_node = spef_rc["pin_nodes"].get((instance_name, port))
            if pin_node is None:
                raise ValueError(f"hard-top SPEF missing {instance_name}:{port}")
        if "dco_therm_index" in signal:
            dco_therm_receiver_nodes[signal["dco_therm_index"]] = spef_rc["pin_nodes"][
                ("oscillator", f"DCO_THERM[{signal['dco_therm_index']}]")
            ]

    digital_pin_node_map = {}
    for instance in instances:
        for port, net in instance["conns"].items():
            pin_node = digital_net_to_pin_node.get(net)
            if pin_node is not None:
                digital_pin_node_map[(instance["name"], port)] = pin_node

    return {
        "path": spef_path,
        "source_net_count": len(spef_rc["parsed_nets"]),
        "dco_therm_count": len(dco_therm_groups) - len(missing_dco_therm),
        "cap_lines": spef_rc["cap_lines"],
        "resistor_lines": spef_rc["resistor_lines"],
        "cap_total_f": spef_rc["cap_total_f"],
        "pin_nodes": spef_rc["pin_nodes"],
        "digital_pin_node_map": digital_pin_node_map,
        "dco_therm_receiver_nodes": dco_therm_receiver_nodes,
    }


def load_hardtop_spef_state(args, instances):
    empty_hardtop_spef_state(args)
    if args.hardtop_spef and args.hardtop_spef_mode == "none":
        args.hardtop_spef_mode = "lumped_cap"
    if args.hardtop_spef_mode == "none":
        return
    if not args.hardtop_spef:
        raise ValueError(
            f"--hardtop-spef is required for --hardtop-spef-mode {args.hardtop_spef_mode}"
        )

    if args.hardtop_spef_mode == "lumped_cap":
        hardtop_spef = load_hardtop_spef_lumped_caps(args)
        args.hardtop_spef_caps = hardtop_spef["caps"]
        args.hardtop_spef_path = hardtop_spef["path"]
        args.hardtop_spef_cap_count = hardtop_spef["source_cap_count"]
        args.hardtop_spef_cap_node_count = hardtop_spef["cap_node_count"]
        args.hardtop_spef_dco_therm_count = hardtop_spef["dco_therm_count"]
        args.hardtop_spef_cap_total_f = hardtop_spef["total_f"]
        print(
            "added lumped hard-top SPEF capacitance on "
            f"{args.hardtop_spef_cap_count} source nets "
            f"({args.hardtop_spef_cap_node_count} loop-deck nodes, "
            f"{args.hardtop_spef_cap_total_f * 1e15:.3f} fF total)",
            flush=True,
        )
        return

    if args.hardtop_spef_mode == "distributed_rc":
        hardtop_spef = load_hardtop_spef_distributed_rc(args, instances)
        args.hardtop_spef_rc = hardtop_spef
        args.hardtop_spef_path = hardtop_spef["path"]
        args.hardtop_spef_cap_count = hardtop_spef["source_net_count"]
        args.hardtop_spef_cap_node_count = len(hardtop_spef["cap_lines"])
        args.hardtop_spef_resistor_count = len(hardtop_spef["resistor_lines"])
        args.hardtop_spef_dco_therm_count = hardtop_spef["dco_therm_count"]
        args.hardtop_spef_cap_total_f = hardtop_spef["cap_total_f"]
        args.hardtop_digital_pin_node_map = hardtop_spef["digital_pin_node_map"]
        args.hardtop_macro_pin_nodes = hardtop_spef["pin_nodes"]
        args.hardtop_dco_therm_receiver_nodes = hardtop_spef[
            "dco_therm_receiver_nodes"
        ]
        args.hardtop_spef_pin_substitutions = len(
            hardtop_spef["digital_pin_node_map"]
        )
        print(
            "added distributed hard-top SPEF RC on "
            f"{args.hardtop_spef_cap_count} source nets "
            f"({args.hardtop_spef_cap_node_count} cap nodes, "
            f"{args.hardtop_spef_resistor_count} resistors, "
            f"{args.hardtop_spef_pin_substitutions} digital pin substitutions, "
            f"{args.hardtop_spef_cap_total_f * 1e15:.3f} fF total)",
            flush=True,
        )
        return

    raise ValueError(f"unsupported hard-top SPEF mode: {args.hardtop_spef_mode}")


def hardtop_spef_distributed_rc_lines(args):
    if not getattr(args, "hardtop_spef_rc", None):
        return []
    return [
        "* Distributed hard-macro-top SPEF loop/inter-macro RC.",
        *args.hardtop_spef_rc["cap_lines"],
        *args.hardtop_spef_rc["resistor_lines"],
    ]


def dco_rcx_lines(args):
    rcx_path = Path(args.dco_rcx_netlist).expanduser().resolve()
    if not rcx_path.exists():
        raise FileNotFoundError(rcx_path)

    ports = parse_named_subckt_ports(rcx_path, args.dco_subckt)
    port_nets = {
        "PLLOUT": macro_pin_node(args, "oscillator", "PLLOUT", "PLLOUT"),
        "RESET_N": "RESET_N",
        "VGND": "VGND",
        "VNB": "VNB",
        "VPB": "VPB",
        "VPWR": "VPWR",
    }
    for index in range(255):
        port = f"DCO_THERM[{index}]"
        port_nets[port] = macro_pin_node(
            args,
            "oscillator",
            port,
            aliased_net(args, bit_net("DCO_THERM", index)),
        )

    missing = [port for port in ports if port not in port_nets]
    if missing:
        raise ValueError(
            f"{args.dco_subckt} has unsupported ports: {', '.join(missing)}"
        )
    return [
        "* Filled post-layout Magic RCX DCO macro in the feedback loop.",
        *wrapped_instance("XDCO", [port_nets[port] for port in ports], args.dco_subckt),
    ]


def bbpd_rcx_lines(args):
    rcx_path = Path(args.bbpd_rcx_netlist).expanduser().resolve()
    if not rcx_path.exists():
        raise FileNotFoundError(rcx_path)

    ports = parse_named_subckt_ports(rcx_path, args.bbpd_subckt)
    port_nets = {
        "BBPD[0]": macro_pin_node(
            args,
            "phase_detector",
            "BBPD[0]",
            bit_net("BBPD", 0),
        ),
        "BBPD[1]": macro_pin_node(
            args,
            "phase_detector",
            "BBPD[1]",
            bit_net("BBPD", 1),
        ),
        "CLKDIVR": macro_pin_node(
            args,
            "phase_detector",
            "CLKDIVR",
            "CLKDIV_RETIMED",
        ),
        "REF": macro_pin_node(args, "phase_detector", "REF", "REF"),
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
        "* Filled post-layout Magic RCX BBPD macro in the feedback loop.",
        f"XBBPD {nodes} {args.bbpd_subckt}",
        f".ic v({bbpd_output_node(args, 1)})=0 v({bbpd_output_node(args, 0)})=0 "
        "v(XBBPD.up_ff.q)=0 v(XBBPD.dn_ff.q)=0 "
        "v(XBBPD.up_delay_0.x)=0 v(XBBPD.up_delay_1.x)=0 "
        "v(XBBPD.dn_delay_0.x)=0 v(XBBPD.dn_delay_1.x)=0 "
        "v(XBBPD.dn_ff.reset_b)=0",
    ]


def hold_high_width_ns(args):
    return args.sim_time_ns + 1000.0


def no_repeat_period_ns(args, delay_ns, width_ns):
    return args.sim_time_ns + delay_ns + width_ns + 1000.0


def supply_source_lines(args):
    if args.supply_ramp_ns <= 0.0:
        return [
            "VVPWR VPWR 0 {VDD}",
            "VVPB VPB 0 {VDD}",
            "VVGND VGND 0 0",
            "VVNB VNB 0 0",
        ]
    high_width_ns = hold_high_width_ns(args)
    repeat_period_ns = no_repeat_period_ns(
        args, args.supply_ramp_delay_ns, high_width_ns
    )
    return [
        "VVPWR VPWR 0 "
        f"PULSE(0 {{VDD}} {args.supply_ramp_delay_ns:g}n "
        f"{args.supply_ramp_ns:g}n {args.supply_ramp_ns:g}n "
        f"{high_width_ns:g}n {repeat_period_ns:g}n)",
        "VVPB VPB 0 "
        f"PULSE(0 {{VDD}} {args.supply_ramp_delay_ns:g}n "
        f"{args.supply_ramp_ns:g}n {args.supply_ramp_ns:g}n "
        f"{high_width_ns:g}n {repeat_period_ns:g}n)",
        "VVGND VGND 0 0",
        "VVNB VNB 0 0",
    ]


def mapped_loop_netlist(case_name, args, instances, subckt_ports):
    case = CASES[case_name]
    initial_dco_phase_cycles = case_initial_dco_phase_cycles(case_name, args)
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
    bbpd_rcx_path = Path(args.bbpd_rcx_netlist).expanduser().resolve()
    dco_rcx_path = Path(args.dco_rcx_netlist).expanduser().resolve()
    if not model_path.exists():
        raise FileNotFoundError(model_path)
    if not cell_path.exists():
        raise FileNotFoundError(cell_path)
    if not bbpd_rcx_path.exists():
        raise FileNotFoundError(bbpd_rcx_path)
    if args.dco_impl == "postlayout" and not dco_rcx_path.exists():
        raise FileNotFoundError(dco_rcx_path)

    if args.ref_mhz is None:
        ref_mhz = args.f128_mhz / args.ndiv
    else:
        ref_mhz = args.ref_mhz
    sim_time_ns = args.sim_time_ns
    hold_width_ns = hold_high_width_ns(args)
    hold_period_ns = no_repeat_period_ns(args, 0.0, hold_width_ns)
    clear_period_ns = no_repeat_period_ns(
        args, args.clear_start_ns, args.clear_width_ns
    )
    tran_suffix = " uic" if args.tran_uic else ""
    tran_line = (
        f".tran {args.step_ps:g}p {sim_time_ns:g}n 0 "
        f"{args.max_step_ps:g}p{tran_suffix}"
    )
    print_nodes = [
        "REF",
        "PLLOUT",
        "VPWR",
        "CLKDIV_RETIMED",
        "RESET_N",
        "DLF_Clear",
        "DLF_En",
        "BBPD_RESET_N",
        bbpd_output_node(args, 1),
        bbpd_output_node(args, 0),
        "CODE",
        "CODE_RAW",
    ]
    if code_observer_source(args) == "dco_code":
        print_nodes.extend(
            aliased_net(args, bit_net("DCO_CODE", index)) for index in range(8)
        )
    if args.dco_impl == "behavioral":
        print_nodes.extend(["FREQ_MHZ", "FERR_MHZ"])
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
                dco_therm_observer_node(args, 0),
                dco_therm_observer_node(args, 127),
                dco_therm_observer_node(args, 128),
                dco_therm_observer_node(args, 254),
                *integrator_debug_nodes(args),
            ]
        )

    lines = [
        f"* OpenPLL mapped-core closed-loop smoke, case={case_name}",
        f"* simulator={args.simulator}",
        f'.lib "{model_path}" {args.corner}',
        f'.include "{cell_path}"',
        f'.include "{bbpd_rcx_path}"',
        *([f'.include "{dco_rcx_path}"'] if args.dco_impl == "postlayout" else []),
        ".param VDD=1.8",
        f".param FREF={ref_mhz:.12g}e6",
        f".param NDIV={args.ndiv}",
        f".param DCO_F0={args.f0_mhz:.12g}e6",
        f".param DCO_F64={args.f64_mhz:.12g}e6",
        f".param DCO_F128={args.f128_mhz:.12g}e6",
        f".param DCO_F192={args.f192_mhz:.12g}e6",
        f".param DCO_F255={args.f255_mhz:.12g}e6",
        f".param CLK_SHARPNESS={args.clock_sharpness:.12g}",
        *supply_source_lines(args),
        "VRESET RESET_N 0 "
        f"PULSE(0 {{VDD}} {args.reset_release_ns:g}n 50p 50p "
        f"{hold_width_ns:g}n {hold_period_ns:g}n)",
        "VDLFEN DLF_En 0 "
        f"PULSE(0 {{VDD}} {args.enable_ns:g}n 50p 50p "
        f"{hold_width_ns:g}n {hold_period_ns:g}n)",
        "VDLFCLEAR DLF_Clear 0 "
        f"PULSE(0 {{VDD}} {args.clear_start_ns:g}n 50p 50p "
        f"{args.clear_width_ns:g}n {clear_period_ns:g}n)",
        "BBBPDRESET BBPD_RESET_N 0 "
        "V={v(RESET_N)*v(DLF_En)*(VDD-v(DLF_Clear))/(VDD*VDD)}",
        "VDLFOVERRIDE DLF_Ext_Override 0 0",
        "VDLFINPOL DLF_IN_POL 0 {VDD}",
        "",
        "* Static control words.",
        *source_bit_lines("DLF_Ext_Data", 10, case["start_dlf"]),
        *source_bit_lines("DLF_KI", 8, args.ki),
        *source_bit_lines("DLF_KP", 8, args.kp),
        *source_bit_lines("COARSEBINARY_CODE", 4, 5),
        *source_bit_lines("MMDCLKDIV_RATIO", 8, args.ndiv),
        "",
        "* Reference source.",
        "BREF REF 0 V={0.9 + 0.9*tanh(CLK_SHARPNESS*sin(2*3.141592653589793*FREF*time))}",
        "",
        *(
            [
                "* Behavioral DCO.",
                f".ic v(DCO_PHASE)={initial_dco_phase_cycles:.12g}",
                f"BPLLOUT {pllout_source_node(args)} 0 V={{0.9 + 0.9*tanh(CLK_SHARPNESS*sin(2*3.141592653589793*v(DCO_PHASE)))}}",
                "CPHASE DCO_PHASE 0 1",
                "BPHASE DCO_PHASE 0 I={v(DCO_FREQ_HZ)}",
                *dco_model_lines(args),
                "",
            ]
            if args.dco_impl == "behavioral"
            else [
                "* DCO code observer and extracted DCO macro.",
                *dco_code_observer_lines(args),
                *dco_therm_ic_lines(case, args),
                *dco_rcx_lines(args),
                "",
            ]
        ),
        *bbpd_rcx_lines(args),
        "",
        *hardtop_spef_lumped_cap_lines(args),
        *hardtop_spef_distributed_rc_lines(args),
        *(
            [""]
            if getattr(args, "hardtop_spef_caps", {})
            or getattr(args, "hardtop_spef_rc", None)
            else []
        ),
        "* Full synthesized Sky130 digital-core mapped netlist.",
        *spice_instance_lines(
            instances,
            subckt_ports,
            getattr(args, "hardtop_digital_pin_node_map", {}),
        ),
        "",
        ".print tran " + " ".join(f"v({node})" for node in print_nodes),
        tran_line,
        ".end",
        "",
    ]
    return "\n".join(lines), ref_mhz


def simulator_command(args, netlist_path):
    if args.simulator == "xyce":
        return xyce_simulator_command(args, netlist_path, xyce_output_base(netlist_path))
    raise ValueError(f"unsupported simulator: {args.simulator}")


def run_spice(args, netlist_path, build_dir):
    start = time.monotonic()
    proc = subprocess.Popen(
        simulator_command(args, netlist_path),
        cwd=build_dir,
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
    initial_dco_phase_cycles = case_initial_dco_phase_cycles(case_name, args)
    netlist, ref_mhz = mapped_loop_netlist(case_name, args, instances, subckt_ports)
    netlist_path = build_dir / f"mapped_loop_{case_name}.spice"
    log_path = build_dir / f"mapped_loop_{case_name}.log"
    resumed = False
    if (
        args.resume
        and netlist_path.exists()
        and reusable_log(log_path)
        and xyce_waveform_path(netlist_path).exists()
        and netlist_path.read_text(encoding="ascii", errors="replace") == netlist
    ):
        returncode = 0
        timed_out = False
        elapsed_s = None
        resumed = True
    else:
        netlist_path.write_text(netlist, encoding="ascii")
        returncode, timed_out, elapsed_s, log_text = run_spice(
            args, netlist_path, build_dir
        )
        log_path.write_text(log_text, encoding="utf-8")

    rows = parse_xyce_waveform(xyce_waveform_path(netlist_path))
    start_code = xyce_sample(rows, "v(code)", args.start_meas_ns * 1e-9)
    end_code = xyce_sample(rows, "v(code)", args.end_meas_ns * 1e-9)
    observed_min_code, observed_max_code = xyce_window_extrema(
        rows,
        "v(code)",
        args.start_meas_ns * 1e-9,
        args.end_meas_ns * 1e-9,
    )
    integ_code_keys = integrator_code_keys(args)
    start_integ_code = dco_units_from_integrator_code(
        xyce_sample_binary_bus(
            rows,
            integ_code_keys,
            args.start_meas_ns * 1e-9,
            args.threshold,
        )
    )
    end_integ_code = dco_units_from_integrator_code(
        xyce_sample_binary_bus(
            rows,
            integ_code_keys,
            args.end_meas_ns * 1e-9,
            args.threshold,
        )
    )
    observed_min_integ_code_raw, observed_max_integ_code_raw = xyce_window_binary_bus_extrema(
        rows,
        integ_code_keys,
        args.start_meas_ns * 1e-9,
        args.end_meas_ns * 1e-9,
        args.threshold,
    )
    observed_min_integ_code = dco_units_from_integrator_code(observed_min_integ_code_raw)
    observed_max_integ_code = dco_units_from_integrator_code(observed_max_integ_code_raw)
    start_freq = xyce_sample(rows, "v(freq_mhz)", args.start_meas_ns * 1e-9)
    end_freq = xyce_sample(rows, "v(freq_mhz)", args.end_meas_ns * 1e-9)
    startup_crossings = xyce_rising_crossings(
        rows,
        "v(pllout)",
        args.threshold,
        args.startup_meas_start_ns * 1e-9,
        args.end_meas_ns * 1e-9,
    )
    target_freq = ref_mhz * args.ndiv
    startup_period_s, startup_freq_mhz = crossing_frequency_mhz(startup_crossings)
    tail_crossings = xyce_rising_crossings(
        rows,
        "v(pllout)",
        args.threshold,
        args.lock_meas_start_ns * 1e-9,
        args.end_meas_ns * 1e-9,
    )
    lock_observed_min_code, lock_observed_max_code = xyce_window_extrema(
        rows,
        "v(code)",
        args.lock_meas_start_ns * 1e-9,
        args.end_meas_ns * 1e-9,
    )
    tail_period_s, tail_freq_mhz = crossing_frequency_mhz(tail_crossings)
    tail_abs_error_mhz = (
        None if tail_freq_mhz is None else abs(tail_freq_mhz - target_freq)
    )
    expected = CASES[case_name]["expected"]
    expected_start_code = CASES[case_name]["expected_start_code"]
    start_ok = (
        start_code is not None
        and abs(start_code - expected_start_code) <= args.start_code_tolerance
    )
    if expected == "increase":
        response_code = observed_max_code
    else:
        response_code = observed_min_code

    if start_code is None or response_code is None:
        moved = False
    elif expected == "increase":
        moved = response_code > start_code + args.min_code_motion
    else:
        moved = response_code < start_code - args.min_code_motion
    if (
        start_code is None
        or observed_min_code is None
        or observed_max_code is None
    ):
        held_code = False
    else:
        held_code = (
            observed_min_code >= start_code - args.min_code_motion
            and observed_max_code <= start_code + args.min_code_motion
        )
    if args.lock_code_check == "none":
        code_window_ok = True
    elif args.lock_code_check == "endpoint":
        code_window_ok = (
            end_code is not None
            and end_code >= args.lock_min_code
            and end_code <= args.lock_max_code
        )
    else:
        code_window_ok = (
            lock_observed_min_code is not None
            and lock_observed_max_code is not None
            and lock_observed_min_code >= args.lock_min_code
            and lock_observed_max_code <= args.lock_max_code
        )
    tail_freq_ok = (
        tail_abs_error_mhz is not None
        and tail_abs_error_mhz <= args.lock_max_abs_ferr_mhz
        and len(tail_crossings) >= args.lock_min_rises
    )

    if args.check_mode == "motion":
        ok = returncode == 0 and not timed_out and start_ok and moved
    elif args.check_mode == "no_motion":
        ok = returncode == 0 and not timed_out and start_ok and held_code
    elif args.check_mode == "lock_window":
        ok = (
            returncode == 0
            and not timed_out
            and start_ok
            and code_window_ok
            and tail_freq_ok
            and (not args.lock_require_motion or moved)
        )
    else:
        startup_freq_ok = (
            startup_freq_mhz is not None
            and args.startup_min_freq_mhz <= startup_freq_mhz <= args.startup_max_freq_mhz
        )
        ok = (
            returncode == 0
            and not timed_out
            and len(startup_crossings) >= args.startup_min_rises
            and startup_freq_ok
        )

    return {
        "case": case_name,
        "status": "pass" if ok else "fail",
        "simulator": args.simulator,
        "xyce_command": " ".join(simulator_command(args, netlist_path)),
        "xyce_mpi_procs": args.xyce_mpi_procs,
        "bbpd_impl": "postlayout",
        "digital_scope": args.digital_scope,
        "mapped_instance_count": args.mapped_instance_count,
        "skipped_physical_only_cells": args.skipped_physical_only_cells,
        "dco_model": "piecewise5_behavioral" if args.dco_impl == "behavioral" else "postlayout_rcx",
        "code_observer_source": code_observer_source(args),
        "hardtop_spef_mode": args.hardtop_spef_mode,
        "hardtop_spef_path": str(args.hardtop_spef_path) if args.hardtop_spef_path else "",
        "hardtop_spef_cap_nets": args.hardtop_spef_cap_count,
        "hardtop_spef_cap_nodes": args.hardtop_spef_cap_node_count,
        "hardtop_spef_resistors": args.hardtop_spef_resistor_count,
        "hardtop_spef_pin_substitutions": args.hardtop_spef_pin_substitutions,
        "hardtop_spef_dco_therm_nets": args.hardtop_spef_dco_therm_count,
        "hardtop_spef_cap_total_ff": f"{args.hardtop_spef_cap_total_f * 1e15:.3f}",
        "expected": expected,
        "check_mode": args.check_mode,
        "ki": args.ki,
        "kp": args.kp,
        "dlf_code_width": args.dlf_code_width,
        "dlf_frac_width": args.dlf_frac_width,
        "ndiv": args.ndiv,
        "ref_mhz": ref_mhz,
        "target_freq_mhz": target_freq,
        "initial_dco_phase_cycles": initial_dco_phase_cycles,
        "enable_ns": args.enable_ns,
        "clear_width_ns": args.clear_width_ns,
        "returncode": returncode,
        "timed_out": "yes" if timed_out else "no",
        "elapsed_s": "" if elapsed_s is None else f"{elapsed_s:.3f}",
        "resumed": "yes" if resumed else "no",
        "start_meas_ns": args.start_meas_ns,
        "end_meas_ns": args.end_meas_ns,
        "expected_start_code": expected_start_code,
        "start_code": "" if start_code is None else start_code,
        "end_code": "" if end_code is None else end_code,
        "observed_min_code": "" if observed_min_code is None else observed_min_code,
        "observed_max_code": "" if observed_max_code is None else observed_max_code,
        "response_code": "" if response_code is None else response_code,
        "start_integ_code": "" if start_integ_code is None else start_integ_code,
        "end_integ_code": "" if end_integ_code is None else end_integ_code,
        "observed_min_integ_code": ""
        if observed_min_integ_code is None
        else observed_min_integ_code,
        "observed_max_integ_code": ""
        if observed_max_integ_code is None
        else observed_max_integ_code,
        "start_freq_mhz": "" if start_freq is None else start_freq,
        "end_freq_mhz": "" if end_freq is None else end_freq,
        "startup_meas_start_ns": args.startup_meas_start_ns,
        "startup_rise_count": len(startup_crossings),
        "startup_period_ns": "" if startup_period_s is None else startup_period_s * 1e9,
        "startup_freq_mhz": "" if startup_freq_mhz is None else startup_freq_mhz,
        "lock_meas_start_ns": args.lock_meas_start_ns,
        "lock_code_check": args.lock_code_check,
        "lock_min_code": args.lock_min_code,
        "lock_max_code": args.lock_max_code,
        "lock_observed_min_code": ""
        if lock_observed_min_code is None
        else lock_observed_min_code,
        "lock_observed_max_code": ""
        if lock_observed_max_code is None
        else lock_observed_max_code,
        "lock_max_abs_ferr_mhz": args.lock_max_abs_ferr_mhz,
        "lock_require_motion": "yes" if args.lock_require_motion else "no",
        "tail_rise_count": len(tail_crossings),
        "tail_period_ns": "" if tail_period_s is None else tail_period_s * 1e9,
        "tail_freq_mhz": "" if tail_freq_mhz is None else tail_freq_mhz,
        "tail_abs_error_mhz": ""
        if tail_abs_error_mhz is None
        else tail_abs_error_mhz,
        "netlist": str(netlist_path),
        "log": str(log_path),
        "waveform": str(xyce_waveform_path(netlist_path)),
    }


def parse_timeout(value):
    if value in (None, "none", "None", "0", "0.0"):
        return None
    timeout = float(value)
    if timeout <= 0:
        raise ValueError("--timeout-s must be positive, 0, or 'none'")
    return timeout


def parse_cases(text):
    cases = [item.strip() for item in text.split(",") if item.strip()]
    for case_name in cases:
        if case_name not in CASES:
            raise ValueError(f"unknown mapped loop case: {case_name}")
    return cases


def main():
    root_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Run a short mapped-digital-core PLL loop SPICE smoke check."
    )
    parser.add_argument("--cases", default="low_start,high_start")
    parser.add_argument(
        "--mapped-verilog",
        default=str(root_dir / "build" / "synth" / "IntegerPLL_DigitalCore_sky130.v"),
    )
    parser.add_argument(
        "--digital-scope",
        default="full",
        help="Label written to CSV for the mapped digital netlist scope.",
    )
    parser.add_argument(
        "--skip-physical-only-cells",
        action="store_true",
        help="Drop tap/fill/decap/antenna-diode cells from final signoff netlists.",
    )
    parser.add_argument("--pdk-root", default=os.environ.get("PDK_ROOT", "~/.volare"))
    parser.add_argument("--pdk", default=os.environ.get("PDK", "sky130A"))
    parser.add_argument(
        "--std-cell-library",
        default=os.environ.get("STD_CELL_LIBRARY", "sky130_fd_sc_hd"),
    )
    parser.add_argument("--corner", default="tt")
    parser.add_argument("--bbpd-rcx-netlist", default=str(
        root_dir
        / "openlane"
        / "IntegerPLL_BBPD"
        / "runs"
        / "librelane_signoff"
        / "rcx-magic"
        / "IntegerPLL_BBPD.rcx.spice"
    ))
    parser.add_argument("--bbpd-subckt", default="IntegerPLL_BBPD")
    parser.add_argument(
        "--dco-impl",
        choices=("behavioral", "postlayout"),
        default="behavioral",
        help="Use the piecewise behavioral DCO model or the filled extracted DCO RCX macro.",
    )
    parser.add_argument(
        "--code-observer-source",
        choices=("auto", "dco_code", "dco_therm"),
        default="auto",
        help=(
            "Source for the analog CODE observer used by checks. 'auto' uses "
            "DCO_THERM for extracted-DCO decks and DCO_CODE for behavioral decks."
        ),
    )
    parser.add_argument(
        "--dco-therm-invert",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Interpret DCO_THERM as active-low thermometer bits for CODE observation.",
    )
    parser.add_argument("--dco-rcx-netlist", default=str(
        root_dir
        / "openlane"
        / "IntegerPLL_DCO"
        / "runs"
        / "librelane_signoff"
        / "rcx-magic"
        / "IntegerPLL_DCO.rcx.spice"
    ))
    parser.add_argument("--dco-subckt", default="IntegerPLL_DCO")
    parser.add_argument(
        "--hardtop-spef-mode",
        choices=("none", "lumped_cap", "distributed_rc"),
        default="none",
        help=(
            "Optionally add parasitics from the signed-off hard-macro top SPEF "
            "on loop/inter-macro nets. distributed_rc substitutes standard-cell "
            "and macro pins onto the selected SPEF RC networks."
        ),
    )
    parser.add_argument(
        "--hardtop-spef",
        default="",
        help="Hard-macro top SPEF used when --hardtop-spef-mode is not none.",
    )
    parser.add_argument(
        "--hardtop-spice",
        default=str(
            root_dir
            / "openlane"
            / "IntegerPLL_HardMacroTop"
            / "runs"
            / "librelane_signoff"
            / "final"
            / "spice"
            / "IntegerPLL_HardMacroTop.spice"
        ),
        help="Hard-macro top extracted SPICE used to map SPEF nets to loop-deck nodes.",
    )
    parser.add_argument("--ki", type=int, default=255)
    parser.add_argument("--kp", type=int, default=32)
    parser.add_argument("--dlf-code-width", type=int, default=10)
    parser.add_argument("--dlf-frac-width", type=int, default=8)
    parser.add_argument("--ndiv", type=int, default=2)
    parser.add_argument("--ref-mhz", type=float, default=None)
    parser.add_argument("--f0-mhz", type=float, default=FILLED_DCO_DEFAULTS["f0_mhz"])
    parser.add_argument("--f64-mhz", type=float, default=FILLED_DCO_DEFAULTS["f64_mhz"])
    parser.add_argument("--f128-mhz", type=float, default=FILLED_DCO_DEFAULTS["f128_mhz"])
    parser.add_argument("--f192-mhz", type=float, default=FILLED_DCO_DEFAULTS["f192_mhz"])
    parser.add_argument("--f255-mhz", type=float, default=FILLED_DCO_DEFAULTS["f255_mhz"])
    parser.add_argument("--threshold", type=float, default=0.9)
    parser.add_argument("--code-sharpness", type=float, default=20.0)
    parser.add_argument("--clock-sharpness", type=float, default=500.0)
    parser.add_argument("--initial-dco-phase-cycles", type=float, default=-0.25)
    parser.add_argument("--low-start-initial-dco-phase-cycles", type=float, default=None)
    parser.add_argument("--high-start-initial-dco-phase-cycles", type=float, default=None)
    parser.add_argument("--mid-start-inc-initial-dco-phase-cycles", type=float, default=None)
    parser.add_argument("--mid-start-dec-initial-dco-phase-cycles", type=float, default=None)
    parser.add_argument("--reset-release-ns", type=float, default=5.0)
    parser.add_argument("--supply-ramp-delay-ns", type=float, default=0.0)
    parser.add_argument(
        "--supply-ramp-ns",
        type=float,
        default=0.0,
        help="Ramp VPWR/VPB over this interval; useful with extracted RCX decks and UIC.",
    )
    parser.add_argument(
        "--init-dco-therm",
        action="store_true",
        help="Seed DCO_THERM nodes from the rail start code for extracted-DCO UIC startup.",
    )
    parser.add_argument("--clear-start-ns", type=float, default=10.0)
    parser.add_argument("--clear-width-ns", type=float, default=60.0)
    parser.add_argument("--enable-ns", type=float, default=80.0)
    parser.add_argument("--start-meas-ns", type=float, default=79.0)
    parser.add_argument("--end-meas-ns", type=float, default=129.0)
    parser.add_argument("--sim-time-ns", type=float, default=130.0)
    parser.add_argument("--step-ps", type=float, default=1000.0)
    parser.add_argument("--max-step-ps", type=float, default=1000.0)
    parser.add_argument(
        "--tran-uic",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Append UIC to the transient statement. Use --no-tran-uic for extracted-DCO startup.",
    )
    parser.add_argument("--start-code-tolerance", type=float, default=2.0)
    parser.add_argument("--min-code-motion", type=float, default=1.0)
    parser.add_argument(
        "--check-mode",
        choices=("motion", "no_motion", "startup", "lock_window"),
        default="motion",
        help=(
            "Validate DCO code motion, deliberate no-motion gain probes, "
            "extracted-DCO startup oscillation, or bounded near-lock tail frequency."
        ),
    )
    parser.add_argument("--startup-meas-start-ns", type=float, default=15.0)
    parser.add_argument("--startup-min-rises", type=int, default=2)
    parser.add_argument("--startup-min-freq-mhz", type=float, default=30.0)
    parser.add_argument("--startup-max-freq-mhz", type=float, default=80.0)
    parser.add_argument("--lock-meas-start-ns", type=float, default=119.0)
    parser.add_argument("--lock-min-rises", type=int, default=3)
    parser.add_argument(
        "--lock-code-check",
        choices=("window", "endpoint", "none"),
        default="window",
        help=(
            "Use full tail-window CODE extrema, final endpoint CODE, or no CODE "
            "bound for check-mode=lock_window."
        ),
    )
    parser.add_argument("--lock-min-code", type=float, default=0.0)
    parser.add_argument("--lock-max-code", type=float, default=255.0)
    parser.add_argument("--lock-max-abs-ferr-mhz", type=float, default=0.25)
    parser.add_argument(
        "--lock-require-motion",
        action="store_true",
        help="Require expected DCO-code motion in addition to the lock-window bounds.",
    )
    parser.add_argument("--timeout-s", default="900")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse matching existing deck/log/waveform files in the build directory.",
    )
    parser.add_argument(
        "--allow-fail",
        action="store_true",
        help="Write failed diagnostic rows but exit zero.",
    )
    parser.add_argument("--print-internal-debug", action="store_true")
    parser.add_argument(
        "--simulator",
        choices=("xyce",),
        default="xyce",
        help="Circuit simulator for the generated mapped loop deck.",
    )
    add_xyce_arguments(parser)
    parser.add_argument(
        "--build-dir",
        default=str(root_dir / "build" / "spice_pll_mapped_loop"),
    )
    args = parser.parse_args()
    args.timeout_s = parse_timeout(args.timeout_s)
    if args.ki < 0 or args.ki > 255 or args.kp < 0 or args.kp > 255:
        raise ValueError("--ki and --kp must be 8-bit values")
    if args.dlf_code_width != 10:
        raise ValueError("--dlf-code-width must remain 10 for the current mapped loop deck")
    if args.dlf_frac_width < 0 or args.dlf_frac_width > 12:
        raise ValueError("--dlf-frac-width must be in 0..12")
    if args.ndiv < 2 or args.ndiv > 255:
        raise ValueError("--ndiv must be in 2..255")
    if args.jobs < 1:
        raise ValueError("--jobs must be positive")
    validate_xyce_arguments(args)

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
    verilog_text = mapped_verilog.read_text(encoding="utf-8")
    args.net_aliases = parse_vector_aliases(verilog_text)
    instances = parse_instances(verilog_text)
    if not instances:
        raise ValueError(f"no Sky130 cell instances found in {mapped_verilog}")
    original_instance_count = len(instances)
    if args.skip_physical_only_cells:
        instances = [
            instance
            for instance in instances
            if not physical_only_cell(instance["type"])
        ]
    args.skipped_physical_only_cells = original_instance_count - len(instances)
    args.mapped_instance_count = len(instances)
    load_hardtop_spef_state(args, instances)
    print(
        f"using {args.mapped_instance_count} mapped digital-core cells "
        f"(skipped {args.skipped_physical_only_cells} physical-only cells, "
        f"resolved {len(args.net_aliases)} DCO output aliases)",
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
        with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
            future_map = {
                executor.submit(
                    run_one, case_name, args, build_dir, instances, subckt_ports
                ): case_name
                for case_name in case_names
            }
            for future in concurrent.futures.as_completed(future_map):
                case_name = future_map[future]
                rows_by_case[case_name] = future.result()
        rows = [rows_by_case[case_name] for case_name in case_names]
    csv_path = build_dir / "mapped_loop_check.csv"
    with csv_path.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    for row in rows:
        print(
            f"case={row['case']} status={row['status']} "
            f"code={row['start_code']}->{row['end_code']} "
            f"response={row['response_code']} "
            f"elapsed_s={row['elapsed_s']} timeout={row['timed_out']}"
        )
    print(f"wrote {csv_path}")

    failed = [row for row in rows if row["status"] != "pass"]
    if failed:
        print(f"{len(failed)} mapped loop SPICE checks failed", file=sys.stderr)
        if args.allow_fail:
            return 0
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
