#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import re
import shutil
import subprocess
import sys
from pathlib import Path

from sky130_pdk import default_pdk_root


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

DEFAULT_DEADZONE_OFFSETS_PS = "0,1,2,5,10,20,50,100,200,500,1000"


def spice_number(value):
    if abs(value - round(value)) < 1e-9:
        return str(int(round(value)))
    return f"{value:g}"


def measure_value(log_text, name):
    for pattern in (
        rf"^\s*{name}\s*=\s*{RE_FLOAT}",
        rf"^\s*{name}\s*:\s*{RE_FLOAT}",
    ):
        match = re.search(pattern, log_text, re.IGNORECASE | re.MULTILINE)
        if match:
            return float(match.group(1))
    return None


def parse_subckt_ports(rcx_netlist, subckt_name="IntegerPLL_BBPD"):
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


def wrapped_instance(name, ports, subckt_name):
    return [f"{name} {' '.join(ports)} {subckt_name}"]


def bbpd_netlist(case_name, args, ports, corner, case, sim_time_ns=None):
    sim_time_ns = args.sim_time_ns if sim_time_ns is None else sim_time_ns
    measure_to_ns = args.measure_to_ns if args.measure_to_ns is not None else sim_time_ns
    measure_to_label = spice_number(measure_to_ns)
    pdk_root = Path(args.pdk_root).expanduser().resolve()
    model_path = pdk_root / args.pdk / "libs.tech" / "ngspice" / "sky130.lib.spice"
    rcx_path = Path(args.rcx_netlist).expanduser().resolve()
    if not model_path.exists():
        raise FileNotFoundError(model_path)
    if not rcx_path.exists():
        raise FileNotFoundError(rcx_path)

    lines = [
        f"* OpenPLL BBPD post-layout transient validation, corner={corner}, case={case_name}",
        f"* RCX netlist: {rcx_path}",
        f'.lib "{model_path}" {corner}',
        f'.include "{rcx_path}"',
        ".option method=gear reltol=1e-4 abstol=1e-15 chgtol=1e-16",
        ".param VDD=1.8",
        "VVPWR VPWR 0 {VDD}",
        "VVPB VPB 0 {VDD}",
        "VVGND VGND 0 0",
        "VVNB VNB 0 0",
        "VRESET RESET_N 0 PULSE(0 {VDD} 1n 20p 20p 50n 100n)",
        f"VREF REF 0 PULSE(0 {{VDD}} {case['ref_delay_ns']}n 20p 20p 2n 100n)",
        f"VDIV CLKDIVR 0 PULSE(0 {{VDD}} {case['div_delay_ns']}n 20p 20p 2n 100n)",
        "",
        *wrapped_instance("XDUT", ports, "IntegerPLL_BBPD"),
        "",
        ".save v(BBPD[1]) v(BBPD[0])",
        ".ic v(BBPD[1])=0 v(BBPD[0])=0 "
        "v(XDUT.up_ff.q)=0 v(XDUT.dn_ff.q)=0 "
        "v(XDUT.up_delay_0.x)=0 v(XDUT.up_delay_1.x)=0 "
        "v(XDUT.dn_delay_0.x)=0 v(XDUT.dn_delay_1.x)=0 "
        "v(XDUT.dn_ff.reset_b)=0",
        f".tran {args.step_ps}p {sim_time_ns}n uic",
        f".meas tran up_max MAX v(BBPD[1]) FROM=2n TO={measure_to_label}n",
        f".meas tran dn_max MAX v(BBPD[0]) FROM=2n TO={measure_to_label}n",
        ".meas tran up_width TRIG v(BBPD[1]) VAL=0.9 RISE=1 TD=2n "
        "TARG v(BBPD[1]) VAL=0.9 FALL=1 TD=2n",
        ".meas tran dn_width TRIG v(BBPD[0]) VAL=0.9 RISE=1 TD=2n "
        "TARG v(BBPD[0]) VAL=0.9 FALL=1 TD=2n",
        ".end",
        "",
    ]
    return "\n".join(lines)


def measured_polarity(up_width, dn_width, min_diff_ps):
    if up_width is None or dn_width is None:
        return "unknown", None
    diff_ps = (up_width - dn_width) * 1.0e12
    if diff_ps > min_diff_ps:
        return "up", diff_ps
    if diff_ps < -min_diff_ps:
        return "dn", diff_ps
    return "tie", diff_ps


def polarity_ok(expected, polarity):
    if expected == "tie":
        return polarity in {"up", "dn", "tie"}
    return polarity == expected


def row_from_log(
    case_name,
    corner,
    args,
    case,
    characterize,
    netlist_path,
    log_path,
    log_text,
    returncode,
    resumed,
    retry,
):
    up_max = measure_value(log_text, "up_max")
    dn_max = measure_value(log_text, "dn_max")
    up_width = measure_value(log_text, "up_width")
    dn_width = measure_value(log_text, "dn_width")
    expected = case["expected"]
    polarity, width_diff_ps = measured_polarity(up_width, dn_width, args.min_diff_ps)
    has_valid_pulses = (
        returncode == 0
        and up_max is not None
        and dn_max is not None
        and up_width is not None
        and dn_width is not None
        and up_max > 1.2
        and dn_max > 1.2
        and up_width > 0
        and dn_width > 0
    )
    polarity_matches = polarity_ok(expected, polarity)
    ok = has_valid_pulses and (characterize or polarity_matches)

    return {
        "corner": corner,
        "case": case_name,
        "expected": expected,
        "status": "pass" if ok else "fail",
        "resumed": "yes" if resumed else "no",
        "retry": "yes" if retry else "no",
        "phase_offset_ps": case.get("phase_offset_ps", ""),
        "polarity": polarity,
        "polarity_ok": "yes" if polarity_matches else "no",
        "width_diff_ps": width_diff_ps if width_diff_ps is not None else "",
        "up_max_v": up_max or "",
        "dn_max_v": dn_max or "",
        "up_width_s": up_width or "",
        "dn_width_s": dn_width or "",
        "ref_delay_ns": case["ref_delay_ns"],
        "div_delay_ns": case["div_delay_ns"],
        "netlist": str(netlist_path),
        "log": str(log_path),
    }


def can_resume(args, netlist_path, log_path, netlist_text):
    if not args.resume or not netlist_path.exists() or not log_path.exists():
        return False
    old_netlist = netlist_path.read_text(encoding="ascii", errors="replace")
    return old_netlist == netlist_text


def run_or_resume(
    case_name,
    corner,
    args,
    build_dir,
    case,
    characterize,
    netlist_path,
    log_path,
    netlist_text,
    retry=False,
):
    if can_resume(args, netlist_path, log_path, netlist_text):
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        row = row_from_log(
            case_name,
            corner,
            args,
            case,
            characterize,
            netlist_path,
            log_path,
            log_text,
            0,
            True,
            retry,
        )
        if row["status"] == "pass":
            return row

    netlist_path.write_text(netlist_text, encoding="ascii")
    proc = subprocess.run(
        [args.ngspice, "-b", str(netlist_path)],
        cwd=build_dir,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log_path.write_text(proc.stdout, encoding="utf-8")
    return row_from_log(
        case_name,
        corner,
        args,
        case,
        characterize,
        netlist_path,
        log_path,
        proc.stdout,
        proc.returncode,
        False,
        retry,
    )


def run_one(case_name, corner, args, ports, build_dir, case, characterize=False):
    netlist_path = build_dir / f"bbpd_postlayout_{corner}_{case_name}.spice"
    log_path = build_dir / f"bbpd_postlayout_{corner}_{case_name}.log"
    retry_netlist_path = build_dir / f"bbpd_postlayout_{corner}_{case_name}_retry.spice"
    retry_log_path = build_dir / f"bbpd_postlayout_{corner}_{case_name}_retry.log"
    if args.retry_sim_time_ns is not None:
        retry_text = bbpd_netlist(
            case_name,
            args,
            ports,
            corner,
            case,
            sim_time_ns=args.retry_sim_time_ns,
        )
        if can_resume(args, retry_netlist_path, retry_log_path, retry_text):
            retry_log = retry_log_path.read_text(encoding="utf-8", errors="replace")
            retry_row = row_from_log(
                case_name,
                corner,
                args,
                case,
                characterize,
                retry_netlist_path,
                retry_log_path,
                retry_log,
                0,
                True,
                True,
            )
            if retry_row["status"] == "pass":
                return retry_row

    netlist_text = bbpd_netlist(case_name, args, ports, corner, case)
    row = run_or_resume(
        case_name,
        corner,
        args,
        build_dir,
        case,
        characterize,
        netlist_path,
        log_path,
        netlist_text,
    )
    if row["status"] == "pass" or args.retry_sim_time_ns is None:
        return row

    retry_text = bbpd_netlist(
        case_name,
        args,
        ports,
        corner,
        case,
        sim_time_ns=args.retry_sim_time_ns,
    )
    return run_or_resume(
        case_name,
        corner,
        args,
        build_dir,
        case,
        characterize,
        retry_netlist_path,
        retry_log_path,
        retry_text,
        retry=True,
    )


def parse_float_list(text, default_text=None):
    if text == "default":
        text = default_text
    values = []
    for item in text.split(","):
        item = item.strip()
        if item:
            values.append(float(item))
    return values


def format_ps(value):
    if abs(value - round(value)) < 1e-9:
        return f"{int(round(value))}"
    return f"{value:g}".replace(".", "p")


def build_cases(args):
    if not args.phase_offsets_ps:
        case_names = [item.strip() for item in args.cases.split(",") if item.strip()]
        cases = []
        for case_name in case_names:
            if case_name not in CASES:
                raise ValueError(f"unknown BBPD case: {case_name}")
            cases.append((case_name, dict(CASES[case_name]), False))
        return cases

    offsets = parse_float_list(args.phase_offsets_ps, DEFAULT_DEADZONE_OFFSETS_PS)
    if not offsets:
        raise ValueError("--phase-offsets-ps did not contain any offsets")
    if any(offset < 0 for offset in offsets):
        raise ValueError("--phase-offsets-ps expects absolute, non-negative offsets")

    cases = []
    seen_offsets = set()
    for offset in offsets:
        if offset in seen_offsets:
            continue
        seen_offsets.add(offset)
        suffix = format_ps(offset)
        if offset == 0:
            cases.append(
                (
                    f"tie_{suffix}ps",
                    {
                        "ref_delay_ns": args.base_edge_ns,
                        "div_delay_ns": args.base_edge_ns,
                        "expected": "tie",
                        "phase_offset_ps": 0.0,
                    },
                    True,
                )
            )
            continue
        cases.append(
            (
                f"ref_leads_{suffix}ps",
                {
                    "ref_delay_ns": args.base_edge_ns,
                    "div_delay_ns": args.base_edge_ns + offset / 1000.0,
                    "expected": "up",
                    "phase_offset_ps": offset,
                },
                True,
            )
        )
        cases.append(
            (
                f"fb_leads_{suffix}ps",
                {
                    "ref_delay_ns": args.base_edge_ns + offset / 1000.0,
                    "div_delay_ns": args.base_edge_ns,
                    "expected": "dn",
                    "phase_offset_ps": -offset,
                },
                True,
            )
        )
    return cases


def write_deadzone_summary(results, build_dir):
    if not any(row["phase_offset_ps"] != "" for row in results):
        return None

    summary_rows = []
    for corner in sorted({row["corner"] for row in results}):
        rows = [row for row in results if row["corner"] == corner]
        tie_rows = [row for row in rows if row["expected"] == "tie"]
        positive_ok = [
            abs(float(row["phase_offset_ps"]))
            for row in rows
            if row["expected"] == "up" and row["polarity_ok"] == "yes"
        ]
        negative_ok = [
            abs(float(row["phase_offset_ps"]))
            for row in rows
            if row["expected"] == "dn" and row["polarity_ok"] == "yes"
        ]
        polarity_bad = [
            row
            for row in rows
            if row["expected"] in {"up", "dn"} and row["polarity_ok"] != "yes"
        ]
        failed = [row for row in rows if row["status"] != "pass"]
        zero_diff = tie_rows[0]["width_diff_ps"] if tie_rows else ""
        summary_rows.append(
            {
                "corner": corner,
                "min_ref_leads_correct_ps": min(positive_ok) if positive_ok else "",
                "min_fb_leads_correct_ps": min(negative_ok) if negative_ok else "",
                "zero_offset_width_diff_ps": zero_diff,
                "polarity_bad_rows": len(polarity_bad),
                "failed_rows": len(failed),
            }
        )

    summary_path = build_dir / "bbpd_deadzone_summary.csv"
    with summary_path.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(summary_rows[0].keys()))
        writer.writeheader()
        writer.writerows(summary_rows)
    return summary_path


def main():
    parser = argparse.ArgumentParser(description="Run BBPD post-layout RCX transient SPICE.")
    parser.add_argument("--cases", default="ref_leads,fb_leads")
    parser.add_argument("--pdk-root", default=default_pdk_root())
    parser.add_argument("--pdk", default="sky130A")
    parser.add_argument("--corner", default="tt")
    parser.add_argument(
        "--corners",
        default=None,
        help="Comma-separated model corners. Defaults to --corner.",
    )
    parser.add_argument(
        "--rcx-netlist",
        default="openlane/IntegerPLL_BBPD/runs/librelane_signoff/rcx-magic/IntegerPLL_BBPD.rcx.spice",
    )
    parser.add_argument("--build-dir", default="build/spice_bbpd_postlayout")
    parser.add_argument("--sim-time-ns", type=float, default=30.0)
    parser.add_argument(
        "--retry-sim-time-ns",
        type=float,
        default=None,
        help="Retry failed cases with a shorter transient stop time.",
    )
    parser.add_argument(
        "--measure-to-ns",
        type=float,
        default=None,
        help="Stop time for MAX measurements. Defaults to the transient stop time.",
    )
    parser.add_argument("--step-ps", type=float, default=5.0)
    parser.add_argument("--base-edge-ns", type=float, default=8.0)
    parser.add_argument(
        "--phase-offsets-ps",
        default=None,
        help=(
            "Comma-separated absolute offsets for a dead-zone sweep, or 'default'. "
            "When set, both REF-leads and feedback-leads cases are generated."
        ),
    )
    parser.add_argument(
        "--min-diff-ps",
        type=float,
        default=0.0,
        help="Minimum UP-DN pulse-width difference required to call polarity non-tie.",
    )
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse existing matching passing netlists/logs in the build directory.",
    )
    parser.add_argument("--ngspice", default=shutil.which("ngspice") or "ngspice")
    args = parser.parse_args()

    run_cases = build_cases(args)
    corners = (
        [item.strip() for item in args.corners.split(",") if item.strip()]
        if args.corners
        else [args.corner]
    )

    ports = parse_subckt_ports(args.rcx_netlist)
    required_ports = {"BBPD[0]", "BBPD[1]", "CLKDIVR", "REF", "RESET_N", "VGND", "VNB", "VPB", "VPWR"}
    missing_ports = required_ports - set(ports)
    if missing_ports:
        raise ValueError(f"RCX netlist missing ports: {sorted(missing_ports)}")

    build_dir = Path(args.build_dir).resolve()
    build_dir.mkdir(parents=True, exist_ok=True)

    tasks = [
        (case_name, corner, case, characterize)
        for corner in corners
        for case_name, case, characterize in run_cases
    ]
    if args.jobs <= 1:
        results = [
            run_one(case_name, corner, args, ports, build_dir, case, characterize)
            for case_name, corner, case, characterize in tasks
        ]
    else:
        results = []
        with ThreadPoolExecutor(max_workers=args.jobs) as executor:
            future_to_task = {
                executor.submit(
                    run_one,
                    case_name,
                    corner,
                    args,
                    ports,
                    build_dir,
                    case,
                    characterize,
                ): (case_name, corner)
                for case_name, corner, case, characterize in tasks
            }
            for future in as_completed(future_to_task):
                results.append(future.result())

    corner_order = {corner: idx for idx, corner in enumerate(corners)}
    results.sort(
        key=lambda row: (
            corner_order[row["corner"]],
            abs(float(row["phase_offset_ps"])) if row["phase_offset_ps"] != "" else -1.0,
            float(row["phase_offset_ps"]) if row["phase_offset_ps"] != "" else 0.0,
            row["case"],
        )
    )
    csv_path = build_dir / "bbpd_postlayout_check.csv"
    with csv_path.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(results[0].keys()))
        writer.writeheader()
        writer.writerows(results)
    summary_path = write_deadzone_summary(results, build_dir)

    failed = [row for row in results if row["status"] != "pass"]
    for row in results:
        phase = (
            f" phase={float(row['phase_offset_ps']):g}ps"
            if row["phase_offset_ps"] != ""
            else ""
        )
        print(
            f"corner={row['corner']} case={row['case']}{phase} "
            f"expected={row['expected']} polarity={row['polarity']} "
            f"polarity_ok={row['polarity_ok']} status={row['status']} "
            f"resumed={row['resumed']} retry={row['retry']} "
            f"up_width={row['up_width_s']} dn_width={row['dn_width_s']} "
            f"diff_ps={row['width_diff_ps']}"
        )
    print(f"wrote {csv_path}")
    if summary_path:
        print(f"wrote {summary_path}")

    if failed:
        print(f"{len(failed)} BBPD post-layout ngspice runs failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
