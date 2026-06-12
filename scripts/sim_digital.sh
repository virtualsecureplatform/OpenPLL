#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/build/sim"

mkdir -p "$BUILD_DIR"

iverilog -g2012 -Wall \
    -o "$BUILD_DIR/tb_digital_core.vvp" \
    "$ROOT_DIR/rtl/IntegerPLL_B2TH.v" \
    "$ROOT_DIR/rtl/IntegerPLL_MMD_Retimer.v" \
    "$ROOT_DIR/rtl/IntegerPLL_Divider.v" \
    "$ROOT_DIR/rtl/IntegerPLL_DLF.v" \
    "$ROOT_DIR/rtl/IntegerPLL_DigitalCore.v" \
    "$ROOT_DIR/tb/tb_digital_core.v"

vvp "$BUILD_DIR/tb_digital_core.vvp"

iverilog -g2012 -Wall \
    -o "$BUILD_DIR/tb_pll_top_model.vvp" \
    "$ROOT_DIR/rtl/IntegerPLL_B2TH.v" \
    "$ROOT_DIR/rtl/IntegerPLL_MMD_Retimer.v" \
    "$ROOT_DIR/rtl/IntegerPLL_Divider.v" \
    "$ROOT_DIR/rtl/IntegerPLL_DLF.v" \
    "$ROOT_DIR/rtl/IntegerPLL_DigitalCore.v" \
    "$ROOT_DIR/rtl/IntegerPLL_Top.v" \
    "$ROOT_DIR/models/IntegerPLL_BBPD_model.v" \
    "$ROOT_DIR/models/IntegerPLL_DCO_model.v" \
    "$ROOT_DIR/tb/tb_pll_top_model.v"

vvp "$BUILD_DIR/tb_pll_top_model.vvp"

"$ROOT_DIR/scripts/sim_pll_top_acq_model.sh"

iverilog -g2012 -Wall \
    -o "$BUILD_DIR/tb_digital_loop_acq.vvp" \
    "$ROOT_DIR/rtl/IntegerPLL_B2TH.v" \
    "$ROOT_DIR/rtl/IntegerPLL_MMD_Retimer.v" \
    "$ROOT_DIR/rtl/IntegerPLL_Divider.v" \
    "$ROOT_DIR/rtl/IntegerPLL_DLF.v" \
    "$ROOT_DIR/rtl/IntegerPLL_DigitalCore.v" \
    "$ROOT_DIR/tb/tb_digital_loop_acq.v"

vvp "$BUILD_DIR/tb_digital_loop_acq.vvp"
