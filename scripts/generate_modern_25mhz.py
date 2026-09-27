#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate the modern Sky130 preset RTL and behavioral DCO from measured data."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from sky130_modern_targets import TARGETS_MHZ, load_target_presets


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "sky130" / "modern_25mhz_targets.json"
MODE_SOURCE = ROOT / "rtl" / "IntegerPLL_25MHzModeConfig.v"
MODE_OUTPUT = ROOT / "rtl" / "IntegerPLL_25MHzModeConfig_modern.v"
MODEL_SOURCE = ROOT / "models" / "IntegerPLL_DCO_25MHzCoarse_model.v"
MODEL_OUTPUT = ROOT / "models" / "IntegerPLL_DCO_25MHzCoarse_modern_model.v"
TB_NAMES = (
    "mode_config",
    "mode_controller",
    "configured_wrapper",
    "configured_behavioral",
)
LEGACY_SETTINGS = {100: (20, 93), 250: (6, 234), 300: (4, 90), 400: (2, 76), 500: (1, 121)}


def render_mode_config(modes: dict[int, dict]) -> str:
    source = MODE_SOURCE.read_text(encoding="ascii")
    for target in TARGETS_MHZ:
        pattern = rf"(DIV_{target}MHZ: begin)(.*?)(\n            end)"
        match = re.search(pattern, source, re.S)
        if match is None:
            raise ValueError(f"missing {target} MHz RTL case")
        block = match.group(2)
        values = modes[target]
        block, coarse_count = re.subn(
            r"COARSEBINARY_CODE = 6'd\d+;",
            f"COARSEBINARY_CODE = 6'd{values['coarse_code']};",
            block,
        )
        block, code_count = re.subn(
            r"TARGET_DCO_CODE = 8'd\d+;",
            f"TARGET_DCO_CODE = 8'd{values['target_code']};",
            block,
        )
        block, seed_count = re.subn(
            r"DLF_Ext_Data = seed_word\(8'd\d+\);",
            f"DLF_Ext_Data = seed_word(8'd{values['target_code']});",
            block,
        )
        if (coarse_count, code_count, seed_count) != (1, 1, 1):
            raise ValueError(f"ambiguous {target} MHz RTL case")
        source = source[:match.start()] + match.group(1) + block + match.group(3) + source[match.end():]
    return source.replace("// SPDX-License-Identifier: Apache-2.0\n",
                          "// SPDX-License-Identifier: Apache-2.0\n"
                          "// Generated from sky130/modern_25mhz_targets.json.\n", 1)


def render_model(data: dict) -> str:
    source = MODEL_SOURCE.read_text(encoding="ascii")
    start = source.index("    function real c20_freq_mhz;")
    end = source.index("    initial begin", start)
    lines = [
        "    function real interp3;",
        "        input integer code;",
        "        input integer seed;",
        "        input real f0;",
        "        input real fseed;",
        "        input real f255;",
        "        begin",
        "            if (code <= seed)",
        "                interp3 = interp(code, 0, f0, seed, fseed);",
        "            else",
        "                interp3 = interp(code, seed, fseed, 255, f255);",
        "        end",
        "    endfunction",
        "",
        "    function real coarse_freq_mhz;",
        "        input [5:0] coarse;",
        "        input integer code;",
        "        begin",
        "            case (coarse)",
    ]
    for target in TARGETS_MHZ:
        row = data["targets"][str(target)]
        lines.append(
            f"                6'd{row['coarse_code']}: coarse_freq_mhz = interp3(code, "
            f"{row['target_code']}, {row['f0_mhz']:.9f}, "
            f"{row['f_target_mhz']:.9f}, {row['f255_mhz']:.9f});"
        )
    fallback = data["targets"]["100"]
    lines.append(
        f"                default: coarse_freq_mhz = interp3(code, {fallback['target_code']}, "
        f"{fallback['f0_mhz']:.9f}, {fallback['f_target_mhz']:.9f}, {fallback['f255_mhz']:.9f});"
    )
    lines.extend(["            endcase", "        end", "    endfunction", ""])
    rendered = source[:start] + "\n".join(lines) + "\n" + source[end:]
    return rendered.replace("// SPDX-License-Identifier: Apache-2.0\n",
                            "// SPDX-License-Identifier: Apache-2.0\n"
                            "// Generated from sky130/modern_25mhz_targets.json.\n", 1)


def render_testbench(name: str, modes: dict[int, dict]) -> str:
    source = (ROOT / "tb" / f"tb_pll_25mhz_{name}.v").read_text(encoding="ascii")
    for target in TARGETS_MHZ:
        old_coarse, old_code = LEGACY_SETTINGS[target]
        old = f"6'd{old_coarse}, 8'd{old_code}"
        new = f"6'd{modes[target]['coarse_code']}, 8'd{modes[target]['target_code']}"
        if old not in source:
            raise ValueError(f"testbench {name} lacks {target} MHz setting")
        source = source.replace(old, new)
    return source.replace("// SPDX-License-Identifier: Apache-2.0\n",
                          "// SPDX-License-Identifier: Apache-2.0\n"
                          "// Generated from sky130/modern_25mhz_targets.json.\n", 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = json.loads(args.manifest.read_text(encoding="ascii"))
    defaults = {
        target: {"coarse_code": 0, "target_code": 128, "ndiv": target // 25}
        for target in TARGETS_MHZ
    }
    modes = load_target_presets(args.manifest, defaults)
    if data.get("pdk_version") != "1689ac3f2dc763876eaf967227c7dfe831b031ae":
        raise ValueError("modern target manifest has an unexpected PDK version")
    dco_source = (ROOT / "sky130" / "IntegerPLL_DCO_einvp_coarse_modern_sky130.v").read_text(encoding="ascii")
    expected_load = f"localparam integer STRONG_LOAD_COUNT = {data.get('dco_strong_load_count')};"
    if expected_load not in dco_source:
        raise ValueError("DCO source load count differs from measured manifest")
    if len({modes[target]["coarse_code"] for target in TARGETS_MHZ}) != len(TARGETS_MHZ):
        raise ValueError("modern model needs distinct coarse bands for each target")
    for target in TARGETS_MHZ:
        row = data["targets"][str(target)]
        for key in ("f0_mhz", "f_target_mhz", "f255_mhz"):
            if not isinstance(row.get(key), (int, float)):
                raise ValueError(f"missing {key} for {target} MHz")
        if not row["f0_mhz"] < row["f_target_mhz"] < row["f255_mhz"]:
            raise ValueError(f"nonmonotonic measured frequency table for {target} MHz")
    outputs = {MODE_OUTPUT: render_mode_config(modes), MODEL_OUTPUT: render_model(data)}
    outputs.update({ROOT / "tb" / f"tb_pll_25mhz_{name}_modern.v": render_testbench(name, modes)
                    for name in TB_NAMES})
    for path, content in outputs.items():
        if args.check:
            if not path.exists() or path.read_text(encoding="ascii") != content:
                raise ValueError(f"stale generated file: {path}")
        else:
            if not path.exists() or path.read_text(encoding="ascii") != content:
                path.write_text(content, encoding="ascii")
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
