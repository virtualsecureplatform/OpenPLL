// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module IntegerPLL_DCO_EINVP_COARSE (
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
    wire [254:0] load_dummy;

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

    genvar f;
    generate
        for (f = 0; f < 255; f = f + 1) begin : gen_dco_load
            if ((f % 2) == 0) begin : gen_mirror_input_load
                sky130_fd_sc_hd__nand2_1 tune_load (
                    `INTEGERPLL_SKY130_CELL_PG
                    .Y(load_dummy[f]),
                    .A(osc_node),
                    .B(DCO_THERM[f])
                );
            end else begin : gen_feedback_load
                sky130_fd_sc_hd__nand2_1 tune_load (
                    `INTEGERPLL_SKY130_CELL_PG
                    .Y(load_dummy[f]),
                    .A(mirror_ret[0]),
                    .B(DCO_THERM[f])
                );
            end
        end

    endgenerate

endmodule

`undef INTEGERPLL_SKY130_CELL_PG
`default_nettype wire
