// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

// Experimental two-core DCO. Coarse code one selects the lower 400 MHz band;
// all other coarse codes use the fast core. Both cores must be qualified.
module IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALCORE (
`ifdef USE_POWER_PINS
    inout wire VPWR,
    inout wire VGND,
    inout wire VPB,
    inout wire VNB,
`endif
    input wire RESET_N,
    input wire [46:0] COARSETHERMAL_CODE,
    input wire [254:0] DCO_THERM,
    output wire PLLOUT
);
    wire lower_band_select;
    wire slow_first_coarse;
    wire fast_out;
    wire slow_out;

    sky130_fd_sc_hd__and2b_1 select_lower_band (
        .X(lower_band_select),
        .A_N(COARSETHERMAL_CODE[1]),
        .B(COARSETHERMAL_CODE[0])
    );
    sky130_fd_sc_hd__and2_4 remap_slow_first (
        .X(slow_first_coarse),
        .A(COARSETHERMAL_CODE[0]),
        .B(COARSETHERMAL_CODE[1])
    );

    IntegerPLL_DCO_EINVP_COARSE_V5_TURN10 fast_core (
`ifdef USE_POWER_PINS
        .VPWR(VPWR), .VGND(VGND), .VPB(VPB), .VNB(VNB),
`endif
        .RESET_N(RESET_N),
        .COARSETHERMAL_CODE(COARSETHERMAL_CODE),
        .DCO_THERM(DCO_THERM),
        .PLLOUT(fast_out)
    );

    IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8 slow_core (
`ifdef USE_POWER_PINS
        .VPWR(VPWR), .VGND(VGND), .VPB(VPB), .VNB(VNB),
`endif
        .RESET_N(RESET_N),
        .COARSETHERMAL_CODE({COARSETHERMAL_CODE[46:1], slow_first_coarse}),
        .DCO_THERM(DCO_THERM),
        .PLLOUT(slow_out)
    );

    sky130_fd_sc_hd__mux2_1 output_select (
        .X(PLLOUT),
        .A0(fast_out),
        .A1(slow_out),
        .S(lower_band_select)
    );
endmodule

`default_nettype wire
