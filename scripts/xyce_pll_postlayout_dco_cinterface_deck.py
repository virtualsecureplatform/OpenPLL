#!/usr/bin/env python3
"""Generate an OpenPLL Xyce C-interface deck with RCX BBPD and RCX DCO."""

from __future__ import annotations

import argparse
from pathlib import Path
import re

from sky130_pdk import default_pdk_root


ROOT = Path(__file__).resolve().parents[1]


def parse_subckt_ports(path: Path, subckt: str) -> list[str]:
    pattern = re.compile(rf"^\s*\.subckt\s+{re.escape(subckt)}\s+(.+?)\s*$", re.IGNORECASE)
    lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    ports: list[str] = []
    in_header = False
    for line in lines:
        stripped = line.strip()
        if not in_header:
            match = pattern.match(stripped)
            if match:
                ports.extend(match.group(1).split())
                in_header = True
            continue
        if stripped.startswith("+"):
            ports.extend(stripped[1:].split())
        else:
            break
    if not ports:
        raise ValueError(f"missing .subckt {subckt} in {path}")
    return ports


def wrapped_instance(name: str, ports: list[str], subckt: str, width: int = 8) -> list[str]:
    tokens = list(ports) + [subckt]
    lines = [f"{name} " + " ".join(tokens[:width])]
    for index in range(width, len(tokens), width):
        lines.append("+ " + " ".join(tokens[index : index + width]))
    return lines


def build_deck(args) -> str:
    pdk_root = Path(args.pdk_root).expanduser().resolve()
    model_path = pdk_root / args.pdk / "libs.tech" / "ngspice" / "sky130.lib.spice"
    bbpd_path = Path(args.bbpd_rcx_netlist).expanduser().resolve()
    dco_path = Path(args.dco_rcx_netlist).expanduser().resolve()
    if not model_path.exists():
        raise FileNotFoundError(model_path)
    if not bbpd_path.exists():
        raise FileNotFoundError(bbpd_path)
    if not dco_path.exists():
        raise FileNotFoundError(dco_path)

    bbpd_ports = parse_subckt_ports(bbpd_path, args.bbpd_subckt)
    bbpd_nets = {
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
    missing_bbpd = [port for port in bbpd_ports if port not in bbpd_nets]
    if missing_bbpd:
        raise ValueError(f"unsupported {args.bbpd_subckt} ports: {', '.join(missing_bbpd)}")

    dco_ports = parse_subckt_ports(dco_path, args.dco_subckt)
    dco_nets = {
        "PLLOUT": "PLLOUT",
        "RESET_N": "RESET_N",
        "VGND": "VGND",
        "VNB": "VNB",
        "VPB": "VPB",
        "VPWR": "VPWR",
    }
    for index in range(255):
        dco_nets[f"DCO_THERM[{index}]"] = f"DCO_THERM[{index}]"
    missing_dco = [port for port in dco_ports if port not in dco_nets]
    if missing_dco:
        raise ValueError(f"unsupported {args.dco_subckt} ports: {', '.join(missing_dco)}")

    reset_high_ns = args.sim_time_ns + 10.0
    reset_period_ns = 2.0 * reset_high_ns
    ref_period_ns = 1.0e3 / args.ref_mhz
    ref_delay_ns = ((-args.clock_phase_offset) % 1.0) * ref_period_ns
    ref_high_ns = 0.5 * ref_period_ns
    tran_suffix = " uic" if args.tran_uic else ""
    if args.ref_source == "pulse":
        ref_source = f"VREF REF 0 PULSE(0 {{VDD}} {ref_delay_ns:.12g}n 20p 20p {ref_high_ns:.12g}n {ref_period_ns:.12g}n)"
    else:
        ref_source = "BREF REF 0 V={0.9 + 0.9*tanh(CLK_SHARPNESS*sin(2*3.141592653589793*(FREF*time+CLOCK_PHASE_OFFSET)))}"

    lines = [
        "* OpenPLL mixed-signal C-interface deck with RCX BBPD and RCX DCO.",
        "* Xyce owns the extracted analog BBPD/DCO. The external C-interface",
        "* driver owns the digital loop filter and feedback divider.",
        f"* BBPD RCX netlist: {bbpd_path}",
        f"* DCO RCX netlist: {dco_path}",
        f'.lib "{model_path}" {args.corner}',
        f'.include "{bbpd_path}"',
        f'.include "{dco_path}"',
        ".param VDD=1.8",
        f".param FREF={args.ref_mhz:.12g}e6",
        f".param CLK_SHARPNESS={args.clock_sharpness:.12g}",
        f".param CLOCK_PHASE_OFFSET={args.clock_phase_offset:.12g}",
        "VVPWR VPWR 0 {VDD}",
        "VVPB VPB 0 {VDD}",
        "VVGND VGND 0 0",
        "VVNB VNB 0 0",
        f"VRESET RESET_N 0 PULSE(0 {{VDD}} {args.reset_release_ns:.12g}n 20p 20p {reset_high_ns:.12g}n {reset_period_ns:.12g}n)",
        "YDAC code_driver CODE 0 code_dac",
        *[
            f"YDAC therm_driver_{index:03d} DCO_THERM[{index}] 0 logic_dac"
            for index in range(255)
        ],
        "YDAC div_driver CLKDIVR 0 logic_dac",
        "YADC up_adc BBPD[1] 0 logic_adc R=1T WIDTH=1",
        "YADC dn_adc BBPD[0] 0 logic_adc R=1T WIDTH=1",
        "YADC pllout_adc PLLOUT 0 logic_adc R=1T WIDTH=1",
        ".model code_dac DAC(tr=20p tf=20p)",
        ".model logic_dac DAC(tr=20p tf=20p)",
        ".model logic_adc ADC(settlingtime=5p uppervoltagelimit=1.8 lowervoltagelimit=0)",
        "",
        ref_source,
        "",
        *wrapped_instance("XDCO", [dco_nets[port] for port in dco_ports], args.dco_subckt),
        *wrapped_instance("XBBPD", [bbpd_nets[port] for port in bbpd_ports], args.bbpd_subckt),
        "",
        ".print tran v(REF) v(CLKDIVR) v(PLLOUT) v(BBPD[1]) v(BBPD[0]) v(CODE) N(YADC!UP_ADC_STATE) N(YADC!DN_ADC_STATE) N(YADC!PLLOUT_ADC_STATE)",
        f".tran {args.step_ps:g}p {args.sim_time_ns:g}n 0 {args.max_step_ps:g}p{tran_suffix}",
        ".end",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdk-root", default=default_pdk_root())
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
    parser.add_argument("--dco-subckt", default="IntegerPLL_DCO_EINVP_SPARSE72")
    parser.add_argument(
        "--dco-rcx-netlist",
        default=str(
            ROOT
            / "openlane"
            / "IntegerPLL_DCO_EINVP_SPARSE72"
            / "runs"
            / "librelane_signoff"
            / "rcx-magic"
            / "IntegerPLL_DCO_EINVP_SPARSE72.rcx.spice"
        ),
    )
    parser.add_argument("--ref-mhz", type=float, default=25.0)
    parser.add_argument("--clock-sharpness", type=float, default=80.0)
    parser.add_argument("--clock-phase-offset", type=float, default=-0.25)
    parser.add_argument("--ref-source", choices=("pulse", "sine"), default="pulse")
    parser.add_argument("--reset-release-ns", type=float, default=1.0)
    parser.add_argument("--dco-therm-invert", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--step-ps", type=float, default=5.0)
    parser.add_argument("--max-step-ps", type=float, default=25.0)
    parser.add_argument("--sim-time-ns", type=float, default=1600.0)
    parser.add_argument("--tran-uic", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT
        / "build"
        / "xyce_pll_postlayout_dco_mixed_fast200"
        / "pll_postlayout_dco_bbpd.cir",
    )
    args = parser.parse_args()

    if args.ref_mhz <= 0.0 or args.max_step_ps <= 0.0 or args.step_ps <= 0.0:
        raise ValueError("reference frequency and transient steps must be positive")
    if args.sim_time_ns <= 0.0:
        raise ValueError("simulation time must be positive")
    if args.reset_release_ns < 0.0:
        raise ValueError("reset release must be non-negative")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(build_deck(args), encoding="ascii")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
