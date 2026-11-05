#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Associate Magic missing-terminal feedback with placed boundary decaps.

This is a spatial diagnostic, not extraction or electrical qualification.
The Sky130 HD decap_3 footprint is 1.38 by 2.72 um.
"""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re


DECAP = "sky130_fd_sc_hd__decap_3"
WIDTH_UM = 1.38
HEIGHT_UM = 2.72
COMPONENT = re.compile(
    r"^\s*-\s+(\S+)\s+(\S+)\s+[^;]*?\+ (?:FIXED|PLACED) "
    r"\( (\d+) (\d+) \) (\S+) ;",
    re.MULTILINE,
)
FEEDBACK = re.compile(
    r'box (\d+) (\d+) (\d+) (\d+)\nfeedback add "device missing 1 terminal;'
    r'\n connecting remainder to node (VPWR|VGND)" pale'
)


def read_def(path):
    source = path.read_text()
    units = re.search(r"UNITS DISTANCE MICRONS (\d+) ;", source)
    design = re.search(r"^DESIGN (\S+) ;", source, re.MULTILINE)
    if not units or not design:
        raise ValueError(f"missing DEF units or design: {path}")
    components = {}
    for name, cell, x, y, orientation in COMPONENT.findall(source):
        if name in components:
            raise ValueError(f"duplicate DEF component {name}: {path}")
        components[name] = (cell, int(x) / int(units[1]), int(y) / int(units[1]), orientation)
    return design[1], components


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wrapper-def", type=Path, required=True)
    parser.add_argument("--macro", action="append", default=[], metavar="INSTANCE=DEF")
    parser.add_argument("--feedback", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    files = [args.wrapper_def, args.feedback]
    _, wrapper = read_def(args.wrapper_def)
    placements = [("wrapper", wrapper, 0.0, 0.0)]
    for item in args.macro:
        instance, separator, filename = item.partition("=")
        if not separator or not instance or not filename:
            parser.error("--macro requires INSTANCE=DEF")
        if instance not in wrapper:
            raise ValueError(f"macro instance {instance} absent from wrapper DEF")
        cell, x, y, orientation = wrapper[instance]
        if orientation != "N":
            raise ValueError(f"macro orientation {orientation} is not supported")
        path = Path(filename)
        files.append(path)
        design, components = read_def(path)
        if design != cell:
            raise ValueError(f"macro {instance} DEF design {design} differs from wrapper cell {cell}")
        placements.append((instance, components, x, y))

    decaps = {}
    for scope, components, dx, dy in placements:
        for name, (cell, x, y, orientation) in components.items():
            if cell == DECAP:
                if orientation not in ("N", "S", "FN", "FS"):
                    raise ValueError(f"decap orientation {orientation} is not supported")
                decaps[f"{scope}/{name}"] = (
                    dx + x, dy + y, dx + x + WIDTH_UM, dy + y + HEIGHT_UM
                )

    source = args.feedback.read_text()
    warnings = FEEDBACK.findall(source)
    if not decaps or not warnings:
        raise ValueError("expected placed decaps and Magic warning boxes")
    if len(warnings) != source.count("feedback add "):
        raise ValueError("feedback contains unsupported warnings")
    counts = Counter()
    for index, (x0, y0, x1, y1, rail) in enumerate(warnings):
        x = (int(x0) + int(x1)) * 0.005 / 2
        y = (int(y0) + int(y1)) * 0.005 / 2
        matches = [name for name, (left, bottom, right, top) in decaps.items()
                   if left <= x <= right and bottom <= y <= top]
        if len(matches) != 1:
            raise ValueError(f"warning {index} at ({x:g}, {y:g}) um matches {matches}")
        counts[matches[0], rail] += 1
    for name in decaps:
        if counts[name, "VPWR"] != 1 or counts[name, "VGND"] != 1:
            raise ValueError(f"decap {name} lacks exactly one warning per rail")

    report = {
        "scope": "diagnostic spatial association only; no connectivity or electrical waiver",
        "pll_release_qualified": False,
        "warnings": len(warnings),
        "placed_decaps": len(decaps),
        "associated_with_one_decap": sum(counts.values()),
        "decaps_by_scope": dict(sorted(Counter(name.split("/", 1)[0] for name in decaps).items())),
        "magic_grid_um": 0.005,
        "cell_footprint_um": [WIDTH_UM, HEIGHT_UM],
        "source_sha256": {str(path.resolve()): digest(path) for path in files},
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in
                      ("warnings", "placed_decaps", "associated_with_one_decap", "decaps_by_scope")},
                     indent=2))


if __name__ == "__main__":
    main()
