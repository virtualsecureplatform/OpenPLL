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
INSTANCE_RE = re.compile(
    r"^\s*(sky130_fd_sc_hd__[A-Za-z0-9_]+)\s+([A-Za-z0-9_]+)\s*\((.*?)^\s*\);\s*$",
    re.MULTILINE | re.DOTALL,
)
PIN_RE = re.compile(r"\.([A-Za-z0-9_]+)\s*\(\s*(.*?)\s*\)", re.DOTALL)
OUTPUT_PINS = {"X", "Y", "Q", "Q_N", "SUM", "COUT"}
SUPPLY_NETS = {
    "VPWR": "VPWR",
    "VPB": "VPWR",
    "VGND": "VGND",
    "VNB": "VGND",
}


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


def parse_indices(text):
    if text == "all":
        return list(range(255))
    indices = []
    for item in text.split(","):
        item = item.strip()
        if not item:
            continue
        index = int(item, 0)
        if index < 0 or index > 254:
            raise ValueError(f"thermometer index out of range: {index}")
        indices.append(index)
    return sorted(set(indices))


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


def operating_point_value(log_text, node):
    pattern = rf"^\s*{re.escape(node)}\s+{RE_FLOAT}\s*$"
    match = re.search(pattern, log_text, re.IGNORECASE | re.MULTILINE)
    if match:
        return float(match.group(1))
    return None


def sanitize_net(name):
    name = name.strip()
    if name.startswith("\\"):
        name = name[1:].strip()
    name = name.replace("[", "_").replace("]", "")
    name = re.sub(r"[^A-Za-z0-9_]+", "_", name)
    name = name.strip("_")
    if not name:
        return "NC"
    if name[0].isdigit():
        name = f"n_{name}"
    return name


def bit_net(name, index):
    return sanitize_net(f"{name}[{index}]")


def parse_subckt_ports(cell_spice_path):
    ports = {}
    for line in cell_spice_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith(".subckt "):
            continue
        parts = line.split()
        if len(parts) >= 3 and parts[1].startswith("sky130_fd_sc_hd__"):
            ports[parts[1]] = parts[2:]
    return ports


def parse_instances(verilog_text):
    instances = []
    for index, match in enumerate(INSTANCE_RE.finditer(verilog_text)):
        cell_type = match.group(1)
        instance_name = match.group(2)
        body = match.group(3)
        conns = {}
        for pin_match in PIN_RE.finditer(body):
            conns[pin_match.group(1)] = sanitize_net(pin_match.group(2))
        instances.append(
            {
                "index": index,
                "type": cell_type,
                "name": instance_name,
                "conns": conns,
            }
        )
    return instances


def output_pins(instance):
    return [pin for pin in instance["conns"] if pin in OUTPUT_PINS]


def input_pins(instance):
    return [
        pin
        for pin in instance["conns"]
        if pin not in OUTPUT_PINS and pin not in SUPPLY_NETS
    ]


def extract_dco_decoder_cone(instances, therm_indices):
    input_nets = {bit_net("DCO_CODE", index) for index in range(8)}
    output_nets = {bit_net("DCO_THERM", index) for index in therm_indices}

    drivers = {}
    for instance in instances:
        for pin in output_pins(instance):
            drivers[instance["conns"][pin]] = instance

    needed = set()
    stack = list(output_nets)
    while stack:
        net = stack.pop()
        if net in input_nets:
            continue
        driver = drivers.get(net)
        if driver is None:
            raise ValueError(f"no driver found for DCO decoder net {net}")
        if driver["index"] in needed:
            continue
        needed.add(driver["index"])
        for pin in input_pins(driver):
            stack.append(driver["conns"][pin])

    return [instance for instance in instances if instance["index"] in needed]


def dco_code_source_lines(code):
    return [
        f"VDCOCODE{index} {bit_net('DCO_CODE', index)} 0 "
        f"{'{VDD}' if ((code >> index) & 1) else '0'}"
        for index in range(8)
    ]


def dco_code_dc_sweep_lines():
    lines = ["VCODESTEP CODE_SWEEP 0 0"]
    for index in range(8):
        divisor = 1 << index
        next_divisor = 1 << (index + 1)
        lines.append(
            f"BDCOCODE{index} {bit_net('DCO_CODE', index)} 0 "
            f"V={{VDD*(floor(v(CODE_SWEEP)/{divisor})"
            f"-2*floor(v(CODE_SWEEP)/{next_divisor}))}}"
        )
    return lines


def spice_instance_lines(instances, subckt_ports):
    lines = []
    missing = {}
    for instance in instances:
        cell_type = instance["type"]
        instance_name = instance["name"]
        conns = instance["conns"]
        if cell_type not in subckt_ports:
            missing.setdefault(cell_type, 0)
            missing[cell_type] += 1
            continue

        nets = []
        for port in subckt_ports[cell_type]:
            if port in SUPPLY_NETS:
                nets.append(SUPPLY_NETS[port])
            elif port in conns:
                nets.append(conns[port])
            else:
                nets.append(f"NC_{sanitize_net(instance_name)}_{port}")
        lines.append(
            f"X{sanitize_net(instance_name)} {' '.join(nets)} {cell_type}"
        )

    if missing:
        missing_text = ", ".join(
            f"{cell_type} ({count})" for cell_type, count in sorted(missing.items())
        )
        raise ValueError(f"missing Sky130 SPICE subckt definitions: {missing_text}")

    return lines


def decoder_netlist(code, args, instances, subckt_ports, therm_indices):
    pdk_dir = Path(args.pdk_root).expanduser().resolve() / args.pdk
    model_path = pdk_dir / "libs.tech" / "ngspice" / "sky130.lib.spice"
    cell_path = (
        pdk_dir
        / "libs.ref"
        / args.std_cell_library
        / "spice"
        / f"{args.std_cell_library}.spice"
    )

    if not model_path.exists():
        raise FileNotFoundError(model_path)
    if not cell_path.exists():
        raise FileNotFoundError(cell_path)

    expected_checked_high = sum(1 for index in therm_indices if index >= code)
    lines = [
        f"* OpenPLL synthesized Sky130 DCO decoder SPICE check, code={code}",
        f"* Expected checked-high DCO_THERM taps={expected_checked_high}",
        f'.lib "{model_path}" {args.corner}',
        f'.include "{cell_path}"',
        ".option method=gear reltol=1e-4 abstol=1e-15 chgtol=1e-16",
        ".param VDD=1.8",
        "VVPWR VPWR 0 {VDD}",
        "VVGND VGND 0 0",
        "",
        "* Static 8-bit DCO_CODE stimulus.",
    ]
    lines.extend(dco_code_source_lines(code))
    lines.extend(
        [
            "",
            "* Backward cone from synthesized DCO_THERM outputs to DCO_CODE inputs.",
        ]
    )
    lines.extend(spice_instance_lines(instances, subckt_ports))
    lines.extend(
        [
            "",
            ".op",
        ]
    )

    lines.extend([".end", ""])
    return "\n".join(lines)


def decoder_dc_sweep_netlist(args, instances, subckt_ports, therm_indices, raw_path):
    pdk_dir = Path(args.pdk_root).expanduser().resolve() / args.pdk
    model_path = pdk_dir / "libs.tech" / "ngspice" / "sky130.lib.spice"
    cell_path = (
        pdk_dir
        / "libs.ref"
        / args.std_cell_library
        / "spice"
        / f"{args.std_cell_library}.spice"
    )

    if not model_path.exists():
        raise FileNotFoundError(model_path)
    if not cell_path.exists():
        raise FileNotFoundError(cell_path)

    lines = [
        "* OpenPLL synthesized Sky130 DCO decoder DC sweep check",
        f"* Checked DCO_THERM taps={len(therm_indices)}",
        f'.lib "{model_path}" {args.corner}',
        f'.include "{cell_path}"',
        ".option method=gear reltol=1e-4 abstol=1e-15 chgtol=1e-16",
        ".param VDD=1.8",
        "VVPWR VPWR 0 {VDD}",
        "VVGND VGND 0 0",
        "",
        "* Swept integer-like DCO_CODE stimulus. Each bit is derived from CODE_SWEEP.",
    ]
    lines.extend(dco_code_dc_sweep_lines())
    lines.extend(
        [
            "",
            "* Backward cone from synthesized DCO_THERM outputs to DCO_CODE inputs.",
        ]
    )
    lines.extend(spice_instance_lines(instances, subckt_ports))
    lines.extend(
        [
            "",
            ".save v(CODE_SWEEP)",
            *[f".save v({bit_net('DCO_THERM', index)})" for index in therm_indices],
            ".control",
            "set filetype=ascii",
            "dc VCODESTEP 0 255 1",
            f"write {raw_path}",
            "quit",
            ".endc",
            ".end",
            "",
        ]
    )
    return "\n".join(lines)


def logic_high(value, threshold):
    return value is not None and value > threshold


def parse_raw_value(text):
    return float(text.strip().split(",", 1)[0])


def parse_ascii_raw(raw_path):
    lines = Path(raw_path).read_text(encoding="utf-8", errors="replace").splitlines()
    variable_count = None
    point_count = None
    variables_start = None
    values_start = None
    for line_number, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("No. Variables:"):
            variable_count = int(stripped.split(":", 1)[1])
        elif stripped.startswith("No. Points:"):
            point_count = int(stripped.split(":", 1)[1])
        elif stripped == "Variables:":
            variables_start = line_number + 1
        elif stripped == "Values:":
            values_start = line_number + 1
            break

    if variable_count is None or point_count is None:
        raise ValueError(f"rawfile is missing variable/point counts: {raw_path}")
    if variables_start is None or values_start is None:
        raise ValueError(f"rawfile is missing Variables/Values sections: {raw_path}")

    variable_names = []
    for line in lines[variables_start : variables_start + variable_count]:
        parts = line.split()
        if len(parts) < 3:
            raise ValueError(f"malformed rawfile variable line: {line}")
        variable_names.append(parts[1].lower())

    rows = []
    cursor = values_start
    for _ in range(point_count):
        while cursor < len(lines) and not lines[cursor].strip():
            cursor += 1
        if cursor >= len(lines):
            raise ValueError(f"rawfile ended before all points were read: {raw_path}")

        first = lines[cursor].split()
        if len(first) < 2:
            raise ValueError(f"malformed rawfile value line: {lines[cursor]}")
        values = [parse_raw_value(first[1])]
        cursor += 1

        for _ in range(variable_count - 1):
            while cursor < len(lines) and not lines[cursor].strip():
                cursor += 1
            if cursor >= len(lines):
                raise ValueError(f"rawfile ended inside point data: {raw_path}")
            parts = lines[cursor].split()
            if not parts:
                raise ValueError(f"malformed rawfile continuation line: {lines[cursor]}")
            values.append(parse_raw_value(parts[0]))
            cursor += 1

        rows.append(dict(zip(variable_names, values)))

    return variable_names, rows


def run_one(code, args, build_dir, instances, subckt_ports, therm_indices):
    netlist_path = build_dir / f"dco_decoder_code_{code:03d}.spice"
    log_path = build_dir / f"dco_decoder_code_{code:03d}.log"
    netlist_path.write_text(
        decoder_netlist(code, args, instances, subckt_ports, therm_indices),
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

    therm_bits = {
        index: operating_point_value(proc.stdout, bit_net("DCO_THERM", index))
        for index in therm_indices
    }
    measured_checked_high = sum(
        1 for value in therm_bits.values() if logic_high(value, args.threshold)
    )
    expected_checked_high = sum(1 for index in therm_indices if index >= code)

    therm_errors = []
    for index, value in therm_bits.items():
        expected_high = index >= code
        measured_high = logic_high(value, args.threshold)
        if measured_high != expected_high:
            therm_errors.append(index)

    status = "pass"
    if proc.returncode != 0:
        status = "fail"
    elif any(value is None for value in therm_bits.values()):
        status = "fail"
    elif measured_checked_high != expected_checked_high:
        status = "fail"
    elif therm_errors:
        status = "fail"

    return {
        "code": code,
        "status": status,
        "checked_indices": ",".join(str(index) for index in therm_indices),
        "expected_checked_high": expected_checked_high,
        "measured_checked_high": measured_checked_high,
        "therm_errors": ",".join(str(index) for index in therm_errors[:16]),
        "netlist": str(netlist_path),
        "log": str(log_path),
    }


def run_dc_sweep(args, build_dir, instances, subckt_ports, therm_indices, codes):
    netlist_path = build_dir / "dco_decoder_dc_sweep.spice"
    raw_path = build_dir / "dco_decoder_dc_sweep.raw"
    log_path = build_dir / "dco_decoder_dc_sweep.log"
    netlist_path.write_text(
        decoder_dc_sweep_netlist(args, instances, subckt_ports, therm_indices, raw_path),
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
    if proc.returncode != 0:
        raise RuntimeError(f"ngspice DC sweep failed; see {log_path}")
    if not raw_path.exists():
        raise FileNotFoundError(raw_path)

    _, raw_rows = parse_ascii_raw(raw_path)
    rows_by_code = {}
    for raw_row in raw_rows:
        sweep_value = raw_row.get("v(code_sweep)", raw_row.get("v(v-sweep)"))
        if sweep_value is None:
            raise ValueError(f"rawfile is missing CODE_SWEEP data: {raw_path}")
        code = int(round(sweep_value))
        if 0 <= code <= 255:
            rows_by_code[code] = raw_row

    missing_codes = [code for code in codes if code not in rows_by_code]
    if missing_codes:
        raise ValueError(f"rawfile missing swept code rows: {missing_codes[:16]}")

    results = []
    checked_indices = ",".join(str(index) for index in therm_indices)
    for code in codes:
        raw_row = rows_by_code[code]
        measured_checked_high = 0
        therm_errors = []
        for index in therm_indices:
            node_name = f"v({bit_net('DCO_THERM', index).lower()})"
            value = raw_row.get(node_name)
            expected_high = index >= code
            measured_high = logic_high(value, args.threshold)
            if measured_high:
                measured_checked_high += 1
            if value is None or measured_high != expected_high:
                therm_errors.append(index)

        expected_checked_high = sum(1 for index in therm_indices if index >= code)
        status = "pass"
        if measured_checked_high != expected_checked_high or therm_errors:
            status = "fail"

        results.append(
            {
                "code": code,
                "status": status,
                "checked_indices": checked_indices,
                "expected_checked_high": expected_checked_high,
                "measured_checked_high": measured_checked_high,
                "therm_errors": ",".join(str(index) for index in therm_errors[:16]),
                "netlist": str(netlist_path),
                "log": str(log_path),
            }
        )

    return results


def main():
    root_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--codes",
        default="0,1,2,127,128,254,255",
        help='Comma-separated DCO codes or "all".',
    )
    parser.add_argument(
        "--therm-indices",
        default="0,1,2,126,127,128,253,254",
        help='Comma-separated DCO_THERM tap indices or "all".',
    )
    parser.add_argument(
        "--mapped-verilog",
        default=str(root_dir / "build" / "synth" / "IntegerPLL_DigitalCore_sky130.v"),
    )
    parser.add_argument("--pdk-root", default=os.environ.get("PDK_ROOT", "~/.volare"))
    parser.add_argument("--pdk", default=os.environ.get("PDK", "sky130A"))
    parser.add_argument(
        "--std-cell-library",
        default=os.environ.get("STD_CELL_LIBRARY", "sky130_fd_sc_hd"),
    )
    parser.add_argument("--corner", default="tt")
    parser.add_argument("--threshold", type=float, default=0.9)
    parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Number of parallel ngspice jobs to run.",
    )
    parser.add_argument(
        "--dc-sweep",
        action="store_true",
        help="Validate requested codes with one ngspice DC sweep over all 256 codes.",
    )
    parser.add_argument("--ngspice", default=shutil.which("ngspice") or "ngspice")
    parser.add_argument(
        "--build-dir",
        default=str(root_dir / "build" / "spice_decoder"),
    )
    args = parser.parse_args()

    mapped_verilog = Path(args.mapped_verilog).expanduser().resolve()
    if not mapped_verilog.exists():
        raise FileNotFoundError(
            f"missing mapped Verilog netlist: {mapped_verilog}. Run make synth first."
        )

    pdk_dir = Path(args.pdk_root).expanduser().resolve() / args.pdk
    cell_spice_path = (
        pdk_dir
        / "libs.ref"
        / args.std_cell_library
        / "spice"
        / f"{args.std_cell_library}.spice"
    )

    subckt_ports = parse_subckt_ports(cell_spice_path)
    all_instances = parse_instances(mapped_verilog.read_text(encoding="utf-8"))
    if not all_instances:
        raise ValueError(f"no Sky130 cell instances found in {mapped_verilog}")

    therm_indices = parse_indices(args.therm_indices)
    instances = extract_dco_decoder_cone(all_instances, therm_indices)
    codes = parse_codes(args.codes)
    if args.jobs < 1:
        raise ValueError("--jobs must be at least 1")
    build_dir = Path(args.build_dir).expanduser().resolve()
    build_dir.mkdir(parents=True, exist_ok=True)

    print(
        f"extracted {len(instances)} DCO decoder cells from "
        f"{len(all_instances)} mapped digital-core cells; "
        f"checking {len(therm_indices)} thermometer taps",
        flush=True,
    )

    if args.dc_sweep:
        results = run_dc_sweep(args, build_dir, instances, subckt_ports, therm_indices, codes)
        for result in results:
            print(
                f"code={result['code']:3d} status={result['status']} "
                f"checked_high={result['measured_checked_high']:3d}/"
                f"{result['expected_checked_high']:3d}",
                flush=True,
            )
    elif args.jobs == 1:
        results = []
        for code in codes:
            result = run_one(code, args, build_dir, instances, subckt_ports, therm_indices)
            results.append(result)
            print(
                f"code={code:3d} status={result['status']} "
                f"checked_high={result['measured_checked_high']:3d}/"
                f"{result['expected_checked_high']:3d}",
                flush=True,
            )
    else:
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
            futures = {
                executor.submit(
                    run_one,
                    code,
                    args,
                    build_dir,
                    instances,
                    subckt_ports,
                    therm_indices,
                ): code
                for code in codes
            }
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                results.append(result)
                print(
                    f"code={result['code']:3d} status={result['status']} "
                    f"checked_high={result['measured_checked_high']:3d}/"
                    f"{result['expected_checked_high']:3d}",
                    flush=True,
                )

    results.sort(key=lambda row: row["code"])

    csv_path = build_dir / "dco_decoder_check.csv"
    with csv_path.open("w", newline="", encoding="ascii") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "code",
                "status",
                "checked_indices",
                "expected_checked_high",
                "measured_checked_high",
                "therm_errors",
                "netlist",
                "log",
            ],
        )
        writer.writeheader()
        writer.writerows(results)

    print(f"wrote {csv_path}")

    failed = [row for row in results if row["status"] != "pass"]
    if failed:
        print(f"{len(failed)} synthesized DCO decoder SPICE checks failed", file=sys.stderr)
        return 1

    print(
        f"validated {len(results)} DCO_CODE values for "
        f"{len(therm_indices)} DCO_THERM taps"
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
