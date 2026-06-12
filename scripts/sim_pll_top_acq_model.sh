#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/build/sim"

KI="${KI:-255}"
KP="${KP:-4}"
RUN_NS="${RUN_NS:-200000}"
TARGET_CODE="${TARGET_CODE:-128}"
TOL_CODE="${TOL_CODE:-32}"
LOW_INIT="${LOW_INIT:-0}"
HIGH_INIT="${HIGH_INIT:-1020}"
MMD_RATIO="${MMD_RATIO:-8}"
REF_HALF_PS="${REF_HALF_PS:-39240}"
DCO_USE_PIECEWISE5="${DCO_USE_PIECEWISE5:-0}"
DCO_F0_MHZ="${DCO_F0_MHZ:-46.25672588520797}"
DCO_F64_MHZ="${DCO_F64_MHZ:-47.95039109460694}"
DCO_F128_MHZ="${DCO_F128_MHZ:-49.762117807733404}"
DCO_F192_MHZ="${DCO_F192_MHZ:-51.61843654151962}"
DCO_F255_MHZ="${DCO_F255_MHZ:-52.34983089216307}"

mkdir -p "$BUILD_DIR"

iverilog -g2012 -Wall \
    -o "$BUILD_DIR/tb_pll_top_acq_model.vvp" \
    "$ROOT_DIR/rtl/IntegerPLL_B2TH.v" \
    "$ROOT_DIR/rtl/IntegerPLL_MMD_Retimer.v" \
    "$ROOT_DIR/rtl/IntegerPLL_Divider.v" \
    "$ROOT_DIR/rtl/IntegerPLL_DLF.v" \
    "$ROOT_DIR/rtl/IntegerPLL_DigitalCore.v" \
    "$ROOT_DIR/rtl/IntegerPLL_Top.v" \
    "$ROOT_DIR/models/IntegerPLL_BBPD_model.v" \
    "$ROOT_DIR/models/IntegerPLL_DCO_model.v" \
    "$ROOT_DIR/tb/tb_pll_top_acq_model.v"

vvp "$BUILD_DIR/tb_pll_top_acq_model.vvp" \
    "+KI=$KI" \
    "+KP=$KP" \
    "+RUN_NS=$RUN_NS" \
    "+TARGET_CODE=$TARGET_CODE" \
    "+TOL_CODE=$TOL_CODE" \
    "+LOW_INIT=$LOW_INIT" \
    "+HIGH_INIT=$HIGH_INIT" \
    "+MMD_RATIO=$MMD_RATIO" \
    "+REF_HALF_PS=$REF_HALF_PS" \
    "+DCO_USE_PIECEWISE5=$DCO_USE_PIECEWISE5" \
    "+DCO_F0_MHZ=$DCO_F0_MHZ" \
    "+DCO_F64_MHZ=$DCO_F64_MHZ" \
    "+DCO_F128_MHZ=$DCO_F128_MHZ" \
    "+DCO_F192_MHZ=$DCO_F192_MHZ" \
    "+DCO_F255_MHZ=$DCO_F255_MHZ" \
    "$@"
