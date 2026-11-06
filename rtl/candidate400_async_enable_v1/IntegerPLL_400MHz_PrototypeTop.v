// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

// Build with USE_POWER_PINS for the physical macro.
module IntegerPLL_400MHz_PrototypeTop (
`ifdef USE_POWER_PINS
    inout wire VPWR, VGND, VPB, VNB,
`endif
    input wire REFCLK, RESET_N, PLL_ENABLE,
    input wire [5:0] STARTUP_COARSE,
    input wire [7:0] STARTUP_FINE,
    input wire STARTUP_INCREASING,
    input wire [7:0] KI,
    input wire [4:0] KP,
    output wire PLLOUT, CLKDIV_RETIMED,
    output wire CONFIG_READY, CONFIG_BUSY, TRACKING, FAILED,
    output wire [5:0] COARSE_CODE,
    output wire [7:0] DCO_CODE,
    output wire [9:0] DLF_CODE
);
    wire osc_reset_n, bbpd_reset_n;
    wire [1:0] bbpd;
    wire [46:0] coarse_therm;
    wire [254:0] fine_therm;
    IntegerPLL_ProgrammedCore digital (
        .REFCLK(REFCLK),.PLLOUT(PLLOUT),.RESET_N(RESET_N),.PLL_ENABLE(PLL_ENABLE),
        .STARTUP_COARSE(STARTUP_COARSE),.STARTUP_FINE(STARTUP_FINE),
        .STARTUP_INCREASING(STARTUP_INCREASING),.KI(KI),.KP(KP),.BBPD(bbpd),
        .OSC_RESET_N(osc_reset_n),.CONFIG_READY(CONFIG_READY),
        .CLKDIV_RETIMED(CLKDIV_RETIMED),.BBPD_RESET_N(bbpd_reset_n),
        .TRACKING(TRACKING),.CONFIG_BUSY(CONFIG_BUSY),.FAILED(FAILED),
        .COARSE_CODE(COARSE_CODE),.DCO_CODE(DCO_CODE),.DLF_CODE(DLF_CODE),
        .COARSETHERMAL_CODE(coarse_therm),.DCO_THERM(fine_therm));
    IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD36_C1FINE160 oscillator (
`ifdef USE_POWER_PINS
        .VPWR(VPWR),.VGND(VGND),.VPB(VPB),.VNB(VNB),
`endif
        .RESET_N(osc_reset_n),.COARSETHERMAL_CODE(coarse_therm),
        .DCO_THERM(fine_therm),.PLLOUT(PLLOUT));
    IntegerPLL_BBPD detector (
`ifdef USE_POWER_PINS
        .VPWR(VPWR),.VGND(VGND),.VPB(VPB),.VNB(VNB),
`endif
        .REF(REFCLK),.CLKDIVR(CLKDIV_RETIMED),.RESET_N(bbpd_reset_n),.BBPD(bbpd));
endmodule
`default_nettype wire
