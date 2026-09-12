// SPDX-License-Identifier: Apache-2.0
// Diagnostic analog boundary selecting configured or experimental acquiring RTL.
`timescale 1ns/1ps
module IntegerPLL_Cosim (
 input wire PLLOUT, RESET_N, PLL_ENABLE, REFCLK, ACQUIRE,
 input wire [1:0] BBPD,
 input wire [7:0] SEED, KI,
 input wire [4:0] KP, MODE_DIVIDER,
 input wire [5:0] COARSE_SEED,
 output wire CLKDIV_RETIMED, BBPD_RESET_N, TRACKING,
 output wire [7:0] DCO_CODE,
 output wire [9:0] DLF_CODE,
 output wire [5:0] COARSE_CODE
);
 wire en, clear, override_ext, polarity;
 wire [7:0] ratio;
 wire [9:0] preset;
 wire [7:0] ki_config;
 wire [4:0] kp_config;
 wire [5:0] coarse;
 wire legacy_div,legacy_tracking;
 wire [7:0] legacy_code;
 wire [9:0] legacy_dlf;
 wire acq_div,acq_reset,acq_tracking;
 wire [7:0] acq_code;
 wire [9:0] acq_dlf;
 wire [5:0] acq_coarse;
 assign BBPD_RESET_N = ACQUIRE ? acq_reset : RESET_N && en && !clear;
 assign CLKDIV_RETIMED=ACQUIRE ? acq_div : legacy_div;
 assign TRACKING=ACQUIRE ? acq_tracking : legacy_tracking;
 assign DCO_CODE=ACQUIRE ? acq_code : legacy_code;
 assign DLF_CODE=ACQUIRE ? acq_dlf : legacy_dlf;
 assign COARSE_CODE=ACQUIRE ? acq_coarse : COARSE_SEED;
 IntegerPLL_AcquiringCore acquiring_core(
 .REFCLK(REFCLK),.PLLOUT(PLLOUT),.RESET_N(RESET_N),.PLL_ENABLE(PLL_ENABLE && ACQUIRE),
 .FEEDBACK_DIVIDER(MODE_DIVIDER),.BBPD(BBPD),.KI(KI),.KP(KP),
 .CLKDIV_RETIMED(acq_div),.BBPD_RESET_N(acq_reset),.TRACKING(acq_tracking),
 .CONFIG_BUSY(),.FAILED(),.COARSE_CODE(acq_coarse),.DCO_CODE(acq_code),.DLF_CODE(acq_dlf),
 .COARSETHERMAL_CODE(),.DCO_THERM());
 IntegerPLL_25MHzModeController controller (
 .CLKDIV_RETIMED(legacy_div), .RESET_N(RESET_N),
 .PLL_ENABLE(PLL_ENABLE && !ACQUIRE), .FEEDBACK_DIVIDER(MODE_DIVIDER),
 .DLF_En(en), .DLF_Clear(clear), .DLF_Ext_Override(override_ext),
 .DLF_IN_POL(polarity), .DLF_Ext_Data(preset), .DLF_KI(ki_config),
 .DLF_KP(kp_config), .COARSEBINARY_CODE(coarse), .MMDCLKDIV_RATIO(ratio),
 .TRACKING(legacy_tracking), .CONFIG_BUSY(), .TARGET_MHZ(),
 .TARGET_DCO_CODE(), .CONFIG_VALID());
 IntegerPLL_DigitalCore #(.DLF_FRAC_WIDTH(2), .DLF_PROP_RAIL_GUARD(1)) core (
 .PLLOUT(PLLOUT), .RESET_N(RESET_N), .BBPD(BBPD),
 .DLF_En(en), .DLF_Clear(clear), .DLF_Ext_Override(override_ext),
 .DLF_IN_POL(polarity), .DLF_Ext_Data({SEED,2'b00}),
 .DLF_KI(KI), .DLF_KP(KP), .COARSEBINARY_CODE(COARSE_SEED),
 .MMDCLKDIV_RATIO(ratio), .CLKDIV_RETIMED(legacy_div),
 .DCO_CODE(legacy_code), .DLF_CODE(legacy_dlf), .PLLOUT_DIV(),
 .COARSETHERMAL_CODE(), .Medium_BINARY_CODE(), .Fine_BINARY_CODE(),
 .Medium_CAPS_CTRL(), .Fine_CAPS_CTRL(), .DCO_THERM());
endmodule
