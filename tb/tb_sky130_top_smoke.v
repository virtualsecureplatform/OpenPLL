// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module IntegerPLL_BBPD (
`ifdef USE_POWER_PINS
    inout wire VPWR,
    inout wire VGND,
    inout wire VPB,
    inout wire VNB,
`endif
    input wire REF,
    input wire CLKDIVR,
    input wire RESET_N,
    output wire [1:0] BBPD
);
    assign BBPD = RESET_N ? 2'b00 : 2'b00;
endmodule

module IntegerPLL_DCO (
`ifdef USE_POWER_PINS
    inout wire VPWR,
    inout wire VGND,
    inout wire VPB,
    inout wire VNB,
`endif
    input wire RESET_N,
    input wire [254:0] DCO_THERM,
    output wire PLLOUT
);
    assign PLLOUT = 1'b0;
endmodule

module tb_sky130_top_smoke;
    supply1 VPWR;
    supply1 VPB;
    supply0 VGND;
    supply0 VNB;

    reg ref_clk;
    reg pllo_drive;
    reg reset_n;
    reg dlf_en;
    reg dlf_clear;
    reg dlf_override;
    reg dlf_in_pol;
    reg [9:0] dlf_ext_data;
    reg [7:0] dlf_ki;
    reg [4:0] dlf_kp;
    reg [5:0] coarse_code;
    reg [7:0] mmd_ratio;

    wire pllo;
    wire pllo_div;
    wire clkdiv_retimed;
    wire [1:0] bbpd_code;
    wire [7:0] dco_code;
    wire [9:0] dlf_code;

    integer pllo_div_edges;
    integer clkdiv_edges;

    IntegerPLL_Top #(
        .DLF_FRAC_WIDTH(6),
        .DLF_ACQ_BOOST_SHIFT(4),
        .DLF_ACQ_BOOST_AFTER(2),
        .DLF_ACQ_RAIL_BOOST(1),
        .DLF_ACQ_FORCE_RAIL_CODE(127),
        .DLF_PROP_RAIL_GUARD(1)
    ) dut (
        .VPWR(VPWR),
        .VGND(VGND),
        .VPB(VPB),
        .VNB(VNB),
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
        forever #5 ref_clk = ~ref_clk;
    end

    initial begin
        pllo_drive = 1'b0;
        forever #1 pllo_drive = ~pllo_drive;
    end

    always @(pllo_drive) begin
        force dut.PLLOUT = pllo_drive;
        force dut.digital_core.PLLOUT = pllo_drive;
    end

    always @(posedge pllo_div)
        pllo_div_edges = pllo_div_edges + 1;

    always @(posedge clkdiv_retimed)
        clkdiv_edges = clkdiv_edges + 1;

    function integer therm_low_count;
        integer idx;
        begin
            therm_low_count = 0;
            for (idx = 0; idx < 255; idx = idx + 1) begin
                if (dut.dco_therm[idx] === 1'b0)
                    therm_low_count = therm_low_count + 1;
                else if (dut.dco_therm[idx] !== 1'b1)
                    therm_low_count = -1;
            end
        end
    endfunction

    task check_external_code;
        input [9:0] ext_code;
        input [7:0] expected_dco_code;
        integer low_bits;
        begin
            dlf_ext_data = ext_code;
            repeat (4) @(posedge clkdiv_retimed);
            #1;

            if (dlf_code !== ext_code)
                $fatal(1, "DLF_CODE mismatch: ext=%0d observed=%0d", ext_code, dlf_code);
            if (dco_code !== expected_dco_code)
                $fatal(1, "DCO_CODE mismatch: ext=%0d expected=%0d observed=%0d",
                       ext_code, expected_dco_code, dco_code);

            low_bits = therm_low_count();
            if (low_bits != expected_dco_code)
                $fatal(1, "DCO_THERM mismatch: code=%0d low_bits=%0d",
                       expected_dco_code, low_bits);

            $display("CHECK: ext=%0d dco_code=%0d therm_low_bits=%0d therm_high_bits=%0d",
                     ext_code, dco_code, low_bits, 255 - low_bits);
        end
    endtask

    initial begin
        ref_clk = 1'b0;
        reset_n = 1'b0;
        dlf_en = 1'b0;
        dlf_clear = 1'b0;
        dlf_override = 1'b1;
        dlf_in_pol = 1'b1;
        dlf_ext_data = 10'd0;
        dlf_ki = 8'd160;
        dlf_kp = 8'd8;
        coarse_code = 4'd5;
        mmd_ratio = 8'd8;
        pllo_div_edges = 0;
        clkdiv_edges = 0;

        force dut.PLLOUT = pllo_drive;
        force dut.digital_core.PLLOUT = pllo_drive;

        repeat (8) @(posedge pllo_drive);
        reset_n = 1'b1;
        dlf_en = 1'b1;
        repeat (8) @(posedge clkdiv_retimed);

        check_external_code(10'd0, 8'd0);
        check_external_code(10'd512, 8'd128);
        check_external_code(10'd1020, 8'd255);

        if (pllo_div_edges < 2)
            $fatal(1, "PLLOUT_DIV did not toggle enough: edges=%0d", pllo_div_edges);
        if (clkdiv_edges < 12)
            $fatal(1, "CLKDIV_RETIMED did not toggle enough: edges=%0d", clkdiv_edges);
        if (^bbpd_code === 1'bx)
            $fatal(1, "BBPD_CODE is unknown");

        $display("PASS: Sky130 structural top smoke");
        $finish;
    end
endmodule

`default_nettype wire
