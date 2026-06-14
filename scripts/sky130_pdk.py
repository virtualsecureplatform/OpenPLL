#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Sky130 PDK root selection helpers."""

from __future__ import annotations

import os
from pathlib import Path


def default_pdk_root(pdk: str | None = None) -> str:
    """Return the preferred local Sky130 PDK root.

    Prefer the Ciel Volare tree under ~/.volare/ciel/sky130. If that tree is
    versioned, return the newest versions/* directory because LibreLane and
    the SPICE scripts expect PDK_ROOT/sky130A to exist.
    """

    pdk_name = pdk or os.environ.get("PDK", "sky130A")
    legacy_root = Path.home() / ".volare"
    ciel_root = Path(os.environ.get("CIEL_SKY130_ROOT", legacy_root / "ciel" / "sky130")).expanduser()

    if (ciel_root / pdk_name).is_dir():
        detected_root = ciel_root
    else:
        current_root = None
        current_file = ciel_root / "current"
        if current_file.is_file():
            current_version = current_file.read_text(encoding="ascii", errors="ignore").strip()
            candidate = ciel_root / "versions" / current_version
            if (candidate / pdk_name).is_dir():
                current_root = candidate
        version_roots = sorted(
            path for path in (ciel_root / "versions").glob("*") if path.is_dir()
        )
        detected_root = current_root or (version_roots[-1] if version_roots else legacy_root)

    env_root = os.environ.get("PDK_ROOT")
    if not env_root:
        return str(detected_root)

    root = Path(env_root).expanduser()
    if root == legacy_root:
        return str(detected_root)
    if root == ciel_root and not (root / pdk_name).is_dir():
        return str(detected_root)
    return str(root)
