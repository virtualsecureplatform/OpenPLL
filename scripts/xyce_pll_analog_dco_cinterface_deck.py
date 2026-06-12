#!/usr/bin/env python3
"""Generate an OpenPLL Xyce C-interface deck with analog BBPD and DCO models."""

from __future__ import annotations

import argparse
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def parse_subckt_ports(path: Path, subckt: str) -> list[str]:
    pattern = re.compile(rf"^\s*\.subckt\s+{re.escape(subckt)}\s+(.+?)\s*$", re.IGNORECASE)
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = pattern.match(line)
        if match:
            return match.group(1).split()
    raise ValueError(f"missing .subckt {subckt} in {path}")


def wrapped_instance(name: str, ports: list[str], subckt: str, width: int = 8) -> list[str]:
    tokens = list(ports) + [subckt]
    lines = [f"{name} " + " ".join(tokens[:width])]
    for index in range(width, len(tokens), width):
        lines.append("+ " + " ".join(tokens[index : index + width]))
    return lines


def dco_model_lines() -> list[str]:
    return [
        "BCODE CODE 0 V={min(255,max(0,255*v(DCO_CODE_V)/VDD))}",
        "BDCO_BLEND64 DCO_BLEND64 0 V={0.5*(1+tanh(10*(v(CODE)-64)))}",
        "BDCO_BLEND128 DCO_BLEND128 0 V={0.5*(1+tanh(10*(v(CODE)-128)))}",
        "BDCO_BLEND192 DCO_BLEND192 0 V={0.5*(1+tanh(10*(v(CODE)-192)))}",
        "BDCO_FREQ_HZ DCO_FREQ_HZ 0 V={(1-v(DCO_BLEND64))*(DCO_F0 + (DCO_F64-DCO_F0)*v(CODE)/64) + v(DCO_BLEND64)*(1-v(DCO_BLEND128))*(DCO_F64 + (DCO_F128-DCO_F64)*(v(CODE)-64)/64) + v(DCO_BLEND128)*(1-v(DCO_BLEND192))*(DCO_F128 + (DCO_F192-DCO_F128)*(v(CODE)-128)/64) + v(DCO_BLEND192)*(DCO_F192 + (DCO_F255-DCO_F192)*(v(CODE)-192)/63) + DCO_COARSE_STEP*COARSE_CODE}",
        "BFREQ FREQ_MHZ 0 V={v(DCO_FREQ_HZ)/1e6}",
        "CPHASE DCO_PHASE 0 1",
        "BPHASE DCO_PHASE 0 I={v(DCO_FREQ_HZ)}",
        "BPLLOUT PLLOUT 0 V={0.9 + 0.9*tanh(CLK_SHARPNESS*sin(2*3.141592653589793*(v(DCO_PHASE)+CLOCK_PHASE_OFFSET)))}",
        "BFBDIV CLKDIVR 0 V={0.9 + 0.9*tanh(CLK_SHARPNESS*sin(2*3.141592653589793*(v(DCO_PHASE)/NDIV+CLOCK_PHASE_OFFSET)))}",
    ]


def build_deck(args) -> str:
    pdk_root = Path(args.pdk_root).expanduser().resolve()
    model_path = pdk_root / args.pdk / "libs.tech" / "ngspice" / "sky130.lib.spice"
    rcx_path = Path(args.bbpd_rcx_netlist).expanduser().resolve()
    if not model_path.exists():
        raise FileNotFoundError(model_path)
    if not rcx_path.exists():
        raise FileNotFoundError(rcx_path)

    ports = parse_subckt_ports(rcx_path, args.bbpd_subckt)
    port_nets = {
        "BBPD[0]": "BBPD[0]",
        "BBPD[1]": "BBPD[1]",
        "CLKDIVR": "CLKDIVR",
        "REF": "REF",
        "RESET_N": "RESET_N",
        "VGND": "VGND",
        "VNB": "VNB",
        "VPB": "VPB",
        "VPWR": "VPWR",
    }
    missing = [port for port in ports if port not in port_nets]
    if missing:
        raise ValueError(f"unsupported {args.bbpd_subckt} ports: {', '.join(missing)}")

    sim_time_ns = args.sim_time_ns
    reset_high_ns = sim_time_ns + 10.0
    reset_period_ns = 2.0 * reset_high_ns
    tran_suffix = " uic" if args.tran_uic else ""

    lines = [
        "* OpenPLL mixed-signal C-interface deck with analog BBPD and DCO.",
        "* Xyce owns the filled BBPD RCX, behavioral DCO phase, and feedback divider.",
        "* The external C-interface driver owns only the digital loop-filter update.",
        f"* BBPD RCX netlist: {rcx_path}",
        f'.lib "{model_path}" {args.corner}',
        f'.include "{rcx_path}"',
        ".param VDD=1.8",
        f".param FREF={args.ref_mhz:.12g}e6",
        f".param NDIV={args.ndiv}",
        f".param DCO_F0={args.f0_mhz:.12g}e6",
        f".param DCO_F64={args.f64_mhz:.12g}e6",
        f".param DCO_F128={args.f128_mhz:.12g}e6",
        f".param DCO_F192={args.f192_mhz:.12g}e6",
        f".param DCO_F255={args.f255_mhz:.12g}e6",
        f".param COARSE_CODE={args.coarse_code}",
        f".param DCO_COARSE_STEP={args.dco_coarse_step_mhz:.12g}e6",
        f".param CLK_SHARPNESS={args.clock_sharpness:.12g}",
        f".param CLOCK_PHASE_OFFSET={args.clock_phase_offset:.12g}",
        "VVPWR VPWR 0 {VDD}",
        "VVPB VPB 0 {VDD}",
        "VVGND VGND 0 0",
        "VVNB VNB 0 0",
        f"VRESET RESET_N 0 PULSE(0 {{VDD}} 1n 20p 20p {reset_high_ns:.12g}n {reset_period_ns:.12g}n)",
        "YDAC code_driver DCO_CODE_V 0 code_dac",
        "YADC up_adc BBPD[1] 0 logic_adc R=1T WIDTH=1",
        "YADC dn_adc BBPD[0] 0 logic_adc R=1T WIDTH=1",
        "YADC pllout_adc PLLOUT 0 logic_adc R=1T WIDTH=1",
        ".model code_dac DAC(tr=20p tf=20p)",
        ".model logic_adc ADC(settlingtime=5p uppervoltagelimit=1.8 lowervoltagelimit=0)",
        "",
        "BREF REF 0 V={0.9 + 0.9*tanh(CLK_SHARPNESS*sin(2*3.141592653589793*(FREF*time+CLOCK_PHASE_OFFSET)))}",
        *dco_model_lines(),
        "",
        *wrapped_instance("XBBPD", [port_nets[port] for port in ports], args.bbpd_subckt),
        "",
        f".ic v(DCO_PHASE)={args.initial_dco_phase_cycles:.12g}",
        ".print tran v(REF) v(CLKDIVR) v(PLLOUT) v(BBPD[1]) v(BBPD[0]) v(DCO_CODE_V) v(CODE) v(FREQ_MHZ) N(YADC!UP_ADC_STATE) N(YADC!DN_ADC_STATE) N(YADC!PLLOUT_ADC_STATE)",
        f".tran {args.step_ps:g}p {sim_time_ns:g}n 0 {args.max_step_ps:g}p{tran_suffix}",
        ".end",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdk-root", default="~/.volare")
    parser.add_argument("--pdk", default="sky130A")
    parser.add_argument("--corner", default="tt")
    parser.add_argument("--bbpd-subckt", default="IntegerPLL_BBPD")
    parser.add_argument(
        "--bbpd-rcx-netlist",
        default=str(
            ROOT
            / "openlane"
            / "IntegerPLL_BBPD"
            / "runs"
            / "librelane_signoff"
            / "rcx-magic"
            / "IntegerPLL_BBPD.rcx.spice"
        ),
    )
    parser.add_argument("--ref-mhz", type=float, default=63.443725)
    parser.add_argument("--ndiv", type=int, default=2)
    parser.add_argument("--f0-mhz", type=float, default=102.518)
    parser.add_argument("--f64-mhz", type=float, default=119.260)
    parser.add_argument("--f128-mhz", type=float, default=142.355)
    parser.add_argument("--f192-mhz", type=float, default=176.267)
    parser.add_argument("--f255-mhz", type=float, default=229.054)
    parser.add_argument("--coarse-code", type=int, default=1)
    parser.add_argument("--dco-coarse-step-mhz", type=float, default=16.0)
    parser.add_argument("--initial-dco-phase-cycles", type=float, default=0.0)
    parser.add_argument("--clock-sharpness", type=float, default=50.0)
    parser.add_argument("--clock-phase-offset", type=float, default=-0.25)
    parser.add_argument("--step-ps", type=float, default=5.0)
    parser.add_argument("--max-step-ps", type=float, default=50.0)
    parser.add_argument("--sim-time-ns", type=float, default=1500.0)
    parser.add_argument("--tran-uic", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT
        / "build"
        / "xyce_pll_analog_dco_mixed_fast100_coarse4"
        / "pll_analog_dco_bbpd.cir",
    )
    args = parser.parse_args()

    if args.ndiv <= 0:
        raise ValueError("--ndiv must be positive")
    if args.coarse_code < 0 or args.coarse_code > 15:
        raise ValueError("--coarse-code must be in 0..15")
    if args.dco_coarse_step_mhz < 0:
        raise ValueError("--dco-coarse-step-mhz must be non-negative")
    points = [args.f0_mhz, args.f64_mhz, args.f128_mhz, args.f192_mhz, args.f255_mhz]
    if any(hi <= lo for lo, hi in zip(points, points[1:])):
        raise ValueError("DCO calibration points must be monotonic increasing")
    if args.max_step_ps <= 0 or args.step_ps <= 0 or args.sim_time_ns <= 0:
        raise ValueError("transient step and time arguments must be positive")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(build_deck(args), encoding="ascii")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
