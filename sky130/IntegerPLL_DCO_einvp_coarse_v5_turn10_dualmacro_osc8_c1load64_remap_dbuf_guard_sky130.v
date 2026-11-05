// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

// Experimental assembly with four logical slow bands and one-position
// coarse remapping. Both routed cores require extracted PVT qualification.
module IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_OSC8_C1LOAD64_REMAP_DBUF_GUARD (
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
    // The coarse-24 input route needs one more retained gate for antenna area.
    wire [46:0] coarse_input_extra_guard_sink;
    genvar cg;
    generate
        for (cg = 0; cg < 47; cg = cg + 1) begin : gen_coarse_input_extra_guard
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__buf_8 input_guard (
                .X(coarse_input_extra_guard_sink[cg]), .A(COARSETHERMAL_CODE[cg])
            );
        end
    endgenerate
    wire coarse24_extra_guard_sink;
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 coarse24_extra_guard (
        .X(coarse24_extra_guard_sink), .A(COARSETHERMAL_CODE[24])
    );
    wire [1:0] slow4_extra_guard_sink;
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 slow4_extra_guard0 (
        .X(slow4_extra_guard_sink[0]), .A(coarse_slow_buffered[4])
    );
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 slow4_extra_guard1 (
        .X(slow4_extra_guard_sink[1]), .A(coarse_slow_buffered[4])
    );
    wire [1:0] slow3_extra_guard_sink;
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 slow3_extra_guard0 (
        .X(slow3_extra_guard_sink[0]), .A(coarse_slow_buffered[3])
    );
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 slow3_extra_guard1 (
        .X(slow3_extra_guard_sink[1]), .A(coarse_slow_buffered[3])
    );
    wire [2:0] slow5_extra_guard_sink;
    genvar slow5g;
    generate
        for (slow5g = 0; slow5g < 3; slow5g = slow5g + 1) begin : gen_slow5_extra_guard
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__buf_8 guard_cell (
                .X(slow5_extra_guard_sink[slow5g]), .A(coarse_slow_buffered[5])
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

    // Provide uniform antenna gate area for macro-bound fine routes. The
    // outputs are unused but retained for physical routing qualification.
    wire [254:0] fine_fast_extra_guard0_sink;
    wire [254:0] fine_fast_extra_guard1_sink;
    wire [254:0] fine_slow_extra_guard0_sink;
    wire [254:0] fine_slow_extra_guard1_sink;
    genvar fg;
    generate
        for (fg = 0; fg < 255; fg = fg + 1) begin : gen_fine_extra_guard
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__buf_8 fast_guard0 (
                .X(fine_fast_extra_guard0_sink[fg]), .A(fine_fast_buffered[fg])
            );
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__buf_8 fast_guard1 (
                .X(fine_fast_extra_guard1_sink[fg]), .A(fine_fast_buffered[fg])
            );
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__buf_8 slow_guard0 (
                .X(fine_slow_extra_guard0_sink[fg]), .A(fine_slow_buffered[fg])
            );
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__buf_8 slow_guard1 (
                .X(fine_slow_extra_guard1_sink[fg]), .A(fine_slow_buffered[fg])
            );
        end
    endgenerate

    wire fine154_extra_guard_sink;
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 fine154_extra_guard (
        .X(fine154_extra_guard_sink), .A(fine_fast_buffered[154])
    );
    wire fine186_extra_guard_sink;
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_1 fine186_extra_guard (
        .X(fine186_extra_guard_sink), .A(fine_fast_buffered[186])
    );
    wire fine188_extra_guard_sink;
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 fine188_extra_guard (
        .X(fine188_extra_guard_sink), .A(fine_fast_buffered[188])
    );
    wire fine117_input_extra_guard_sink;
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 fine117_input_extra_guard (
        .X(fine117_input_extra_guard_sink), .A(DCO_THERM[117])
    );
    wire [1:0] fine32_extra_guard_sink;
    wire [1:0] fine66_extra_guard_sink;
    genvar extra;
    generate
        for (extra = 0; extra < 2; extra = extra + 1) begin : gen_extra_fine_guard
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__buf_8 fine32_guard (
                .X(fine32_extra_guard_sink[extra]), .A(fine_fast_buffered[32])
            );
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__buf_8 fine66_guard (
                .X(fine66_extra_guard_sink[extra]), .A(fine_fast_buffered[66])
            );
        end
    endgenerate

    // Additional gate area on the four slow fine routes flagged by the
    // physically routed fast-(60,65)/slow-(245,95) placement.
    wire [1:0] fine187_slow_extra_guard_sink;
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 fine187_slow_extra_guard0 (
        .X(fine187_slow_extra_guard_sink[0]), .A(fine_slow_buffered[187])
    );
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 fine187_slow_extra_guard1 (
        .X(fine187_slow_extra_guard_sink[1]), .A(fine_slow_buffered[187])
    );
    wire fine253_slow_extra_guard_sink;
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 fine253_slow_extra_guard (
        .X(fine253_slow_extra_guard_sink), .A(fine_slow_buffered[253])
    );
    wire fine254_slow_extra_guard_sink;
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 fine254_slow_extra_guard (
        .X(fine254_slow_extra_guard_sink), .A(fine_slow_buffered[254])
    );
    wire fine157_slow_extra_guard_sink;
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 fine157_slow_extra_guard (
        .X(fine157_slow_extra_guard_sink), .A(fine_slow_buffered[157])
    );

    wire lower_band_select;
    wire first_lower_select;
    wire second_lower_select;
    wire fourth_lower_select;
    wire fifth_lower_select;
    wire first_two_lower_select;
    wire last_two_lower_select;
    wire slow_second_coarse;
    wire slow_first_coarse;
    wire fast_out;
    wire slow_out;
    wire slow_buf_out;

    // Logical bands 1/2/4/5 expose slow physical bands 0/1/3/4.
    // Other positive logical bands select fast physical coarse minus one.
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
    sky130_fd_sc_hd__and2b_1 select_fourth_lower_band (
        .X(fourth_lower_select),
        .A_N(COARSETHERMAL_CODE[4]),
        .B(COARSETHERMAL_CODE[3])
    );
    sky130_fd_sc_hd__and2b_1 select_fifth_lower_band (
        .X(fifth_lower_select),
        .A_N(COARSETHERMAL_CODE[5]),
        .B(COARSETHERMAL_CODE[4])
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

    IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_C1LOAD64 slow_core (
`ifdef USE_POWER_PINS
        .VPWR(VPWR), .VGND(VGND), .VPB(VPB), .VNB(VNB),
`endif
        .RESET_N(RESET_N),
        .COARSETHERMAL_CODE({1'b0, coarse_slow_buffered[46:3], slow_second_coarse, slow_first_coarse}),
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
