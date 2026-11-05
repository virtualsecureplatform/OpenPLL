#!/usr/bin/env python3
"""Check extracted-DCO qualification reports against the approved PVT grid."""

import hashlib
import itertools
import json
import math
import re
from pathlib import Path

from dco_calibration import assess, assess_interpolation, measure


def has_xyce_temperature(deck: str, requested: float) -> bool:
    """Reject ignored ngspice syntax and ambiguous global temperature settings."""
    if re.search(r"(?im)^\s*\.temp\b", deck):
        return False
    values = re.findall(r"(?im)^\s*\.options\s+device\b[^\n]*?\btemp\s*=\s*"
                        r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?)", deck)
    return len(values) == 1 and math.isclose(float(values[0]), requested, abs_tol=1e-10)


def check_sample_evidence(point: Path, corner: str, coarse: int, vdd: float,
                          samples: dict, provenance: dict) -> bool:
    """Remeasure every reported waveform and match its completed run sidecar."""
    for variant, values in samples.items():
        run = point / variant
        record = provenance.get(variant)
        if not isinstance(record, dict):
            return False
        run_record = json.loads((run / "provenance.json").read_text())
        if run_record != record:
            return False
        parameters = record["parameters"]
        start = parameters["meas_start_ns"]
        stop = parameters["sim_time_ns"]
        for text_code, reported in values.items():
            code = int(text_code)
            base = run / f"dco_postlayout_{corner}_coarse_{coarse:02d}_code_{code:03d}"
            sidecar = json.loads(base.with_suffix(".provenance.json").read_text())
            deck_path = base.with_suffix(".spice")
            deck = deck_path.read_text()
            if (not has_xyce_temperature(deck, parameters["temperature_c"])
                    or sidecar.get("netlist_sha256") != hashlib.sha256(deck_path.read_bytes()).hexdigest()):
                return False
            if sidecar.get("completed") is not True or any(
                sidecar.get(key) != record.get(key)
                for key in ("files", "parameters", "fingerprint")
            ):
                return False
            observed = measure(base.with_suffix(".prn"), start, stop, vdd)
            for field in ("mhz", "half_window_difference_mhz",
                          "first_edge_ns", "last_edge_ns"):
                if not math.isclose(observed[field], reported[field],
                                    rel_tol=1e-10, abs_tol=1e-9):
                    return False
            if observed["periods"] != reported["periods"]:
                return False
    return True


def check_pvt_grid(root: Path, spec: dict, rcx: Path, subckt_name: str) -> dict:
    expected = list(itertools.product(
        spec["modes_mhz"], spec["corners"], spec["voltages"],
        spec["temperatures_c"]))
    rcx_hash = hashlib.sha256(rcx.read_bytes()).hexdigest()
    issues = []
    present = qualified = 0
    for mode, corner, vdd, temp in expected:
        path = (root / f"mode_{mode}" / f"{corner}_{vdd:g}V_{temp:g}C"
                / "calibration.json")
        label = f"{mode} MHz {corner} {vdd:g} V {temp:g} C"
        if not path.is_file():
            issues.append(f"{label}: missing report")
            continue
        present += 1
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            valid = (
                report.get("stage") == "qualify"
                and report.get("mode_mhz") == mode
                and report.get("corner") == corner
                and report.get("vdd") == vdd
                and report.get("temperature_c") == temp
                and report.get("simulator") == "Xyce"
                and report.get("subckt_name") == subckt_name
                and report.get("evidence") == "deterministic_frequency_only"
                and report.get("errors") == []
                and report.get("convergence_passed") is True
                and report.get("coverage_passed") is True
                and report.get("interpolation_validated") is True
                and report.get("target_frequency_passed") is True
                and report.get("target_monotonic_passed") is True
                and isinstance(report.get("coarse"), int)
                and 0 <= report["coarse"] <= 47
                and isinstance(report.get("target_code"), int)
                and spec["fine_code_min"] <= report["target_code"] <= spec["fine_code_max"]
                and isinstance(report.get("target_frequency_mhz"), (int, float))
                and math.isfinite(report["target_frequency_mhz"])
                and abs(report["target_frequency_mhz"] / mode - 1) * 1e6
                    <= spec["frequency_error_ppm"]
            )
            provenance = report.get("provenance")
            valid &= isinstance(provenance, dict) and set(provenance) == {
                "baseline", "tolerance", "step", "settling", "interpolation"}
            if valid:
                band = report["samples"][str(report["coarse"])]
                variants = {name: {int(code): value for code, value in band[name].items()}
                            for name in ("baseline", "tolerance", "step", "settling")}
                holdouts = {int(code): value for code, value in
                            band["interpolation"].items()}
                anchors = sorted(set(range(
                    spec["fine_code_min"], spec["fine_code_max"] + 1, 16))
                    | {spec["fine_code_max"]})
                valid &= (assess(variants, mode, spec)["convergence_passed"]
                          and assess_interpolation(variants["settling"], holdouts,
                                                   anchors, mode, spec)["interpolation_validated"])
                endpoints = [variants["settling"][code]["mhz"]
                             for code in (spec["fine_code_min"], spec["fine_code_max"])]
                valid &= min(endpoints) <= mode <= max(endpoints)
                settling = band["settling"]
                local_codes = [code for code in (
                    report["target_code"] - 1, report["target_code"],
                    report["target_code"] + 1)
                    if spec["fine_code_min"] <= code <= spec["fine_code_max"]]
                local_mhz = [settling[str(code)]["mhz"] for code in local_codes]
                valid &= (all(isinstance(value, (int, float)) and math.isfinite(value)
                              for value in local_mhz)
                          and local_mhz[local_codes.index(report["target_code"])]
                          == report["target_frequency_mhz"]
                          and all(left < right for left, right in
                                  zip(local_mhz, local_mhz[1:])))
            if valid:
                for record in provenance.values():
                    files = record.get("files") if isinstance(record, dict) else None
                    parameters = record.get("parameters") if isinstance(record, dict) else None
                    calculated = (hashlib.sha256(json.dumps(
                        {"files": files, "parameters": parameters}, sort_keys=True,
                        allow_nan=False).encode()).hexdigest()
                        if isinstance(files, dict) and isinstance(parameters, dict)
                        else None)
                    if (not isinstance(files, dict) or not isinstance(parameters, dict)
                            or record.get("fingerprint") != calculated
                            or parameters.get("corner") != corner
                            or parameters.get("vdd") != vdd
                            or parameters.get("temperature_c") != temp
                            or parameters.get("subckt_name") != subckt_name
                            or not any(Path(name).name == rcx.name and digest == rcx_hash
                                       for name, digest in files.items())):
                        valid = False
                        break
            if valid:
                valid = check_sample_evidence(path.parent, corner, report["coarse"],
                                              vdd, band, provenance)
        except (OSError, ValueError, TypeError, KeyError, AttributeError,
                ZeroDivisionError):
            valid = False
        if valid:
            qualified += 1
        else:
            issues.append(f"{label}: invalid or unqualified report")
    return {
        "expected": len(expected), "present": present, "qualified": qualified,
        "passed": qualified == len(expected), "issues": issues[:20],
        "issue_count": len(issues),
    }
