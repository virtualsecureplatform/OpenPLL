// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module IntegerPLL_Top #(
    parameter DLF_CODE_WIDTH = 10,
    parameter DLF_FRAC_WIDTH = 8,
    parameter DLF_GAIN_WIDTH = 8,
    parameter DLF_ACQ_BOOST_SHIFT = 0,
    parameter DLF_ACQ_BOOST_AFTER = 3,
    parameter DLF_ACQ_RAIL_BOOST = 0,
    parameter DLF_ACQ_FORCE_RAIL_CODE = 0,
    parameter DLF_UPDATE_ON_PLLOUT = 0,
    parameter DLF_PROP_RAIL_GUARD = 0,
    parameter THERM_INVERT = 0,
    parameter DCO_THERM_INVERT = 1,
    parameter DCO_CONTROL_REGISTERED = 1,
    parameter DCO_COARSE_BITS = 0
) (
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
    input wire [DLF_CODE_WIDTH-1:0] DLF_Ext_Data,
    input wire [DLF_GAIN_WIDTH-1:0] DLF_KI,
    input wire [DLF_GAIN_WIDTH-1:0] DLF_KP,
    input wire [5:0] COARSEBINARY_CODE,
    input wire [7:0] MMDCLKDIV_RATIO,
    output wire PLLOUT,
    output wire PLLOUT_DIV,
    output wire CLKDIV_RETIMED,
    output wire [1:0] BBPD_CODE,
    output wire [7:0] DCO_CODE,
    output wire [DLF_CODE_WIDTH-1:0] DLF_CODE
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

    IntegerPLL_DigitalCore #(
        .DLF_CODE_WIDTH(DLF_CODE_WIDTH),
        .DLF_FRAC_WIDTH(DLF_FRAC_WIDTH),
        .DLF_GAIN_WIDTH(DLF_GAIN_WIDTH),
        .DLF_ACQ_BOOST_SHIFT(DLF_ACQ_BOOST_SHIFT),
        .DLF_ACQ_BOOST_AFTER(DLF_ACQ_BOOST_AFTER),
        .DLF_ACQ_RAIL_BOOST(DLF_ACQ_RAIL_BOOST),
        .DLF_ACQ_FORCE_RAIL_CODE(DLF_ACQ_FORCE_RAIL_CODE),
        .DLF_UPDATE_ON_PLLOUT(DLF_UPDATE_ON_PLLOUT),
        .DLF_PROP_RAIL_GUARD(DLF_PROP_RAIL_GUARD),
        .THERM_INVERT(THERM_INVERT),
        .DCO_THERM_INVERT(DCO_THERM_INVERT),
        .DCO_CONTROL_REGISTERED(DCO_CONTROL_REGISTERED),
        .DCO_COARSE_BITS(DCO_COARSE_BITS)
    ) digital_core (
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

    IntegerPLL_DCO oscillator (
`ifdef USE_POWER_PINS
        .VPWR(VPWR),
        .VGND(VGND),
        .VPB(VPB),
        .VNB(VNB),
`endif
        .RESET_N(RESET_N),
`ifdef OPENPLL_DCO_MODEL_COARSE
        .COARSEBINARY_CODE(COARSEBINARY_CODE),
`endif
        .DCO_THERM(dco_therm),
        .PLLOUT(PLLOUT)
    );

endmodule

`default_nettype wire
