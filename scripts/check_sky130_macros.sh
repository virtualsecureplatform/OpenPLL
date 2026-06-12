#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/build/check"
PDK_ROOT="${PDK_ROOT:-$HOME/.volare}"
PDK="${PDK:-sky130A}"
STD_CELL_LIBRARY="${STD_CELL_LIBRARY:-sky130_fd_sc_hd}"
STD_CELL_VERILOG="$PDK_ROOT/$PDK/libs.ref/$STD_CELL_LIBRARY/verilog/$STD_CELL_LIBRARY.v"
STD_CELL_PRIMITIVES="$PDK_ROOT/$PDK/libs.ref/$STD_CELL_LIBRARY/verilog/primitives.v"
COMPILE_OUT="$BUILD_DIR/sky130_macro_compile.vvp"
EINVP_COMPILE_OUT="$BUILD_DIR/sky130_dco_einvp_compile.vvp"
SMOKE_OUT="$BUILD_DIR/sky130_macro_top_smoke.vvp"
LOG="$BUILD_DIR/sky130_macro_top_smoke.log"

if [[ ! -f "$STD_CELL_PRIMITIVES" ]]; then
    echo "Missing Sky130 primitives Verilog: $STD_CELL_PRIMITIVES" >&2
    exit 1
fi

if [[ ! -f "$STD_CELL_VERILOG" ]]; then
    echo "Missing Sky130 standard-cell Verilog: $STD_CELL_VERILOG" >&2
    exit 1
fi

mkdir -p "$BUILD_DIR"

iverilog -g2012 -DUSE_POWER_PINS -DUSE_CELL_POWER_PINS -Wall \
    -s IntegerPLL_Top \
    -o "$COMPILE_OUT" \
    "$STD_CELL_PRIMITIVES" \
    "$STD_CELL_VERILOG" \
    "$ROOT_DIR/rtl/IntegerPLL_B2TH.v" \
    "$ROOT_DIR/rtl/IntegerPLL_MMD_Retimer.v" \
    "$ROOT_DIR/rtl/IntegerPLL_Divider.v" \
    "$ROOT_DIR/rtl/IntegerPLL_DLF.v" \
    "$ROOT_DIR/rtl/IntegerPLL_DigitalCore.v" \
    "$ROOT_DIR/rtl/IntegerPLL_Top.v" \
    "$ROOT_DIR/sky130/IntegerPLL_BBPD_sky130.v" \
    "$ROOT_DIR/sky130/IntegerPLL_DCO_sky130.v"

iverilog -g2012 -DUSE_POWER_PINS -DUSE_CELL_POWER_PINS -Wall \
    -s IntegerPLL_DCO_EINVP \
    -o "$EINVP_COMPILE_OUT" \
    "$STD_CELL_PRIMITIVES" \
    "$STD_CELL_VERILOG" \
    "$ROOT_DIR/sky130/IntegerPLL_DCO_einvp_sky130.v"

iverilog -g2012 -DUSE_POWER_PINS -Wall \
    -s tb_sky130_top_smoke \
    -o "$SMOKE_OUT" \
    "$ROOT_DIR/rtl/IntegerPLL_B2TH.v" \
    "$ROOT_DIR/rtl/IntegerPLL_MMD_Retimer.v" \
    "$ROOT_DIR/rtl/IntegerPLL_Divider.v" \
    "$ROOT_DIR/rtl/IntegerPLL_DLF.v" \
    "$ROOT_DIR/rtl/IntegerPLL_DigitalCore.v" \
    "$ROOT_DIR/rtl/IntegerPLL_Top.v" \
    "$ROOT_DIR/tb/tb_sky130_top_smoke.v"

vvp "$SMOKE_OUT" | tee "$LOG"

echo "Wrote $COMPILE_OUT"
echo "Wrote $EINVP_COMPILE_OUT"
echo "Wrote $SMOKE_OUT"
echo "Wrote $LOG"
