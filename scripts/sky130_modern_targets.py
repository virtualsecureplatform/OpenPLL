#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Load independently characterized 25 MHz-reference Sky130 mode presets."""

from __future__ import annotations

import json
from pathlib import Path


TARGETS_MHZ = (100, 250, 300, 400, 500)


def load_target_presets(path: Path, defaults: dict[int, dict]) -> dict[int, dict]:
    data = json.loads(path.read_text(encoding="ascii"))
    modes = data.get("targets")
    if not isinstance(modes, dict) or {int(key) for key in modes} != set(TARGETS_MHZ):
        raise ValueError("target manifest must contain exactly 100, 250, 300, 400, 500 MHz")
    result = {}
    for target_mhz in TARGETS_MHZ:
        mode = modes[str(target_mhz)]
        if not isinstance(mode, dict):
            raise ValueError(f"invalid {target_mhz} MHz preset")
        coarse = mode.get("coarse_code")
        fine = mode.get("target_code")
        ndiv = mode.get("ndiv")
        if not isinstance(coarse, int) or not 0 <= coarse <= 47:
            raise ValueError(f"invalid {target_mhz} MHz coarse code")
        if not isinstance(fine, int) or not 4 <= fine <= 251:
            raise ValueError(f"invalid {target_mhz} MHz fine code")
        if ndiv != target_mhz // 25:
            raise ValueError(f"invalid {target_mhz} MHz divider")
        result[target_mhz] = {
            **defaults[target_mhz],
            "coarse_code": coarse,
            "target_code": fine,
            "ndiv": ndiv,
        }
    return result
