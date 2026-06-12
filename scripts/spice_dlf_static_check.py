#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from spice_dlf_update_check import (
    bit_net,
    extract_cone,
    input_pins,
    parse_instances,
    parse_subckt_ports,
    parse_timeout,
    sanitize_net,
    source_bit_lines,
    spice_instance_lines,
)


SUPPLY_NETS = {
    "VPWR": "VPWR",
    "VPB": "VPWR",
    "VGND": "VGND",
    "VNB": "VGND",
}

CASES = {
    "hold_mid": {
        "bbpd": 0b00,
        "start_dlf": 512,
        "direction": 0,
    },
    "inc_mid": {
        "bbpd": 0b10,
        "start_dlf": 512,
        "direction": 1,
    },
    "dec_mid": {
        "bbpd": 0b01,
        "start_dlf": 512,
        "direction": -1,
    },
}


def internal_bit_net(prefix, index):
    return sanitize_net(f"\\{prefix} [{index}]")


def integ_acc_net(index):
    return internal_bit_net("loop_filter.integ_acc", index)


def find_next_acc_nets(instances):
    next_nets = {}
    for instance in instances:
        if instance["type"] != "sky130_fd_sc_hd__dfrtp_1":
            continue
        conns = instance["conns"]
        for index in range(19):
            if conns.get("Q") == integ_acc_net(index):
                next_nets[index] = conns.get("D")
    missing = sorted(set(range(19)) - set(next_nets))
    if missing:
        raise ValueError(f"missing mapped DLF accumulator flop D nets: {missing}")
    return next_nets


def parse_cases(text):
    cases = [item.strip() for item in text.split(",") if item.strip()]
    for case_name in cases:
        if case_name not in CASES:
            raise ValueError(f"unknown static DLF case: {case_name}")
    return cases


def parse_bit_list(text, width):
    if not text:
        return []
    bits = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        bit = int(item, 0)
        if bit < 0 or bit >= width:
            raise ValueError(f"bit index out of range 0..{width - 1}: {bit}")
        bits.append(bit)
    return sorted(set(bits))


def sat_acc(value):
    return max(0, min((1023 << 8), value))


def expected_values(case_name, ki, kp):
    case = CASES[case_name]
    start_acc = case["start_dlf"] << 8
    direction = case["direction"]
    prop_acc = sat_acc(start_acc + direction * (kp << 8))
    next_acc = sat_acc(start_acc + direction * ki)
    return {
        "start_acc": start_acc,
        "expected_dco_code": (prop_acc >> 8) >> 2,
        "expected_next_acc": next_acc,
    }


def source_node(name, value):
    return f"V{sanitize_net(name).upper()} {sanitize_net(name)} 0 {'{VDD}' if value else '0'}"


def source_internal_bits(prefix, width, value):
    return [
        f"V{sanitize_net(prefix).upper()}{index} {internal_bit_net(prefix, index)} 0 "
        f"{'{VDD}' if ((value >> index) & 1) else '0'}"
        for index in range(width)
    ]


def run_ngspice(args, netlist_path, build_dir):
    start = time.monotonic()
    env = os.environ.copy()
    if args.ngspice_threads > 0:
        env["OMP_NUM_THREADS"] = str(args.ngspice_threads)
    proc = subprocess.Popen(
        [args.ngspice, "-b", str(netlist_path)],
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
            f"\nOpenPLL timeout: killed ngspice after {args.timeout_s:.1f} s "
            f"for {netlist_path.name}\n"
        )
    return proc.returncode, timed_out, elapsed_s, stdout


def parse_node_voltages(log_text):
    voltages = {}
    in_nodes = False
    for line in log_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("Node") and "Voltage" in stripped:
            in_nodes = True
            continue
        if not in_nodes:
            continue
        if stripped.startswith("Source"):
            break
        if not stripped or stripped.startswith("-"):
            continue
        parts = stripped.split()
        if len(parts) != 2:
            continue
        try:
            voltages[parts[0].lower()] = float(parts[1])
        except ValueError:
            continue
    return voltages


def measured_bits(voltages, nets, threshold):
    value = 0
    missing = []
    raw = {}
    for index, net in nets.items():
        voltage = voltages.get(net.lower())
        raw[index] = voltage
        if voltage is None:
            missing.append(index)
        elif voltage > threshold:
            value |= 1 << index
    return value, missing, raw


def static_netlist(case_name, args, instances, subckt_ports):
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

    expected = expected_values(case_name, args.ki, args.kp)
    case = CASES[case_name]
    lines = [
        f"* OpenPLL synthesized Sky130 DLF static SPICE check, case={case_name}",
        f'.lib "{model_path}" {args.corner}',
        f'.include "{cell_path}"',
        ".option reltol=1e-4 abstol=1e-15 chgtol=1e-16"
        + (f" num_threads={args.ngspice_threads}" if args.ngspice_threads > 0 else ""),
        ".param VDD=1.8",
        "VVPWR VPWR 0 {VDD}",
        "VVGND VGND 0 0",
        source_node("RESET_N", 1),
        source_node("DLF_En", 1),
        source_node("DLF_Clear", 0),
        source_node("DLF_Ext_Override", 0),
        source_node("DLF_IN_POL", 1),
        source_node("PLLOUT", 0),
        source_node("CLKDIV_RETIMED", 0),
        "",
        "* Static DLF inputs and directly driven accumulator/decision state.",
        *source_bit_lines("BBPD", 2, case["bbpd"]),
        *source_bit_lines("bbpd_decision", 2, case["bbpd"]),
        *source_bit_lines("DLF_Ext_Data", 10, case["start_dlf"]),
        *source_bit_lines("DLF_KI", 8, args.ki),
        *source_bit_lines("DLF_KP", 8, args.kp),
        *source_bit_lines("COARSEBINARY_CODE", 4, 5),
        *source_bit_lines("MMDCLKDIV_RATIO", 8, args.mmd_ratio),
        *source_internal_bits("loop_filter.integ_acc", 19, expected["start_acc"]),
        "",
        "* Extracted combinational cone from accumulator/input state to DCO_CODE",
        "* and next accumulator D inputs.",
        *spice_instance_lines(instances, subckt_ports),
        "",
        ".op",
        ".end",
        "",
    ]
    return "\n".join(lines)


def run_one(case_name, args, build_dir, instances, subckt_ports, checked_next_acc_nets):
    netlist_path = build_dir / f"dlf_static_{case_name}.spice"
    log_path = build_dir / f"dlf_static_{case_name}.log"
    netlist_path.write_text(
        static_netlist(case_name, args, instances, subckt_ports),
        encoding="ascii",
    )
    returncode, timed_out, elapsed_s, log_text = run_ngspice(args, netlist_path, build_dir)
    log_path.write_text(log_text, encoding="utf-8")

    voltages = parse_node_voltages(log_text)
    dco_nets = {index: bit_net("DCO_CODE", index) for index in range(8)}
    dco_code, missing_dco, _ = measured_bits(voltages, dco_nets, args.threshold)
    next_acc, missing_acc, _ = measured_bits(voltages, checked_next_acc_nets, args.threshold)
    expected = expected_values(case_name, args.ki, args.kp)
    expected_next_acc = ""
    if checked_next_acc_nets:
        mask = sum(1 << bit for bit in checked_next_acc_nets)
        expected_next_acc = expected["expected_next_acc"] & mask
    ok = (
        returncode == 0
        and not timed_out
        and not missing_dco
        and dco_code == expected["expected_dco_code"]
        and (
            not checked_next_acc_nets
            or (not missing_acc and next_acc == expected_next_acc)
        )
    )
    return {
        "case": case_name,
        "status": "pass" if ok else "fail",
        "ki": args.ki,
        "kp": args.kp,
        "start_acc": expected["start_acc"],
        "expected_dco_code": expected["expected_dco_code"],
        "measured_dco_code": "" if missing_dco else dco_code,
        "checked_next_acc_bits": ",".join(str(bit) for bit in checked_next_acc_nets),
        "expected_next_acc": expected_next_acc,
        "measured_next_acc": "" if missing_acc or not checked_next_acc_nets else next_acc,
        "missing_dco_bits": ",".join(str(bit) for bit in missing_dco),
        "missing_next_acc_bits": ",".join(str(bit) for bit in missing_acc),
        "returncode": returncode,
        "timed_out": "yes" if timed_out else "no",
        "elapsed_s": f"{elapsed_s:.3f}",
        "netlist": str(netlist_path),
        "log": str(log_path),
    }


def main():
    root_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Run static SPICE checks for the synthesized Sky130 DLF update cone."
    )
    parser.add_argument("--cases", default="hold_mid,inc_mid,dec_mid")
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
    parser.add_argument(
        "--next-acc-bits",
        default="",
        help="Optional comma-separated mapped accumulator D-input bits to check.",
    )
    parser.add_argument("--mmd-ratio", type=int, default=2)
    parser.add_argument("--threshold", type=float, default=0.9)
    parser.add_argument("--timeout-s", default="60")
    parser.add_argument("--ngspice", default=shutil.which("ngspice") or "ngspice")
    parser.add_argument(
        "--ngspice-threads",
        type=int,
        default=int(os.environ.get("NGSPICE_THREADS", "0")),
        help="Set ngspice OpenMP threads via .option num_threads and OMP_NUM_THREADS; 0 leaves default.",
    )
    parser.add_argument(
        "--build-dir",
        default=str(root_dir / "build" / "spice_dlf_static"),
    )
    args = parser.parse_args()
    args.timeout_s = parse_timeout(args.timeout_s)
    if args.ki < 0 or args.ki > 255 or args.kp < 0 or args.kp > 255:
        raise ValueError("--ki and --kp must be 8-bit values")
    if args.mmd_ratio < 2 or args.mmd_ratio > 255:
        raise ValueError("--mmd-ratio must be in 2..255")
    if args.ngspice_threads < 0:
        raise ValueError("--ngspice-threads must be non-negative")
    checked_next_bits = parse_bit_list(args.next_acc_bits, 19)

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

    next_acc_nets = find_next_acc_nets(all_instances)
    checked_next_acc_nets = {
        bit: next_acc_nets[bit]
        for bit in checked_next_bits
    }
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
        | {bit_net("bbpd_decision", index) for index in range(2)}
        | {bit_net("DLF_Ext_Data", index) for index in range(10)}
        | {bit_net("DLF_KI", index) for index in range(8)}
        | {bit_net("DLF_KP", index) for index in range(8)}
        | {bit_net("MMDCLKDIV_RATIO", index) for index in range(8)}
        | {bit_net("COARSEBINARY_CODE", index) for index in range(4)}
        | {integ_acc_net(index) for index in range(19)}
    )
    output_nets = (
        {bit_net("DCO_CODE", index) for index in range(8)}
        | set(checked_next_acc_nets.values())
    )
    instances = extract_cone(all_instances, output_nets, input_nets)
    print(
        f"extracted {len(instances)} static DLF cone cells from "
        f"{len(all_instances)} mapped digital-core cells",
        flush=True,
    )

    build_dir = Path(args.build_dir).expanduser().resolve()
    build_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        run_one(case_name, args, build_dir, instances, subckt_ports, checked_next_acc_nets)
        for case_name in parse_cases(args.cases)
    ]

    csv_path = build_dir / "dlf_static_check.csv"
    with csv_path.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    for row in rows:
        print(
            f"case={row['case']} status={row['status']} "
            f"dco={row['measured_dco_code']}/{row['expected_dco_code']} "
            f"next_acc={row['measured_next_acc']}/{row['expected_next_acc']} "
            f"elapsed_s={row['elapsed_s']}"
        )
    print(f"wrote {csv_path}")

    failed = [row for row in rows if row["status"] != "pass"]
    if failed:
        print(f"{len(failed)} static DLF SPICE checks failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
