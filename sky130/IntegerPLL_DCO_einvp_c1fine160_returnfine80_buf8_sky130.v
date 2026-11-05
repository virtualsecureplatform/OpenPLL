// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

// Experimental full-resolution DCO with a strengthened coarse-0 turn stage.
// Requires extracted PVT qualification before promotion.
module IntegerPLL_DCO_EINVP_C1FINE160_RETURNFINE80_BUF8 (
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

    // Two further matched turn drivers target the RC-limited fastest band.
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__nand2b_4 mirror_turn_parallel4 (
        `INTEGERPLL_SKY130_CELL_PG
        .Y(mirror_turn_n[0]), .A_N(COARSETHERMAL_CODE[0]), .B(osc_node)
    );
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__nand2b_4 mirror_turn_parallel5 (
        `INTEGERPLL_SKY130_CELL_PG
        .Y(mirror_turn_n[0]), .A_N(COARSETHERMAL_CODE[0]), .B(osc_node)
    );

    // Four further matched coarse-0 turn drivers test the slow-corner limit.
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__nand2b_4 mirror_turn_parallel6 (
        `INTEGERPLL_SKY130_CELL_PG
        .Y(mirror_turn_n[0]), .A_N(COARSETHERMAL_CODE[0]), .B(osc_node)
    );
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__nand2b_4 mirror_turn_parallel7 (
        `INTEGERPLL_SKY130_CELL_PG
        .Y(mirror_turn_n[0]), .A_N(COARSETHERMAL_CODE[0]), .B(osc_node)
    );
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__nand2b_4 mirror_turn_parallel8 (
        `INTEGERPLL_SKY130_CELL_PG
        .Y(mirror_turn_n[0]), .A_N(COARSETHERMAL_CODE[0]), .B(osc_node)
    );
    (* keep = "true", dont_touch = "true" *)
    sky130_fd_sc_hd__nand2b_4 mirror_turn_parallel9 (
        `INTEGERPLL_SKY130_CELL_PG
        .Y(mirror_turn_n[0]), .A_N(COARSETHERMAL_CODE[0]), .B(osc_node)
    );

    // Four additional matched oscillator gates offset switched-driver loading.
    genvar osc_boost;
    generate
        for (osc_boost = 0; osc_boost < 4; osc_boost = osc_boost + 1) begin : gen_osc_boost
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__nand2_8 driver (
                `INTEGERPLL_SKY130_CELL_PG
                .Y(osc_node), .A(mirror_ret[0]), .B(RESET_N)
            );
        end
    endgenerate

    // Enable matched extra turn drive progressively as fine code rises.
    // OR disables every extra driver outside coarse band zero.
    genvar boost;
    generate
        for (boost = 0; boost < 8; boost = boost + 1) begin : gen_turn_boost
            wire disable_b;
            sky130_fd_sc_hd__or2_1 control (
                `INTEGERPLL_SKY130_CELL_PG
                .X(disable_b), .A(COARSETHERMAL_CODE[0]),
                .B(DCO_THERM[8 + 32 * boost])
            );
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__einvn_4 driver (
                `INTEGERPLL_SKY130_CELL_PG
                .Z(mirror_turn_n[0]), .A(osc_node), .TE_B(disable_b)
            );
        end
    endgenerate

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

    sky130_fd_sc_hd__buf_8 out_buf (
        `INTEGERPLL_SKY130_CELL_PG
        .X(PLLOUT),
        .A(osc_node)
    );

    // Additional fixed loads test hot-SS coverage of the 450 MHz target.
    // All 255 fine controls remain independent for the release code range.
    wire [35:0] fixed_load_dummy;
    genvar fixed_index;
    generate
        for (fixed_index = 0; fixed_index < 36; fixed_index = fixed_index + 1) begin : gen_fixed_load
            if ((fixed_index % 2) == 0) begin : gen_input_load
                (* keep = "true", dont_touch = "true" *)
                sky130_fd_sc_hd__einvp_1 fixed_load (
                    `INTEGERPLL_SKY130_CELL_PG
                    .Z(fixed_load_dummy[fixed_index]),
                    .A(osc_node), .TE(tie_hi)
                );
            end else begin : gen_feedback_load
                (* keep = "true", dont_touch = "true" *)
                sky130_fd_sc_hd__einvp_1 fixed_load (
                    `INTEGERPLL_SKY130_CELL_PG
                    .Z(fixed_load_dummy[fixed_index]),
                    .A(mirror_ret[0]), .TE(tie_hi)
                );
            end
        end
    endgenerate

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
        end

    endgenerate

    // Fine-controlled load on the active coarse-1 turn. TE=1 loads the node.
    // Increasing fine code removes loads; all original 255 controls remain.
    wire [159:0] coarse1_fine_dummy;
    genvar c1fine;
    generate
        for (c1fine = 0; c1fine < 160; c1fine = c1fine + 1) begin : gen_coarse1_fine_load
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__einvp_1 load (
                `INTEGERPLL_SKY130_CELL_PG
                .A(mirror_turn_n[1]),
                .TE(DCO_THERM[(255*c1fine)/160]),
                .Z(coarse1_fine_dummy[c1fine])
            );
        end
    endgenerate


    // Experimental fine-range extension on the weakest common return stage.
    // New load outputs are independent floating dummies; no new ring driver.
    wire [79:0] return_fine_dummy;
    function integer return_fine_index;
        input integer unit_index;
        begin
            case (unit_index)
                0: return_fine_index = 2;
                1: return_fine_index = 5;
                2: return_fine_index = 8;
                3: return_fine_index = 10;
                4: return_fine_index = 13;
                5: return_fine_index = 16;
                6: return_fine_index = 21;
                7: return_fine_index = 24;
                8: return_fine_index = 26;
                9: return_fine_index = 29;
                10: return_fine_index = 32;
                11: return_fine_index = 37;
                12: return_fine_index = 40;
                13: return_fine_index = 42;
                14: return_fine_index = 45;
                15: return_fine_index = 48;
                16: return_fine_index = 53;
                17: return_fine_index = 56;
                18: return_fine_index = 59;
                19: return_fine_index = 61;
                20: return_fine_index = 64;
                21: return_fine_index = 67;
                22: return_fine_index = 72;
                23: return_fine_index = 75;
                24: return_fine_index = 77;
                25: return_fine_index = 80;
                26: return_fine_index = 83;
                27: return_fine_index = 88;
                28: return_fine_index = 91;
                29: return_fine_index = 93;
                30: return_fine_index = 96;
                31: return_fine_index = 99;
                32: return_fine_index = 104;
                33: return_fine_index = 107;
                34: return_fine_index = 110;
                35: return_fine_index = 112;
                36: return_fine_index = 115;
                37: return_fine_index = 118;
                38: return_fine_index = 123;
                39: return_fine_index = 126;
                40: return_fine_index = 128;
                41: return_fine_index = 131;
                42: return_fine_index = 134;
                43: return_fine_index = 139;
                44: return_fine_index = 142;
                45: return_fine_index = 144;
                46: return_fine_index = 147;
                47: return_fine_index = 150;
                48: return_fine_index = 155;
                49: return_fine_index = 158;
                50: return_fine_index = 161;
                51: return_fine_index = 163;
                52: return_fine_index = 166;
                53: return_fine_index = 169;
                54: return_fine_index = 174;
                55: return_fine_index = 177;
                56: return_fine_index = 179;
                57: return_fine_index = 182;
                58: return_fine_index = 185;
                59: return_fine_index = 190;
                60: return_fine_index = 193;
                61: return_fine_index = 195;
                62: return_fine_index = 198;
                63: return_fine_index = 201;
                64: return_fine_index = 206;
                65: return_fine_index = 209;
                66: return_fine_index = 212;
                67: return_fine_index = 214;
                68: return_fine_index = 217;
                69: return_fine_index = 220;
                70: return_fine_index = 225;
                71: return_fine_index = 228;
                72: return_fine_index = 230;
                73: return_fine_index = 233;
                74: return_fine_index = 236;
                75: return_fine_index = 241;
                76: return_fine_index = 244;
                77: return_fine_index = 246;
                78: return_fine_index = 249;
                79: return_fine_index = 252;
                default: return_fine_index = 0;
            endcase
        end
    endfunction

    genvar return_fine;
    generate
        for (return_fine = 0; return_fine < 80; return_fine = return_fine + 1) begin : gen_return_fine_load
            (* keep = "true", dont_touch = "true" *)
            sky130_fd_sc_hd__einvp_1 load (
                `INTEGERPLL_SKY130_CELL_PG
                .A(mirror_pass_n[0]),
                .TE(DCO_THERM[return_fine_index(return_fine)]),
                .Z(return_fine_dummy[return_fine])
            );
        end
    endgenerate

endmodule

`undef INTEGERPLL_SKY130_CELL_PG
`default_nettype wire
