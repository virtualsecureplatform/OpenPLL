// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module tb_pll_25mhz_mode_config;
    reg [4:0] feedback_divider;
    wire [7:0] mmd_ratio;
    wire [5:0] coarse_code;
    wire [9:0] dlf_ext_data;
    wire [7:0] dlf_ki;
    wire [4:0] dlf_kp;
    wire [15:0] target_mhz;
    wire [7:0] target_dco_code;
    wire config_valid;

    IntegerPLL_25MHzModeConfig dut (
        .FEEDBACK_DIVIDER(feedback_divider),
        .MMDCLKDIV_RATIO(mmd_ratio),
        .COARSEBINARY_CODE(coarse_code),
        .DLF_Ext_Data(dlf_ext_data),
        .DLF_KI(dlf_ki),
        .DLF_KP(dlf_kp),
        .TARGET_MHZ(target_mhz),
        .TARGET_DCO_CODE(target_dco_code),
        .CONFIG_VALID(config_valid)
    );

    task check_divider;
        input [4:0] divider;
        input [15:0] expected_target_mhz;
        input [7:0] expected_ratio;
        input [5:0] expected_coarse_code;
        input [7:0] expected_dco_code;
        input [7:0] expected_ki;
        input [4:0] expected_kp;
        input expected_valid;
        begin
            feedback_divider = divider;
            #1;
            if (target_mhz !== expected_target_mhz)
                $fatal(1, "target mismatch for divider %0d: got %0d expected %0d",
                       divider, target_mhz, expected_target_mhz);
            if (mmd_ratio !== expected_ratio)
                $fatal(1, "MMD ratio mismatch for divider %0d: got %0d expected %0d",
                       divider, mmd_ratio, expected_ratio);
            if (coarse_code !== expected_coarse_code)
                $fatal(1, "coarse mismatch for divider %0d: got %0d expected %0d",
                       divider, coarse_code, expected_coarse_code);
            if (target_dco_code !== expected_dco_code)
                $fatal(1, "target code mismatch for divider %0d: got %0d expected %0d",
                       divider, target_dco_code, expected_dco_code);
            if (dlf_ext_data !== (expected_valid ? {expected_dco_code, 2'b00} : 10'd0))
                $fatal(1, "DLF seed mismatch for divider %0d: got %0d",
                       divider, dlf_ext_data);
            if (dlf_ki !== expected_ki)
                $fatal(1, "KI mismatch for divider %0d: got %0d expected %0d",
                       divider, dlf_ki, expected_ki);
            if (dlf_kp !== expected_kp)
                $fatal(1, "KP mismatch for divider %0d: got %0d expected %0d",
                       divider, dlf_kp, expected_kp);
            if (config_valid !== expected_valid)
                $fatal(1, "CONFIG_VALID mismatch for divider %0d: got %0b expected %0b",
                       divider, config_valid, expected_valid);
        end
    endtask

    initial begin
        check_divider(5'd4, 16'd100, 8'd4, 6'd24, 8'd139, 8'd4, 5'd2, 1'b1);
        check_divider(5'd10, 16'd250, 8'd10, 6'd7, 8'd8, 8'd4, 5'd2, 1'b1);
        check_divider(5'd12, 16'd300, 8'd12, 6'd6, 8'd242, 8'd4, 5'd2, 1'b1);
        check_divider(5'd16, 16'd400, 8'd16, 6'd3, 8'd45, 8'd4, 5'd2, 1'b1);
        check_divider(5'd20, 16'd500, 8'd20, 6'd2, 8'd149, 8'd4, 5'd2, 1'b1);
        check_divider(5'd5, 16'd0, 8'd5, 6'd0, 8'd0, 8'd4, 5'd2, 1'b0);
        $display("PASS: 25 MHz PLL divider configuration table");
        $finish;
    end
endmodule

`default_nettype wire
