// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module tb_pll_25mhz_configured_behavioral;
    reg ref_clk;
    reg reset_n;
    reg pll_enable;
    reg [4:0] feedback_divider;

    wire dlf_en;
    wire dlf_clear;
    wire dlf_override;
    wire dlf_in_pol;
    wire [9:0] dlf_ext_data;
    wire [7:0] dlf_ki;
    wire [7:0] dlf_kp;
    wire [5:0] coarse_code;
    wire [7:0] mmd_ratio;
    wire config_busy;
    wire tracking;
    wire [15:0] target_mhz;
    wire [7:0] target_dco_code;
    wire config_valid;

    wire pllout;
    wire pllout_div;
    wire clkdiv_retimed;
    wire [1:0] bbpd_code;
    wire [7:0] dco_code;
    wire [9:0] dlf_code;

    integer pllout_edges;

    IntegerPLL_25MHzModeController #(
        .CLEAR_CYCLES(4)
    ) mode_controller (
        .CLKDIV_RETIMED(clkdiv_retimed),
        .RESET_N(reset_n),
        .PLL_ENABLE(pll_enable),
        .FEEDBACK_DIVIDER(feedback_divider),
        .DLF_En(dlf_en),
        .DLF_Clear(dlf_clear),
        .DLF_Ext_Override(dlf_override),
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

    IntegerPLL_Top #(
        .DLF_FRAC_WIDTH(2),
        .DLF_PROP_RAIL_GUARD(1)
    ) pll (
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
        .PLLOUT(pllout),
        .PLLOUT_DIV(pllout_div),
        .CLKDIV_RETIMED(clkdiv_retimed),
        .BBPD_CODE(bbpd_code),
        .DCO_CODE(dco_code),
        .DLF_CODE(dlf_code)
    );

    initial begin
        ref_clk = 1'b0;
        forever #20 ref_clk = ~ref_clk;
    end

    always @(posedge pllout)
        pllout_edges = pllout_edges + 1;

    function integer abs_int;
        input integer value;
        begin
            abs_int = (value < 0) ? -value : value;
        end
    endfunction

    function real abs_real;
        input real value;
        begin
            abs_real = (value < 0.0) ? -value : value;
        end
    endfunction

    task wait_for_tracking;
        integer guard;
        begin
            guard = 0;
            while ((tracking !== 1'b1) && (guard < 400)) begin
                @(posedge ref_clk);
                guard = guard + 1;
            end
            if (tracking !== 1'b1)
                $fatal(1, "tracking did not assert for divider %0d", feedback_divider);
        end
    endtask

    task run_divider;
        input [4:0] divider;
        input [15:0] expected_target_mhz;
        input [7:0] expected_ratio;
        input [5:0] expected_coarse_code;
        input [7:0] expected_target_code;
        integer start_edges;
        integer end_edges;
        integer idx;
        integer inc_count;
        integer dec_count;
        integer idle_count;
        realtime start_time;
        realtime end_time;
        real measured_mhz;
        begin
            reset_n = 1'b0;
            pll_enable = 1'b0;
            feedback_divider = divider;
            repeat (5) @(posedge ref_clk);
            reset_n = 1'b1;
            repeat (2) @(posedge ref_clk);
            pll_enable = 1'b1;

            wait_for_tracking();
            if (config_valid !== 1'b1)
                $fatal(1, "divider %0d did not produce a valid configuration", divider);
            if (target_mhz !== expected_target_mhz)
                $fatal(1, "divider %0d target mismatch: got %0d expected %0d",
                       divider, target_mhz, expected_target_mhz);
            if (mmd_ratio !== expected_ratio)
                $fatal(1, "divider %0d MMD ratio mismatch: got %0d expected %0d",
                       divider, mmd_ratio, expected_ratio);
            if (coarse_code !== expected_coarse_code)
                $fatal(1, "divider %0d coarse mismatch: got %0d expected %0d",
                       divider, coarse_code, expected_coarse_code);
            if (target_dco_code !== expected_target_code)
                $fatal(1, "divider %0d target-code mismatch: got %0d expected %0d",
                       divider, target_dco_code, expected_target_code);
            if (abs_int(dco_code - expected_target_code) > 4)
                $fatal(1, "divider %0d did not load near target: dco=%0d target=%0d",
                       divider, dco_code, expected_target_code);

            inc_count = 0;
            dec_count = 0;
            idle_count = 0;
            start_edges = pllout_edges;
            start_time = $realtime;
            for (idx = 0; idx < 512; idx = idx + 1) begin
                @(posedge clkdiv_retimed);
                if (bbpd_code == 2'b10)
                    inc_count = inc_count + 1;
                else if (bbpd_code == 2'b01)
                    dec_count = dec_count + 1;
                else
                    idle_count = idle_count + 1;
            end
            end_time = $realtime;
            end_edges = pllout_edges;
            measured_mhz = 1000.0 * (end_edges - start_edges) / (end_time - start_time);

            if ((dco_code < 4) || (dco_code > 251))
                $fatal(1, "divider %0d final code remains railed: dco=%0d target=%0d",
                       divider, dco_code, expected_target_code);
            if (abs_real(measured_mhz - expected_target_mhz) > 8.0)
                $fatal(1, "divider %0d measured frequency too far: got %0.3f MHz expected %0d MHz",
                       divider, measured_mhz, expected_target_mhz);
            if ((inc_count + dec_count) < 1)
                $fatal(1, "divider %0d saw no active BBPD decisions", divider);

            $display("RESULT: feedback_divider=%0d target_mhz=%0d ratio=%0d coarse=%0d target_code=%0d final_code=%0d measured_mhz=%0.3f inc=%0d dec=%0d idle=%0d",
                     divider, expected_target_mhz, expected_ratio, expected_coarse_code,
                     expected_target_code, dco_code, measured_mhz,
                     inc_count, dec_count, idle_count);

            pll_enable = 1'b0;
            repeat (3) @(posedge ref_clk);
        end
    endtask

    initial begin
        reset_n = 1'b0;
        pll_enable = 1'b0;
        feedback_divider = 5'd4;
        pllout_edges = 0;

        run_divider(5'd4, 16'd100, 8'd4, 6'd20, 8'd93);
        run_divider(5'd10, 16'd250, 8'd10, 6'd6, 8'd234);
        run_divider(5'd12, 16'd300, 8'd12, 6'd4, 8'd90);
        run_divider(5'd16, 16'd400, 8'd16, 6'd2, 8'd76);

        $display("PASS: 25 MHz configured behavioral PLL tracking");
        $finish;
    end
endmodule

`default_nettype wire
