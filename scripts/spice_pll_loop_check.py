#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import time
from argparse import Namespace
from pathlib import Path

from sky130_pdk import default_pdk_root
from xyce_utils import add_xyce_arguments, validate_xyce_arguments, xyce_simulator_command


RE_FLOAT = r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"


CASES = {
    "low_start": {
        "initial_code": 0.0,
        "expected_direction": "increase",
    },
    "high_start": {
        "initial_code": 255.0,
        "expected_direction": "decrease",
    },
}


def dco_points_mhz(args):
    coarse_offset_mhz = args.coarse_code * args.dco_coarse_step_mhz
    if args.dco_model == "linear":
        return [
            (0.0, args.fmin_mhz + coarse_offset_mhz),
            (255.0, args.fmax_mhz + coarse_offset_mhz),
        ]
    if args.dco_model == "piecewise3":
        return [
            (0.0, args.f0_mhz + coarse_offset_mhz),
            (128.0, args.f128_mhz + coarse_offset_mhz),
            (255.0, args.f255_mhz + coarse_offset_mhz),
        ]
    return [
        (0.0, args.f0_mhz + coarse_offset_mhz),
        (64.0, args.f64_mhz + coarse_offset_mhz),
        (128.0, args.f128_mhz + coarse_offset_mhz),
        (192.0, args.f192_mhz + coarse_offset_mhz),
        (255.0, args.f255_mhz + coarse_offset_mhz),
    ]


def dco_freq_mhz_at_code(args, code):
    points = dco_points_mhz(args)
    if code <= points[0][0]:
        return points[0][1]
    for (code0, freq0), (code1, freq1) in zip(points, points[1:]):
        if code <= code1:
            return freq0 + (freq1 - freq0) * (code - code0) / (code1 - code0)
    return points[-1][1]


def dco_target_code(args, target_mhz):
    points = dco_points_mhz(args)
    target_code = None
    for (code0, freq0), (code1, freq1) in zip(points, points[1:]):
        if freq0 <= target_mhz <= freq1:
            target_code = code0 + (code1 - code0) * (target_mhz - freq0) / (freq1 - freq0)
            break

    if target_code is None or target_code < 0.0 or target_code > 255.0:
        raise ValueError(
            f"target {target_mhz:.6g} MHz is outside DCO range "
            f"{points[0][1]:.6g}..{points[-1][1]:.6g} MHz"
        )
    return target_code


def case_initial_dco_phase_cycles(case_name, args):
    if case_name == "low_start" and args.low_start_initial_dco_phase_cycles is not None:
        return args.low_start_initial_dco_phase_cycles
    if case_name == "high_start" and args.high_start_initial_dco_phase_cycles is not None:
        return args.high_start_initial_dco_phase_cycles
    return args.initial_dco_phase_cycles


def normalize_dco_model(args):
    if args.dco_model == "linear":
        if args.fmax_mhz <= args.fmin_mhz:
            raise ValueError("--fmax-mhz must be greater than --fmin-mhz")
        args.f0_mhz = args.fmin_mhz
        args.f64_mhz = args.fmin_mhz + (args.fmax_mhz - args.fmin_mhz) * 64.0 / 255.0
        args.f128_mhz = args.fmin_mhz + (args.fmax_mhz - args.fmin_mhz) * 128.0 / 255.0
        args.f192_mhz = args.fmin_mhz + (args.fmax_mhz - args.fmin_mhz) * 192.0 / 255.0
        args.f255_mhz = args.fmax_mhz
        return args

    required_names = ("f0_mhz", "f128_mhz", "f255_mhz")
    if args.dco_model == "piecewise5":
        required_names = ("f0_mhz", "f64_mhz", "f128_mhz", "f192_mhz", "f255_mhz")
    missing = [
        name
        for name in required_names
        if getattr(args, name) is None
    ]
    if missing:
        flags = ", ".join("--" + name.replace("_", "-") for name in missing)
        raise ValueError(f"--dco-model {args.dco_model} requires {flags}")
    if args.dco_model == "piecewise3":
        args.f64_mhz = args.f0_mhz + (args.f128_mhz - args.f0_mhz) * 64.0 / 128.0
        args.f192_mhz = args.f128_mhz + (args.f255_mhz - args.f128_mhz) * 64.0 / 127.0
    points = dco_points_mhz(args)
    for (code0, freq0), (code1, freq1) in zip(points, points[1:]):
        if freq1 <= freq0:
            raise ValueError(
                f"DCO calibration must be monotonic increasing: code {code0:g} "
                f"has {freq0:g} MHz, code {code1:g} has {freq1:g} MHz"
            )
    args.fmin_mhz = args.f0_mhz
    args.fmax_mhz = args.f255_mhz
    return args


def dco_model_lines(args):
    lines = ["BCODE CODE 0 V={min(255,max(0,v(CODE_DRIVE)))}"]
    if args.dco_model == "linear":
        lines.append(
            "BDCO_FREQ_HZ DCO_FREQ_HZ 0 V={FMIN + (FMAX-FMIN)*v(CODE)/255 + DCO_COARSE_STEP*COARSE_CODE}"
        )
        return lines

    if args.dco_model == "piecewise3":
        lines.extend(
            [
                "* Smooth blend across the measured midpoint; both segments equal DCO_F128 at code 128.",
                "BDCO_BLEND DCO_BLEND 0 V={0.5*(1+tanh(10*(v(CODE)-128)))}",
                "BDCO_FREQ_HZ DCO_FREQ_HZ 0 V={(1-v(DCO_BLEND))*(DCO_F0 + (DCO_F128-DCO_F0)*v(CODE)/128) + v(DCO_BLEND)*(DCO_F128 + (DCO_F255-DCO_F128)*(v(CODE)-128)/127) + DCO_COARSE_STEP*COARSE_CODE}",
            ]
        )
        return lines

    lines.extend(
        [
            "* Smooth blends across measured filled-RCX calibration points.",
            "BDCO_BLEND64 DCO_BLEND64 0 V={0.5*(1+tanh(10*(v(CODE)-64)))}",
            "BDCO_BLEND128 DCO_BLEND128 0 V={0.5*(1+tanh(10*(v(CODE)-128)))}",
            "BDCO_BLEND192 DCO_BLEND192 0 V={0.5*(1+tanh(10*(v(CODE)-192)))}",
            "BDCO_FREQ_HZ DCO_FREQ_HZ 0 V={(1-v(DCO_BLEND64))*(DCO_F0 + (DCO_F64-DCO_F0)*v(CODE)/64) + v(DCO_BLEND64)*(1-v(DCO_BLEND128))*(DCO_F64 + (DCO_F128-DCO_F64)*(v(CODE)-64)/64) + v(DCO_BLEND128)*(1-v(DCO_BLEND192))*(DCO_F128 + (DCO_F192-DCO_F128)*(v(CODE)-128)/64) + v(DCO_BLEND192)*(DCO_F192 + (DCO_F255-DCO_F192)*(v(CODE)-192)/63) + DCO_COARSE_STEP*COARSE_CODE}",
        ]
    )
    return lines


def xyce_waveform_path(netlist_path):
    return netlist_path.with_suffix(".prn")


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


def xyce_average(rows, key, start_s, stop_s):
    if not rows or stop_s <= start_s:
        return None
    key = key.lower()
    if key not in rows[0]:
        return None

    points = []
    start_value = xyce_sample(rows, key, start_s)
    stop_value = xyce_sample(rows, key, stop_s)
    if start_value is None or stop_value is None:
        return None
    points.append((start_s, start_value))
    for row in rows:
        time_s = row["time"]
        if start_s < time_s < stop_s:
            points.append((time_s, row[key]))
    points.append((stop_s, stop_value))

    area = 0.0
    for (t0, v0), (t1, v1) in zip(points, points[1:]):
        area += 0.5 * (v0 + v1) * (t1 - t0)
    return area / (stop_s - start_s)


def measure_value(log_text, name):
    for pattern in (
        rf"^\s*{name}\s*=\s*{RE_FLOAT}",
        rf"^\s*{name}\s*:\s*{RE_FLOAT}",
    ):
        match = re.search(pattern, log_text, re.IGNORECASE | re.MULTILINE)
        if match:
            return float(match.group(1))
    return None


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

    ports = []
    for idx, line in enumerate(header):
        if idx == 0:
            ports.extend(line.split()[2:])
        else:
            ports.extend(line[1:].split())
    return ports


def bbpd_macro_lines():
    return [
        "* Sky130 transistor-level BBPD macro candidate.",
        "XDUT_UPD0 UP_Q VGND VNB VPB VPWR UP_D1 sky130_fd_sc_hd__buf_1",
        "XDUT_UPD1 UP_D1 VGND VNB VPB VPWR UP_D2 sky130_fd_sc_hd__buf_1",
        "XDUT_DND0 DN_Q VGND VNB VPB VPWR DN_D1 sky130_fd_sc_hd__buf_1",
        "XDUT_DND1 DN_D1 VGND VNB VPB VPWR DN_D2 sky130_fd_sc_hd__buf_1",
        "XDUT_BOTH UP_D2 DN_D2 VGND VNB VPB VPWR BOTH_HIGH sky130_fd_sc_hd__and2_1",
        "XDUT_RST BOTH_HIGH RESET_N VGND VNB VPB VPWR RESET_B sky130_fd_sc_hd__and2b_1",
        "XDUT_UPFF REF D RESET_B VGND VNB VPB VPWR UP_Q sky130_fd_sc_hd__dfrtp_1",
        "XDUT_DNFF CLKDIVR D RESET_B VGND VNB VPB VPWR DN_Q sky130_fd_sc_hd__dfrtp_1",
    ]


def bbpd_lines(args):
    if args.bbpd_impl == "stdcell":
        return (
            bbpd_macro_lines(),
            "v(UP_Q)=0 v(DN_Q)=0 v(UP_D1)=0 v(UP_D2)=0 v(DN_D1)=0 v(DN_D2)=0",
        )

    rcx_path = Path(args.bbpd_rcx_netlist).expanduser().resolve()
    if not rcx_path.exists():
        raise FileNotFoundError(rcx_path)
    ports = parse_subckt_ports(rcx_path, "IntegerPLL_BBPD")
    port_map = {
        "BBPD[0]": "DN_Q",
        "BBPD[1]": "UP_Q",
        "CLKDIVR": "CLKDIVR",
        "REF": "REF",
        "RESET_N": "RESET_N",
        "VGND": "VGND",
        "VNB": "VNB",
        "VPB": "VPB",
        "VPWR": "VPWR",
    }
    missing_ports = sorted(set(port_map) - set(ports))
    if missing_ports:
        raise ValueError(f"BBPD RCX netlist missing ports: {missing_ports}")
    nodes = [port_map[port] for port in ports]
    return (
        [
            "* Filled post-layout Magic RCX BBPD macro.",
            f'* BBPD RCX netlist: {rcx_path}',
            f'.include "{rcx_path}"',
            f"XBBPD {' '.join(nodes)} IntegerPLL_BBPD",
        ],
        "v(UP_Q)=0 v(DN_Q)=0 "
        "v(XBBPD.up_ff.q)=0 v(XBBPD.dn_ff.q)=0 "
        "v(XBBPD.up_delay_0.x)=0 "
        "v(XBBPD.dn_delay_0.x)=0 v(XBBPD.dn_delay_1.x)=0 "
        "v(XBBPD.dn_ff.reset_b)=0",
    )


def loop_state_lines(args):
    common = [
        "* Digital-loop surrogate. CODE_RAW is a numerical state variable where",
        "* 1 V means one DCO code step; it is not a physical loop-filter capacitor.",
        "CSTATE CODE_RAW 0 1",
        "CDEC DEC_HELD 0 1",
        "RDEC_LEAK DEC_HELD 0 1e12",
    ]

    if args.loop_model == "continuous":
        return (
            [
                f".param CODE_SLEW={args.code_slew_lsb_per_us * 1e6:.12g}",
                f".param LOOP_SIGN={args.loop_current_sign:.12g}",
            ],
            [
                *common,
                "* Continuous mode integrates BBPD pulse width. It is a fast acquisition",
                "* sanity check, not the RTL DLF update law.",
                "* LOOP_SIGN accounts for simulator B-source current orientation; UP",
                "* pulses raise the code state, and DN pulses lower it.",
                "BLOOP CODE_RAW 0 I={LOOP_SIGN*CODE_SLEW*(0.5*(1+tanh(20*(v(DN_Q)-0.9))) - 0.5*(1+tanh(20*(v(UP_Q)-0.9))))}",
                "BCODE_DRIVE CODE_DRIVE 0 V={v(CODE_RAW)}",
            ],
        )

    if args.loop_model == "sampled":
        return (
            [
                f".param DLF_STEP={args.dlf_step_lsb:.12g}",
                f".param DLF_PROP_STEP={args.dlf_prop_lsb:.12g}",
                f".param LOOP_SIGN={args.loop_current_sign:.12g}",
                f".param SAMPLE_DELAY={args.sample_delay_ps * 1e-12:.12g}",
                f".param EDGE_SIGMA={args.edge_sigma_rad:.12g}",
                f".param DEC_TRACK_RATE={args.decision_track_rate_per_s:.12g}",
            ],
            [
                *common,
                "* Sampled mode updates the code only in a narrow aperture after each",
                "* feedback-divider rising edge. This is the SPICE surrogate for the",
                "* RTL DLF fixed-point accumulator update.",
                "* The sample delay lets the BBPD output propagate after the feedback edge.",
                "* The Gaussian edge aperture is normalized so DLF_STEP is in LSB/update.",
                "* DEC_HELD tracks the sampled BBPD sign so the optional proportional",
                "* term is held between DLF update apertures, matching the RTL DLF input",
                "* more closely than a raw BBPD pulse-width term.",
                "BSAMPLE_GATE SAMPLE_GATE 0 V={exp(-pow(sin(2*3.141592653589793*(v(DCO_PHASE)-v(DCO_FREQ_HZ)*SAMPLE_DELAY)/NDIV)/EDGE_SIGMA,2))*0.5*(1+tanh(20*cos(2*3.141592653589793*(v(DCO_PHASE)-v(DCO_FREQ_HZ)*SAMPLE_DELAY)/NDIV)))}",
                "BSAMPLE_DENSITY SAMPLE_DENSITY 0 V={(2*3.141592653589793*v(DCO_FREQ_HZ)/NDIV)/(sqrt(3.141592653589793)*EDGE_SIGMA)*v(SAMPLE_GATE)}",
                "BDEC_TARGET DEC_TARGET 0 V={0.5*(1+tanh(20*(v(UP_Q)-0.9))) - 0.5*(1+tanh(20*(v(DN_Q)-0.9)))}",
                "BDEC DEC_HELD 0 I={-DEC_TRACK_RATE*v(SAMPLE_GATE)*(v(DEC_TARGET)-v(DEC_HELD))}",
                "BLOOP CODE_RAW 0 I={-LOOP_SIGN*DLF_STEP*v(SAMPLE_DENSITY)*v(DEC_TARGET)}",
                "BCODE_DRIVE CODE_DRIVE 0 V={v(CODE_RAW)+LOOP_SIGN*DLF_PROP_STEP*v(DEC_HELD)}",
            ],
        )

    return (
        [
            f".param DLF_STEP={args.dlf_step_lsb:.12g}",
            f".param DLF_PROP_STEP={args.dlf_prop_lsb:.12g}",
            f".param LOOP_SIGN={args.loop_current_sign:.12g}",
            f".param SAMPLE_DELAY={args.sample_delay_ps * 1e-12:.12g}",
            ".param SAMPLE_CLEAR_DELAY=30e-12",
            f".param EDGE_SIGMA={args.edge_sigma_rad:.12g}",
            f".param DEC_TRACK_RATE={args.decision_track_rate_per_s:.12g}",
        ],
        [
            *common,
            "CUP_SEEN UP_SEEN 0 1",
            "CDN_SEEN DN_SEEN 0 1",
            "* Latched sampled mode records the first BBPD polarity seen in a",
            "* feedback-update period, then applies one fixed-point DLF update at the",
            "* divider edge. This avoids missing narrow BBPD pulses and avoids turning",
            "* the reset-overlap interval into an idle 2'b11 decision.",
            "BSAMPLE_GATE SAMPLE_GATE 0 V={exp(-pow(sin(2*3.141592653589793*(v(DCO_PHASE)-v(DCO_FREQ_HZ)*SAMPLE_DELAY)/NDIV)/EDGE_SIGMA,2))*0.5*(1+tanh(20*cos(2*3.141592653589793*(v(DCO_PHASE)-v(DCO_FREQ_HZ)*SAMPLE_DELAY)/NDIV)))}",
            "BCLEAR_GATE SAMPLE_CLEAR_GATE 0 V={exp(-pow(sin(2*3.141592653589793*(v(DCO_PHASE)-v(DCO_FREQ_HZ)*(SAMPLE_DELAY+SAMPLE_CLEAR_DELAY))/NDIV)/EDGE_SIGMA,2))*0.5*(1+tanh(20*cos(2*3.141592653589793*(v(DCO_PHASE)-v(DCO_FREQ_HZ)*(SAMPLE_DELAY+SAMPLE_CLEAR_DELAY))/NDIV)))}",
            "BSAMPLE_DENSITY SAMPLE_DENSITY 0 V={(2*3.141592653589793*v(DCO_FREQ_HZ)/NDIV)/(sqrt(3.141592653589793)*EDGE_SIGMA)*v(SAMPLE_GATE)}",
            "BUP_LEVEL UP_LEVEL 0 V={0.5*(1+tanh(20*(v(UP_Q)-0.9)))}",
            "BDN_LEVEL DN_LEVEL 0 V={0.5*(1+tanh(20*(v(DN_Q)-0.9)))}",
            "BUP_SEEN UP_SEEN 0 I={-DEC_TRACK_RATE*(v(UP_LEVEL)*(1-v(UP_SEEN))*(1-v(DN_SEEN))-v(SAMPLE_CLEAR_GATE)*v(UP_SEEN))}",
            "BDN_SEEN DN_SEEN 0 I={-DEC_TRACK_RATE*(v(DN_LEVEL)*(1-v(DN_SEEN))*(1-v(UP_SEEN))-v(SAMPLE_CLEAR_GATE)*v(DN_SEEN))}",
            "BDEC_TARGET DEC_TARGET 0 V={v(UP_SEEN)-v(DN_SEEN)}",
            "BDEC DEC_HELD 0 I={-DEC_TRACK_RATE*v(SAMPLE_GATE)*(v(DEC_TARGET)-v(DEC_HELD))}",
            "BLOOP CODE_RAW 0 I={-LOOP_SIGN*DLF_STEP*v(SAMPLE_DENSITY)*v(DEC_TARGET)}",
            "BCODE_DRIVE CODE_DRIVE 0 V={v(CODE_RAW)+LOOP_SIGN*DLF_PROP_STEP*v(DEC_HELD)}",
        ],
    )


def pll_loop_netlist(case_name, args):
    case = CASES[case_name]
    pdk_root = Path(args.pdk_root).expanduser().resolve()
    pdk_dir = pdk_root / args.pdk
    model_path = pdk_dir / "libs.tech" / "ngspice" / "sky130.lib.spice"
    cell_path = pdk_dir / "libs.ref" / "sky130_fd_sc_hd" / "spice" / "sky130_fd_sc_hd.spice"

    if not model_path.exists():
        raise FileNotFoundError(model_path)
    if args.bbpd_impl == "stdcell" and not cell_path.exists():
        raise FileNotFoundError(cell_path)

    target_mhz = args.ref_mhz * args.ndiv
    target_code = dco_target_code(args, target_mhz)

    sim_time_ns = args.sim_time_us * 1000.0
    final_meas_ns = max(sim_time_ns - args.step_ps * 1e-3, 0.0)
    meas_from_ns = max(args.sim_time_us * 1000.0 - 500.0, 0.0)
    reset_high_ns = sim_time_ns + 10.0
    reset_period_ns = 2.0 * reset_high_ns
    init_code = case["initial_code"]

    bbpd_spice_lines, bbpd_ic = bbpd_lines(args)
    loop_params, loop_lines = loop_state_lines(args)
    if args.max_step_ps > 0:
        tran_line = f".tran {args.step_ps}p {sim_time_ns}n 0 {args.max_step_ps}p uic"
    else:
        tran_line = f".tran {args.step_ps}p {sim_time_ns}n uic"

    option_lines = []
    if args.simulator == "ngspice":
        option_lines.append(
            ".option method=gear reltol=1e-3 abstol=1e-15 chgtol=1e-16"
            + (f" num_threads={args.ngspice_threads}" if args.ngspice_threads > 0 else "")
        )

    initial_dco_phase_cycles = case_initial_dco_phase_cycles(case_name, args)
    ic_nodes = [
        f"v(CODE_RAW)={init_code}",
        f"v(DCO_PHASE)={initial_dco_phase_cycles:.12g}",
    ]
    if args.loop_model in ("sampled", "sampled_latched"):
        ic_nodes.append("v(DEC_HELD)=0")
    if args.loop_model == "sampled_latched":
        ic_nodes.append("v(UP_SEEN)=0 v(DN_SEEN)=0")
    if bbpd_ic:
        ic_nodes.append(bbpd_ic)

    lines = [
        f"* OpenPLL closed-loop SPICE acquisition check, corner={args.corner}, case={case_name}, bbpd={args.bbpd_impl}, loop={args.loop_model}, dco_model={args.dco_model}",
        f"* simulator={args.simulator}",
        "* DCO frequency model is derived from measured Sky130 DCO SPICE data.",
        f'.lib "{model_path}" {args.corner}',
        *([f'.include "{cell_path}"'] if args.bbpd_impl == "stdcell" else []),
        *option_lines,
        ".param VDD=1.8",
        f".param FREF={args.ref_mhz}e6",
        f".param NDIV={args.ndiv}",
        f".param FMIN={args.fmin_mhz}e6",
        f".param FMAX={args.fmax_mhz}e6",
        f".param DCO_F0={args.f0_mhz}e6",
        f".param DCO_F64={args.f64_mhz}e6",
        f".param DCO_F128={args.f128_mhz}e6",
        f".param DCO_F192={args.f192_mhz}e6",
        f".param DCO_F255={args.f255_mhz}e6",
        f".param COARSE_CODE={args.coarse_code:.12g}",
        f".param DCO_COARSE_STEP={args.dco_coarse_step_mhz:.12g}e6",
        f".param CLK_SHARPNESS={args.clock_sharpness:.12g}",
        *loop_params,
        f".param INIT_CODE={init_code}",
        "VVPWR VPWR 0 {VDD}",
        "VVPB VPB 0 {VDD}",
        "VVGND VGND 0 0",
        "VVNB VNB 0 0",
        "VD D 0 {VDD}",
        f"VRESET RESET_N 0 PULSE(0 {{VDD}} 5n 50p 50p {reset_high_ns:.12g}n {reset_period_ns:.12g}n)",
        "",
        "* Smooth behavioral clocks keep ngspice timesteps practical while still",
        "* driving transistor-level Sky130 standard-cell inputs.",
        "BREF REF 0 V={0.9 + 0.9*tanh(CLK_SHARPNESS*sin(2*3.141592653589793*FREF*time))}",
        "BFBDIV CLKDIVR 0 V={0.9 + 0.9*tanh(CLK_SHARPNESS*sin(2*3.141592653589793*v(DCO_PHASE)/NDIV))}",
        "BPLOUT PLLOUT 0 V={0.9 + 0.9*tanh(CLK_SHARPNESS*sin(2*3.141592653589793*v(DCO_PHASE)))}",
        "",
        *bbpd_spice_lines,
        "",
        *loop_lines,
        ".ic " + " ".join(ic_nodes),
        *dco_model_lines(args),
        "BFREQ FREQ_MHZ 0 V={v(DCO_FREQ_HZ)/1e6}",
        "BTARGET TARGET_MHZ 0 V={FREF*NDIV/1e6}",
        "BFERR FERR_MHZ 0 V={v(FREQ_MHZ)-v(TARGET_MHZ)}",
        "",
        "* Phase is measured in output cycles; d(phase)/dt is DCO frequency.",
        "CPHASE DCO_PHASE 0 1",
        "BPHASE DCO_PHASE 0 I={v(DCO_FREQ_HZ)}",
        "",
    ]
    if args.simulator == "ngspice":
        lines.extend(
            [
                ".save v(CODE) v(CODE_RAW) v(CODE_DRIVE) v(DEC_HELD) v(DCO_FREQ_HZ) v(FREQ_MHZ) v(FERR_MHZ) v(UP_Q) v(DN_Q) v(REF) v(CLKDIVR)",
                tran_line,
                ".meas tran code_start FIND v(CODE) AT=20n",
                f".meas tran code_end FIND v(CODE) AT={final_meas_ns:.9g}n",
                ".meas tran freq_start_mhz FIND v(FREQ_MHZ) AT=20n",
                f".meas tran freq_end_mhz FIND v(FREQ_MHZ) AT={final_meas_ns:.9g}n",
                f".meas tran freq_avg_mhz AVG v(FREQ_MHZ) FROM={meas_from_ns:.9g}n TO={sim_time_ns:.9g}n",
                f".meas tran ferr_avg_mhz AVG v(FERR_MHZ) FROM={meas_from_ns:.9g}n TO={sim_time_ns:.9g}n",
            ]
        )
    else:
        lines.extend(
            [
                ".print tran v(CODE) v(CODE_RAW) v(CODE_DRIVE) v(DEC_HELD) v(DCO_FREQ_HZ) v(FREQ_MHZ) v(FERR_MHZ) v(UP_Q) v(DN_Q) v(REF) v(CLKDIVR)",
                tran_line,
            ]
        )
    lines.extend([".end", ""])
    return "\n".join(lines), target_mhz, target_code


def simulator_command(args, netlist_path):
    if args.simulator == "ngspice":
        return [args.ngspice, "-b", str(netlist_path)]
    if args.simulator == "xyce":
        return xyce_simulator_command(args, netlist_path, netlist_path.stem)
    raise ValueError(f"unsupported simulator: {args.simulator}")


def xyce_measurements(args, netlist_path):
    rows = parse_xyce_waveform(xyce_waveform_path(netlist_path))
    if not rows:
        return {
            "code_start": None,
            "code_end": None,
            "freq_start": None,
            "freq_end": None,
            "freq_avg": None,
            "ferr_avg": None,
        }

    sim_time_ns = args.sim_time_us * 1000.0
    final_meas_s = max(sim_time_ns - args.step_ps * 1e-3, 0.0) * 1e-9
    meas_from_s = max(args.sim_time_us * 1000.0 - 500.0, 0.0) * 1e-9
    sim_time_s = sim_time_ns * 1e-9
    return {
        "code_start": xyce_sample(rows, "v(code)", 20e-9),
        "code_end": xyce_sample(rows, "v(code)", final_meas_s),
        "freq_start": xyce_sample(rows, "v(freq_mhz)", 20e-9),
        "freq_end": xyce_sample(rows, "v(freq_mhz)", final_meas_s),
        "freq_avg": xyce_average(rows, "v(freq_mhz)", meas_from_s, sim_time_s),
        "ferr_avg": xyce_average(rows, "v(ferr_mhz)", meas_from_s, sim_time_s),
    }


def run_one(case_name, args, build_dir):
    netlist, target_mhz, target_code = pll_loop_netlist(case_name, args)
    netlist_path = build_dir / f"pll_loop_{args.corner}_{case_name}.spice"
    log_path = build_dir / f"pll_loop_{args.corner}_{case_name}.log"
    resumed = False
    if args.resume and netlist_path.exists() and log_path.exists():
        old_netlist = netlist_path.read_text(encoding="ascii", errors="replace")
        if old_netlist == netlist:
            log_text = log_path.read_text(encoding="utf-8", errors="replace")
            returncode = 0
            timed_out = False
            elapsed_s = None
            resumed = True
        else:
            log_text = None
    else:
        log_text = None

    if log_text is None:
        netlist_path.write_text(netlist, encoding="ascii")
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
            log_text, _ = proc.communicate(timeout=args.timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
            proc.kill()
            log_text, _ = proc.communicate()
        elapsed_s = time.monotonic() - start
        if timed_out:
            log_text += (
                f"\nOpenPLL timeout: killed {args.simulator} after {args.timeout_s:.1f} s "
                f"for corner={args.corner} case={case_name} bbpd={args.bbpd_impl}\n"
            )
        returncode = proc.returncode
        log_path.write_text(log_text, encoding="utf-8")

    if args.simulator == "xyce":
        measurements = xyce_measurements(args, netlist_path)
        code_start = measurements["code_start"]
        code_end = measurements["code_end"]
        freq_start = measurements["freq_start"]
        freq_end = measurements["freq_end"]
        freq_avg = measurements["freq_avg"]
        ferr_avg = measurements["ferr_avg"]
    else:
        code_start = measure_value(log_text, "code_start")
        code_end = measure_value(log_text, "code_end")
        freq_start = measure_value(log_text, "freq_start_mhz")
        freq_end = measure_value(log_text, "freq_end_mhz")
        freq_avg = measure_value(log_text, "freq_avg_mhz")
        ferr_avg = measure_value(log_text, "ferr_avg_mhz")

    expected_direction = CASES[case_name]["expected_direction"]
    moved = None
    if code_start is not None and code_end is not None:
        if expected_direction == "increase":
            moved = code_end > code_start + args.min_code_motion
        else:
            moved = code_end < code_start - args.min_code_motion

    freq_tolerance_mhz = max(
        args.lock_tolerance_mhz,
        args.code_tolerance * (args.f255_mhz - args.f0_mhz) / 255.0,
    )
    converged = (
        ferr_avg is not None
        and abs(ferr_avg) <= freq_tolerance_mhz
        and code_end is not None
        and abs(code_end - target_code) <= args.code_tolerance
    )
    ok = returncode == 0 and not timed_out and moved and converged

    return {
        "corner": args.corner,
        "case": case_name,
        "status": "pass" if ok else "fail",
        "simulator": args.simulator,
        "xyce_mpi_procs": args.xyce_mpi_procs if args.simulator == "xyce" else "",
        "bbpd_impl": args.bbpd_impl,
        "bbpd_rcx_netlist": "" if args.bbpd_impl == "stdcell" else str(Path(args.bbpd_rcx_netlist).expanduser().resolve()),
        "loop_model": args.loop_model,
        "expected_direction": expected_direction,
        "returncode": returncode,
        "timed_out": "yes" if timed_out else "no",
        "elapsed_s": "" if elapsed_s is None else f"{elapsed_s:.3f}",
        "dco_model": args.dco_model,
        "code_slew_lsb_per_us": args.code_slew_lsb_per_us,
        "loop_current_sign": args.loop_current_sign,
        "dlf_step_lsb": args.dlf_step_lsb,
        "dlf_prop_lsb": args.dlf_prop_lsb,
        "sample_delay_ps": args.sample_delay_ps,
        "max_step_ps": args.max_step_ps,
        "edge_sigma_rad": args.edge_sigma_rad,
        "decision_track_rate_per_s": args.decision_track_rate_per_s,
        "clock_sharpness": args.clock_sharpness,
        "initial_dco_phase_cycles": case_initial_dco_phase_cycles(case_name, args),
        "fmin_mhz": args.fmin_mhz,
        "fmax_mhz": args.fmax_mhz,
        "f0_mhz": args.f0_mhz,
        "f64_mhz": args.f64_mhz,
        "f128_mhz": args.f128_mhz,
        "f192_mhz": args.f192_mhz,
        "f255_mhz": args.f255_mhz,
        "coarse_code": args.coarse_code,
        "dco_coarse_step_mhz": args.dco_coarse_step_mhz,
        "ref_mhz": args.ref_mhz,
        "ndiv": args.ndiv,
        "target_mhz": target_mhz,
        "target_code": target_code,
        "freq_tolerance_mhz": freq_tolerance_mhz,
        "resumed": "yes" if resumed else "no",
        "code_start": "" if code_start is None else code_start,
        "code_end": "" if code_end is None else code_end,
        "freq_start_mhz": "" if freq_start is None else freq_start,
        "freq_end_mhz": "" if freq_end is None else freq_end,
        "freq_avg_mhz": "" if freq_avg is None else freq_avg,
        "ferr_avg_mhz": "" if ferr_avg is None else ferr_avg,
        "netlist": str(netlist_path),
        "log": str(log_path),
        "waveform": str(xyce_waveform_path(netlist_path)) if args.simulator == "xyce" else "",
    }


def parse_csv_corners(text):
    return [item.strip() for item in text.split(",") if item.strip()]


def load_dco_spans(csv_path, corners):
    path = Path(csv_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(path)

    by_corner = {corner: [] for corner in corners}
    with path.open(newline="", encoding="utf-8") as csv_file:
        reader = csv.DictReader(csv_file)
        for row in reader:
            corner = row.get("corner", "")
            if corner not in by_corner or row.get("status") != "pass":
                continue
            by_corner[corner].append(
                {
                    "code": int(row["code"]),
                    "freq_mhz": float(row["freq_mhz"]),
                }
            )

    spans = {}
    for corner, rows in by_corner.items():
        if not rows:
            raise ValueError(f"no passing DCO rows found for corner {corner!r} in {path}")
        rows.sort(key=lambda row: row["code"])
        if rows[0]["code"] != 0 or rows[-1]["code"] != 255:
            raise ValueError(f"corner {corner!r} is missing DCO code 0 or 255 endpoint rows")
        spans[corner] = (rows[0]["freq_mhz"], rows[-1]["freq_mhz"])
    return spans


def build_run_args(args):
    if not args.dco_pvt_csv:
        return [args]
    if args.dco_model != "linear":
        raise ValueError("--dco-pvt-csv currently supports only --dco-model linear")

    corners = parse_csv_corners(args.dco_pvt_corners)
    spans = load_dco_spans(args.dco_pvt_csv, corners)
    run_args = []
    for corner in corners:
        fmin_mhz, fmax_mhz = spans[corner]
        target_mhz = fmin_mhz + (fmax_mhz - fmin_mhz) * args.target_code / 255.0
        corner_args = Namespace(**vars(args))
        corner_args.corner = corner
        corner_args.fmin_mhz = fmin_mhz
        corner_args.fmax_mhz = fmax_mhz
        corner_args.f0_mhz = fmin_mhz
        corner_args.f64_mhz = dco_freq_mhz_at_code(corner_args, 64.0)
        corner_args.f128_mhz = dco_freq_mhz_at_code(corner_args, 128.0)
        corner_args.f192_mhz = dco_freq_mhz_at_code(corner_args, 192.0)
        corner_args.f255_mhz = fmax_mhz
        corner_args.ref_mhz = target_mhz / args.ndiv
        run_args.append(corner_args)
    return run_args


def parse_timeout(value):
    if value in (None, "none", "None", "0", "0.0"):
        return None
    timeout = float(value)
    if timeout <= 0:
        raise ValueError("--timeout-s must be positive, 0, or 'none'")
    return timeout


def main():
    parser = argparse.ArgumentParser(description="Run a closed-loop PLL acquisition SPICE check.")
    parser.add_argument("--cases", default="low_start,high_start")
    parser.add_argument("--pdk-root", default=default_pdk_root())
    parser.add_argument("--pdk", default=os.environ.get("PDK", "sky130A"))
    parser.add_argument("--corner", default="tt")
    parser.add_argument("--fmin-mhz", type=float, default=50.94408409075311)
    parser.add_argument("--fmax-mhz", type=float, default=60.002955827195265)
    parser.add_argument(
        "--dco-model",
        choices=("linear", "piecewise3", "piecewise5"),
        default="linear",
        help="Behavioral DCO frequency model used by the PLL loop surrogate.",
    )
    parser.add_argument("--f0-mhz", type=float, default=None)
    parser.add_argument("--f64-mhz", type=float, default=None)
    parser.add_argument("--f128-mhz", type=float, default=None)
    parser.add_argument("--f192-mhz", type=float, default=None)
    parser.add_argument("--f255-mhz", type=float, default=None)
    parser.add_argument(
        "--coarse-code",
        type=float,
        default=0.0,
        help="Static independent DCO coarse-band code added to the analog DCO model.",
    )
    parser.add_argument(
        "--dco-coarse-step-mhz",
        type=float,
        default=0.0,
        help="Frequency offset per independent coarse-band code step.",
    )
    parser.add_argument("--ref-mhz", type=float, default=11.2)
    parser.add_argument("--ndiv", type=int, default=5)
    parser.add_argument("--target-code", type=float, default=128.0)
    parser.add_argument("--bbpd-impl", choices=("stdcell", "postlayout"), default="stdcell")
    parser.add_argument(
        "--bbpd-rcx-netlist",
        default="openlane/IntegerPLL_BBPD/runs/librelane_signoff/rcx-magic/IntegerPLL_BBPD.rcx.spice",
    )
    parser.add_argument(
        "--dco-pvt-csv",
        default=None,
        help="Use measured DCO PVT CSV endpoint spans and run all selected corners.",
    )
    parser.add_argument("--dco-pvt-corners", default="tt,ff,ss,sf,fs")
    parser.add_argument(
        "--code-slew-lsb-per-us",
        type=float,
        default=50.0,
        help="Numerical digital-code slew used by --loop-model continuous.",
    )
    parser.add_argument(
        "--loop-model",
        choices=("continuous", "sampled", "sampled_latched"),
        default="continuous",
    )
    parser.add_argument(
        "--dlf-step-lsb",
        type=float,
        default=1.5,
        help="Sampled-loop KI-like DCO code step in LSB per feedback update.",
    )
    parser.add_argument(
        "--dlf-prop-lsb",
        type=float,
        default=0.0,
        help=(
            "Sampled-loop proportional DCO-code offset in 8-bit LSB. "
            "A value of 1.0 approximates RTL DLF_KP=4 because DCO_CODE is DLF_CODE[9:2]."
        ),
    )
    parser.add_argument(
        "--sample-delay-ps",
        type=float,
        default=150.0,
        help="Delay from feedback rising edge to sampled DLF aperture.",
    )
    parser.add_argument(
        "--edge-sigma-rad",
        type=float,
        default=0.03,
        help="Gaussian sampled-loop edge aperture width in feedback phase radians.",
    )
    parser.add_argument(
        "--clock-sharpness",
        type=float,
        default=20.0,
        help="tanh() sharpness for behavioral REF/feedback/DCO clocks.",
    )
    parser.add_argument(
        "--decision-track-rate-per-s",
        type=float,
        default=1e10,
        help="First-order tracking rate used to hold sampled BBPD decisions for the proportional term.",
    )
    parser.add_argument(
        "--initial-dco-phase-cycles",
        type=float,
        default=0.0,
        help="Initial DCO phase in output cycles; useful for phase-aperture sensitivity checks.",
    )
    parser.add_argument(
        "--low-start-initial-dco-phase-cycles",
        type=float,
        default=None,
        help="Override --initial-dco-phase-cycles for the low_start case.",
    )
    parser.add_argument(
        "--high-start-initial-dco-phase-cycles",
        type=float,
        default=None,
        help="Override --initial-dco-phase-cycles for the high_start case.",
    )
    parser.add_argument("--sim-time-us", type=float, default=8.0)
    parser.add_argument("--step-ps", type=float, default=200.0)
    parser.add_argument(
        "--max-step-ps",
        type=float,
        default=0.0,
        help=(
            "Optional transient maximum timestep. Xyce treats the first .TRAN "
            "value as the initial step, so this is required when behavioral "
            "clocks drive transistor-level flip-flops."
        ),
    )
    parser.add_argument("--lock-tolerance-mhz", type=float, default=0.75)
    parser.add_argument("--code-tolerance", type=float, default=32.0)
    parser.add_argument("--min-code-motion", type=float, default=16.0)
    parser.add_argument(
        "--loop-current-sign",
        type=float,
        default=1.0,
        help="Sign multiplier for the numerical loop-current source; default matches validated ngspice targets.",
    )
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--timeout-s",
        default="none",
        help="Per-simulation wall-clock timeout in seconds, 0, or 'none'.",
    )
    parser.add_argument(
        "--simulator",
        choices=("ngspice", "xyce"),
        default="ngspice",
        help="Circuit simulator for the generated PLL loop deck.",
    )
    parser.add_argument("--ngspice", default=shutil.which("ngspice") or "ngspice")
    add_xyce_arguments(parser)
    parser.add_argument(
        "--ngspice-threads",
        type=int,
        default=int(os.environ.get("NGSPICE_THREADS", "0")),
        help="Set ngspice OpenMP threads via .option num_threads and OMP_NUM_THREADS; 0 leaves default.",
    )
    parser.add_argument(
        "--build-dir",
        default=str(Path(__file__).resolve().parents[1] / "build" / "spice_pll_loop"),
    )
    args = parser.parse_args()
    args.timeout_s = parse_timeout(args.timeout_s)
    if args.ngspice_threads < 0:
        raise ValueError("--ngspice-threads must be non-negative")
    validate_xyce_arguments(args)
    if args.clock_sharpness <= 0:
        raise ValueError("--clock-sharpness must be positive")
    if args.max_step_ps < 0:
        raise ValueError("--max-step-ps must be non-negative")
    if args.dlf_prop_lsb < 0:
        raise ValueError("--dlf-prop-lsb must be non-negative")
    if args.coarse_code < 0 or args.coarse_code > 15:
        raise ValueError("--coarse-code must be in 0..15")
    if args.dco_coarse_step_mhz < 0:
        raise ValueError("--dco-coarse-step-mhz must be non-negative")
    if args.decision_track_rate_per_s <= 0:
        raise ValueError("--decision-track-rate-per-s must be positive")
    args = normalize_dco_model(args)

    case_names = [item.strip() for item in args.cases.split(",") if item.strip()]
    for case_name in case_names:
        if case_name not in CASES:
            raise ValueError(f"unknown PLL loop case: {case_name}")

    build_dir = Path(args.build_dir).expanduser().resolve()
    build_dir.mkdir(parents=True, exist_ok=True)

    rows = [
        run_one(case_name, run_args, build_dir)
        for run_args in build_run_args(args)
        for case_name in case_names
    ]
    csv_path = build_dir / "pll_loop_check.csv"
    with csv_path.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    for row in rows:
        print(
            f"corner={row['corner']} case={row['case']} status={row['status']} "
            f"code={row['code_start']}->{row['code_end']} "
            f"freq_avg_mhz={row['freq_avg_mhz']} ferr_avg_mhz={row['ferr_avg_mhz']}"
        )
    print(f"wrote {csv_path}")

    failed = [row for row in rows if row["status"] != "pass"]
    if failed:
        print(f"{len(failed)} PLL loop SPICE runs failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
