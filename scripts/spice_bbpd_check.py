#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


RE_FLOAT = r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)"


CASES = {
    "ref_leads": {
        "ref_delay_ns": 5.0,
        "div_delay_ns": 8.0,
        "expected": "up",
    },
    "fb_leads": {
        "ref_delay_ns": 8.0,
        "div_delay_ns": 5.0,
        "expected": "dn",
    },
}


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


def bbpd_netlist(case_name, pdk_root, pdk, corner, sim_time_ns, step_ps):
    case = CASES[case_name]
    pdk_dir = pdk_root / pdk
    model_path = pdk_dir / "libs.tech" / "ngspice" / "sky130.lib.spice"
    cell_path = (
        pdk_dir
        / "libs.ref"
        / "sky130_fd_sc_hd"
        / "spice"
        / "sky130_fd_sc_hd.spice"
    )

    if not model_path.exists():
        raise FileNotFoundError(model_path)
    if not cell_path.exists():
        raise FileNotFoundError(cell_path)

    ref_delay = case["ref_delay_ns"]
    div_delay = case["div_delay_ns"]

    lines = [
            f"* OpenPLL Sky130 BBPD transient validation, case={case_name}",
            f'.lib "{model_path}" {corner}',
            f'.include "{cell_path}"',
            ".option method=gear reltol=1e-4 abstol=1e-15 chgtol=1e-16",
            ".param VDD=1.8",
            "VVPWR VPWR 0 {VDD}",
            "VVPB VPB 0 {VDD}",
            "VVGND VGND 0 0",
            "VVNB VNB 0 0",
            "VD D 0 {VDD}",
            "VRESET RESET_N 0 PULSE(0 {VDD} 1n 20p 20p 50n 100n)",
            f"VREF REF 0 PULSE(0 {{VDD}} {ref_delay}n 20p 20p 2n 100n)",
            f"VDIV CLKDIVR 0 PULSE(0 {{VDD}} {div_delay}n 20p 20p 2n 100n)",
            "",
            "* Two DFF BBPD with delayed cross-reset, matching the RTL macro candidate.",
            "XUPD0 UP_Q VGND VNB VPB VPWR UP_D1 sky130_fd_sc_hd__buf_1",
            "XUPD1 UP_D1 VGND VNB VPB VPWR UP_D2 sky130_fd_sc_hd__buf_1",
            "XDND0 DN_Q VGND VNB VPB VPWR DN_D1 sky130_fd_sc_hd__buf_1",
            "XDND1 DN_D1 VGND VNB VPB VPWR DN_D2 sky130_fd_sc_hd__buf_1",
            "XBOTH UP_D2 DN_D2 VGND VNB VPB VPWR BOTH_HIGH sky130_fd_sc_hd__and2_1",
            "XRST BOTH_HIGH RESET_N VGND VNB VPB VPWR RESET_B sky130_fd_sc_hd__and2b_1",
            "XUPFF REF D RESET_B VGND VNB VPB VPWR UP_Q sky130_fd_sc_hd__dfrtp_1",
            "XDNFF CLKDIVR D RESET_B VGND VNB VPB VPWR DN_Q sky130_fd_sc_hd__dfrtp_1",
            "",
            ".ic v(UP_Q)=0 v(DN_Q)=0 v(UP_D1)=0 v(UP_D2)=0 v(DN_D1)=0 v(DN_D2)=0",
            f".tran {step_ps}p {sim_time_ns}n uic",
            ".meas tran up_max MAX v(UP_Q) FROM=2n TO=20n",
            ".meas tran dn_max MAX v(DN_Q) FROM=2n TO=20n",
    ]

    lines.extend(
        [
            ".meas tran up_width TRIG v(UP_Q) VAL=0.9 RISE=1 TD=2n "
            "TARG v(UP_Q) VAL=0.9 FALL=1 TD=2n",
            ".meas tran dn_width TRIG v(DN_Q) VAL=0.9 RISE=1 TD=2n "
            "TARG v(DN_Q) VAL=0.9 FALL=1 TD=2n",
        ]
    )

    lines.extend([".end", ""])
    return "\n".join(lines)


def run_one(case_name, args, build_dir):
    netlist_path = build_dir / f"bbpd_{case_name}.spice"
    log_path = build_dir / f"bbpd_{case_name}.log"
    netlist_path.write_text(
        bbpd_netlist(
            case_name=case_name,
            pdk_root=Path(args.pdk_root).expanduser().resolve(),
            pdk=args.pdk,
            corner=args.corner,
            sim_time_ns=args.sim_time_ns,
            step_ps=args.step_ps,
        ),
        encoding="ascii",
    )

    proc = subprocess.run(
        [args.ngspice, "-b", str(netlist_path)],
        cwd=build_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log_path.write_text(proc.stdout, encoding="utf-8")

    up_max = measure_value(proc.stdout, "up_max")
    dn_max = measure_value(proc.stdout, "dn_max")
    up_width = measure_value(proc.stdout, "up_width")
    dn_width = measure_value(proc.stdout, "dn_width")

    expected = CASES[case_name]["expected"]
    if expected == "up":
        ok = (
            proc.returncode == 0
            and up_max
            and up_max > 1.2
            and up_width
            and up_width > 0
            and dn_width
            and up_width > dn_width
        )
    else:
        ok = (
            proc.returncode == 0
            and dn_max
            and dn_max > 1.2
            and dn_width
            and dn_width > 0
            and up_width
            and dn_width > up_width
        )

    return {
        "case": case_name,
        "expected": expected,
        "status": "pass" if ok else "fail",
        "up_max_v": up_max or "",
        "dn_max_v": dn_max or "",
        "up_width_s": up_width or "",
        "dn_width_s": dn_width or "",
        "netlist": str(netlist_path),
        "log": str(log_path),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", default="ref_leads,fb_leads")
    parser.add_argument("--pdk-root", default=os.environ.get("PDK_ROOT", "~/.volare"))
    parser.add_argument("--pdk", default=os.environ.get("PDK", "sky130A"))
    parser.add_argument("--corner", default="tt")
    parser.add_argument("--sim-time-ns", type=float, default=30.0)
    parser.add_argument("--step-ps", type=float, default=5.0)
    parser.add_argument("--ngspice", default=shutil.which("ngspice") or "ngspice")
    parser.add_argument(
        "--build-dir",
        default=str(Path(__file__).resolve().parents[1] / "build" / "spice"),
    )
    args = parser.parse_args()

    case_names = [item.strip() for item in args.cases.split(",") if item.strip()]
    for case_name in case_names:
        if case_name not in CASES:
            raise ValueError(f"unknown BBPD case: {case_name}")

    build_dir = Path(args.build_dir).expanduser().resolve()
    build_dir.mkdir(parents=True, exist_ok=True)

    results = [run_one(case_name, args, build_dir) for case_name in case_names]

    csv_path = build_dir / "bbpd_check.csv"
    with csv_path.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "case",
                "expected",
                "status",
                "up_max_v",
                "dn_max_v",
                "up_width_s",
                "dn_width_s",
                "netlist",
                "log",
            ],
        )
        writer.writeheader()
        writer.writerows(results)

    failed = [row for row in results if row["status"] != "pass"]
    for row in results:
        print(
            f"case={row['case']} expected={row['expected']} status={row['status']} "
            f"up_width={row['up_width_s']} dn_width={row['dn_width_s']}"
        )
    print(f"wrote {csv_path}")

    if failed:
        print(f"{len(failed)} BBPD ngspice runs failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
