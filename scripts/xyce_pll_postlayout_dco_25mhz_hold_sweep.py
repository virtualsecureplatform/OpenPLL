#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run direct extracted-DCO mixed-step hold smokes for 25 MHz PLL targets."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import re
import subprocess
import sys
import time

from sky130_pdk import default_pdk_root


ROOT = Path(__file__).resolve().parents[1]

SUMMARY_RE = re.compile(r"^xyce_pll_postlayout_dco_mixed_signal_smoke=(\w+)\s+(.*)$")

TARGETS = {
    100: {
        "coarse_code": 20,
        "target_code": 93,
        "ndiv": 4,
        "freq_tol_mhz": 25.0,
        "min_pllout_rises": 6,
        "cosim_step_ns": 0.1,
    },
    250: {
        "coarse_code": 6,
        "target_code": 234,
        "ndiv": 10,
        "freq_tol_mhz": 25.0,
        "min_pllout_rises": 6,
        "cosim_step_ns": 0.1,
    },
    300: {
        "coarse_code": 4,
        "target_code": 90,
        "ndiv": 12,
        "freq_tol_mhz": 25.0,
        "min_pllout_rises": 8,
        "cosim_step_ns": 0.1,
    },
    400: {
        "coarse_code": 2,
        "target_code": 76,
        "ndiv": 16,
        "freq_tol_mhz": 25.0,
        "min_pllout_rises": 8,
        "cosim_step_ns": 0.1,
    },
    500: {
        "coarse_code": 1,
        "target_code": 121,
        "ndiv": 20,
        "freq_tol_mhz": 25.0,
        "min_pllout_rises": 10,
        "cosim_step_ns": 0.1,
    },
}


def resolve_repo_path(path: Path) -> Path:
    path = path.expanduser()
    if not path.is_absolute():
        path = ROOT / path
    return path.resolve()


def artifact_path_text(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def parse_targets(text: str) -> list[int]:
    result = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        target = int(item, 0)
        if target not in TARGETS:
            raise argparse.ArgumentTypeError(
                f"unsupported target {target}; expected one of {sorted(TARGETS)}"
            )
        if target not in result:
            result.append(target)
    if not result:
        raise argparse.ArgumentTypeError("expected at least one target")
    return result


def parse_summary_line(text: str) -> dict[str, str]:
    for line in text.splitlines():
        match = SUMMARY_RE.match(line.strip())
        if not match:
            continue
        values = {"status": match.group(1)}
        for token in match.group(2).split():
            if "=" not in token:
                continue
            key, value = token.split("=", 1)
            values[key] = value
        return values
    return {}


def parse_measure_line(text: str) -> dict[str, str]:
    header: list[str] | None = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("measure,start_ns,"):
            header = line.split(",")
            continue
        if header is not None and line.startswith("measure,"):
            values = line.split(",")
            if len(values) == len(header):
                return dict(zip(header, values))
    return {}


def print_driver_excerpt(text: str) -> None:
    for line in text.splitlines():
        if (
            line.startswith("cycle,")
            or re.match(r"^\d+,", line)
            or line.startswith("measure,")
            or line.startswith("xyce_pll_postlayout_dco_mixed_signal_smoke=")
        ):
            print(line, flush=True)


def completed_pass(
    log_path: Path,
    args: argparse.Namespace,
    target_mhz: int,
    target_code: int,
) -> tuple[dict[str, str], dict[str, str]] | None:
    if not log_path.exists():
        return None
    text = log_path.read_text(encoding="utf-8", errors="replace")
    summary = parse_summary_line(text)
    if summary.get("status") != "pass":
        return None
    if summary.get("target_code") != str(target_code):
        return None
    if summary.get("target_mhz") != f"{float(target_mhz):.3f}":
        return None
    measure = parse_measure_line(text)
    if measure:
        tref_ns = 1000.0 / args.ref_mhz
        expected_start_ns = args.start_ns + args.cycles * tref_ns + args.measure_settle_ns
        expected_end_ns = args.start_ns + (args.cycles + args.measure_cycles) * tref_ns
        try:
            start_ns = float(measure["start_ns"])
            end_ns = float(measure["end_ns"])
        except (KeyError, ValueError):
            return None
        if abs(start_ns - expected_start_ns) > 1.0e-3:
            return None
        if abs(end_ns - expected_end_ns) > 1.0e-3:
            return None
    return summary, measure


def target_paths(build_dir: Path, target_mhz: int, coarse_code: int, target_code: int) -> tuple[Path, Path]:
    deck = build_dir / f"target{target_mhz}_c{coarse_code:02d}.cir"
    log = build_dir / f"target{target_mhz}_c{coarse_code:02d}_code{target_code:03d}_hold.log"
    return deck, log


def generate_deck(args: argparse.Namespace, target_mhz: int, coarse_code: int, deck: Path) -> None:
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "xyce_pll_postlayout_dco_cinterface_deck.py"),
        "--pdk-root",
        str(args.pdk_root),
        "--pdk",
        args.pdk,
        "--out",
        str(deck),
        "--ref-mhz",
        f"{args.ref_mhz:g}",
        "--dco-subckt",
        args.dco_subckt,
        "--dco-rcx-netlist",
        str(args.dco_rcx_netlist),
        "--coarse-code",
        str(coarse_code),
        "--sim-time-ns",
        f"{args.sim_time_ns:g}",
        "--step-ps",
        f"{args.step_ps:g}",
        "--max-step-ps",
        f"{args.max_step_ps:g}",
        "--clock-sharpness",
        f"{args.clock_sharpness:g}",
        "--clock-phase-offset",
        f"{args.clock_phase_offset:g}",
        "--reset-release-ns",
        f"{args.reset_release_ns:g}",
        "--ref-source",
        args.ref_source,
    ]
    if args.pllout_isolation_buffer_drive:
        cmd.extend(
            [
                "--pllout-isolation-buffer-drive",
                str(args.pllout_isolation_buffer_drive),
            ]
        )
    subprocess.run(cmd, cwd=ROOT, check=True)


def run_target(args: argparse.Namespace, target_mhz: int) -> dict[str, str]:
    cfg = TARGETS[target_mhz]
    coarse_code = int(cfg["coarse_code"])
    target_code = int(cfg["target_code"])
    deck, log = target_paths(args.build_dir, target_mhz, coarse_code, target_code)
    generate_deck(args, target_mhz, coarse_code, deck)

    resumed = False
    completed = completed_pass(log, args, target_mhz, target_code) if args.resume else None
    if completed is not None:
        summary, measure = completed
        resumed = True
        print(f"target{target_mhz}_c{coarse_code:02d}_code{target_code:03d}: resumed pass", flush=True)
    else:
        cmd = [
            str(args.driver),
            str(deck),
            "--init-code",
            str(target_code),
            "--target-code",
            str(target_code),
            "--cycles",
            str(args.cycles),
            "--ki",
            "0",
            "--kp",
            "0",
            "--frac",
            str(args.frac),
            "--ref-mhz",
            f"{args.ref_mhz:g}",
            "--ndiv",
            str(int(cfg["ndiv"])),
            "--target-mhz",
            str(target_mhz),
            "--freq-tol-mhz",
            f"{float(cfg['freq_tol_mhz']):g}",
            "--measure-cycles",
            str(args.measure_cycles),
            "--measure-settle-ns",
            f"{args.measure_settle_ns:g}",
            "--min-pllout-rises",
            str(int(cfg["min_pllout_rises"])),
            "--expect",
            args.expect,
            "--min-motion",
            "0",
            "--tol-code",
            "0",
            "--start-ns",
            f"{args.start_ns:g}",
            "--cosim-step-ns",
            f"{float(cfg['cosim_step_ns']):g}",
            "--divider-latency-ps",
            f"{args.divider_latency_ps:g}",
            "--initial-divider-count",
            str(args.initial_divider_count),
            "--no-warmup-divider",
            "--prop-rail-guard",
        ]
        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                cwd=ROOT,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=args.timeout_s,
                check=False,
            )
            output = proc.stdout
            returncode = proc.returncode
        except subprocess.TimeoutExpired as exc:
            output = (exc.stdout or "") + f"\nOpenPLL timeout after {args.timeout_s:.1f} s\n"
            returncode = 124
        elapsed_s = time.monotonic() - start
        log.write_text(output, encoding="utf-8", errors="replace")
        print_driver_excerpt(output)
        summary = parse_summary_line(output)
        measure = parse_measure_line(output)
        if returncode != 0 or summary.get("status") != "pass":
            raise RuntimeError(
                f"target {target_mhz} MHz direct-RCX hold failed; "
                f"see {artifact_path_text(log)}"
            )
        summary["elapsed_s"] = f"{elapsed_s:.3f}"

    return {
        "target_mhz": str(target_mhz),
        "ref_mhz": f"{args.ref_mhz:.6f}",
        "multiplier": str(int(cfg["ndiv"])),
        "coarse_code": str(coarse_code),
        "target_code": str(target_code),
        "status": summary.get("status", ""),
        "final_code": summary.get("final_code", ""),
        "expected_decisions": summary.get("expected_decisions", ""),
        "measured_mhz": summary.get("measured_mhz", measure.get("measured_mhz", "")),
        "target_freq_mhz": summary.get("target_mhz", measure.get("target_mhz", "")),
        "freq_abs_error_mhz": summary.get(
            "freq_abs_error_mhz", measure.get("freq_abs_error_mhz", "")
        ),
        "freq_tol_mhz": f"{float(cfg['freq_tol_mhz']):g}",
        "pllout_rises": summary.get("pllout_rises", measure.get("pllout_rises", "")),
        "cosim_step_ns": f"{float(cfg['cosim_step_ns']):g}",
        "resumed": "1" if resumed else "0",
        "elapsed_s": summary.get("elapsed_s", ""),
        "deck": artifact_path_text(deck),
        "log": artifact_path_text(log),
    }


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    fields = [
        "target_mhz",
        "ref_mhz",
        "multiplier",
        "coarse_code",
        "target_code",
        "status",
        "final_code",
        "expected_decisions",
        "measured_mhz",
        "target_freq_mhz",
        "freq_abs_error_mhz",
        "freq_tol_mhz",
        "pllout_rises",
        "cosim_step_ns",
        "resumed",
        "elapsed_s",
        "deck",
        "log",
    ]
    with path.open("w", encoding="ascii", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--driver",
        type=Path,
        default=ROOT / "build" / "xyce_cinterface_smoke_mpi" / "xyce_pll_postlayout_dco_mixed_signal_smoke",
    )
    parser.add_argument("--pdk-root", type=Path, default=Path(default_pdk_root()))
    parser.add_argument("--pdk", default="sky130A")
    parser.add_argument("--targets-mhz", type=parse_targets, default=parse_targets("100,250,300,400,500"))
    parser.add_argument("--ref-mhz", type=float, default=25.0)
    parser.add_argument(
        "--dco-subckt",
        default="IntegerPLL_DCO_EINVP_COARSE",
    )
    parser.add_argument(
        "--dco-rcx-netlist",
        type=Path,
        default=ROOT
        / "openlane"
        / "IntegerPLL_DCO_EINVP_COARSE"
        / "runs"
        / "librelane_signoff"
        / "rcx-magic"
        / "IntegerPLL_DCO_EINVP_COARSE.rcx.spice",
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=ROOT / "build" / "xyce_pll_postlayout_dco_mixed_25mhz_coarse",
    )
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--frac", type=int, default=2)
    parser.add_argument("--measure-cycles", type=int, default=2)
    parser.add_argument("--measure-settle-ns", type=float, default=5.0)
    parser.add_argument("--start-ns", type=float, default=8.0)
    parser.add_argument("--divider-latency-ps", type=float, default=50.0)
    parser.add_argument("--initial-divider-count", type=int, default=0)
    parser.add_argument("--expect", choices=("increase", "decrease"), default="increase")
    parser.add_argument("--sim-time-ns", type=float, default=160.0)
    parser.add_argument("--step-ps", type=float, default=20.0)
    parser.add_argument("--max-step-ps", type=float, default=100.0)
    parser.add_argument("--clock-sharpness", type=float, default=80.0)
    parser.add_argument("--clock-phase-offset", type=float, default=-0.25)
    parser.add_argument("--reset-release-ns", type=float, default=1.0)
    parser.add_argument("--ref-source", choices=("pulse", "sine"), default="pulse")
    parser.add_argument(
        "--pllout-isolation-buffer-drive",
        type=int,
        default=0,
        help="Optionally insert an HS output isolation buffer in generated decks.",
    )
    parser.add_argument("--timeout-s", type=float, default=1200.0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    args.driver = resolve_repo_path(args.driver)
    args.pdk_root = args.pdk_root.expanduser().resolve()
    args.dco_rcx_netlist = resolve_repo_path(args.dco_rcx_netlist)
    args.build_dir = resolve_repo_path(args.build_dir)
    args.build_dir.mkdir(parents=True, exist_ok=True)

    if not args.driver.exists():
        raise FileNotFoundError(args.driver)
    if not (args.pdk_root / args.pdk / "libs.tech" / "ngspice" / "sky130.lib.spice").exists():
        raise FileNotFoundError(args.pdk_root / args.pdk / "libs.tech" / "ngspice" / "sky130.lib.spice")
    if not args.dco_rcx_netlist.exists():
        raise FileNotFoundError(args.dco_rcx_netlist)
    if args.pllout_isolation_buffer_drive not in (0, 1, 2, 4, 8, 16):
        raise ValueError("PLLOUT isolation buffer drive must be one of 0, 1, 2, 4, 8, 16")

    rows = [run_target(args, target) for target in args.targets_mhz]
    status = "pass" if all(row["status"] == "pass" for row in rows) else "fail"
    csv_path = args.build_dir / "pll_postlayout_dco_25mhz_hold_summary.csv"
    json_path = args.build_dir / "pll_postlayout_dco_25mhz_hold_summary.json"
    write_csv(csv_path, rows)
    output = {
        "status": status,
        "ref_mhz": args.ref_mhz,
        "targets_mhz": args.targets_mhz,
        "summary_csv": artifact_path_text(csv_path),
        "target_results": rows,
    }
    json_path.write_text(json.dumps(output, indent=2) + "\n", encoding="ascii")
    print(json.dumps(output, indent=2))
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
