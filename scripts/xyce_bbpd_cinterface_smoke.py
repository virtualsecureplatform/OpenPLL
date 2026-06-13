#!/usr/bin/env python3
"""Generate a YADC/YDAC C-interface smoke deck for the Sky130 BBPD RCX macro."""

from __future__ import annotations

import argparse
from pathlib import Path
import re

from sky130_pdk import default_pdk_root


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


def build_deck(args) -> str:
    pdk_root = Path(args.pdk_root).expanduser().resolve()
    model_path = pdk_root / args.pdk / "libs.tech" / "ngspice" / "sky130.lib.spice"
    rcx_path = Path(args.rcx_netlist).expanduser().resolve()
    if not model_path.exists():
        raise FileNotFoundError(model_path)
    if not rcx_path.exists():
        raise FileNotFoundError(rcx_path)

    ports = parse_subckt_ports(rcx_path, args.subckt)
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
        raise ValueError(f"unsupported {args.subckt} ports: {', '.join(missing)}")

    lines = [
        "* OpenPLL BBPD RCX mixed-signal C-interface smoke deck.",
        f"* RCX netlist: {rcx_path}",
        f'.lib "{model_path}" {args.corner}',
        f'.include "{rcx_path}"',
        ".param VDD=1.8",
        "VVPWR VPWR 0 {VDD}",
        "VVPB VPB 0 {VDD}",
        "VVGND VGND 0 0",
        "VVNB VNB 0 0",
        "VRESET RESET_N 0 PULSE(0 {VDD} 1n 20p 20p 50n 100n)",
        "YDAC ref_driver REF 0 logic_dac",
        "YDAC div_driver CLKDIVR 0 logic_dac",
        "YADC up_adc BBPD[1] 0 logic_adc R=1T WIDTH=1",
        "YADC dn_adc BBPD[0] 0 logic_adc R=1T WIDTH=1",
        ".model logic_dac DAC(tr=20p tf=20p)",
        ".model logic_adc ADC(settlingtime=5p uppervoltagelimit=1.8 lowervoltagelimit=0)",
        "",
        *wrapped_instance("XBBPD", [port_nets[port] for port in ports], args.subckt),
        "",
        ".print tran v(REF) v(CLKDIVR) v(BBPD[1]) v(BBPD[0]) "
        "N(YADC!UP_ADC_STATE) N(YADC!DN_ADC_STATE)",
        f".tran {args.step_ps:g}p {args.sim_time_ns:g}n",
        ".end",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdk-root", default=default_pdk_root())
    parser.add_argument("--pdk", default="sky130A")
    parser.add_argument("--corner", default="tt")
    parser.add_argument("--subckt", default="IntegerPLL_BBPD")
    parser.add_argument(
        "--rcx-netlist",
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
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "build" / "xyce_bbpd_cinterface_smoke" / "bbpd_yadc_ydac.cir",
    )
    parser.add_argument("--step-ps", type=float, default=2.0)
    parser.add_argument("--sim-time-ns", type=float, default=25.0)
    args = parser.parse_args()

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(build_deck(args), encoding="ascii")
    print(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
