// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module tb_pll_25mhz_configured_wrapper;
    reg ref_clk;
    reg reset_n;
    reg pll_enable;
    reg [4:0] feedback_divider;

    wire pllout;
    wire pllout_div;
    wire clkdiv_retimed;
    wire [1:0] bbpd_code;
    wire [7:0] dco_code;
    wire [9:0] dlf_code;
    wire config_busy;
    wire tracking;
    wire [15:0] target_mhz;
    wire [7:0] target_dco_code;
    wire config_valid;

    IntegerPLL_HardMacroTop_EINVP_25MHzConfigured #(
        .MODE_CLEAR_CYCLES(3)
    ) dut (
        .REF(ref_clk),
        .RESET_N(reset_n),
        .PLL_ENABLE(pll_enable),
        .FEEDBACK_DIVIDER(feedback_divider),
        .PLLOUT(pllout),
        .PLLOUT_DIV(pllout_div),
        .CLKDIV_RETIMED(clkdiv_retimed),
        .BBPD_CODE(bbpd_code),
        .DCO_CODE(dco_code),
        .DLF_CODE(dlf_code),
        .CONFIG_BUSY(config_busy),
        .TRACKING(tracking),
        .TARGET_MHZ(target_mhz),
        .TARGET_DCO_CODE(target_dco_code),
        .CONFIG_VALID(config_valid)
    );

    initial begin
        ref_clk = 1'b0;
        forever #20 ref_clk = ~ref_clk;
    end

    task tick;
        begin
            @(posedge clkdiv_retimed);
            #1;
        end
    endtask

    task check_hard_macro_inputs;
        input [1023:0] label;
        input expected_dlf_en;
        input expected_dlf_clear;
        input [15:0] expected_target_mhz;
        input [7:0] expected_ratio;
        input [5:0] expected_coarse_code;
        input [7:0] expected_dco_code;
        input expected_valid;
        begin
            if (dut.hard_macro.DLF_En !== expected_dlf_en)
                $fatal(1, "%0s hard macro DLF_En mismatch: got %0b expected %0b",
                       label, dut.hard_macro.DLF_En, expected_dlf_en);
            if (dut.hard_macro.DLF_Clear !== expected_dlf_clear)
                $fatal(1, "%0s hard macro DLF_Clear mismatch: got %0b expected %0b",
                       label, dut.hard_macro.DLF_Clear, expected_dlf_clear);
            if (dut.hard_macro.DLF_Ext_Override !== 1'b0)
                $fatal(1, "%0s hard macro DLF_Ext_Override should remain low", label);
            if (dut.hard_macro.DLF_IN_POL !== 1'b1)
                $fatal(1, "%0s hard macro DLF_IN_POL should remain high", label);
            if (dut.hard_macro.DLF_KI !== 8'd16)
                $fatal(1, "%0s hard macro DLF_KI mismatch: got %0d expected 16",
                       label, dut.hard_macro.DLF_KI);
            if (dut.hard_macro.DLF_KP !== 8'd4)
                $fatal(1, "%0s hard macro DLF_KP mismatch: got %0d expected 4",
                       label, dut.hard_macro.DLF_KP);
            if (dut.hard_macro.MMDCLKDIV_RATIO !== expected_ratio)
                $fatal(1, "%0s hard macro divider mismatch: got %0d expected %0d",
                       label, dut.hard_macro.MMDCLKDIV_RATIO, expected_ratio);
            if (dut.hard_macro.COARSEBINARY_CODE !== expected_coarse_code)
                $fatal(1, "%0s hard macro coarse mismatch: got %0d expected %0d",
                       label, dut.hard_macro.COARSEBINARY_CODE, expected_coarse_code);
            if (dut.hard_macro.DLF_Ext_Data !== (expected_valid ? {expected_dco_code, 2'b00} : 10'd0))
                $fatal(1, "%0s hard macro seed mismatch: got %0d",
                       label, dut.hard_macro.DLF_Ext_Data);
            if (target_mhz !== expected_target_mhz)
                $fatal(1, "%0s target MHz mismatch: got %0d expected %0d",
                       label, target_mhz, expected_target_mhz);
            if (target_dco_code !== expected_dco_code)
                $fatal(1, "%0s target code mismatch: got %0d expected %0d",
                       label, target_dco_code, expected_dco_code);
            if (config_valid !== expected_valid)
                $fatal(1, "%0s CONFIG_VALID mismatch: got %0b expected %0b",
                       label, config_valid, expected_valid);
        end
    endtask

    task load_and_track_divider;
        input [4:0] divider;
        input [15:0] expected_target_mhz;
        input [7:0] expected_ratio;
        input [5:0] expected_coarse_code;
        input [7:0] expected_dco_code;
        begin
            feedback_divider = divider;
            pll_enable = 1'b1;

            tick();
            if (config_busy !== 1'b1 || tracking !== 1'b0)
                $fatal(1, "divider %0d first load edge status busy=%0b tracking=%0b",
                       divider, config_busy, tracking);
            check_hard_macro_inputs("first load edge", 1'b0, 1'b1,
                                    expected_target_mhz, expected_ratio,
                                    expected_coarse_code, expected_dco_code, 1'b1);

            tick();
            check_hard_macro_inputs("second load edge", 1'b0, 1'b1,
                                    expected_target_mhz, expected_ratio,
                                    expected_coarse_code, expected_dco_code, 1'b1);
            tick();
            check_hard_macro_inputs("third load edge", 1'b0, 1'b1,
                                    expected_target_mhz, expected_ratio,
                                    expected_coarse_code, expected_dco_code, 1'b1);
            tick();
            if (config_busy !== 1'b0 || tracking !== 1'b1)
                $fatal(1, "divider %0d track status busy=%0b tracking=%0b",
                       divider, config_busy, tracking);
            check_hard_macro_inputs("track edge", 1'b1, 1'b0,
                                    expected_target_mhz, expected_ratio,
                                    expected_coarse_code, expected_dco_code, 1'b1);
            if (pllout_div !== 1'b1)
                $fatal(1, "divider %0d stub PLLOUT_DIV should show tracking enable", divider);
        end
    endtask

    task load_invalid_divider;
        input [4:0] divider;
        begin
            feedback_divider = divider;
            pll_enable = 1'b1;

            tick();
            if (config_busy !== 1'b1 || tracking !== 1'b0)
                $fatal(1, "invalid divider first edge status busy=%0b tracking=%0b",
                       config_busy, tracking);
            check_hard_macro_inputs("invalid first edge", 1'b0, 1'b0,
                                    16'd0, {3'd0, divider}, 6'd0, 8'd0, 1'b0);

            tick();
            tick();
            tick();
            if (config_busy !== 1'b1 || tracking !== 1'b0)
                $fatal(1, "invalid divider held status busy=%0b tracking=%0b",
                       config_busy, tracking);
            check_hard_macro_inputs("invalid held", 1'b0, 1'b0,
                                    16'd0, {3'd0, divider}, 6'd0, 8'd0, 1'b0);
        end
    endtask

    initial begin
        reset_n = 1'b0;
        pll_enable = 1'b0;
        feedback_divider = 5'd4;

        repeat (2) @(posedge ref_clk);
        #1;
        if (config_busy !== 1'b0 || tracking !== 1'b0)
            $fatal(1, "reset status mismatch busy=%0b tracking=%0b",
                   config_busy, tracking);
        check_hard_macro_inputs("reset", 1'b0, 1'b0, 16'd100, 8'd4, 6'd20, 8'd93, 1'b1);

        reset_n = 1'b1;
        load_and_track_divider(5'd4, 16'd100, 8'd4, 6'd20, 8'd93);

        feedback_divider = 5'd10;
        #1;
        check_hard_macro_inputs("before 250 MHz reload", 1'b1, 1'b0,
                                16'd100, 8'd4, 6'd20, 8'd93, 1'b1);
        load_and_track_divider(5'd10, 16'd250, 8'd10, 6'd6, 8'd234);

        feedback_divider = 5'd12;
        #1;
        check_hard_macro_inputs("before 300 MHz reload", 1'b1, 1'b0,
                                16'd250, 8'd10, 6'd6, 8'd234, 1'b1);
        load_and_track_divider(5'd12, 16'd300, 8'd12, 6'd4, 8'd90);

        feedback_divider = 5'd16;
        #1;
        check_hard_macro_inputs("before 400 MHz reload", 1'b1, 1'b0,
                                16'd300, 8'd12, 6'd4, 8'd90, 1'b1);
        load_and_track_divider(5'd16, 16'd400, 8'd16, 6'd2, 8'd76);

        feedback_divider = 5'd20;
        #1;
        check_hard_macro_inputs("before 500 MHz reload", 1'b1, 1'b0,
                                16'd400, 8'd16, 6'd2, 8'd76, 1'b1);
        load_and_track_divider(5'd20, 16'd500, 8'd20, 6'd1, 8'd121);

        pll_enable = 1'b0;
        tick();
        if (config_busy !== 1'b0 || tracking !== 1'b0)
            $fatal(1, "disabled status mismatch busy=%0b tracking=%0b",
                   config_busy, tracking);
        check_hard_macro_inputs("disabled", 1'b0, 1'b0, 16'd500, 8'd20, 6'd1, 8'd121, 1'b1);

        load_invalid_divider(5'd5);

        $display("PASS: 25 MHz configured wrapper divider sequencing");
        $finish;
    end
endmodule

`default_nettype wire
