// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

// Experimental assembly of two routed DCO hard macros. Coarse code one selects the lower 400 MHz band;
// all other coarse codes use the fast core. Both cores must be qualified.
module IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_DBUF_ANT5 (
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

    // Add gate area only to the four nets left above the met3/met4 antenna limit.
    // These loads are isolated until the routed implementation passes signoff.
    wire [4:0] antenna_sink;
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 antenna_input_198 (
        .X(antenna_sink[0]), .A(DCO_THERM[198])
    );
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 antenna_input_242 (
        .X(antenna_sink[1]), .A(DCO_THERM[242])
    );
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 antenna_slow_201 (
        .X(antenna_sink[2]), .A(fine_slow_buffered[201])
    );
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 antenna_slow_237 (
        .X(antenna_sink[3]), .A(fine_slow_buffered[237])
    );

    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 antenna_slow_243 (
        .X(antenna_sink[4]), .A(fine_slow_buffered[243])
    );

    wire lower_band_select;
    wire slow_first_coarse;
    wire fast_out;
    wire slow_out;
    wire slow_buf_out;

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
        .COARSETHERMAL_CODE(coarse_fast_buffered),
        .DCO_THERM(fine_fast_buffered),
        .PLLOUT(fast_out)
    );

    IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8 slow_core (
`ifdef USE_POWER_PINS
        .VPWR(VPWR), .VGND(VGND), .VPB(VPB), .VNB(VNB),
`endif
        .RESET_N(RESET_N),
        .COARSETHERMAL_CODE({coarse_slow_buffered[46:1], slow_first_coarse}),
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
