// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module tb_pll_25mhz_mode_config;
    reg [1:0] mode_select;
    wire [7:0] mmd_ratio;
    wire [5:0] coarse_code;
    wire [9:0] dlf_ext_data;
    wire [7:0] dlf_ki;
    wire [7:0] dlf_kp;
    wire [15:0] target_mhz;
    wire [7:0] target_dco_code;

    IntegerPLL_25MHzModeConfig dut (
        .MODE_SELECT(mode_select),
        .MMDCLKDIV_RATIO(mmd_ratio),
        .COARSEBINARY_CODE(coarse_code),
        .DLF_Ext_Data(dlf_ext_data),
        .DLF_KI(dlf_ki),
        .DLF_KP(dlf_kp),
        .TARGET_MHZ(target_mhz),
        .TARGET_DCO_CODE(target_dco_code)
    );

    task check_mode;
        input [1:0] mode;
        input [15:0] expected_target_mhz;
        input [7:0] expected_ratio;
        input [5:0] expected_coarse_code;
        input [7:0] expected_dco_code;
        begin
            mode_select = mode;
            #1;
            if (target_mhz !== expected_target_mhz)
                $fatal(1, "target mismatch for mode %0d: got %0d expected %0d",
                       mode, target_mhz, expected_target_mhz);
            if (mmd_ratio !== expected_ratio)
                $fatal(1, "divider mismatch for mode %0d: got %0d expected %0d",
                       mode, mmd_ratio, expected_ratio);
            if (coarse_code !== expected_coarse_code)
                $fatal(1, "coarse mismatch for mode %0d: got %0d expected %0d",
                       mode, coarse_code, expected_coarse_code);
            if (target_dco_code !== expected_dco_code)
                $fatal(1, "target code mismatch for mode %0d: got %0d expected %0d",
                       mode, target_dco_code, expected_dco_code);
            if (dlf_ext_data !== {expected_dco_code, 2'b00})
                $fatal(1, "DLF seed mismatch for mode %0d: got %0d expected %0d",
                       mode, dlf_ext_data, {expected_dco_code, 2'b00});
            if (dlf_ki !== 8'd16)
                $fatal(1, "KI mismatch for mode %0d: got %0d expected 16",
                       mode, dlf_ki);
            if (dlf_kp !== 8'd4)
                $fatal(1, "KP mismatch for mode %0d: got %0d expected 4",
                       mode, dlf_kp);
        end
    endtask

    initial begin
        check_mode(2'd0, 16'd100, 8'd4, 6'd20, 8'd93);
        check_mode(2'd1, 16'd250, 8'd10, 6'd6, 8'd234);
        check_mode(2'd2, 16'd300, 8'd12, 6'd4, 8'd90);
        check_mode(2'd3, 16'd400, 8'd16, 6'd2, 8'd76);
        $display("PASS: 25 MHz PLL mode configuration table");
        $finish;
    end
endmodule

`default_nettype wire
