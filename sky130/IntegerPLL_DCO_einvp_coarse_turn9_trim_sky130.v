// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

// Experimental full-resolution DCO with a strengthened coarse-1 path and
// balanced supplemental fine loads to extend the coarse-0 lower endpoint.
// Requires extracted PVT qualification before promotion.
module IntegerPLL_DCO_EINVP_COARSE_TURN9_TRIM (
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

`ifndef USE_POWER_PINS
    supply1 VPWR;
    supply1 VPB;
    supply0 VGND;
    supply0 VNB;
`endif

`ifdef USE_CELL_POWER_PINS
`define INTEGERPLL_SKY130_CELL_PG .VPWR(VPWR), .VGND(VGND), .VPB(VPB), .VNB(VNB),
`else
`define INTEGERPLL_SKY130_CELL_PG
`endif

    wire tie_hi;
    wire tie_lo;
    wire osc_node;
    wire [47:0] mirror_fwd;
    wire [47:0] mirror_ret;
    wire [47:0] mirror_turn_n;
    wire [46:0] mirror_pass_n;
    // Each thermometer bit controls one physical load to preserve all 256 fine codes.
    wire [254:0] load_dummy;
    wire [254:0] load_dummy_extra;
    wire [254:0] load_dummy_turn_extra;
    wire trim_dummy;

    sky130_fd_sc_hd__conb_1 tie_cell (
        `INTEGERPLL_SKY130_CELL_PG
        .HI(tie_hi),
        .LO(tie_lo)
    );

    sky130_fd_sc_hd__nand2_8 osc_gate (
        `INTEGERPLL_SKY130_CELL_PG
        .Y(osc_node),
        .A(mirror_ret[0]),
        .B(RESET_N)
    );

    // Parallel copies strengthen the shortest path without enlarging all 48 bands.
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__nand2_8 osc_gate_parallel (
        `INTEGERPLL_SKY130_CELL_PG
        .Y(osc_node), .A(mirror_ret[0]), .B(RESET_N)
    );
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__nand2b_4 mirror_turn_parallel (
        `INTEGERPLL_SKY130_CELL_PG
        .Y(mirror_turn_n[0]), .A_N(COARSETHERMAL_CODE[0]), .B(osc_node)
    );
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__nand2_8 mirror_merge_parallel (
        `INTEGERPLL_SKY130_CELL_PG
        .Y(mirror_ret[0]), .A(mirror_turn_n[0]), .B(mirror_pass_n[0])
    );

    // Parallel copies strengthen the shortest path without enlarging all 48 bands.
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__nand2_8 osc_gate_parallel2 (
        `INTEGERPLL_SKY130_CELL_PG
        .Y(osc_node), .A(mirror_ret[0]), .B(RESET_N)
    );
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__nand2b_4 mirror_turn_parallel2 (
        `INTEGERPLL_SKY130_CELL_PG
        .Y(mirror_turn_n[0]), .A_N(COARSETHERMAL_CODE[0]), .B(osc_node)
    );
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__nand2_8 mirror_merge_parallel2 (
        `INTEGERPLL_SKY130_CELL_PG
        .Y(mirror_ret[0]), .A(mirror_turn_n[0]), .B(mirror_pass_n[0])
    );

    // Parallel copies strengthen the shortest path without enlarging all 48 bands.
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__nand2_8 osc_gate_parallel3 (
        `INTEGERPLL_SKY130_CELL_PG
        .Y(osc_node), .A(mirror_ret[0]), .B(RESET_N)
    );
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__nand2b_4 mirror_turn_parallel3 (
        `INTEGERPLL_SKY130_CELL_PG
        .Y(mirror_turn_n[0]), .A_N(COARSETHERMAL_CODE[0]), .B(osc_node)
    );
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__nand2_8 mirror_merge_parallel3 (
        `INTEGERPLL_SKY130_CELL_PG
        .Y(mirror_ret[0]), .A(mirror_turn_n[0]), .B(mirror_pass_n[0])
    );

    // Coarse 1 passes through these four additional stages. Parallel copies
    // strengthen that path while leaving the existing 255 fine controls intact.
    genvar p;
    generate
        for (p = 0; p < 3; p = p + 1) begin : gen_coarse1_parallel
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__nand2_8 mirror_forward (
                `INTEGERPLL_SKY130_CELL_PG
                .Y(mirror_fwd[1]), .A(osc_node), .B(COARSETHERMAL_CODE[0])
            );
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__nand2b_4 mirror_turn (
                `INTEGERPLL_SKY130_CELL_PG
                .Y(mirror_turn_n[1]), .A_N(COARSETHERMAL_CODE[1]),
                .B(mirror_fwd[1])
            );
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__nand2_8 mirror_merge (
                `INTEGERPLL_SKY130_CELL_PG
                .Y(mirror_ret[1]), .A(mirror_turn_n[1]), .B(mirror_pass_n[1])
            );
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__nand2b_4 mirror_return (
                `INTEGERPLL_SKY130_CELL_PG
                .Y(mirror_pass_n[0]), .A_N(mirror_ret[1]),
                .B(COARSETHERMAL_CODE[0])
            );
        end
    endgenerate

    genvar i;
    generate
        for (i = 0; i < 47; i = i + 1) begin : gen_mirror_forward
            if (i == 0) begin : gen_from_mirror_input
                sky130_fd_sc_hd__nand2_8 mirror_forward (
                    `INTEGERPLL_SKY130_CELL_PG
                    .Y(mirror_fwd[i+1]),
                    .A(osc_node),
                    .B(COARSETHERMAL_CODE[i])
                );
            end else begin : gen_chain_forward
                sky130_fd_sc_hd__nand2_8 mirror_forward (
                    `INTEGERPLL_SKY130_CELL_PG
                    .Y(mirror_fwd[i+1]),
                    .A(mirror_fwd[i]),
                    .B(COARSETHERMAL_CODE[i])
                );
            end
        end

        for (i = 0; i < 48; i = i + 1) begin : gen_mirror_delay
            if (i == 0) begin : gen_turn_from_mirror_input
                sky130_fd_sc_hd__nand2b_4 mirror_turn (
                    `INTEGERPLL_SKY130_CELL_PG
                    .Y(mirror_turn_n[i]),
                    .A_N(COARSETHERMAL_CODE[i]),
                    .B(osc_node)
                );
            end else if (i < 47) begin : gen_turn_controlled
                sky130_fd_sc_hd__nand2b_4 mirror_turn (
                    `INTEGERPLL_SKY130_CELL_PG
                    .Y(mirror_turn_n[i]),
                    .A_N(COARSETHERMAL_CODE[i]),
                    .B(mirror_fwd[i])
                );
            end else begin : gen_turn_terminal
                sky130_fd_sc_hd__nand2b_4 mirror_turn (
                    `INTEGERPLL_SKY130_CELL_PG
                    .Y(mirror_turn_n[i]),
                    .A_N(tie_lo),
                    .B(mirror_fwd[i])
                );
            end

            if (i < 47) begin : gen_return_pass
                sky130_fd_sc_hd__nand2b_4 mirror_return (
                    `INTEGERPLL_SKY130_CELL_PG
                    .Y(mirror_pass_n[i]),
                    .A_N(mirror_ret[i+1]),
                    .B(COARSETHERMAL_CODE[i])
                );
            end

            if (i < 47) begin : gen_merge_pass
                sky130_fd_sc_hd__nand2_8 mirror_merge (
                    `INTEGERPLL_SKY130_CELL_PG
                    .Y(mirror_ret[i]),
                    .A(mirror_turn_n[i]),
                    .B(mirror_pass_n[i])
                );
            end else begin : gen_return_terminal
                sky130_fd_sc_hd__nand2_8 mirror_merge (
                    `INTEGERPLL_SKY130_CELL_PG
                    .Y(mirror_ret[i]),
                    .A(mirror_turn_n[i]),
                    .B(tie_hi)
                );
            end
        end
    endgenerate

    sky130_fd_sc_hd__buf_1 out_buf (
        `INTEGERPLL_SKY130_CELL_PG
        .X(PLLOUT),
        .A(osc_node)
    );

    // A fixed trim load shifts the coarse-0 band without changing fine-code spacing.
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__einvp_1 turn_trim_load (
        `INTEGERPLL_SKY130_CELL_PG
        .Z(trim_dummy),
        .A(mirror_turn_n[0]),
        .TE(tie_hi)
    );

    genvar f;
    generate
        for (f = 0; f < 255; f = f + 1) begin : gen_dco_load
            if ((f % 2) == 0) begin : gen_mirror_input_load
                sky130_fd_sc_hd__einvp_1 tune_load (
                    `INTEGERPLL_SKY130_CELL_PG
                    .Z(load_dummy[f]),
                    .A(osc_node),
                    .TE(DCO_THERM[f])
                );
            end else begin : gen_feedback_load
                sky130_fd_sc_hd__einvp_1 tune_load (
                    `INTEGERPLL_SKY130_CELL_PG
                    .Z(load_dummy[f]),
                    .A(mirror_ret[0]),
                    .TE(DCO_THERM[f])
                );
            end
            // Duplicate every fourth oscillator-side and return-side load.
            // Selected codes switch two loads; every other code still switches
            // one, so no adjacent fine codes alias.
            if ((f % 4) < 2) begin : gen_supplemental_load
                sky130_fd_sc_hd__einvp_1 tune_load_extra (
                    `INTEGERPLL_SKY130_CELL_PG
                    .Z(load_dummy_extra[f]),
                    .A((f % 2) == 0 ? osc_node : mirror_ret[0]),
                    .TE(DCO_THERM[f])
                );
            end
            // Add nine spaced fine-controlled loads to the coarse-0 turn node.
            if ((f % 29) == 10) begin : gen_turn_supplemental_load
                sky130_fd_sc_hd__einvp_1 tune_load_turn_extra (
                    `INTEGERPLL_SKY130_CELL_PG
                    .Z(load_dummy_turn_extra[f]),
                    .A(mirror_turn_n[0]),
                    .TE(DCO_THERM[f])
                );
            end
        end

    endgenerate

endmodule

`undef INTEGERPLL_SKY130_CELL_PG
`default_nettype wire
