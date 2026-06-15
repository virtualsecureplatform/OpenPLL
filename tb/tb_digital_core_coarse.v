// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module tb_digital_core_coarse;

    reg pllo;
    reg reset_n;
    reg [1:0] bbpd;
    reg dlf_en;
    reg dlf_clear;
    reg dlf_override;
    reg dlf_in_pol;
    reg [9:0] dlf_ext_data;
    reg [7:0] dlf_ki;
    reg [4:0] dlf_kp;
    reg [3:0] coarse_code;
    reg [7:0] mmd_ratio;

    wire clkdiv_retimed;
    wire pllo_div;
    wire [14:0] coarse_therm;
    wire [4:0] medium_binary;
    wire [4:0] fine_binary;
    wire [30:0] medium_ctrl;
    wire [30:0] fine_ctrl;
    wire [7:0] dco_code;
    wire [254:0] dco_therm;
    wire [9:0] dlf_code;

    integer load_count;
    integer coarse_load_count;

    function integer count255;
        input [254:0] value;
        integer i;
        begin
            count255 = 0;
            for (i = 0; i < 255; i = i + 1)
                count255 = count255 + value[i];
        end
    endfunction

    function integer count15;
        input [14:0] value;
        integer i;
        begin
            count15 = 0;
            for (i = 0; i < 15; i = i + 1)
                count15 = count15 + value[i];
        end
    endfunction

    task check_code;
        input [3:0] coarse;
        input [9:0] dlf_word;
        input [7:0] expected_code;
        begin
            coarse_code = coarse;
            dlf_ext_data = dlf_word;
            repeat (2) @(posedge pllo);
            #1;

            load_count = count255(dco_therm);
            if (dco_code !== expected_code) begin
                $display("FAIL: coarse DCO code mismatch coarse=%0d dlf=%0d expected=%0d observed=%0d",
                         coarse, dlf_word, expected_code, dco_code);
                $fatal(1);
            end
            if (load_count !== (255 - expected_code)) begin
                $display("FAIL: coarse DCO thermometer mismatch code=%0d loads=%0d",
                         expected_code, load_count);
                $fatal(1);
            end
        end
    endtask

    IntegerPLL_DigitalCore #(
        .DCO_COARSE_BITS(0),
        .DCO_CONTROL_REGISTERED(0)
    ) dut (
        .PLLOUT(pllo),
        .RESET_N(reset_n),
        .BBPD(bbpd),
        .DLF_En(dlf_en),
        .DLF_Clear(dlf_clear),
        .DLF_Ext_Override(dlf_override),
        .DLF_IN_POL(dlf_in_pol),
        .DLF_Ext_Data(dlf_ext_data),
        .DLF_KI(dlf_ki),
        .DLF_KP(dlf_kp),
        .COARSEBINARY_CODE(coarse_code),
        .MMDCLKDIV_RATIO(mmd_ratio),
        .CLKDIV_RETIMED(clkdiv_retimed),
        .PLLOUT_DIV(pllo_div),
        .COARSETHERMAL_CODE(coarse_therm),
        .Medium_BINARY_CODE(medium_binary),
        .Fine_BINARY_CODE(fine_binary),
        .Medium_CAPS_CTRL(medium_ctrl),
        .Fine_CAPS_CTRL(fine_ctrl),
        .DCO_CODE(dco_code),
        .DCO_THERM(dco_therm),
        .DLF_CODE(dlf_code)
    );

    initial begin
        pllo = 1'b0;
        forever #1 pllo = ~pllo;
    end

    initial begin
        reset_n = 1'b0;
        bbpd = 2'b00;
        dlf_en = 1'b0;
        dlf_clear = 1'b0;
        dlf_override = 1'b1;
        dlf_in_pol = 1'b1;
        dlf_ext_data = 10'd0;
        dlf_ki = 8'd0;
        dlf_kp = 5'd0;
        coarse_code = 4'd0;
        mmd_ratio = 8'd8;

        repeat (4) @(posedge pllo);
        reset_n = 1'b1;
        repeat (4) @(posedge pllo);

        check_code(4'd0, 10'd0, 8'h00);
        check_code(4'd5, 10'd0, 8'h00);
        check_code(4'd5, 10'd512, 8'h80);
        check_code(4'd5, 10'd960, 8'hf0);
        check_code(4'd15, 10'd960, 8'hf0);

        coarse_load_count = count15(coarse_therm);
        if (coarse_load_count !== 15) begin
            $display("FAIL: coarse thermometer decode is %b", coarse_therm);
            $fatal(1);
        end

        $display("PASS: digital core independent coarse/fine DCO mode");
        $finish;
    end

endmodule

`default_nettype wire
