#!/usr/bin/env python3
"""Check whether the Xyce app-note mixed-signal interface is usable."""

from __future__ import annotations

import argparse
import ctypes.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def command_words(command: str) -> list[str]:
    words = shlex.split(command)
    if not words:
        raise ValueError("empty Xyce command")
    executable = words[0]
    if "/" not in executable:
        resolved = shutil.which(executable)
        if resolved is None:
            raise FileNotFoundError(f"Xyce executable not found in PATH: {executable}")
        words[0] = resolved
    return words


def run_command(words: list[str], *, cwd: Path | None = None, timeout_s: float = 30.0):
    return subprocess.run(
        words,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout_s,
        check=False,
    )


def candidate_lib_dirs(args) -> list[Path]:
    raw_dirs = []
    raw_dirs.extend(args.xyce_lib_dir or [])
    raw_dirs.extend(os.environ.get("XYCE_LIB_DIR", "").split(os.pathsep))
    raw_dirs.extend(
        [
            "/home/ubuntu/.local/xyce-mpi/lib",
            "/usr/local/lib",
            "/usr/local/Xyce/lib",
        ]
    )
    dirs = []
    seen = set()
    for raw_dir in raw_dirs:
        if not raw_dir:
            continue
        path = Path(raw_dir).expanduser()
        key = str(path)
        if key not in seen:
            dirs.append(path)
            seen.add(key)
    return dirs


def find_shared_interface(lib_dirs: list[Path]) -> tuple[str | None, list[str]]:
    checked = []
    loader_name = ctypes.util.find_library("xycecinterface")
    if loader_name:
        return loader_name, ["dynamic loader search path"]
    for lib_dir in lib_dirs:
        for filename in (
            "libxycecinterface.so",
            "libxycecinterface.dylib",
            "xycecinterface.dll",
        ):
            candidate = lib_dir / filename
            checked.append(str(candidate))
            if candidate.exists():
                return str(candidate), checked
    return None, checked


def candidate_build_dirs(args) -> list[Path]:
    raw_dirs = []
    if args.xyce_build_dir:
        raw_dirs.append(args.xyce_build_dir)
    raw_dirs.extend(os.environ.get("XYCE_BUILD_DIR", "").split(os.pathsep))
    raw_dirs.append("/home/ubuntu/builds/xyce/xyce-mpi")
    dirs = []
    seen = set()
    for raw_dir in raw_dirs:
        if not raw_dir:
            continue
        path = Path(raw_dir).expanduser()
        key = str(path)
        if key not in seen:
            dirs.append(path)
            seen.add(key)
    return dirs


def find_static_interface(build_dirs: list[Path]) -> tuple[str | None, list[str]]:
    checked = []
    for build_dir in build_dirs:
        candidate = build_dir / "utils" / "XyceCInterface" / "libxycecinterface.a"
        checked.append(str(candidate))
        if candidate.exists():
            return str(candidate), checked
    return None, checked


def candidate_share_dirs(args, xyce_words: list[str]) -> list[Path]:
    raw_dirs = []
    raw_dirs.extend(args.xyce_share or [])
    raw_dirs.extend(os.environ.get("XYCE_SHARE", "").split(os.pathsep))
    xyce_path = Path(xyce_words[0]).resolve()
    raw_dirs.append(str(xyce_path.parent.parent / "share"))
    raw_dirs.extend(
        [
            "/home/ubuntu/.local/xyce-mpi/share",
            "/usr/local/share",
            "/usr/local/Xyce/share",
        ]
    )
    dirs = []
    seen = set()
    for raw_dir in raw_dirs:
        if not raw_dir:
            continue
        path = Path(raw_dir).expanduser()
        key = str(path)
        if key not in seen:
            dirs.append(path)
            seen.add(key)
    return dirs


def find_xyce_interface_py(share_dirs: list[Path]) -> tuple[str | None, list[str]]:
    checked = []
    for share_dir in share_dirs:
        candidate = share_dir / "xyce_interface.py"
        checked.append(str(candidate))
        if candidate.exists():
            return str(candidate), checked
    return None, checked


def run_bridge_device_probe(xyce_words: list[str], build_dir: Path):
    build_dir.mkdir(parents=True, exist_ok=True)
    deck = build_dir / "yadc_ydac_probe.cir"
    deck.write_text(
        "\n".join(
            [
                "* Xyce YADC/YDAC syntax probe only.",
                "YDAC dac1 out 0 dacmod",
                "Rload out 0 1k",
                "YADC adc1 out 0 adcmod R=1T WIDTH=1",
                ".model dacmod DAC(tr=1n tf=1n)",
                ".model adcmod ADC(settlingtime=1n uppervoltagelimit=1.8 lowervoltagelimit=0)",
                ".print tran v(out) N(YADC!ADC1_STATE)",
                ".tran 1n 2n",
                ".end",
                "",
            ]
        ),
        encoding="ascii",
    )
    result = run_command(xyce_words + [str(deck)], cwd=build_dir, timeout_s=30.0)
    log_path = build_dir / "yadc_ydac_probe.log"
    log_path.write_text(result.stdout, encoding="utf-8", errors="replace")
    return {
        "ok": result.returncode == 0,
        "returncode": result.returncode,
        "deck": str(deck),
        "log": str(log_path),
    }


def classify_deck(path: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    has_yadc = re.search(r"(?im)^\s*yadc", text) is not None
    has_ydac = re.search(r"(?im)^\s*ydac", text) is not None
    has_std_cell_spice = "sky130_fd_sc_hd.spice" in text
    has_sky130_cells = "sky130_fd_sc_hd__" in text
    has_mapped_label = "Full synthesized Sky130 digital-core mapped netlist" in text
    if has_yadc or has_ydac:
        classification = "xyce_bridge_device_deck"
    elif has_std_cell_spice or has_sky130_cells or has_mapped_label:
        classification = "all_spice_mapped_digital_transient"
    else:
        classification = "no_xyce_bridge_devices_detected"
    return {
        "path": str(path),
        "classification": classification,
        "has_yadc": has_yadc,
        "has_ydac": has_ydac,
        "has_sky130_standard_cell_spice": has_std_cell_spice,
        "has_sky130_standard_cell_instances": has_sky130_cells,
        "has_mapped_digital_label": has_mapped_label,
    }


def print_summary(summary: dict[str, object]) -> None:
    print("Xyce mixed-signal readiness")
    print(f"  xyce_command: {' '.join(summary['xyce_command'])}")
    print(f"  xyce_capabilities: {summary.get('xyce_capabilities', 'unavailable')}")
    print(
        "  yadc_ydac_device_probe: "
        + ("pass" if summary["bridge_device_probe"]["ok"] else "fail")
    )
    print(f"  xyce_interface_py: {summary.get('xyce_interface_py') or 'missing'}")
    print(
        "  shared_interface_library: "
        + (summary.get("shared_interface_library") or "missing")
    )
    print(
        "  static_interface_library: "
        + (summary.get("static_interface_library") or "missing")
    )
    print(
        "  ready_for_app_note_cosim: "
        + ("yes" if summary["ready_for_app_note_cosim"] else "no")
    )
    deck_results = summary.get("deck_classification") or []
    for deck in deck_results:
        print(f"  deck: {deck['path']}")
        print(f"    classification: {deck['classification']}")
        print(f"    has_yadc: {int(deck['has_yadc'])}")
        print(f"    has_ydac: {int(deck['has_ydac'])}")
        print(
            "    has_sky130_standard_cell_spice: "
            f"{int(deck['has_sky130_standard_cell_spice'])}"
        )
    if not summary["ready_for_app_note_cosim"]:
        print("  missing_for_cosim:")
        for item in summary["missing_for_cosim"]:
            print(f"    - {item}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Probe Xyce YADC/YDAC support and the shared XyceCInterface library "
            "needed by the Xyce mixed-signal app-note Python/VPI flow."
        )
    )
    parser.add_argument("--xyce", default=os.environ.get("XYCE", "Xyce"))
    parser.add_argument("--xyce-lib-dir", action="append")
    parser.add_argument("--xyce-share", action="append")
    parser.add_argument("--xyce-build-dir")
    parser.add_argument(
        "--deck",
        action="append",
        type=Path,
        help="Optional generated deck to classify as app-note mixed or all-SPICE.",
    )
    parser.add_argument(
        "--build-dir",
        type=Path,
        default=ROOT / "build" / "xyce_mixed_signal_probe",
    )
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--skip-device-probe", action="store_true")
    parser.add_argument(
        "--allow-missing-shared",
        action="store_true",
        help="Exit zero when only the shared C-interface library is missing.",
    )
    args = parser.parse_args()

    xyce_words = command_words(args.xyce)
    capabilities = run_command(xyce_words + ["-capabilities"], timeout_s=30.0)
    caps_text = capabilities.stdout.strip().replace("\n", "; ")

    lib_path, checked_libs = find_shared_interface(candidate_lib_dirs(args))
    static_lib_path, checked_static_libs = find_static_interface(candidate_build_dirs(args))
    interface_py, checked_interfaces = find_xyce_interface_py(
        candidate_share_dirs(args, xyce_words)
    )
    if args.skip_device_probe:
        bridge_probe = {"ok": True, "returncode": 0, "deck": "", "log": ""}
    else:
        bridge_probe = run_bridge_device_probe(xyce_words, args.build_dir)

    deck_results = []
    for deck in args.deck or []:
        deck = deck.expanduser()
        if not deck.exists():
            deck_results.append(
                {
                    "path": str(deck),
                    "classification": "missing",
                    "has_yadc": False,
                    "has_ydac": False,
                    "has_sky130_standard_cell_spice": False,
                    "has_sky130_standard_cell_instances": False,
                    "has_mapped_digital_label": False,
                }
            )
        else:
            deck_results.append(classify_deck(deck))

    missing = []
    if not lib_path:
        missing.append("libxycecinterface.so or platform equivalent")
    if not interface_py:
        missing.append("xyce_interface.py on the Xyce share path")
    if not bridge_probe["ok"]:
        missing.append("working YADC/YDAC bridge-device simulation")

    ready = not missing
    summary = {
        "xyce_command": xyce_words,
        "xyce_capabilities": caps_text,
        "bridge_device_probe": bridge_probe,
        "xyce_interface_py": interface_py,
        "checked_xyce_interface_py": checked_interfaces,
        "shared_interface_library": lib_path,
        "checked_shared_interface_libraries": checked_libs,
        "static_interface_library": static_lib_path,
        "checked_static_interface_libraries": checked_static_libs,
        "ready_for_app_note_cosim": ready,
        "missing_for_cosim": missing,
        "deck_classification": deck_results,
    }

    print_summary(summary)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(summary, indent=2) + "\n", encoding="ascii")

    if ready:
        return 0
    if args.allow_missing_shared and missing == [
        "libxycecinterface.so or platform equivalent"
    ]:
        return 0
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, subprocess.TimeoutExpired, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
