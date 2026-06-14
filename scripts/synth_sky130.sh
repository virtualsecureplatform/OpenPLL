#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${BUILD_DIR:-$ROOT_DIR/build/synth}"
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
STD_CELL_LIB="$PDK_ROOT/$PDK/libs.ref/$STD_CELL_LIBRARY/lib/${STD_CELL_LIBRARY}__tt_025C_1v80.lib"
DLF_FRAC_WIDTH="${DLF_FRAC_WIDTH:-8}"
DLF_ACQ_BOOST_SHIFT="${DLF_ACQ_BOOST_SHIFT:-0}"
DLF_ACQ_BOOST_AFTER="${DLF_ACQ_BOOST_AFTER:-3}"
DLF_ACQ_RAIL_BOOST="${DLF_ACQ_RAIL_BOOST:-0}"
DLF_ACQ_FORCE_RAIL_CODE="${DLF_ACQ_FORCE_RAIL_CODE:-0}"
DLF_UPDATE_ON_PLLOUT="${DLF_UPDATE_ON_PLLOUT:-0}"
DLF_PROP_RAIL_GUARD="${DLF_PROP_RAIL_GUARD:-0}"
DCO_CONTROL_REGISTERED="${DCO_CONTROL_REGISTERED:-1}"
DCO_COARSE_BITS="${DCO_COARSE_BITS:-0}"

if [[ ! -f "$STD_CELL_LIB" ]]; then
    LIB_DIR="$PDK_ROOT/$PDK/libs.ref/$STD_CELL_LIBRARY/lib"
    mapfile -t STD_CELL_LIB_CANDIDATES < <(find "$LIB_DIR" -maxdepth 1 -type f -name "${STD_CELL_LIBRARY}__tt_025C_*.lib" 2>/dev/null | sort)
    if (( ${#STD_CELL_LIB_CANDIDATES[@]} > 0 )); then
        STD_CELL_LIB="${STD_CELL_LIB_CANDIDATES[0]}"
    else
        echo "Missing liberty file under: $LIB_DIR" >&2
        echo "Expected ${STD_CELL_LIBRARY}__tt_025C_1v80.lib or another tt_025C liberty view." >&2
        exit 1
    fi
fi

if (( DCO_COARSE_BITS < 0 || DCO_COARSE_BITS > 4 )); then
    echo "DCO_COARSE_BITS must be in the range 0..4, got $DCO_COARSE_BITS" >&2
    exit 1
fi

mkdir -p "$BUILD_DIR"

yosys -p "
    read_verilog \
        $ROOT_DIR/rtl/IntegerPLL_B2TH.v \
        $ROOT_DIR/rtl/IntegerPLL_MMD_Retimer.v \
        $ROOT_DIR/rtl/IntegerPLL_Divider.v \
        $ROOT_DIR/rtl/IntegerPLL_DLF.v \
        $ROOT_DIR/rtl/IntegerPLL_DigitalCore.v;
    chparam -set DLF_FRAC_WIDTH $DLF_FRAC_WIDTH IntegerPLL_DigitalCore;
    chparam -set DLF_ACQ_BOOST_SHIFT $DLF_ACQ_BOOST_SHIFT IntegerPLL_DigitalCore;
    chparam -set DLF_ACQ_BOOST_AFTER $DLF_ACQ_BOOST_AFTER IntegerPLL_DigitalCore;
    chparam -set DLF_ACQ_RAIL_BOOST $DLF_ACQ_RAIL_BOOST IntegerPLL_DigitalCore;
    chparam -set DLF_ACQ_FORCE_RAIL_CODE $DLF_ACQ_FORCE_RAIL_CODE IntegerPLL_DigitalCore;
    chparam -set DLF_UPDATE_ON_PLLOUT $DLF_UPDATE_ON_PLLOUT IntegerPLL_DigitalCore;
    chparam -set DLF_PROP_RAIL_GUARD $DLF_PROP_RAIL_GUARD IntegerPLL_DigitalCore;
    chparam -set DCO_CONTROL_REGISTERED $DCO_CONTROL_REGISTERED IntegerPLL_DigitalCore;
    chparam -set DCO_COARSE_BITS $DCO_COARSE_BITS IntegerPLL_DigitalCore;
    hierarchy -check -top IntegerPLL_DigitalCore;
    synth -top IntegerPLL_DigitalCore;
    dfflibmap -liberty $STD_CELL_LIB;
    abc -liberty $STD_CELL_LIB;
    flatten;
    delete t:\$scopeinfo;
    clean;
    stat -liberty $STD_CELL_LIB;
    write_verilog -noattr $BUILD_DIR/IntegerPLL_DigitalCore_sky130.v;
" 2>&1 | tee "$BUILD_DIR/yosys_sky130.log"

echo "Wrote $BUILD_DIR/IntegerPLL_DigitalCore_sky130.v (DLF_FRAC_WIDTH=$DLF_FRAC_WIDTH DLF_ACQ_BOOST_SHIFT=$DLF_ACQ_BOOST_SHIFT DLF_ACQ_BOOST_AFTER=$DLF_ACQ_BOOST_AFTER DLF_ACQ_RAIL_BOOST=$DLF_ACQ_RAIL_BOOST DLF_ACQ_FORCE_RAIL_CODE=$DLF_ACQ_FORCE_RAIL_CODE DLF_UPDATE_ON_PLLOUT=$DLF_UPDATE_ON_PLLOUT DLF_PROP_RAIL_GUARD=$DLF_PROP_RAIL_GUARD DCO_CONTROL_REGISTERED=$DCO_CONTROL_REGISTERED DCO_COARSE_BITS=$DCO_COARSE_BITS)"
