#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import concurrent.futures
import csv
import json
import os
import shutil
import subprocess
import time
import re
from pathlib import Path

from sky130_pdk import default_pdk_root
from xyce_utils import add_xyce_arguments, validate_xyce_arguments, xyce_simulator_command


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


def parse_coarse_codes(text):
    codes = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        code = int(item, 0)
        if code < 0 or code > 63:
            raise ValueError(f"coarse code out of mirror-turn range: {code}")
        codes.append(code)
    return codes


def coarse_thermal_bits_for_turn(coarse_code, width):
    if coarse_code < 0 or coarse_code > width:
        raise ValueError(
            f"coarse mirror turn {coarse_code} is not representable by "
            f"COARSETHERMAL_CODE[{width - 1}:0]"
        )
    bits = [False] * width
    for bit in range(width):
        bits[bit] = bit < coarse_code
    return bits


def enabled_load_count(code, therm_invert):
    count = 0
    for idx in range(255):
        active = idx < code
        if therm_invert:
            active = not active
        if active:
            count += 1
    return count


def measure_value(log_text, name):
    for pattern in (
        rf"^\s*{name}\s*=\s*{RE_FLOAT}",
        rf"^\s*{name}\s*:\s*{RE_FLOAT}",
    ):
        match = re.search(pattern, log_text, re.IGNORECASE | re.MULTILINE)
        if match:
            return float(match.group(1))
    return None


def xyce_output_base(netlist_path):
    return netlist_path.with_suffix("")


def xyce_waveform_path(netlist_path):
    return Path(f"{xyce_output_base(netlist_path)}.prn")


def crossing_period_freq(waveform_path, meas_start_ns, threshold=0.9):
    metrics = crossing_waveform_metrics(waveform_path, meas_start_ns, threshold)
    return metrics["period_s"], metrics["freq_hz"]


def read_waveform_points(waveform_path):
    if not waveform_path.exists():
        return []

    points = []
    for line in waveform_path.read_text(encoding="utf-8", errors="replace").splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        try:
            if len(parts) >= 3:
                time_s = float(parts[1])
                value = float(parts[2])
            else:
                time_s = float(parts[0])
                value = float(parts[1])
        except ValueError:
            continue
        points.append((time_s, value))
    return points


def threshold_crossings(points, threshold, direction, meas_start_s):
    prev_time = None
    prev_value = None
    crossings = []
    for time_s, value in points:
        if (
            prev_time is not None
            and prev_value is not None
            and (
                (direction == "rise" and prev_value < threshold and value >= threshold)
                or (direction == "fall" and prev_value > threshold and value <= threshold)
            )
        ):
            slope = value - prev_value
            if slope != 0:
                frac = (threshold - prev_value) / slope
                crossing_s = prev_time + frac * (time_s - prev_time)
                if crossing_s >= meas_start_s:
                    crossings.append(crossing_s)
        prev_time = time_s
        prev_value = value
    return crossings


def crossing_waveform_metrics(waveform_path, meas_start_ns, mid_threshold=0.9):
    points = read_waveform_points(waveform_path)
    metrics = {
        "period_s": None,
        "freq_hz": None,
        "high_time_s": None,
        "low_time_s": None,
        "duty_ratio": None,
        "rise_time_s": None,
        "fall_time_s": None,
    }
    if not points:
        return metrics

    meas_start_s = meas_start_ns * 1.0e-9
    rises_mid = threshold_crossings(points, mid_threshold, "rise", meas_start_s)
    falls_mid = threshold_crossings(points, mid_threshold, "fall", meas_start_s)
    rises_20 = threshold_crossings(points, 0.36, "rise", meas_start_s)
    rises_80 = threshold_crossings(points, 1.44, "rise", meas_start_s)
    falls_80 = threshold_crossings(points, 1.44, "fall", meas_start_s)
    falls_20 = threshold_crossings(points, 0.36, "fall", meas_start_s)

    if len(rises_mid) >= 3:
        period_s = (rises_mid[2] - rises_mid[0]) / 2.0
        if period_s > 0:
            metrics["period_s"] = period_s
            metrics["freq_hz"] = 1.0 / period_s
    if len(rises_mid) >= 2 and falls_mid:
        for rise_a, rise_b in zip(rises_mid, rises_mid[1:]):
            fall = next((item for item in falls_mid if rise_a < item < rise_b), None)
            if fall is None:
                continue
            high_time = fall - rise_a
            low_time = rise_b - fall
            if high_time > 0 and low_time > 0:
                metrics["high_time_s"] = high_time
                metrics["low_time_s"] = low_time
                metrics["duty_ratio"] = high_time / (high_time + low_time)
                break
    for lo in rises_20:
        hi = next((item for item in rises_80 if item > lo), None)
        if hi is not None:
            metrics["rise_time_s"] = hi - lo
            break
    for hi in falls_80:
        lo = next((item for item in falls_20 if item > hi), None)
        if lo is not None:
            metrics["fall_time_s"] = lo - hi
            break
    return metrics


def waveform_values_from_log(log_text, period):
    high_candidates = [
        measure_value(log_text, "high_time_same_s"),
        measure_value(log_text, "high_time_next_s"),
    ]
    low_candidates = [
        measure_value(log_text, "low_time_same_s"),
        measure_value(log_text, "low_time_next_s"),
    ]
    rise_candidates = [
        measure_value(log_text, "rise_time_same_s"),
        measure_value(log_text, "rise_time_offset_s"),
    ]
    fall_candidates = [
        measure_value(log_text, "fall_time_same_s"),
        measure_value(log_text, "fall_time_offset_s"),
    ]

    def first_positive(values):
        for value in values:
            if value is not None and value > 0.0:
                return value
        return None

    high_time = first_positive(
        value for value in high_candidates if period is None or value is None or value <= period
    )
    low_time = first_positive(
        value for value in low_candidates if period is None or value is None or value <= period
    )
    rise_time = first_positive(rise_candidates)
    fall_time = first_positive(fall_candidates)
    duty_ratio = None
    if high_time is not None and low_time is not None and high_time + low_time > 0:
        duty_ratio = high_time / (high_time + low_time)
    return {
        "high_time_s": high_time,
        "low_time_s": low_time,
        "duty_ratio": duty_ratio,
        "rise_time_s": rise_time,
        "fall_time_s": fall_time,
    }


def parse_subckt_ports(rcx_netlist, subckt_name):
    lines = Path(rcx_netlist).read_text(encoding="utf-8", errors="replace").splitlines()
    header = []
    in_header = False
    for line in lines:
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
        raise ValueError(f"subckt {subckt_name!r} not found in {rcx_netlist}")

    tokens = []
    for idx, line in enumerate(header):
        if idx == 0:
            tokens.extend(line.split()[2:])
        else:
            tokens.extend(line[1:].split())
    return tokens


def wrapped_instance(name, ports, subckt_name, width=8):
    tokens = list(ports) + [subckt_name]
    lines = [f"{name} " + " ".join(tokens[:width])]
    for idx in range(width, len(tokens), width):
        lines.append("+ " + " ".join(tokens[idx : idx + width]))
    return lines


def dco_netlist(args, code, coarse_code, ports):
    pdk_root = Path(args.pdk_root).expanduser().resolve()
    model_path = pdk_root / args.pdk / "libs.tech" / "ngspice" / "sky130.lib.spice"
    rcx_path = Path(args.rcx_netlist).expanduser().resolve()
    if not model_path.exists():
        raise FileNotFoundError(model_path)
    if not rcx_path.exists():
        raise FileNotFoundError(rcx_path)

    lines = [
        f"* OpenPLL DCO post-layout transient, code={code}, coarse_code={coarse_code}",
        f"* simulator={args.simulator}",
        f"* therm_invert={int(args.therm_invert)}, enabled_loads={enabled_load_count(code, args.therm_invert)}",
        f"* coarse_code={coarse_code}",
        f"* RCX netlist: {rcx_path}",
        f"* subckt_name={args.subckt_name}",
        f'.lib "{model_path}" {args.corner}',
        f'.include "{rcx_path}"',
        ".param VDD=1.8",
        "VVPWR VPWR 0 {VDD}",
        "VVPB VPB 0 {VDD}",
        "VVGND VGND 0 0",
        "VVNB VNB 0 0",
        f"VRESET RESET_N 0 PULSE(0 {{VDD}} {args.reset_release_ns}n 50p 50p {args.sim_time_ns}n {2 * args.sim_time_ns}n)",
    ]
    if args.simulator == "ngspice":
        lines.insert(
            5,
            ".option method=gear reltol=1e-3 abstol=1e-15 chgtol=1e-16"
            + (
                f" num_threads={args.ngspice_threads}"
                if args.ngspice_threads > 0
                else ""
            ),
        )

    seen = set()
    for port in ports:
        match = re.fullmatch(r"DCO_THERM\[(\d+)\]", port)
        if not match:
            continue
        idx = int(match.group(1))
        if idx in seen:
            continue
        seen.add(idx)
        active = idx < code
        if args.therm_invert:
            active = not active
        value = "{VDD}" if active else "0"
        lines.append(f"VCTRL{idx:03d} {port} 0 {value}")

    seen_coarse = set()
    coarse_binary_width = max(
        (
            int(match.group(1)) + 1
            for port in ports
            for match in [re.fullmatch(r"COARSEBINARY_CODE\[(\d+)\]", port)]
            if match
        ),
        default=0,
    )
    for port in ports:
        match = re.fullmatch(r"COARSEBINARY_CODE\[(\d+)\]", port)
        if not match:
            continue
        idx = int(match.group(1))
        if idx in seen_coarse:
            continue
        seen_coarse.add(idx)
        if idx >= coarse_binary_width:
            raise ValueError(f"unsupported coarse port index: {port}")
        value = "{VDD}" if ((coarse_code >> idx) & 1) else "0"
        lines.append(f"VCOARSE{idx} {port} 0 {value}")

    coarse_thermal_width = max(
        (
            int(match.group(1)) + 1
            for port in ports
            for match in [re.fullmatch(r"COARSETHERMAL_CODE\[(\d+)\]", port)]
            if match
        ),
        default=0,
    )
    coarse_thermal_bits = (
        coarse_thermal_bits_for_turn(coarse_code, coarse_thermal_width)
        if coarse_thermal_width
        else []
    )
    seen_coarse_thermal = set()
    for port in ports:
        match = re.fullmatch(r"COARSETHERMAL_CODE\[(\d+)\]", port)
        if not match:
            continue
        idx = int(match.group(1))
        if idx in seen_coarse_thermal:
            continue
        seen_coarse_thermal.add(idx)
        if idx >= coarse_thermal_width:
            raise ValueError(f"unsupported coarse thermal port index: {port}")
        value = "{VDD}" if coarse_thermal_bits[idx] else "0"
        lines.append(f"VCOARSETHERM{idx:02d} {port} 0 {value}")

    lines.extend(
        [
            "",
            "* The reset pulse puts the extracted odd-inverter loop into a known",
            "* state before it is released for free-running oscillation.",
            *wrapped_instance("XDUT", ports, args.subckt_name),
            "",
        ]
    )
    if args.simulator == "ngspice":
        lines.append(".save v(PLLOUT)")
    else:
        lines.append(".print tran v(PLLOUT)")
    lines.extend(
        [
            f".tran {args.step_ps}p {args.sim_time_ns}n",
            f".meas tran two_cycle_s TRIG v(PLLOUT) VAL=0.9 TD={args.meas_start_ns}n RISE=1 "
            f"TARG v(PLLOUT) VAL=0.9 TD={args.meas_start_ns}n RISE=3",
            ".meas tran period_s PARAM='two_cycle_s/2'",
            ".meas tran freq_hz PARAM='1/period_s'",
            f".meas tran high_time_same_s TRIG v(PLLOUT) VAL=0.9 TD={args.meas_start_ns}n RISE=2 "
            f"TARG v(PLLOUT) VAL=0.9 TD={args.meas_start_ns}n FALL=2",
            f".meas tran high_time_next_s TRIG v(PLLOUT) VAL=0.9 TD={args.meas_start_ns}n RISE=2 "
            f"TARG v(PLLOUT) VAL=0.9 TD={args.meas_start_ns}n FALL=3",
            f".meas tran low_time_same_s TRIG v(PLLOUT) VAL=0.9 TD={args.meas_start_ns}n FALL=2 "
            f"TARG v(PLLOUT) VAL=0.9 TD={args.meas_start_ns}n RISE=2",
            f".meas tran low_time_next_s TRIG v(PLLOUT) VAL=0.9 TD={args.meas_start_ns}n FALL=2 "
            f"TARG v(PLLOUT) VAL=0.9 TD={args.meas_start_ns}n RISE=3",
            f".meas tran rise_time_same_s TRIG v(PLLOUT) VAL=0.36 TD={args.meas_start_ns}n RISE=2 "
            f"TARG v(PLLOUT) VAL=1.44 TD={args.meas_start_ns}n RISE=2",
            f".meas tran rise_time_offset_s TRIG v(PLLOUT) VAL=0.36 TD={args.meas_start_ns}n RISE=3 "
            f"TARG v(PLLOUT) VAL=1.44 TD={args.meas_start_ns}n RISE=2",
            f".meas tran fall_time_same_s TRIG v(PLLOUT) VAL=1.44 TD={args.meas_start_ns}n FALL=2 "
            f"TARG v(PLLOUT) VAL=0.36 TD={args.meas_start_ns}n FALL=2",
            f".meas tran fall_time_offset_s TRIG v(PLLOUT) VAL=1.44 TD={args.meas_start_ns}n FALL=1 "
            f"TARG v(PLLOUT) VAL=0.36 TD={args.meas_start_ns}n FALL=2",
            ".end",
            "",
        ]
    )
    return "\n".join(lines)


def simulator_command(args, netlist_path):
    if args.simulator == "ngspice":
        return [args.ngspice, "-b", str(netlist_path)]
    if args.simulator == "xyce":
        return xyce_simulator_command(args, netlist_path, xyce_output_base(netlist_path))
    raise ValueError(f"unsupported simulator: {args.simulator}")


def run_spice(args, netlist_path, log_path, build_dir):
    start = time.monotonic()
    env = os.environ.copy()
    if args.simulator == "ngspice" and args.ngspice_threads > 0:
        env["OMP_NUM_THREADS"] = str(args.ngspice_threads)
    model_dir = (
        Path(args.pdk_root).expanduser().resolve()
        / args.pdk
        / "libs.tech"
        / "ngspice"
    )
    proc = subprocess.Popen(
        simulator_command(args, netlist_path),
        cwd=model_dir,
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
    log_path.write_text(stdout, encoding="utf-8")
    return proc.returncode, timed_out, elapsed_s, stdout


def row_from_log(
    args,
    code,
    coarse_code,
    netlist_path,
    log_path,
    log_text,
    returncode,
    timed_out,
    elapsed_s,
    resumed,
):
    waveform_path = ""
    if args.simulator == "xyce":
        waveform_path = str(xyce_waveform_path(netlist_path))
        waveform_metrics = crossing_waveform_metrics(
            xyce_waveform_path(netlist_path), args.meas_start_ns
        )
        period = waveform_metrics["period_s"]
        freq = waveform_metrics["freq_hz"]
    else:
        period = measure_value(log_text, "period_s")
        freq = measure_value(log_text, "freq_hz")
        waveform_metrics = waveform_values_from_log(log_text, period)
    ok = (
        returncode == 0
        and not timed_out
        and period is not None
        and period > 0.0
        and freq is not None
        and freq > 0.0
        and waveform_metrics["high_time_s"] is not None
        and waveform_metrics["low_time_s"] is not None
        and waveform_metrics["duty_ratio"] is not None
        and waveform_metrics["rise_time_s"] is not None
        and waveform_metrics["fall_time_s"] is not None
    )
    return {
        "simulator": args.simulator,
        "xyce_mpi_procs": args.xyce_mpi_procs if args.simulator == "xyce" else "",
        "corner": args.corner,
        "subckt_name": args.subckt_name,
        "coarse_code": coarse_code,
        "code": code,
        "therm_invert": int(args.therm_invert),
        "enabled_loads": enabled_load_count(code, args.therm_invert),
        "status": "pass" if ok else "fail",
        "returncode": returncode,
        "timed_out": "yes" if timed_out else "no",
        "elapsed_s": f"{elapsed_s:.3f}" if elapsed_s is not None else "",
        "resumed": "yes" if resumed else "no",
        "period_s": period or "",
        "freq_hz": freq or "",
        "freq_mhz": (freq / 1.0e6) if freq else "",
        "high_time_s": waveform_metrics["high_time_s"] or "",
        "low_time_s": waveform_metrics["low_time_s"] or "",
        "duty_ratio": waveform_metrics["duty_ratio"] or "",
        "rise_time_s": waveform_metrics["rise_time_s"] or "",
        "fall_time_s": waveform_metrics["fall_time_s"] or "",
        "netlist": str(netlist_path),
        "log": str(log_path),
        "waveform": waveform_path,
    }


def can_resume(args, netlist_path, log_path, netlist_text):
    if not args.resume or not netlist_path.exists() or not log_path.exists():
        return False
    old_netlist = netlist_path.read_text(encoding="ascii", errors="replace")
    return old_netlist == netlist_text


def run_one(code, coarse_code, args, ports, build_dir):
    netlist_path = (
        build_dir
        / f"dco_postlayout_{args.corner}_coarse_{coarse_code:02d}_code_{code:03d}.spice"
    )
    log_path = (
        build_dir
        / f"dco_postlayout_{args.corner}_coarse_{coarse_code:02d}_code_{code:03d}.log"
    )
    netlist_text = dco_netlist(args, code, coarse_code, ports)
    if can_resume(args, netlist_path, log_path, netlist_text):
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        row = row_from_log(
            args, code, coarse_code, netlist_path, log_path, log_text, 0, False, None, True
        )
        if row["status"] == "pass":
            return row

    netlist_path.write_text(netlist_text, encoding="ascii")
    returncode, timed_out, elapsed_s, log_text = run_spice(
        args, netlist_path, log_path, build_dir
    )
    return row_from_log(
        args,
        code,
        coarse_code,
        netlist_path,
        log_path,
        log_text,
        returncode,
        timed_out,
        elapsed_s,
        False,
    )


def parse_timeout(value):
    if value in (None, "", "none"):
        return None
    timeout = float(value)
    if timeout <= 0:
        raise ValueError("--timeout-s must be positive or 'none'")
    return timeout


def main():
    parser = argparse.ArgumentParser(description="Run DCO post-layout RCX transient SPICE.")
    parser.add_argument("--codes", default="0,128,255")
    parser.add_argument("--coarse-codes", default="0")
    parser.add_argument("--corner", default="tt")
    parser.add_argument("--pdk-root", default=default_pdk_root())
    parser.add_argument("--pdk", default="sky130A")
    parser.add_argument(
        "--rcx-netlist",
        default="openlane/IntegerPLL_DCO/runs/librelane_signoff/rcx-magic/IntegerPLL_DCO.rcx.spice",
    )
    parser.add_argument(
        "--subckt-name",
        default="IntegerPLL_DCO",
        help="Name of the extracted DCO subckt to instantiate from --rcx-netlist.",
    )
    parser.add_argument("--build-dir", default="build/spice_dco_postlayout")
    parser.add_argument("--sim-time-ns", type=float, default=200.0)
    parser.add_argument("--reset-release-ns", type=float, default=5.0)
    parser.add_argument("--meas-start-ns", type=float, default=20.0)
    parser.add_argument("--step-ps", type=float, default=20.0)
    parser.add_argument(
        "--timeout-s",
        default="none",
        help="Per-simulation wall-clock timeout in seconds, or 'none'.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse an existing matching passing netlist/log in the build directory.",
    )
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument(
        "--ngspice-threads",
        type=int,
        default=int(os.environ.get("NGSPICE_THREADS", "0")),
        help="Set ngspice OpenMP threads via .option num_threads and OMP_NUM_THREADS; 0 leaves default.",
    )
    parser.add_argument(
        "--therm-invert",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use the RTL top-level inverted thermometer polarity by default.",
    )
    parser.add_argument(
        "--simulator",
        choices=("ngspice", "xyce"),
        default="ngspice",
        help="Circuit simulator for the generated post-layout deck.",
    )
    parser.add_argument("--ngspice", default=shutil.which("ngspice") or "ngspice")
    add_xyce_arguments(parser)
    args = parser.parse_args()
    args.timeout_s = parse_timeout(args.timeout_s)
    if args.ngspice_threads < 0:
        raise ValueError("--ngspice-threads must be non-negative")
    validate_xyce_arguments(args)

    codes = parse_codes(args.codes)
    coarse_codes = parse_coarse_codes(args.coarse_codes)
    ports = parse_subckt_ports(args.rcx_netlist, args.subckt_name)
    if len([port for port in ports if port.startswith("DCO_THERM[")]) != 255:
        raise ValueError("RCX netlist does not expose all 255 thermometer ports")
    coarse_ports = [port for port in ports if port.startswith("COARSEBINARY_CODE[")]
    coarse_thermal_ports = [
        port for port in ports if port.startswith("COARSETHERMAL_CODE[")
    ]
    coarse_width = 0
    if coarse_ports:
        coarse_indices = sorted(
            int(re.fullmatch(r"COARSEBINARY_CODE\[(\d+)\]", port).group(1))
            for port in coarse_ports
        )
        if coarse_indices != list(range(coarse_indices[-1] + 1)):
            raise ValueError("RCX netlist exposes a partial coarse-code bus")
        coarse_width = coarse_indices[-1] + 1
    coarse_thermal_width = 0
    if coarse_thermal_ports:
        coarse_thermal_indices = sorted(
            int(re.fullmatch(r"COARSETHERMAL_CODE\[(\d+)\]", port).group(1))
            for port in coarse_thermal_ports
        )
        if coarse_thermal_indices != list(range(coarse_thermal_indices[-1] + 1)):
            raise ValueError("RCX netlist exposes a partial coarse-thermal bus")
        coarse_thermal_width = coarse_thermal_indices[-1] + 1
        for code in coarse_codes:
            coarse_thermal_bits_for_turn(code, coarse_thermal_width)
    if coarse_ports and any(code >= (1 << coarse_width) for code in coarse_codes):
        raise ValueError(
            f"COARSEBINARY_CODE ports only support coarse codes 0..{(1 << coarse_width) - 1}"
        )
    if not coarse_ports and not coarse_thermal_ports and any(code != 0 for code in coarse_codes):
        raise ValueError(
            "--coarse-codes requires COARSEBINARY_CODE or COARSETHERMAL_CODE ports "
            "in the RCX netlist"
        )

    build_dir = Path(args.build_dir).resolve()
    build_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        futures = [
            executor.submit(run_one, code, coarse_code, args, ports, build_dir)
            for coarse_code in coarse_codes
            for code in codes
        ]
        for future in concurrent.futures.as_completed(futures):
            rows.append(future.result())

    rows.sort(key=lambda row: (row["coarse_code"], row["code"]))
    csv_path = build_dir / "dco_postlayout_results.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "simulator": args.simulator,
        "rows": len(rows),
        "bad_rows": sum(1 for row in rows if row["status"] != "pass"),
        "results_csv": str(csv_path),
        "rcx_netlist": str(Path(args.rcx_netlist).resolve()),
        "subckt_name": args.subckt_name,
        "coarse_codes": coarse_codes,
    }
    print(json.dumps(summary, indent=2))
    for row in rows:
        print(
            f"{row['status']:>4} {row['simulator']} "
            f"coarse={row['coarse_code']:2d} code={row['code']:3d} "
            f"enabled_loads={row['enabled_loads']:3d} "
            f"freq_mhz={row['freq_mhz'] if row['freq_mhz'] != '' else 'NA'} "
            f"duty={row['duty_ratio'] if row['duty_ratio'] != '' else 'NA'} "
            f"rise_s={row['rise_time_s'] if row['rise_time_s'] != '' else 'NA'} "
            f"fall_s={row['fall_time_s'] if row['fall_time_s'] != '' else 'NA'} "
            f"timeout={row['timed_out']} elapsed_s={row['elapsed_s']} "
            f"resumed={row['resumed']}"
        )

    if summary["bad_rows"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
