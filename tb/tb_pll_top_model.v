// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module tb_pll_top_model;

    reg ref_clk;
    reg reset_n;
    reg dlf_en;
    reg dlf_clear;
    reg dlf_override;
    reg dlf_in_pol;
    reg [9:0] dlf_ext_data;
    reg [7:0] dlf_ki;
    reg [4:0] dlf_kp;
    reg [3:0] coarse_code;
    reg [7:0] mmd_ratio;

    wire pllo;
    wire pllo_div;
    wire clkdiv_retimed;
    wire [1:0] bbpd_code;
    wire [7:0] dco_code;
    wire [9:0] dlf_code;

    integer pllo_edges;
    integer clkdiv_edges;
    integer dco_load_count;

    function integer count255;
        input [254:0] value;
        integer i;
        begin
            count255 = 0;
            for (i = 0; i < 255; i = i + 1)
                count255 = count255 + value[i];
        end
    endfunction

    IntegerPLL_Top dut (
        .REF(ref_clk),
        .RESET_N(reset_n),
        .DLF_En(dlf_en),
        .DLF_Clear(dlf_clear),
        .DLF_Ext_Override(dlf_override),
        .DLF_IN_POL(dlf_in_pol),
        .DLF_Ext_Data(dlf_ext_data),
        .DLF_KI(dlf_ki),
        .DLF_KP(dlf_kp),
        .COARSEBINARY_CODE(coarse_code),
        .MMDCLKDIV_RATIO(mmd_ratio),
        .PLLOUT(pllo),
        .PLLOUT_DIV(pllo_div),
        .CLKDIV_RETIMED(clkdiv_retimed),
        .BBPD_CODE(bbpd_code),
        .DCO_CODE(dco_code),
        .DLF_CODE(dlf_code)
    );

    initial begin
        ref_clk = 1'b0;
        forever #12.5 ref_clk = ~ref_clk;
    end

    always @(posedge pllo)
        pllo_edges = pllo_edges + 1;

    always @(posedge clkdiv_retimed)
        clkdiv_edges = clkdiv_edges + 1;

    initial begin
        reset_n = 1'b0;
        dlf_en = 1'b0;
        dlf_clear = 1'b0;
        dlf_override = 1'b0;
        dlf_in_pol = 1'b1;
        dlf_ext_data = 10'd512;
        dlf_ki = 8'd16;
        dlf_kp = 5'd0;
        coarse_code = 4'd5;
        mmd_ratio = 8'd10;
        pllo_edges = 0;
        clkdiv_edges = 0;

        #100;
        reset_n = 1'b1;
        dlf_clear = 1'b1;
        #500;
        dlf_clear = 1'b0;
        dlf_en = 1'b1;
        #2000;

        if (pllo_edges < 10) begin
            $display("FAIL: top model PLLOUT did not toggle enough");
            $finish;
        end

        if (clkdiv_edges < 2) begin
            $display("FAIL: top model feedback divider did not toggle enough");
            $finish;
        end

        if (bbpd_code === 2'b00) begin
            $display("FAIL: top model BBPD stayed idle");
            $finish;
        end

        dco_load_count = count255(dut.dco_therm);
        if (dco_code !== 8'd128 || dco_load_count !== 127) begin
            $display("FAIL: top model DCO polarity failed: dco_code=%0d loads=%0d",
                     dco_code, dco_load_count);
            $finish;
        end

        $display("PASS: PLL top model smoke test, dco_code=%0d dlf_code=%0d",
                 dco_code, dlf_code);
        $finish;
    end

endmodule

`default_nettype wire
