#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/build/check"
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
STD_CELL_LIBRARY="${STD_CELL_LIBRARY:-sky130_fd_sc_hd}"
STD_CELL_VERILOG="$PDK_ROOT/$PDK/libs.ref/$STD_CELL_LIBRARY/verilog/$STD_CELL_LIBRARY.v"
STD_CELL_PRIMITIVES="$PDK_ROOT/$PDK/libs.ref/$STD_CELL_LIBRARY/verilog/primitives.v"
COARSE_DCO_RTL="$ROOT_DIR/sky130/IntegerPLL_DCO_einvp_coarse_sky130.v"
COMPILE_OUT="$BUILD_DIR/sky130_macro_compile.vvp"
EINVP_COMPILE_OUT="$BUILD_DIR/sky130_dco_einvp_compile.vvp"
EINVP_FAST_COMPILE_OUT="$BUILD_DIR/sky130_dco_einvp_fast_compile.vvp"
EINVP_COARSE_COMPILE_OUT="$BUILD_DIR/sky130_dco_einvp_coarse_compile.vvp"
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

require_coarse_dco_fragment() {
    local fragment="$1"
    if ! grep -Fq "$fragment" "$COARSE_DCO_RTL"; then
        echo "Coarse DCO RTL is missing required mirror-delay fragment: $fragment" >&2
        exit 1
    fi
}

if grep -Eq "sky130_fd_sc_(hd|hs)__inv_1" "$COARSE_DCO_RTL"; then
    echo "Coarse DCO must use NAND/NAND2B mirror delay, not an inverter-chain ring" >&2
    exit 1
fi

if grep -Eq "sky130_fd_sc_(hd|hs)__mux4_1" "$COARSE_DCO_RTL"; then
    echo "Coarse DCO must use turn/pass mirror delay, not a mux-selected feedback tap" >&2
    exit 1
fi

if grep -Eq "sky130_fd_sc_hs__buf_(2|4|8|16)[[:space:]]+out_buf" "$COARSE_DCO_RTL"; then
    echo "Coarse DCO output buffer must stay hs__buf_1 to avoid extra oscillator loading" >&2
    exit 1
fi

require_coarse_dco_fragment "sky130_fd_sc_hs__nand2_4 osc_gate"
require_coarse_dco_fragment "input wire [46:0] COARSETHERMAL_CODE"
require_coarse_dco_fragment "wire [47:0] mirror_fwd"
require_coarse_dco_fragment "sky130_fd_sc_hs__nand2_4 mirror_forward"
require_coarse_dco_fragment "sky130_fd_sc_hs__nand2b_4 mirror_turn"
require_coarse_dco_fragment "sky130_fd_sc_hs__nand2b_4 mirror_return"
require_coarse_dco_fragment "sky130_fd_sc_hs__nand2_4 mirror_merge"
require_coarse_dco_fragment "sky130_fd_sc_hs__buf_1 out_buf"
require_coarse_dco_fragment "sky130_fd_sc_hs__nand2_1 tune_load"
require_coarse_dco_fragment "for (f = 0; f < 90; f = f + 1)"
require_coarse_dco_fragment "DCO_THERM_INDEX"
require_coarse_dco_fragment ".A_N(tie_lo)"
require_coarse_dco_fragment ".A(osc_node)"
require_coarse_dco_fragment ".A_N(mirror_ret[i+1])"

if grep -Eq "gen_(c19_)?slow_dco_load|c19_slow_band|mirror_fwd\\[19\\]|mirror_ret\\[19\\]|mirror_fwd\\[20\\]|mirror_ret\\[20\\]" "$COARSE_DCO_RTL"; then
    echo "Coarse DCO must not add deep-node C19/C20 slow-load banks; use local base fine loads instead" >&2
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

iverilog -g2012 -DUSE_POWER_PINS -DUSE_CELL_POWER_PINS -Wall \
    -s IntegerPLL_DCO_EINVP_FAST \
    -o "$EINVP_FAST_COMPILE_OUT" \
    "$STD_CELL_PRIMITIVES" \
    "$STD_CELL_VERILOG" \
    "$ROOT_DIR/sky130/IntegerPLL_DCO_einvp_fast_sky130.v"

iverilog -g2012 -DUSE_POWER_PINS -Wall \
    -s IntegerPLL_DCO_EINVP_COARSE \
    -o "$EINVP_COARSE_COMPILE_OUT" \
    "$ROOT_DIR/sky130/sky130_fd_sc_hd_pll_blackbox.v" \
    "$ROOT_DIR/sky130/IntegerPLL_DCO_einvp_coarse_sky130.v"

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
echo "Wrote $EINVP_FAST_COMPILE_OUT"
echo "Wrote $EINVP_COARSE_COMPILE_OUT"
echo "Wrote $SMOKE_OUT"
echo "Wrote $LOG"
