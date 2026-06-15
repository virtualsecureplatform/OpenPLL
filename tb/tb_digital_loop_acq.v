// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module tb_digital_loop_acq #(
    parameter DLF_FRAC_WIDTH = 8,
    parameter DLF_ACQ_BOOST_SHIFT = 0,
    parameter DLF_ACQ_BOOST_AFTER = 3,
    parameter DLF_ACQ_RAIL_BOOST = 0,
    parameter DLF_ACQ_FORCE_RAIL_CODE = 0,
    parameter DLF_UPDATE_ON_PLLOUT = 0,
    parameter DLF_PROP_RAIL_GUARD = 0,
    parameter DCO_COARSE_BITS = 0
);

    localparam real TARGET_DCO_MHZ = 101.9368;
    localparam integer DEFAULT_TARGET_DCO_CODE = 128;
    localparam integer DEFAULT_TARGET_TOL_CODE = 32;
    localparam integer MMD_RATIO = 8;
    localparam real REF_HALF_NS = 39.24;

    reg ref_clk;
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

    real half_period_ns;
    integer load_count;
    integer start_code;
    integer final_code;
    integer cfg_ki;
    integer cfg_kp;
    integer cfg_target_code;
    integer cfg_target_tol;
    integer cfg_run_ns;
    integer cfg_low_init;
    integer cfg_high_init;
    integer cfg_allow_fail;
    integer cfg_coarse_code;
    integer case_passed;
    integer run_start_ns;
    integer run_deadline_ns;
    integer lock_ns;
    integer min_abs_error_code;
    integer current_code;
    integer current_error_code;

    function integer abs_int;
        input integer value;
        begin
            abs_int = (value < 0) ? -value : value;
        end
    endfunction

    function integer count255;
        input [254:0] value;
        integer i;
        begin
            count255 = 0;
            for (i = 0; i < 255; i = i + 1)
                count255 = count255 + value[i];
        end
    endfunction

    task drive_bbpd_event;
        input [1:0] first_code;
        begin
            bbpd = 2'b00;
            #1;
            bbpd = first_code;
            #2;
            bbpd = 2'b11;
            #2;
            bbpd = 2'b00;
        end
    endtask

    IntegerPLL_DigitalCore #(
        .DLF_FRAC_WIDTH(DLF_FRAC_WIDTH),
        .DLF_ACQ_BOOST_SHIFT(DLF_ACQ_BOOST_SHIFT),
        .DLF_ACQ_BOOST_AFTER(DLF_ACQ_BOOST_AFTER),
        .DLF_ACQ_RAIL_BOOST(DLF_ACQ_RAIL_BOOST),
        .DLF_ACQ_FORCE_RAIL_CODE(DLF_ACQ_FORCE_RAIL_CODE),
        .DLF_UPDATE_ON_PLLOUT(DLF_UPDATE_ON_PLLOUT),
        .DLF_PROP_RAIL_GUARD(DLF_PROP_RAIL_GUARD),
        .DCO_COARSE_BITS(DCO_COARSE_BITS)
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
        ref_clk = 1'b0;
        forever #(REF_HALF_NS) ref_clk = ~ref_clk;
    end

    always @* begin
        load_count = count255(dco_therm);
        half_period_ns = 3.0 + (0.015 * load_count);
    end

    always begin
        if (!reset_n) begin
            pllo = 1'b0;
            @(posedge reset_n);
        end else begin
            #(half_period_ns) pllo = ~pllo;
        end
    end

    always @(posedge clkdiv_retimed or negedge reset_n) begin
        if (!reset_n || !dlf_en)
            bbpd <= 2'b00;
        else if (dco_code < cfg_target_code[7:0])
            drive_bbpd_event(2'b10);
        else if (dco_code > cfg_target_code[7:0])
            drive_bbpd_event(2'b01);
        else
            bbpd <= 2'b00;
    end

    task run_case;
        input [1023:0] name;
        input [9:0] init_code;
        input integer expect_increase;
        begin
            reset_n = 1'b0;
            dlf_en = 1'b0;
            dlf_clear = 1'b0;
            dlf_override = 1'b0;
            dlf_in_pol = 1'b1;
            dlf_ext_data = init_code;
            dlf_ki = cfg_ki[7:0];
            dlf_kp = cfg_kp[4:0];
            coarse_code = cfg_coarse_code[3:0];
            mmd_ratio = MMD_RATIO[7:0];

            repeat (6) @(posedge ref_clk);
            reset_n = 1'b1;
            repeat (2) @(posedge ref_clk);

            dlf_clear = 1'b1;
            repeat (4) @(posedge clkdiv_retimed);
            dlf_clear = 1'b0;
            repeat (2) @(posedge clkdiv_retimed);

            start_code = dco_code;
            current_code = dco_code;
            min_abs_error_code = abs_int(current_code - cfg_target_code);
            lock_ns = -1;
            run_start_ns = $time;
            run_deadline_ns = run_start_ns + cfg_run_ns;
            dlf_en = 1'b1;
            while ($time < run_deadline_ns) begin
                @(posedge clkdiv_retimed);
                current_code = dco_code;
                current_error_code = abs_int(current_code - cfg_target_code);
                if (current_error_code < min_abs_error_code)
                    min_abs_error_code = current_error_code;
                if ((lock_ns < 0) && (current_error_code <= cfg_target_tol))
                    lock_ns = $time - run_start_ns;
            end
            final_code = dco_code;
            case_passed = 1;

            if (expect_increase && final_code <= start_code) begin
                case_passed = 0;
            end

            if (!expect_increase && final_code >= start_code) begin
                case_passed = 0;
            end

            if (abs_int(final_code - cfg_target_code) > cfg_target_tol) begin
                case_passed = 0;
            end

            if (lock_ns < 0) begin
                case_passed = 0;
            end

            $display("RESULT: case=%0s pass=%0d ki=%0d kp=%0d init_dlf=%0d start_code=%0d final_code=%0d target_code=%0d tol_code=%0d run_ns=%0d lock_ns=%0d min_abs_error_code=%0d ref_mhz=%0.3f",
                     name, case_passed, cfg_ki, cfg_kp, init_code, start_code,
                     final_code, cfg_target_code, cfg_target_tol, cfg_run_ns,
                     lock_ns, min_abs_error_code, TARGET_DCO_MHZ / MMD_RATIO);

            if (!case_passed && !cfg_allow_fail)
                $fatal(1, "FAIL: %0s did not acquire target", name);

            dlf_en = 1'b0;
            repeat (4) @(posedge ref_clk);
        end
    endtask

    initial begin
        pllo = 1'b0;
        reset_n = 1'b0;
        bbpd = 2'b00;
        dlf_en = 1'b0;
        dlf_clear = 1'b0;
        dlf_override = 1'b0;
        dlf_in_pol = 1'b1;
        dlf_ext_data = 10'd0;
        cfg_ki = 255;
        cfg_kp = 4;
        cfg_target_code = DEFAULT_TARGET_DCO_CODE;
        cfg_target_tol = DEFAULT_TARGET_TOL_CODE;
        cfg_run_ns = 120000;
        cfg_low_init = 0;
        cfg_high_init = 1020;
        cfg_allow_fail = 0;
        cfg_coarse_code = 5;
        if (!$value$plusargs("KI=%d", cfg_ki))
            cfg_ki = 255;
        if (!$value$plusargs("KP=%d", cfg_kp))
            cfg_kp = 4;
        if (!$value$plusargs("TARGET_CODE=%d", cfg_target_code))
            cfg_target_code = DEFAULT_TARGET_DCO_CODE;
        if (!$value$plusargs("TOL_CODE=%d", cfg_target_tol))
            cfg_target_tol = DEFAULT_TARGET_TOL_CODE;
        if (!$value$plusargs("RUN_NS=%d", cfg_run_ns))
            cfg_run_ns = 120000;
        if (!$value$plusargs("LOW_INIT=%d", cfg_low_init))
            cfg_low_init = 0;
        if (!$value$plusargs("HIGH_INIT=%d", cfg_high_init))
            cfg_high_init = 1020;
        if (!$value$plusargs("ALLOW_FAIL=%d", cfg_allow_fail))
            cfg_allow_fail = 0;
        if (!$value$plusargs("COARSE_CODE=%d", cfg_coarse_code))
            cfg_coarse_code = 5;

        dlf_ki = cfg_ki[7:0];
        dlf_kp = cfg_kp[4:0];
        coarse_code = cfg_coarse_code[3:0];
        mmd_ratio = MMD_RATIO[7:0];

        run_case("low-start", cfg_low_init[9:0], 1);
        run_case("high-start", cfg_high_init[9:0], 0);

        $display("PASS: digital loop acquisition test");
        $finish;
    end

endmodule

`default_nettype wire
