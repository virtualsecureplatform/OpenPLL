#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="${BUILD_DIR:-$ROOT_DIR/build/synth}"
PDK_ROOT="${PDK_ROOT:-$HOME/.volare}"
PDK="${PDK:-sky130A}"
STD_CELL_LIBRARY="${STD_CELL_LIBRARY:-sky130_fd_sc_hd}"
STD_CELL_LIB="$PDK_ROOT/$PDK/libs.ref/$STD_CELL_LIBRARY/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
DLF_FRAC_WIDTH="${DLF_FRAC_WIDTH:-8}"
DLF_ACQ_BOOST_SHIFT="${DLF_ACQ_BOOST_SHIFT:-0}"
DLF_ACQ_BOOST_AFTER="${DLF_ACQ_BOOST_AFTER:-3}"
DLF_ACQ_RAIL_BOOST="${DLF_ACQ_RAIL_BOOST:-0}"
DLF_ACQ_FORCE_RAIL_CODE="${DLF_ACQ_FORCE_RAIL_CODE:-0}"
DLF_UPDATE_ON_PLLOUT="${DLF_UPDATE_ON_PLLOUT:-0}"
DLF_PROP_RAIL_GUARD="${DLF_PROP_RAIL_GUARD:-0}"
DCO_CONTROL_REGISTERED="${DCO_CONTROL_REGISTERED:-1}"

if [[ ! -f "$STD_CELL_LIB" ]]; then
    echo "Missing liberty file: $STD_CELL_LIB" >&2
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

echo "Wrote $BUILD_DIR/IntegerPLL_DigitalCore_sky130.v (DLF_FRAC_WIDTH=$DLF_FRAC_WIDTH DLF_ACQ_BOOST_SHIFT=$DLF_ACQ_BOOST_SHIFT DLF_ACQ_BOOST_AFTER=$DLF_ACQ_BOOST_AFTER DLF_ACQ_RAIL_BOOST=$DLF_ACQ_RAIL_BOOST DLF_ACQ_FORCE_RAIL_CODE=$DLF_ACQ_FORCE_RAIL_CODE DLF_UPDATE_ON_PLLOUT=$DLF_UPDATE_ON_PLLOUT DLF_PROP_RAIL_GUARD=$DLF_PROP_RAIL_GUARD DCO_CONTROL_REGISTERED=$DCO_CONTROL_REGISTERED)"
