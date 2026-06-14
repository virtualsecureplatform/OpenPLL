#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_TAG="${RUN_TAG:-librelane_signoff}"
RUN_DIR="$ROOT_DIR/openlane/IntegerPLL_BBPD/runs/$RUN_TAG"
LIBRELANE_ROOT="${LIBRELANE_ROOT:-/home/ubuntu/sources/librelane}"
PDK="${PDK:-sky130A}"
CIEL_SKY130_ROOT="${CIEL_SKY130_ROOT:-$HOME/.volare/ciel/sky130}"
LEGACY_VOLARE_ROOT="${LEGACY_VOLARE_ROOT:-$HOME/.volare}"
NORMALIZED_PDK_ROOT="${PDK_ROOT:-}"
if [[ "$NORMALIZED_PDK_ROOT" == "~/"* ]]; then
    NORMALIZED_PDK_ROOT="$HOME/${NORMALIZED_PDK_ROOT#~/}"
fi
if [[ -z "${PDK_ROOT:-}" || "${NORMALIZED_PDK_ROOT%/}" == "${LEGACY_VOLARE_ROOT%/}" || ( "${NORMALIZED_PDK_ROOT%/}" == "${CIEL_SKY130_ROOT%/}" && ! -d "$NORMALIZED_PDK_ROOT/$PDK" ) ]]; then
    if [[ -d "$CIEL_SKY130_ROOT/$PDK" ]]; then
        PDK_ROOT="$CIEL_SKY130_ROOT"
    else
        CIEL_SKY130_CURRENT_ROOT=""
        if [[ -f "$CIEL_SKY130_ROOT/current" ]]; then
            CIEL_SKY130_CURRENT_VERSION="$(tr -d '[:space:]' < "$CIEL_SKY130_ROOT/current")"
            if [[ -n "$CIEL_SKY130_CURRENT_VERSION" && -d "$CIEL_SKY130_ROOT/versions/$CIEL_SKY130_CURRENT_VERSION/$PDK" ]]; then
                CIEL_SKY130_CURRENT_ROOT="$CIEL_SKY130_ROOT/versions/$CIEL_SKY130_CURRENT_VERSION"
            fi
        fi
        CIEL_SKY130_VERSION_ROOT="${CIEL_SKY130_CURRENT_ROOT:-$(find "$CIEL_SKY130_ROOT/versions" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | tail -n 1 || true)}"
        PDK_ROOT="${CIEL_SKY130_VERSION_ROOT:-$LEGACY_VOLARE_ROOT}"
    fi
fi
OUT_DIR="${OUT_DIR:-$RUN_DIR/rcx-magic}"
DO_RESISTANCE="${DO_RESISTANCE:-0}"
DO_CAPACITANCE="${DO_CAPACITANCE:-1}"
CTHRESH_FF="${CTHRESH_FF:-0.01}"
EXTRACT_STYLE="${EXTRACT_STYLE:-ngspice()}"

state="$(find "$RUN_DIR" -path '*magic-streamout/state_out.json' | sort -V | tail -n 1)"
if [[ -z "$state" ]]; then
    echo "Missing Magic streamout state under $RUN_DIR; run make bbpd-librelane-signoff first." >&2
    exit 1
fi

config_in="${state%state_out.json}config.json"
config_rcx="$RUN_DIR/rcx-magic.config.json"

python3 - "$config_in" "$config_rcx" "$DO_RESISTANCE" "$DO_CAPACITANCE" "$CTHRESH_FF" "$EXTRACT_STYLE" <<'PY'
import json
import sys
from pathlib import Path

config_in, config_out, do_res, do_cap, cthresh, style = sys.argv[1:]
data = json.loads(Path(config_in).read_text())
data["MAGIC_RCX_DO_RESISTANCE"] = bool(int(do_res))
data["MAGIC_RCX_DO_CAPACITANCE"] = bool(int(do_cap))
data["MAGIC_RCX_CTHRESH"] = float(cthresh)
data["MAGIC_RCX_EXTRACT_STYLE"] = style
Path(config_out).write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
print(
    "Wrote",
    config_out,
    "resistance=",
    data["MAGIC_RCX_DO_RESISTANCE"],
    "capacitance=",
    data["MAGIC_RCX_DO_CAPACITANCE"],
    "cthresh_fF=",
    data["MAGIC_RCX_CTHRESH"],
)
PY

rm -rf "$OUT_DIR"

nix-shell "$LIBRELANE_ROOT" --run \
    "python3 -m librelane.steps run --condensed --hide-progress-bar --pdk-root '$PDK_ROOT' --id Magic.RCX --config '$config_rcx' --state-in '$state' --output '$OUT_DIR'"
