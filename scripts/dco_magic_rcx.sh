#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DESIGN_DIR="${DESIGN_DIR:-openlane/IntegerPLL_DCO}"
RUN_TAG="${RUN_TAG:-librelane_signoff}"
RUN_DIR="${RUN_DIR:-$ROOT_DIR/$DESIGN_DIR/runs/$RUN_TAG}"
LIBRELANE_ROOT="${LIBRELANE_ROOT:-/home/ubuntu/sources/librelane}"
PDK_ROOT="${PDK_ROOT:-$HOME/.volare}"
OUT_DIR="${OUT_DIR:-$RUN_DIR/rcx-magic}"
DO_RESISTANCE="${DO_RESISTANCE:-0}"
DO_CAPACITANCE="${DO_CAPACITANCE:-1}"
CTHRESH_FF="${CTHRESH_FF:-0.01}"
EXTRACT_STYLE="${EXTRACT_STYLE:-ngspice()}"

state="$(find "$RUN_DIR" -path '*magic-streamout/state_out.json' | sort -V | tail -n 1)"
if [[ -z "$state" ]]; then
    echo "Missing Magic streamout state under $RUN_DIR; run the DCO LibreLane flow first." >&2
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
