// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module tb_pll_25mhz_mode_controller;
    reg clkdiv_retimed;
    reg reset_n;
    reg pll_enable;
    reg [4:0] feedback_divider;

    wire dlf_en;
    wire dlf_clear;
    wire dlf_ext_override;
    wire dlf_in_pol;
    wire [9:0] dlf_ext_data;
    wire [7:0] dlf_ki;
    wire [4:0] dlf_kp;
    wire [5:0] coarse_code;
    wire [7:0] mmd_ratio;
    wire config_busy;
    wire tracking;
    wire [15:0] target_mhz;
    wire [7:0] target_dco_code;
    wire config_valid;

    IntegerPLL_25MHzModeController #(
        .CLEAR_CYCLES(3)
    ) dut (
        .CLKDIV_RETIMED(clkdiv_retimed),
        .RESET_N(reset_n),
        .PLL_ENABLE(pll_enable),
        .FEEDBACK_DIVIDER(feedback_divider),
        .DLF_En(dlf_en),
        .DLF_Clear(dlf_clear),
        .DLF_Ext_Override(dlf_ext_override),
        .DLF_IN_POL(dlf_in_pol),
        .DLF_Ext_Data(dlf_ext_data),
        .DLF_KI(dlf_ki),
        .DLF_KP(dlf_kp),
        .COARSEBINARY_CODE(coarse_code),
        .MMDCLKDIV_RATIO(mmd_ratio),
        .CONFIG_BUSY(config_busy),
        .TRACKING(tracking),
        .TARGET_MHZ(target_mhz),
        .TARGET_DCO_CODE(target_dco_code),
        .CONFIG_VALID(config_valid)
    );

    initial begin
        clkdiv_retimed = 1'b0;
        forever #5 clkdiv_retimed = ~clkdiv_retimed;
    end

    task tick;
        begin
            @(posedge clkdiv_retimed);
            #1;
        end
    endtask

    task check_mode_outputs;
        input [1023:0] label;
        input [15:0] expected_target_mhz;
        input [7:0] expected_ratio;
        input [5:0] expected_coarse_code;
        input [7:0] expected_dco_code;
        input [7:0] expected_ki;
        input [4:0] expected_kp;
        input expected_valid;
        begin
            if (target_mhz !== expected_target_mhz)
                $fatal(1, "%0s target mismatch: got %0d expected %0d",
                       label, target_mhz, expected_target_mhz);
            if (mmd_ratio !== expected_ratio)
                $fatal(1, "%0s divider mismatch: got %0d expected %0d",
                       label, mmd_ratio, expected_ratio);
            if (coarse_code !== expected_coarse_code)
                $fatal(1, "%0s coarse mismatch: got %0d expected %0d",
                       label, coarse_code, expected_coarse_code);
            if (target_dco_code !== expected_dco_code)
                $fatal(1, "%0s target code mismatch: got %0d expected %0d",
                       label, target_dco_code, expected_dco_code);
            if (dlf_ext_data !== (expected_valid ? {expected_dco_code, 2'b00} : 10'd0))
                $fatal(1, "%0s DLF seed mismatch: got %0d",
                       label, dlf_ext_data);
            if (dlf_ki !== expected_ki)
                $fatal(1, "%0s KI mismatch: got %0d expected %0d",
                       label, dlf_ki, expected_ki);
            if (dlf_kp !== expected_kp)
                $fatal(1, "%0s KP mismatch: got %0d expected %0d",
                       label, dlf_kp, expected_kp);
            if (config_valid !== expected_valid)
                $fatal(1, "%0s CONFIG_VALID mismatch: got %0b expected %0b",
                       label, config_valid, expected_valid);
        end
    endtask

    task check_controls;
        input [1023:0] label;
        input expected_en;
        input expected_clear;
        input expected_busy;
        input expected_tracking;
        begin
            if (dlf_en !== expected_en)
                $fatal(1, "%0s DLF_En mismatch: got %0b expected %0b",
                       label, dlf_en, expected_en);
            if (dlf_clear !== expected_clear)
                $fatal(1, "%0s DLF_Clear mismatch: got %0b expected %0b",
                       label, dlf_clear, expected_clear);
            if (config_busy !== expected_busy)
                $fatal(1, "%0s CONFIG_BUSY mismatch: got %0b expected %0b",
                       label, config_busy, expected_busy);
            if (tracking !== expected_tracking)
                $fatal(1, "%0s TRACKING mismatch: got %0b expected %0b",
                       label, tracking, expected_tracking);
            if (dlf_ext_override !== 1'b0)
                $fatal(1, "%0s DLF_Ext_Override should remain low", label);
            if (dlf_in_pol !== 1'b1)
                $fatal(1, "%0s DLF_IN_POL should remain high", label);
        end
    endtask

    task load_and_track_divider;
        input [4:0] divider;
        input [15:0] expected_target_mhz;
        input [7:0] expected_ratio;
        input [5:0] expected_coarse_code;
        input [7:0] expected_dco_code;
        input [7:0] expected_ki;
        input [4:0] expected_kp;
        begin
            feedback_divider = divider;
            pll_enable = 1'b1;

            tick();
            check_controls("load edge 0", 1'b0, 1'b1, 1'b1, 1'b0);
            check_mode_outputs("load edge 0", expected_target_mhz, expected_ratio,
                               expected_coarse_code, expected_dco_code,
                               expected_ki, expected_kp, 1'b1);

            tick();
            check_controls("load edge 1", 1'b0, 1'b1, 1'b1, 1'b0);
            tick();
            check_controls("load edge 2", 1'b0, 1'b1, 1'b1, 1'b0);
            tick();
            check_controls("track edge", 1'b1, 1'b0, 1'b0, 1'b1);
            check_mode_outputs("track edge", expected_target_mhz, expected_ratio,
                               expected_coarse_code, expected_dco_code,
                               expected_ki, expected_kp, 1'b1);
        end
    endtask

    task load_invalid_divider;
        input [4:0] divider;
        begin
            feedback_divider = divider;
            pll_enable = 1'b1;

            tick();
            check_controls("invalid load edge 0", 1'b0, 1'b0, 1'b1, 1'b0);
            check_mode_outputs("invalid load edge 0", 16'd0, {3'd0, divider},
                               6'd0, 8'd0, 8'd16, 5'd4, 1'b0);

            tick();
            check_controls("invalid load edge 1", 1'b0, 1'b0, 1'b1, 1'b0);
            tick();
            check_controls("invalid load edge 2", 1'b0, 1'b0, 1'b1, 1'b0);
            tick();
            check_controls("invalid held busy", 1'b0, 1'b0, 1'b1, 1'b0);
            check_mode_outputs("invalid held busy", 16'd0, {3'd0, divider},
                               6'd0, 8'd0, 8'd16, 5'd4, 1'b0);
        end
    endtask

    initial begin
        reset_n = 1'b1;
        pll_enable = 1'b0;
        feedback_divider = 5'd20;

        #1 reset_n = 1'b0;
        #1;
        check_controls("reset", 1'b0, 1'b0, 1'b0, 1'b0);
        check_mode_outputs("reset", 16'd500, 8'd20, 6'd1, 8'd121, 8'd16, 5'd5, 1'b1);

        reset_n = 1'b1;
        load_and_track_divider(5'd4, 16'd100, 8'd4, 6'd20, 8'd93, 8'd16, 5'd8);
        load_and_track_divider(5'd10, 16'd250, 8'd10, 6'd6, 8'd234, 8'd16, 5'd8);
        load_and_track_divider(5'd12, 16'd300, 8'd12, 6'd4, 8'd90, 8'd16, 5'd2);
        load_and_track_divider(5'd16, 16'd400, 8'd16, 6'd2, 8'd76, 8'd1, 5'd4);
        load_and_track_divider(5'd20, 16'd500, 8'd20, 6'd1, 8'd121, 8'd16, 5'd5);

        pll_enable = 1'b0;
        tick();
        check_controls("disabled", 1'b0, 1'b0, 1'b0, 1'b0);
        check_mode_outputs("disabled", 16'd500, 8'd20, 6'd1, 8'd121, 8'd16, 5'd5, 1'b1);

        load_invalid_divider(5'd5);
        load_and_track_divider(5'd20, 16'd500, 8'd20, 6'd1, 8'd121, 8'd16, 5'd5);

        $display("PASS: 25 MHz PLL divider controller sequencing");
        $finish;
    end
endmodule

`default_nettype wire
