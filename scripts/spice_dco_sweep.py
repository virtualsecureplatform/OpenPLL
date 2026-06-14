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
from pathlib import Path

from sky130_pdk import default_pdk_root


RE_FLOAT = r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"


def parse_codes(text):
    if text == "all":
        return list(range(256))
    codes = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        code = int(item, 0)
        if code < 0 or code > 255:
            raise ValueError(f"code out of 8-bit range: {code}")
        codes.append(code)
    return codes


def parse_coarse_codes(text, max_code=15):
    if text == "all":
        return list(range(max_code + 1))
    codes = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        code = int(item, 0)
        if code < 0 or code > max_code:
            raise ValueError(f"coarse code out of range 0..{max_code}: {code}")
        codes.append(code)
    return codes


def parse_drive_list(text):
    drives = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        drive = int(item, 0)
        if drive < 1:
            raise ValueError(f"drive strength must be positive: {drive}")
        drives.append(drive)
    if not drives:
        raise ValueError("at least one output buffer drive is required")
    return drives


def measure_value(log_text, name):
    patterns = [
        rf"^\s*{name}\s*=\s*{RE_FLOAT}",
        rf"^\s*{name}\s*:\s*{RE_FLOAT}",
    ]
    for pattern in patterns:
        match = re.search(pattern, log_text, re.IGNORECASE | re.MULTILINE)
        if match:
            return float(match.group(1))
    return None


def select_positive_measure(values, upper_bound=None):
    for value in values:
        if value is None or value <= 0:
            continue
        if upper_bound is not None and value >= upper_bound:
            continue
        return value
    return None


def waveform_values(log_text, period):
    high_time = select_positive_measure(
        [
            measure_value(log_text, "high_time_same_s"),
            measure_value(log_text, "high_time_next_s"),
        ],
        period,
    )
    low_time = select_positive_measure(
        [
            measure_value(log_text, "low_time_same_s"),
            measure_value(log_text, "low_time_next_s"),
        ],
        period,
    )
    edge_bound = period * 0.5 if period else None
    rise_time = select_positive_measure(
        [
            measure_value(log_text, "rise_time_same_s"),
            measure_value(log_text, "rise_time_offset_s"),
        ],
        edge_bound,
    )
    fall_time = select_positive_measure(
        [
            measure_value(log_text, "fall_time_same_s"),
            measure_value(log_text, "fall_time_offset_s"),
        ],
        edge_bound,
    )
    duty_ratio = (
        high_time / (high_time + low_time)
        if high_time and low_time and (high_time + low_time) > 0
        else None
    )
    return high_time, low_time, duty_ratio, rise_time, fall_time


def load_control_index(idx, load_index_min, load_index_max, load_control_map):
    if load_control_map == "physical-index":
        return idx
    if load_control_map == "even":
        load_count = load_index_max - load_index_min + 1
        offset = idx - load_index_min
        return ((offset + 1) * 255) // load_count - 1
    raise ValueError(f"unsupported load control map: {load_control_map}")


def load_active_for_code(control_index, code, therm_invert):
    active = control_index < code
    if therm_invert:
        active = not active
    return active


def enabled_load_count(
    code,
    therm_invert,
    load_index_min=0,
    load_index_max=254,
    load_control_map="physical-index",
):
    count = 0
    for idx in range(load_index_min, load_index_max + 1):
        control_index = load_control_index(
            idx, load_index_min, load_index_max, load_control_map
        )
        if load_active_for_code(control_index, code, therm_invert):
            count += 1
    return count


def monotonic_failures(rows, therm_invert):
    failures = []
    by_corner = {}
    for row in rows:
        key = (row["corner"], int(row.get("coarse_code") or 0))
        by_corner.setdefault(key, []).append(row)

    for (corner, coarse_code), corner_rows in by_corner.items():
        sorted_rows = sorted(corner_rows, key=lambda row: row["code"])
        for prev, curr in zip(sorted_rows, sorted_rows[1:]):
            prev_freq = float(prev["freq_hz"])
            curr_freq = float(curr["freq_hz"])
            if therm_invert:
                ok = curr_freq > prev_freq
                relation = "increase"
            else:
                ok = curr_freq < prev_freq
                relation = "decrease"
            if not ok:
                failures.append(
                    (
                        corner,
                        coarse_code,
                        prev["code"],
                        prev_freq,
                        curr["code"],
                        curr_freq,
                        relation,
                    )
                )
    return failures


def load_cell_lines(idx, active, ring_node, load_style, cell_prefix, load_drive):
    if load_style == "nand2":
        ctrl = "VDD" if active else "0"
        return [
            f"VCTRL{idx:03d} C{idx:03d} 0 {{{ctrl}}}",
            f"XLOAD{idx:03d} {ring_node} C{idx:03d} VGND VNB VPB VPWR "
            f"LD{idx:03d} {cell_prefix}__nand2_{load_drive}",
        ]
    if load_style == "einvp":
        ctrl = "VDD" if active else "0"
        return [
            f"VCTRL{idx:03d} C{idx:03d} 0 {{{ctrl}}}",
            f"XLOAD{idx:03d} {ring_node} C{idx:03d} VGND VNB VPB VPWR "
            f"LD{idx:03d} {cell_prefix}__einvp_1",
        ]
    if load_style == "einvn":
        ctrl = "0" if active else "VDD"
        return [
            f"VCTRL{idx:03d} C{idx:03d} 0 {{{ctrl}}}",
            f"XLOAD{idx:03d} {ring_node} C{idx:03d} VGND VNB VPB VPWR "
            f"LD{idx:03d} {cell_prefix}__einvn_1",
        ]
    if load_style == "dlclkp":
        ctrl = "VDD" if active else "0"
        return [
            f"VCTRL{idx:03d} C{idx:03d} 0 {{{ctrl}}}",
            f"XLOAD{idx:03d} {ring_node} C{idx:03d} VGND VNB VPB VPWR "
            f"LD{idx:03d} {cell_prefix}__dlclkp_1",
        ]
    raise ValueError(f"unsupported load style: {load_style}")


def mirror_turn_cell(coarse_code):
    return coarse_code


def fixed_delay_nodes(fixed_delay_cells):
    if fixed_delay_cells == 0:
        return []
    return [f"D{idx:02d}" for idx in range(fixed_delay_cells - 1)] + ["N0"]


def mirror_input_node(fixed_delay_cells):
    nodes = fixed_delay_nodes(fixed_delay_cells)
    return nodes[-1] if nodes else "NRAW"


def mirror_loop_lines(
    coarse_code,
    cell_prefix,
    mirror_segments,
    logic_drive,
    turn_drive,
    fixed_delay_cells,
):
    last_segment = mirror_segments - 1
    mirror_input = mirror_input_node(fixed_delay_cells)
    lines = [
        "* mirror_delay_style=turn-pass",
        f"* mirror_turn_cell=C{mirror_turn_cell(coarse_code):02d}",
        f"* mirror_segments={mirror_segments}",
        f"* logic_drive={logic_drive}",
        f"* turn_drive={turn_drive}",
        f"* fixed_delay_cells={fixed_delay_cells}",
        "* One NAND reset inversion, optional fixed NAND base-delay cells,",
        "* and a NAND/NAND2B turn-pass mirror-delay path.",
        f"XOSC R00 EN VGND VNB VPB VPWR NRAW {cell_prefix}__nand2_{logic_drive}",
    ]
    previous_node = "NRAW"
    for idx, output_node in enumerate(fixed_delay_nodes(fixed_delay_cells)):
        lines.append(
            f"XFIX{idx:02d} {previous_node} VPWR VGND VNB VPB VPWR "
            f"{output_node} {cell_prefix}__nand2_{logic_drive}"
        )
        previous_node = output_node
    for idx in range(mirror_segments):
        value = "VDD" if idx < coarse_code else "0"
        lines.append(f"VCOARSE{idx:02d} P{idx:02d} 0 {{{value}}}")
    for idx in range(last_segment):
        fin = mirror_input if idx == 0 else f"F{idx:02d}"
        lines.append(
            f"XMFWD{idx:02d} {fin} P{idx:02d} VGND VNB VPB VPWR F{idx + 1:02d} "
            f"{cell_prefix}__nand2_{logic_drive}"
        )
    lines.append(f"VPASS{last_segment:02d} PN{last_segment:02d} 0 {{VDD}}")
    for idx in range(last_segment, -1, -1):
        fin = mirror_input if idx == 0 else f"F{idx:02d}"
        lines.append(
            f"XMTURN{idx:02d} P{idx:02d} {fin} VGND VNB VPB VPWR TN{idx:02d} "
            f"{cell_prefix}__nand2b_{turn_drive}"
        )
        if idx < last_segment:
            lines.append(
                f"XMRET{idx:02d} R{idx + 1:02d} P{idx:02d} VGND VNB VPB VPWR PN{idx:02d} "
                f"{cell_prefix}__nand2b_{turn_drive}"
            )
        lines.append(
            f"XMMERGE{idx:02d} TN{idx:02d} PN{idx:02d} VGND VNB VPB VPWR R{idx:02d} "
            f"{cell_prefix}__nand2_{logic_drive}"
        )
    return lines


def mirror_initial_nodes(coarse_code, fixed_delay_cells):
    nodes = ["R00", "NRAW", *fixed_delay_nodes(fixed_delay_cells)]
    nodes.extend(f"F{idx:02d}" for idx in range(1, coarse_code + 1))
    nodes.extend(f"R{idx:02d}" for idx in range(coarse_code, 0, -1))
    return nodes


def model_include_lines(model_path, corner):
    model_dir = model_path.parent
    supported = {"tt", "ff", "ss", "sf", "fs"}
    if corner not in supported:
        raise ValueError(
            f"explicit ngspice corner includes support {sorted(supported)}, got {corner!r}"
        )
    return [
        f"* model_library={model_path}",
        f"* model_corner={corner}",
        ".param mc_mm_switch=0",
        ".param mc_pr_switch=0",
        f'.include "{model_dir / "corners" / f"{corner}.spice"}"',
        f'.include "{model_dir / "r+c" / "res_typical__cap_typical.spice"}"',
        f'.include "{model_dir / "r+c" / "res_typical__cap_typical__lin.spice"}"',
        f'.include "{model_dir / "corners" / corner / "specialized_cells.spice"}"',
    ]


def dco_netlist(
    code,
    coarse_code,
    pdk_root,
    pdk,
    corner,
    sim_time_ns,
    step_ps,
    meas_start_ns,
    therm_invert,
    ngspice_threads,
    load_style,
    std_cell_library,
    topology,
    ring_stages,
    load_index_min,
    load_index_max,
    load_control_map,
    mirror_segments,
    logic_drive,
    turn_drive,
    output_buffer_drives,
    load_drive,
    fixed_delay_cells,
):
    pdk_dir = pdk_root / pdk
    model_path = pdk_dir / "libs.tech" / "ngspice" / "sky130.lib.spice"
    cell_path = (
        pdk_dir
        / "libs.ref"
        / std_cell_library
        / "spice"
        / f"{std_cell_library}.spice"
    )
    cell_prefix = std_cell_library

    if not model_path.exists():
        raise FileNotFoundError(model_path)
    if not cell_path.exists():
        raise FileNotFoundError(cell_path)

    mirror_input = mirror_input_node(fixed_delay_cells)
    if topology == "mirror-coarse":
        en_source = "VEN EN 0 {VDD}"
        reset_source = "uic-active-path"
        startup_kick = f"IKICK {mirror_input} 0 PULSE(0 1u 0.55n 1p 1p 20p 100n)"
    else:
        en_source = "VEN EN 0 {VDD}"
        reset_source = "held-enabled"
        startup_kick = ""

    lines = [
        f"* OpenPLL Sky130 8-bit DCO transient validation, code={code}",
        f"* therm_invert={int(therm_invert)}, enabled_loads={enabled_load_count(code, therm_invert, load_index_min, load_index_max, load_control_map)}",
        f"* load_style={load_style}",
        f"* load_control_map={load_control_map}",
        f"* std_cell_library={std_cell_library}",
        f"* topology={topology}",
        f"* reset_source={reset_source}",
        f"* coarse_code={coarse_code}",
        f"* ring_stages={ring_stages}",
        f"* mirror_segments={mirror_segments}",
        f"* meas_start_ns={meas_start_ns}",
        f"* load_index_min={load_index_min}",
        f"* load_index_max={load_index_max}",
        f"* logic_drive={logic_drive}",
        f"* turn_drive={turn_drive}",
        f"* output_buffer_drives={','.join(str(drive) for drive in output_buffer_drives)}",
        f"* load_drive={load_drive}",
        f"* fixed_delay_cells={fixed_delay_cells}",
        *model_include_lines(model_path, corner),
        f'.include "{cell_path}"',
        ".option method=gear reltol=1e-3 abstol=1e-15 chgtol=1e-16"
        + (f" num_threads={ngspice_threads}" if ngspice_threads > 0 else ""),
        ".param VDD=1.8",
        "VVPWR VPWR 0 {VDD}",
        "VVPB VPB 0 {VDD}",
        "VVGND VGND 0 0",
        "VVNB VNB 0 0",
        en_source,
        startup_kick,
        "",
    ]

    if topology == "inverter-ring":
        lines.extend(
            [
                f"* {ring_stages}-stage enabled ring. Active-low reset behavior is represented",
                "* by the NAND gate enable input held high during this free-run test.",
                f"XOSC N{ring_stages - 1} EN VGND VNB VPB VPWR N0 {cell_prefix}__nand2_{logic_drive}",
            ]
        )
        for idx in range(1, ring_stages):
            lines.append(
                f"XINV{idx:02d} N{idx - 1} VGND VNB VPB VPWR N{idx} "
                f"{cell_prefix}__inv_1"
            )
        load_nodes = [f"N{idx}" for idx in range(ring_stages)]
        initial_nodes = load_nodes
        pllout_source = f"N{ring_stages - 1}"
    elif topology == "mirror-coarse":
        lines.extend(
            mirror_loop_lines(
                coarse_code=coarse_code,
                cell_prefix=cell_prefix,
                mirror_segments=mirror_segments,
                logic_drive=logic_drive,
                turn_drive=turn_drive,
                fixed_delay_cells=fixed_delay_cells,
            )
        )
        load_nodes = [mirror_input, "R00"]
        initial_nodes = mirror_initial_nodes(coarse_code, fixed_delay_cells)
        pllout_source = mirror_input
    else:
        raise ValueError(f"unsupported topology: {topology}")

    lines.extend(["", "* Buffered PLL output measurement point."])
    output_source = pllout_source
    for idx, drive in enumerate(output_buffer_drives):
        output_node = "PLLOUT" if idx == len(output_buffer_drives) - 1 else f"PLLOUT_B{idx}"
        lines.append(
            f"XOUTBUF{idx:02d} {output_source} VGND VNB VPB VPWR "
            f"{output_node} {cell_prefix}__buf_{drive}"
        )
        output_source = output_node

    lines.extend(
        [
            "",
            f"* {load_index_max - load_index_min + 1} {load_style} varactor/load cells.",
            f"* Instantiated thermometer index range: {load_index_min}..{load_index_max}.",
            f"* Load control mapping: {load_control_map}.",
            "* A high thermometer control",
            "* enables dummy output switching for the active load styles.",
        ]
    )

    for idx in range(load_index_min, load_index_max + 1):
        control_index = load_control_index(
            idx, load_index_min, load_index_max, load_control_map
        )
        active = load_active_for_code(control_index, code, therm_invert)
        ring_node = load_nodes[idx % len(load_nodes)]
        lines.extend(
            load_cell_lines(
                idx=idx,
                active=active,
                ring_node=ring_node,
                load_style=load_style,
                cell_prefix=cell_prefix,
                load_drive=load_drive,
            )
        )

    lines.extend(
        [
            "",
            "* Alternating initial conditions force startup in batch ngspice.",
        ]
    )

    if initial_nodes:
        for idx, node in enumerate(initial_nodes):
            value = "VDD" if idx % 2 else "0"
            lines.append(f".ic v({node})={{{value}}}")

    tran_suffix = " uic" if initial_nodes else ""

    lines.extend(
        [
            "",
            f".tran {step_ps}p {sim_time_ns}n{tran_suffix}",
            f".meas tran two_cycle_s TRIG v(PLLOUT) VAL=0.9 TD={meas_start_ns}n RISE=1 "
            f"TARG v(PLLOUT) VAL=0.9 TD={meas_start_ns}n RISE=3",
            ".meas tran period_s PARAM='two_cycle_s/2'",
            ".meas tran freq_hz PARAM='1/period_s'",
            f".meas tran high_time_same_s TRIG v(PLLOUT) VAL=0.9 TD={meas_start_ns}n RISE=2 "
            f"TARG v(PLLOUT) VAL=0.9 TD={meas_start_ns}n FALL=2",
            f".meas tran high_time_next_s TRIG v(PLLOUT) VAL=0.9 TD={meas_start_ns}n RISE=2 "
            f"TARG v(PLLOUT) VAL=0.9 TD={meas_start_ns}n FALL=3",
            f".meas tran low_time_same_s TRIG v(PLLOUT) VAL=0.9 TD={meas_start_ns}n FALL=2 "
            f"TARG v(PLLOUT) VAL=0.9 TD={meas_start_ns}n RISE=2",
            f".meas tran low_time_next_s TRIG v(PLLOUT) VAL=0.9 TD={meas_start_ns}n FALL=2 "
            f"TARG v(PLLOUT) VAL=0.9 TD={meas_start_ns}n RISE=3",
            f".meas tran rise_time_same_s TRIG v(PLLOUT) VAL=0.36 TD={meas_start_ns}n RISE=2 "
            f"TARG v(PLLOUT) VAL=1.44 TD={meas_start_ns}n RISE=2",
            f".meas tran rise_time_offset_s TRIG v(PLLOUT) VAL=0.36 TD={meas_start_ns}n RISE=3 "
            f"TARG v(PLLOUT) VAL=1.44 TD={meas_start_ns}n RISE=3",
            f".meas tran fall_time_same_s TRIG v(PLLOUT) VAL=1.44 TD={meas_start_ns}n FALL=2 "
            f"TARG v(PLLOUT) VAL=0.36 TD={meas_start_ns}n FALL=2",
            f".meas tran fall_time_offset_s TRIG v(PLLOUT) VAL=1.44 TD={meas_start_ns}n FALL=3 "
            f"TARG v(PLLOUT) VAL=0.36 TD={meas_start_ns}n FALL=3",
            ".end",
            "",
        ]
    )
    return "\n".join(lines)


def dco_result_from_log(code, coarse_code, corner, args, netlist_path, log_path):
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    period = measure_value(log_text, "period_s")
    freq = measure_value(log_text, "freq_hz")
    high_time, low_time, duty_ratio, rise_time, fall_time = waveform_values(
        log_text, period
    )
    status = (
        "pass"
        if period and freq and high_time and low_time and duty_ratio and rise_time and fall_time
        else "fail"
    )
    selected_tap = mirror_turn_cell(coarse_code) if args.topology == "mirror-coarse" else ""
    return {
        "corner": corner,
        "topology": args.topology,
        "std_cell_library": args.std_cell_library,
        "coarse_code": coarse_code,
        "selected_tap": selected_tap,
        "code": code,
        "therm_invert": int(args.therm_invert),
        "enabled_loads": enabled_load_count(
            code,
            args.therm_invert,
            args.load_index_min,
            args.load_index_max,
            args.load_control_map,
        ),
        "ring_stages": args.ring_stages,
        "mirror_segments": args.mirror_segments,
        "meas_start_ns": args.meas_start_ns,
        "load_index_min": args.load_index_min,
        "load_index_max": args.load_index_max,
        "load_control_map": args.load_control_map,
        "logic_drive": args.logic_drive,
        "turn_drive": args.turn_drive,
        "output_buffer_drives": args.output_buffer_drives_text,
        "load_drive": args.load_drive,
        "fixed_delay_cells": args.fixed_delay_cells,
        "status": status,
        "period_s": period or "",
        "freq_hz": freq or "",
        "freq_mhz": (freq / 1.0e6) if freq else "",
        "high_time_s": high_time or "",
        "low_time_s": low_time or "",
        "duty_ratio": duty_ratio or "",
        "rise_time_s": rise_time or "",
        "fall_time_s": fall_time or "",
        "netlist": str(netlist_path),
        "log": str(log_path),
    }


def existing_result_matches_request(netlist_path, code, coarse_code, corner, args):
    if not netlist_path.exists():
        return False
    text = netlist_path.read_text(encoding="ascii", errors="ignore")
    required_snippets = [
        f"code={code}",
        f"therm_invert={int(args.therm_invert)}",
        f"load_style={args.load_style}",
        f"load_control_map={args.load_control_map}",
        f"std_cell_library={args.std_cell_library}",
        f"topology={args.topology}",
        f"coarse_code={coarse_code}",
        f"ring_stages={args.ring_stages}",
        f"mirror_segments={args.mirror_segments}",
        f"meas_start_ns={args.meas_start_ns}",
        f"load_index_min={args.load_index_min}",
        f"load_index_max={args.load_index_max}",
        f"logic_drive={args.logic_drive}",
        f"turn_drive={args.turn_drive}",
        f"output_buffer_drives={args.output_buffer_drives_text}",
        f"load_drive={args.load_drive}",
        f"fixed_delay_cells={args.fixed_delay_cells}",
        f"model_corner={corner}",
        f".tran {args.step_ps}p {args.sim_time_ns}n uic",
    ]
    if args.ngspice_threads > 0:
        required_snippets.append(f"num_threads={args.ngspice_threads}")
    if args.topology == "mirror-coarse":
        required_snippets.append("mirror_delay_style=turn-pass")
        required_snippets.append("reset_source=uic-active-path")
        required_snippets.append("IKICK ")
        if args.fixed_delay_cells > 0:
            required_snippets.append("XFIX00")
    required_snippets.append("XOUTBUF00")
    required_snippets.append("high_time_same_s")
    required_snippets.append("high_time_next_s")
    required_snippets.append("rise_time_same_s")
    required_snippets.append("fall_time_offset_s")
    return all(snippet in text for snippet in required_snippets)


def run_one(code, coarse_code, corner, args, build_dir):
    if args.topology == "mirror-coarse":
        stem = f"dco_{corner}_coarse_{coarse_code:02d}_code_{code:03d}"
    else:
        stem = f"dco_{corner}_code_{code:03d}"
    netlist_path = build_dir / f"{stem}.spice"
    log_path = build_dir / f"{stem}.log"
    if (
        args.resume
        and log_path.exists()
        and existing_result_matches_request(netlist_path, code, coarse_code, corner, args)
    ):
        result = dco_result_from_log(code, coarse_code, corner, args, netlist_path, log_path)
        if result["status"] == "pass":
            result["resumed"] = True
            return result

    netlist_path.write_text(
        dco_netlist(
            code=code,
            coarse_code=coarse_code,
            pdk_root=Path(args.pdk_root).expanduser().resolve(),
            pdk=args.pdk,
            corner=corner,
            sim_time_ns=args.sim_time_ns,
            step_ps=args.step_ps,
            meas_start_ns=args.meas_start_ns,
            therm_invert=args.therm_invert,
            ngspice_threads=args.ngspice_threads,
            load_style=args.load_style,
            std_cell_library=args.std_cell_library,
            topology=args.topology,
            ring_stages=args.ring_stages,
            load_index_min=args.load_index_min,
            load_index_max=args.load_index_max,
            load_control_map=args.load_control_map,
            mirror_segments=args.mirror_segments,
            logic_drive=args.logic_drive,
            turn_drive=args.turn_drive,
            output_buffer_drives=args.output_buffer_drives,
            load_drive=args.load_drive,
            fixed_delay_cells=args.fixed_delay_cells,
        ),
        encoding="ascii",
    )

    env = os.environ.copy()
    if args.ngspice_threads > 0:
        env["OMP_NUM_THREADS"] = str(args.ngspice_threads)
    model_dir = (
        Path(args.pdk_root).expanduser().resolve()
        / args.pdk
        / "libs.tech"
        / "ngspice"
    )
    proc = subprocess.run(
        [args.ngspice, "-b", str(netlist_path)],
        cwd=model_dir,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log_path.write_text(proc.stdout, encoding="utf-8")

    period = measure_value(proc.stdout, "period_s")
    freq = measure_value(proc.stdout, "freq_hz")
    high_time, low_time, duty_ratio, rise_time, fall_time = waveform_values(
        proc.stdout, period
    )
    status = (
        "pass"
        if proc.returncode == 0
        and period
        and freq
        and high_time
        and low_time
        and duty_ratio
        and rise_time
        and fall_time
        else "fail"
    )
    selected_tap = mirror_turn_cell(coarse_code) if args.topology == "mirror-coarse" else ""
    return {
        "corner": corner,
        "topology": args.topology,
        "std_cell_library": args.std_cell_library,
        "coarse_code": coarse_code,
        "selected_tap": selected_tap,
        "code": code,
        "therm_invert": int(args.therm_invert),
        "enabled_loads": enabled_load_count(
            code,
            args.therm_invert,
            args.load_index_min,
            args.load_index_max,
            args.load_control_map,
        ),
        "ring_stages": args.ring_stages,
        "mirror_segments": args.mirror_segments,
        "meas_start_ns": args.meas_start_ns,
        "load_index_min": args.load_index_min,
        "load_index_max": args.load_index_max,
        "load_control_map": args.load_control_map,
        "logic_drive": args.logic_drive,
        "turn_drive": args.turn_drive,
        "output_buffer_drives": args.output_buffer_drives_text,
        "load_drive": args.load_drive,
        "fixed_delay_cells": args.fixed_delay_cells,
        "status": status,
        "period_s": period or "",
        "freq_hz": freq or "",
        "freq_mhz": (freq / 1.0e6) if freq else "",
        "high_time_s": high_time or "",
        "low_time_s": low_time or "",
        "duty_ratio": duty_ratio or "",
        "rise_time_s": rise_time or "",
        "fall_time_s": fall_time or "",
        "netlist": str(netlist_path),
        "log": str(log_path),
        "resumed": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--codes",
        default="0,64,128,192,255",
        help='Comma-separated DCO codes or "all". Default is a representative sweep.',
    )
    parser.add_argument("--pdk-root", default=default_pdk_root())
    parser.add_argument("--pdk", default=os.environ.get("PDK", "sky130A"))
    parser.add_argument(
        "--std-cell-library",
        default=os.environ.get("STD_CELL_LIBRARY", "sky130_fd_sc_hd"),
        help="Sky130 standard-cell library used for generated transistor DCO decks.",
    )
    parser.add_argument("--corner", default="tt")
    parser.add_argument(
        "--corners",
        default=None,
        help="Comma-separated model corners. Defaults to --corner.",
    )
    parser.add_argument("--sim-time-ns", type=float, default=120.0)
    parser.add_argument("--step-ps", type=float, default=10.0)
    parser.add_argument(
        "--meas-start-ns",
        type=float,
        default=10.0,
        help="Transient time after which DCO frequency, duty, and edge measurements start.",
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Number of parallel ngspice jobs to run.",
    )
    parser.add_argument(
        "--coarse-codes",
        default="0",
        help='Comma-separated coarse codes or "all" for --topology mirror-coarse.',
    )
    parser.add_argument(
        "--therm-invert",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Invert the binary-to-thermometer decoder output before the DCO "
            "load bank. The default matches the RTL PLL top-level polarity."
        ),
    )
    parser.add_argument(
        "--topology",
        choices=("inverter-ring", "mirror-coarse"),
        default="inverter-ring",
        help="Oscillator topology to generate. mirror-coarse matches IntegerPLL_DCO_EINVP_COARSE.",
    )
    parser.add_argument(
        "--load-style",
        choices=("nand2", "einvp", "einvn", "dlclkp"),
        default="nand2",
        help="Standard-cell topology used for each thermometer-controlled DCO dummy load.",
    )
    parser.add_argument(
        "--ring-stages",
        type=int,
        default=17,
        help="Odd number of enabled ring stages including the NAND enable gate.",
    )
    parser.add_argument(
        "--mirror-segments",
        type=int,
        default=16,
        help="Number of turn/pass mirror-delay coarse positions for --topology mirror-coarse.",
    )
    parser.add_argument(
        "--load-index-min",
        type=int,
        default=0,
        help="Lowest thermometer-load index physically instantiated in the DCO probe.",
    )
    parser.add_argument(
        "--load-index-max",
        type=int,
        default=254,
        help="Highest thermometer-load index physically instantiated in the DCO probe.",
    )
    parser.add_argument(
        "--load-control-map",
        choices=("physical-index", "even"),
        default="physical-index",
        help=(
            "Map physical load cells to thermometer control codes directly or "
            "spread a sparse physical load bank across the full 8-bit code range."
        ),
    )
    parser.add_argument(
        "--logic-drive",
        type=int,
        default=1,
        help="Drive strength suffix for NAND2 cells in the active oscillator path.",
    )
    parser.add_argument(
        "--turn-drive",
        type=int,
        default=1,
        help="Drive strength suffix for NAND2B cells in the mirror turn/pass path.",
    )
    parser.add_argument(
        "--output-buffer-drives",
        default="1",
        help=(
            "Comma-separated drive strengths for the PLLOUT buffer chain. The first "
            "entry is the only buffer input attached to the oscillator node."
        ),
    )
    parser.add_argument(
        "--load-drive",
        type=int,
        default=1,
        help="Drive strength suffix for NAND2 fine-load cells.",
    )
    parser.add_argument(
        "--fixed-delay-cells",
        type=int,
        default=2,
        help="Number of fixed NAND2 base-delay cells after the reset gate in mirror-coarse topology.",
    )
    parser.add_argument("--ngspice", default=shutil.which("ngspice") or "ngspice")
    parser.add_argument(
        "--ngspice-threads",
        type=int,
        default=int(os.environ.get("NGSPICE_THREADS", "0")),
        help="Set ngspice OpenMP threads via .option num_threads and OMP_NUM_THREADS; 0 leaves default.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse matching existing passing netlists/logs in the build directory.",
    )
    parser.add_argument(
        "--build-dir",
        default=str(Path(__file__).resolve().parents[1] / "build" / "spice"),
    )
    args = parser.parse_args()
    args.output_buffer_drives = parse_drive_list(args.output_buffer_drives)
    args.output_buffer_drives_text = ",".join(str(drive) for drive in args.output_buffer_drives)

    codes = parse_codes(args.codes)
    corners = (
        [item.strip() for item in args.corners.split(",") if item.strip()]
        if args.corners
        else [args.corner]
    )
    build_dir = Path(args.build_dir).expanduser().resolve()
    build_dir.mkdir(parents=True, exist_ok=True)
    if args.jobs < 1:
        raise ValueError("--jobs must be at least 1")
    if args.ngspice_threads < 0:
        raise ValueError("--ngspice-threads must be non-negative")
    if args.meas_start_ns < 0 or args.meas_start_ns >= args.sim_time_ns:
        raise ValueError("--meas-start-ns must be non-negative and less than --sim-time-ns")
    for name in ("logic_drive", "turn_drive", "load_drive"):
        if getattr(args, name) < 1:
            raise ValueError(f"--{name.replace('_', '-')} must be positive")
    if args.fixed_delay_cells < 0:
        raise ValueError("--fixed-delay-cells must be non-negative")
    if args.ring_stages < 3 or (args.ring_stages % 2) == 0:
        raise ValueError("--ring-stages must be an odd integer >= 3")
    if args.mirror_segments < 2:
        raise ValueError("--mirror-segments must be at least 2")
    if args.topology == "mirror-coarse":
        args.ring_stages = args.mirror_segments + 1
    elif args.mirror_segments != 16:
        raise ValueError("--mirror-segments only applies to --topology mirror-coarse")
    coarse_codes = parse_coarse_codes(
        args.coarse_codes,
        args.mirror_segments - 1 if args.topology == "mirror-coarse" else 0,
    )
    if args.topology == "inverter-ring" and coarse_codes != [0]:
        raise ValueError("--coarse-codes other than 0 require --topology mirror-coarse")
    allowed_scls = {"sky130_fd_sc_hd", "sky130_fd_sc_hs"}
    if args.std_cell_library not in allowed_scls:
        raise ValueError(f"--std-cell-library must be one of {sorted(allowed_scls)}")
    if (
        args.load_index_min < 0
        or args.load_index_max > 254
        or args.load_index_min > args.load_index_max
    ):
        raise ValueError("--load-index-min/max must define a valid range within 0..254")

    results = []
    work_items = [
        (corner, coarse_code, code)
        for corner in corners
        for coarse_code in coarse_codes
        for code in codes
    ]
    if args.jobs == 1:
        for corner, coarse_code, code in work_items:
            result = run_one(code, coarse_code, corner, args, build_dir)
            results.append(result)
            print_result(result)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
            futures = {
                executor.submit(run_one, code, coarse_code, corner, args, build_dir): (corner, coarse_code, code)
                for corner, coarse_code, code in work_items
            }
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                results.append(result)
                print_result(result)

    corner_order = {corner: index for index, corner in enumerate(corners)}
    results.sort(
        key=lambda row: (
            corner_order.get(row["corner"], 999),
            int(row.get("coarse_code") or 0),
            row["code"],
        )
    )

    csv_path = build_dir / "dco_sweep.csv"
    with csv_path.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "corner",
                "topology",
                "std_cell_library",
                "coarse_code",
                "selected_tap",
                "code",
                "therm_invert",
                "enabled_loads",
                "ring_stages",
                "mirror_segments",
                "meas_start_ns",
                "load_index_min",
                "load_index_max",
                "load_control_map",
                "logic_drive",
                "turn_drive",
                "output_buffer_drives",
                "load_drive",
                "fixed_delay_cells",
                "status",
                "period_s",
                "freq_hz",
                "freq_mhz",
                "high_time_s",
                "low_time_s",
                "duty_ratio",
                "rise_time_s",
                "fall_time_s",
                "netlist",
                "log",
                "resumed",
            ],
        )
        writer.writeheader()
        writer.writerows(results)

    passed = [row for row in results if row["status"] == "pass"]
    failed = [row for row in results if row["status"] != "pass"]
    print(f"wrote {csv_path}")

    if failed:
        print(f"{len(failed)} ngspice runs failed", file=sys.stderr)
        return 1

    if len(passed) >= 2:
        freqs = [float(row["freq_hz"]) for row in passed]
        print(
            "validated frequency span: "
            f"{min(freqs) / 1e6:.3f} MHz to {max(freqs) / 1e6:.3f} MHz"
        )

        monotonic_errors = monotonic_failures(passed, args.therm_invert)
        if monotonic_errors:
            for corner, coarse_code, code_a, freq_a, code_b, freq_b, relation in monotonic_errors:
                print(
                    f"nonmonotonic {corner} coarse={coarse_code}: expected frequency to {relation} "
                    f"from code {code_a} ({freq_a / 1e6:.3f} MHz) "
                    f"to code {code_b} ({freq_b / 1e6:.3f} MHz)",
                    file=sys.stderr,
                )
            return 1
        if args.therm_invert:
            print("validated monotonic polarity: increasing code increases frequency")
        else:
            print("validated monotonic polarity: increasing code decreases frequency")

        if len(corners) > 1:
            for corner in corners:
                corner_rows = [
                    row
                    for row in passed
                    if row["corner"] == corner and row["freq_hz"]
                ]
                if corner_rows:
                    corner_freqs = [float(row["freq_hz"]) for row in corner_rows]
                    print(
                        f"{corner} span: "
                        f"{min(corner_freqs) / 1e6:.3f} MHz to "
                        f"{max(corner_freqs) / 1e6:.3f} MHz"
                    )

    return 0


def print_result(result):
    prefix = "resumed " if result.get("resumed") else ""
    coarse_text = ""
    if result.get("topology") == "mirror-coarse":
        coarse_text = (
            f" coarse={int(result['coarse_code']):2d}"
            f" turn=C{int(result['selected_tap']):02d}"
        )
    if result["status"] == "pass":
        print(
            f"{prefix}corner={result['corner']} code={int(result['code']):3d} "
            f"{coarse_text} "
            f"loads={result['enabled_loads']:3d} "
            f"freq={result['freq_mhz']:.3f} MHz "
            f"period={float(result['period_s']) * 1e9:.3f} ns "
            f"duty={float(result['duty_ratio']) * 100.0:.1f}% "
            f"tr={float(result['rise_time_s']) * 1e12:.1f} ps "
            f"tf={float(result['fall_time_s']) * 1e12:.1f} ps",
            flush=True,
        )
    else:
        print(
            f"{prefix}corner={result['corner']} code={int(result['code']):3d} "
            f"{coarse_text} "
            f"failed; see {result['log']}",
            flush=True,
        )


if __name__ == "__main__":
    sys.exit(main())
