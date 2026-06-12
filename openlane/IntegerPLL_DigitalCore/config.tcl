# SPDX-License-Identifier: Apache-2.0

set ::env(DESIGN_NAME) IntegerPLL_DigitalCore

set ::env(VERILOG_FILES) "\
    $::env(DESIGN_DIR)/../../rtl/IntegerPLL_B2TH.v \
    $::env(DESIGN_DIR)/../../rtl/IntegerPLL_MMD_Retimer.v \
    $::env(DESIGN_DIR)/../../rtl/IntegerPLL_Divider.v \
    $::env(DESIGN_DIR)/../../rtl/IntegerPLL_DLF.v \
    $::env(DESIGN_DIR)/../../rtl/IntegerPLL_DigitalCore.v"

set ::env(CLOCK_PORT) "PLLOUT"
set ::env(CLOCK_PERIOD) "2.0"

set ::env(FP_SIZING) absolute
set ::env(DIE_AREA) "0 0 120 120"
set ::env(PL_TARGET_DENSITY) 0.42

set ::env(SYNTH_STRATEGY) "AREA 0"
set ::env(SYNTH_MAX_FANOUT) 8

set ::env(RUN_CVC) 0
