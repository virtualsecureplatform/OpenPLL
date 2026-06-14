// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module IntegerPLL_HardMacroTop_EINVP (
`ifdef USE_POWER_PINS
    inout wire VPWR,
    inout wire VGND,
    inout wire VPB,
    inout wire VNB,
`endif
    input wire REF,
    input wire RESET_N,
    input wire DLF_En,
    input wire DLF_Clear,
    input wire DLF_Ext_Override,
    input wire DLF_IN_POL,
    input wire [9:0] DLF_Ext_Data,
    input wire [7:0] DLF_KI,
    input wire [7:0] DLF_KP,
    input wire [5:0] COARSEBINARY_CODE,
    input wire [7:0] MMDCLKDIV_RATIO,
    output wire PLLOUT,
    output wire PLLOUT_DIV,
    output wire CLKDIV_RETIMED,
    output wire [1:0] BBPD_CODE,
    output wire [7:0] DCO_CODE,
    output wire [9:0] DLF_CODE
);

    wire [46:0] coarse_ctrl;
    wire [4:0] medium_binary;
    wire [4:0] fine_binary;
    wire [30:0] medium_ctrl;
    wire [30:0] fine_ctrl;
    wire [254:0] dco_therm;
    wire bbpd_reset_n;

    assign bbpd_reset_n = RESET_N && DLF_En && !DLF_Clear;

    IntegerPLL_BBPD phase_detector (
`ifdef USE_POWER_PINS
        .VPWR(VPWR),
        .VGND(VGND),
        .VPB(VPB),
        .VNB(VNB),
`endif
        .REF(REF),
        .CLKDIVR(CLKDIV_RETIMED),
        .RESET_N(bbpd_reset_n),
        .BBPD(BBPD_CODE)
    );

    IntegerPLL_DigitalCore digital_core (
`ifdef USE_POWER_PINS
        .VPWR(VPWR),
        .VGND(VGND),
`endif
        .PLLOUT(PLLOUT),
        .RESET_N(RESET_N),
        .BBPD(BBPD_CODE),
        .DLF_En(DLF_En),
        .DLF_Clear(DLF_Clear),
        .DLF_Ext_Override(DLF_Ext_Override),
        .DLF_IN_POL(DLF_IN_POL),
        .DLF_Ext_Data(DLF_Ext_Data),
        .DLF_KI(DLF_KI),
        .DLF_KP(DLF_KP),
        .COARSEBINARY_CODE(COARSEBINARY_CODE),
        .MMDCLKDIV_RATIO(MMDCLKDIV_RATIO),
        .CLKDIV_RETIMED(CLKDIV_RETIMED),
        .PLLOUT_DIV(PLLOUT_DIV),
        .COARSETHERMAL_CODE(coarse_ctrl),
        .Medium_BINARY_CODE(medium_binary),
        .Fine_BINARY_CODE(fine_binary),
        .Medium_CAPS_CTRL(medium_ctrl),
        .Fine_CAPS_CTRL(fine_ctrl),
        .DCO_CODE(DCO_CODE),
        .DCO_THERM(dco_therm),
        .DLF_CODE(DLF_CODE)
    );

    IntegerPLL_DCO_EINVP_COARSE oscillator (
`ifdef USE_POWER_PINS
        .VPWR(VPWR),
        .VGND(VGND),
        .VPB(VPB),
        .VNB(VNB),
`endif
        .RESET_N(RESET_N),
        .COARSETHERMAL_CODE(coarse_ctrl),
        .DCO_THERM(dco_therm),
        .PLLOUT(PLLOUT)
    );

endmodule

`default_nettype wire
