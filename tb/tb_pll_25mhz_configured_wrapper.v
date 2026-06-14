// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module tb_pll_25mhz_configured_wrapper;
    reg ref_clk;
    reg reset_n;
    reg pll_enable;
    reg [1:0] mode_select;

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

    IntegerPLL_HardMacroTop_EINVP_25MHzConfigured #(
        .MODE_CLEAR_CYCLES(3)
    ) dut (
        .REF(ref_clk),
        .RESET_N(reset_n),
        .PLL_ENABLE(pll_enable),
        .MODE_SELECT(mode_select),
        .PLLOUT(pllout),
        .PLLOUT_DIV(pllout_div),
        .CLKDIV_RETIMED(clkdiv_retimed),
        .BBPD_CODE(bbpd_code),
        .DCO_CODE(dco_code),
        .DLF_CODE(dlf_code),
        .CONFIG_BUSY(config_busy),
        .TRACKING(tracking),
        .TARGET_MHZ(target_mhz),
        .TARGET_DCO_CODE(target_dco_code)
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
            if (dut.hard_macro.DLF_Ext_Data !== {expected_dco_code, 2'b00})
                $fatal(1, "%0s hard macro seed mismatch: got %0d expected %0d",
                       label, dut.hard_macro.DLF_Ext_Data, {expected_dco_code, 2'b00});
            if (target_mhz !== expected_target_mhz)
                $fatal(1, "%0s target MHz mismatch: got %0d expected %0d",
                       label, target_mhz, expected_target_mhz);
            if (target_dco_code !== expected_dco_code)
                $fatal(1, "%0s target code mismatch: got %0d expected %0d",
                       label, target_dco_code, expected_dco_code);
        end
    endtask

    task load_and_track_mode;
        input [1:0] mode;
        input [15:0] expected_target_mhz;
        input [7:0] expected_ratio;
        input [5:0] expected_coarse_code;
        input [7:0] expected_dco_code;
        begin
            mode_select = mode;
            pll_enable = 1'b1;

            tick();
            if (config_busy !== 1'b1 || tracking !== 1'b0)
                $fatal(1, "mode %0d first load edge status busy=%0b tracking=%0b",
                       mode, config_busy, tracking);
            check_hard_macro_inputs("first load edge", 1'b0, 1'b1,
                                    expected_target_mhz, expected_ratio,
                                    expected_coarse_code, expected_dco_code);

            tick();
            check_hard_macro_inputs("second load edge", 1'b0, 1'b1,
                                    expected_target_mhz, expected_ratio,
                                    expected_coarse_code, expected_dco_code);
            tick();
            check_hard_macro_inputs("third load edge", 1'b0, 1'b1,
                                    expected_target_mhz, expected_ratio,
                                    expected_coarse_code, expected_dco_code);
            tick();
            if (config_busy !== 1'b0 || tracking !== 1'b1)
                $fatal(1, "mode %0d track status busy=%0b tracking=%0b",
                       mode, config_busy, tracking);
            check_hard_macro_inputs("track edge", 1'b1, 1'b0,
                                    expected_target_mhz, expected_ratio,
                                    expected_coarse_code, expected_dco_code);
            if (pllout_div !== 1'b1)
                $fatal(1, "mode %0d stub PLLOUT_DIV should show tracking enable", mode);
        end
    endtask

    initial begin
        reset_n = 1'b0;
        pll_enable = 1'b0;
        mode_select = 2'd0;

        repeat (2) @(posedge ref_clk);
        #1;
        if (config_busy !== 1'b0 || tracking !== 1'b0)
            $fatal(1, "reset status mismatch busy=%0b tracking=%0b",
                   config_busy, tracking);
        check_hard_macro_inputs("reset", 1'b0, 1'b0, 16'd100, 8'd4, 6'd20, 8'd93);

        reset_n = 1'b1;
        load_and_track_mode(2'd0, 16'd100, 8'd4, 6'd20, 8'd93);

        mode_select = 2'd1;
        #1;
        check_hard_macro_inputs("before 250 MHz reload", 1'b1, 1'b0,
                                16'd100, 8'd4, 6'd20, 8'd93);
        load_and_track_mode(2'd1, 16'd250, 8'd10, 6'd6, 8'd234);

        mode_select = 2'd2;
        #1;
        check_hard_macro_inputs("before 300 MHz reload", 1'b1, 1'b0,
                                16'd250, 8'd10, 6'd6, 8'd234);
        load_and_track_mode(2'd2, 16'd300, 8'd12, 6'd4, 8'd90);

        mode_select = 2'd3;
        #1;
        check_hard_macro_inputs("before 400 MHz reload", 1'b1, 1'b0,
                                16'd300, 8'd12, 6'd4, 8'd90);
        load_and_track_mode(2'd3, 16'd400, 8'd16, 6'd2, 8'd76);

        pll_enable = 1'b0;
        tick();
        if (config_busy !== 1'b0 || tracking !== 1'b0)
            $fatal(1, "disabled status mismatch busy=%0b tracking=%0b",
                   config_busy, tracking);
        check_hard_macro_inputs("disabled", 1'b0, 1'b0, 16'd400, 8'd16, 6'd2, 8'd76);

        $display("PASS: 25 MHz configured wrapper mode sequencing");
        $finish;
    end
endmodule

`default_nettype wire
