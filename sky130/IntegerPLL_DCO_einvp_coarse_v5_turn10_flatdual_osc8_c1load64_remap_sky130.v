// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

// Experimental flat two-core DCO for 100/250/300/400/450 MHz screening.
// Physical and PVT qualification are required before release use.
module IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_FLATDUAL_OSC8_C1LOAD64_REMAP (
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
    wire first_lower_select;
    wire second_lower_select;
    wire fourth_lower_select;
    wire fifth_lower_select;
    wire first_two_lower_select;
    wire last_two_lower_select;
    wire lower_band_select;
    wire slow_first_coarse;
    wire slow_second_coarse;
    wire fast_first_coarse;
    wire fast_out;
    wire slow_out;

    // Logical bands 1/2/4/5 select slow physical bands 0/1/3/4.
    // All other positive logical bands select fast physical band minus one.
    sky130_fd_sc_hd__and2b_1 select_first_lower_band (
        .X(first_lower_select),
        .A_N(COARSETHERMAL_CODE[1]), .B(COARSETHERMAL_CODE[0])
    );
    sky130_fd_sc_hd__and2b_1 select_second_lower_band (
        .X(second_lower_select),
        .A_N(COARSETHERMAL_CODE[2]), .B(COARSETHERMAL_CODE[1])
    );
    sky130_fd_sc_hd__and2b_1 select_fourth_lower_band (
        .X(fourth_lower_select),
        .A_N(COARSETHERMAL_CODE[4]), .B(COARSETHERMAL_CODE[3])
    );
    sky130_fd_sc_hd__and2b_1 select_fifth_lower_band (
        .X(fifth_lower_select),
        .A_N(COARSETHERMAL_CODE[5]), .B(COARSETHERMAL_CODE[4])
    );
    sky130_fd_sc_hd__or2_1 combine_first_two_lower_bands (
        .X(first_two_lower_select),
        .A(first_lower_select), .B(second_lower_select)
    );
    sky130_fd_sc_hd__or2_1 combine_last_two_lower_bands (
        .X(last_two_lower_select),
        .A(fourth_lower_select), .B(fifth_lower_select)
    );
    sky130_fd_sc_hd__or2_1 combine_lower_bands (
        .X(lower_band_select),
        .A(first_two_lower_select), .B(last_two_lower_select)
    );
    sky130_fd_sc_hd__and2_4 remap_slow_first (
        .X(slow_first_coarse),
        .A(COARSETHERMAL_CODE[0]), .B(COARSETHERMAL_CODE[1])
    );
    sky130_fd_sc_hd__and2_4 remap_slow_second (
        .X(slow_second_coarse),
        .A(COARSETHERMAL_CODE[1]), .B(COARSETHERMAL_CODE[2])
    );
    // Coarse code zero exposes fast physical band 1 for SF/FS 450 MHz.
    // Positive logical codes retain the original one-position remap.
    sky130_fd_sc_hd__or2b_2 remap_fast_zero_to_first (
        .X(fast_first_coarse),
        .A(COARSETHERMAL_CODE[1]), .B_N(COARSETHERMAL_CODE[0])
    );

    IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8 fast_core (
`ifdef USE_POWER_PINS
        .VPWR(VPWR), .VGND(VGND), .VPB(VPB), .VNB(VNB),
`endif
        .RESET_N(RESET_N),
        .COARSETHERMAL_CODE({1'b0, COARSETHERMAL_CODE[46:2], fast_first_coarse}),
        .DCO_THERM(DCO_THERM),
        .PLLOUT(fast_out)
    );

    IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_C1LOAD64 slow_core (
`ifdef USE_POWER_PINS
        .VPWR(VPWR), .VGND(VGND), .VPB(VPB), .VNB(VNB),
`endif
        .RESET_N(RESET_N),
        .COARSETHERMAL_CODE({1'b0, COARSETHERMAL_CODE[46:3],
                             slow_second_coarse, slow_first_coarse}),
        .DCO_THERM(DCO_THERM),
        .PLLOUT(slow_out)
    );

    sky130_fd_sc_hd__mux2_1 output_select (
        .X(PLLOUT), .A0(fast_out), .A1(slow_out), .S(lower_band_select)
    );
endmodule

`default_nettype wire
