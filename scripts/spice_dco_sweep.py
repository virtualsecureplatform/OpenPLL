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


def enabled_load_count(code, therm_invert):
    count = 0
    for idx in range(255):
        active = idx < code
        if therm_invert:
            active = not active
        if active:
            count += 1
    return count


def monotonic_failures(rows, therm_invert):
    failures = []
    by_corner = {}
    for row in rows:
        by_corner.setdefault(row["corner"], []).append(row)

    for corner, corner_rows in by_corner.items():
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
                        prev["code"],
                        prev_freq,
                        curr["code"],
                        curr_freq,
                        relation,
                    )
                )
    return failures


def load_cell_lines(idx, active, ring_node, load_style):
    if load_style == "nand2":
        ctrl = "VDD" if active else "0"
        return [
            f"VCTRL{idx:03d} C{idx:03d} 0 {{{ctrl}}}",
            f"XLOAD{idx:03d} {ring_node} C{idx:03d} VGND VNB VPB VPWR "
            f"LD{idx:03d} sky130_fd_sc_hd__nand2_1",
        ]
    if load_style == "einvp":
        ctrl = "VDD" if active else "0"
        return [
            f"VCTRL{idx:03d} C{idx:03d} 0 {{{ctrl}}}",
            f"XLOAD{idx:03d} {ring_node} C{idx:03d} VGND VNB VPB VPWR "
            f"LD{idx:03d} sky130_fd_sc_hd__einvp_1",
        ]
    if load_style == "einvn":
        ctrl = "0" if active else "VDD"
        return [
            f"VCTRL{idx:03d} C{idx:03d} 0 {{{ctrl}}}",
            f"XLOAD{idx:03d} {ring_node} C{idx:03d} VGND VNB VPB VPWR "
            f"LD{idx:03d} sky130_fd_sc_hd__einvn_1",
        ]
    if load_style == "dlclkp":
        ctrl = "VDD" if active else "0"
        return [
            f"VCTRL{idx:03d} C{idx:03d} 0 {{{ctrl}}}",
            f"XLOAD{idx:03d} {ring_node} C{idx:03d} VGND VNB VPB VPWR "
            f"LD{idx:03d} sky130_fd_sc_hd__dlclkp_1",
        ]
    raise ValueError(f"unsupported load style: {load_style}")


def dco_netlist(
    code,
    pdk_root,
    pdk,
    corner,
    sim_time_ns,
    step_ps,
    therm_invert,
    ngspice_threads,
    load_style,
    ring_stages,
):
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

    lines = [
        f"* OpenPLL Sky130 8-bit DCO transient validation, code={code}",
        f"* therm_invert={int(therm_invert)}, enabled_loads={enabled_load_count(code, therm_invert)}",
        f"* load_style={load_style}",
        f"* ring_stages={ring_stages}",
        f'.lib "{model_path}" {corner}',
        f'.include "{cell_path}"',
        ".option method=gear reltol=1e-3 abstol=1e-15 chgtol=1e-16"
        + (f" num_threads={ngspice_threads}" if ngspice_threads > 0 else ""),
        ".param VDD=1.8",
        "VVPWR VPWR 0 {VDD}",
        "VVPB VPB 0 {VDD}",
        "VVGND VGND 0 0",
        "VVNB VNB 0 0",
        "VEN EN 0 {VDD}",
        "",
        f"* {ring_stages}-stage enabled ring. Active-low reset behavior is represented",
        "* by the NAND gate enable input held high during this free-run test.",
        f"XOSC N{ring_stages - 1} EN VGND VNB VPB VPWR N0 sky130_fd_sc_hd__nand2_1",
    ]

    for idx in range(1, ring_stages):
        lines.append(
            f"XINV{idx:02d} N{idx - 1} VGND VNB VPB VPWR N{idx} "
            "sky130_fd_sc_hd__inv_1"
        )

    lines.extend(
        [
            "",
            f"* 255 {load_style} varactor/load cells. A high thermometer control",
            "* enables dummy output switching for the active load styles.",
        ]
    )

    for idx in range(255):
        active = idx < code
        if therm_invert:
            active = not active
        ring_node = f"N{idx % ring_stages}"
        lines.extend(load_cell_lines(idx, active, ring_node, load_style))

    lines.extend(
        [
            "",
            "* Alternating initial conditions force startup in batch ngspice.",
        ]
    )

    for idx in range(ring_stages):
        value = "VDD" if idx % 2 else "0"
        lines.append(f".ic v(N{idx})={{{value}}}")

    lines.extend(
        [
            "",
            f".tran {step_ps}p {sim_time_ns}n uic",
            f".meas tran two_cycle_s TRIG v(N{ring_stages - 1}) VAL=0.9 RISE=2 "
            f"TARG v(N{ring_stages - 1}) VAL=0.9 RISE=4",
            ".meas tran period_s PARAM='two_cycle_s/2'",
            ".meas tran freq_hz PARAM='1/period_s'",
            ".end",
            "",
        ]
    )
    return "\n".join(lines)


def dco_result_from_log(code, corner, args, netlist_path, log_path):
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    period = measure_value(log_text, "period_s")
    freq = measure_value(log_text, "freq_hz")
    status = "pass" if period and freq else "fail"
    return {
        "corner": corner,
        "code": code,
        "therm_invert": int(args.therm_invert),
        "enabled_loads": enabled_load_count(code, args.therm_invert),
        "ring_stages": args.ring_stages,
        "status": status,
        "period_s": period or "",
        "freq_hz": freq or "",
        "freq_mhz": (freq / 1.0e6) if freq else "",
        "netlist": str(netlist_path),
        "log": str(log_path),
    }


def existing_result_matches_request(netlist_path, code, corner, args):
    if not netlist_path.exists():
        return False
    text = netlist_path.read_text(encoding="ascii", errors="ignore")
    required_snippets = [
        f"code={code}",
        f"therm_invert={int(args.therm_invert)}",
        f"load_style={args.load_style}",
        f"ring_stages={args.ring_stages}",
        f".lib \"{Path(args.pdk_root).expanduser().resolve() / args.pdk / 'libs.tech' / 'ngspice' / 'sky130.lib.spice'}\" {corner}",
        f".tran {args.step_ps}p {args.sim_time_ns}n uic",
    ]
    if args.ngspice_threads > 0:
        required_snippets.append(f"num_threads={args.ngspice_threads}")
    return all(snippet in text for snippet in required_snippets)


def run_one(code, corner, args, build_dir):
    netlist_path = build_dir / f"dco_{corner}_code_{code:03d}.spice"
    log_path = build_dir / f"dco_{corner}_code_{code:03d}.log"
    if (
        args.resume
        and log_path.exists()
        and existing_result_matches_request(netlist_path, code, corner, args)
    ):
        result = dco_result_from_log(code, corner, args, netlist_path, log_path)
        if result["status"] == "pass":
            result["resumed"] = True
            return result

    netlist_path.write_text(
        dco_netlist(
            code=code,
            pdk_root=Path(args.pdk_root).expanduser().resolve(),
            pdk=args.pdk,
            corner=corner,
            sim_time_ns=args.sim_time_ns,
            step_ps=args.step_ps,
            therm_invert=args.therm_invert,
            ngspice_threads=args.ngspice_threads,
            load_style=args.load_style,
            ring_stages=args.ring_stages,
        ),
        encoding="ascii",
    )

    env = os.environ.copy()
    if args.ngspice_threads > 0:
        env["OMP_NUM_THREADS"] = str(args.ngspice_threads)
    proc = subprocess.run(
        [args.ngspice, "-b", str(netlist_path)],
        cwd=build_dir,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log_path.write_text(proc.stdout, encoding="utf-8")

    period = measure_value(proc.stdout, "period_s")
    freq = measure_value(proc.stdout, "freq_hz")
    status = "pass" if proc.returncode == 0 and period and freq else "fail"
    return {
        "corner": corner,
        "code": code,
        "therm_invert": int(args.therm_invert),
        "enabled_loads": enabled_load_count(code, args.therm_invert),
        "ring_stages": args.ring_stages,
        "status": status,
        "period_s": period or "",
        "freq_hz": freq or "",
        "freq_mhz": (freq / 1.0e6) if freq else "",
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
    parser.add_argument("--pdk-root", default=os.environ.get("PDK_ROOT", "~/.volare"))
    parser.add_argument("--pdk", default=os.environ.get("PDK", "sky130A"))
    parser.add_argument("--corner", default="tt")
    parser.add_argument(
        "--corners",
        default=None,
        help="Comma-separated model corners. Defaults to --corner.",
    )
    parser.add_argument("--sim-time-ns", type=float, default=120.0)
    parser.add_argument("--step-ps", type=float, default=10.0)
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Number of parallel ngspice jobs to run.",
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
    if args.ring_stages < 3 or (args.ring_stages % 2) == 0:
        raise ValueError("--ring-stages must be an odd integer >= 3")

    results = []
    work_items = [(corner, code) for corner in corners for code in codes]
    if args.jobs == 1:
        for corner, code in work_items:
            result = run_one(code, corner, args, build_dir)
            results.append(result)
            print_result(result)
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
            futures = {
                executor.submit(run_one, code, corner, args, build_dir): (corner, code)
                for corner, code in work_items
            }
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                results.append(result)
                print_result(result)

    corner_order = {corner: index for index, corner in enumerate(corners)}
    results.sort(key=lambda row: (corner_order.get(row["corner"], 999), row["code"]))

    csv_path = build_dir / "dco_sweep.csv"
    with csv_path.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "corner",
                "code",
                "therm_invert",
                "enabled_loads",
                "ring_stages",
                "status",
                "period_s",
                "freq_hz",
                "freq_mhz",
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
            for corner, code_a, freq_a, code_b, freq_b, relation in monotonic_errors:
                print(
                    f"nonmonotonic {corner}: expected frequency to {relation} "
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
    if result["status"] == "pass":
        print(
            f"{prefix}corner={result['corner']} code={int(result['code']):3d} "
            f"loads={result['enabled_loads']:3d} "
            f"freq={result['freq_mhz']:.3f} MHz "
            f"period={float(result['period_s']) * 1e9:.3f} ns",
            flush=True,
        )
    else:
        print(
            f"{prefix}corner={result['corner']} code={int(result['code']):3d} "
            f"failed; see {result['log']}",
            flush=True,
        )


if __name__ == "__main__":
    sys.exit(main())
