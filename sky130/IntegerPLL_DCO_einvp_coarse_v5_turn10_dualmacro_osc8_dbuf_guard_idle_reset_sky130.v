// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

// Experimental assembly with oscillator-drive fast macro and routed slow macro. Coarse code one selects the lower 400 MHz band;
// all other coarse codes use the fast core. Both cores must be qualified.
module IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_DUALMACRO_OSC8_DBUF_GUARD_IDLE_RESET (
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
    wire fast_reset_pre;
    wire slow_reset_pre;
    wire fast_reset_n;
    wire slow_reset_n;
    wire slow_first_coarse;
    wire fast_out;
    wire slow_out;
    wire slow_buf_out;

    sky130_fd_sc_hd__and2b_1 select_lower_band (
        .X(lower_band_select),
        .A_N(COARSETHERMAL_CODE[1]),
        .B(COARSETHERMAL_CODE[0])
    );
    // Keep the unselected oscillator at a static reset level to reduce
    // switching power and simplify the two-core operating point.
    sky130_fd_sc_hd__and2b_1 fast_reset_select (
        .X(fast_reset_pre), .A_N(lower_band_select), .B(RESET_N)
    );
    sky130_fd_sc_hd__and2_4 slow_reset_select (
        .X(slow_reset_pre), .A(lower_band_select), .B(RESET_N)
    );
    sky130_fd_sc_hd__buf_8 fast_reset_driver (
        .X(fast_reset_n), .A(fast_reset_pre)
    );
    sky130_fd_sc_hd__buf_8 slow_reset_driver (
        .X(slow_reset_n), .A(slow_reset_pre)
    );

    sky130_fd_sc_hd__and2_4 remap_slow_first (
        .X(slow_first_coarse),
        .A(COARSETHERMAL_CODE[0]),
        .B(COARSETHERMAL_CODE[1])
    );

    IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8 fast_core (
`ifdef USE_POWER_PINS
        .VPWR(VPWR), .VGND(VGND), .VPB(VPB), .VNB(VNB),
`endif
        .RESET_N(fast_reset_n),
        .COARSETHERMAL_CODE(coarse_fast_buffered),
        .DCO_THERM(fine_fast_buffered),
        .PLLOUT(fast_out)
    );

    IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8 slow_core (
`ifdef USE_POWER_PINS
        .VPWR(VPWR), .VGND(VGND), .VPB(VPB), .VNB(VNB),
`endif
        .RESET_N(slow_reset_n),
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
