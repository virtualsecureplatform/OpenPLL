// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

// Experimental three-core assembly with separate nominal 300 MHz and
// fast-corner 500 MHz bands. All cores require extracted PVT qualification.
module IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_TRIMACRO_OSC8_LOAD24_SLOW24_GUARD (
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
    wire [46:0] coarse_input_buffered;
    wire [46:0] coarse_fast_buffered;
    wire [46:0] coarse_slow_buffered;
    wire [46:0] coarse_loaded_buffered;
    wire [46:0] coarse_fast_remapped;
    wire [46:0] coarse_slow_remapped;
    wire [46:0] coarse_loaded_remapped;
    wire [254:0] fine_input_buffered;
    wire [254:0] fine_fast_buffered;
    wire [254:0] fine_slow_buffered;
    wire [254:0] fine_loaded_buffered;
    genvar c;
    generate
        for (c = 0; c < 47; c = c + 1) begin : gen_coarse_buffer
            sky130_fd_sc_hd__buf_8 input_driver (
                .X(coarse_input_buffered[c]), .A(COARSETHERMAL_CODE[c])
            );
            sky130_fd_sc_hd__buf_8 fast_driver (
                .X(coarse_fast_buffered[c]), .A(coarse_input_buffered[c])
            );
            sky130_fd_sc_hd__buf_8 slow_driver (
                .X(coarse_slow_buffered[c]), .A(coarse_input_buffered[c])
            );
            sky130_fd_sc_hd__buf_8 loaded_driver (
                .X(coarse_loaded_buffered[c]), .A(coarse_input_buffered[c])
            );
        end
    endgenerate
    genvar f;
    generate
        for (f = 0; f < 255; f = f + 1) begin : gen_fine_buffer
            sky130_fd_sc_hd__buf_8 input_driver (
                .X(fine_input_buffered[f]), .A(DCO_THERM[f])
            );
            sky130_fd_sc_hd__buf_8 fast_driver (
                .X(fine_fast_buffered[f]), .A(fine_input_buffered[f])
            );
            sky130_fd_sc_hd__buf_8 slow_driver (
                .X(fine_slow_buffered[f]), .A(fine_input_buffered[f])
            );
            sky130_fd_sc_hd__buf_8 loaded_driver (
                .X(fine_loaded_buffered[f]), .A(fine_input_buffered[f])
            );
            if (f == 111 || f == 254) begin : gen_shared_route_guard
                wire [1:0] sink;
                (* keep = "true", dont_touch = "true" *)
                sky130_fd_sc_hd__buf_8 extra0 (
                    .X(sink[0]), .A(fine_input_buffered[f])
                );
                (* keep = "true", dont_touch = "true" *)
                sky130_fd_sc_hd__buf_8 extra1 (
                    .X(sink[1]), .A(fine_input_buffered[f])
                );
            end
        end
    endgenerate

    // Buffer external controls before they fan out to the three macro branches.
    // Retained guards provide gate area on the remaining exposed input routes.
    // Guard outputs are intentionally unused; physical and electrical
    // qualification is required before this experimental wrapper is promoted.
    wire [46:0] coarse_input_guard_sink;
    wire [46:0] coarse_fast_guard_sink;
    wire [46:0] coarse_slow_guard_sink;
    wire [46:0] coarse_loaded_guard_sink;
    wire [254:0] fine_input_guard_sink;
    wire [254:0] fine_fast_guard_sink;
    wire [254:0] fine_slow_guard_sink;
    wire [254:0] fine_loaded_guard_sink;
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
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__buf_8 loaded_guard (
                .X(coarse_loaded_guard_sink[gc]), .A(coarse_loaded_buffered[gc])
            );
        end
    endgenerate
    // The coarse-24 input route needs one more retained gate for antenna area.
    wire coarse24_extra_guard_sink;
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 coarse24_extra_guard (
        .X(coarse24_extra_guard_sink), .A(COARSETHERMAL_CODE[24])
    );
    wire [1:0] slow0_extra_guard_sink;
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 slow0_extra_guard0 (
        .X(slow0_extra_guard_sink[0]), .A(coarse_slow_buffered[0])
    );
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__buf_8 slow0_extra_guard1 (
        .X(slow0_extra_guard_sink[1]), .A(coarse_slow_buffered[0])
    );
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
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__buf_8 loaded_guard (
                .X(fine_loaded_guard_sink[gf]), .A(fine_loaded_buffered[gf])
            );
        end
    endgenerate

    wire slow_select;
    wire loaded_select;
    wire first_slow_select;
    wire second_slow_select;
    wire sixth_slow_select;
    wire first_two_slow_select;
    wire fast_out;
    wire slow_out;
    wire loaded_out;
    wire slow_buf_out;
    wire loaded_buf_out;
    wire fast_or_slow_out;

    // Logical 1/2 expose slow physical 0/1; logical 6 exposes slow 4.
    sky130_fd_sc_hd__and2b_1 select_first_slow (
        .X(first_slow_select), .A_N(coarse_slow_buffered[1]),
        .B(coarse_slow_buffered[0])
    );
    sky130_fd_sc_hd__and2b_1 select_second_slow (
        .X(second_slow_select), .A_N(coarse_slow_buffered[2]),
        .B(coarse_slow_buffered[1])
    );
    sky130_fd_sc_hd__and2b_1 select_sixth_slow (
        .X(sixth_slow_select), .A_N(coarse_slow_buffered[6]),
        .B(coarse_slow_buffered[5])
    );
    sky130_fd_sc_hd__or2_1 combine_first_two_slow (
        .X(first_two_slow_select), .A(first_slow_select),
        .B(second_slow_select)
    );
    sky130_fd_sc_hd__or2_1 combine_slow (
        .X(slow_select), .A(first_two_slow_select),
        .B(sixth_slow_select)
    );
    // Logical 5 selects loaded fast physical 3 for nominal 300 MHz.
    sky130_fd_sc_hd__and2b_1 select_loaded (
        .X(loaded_select), .A_N(coarse_loaded_buffered[5]),
        .B(coarse_loaded_buffered[4])
    );

    // The original fast macro gets logical 4 as physical 3 and skips logical
    // 5, which is reserved for the loaded fast macro. From logical 7 on it
    // resumes as physical 5, preserving descending coarse-band order.
    genvar r;
    generate
        for (r = 0; r < 47; r = r + 1) begin : gen_coarse_remap
            if (r < 4) begin : gen_fast_first
                sky130_fd_sc_hd__buf_8 remap (
                    .X(coarse_fast_remapped[r]),
                    .A(coarse_fast_buffered[r + 1])
                );
            end else if (r < 45) begin : gen_fast_rest
                sky130_fd_sc_hd__buf_8 remap (
                    .X(coarse_fast_remapped[r]),
                    .A(coarse_fast_buffered[r + 2])
                );
            end else begin : gen_fast_tail
                sky130_fd_sc_hd__conb_1 tie_cell (
                    .LO(coarse_fast_remapped[r]), .HI()
                );
            end
            if (r < 4) begin : gen_slow_first
                sky130_fd_sc_hd__buf_8 remap (
                    .X(coarse_slow_remapped[r]),
                    .A(coarse_slow_buffered[r + 1])
                );
            end else if (r < 45) begin : gen_slow_rest
                sky130_fd_sc_hd__buf_8 remap (
                    .X(coarse_slow_remapped[r]),
                    .A(coarse_slow_buffered[r + 2])
                );
            end else begin : gen_slow_tail
                sky130_fd_sc_hd__conb_1 tie_cell (
                    .LO(coarse_slow_remapped[r]), .HI()
                );
            end
            if (r < 45) begin : gen_loaded
                sky130_fd_sc_hd__buf_8 remap (
                    .X(coarse_loaded_remapped[r]),
                    .A(coarse_loaded_buffered[r + 2])
                );
            end else begin : gen_loaded_tail
                sky130_fd_sc_hd__conb_1 tie_cell (
                    .LO(coarse_loaded_remapped[r]), .HI()
                );
            end
        end
    endgenerate

    IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8 fast_core (
`ifdef USE_POWER_PINS
        .VPWR(VPWR), .VGND(VGND), .VPB(VPB), .VNB(VNB),
`endif
        .RESET_N(RESET_N),
        .COARSETHERMAL_CODE(coarse_fast_remapped),
        .DCO_THERM(fine_fast_buffered),
        .PLLOUT(fast_out)
    );

    IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_LOAD24 slow_core (
`ifdef USE_POWER_PINS
        .VPWR(VPWR), .VGND(VGND), .VPB(VPB), .VNB(VNB),
`endif
        .RESET_N(RESET_N),
        .COARSETHERMAL_CODE(coarse_slow_remapped),
        .DCO_THERM(fine_slow_buffered),
        .PLLOUT(slow_out)
    );

    IntegerPLL_DCO_EINVP_COARSE_V5_TURN10_BOOST8_OSC8_LOAD24 loaded_core (
`ifdef USE_POWER_PINS
        .VPWR(VPWR), .VGND(VGND), .VPB(VPB), .VNB(VNB),
`endif
        .RESET_N(RESET_N),
        .COARSETHERMAL_CODE(coarse_loaded_remapped),
        .DCO_THERM(fine_loaded_buffered),
        .PLLOUT(loaded_out)
    );

    sky130_fd_sc_hd__buf_8 slow_output_buffer (.X(slow_buf_out), .A(slow_out));
    sky130_fd_sc_hd__buf_8 loaded_output_buffer (.X(loaded_buf_out), .A(loaded_out));
    sky130_fd_sc_hd__mux2_1 select_slow (
        .X(fast_or_slow_out), .A0(fast_out),
        .A1(slow_buf_out), .S(slow_select)
    );
    sky130_fd_sc_hd__mux2_1 select_loaded_output (
        .X(PLLOUT), .A0(fast_or_slow_out),
        .A1(loaded_buf_out), .S(loaded_select)
    );
endmodule

`default_nettype wire
