// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

// Experimental assembly with two logical slow bands and one-position fast
// coarse remapping. Both routed cores require extracted PVT qualification.
module IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_OSC8_REMAP_DBUF_GUARD (
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
    wire [46:0] coarse_fast_buffered;
    wire [46:0] coarse_slow_buffered;
    wire [254:0] fine_fast_buffered;
    wire [254:0] fine_slow_buffered;
    genvar c;
    generate
        for (c = 0; c < 47; c = c + 1) begin : gen_coarse_buffer
            sky130_fd_sc_hd__buf_8 fast_driver (
                .X(coarse_fast_buffered[c]), .A(COARSETHERMAL_CODE[c])
            );
            sky130_fd_sc_hd__buf_8 slow_driver (
                .X(coarse_slow_buffered[c]), .A(COARSETHERMAL_CODE[c])
            );
        end
    endgenerate
    genvar f;
    generate
        for (f = 0; f < 255; f = f + 1) begin : gen_fine_buffer
            sky130_fd_sc_hd__buf_8 fast_driver (
                .X(fine_fast_buffered[f]), .A(DCO_THERM[f])
            );
            sky130_fd_sc_hd__buf_8 slow_driver (
                .X(fine_slow_buffered[f]), .A(DCO_THERM[f])
            );
        end
    endgenerate

    // Uniform gate area on external controls and the two core-local branches.
    // Guard outputs are intentionally unused; physical and electrical
    // qualification is required before this experimental wrapper is promoted.
    wire [46:0] coarse_input_guard_sink;
    wire [46:0] coarse_fast_guard_sink;
    wire [46:0] coarse_slow_guard_sink;
    wire [254:0] fine_input_guard_sink;
    wire [254:0] fine_fast_guard_sink;
    wire [254:0] fine_slow_guard_sink;
    genvar gc;
    generate
        for (gc = 0; gc < 47; gc = gc + 1) begin : gen_coarse_guard
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__buf_8 input_guard (
                .X(coarse_input_guard_sink[gc]), .A(COARSETHERMAL_CODE[gc])
            );
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__buf_8 fast_guard (
                .X(coarse_fast_guard_sink[gc]), .A(coarse_fast_buffered[gc])
            );
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__buf_8 slow_guard (
                .X(coarse_slow_guard_sink[gc]), .A(coarse_slow_buffered[gc])
            );
        end
    endgenerate
    genvar gf;
    generate
        for (gf = 0; gf < 255; gf = gf + 1) begin : gen_fine_guard
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__buf_8 input_guard (
                .X(fine_input_guard_sink[gf]), .A(DCO_THERM[gf])
            );
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__buf_8 fast_guard (
                .X(fine_fast_guard_sink[gf]), .A(fine_fast_buffered[gf])
            );
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__buf_8 slow_guard (
                .X(fine_slow_guard_sink[gf]), .A(fine_slow_buffered[gf])
            );
        end
    endgenerate

    wire lower_band_select;
    wire first_lower_select;
    wire second_lower_select;
    wire slow_second_coarse;
    wire slow_first_coarse;
    wire fast_out;
    wire slow_out;
    wire slow_buf_out;

    // Logical bands one and two expose the slow core's first two bands.
    sky130_fd_sc_hd__and2b_1 select_first_lower_band (
        .X(first_lower_select),
        .A_N(COARSETHERMAL_CODE[1]),
        .B(COARSETHERMAL_CODE[0])
    );
    sky130_fd_sc_hd__and2b_1 select_second_lower_band (
        .X(second_lower_select),
        .A_N(COARSETHERMAL_CODE[2]),
        .B(COARSETHERMAL_CODE[1])
    );
    sky130_fd_sc_hd__or2_1 combine_lower_bands (
        .X(lower_band_select),
        .A(first_lower_select), .B(second_lower_select)
    );
    sky130_fd_sc_hd__and2_4 remap_slow_first (
        .X(slow_first_coarse),
        .A(COARSETHERMAL_CODE[0]),
        .B(COARSETHERMAL_CODE[1])
    );

    sky130_fd_sc_hd__and2_4 remap_slow_second (
        .X(slow_second_coarse),
        .A(COARSETHERMAL_CODE[1]),
        .B(COARSETHERMAL_CODE[2])
    );

    IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8 fast_core (
`ifdef USE_POWER_PINS
        .VPWR(VPWR), .VGND(VGND), .VPB(VPB), .VNB(VNB),
`endif
        .RESET_N(RESET_N),
        .COARSETHERMAL_CODE({1'b0, coarse_fast_buffered[46:1]}),
        .DCO_THERM(fine_fast_buffered),
        .PLLOUT(fast_out)
    );

    IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8 slow_core (
`ifdef USE_POWER_PINS
        .VPWR(VPWR), .VGND(VGND), .VPB(VPB), .VNB(VNB),
`endif
        .RESET_N(RESET_N),
        .COARSETHERMAL_CODE({coarse_slow_buffered[46:2], slow_second_coarse, slow_first_coarse}),
        .DCO_THERM(fine_slow_buffered),
        .PLLOUT(slow_out)
    );

    sky130_fd_sc_hd__buf_8 slow_output_buffer (.X(slow_buf_out), .A(slow_out));

    sky130_fd_sc_hd__mux2_1 output_select (
        .X(PLLOUT),
        .A0(fast_out),
        .A1(slow_buf_out),
        .S(lower_band_select)
    );
endmodule

`default_nettype wire
