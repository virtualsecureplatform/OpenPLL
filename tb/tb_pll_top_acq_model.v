// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module tb_pll_top_acq_model #(
    parameter DLF_FRAC_WIDTH = 8,
    parameter DLF_ACQ_BOOST_SHIFT = 0,
    parameter DLF_ACQ_BOOST_AFTER = 3,
    parameter DLF_ACQ_RAIL_BOOST = 0,
    parameter DLF_ACQ_FORCE_RAIL_CODE = 0,
    parameter DLF_UPDATE_ON_PLLOUT = 0,
    parameter DLF_PROP_RAIL_GUARD = 0,
    parameter DCO_COARSE_BITS = 0
);

    localparam integer DEFAULT_TARGET_DCO_CODE = 128;
    localparam integer DEFAULT_TARGET_TOL_CODE = 32;
    localparam integer DEFAULT_REF_HALF_PS = 39240;
    localparam integer DEFAULT_MMD_RATIO = 8;

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

    integer cfg_ki;
    integer cfg_kp;
    integer cfg_target_code;
    integer cfg_target_tol;
    integer cfg_run_ns;
    integer cfg_low_init;
    integer cfg_high_init;
    integer cfg_mmd_ratio;
    integer cfg_ref_half_ps;
    integer cfg_allow_fail;
    integer cfg_coarse_code;

    integer start_code;
    integer final_code;
    integer case_passed;
    integer run_start_ns;
    integer run_deadline_ns;
    integer lock_ns;
    integer min_abs_error_code;
    integer current_code;
    integer current_error_code;
    integer pllo_edges_start;
    integer pllo_edges_end;
    integer clkdiv_edges_start;
    integer clkdiv_edges_end;
    integer pllo_edges;
    integer clkdiv_edges;
    integer bbpd_inc_count;
    integer bbpd_dec_count;
    integer bbpd_idle_count;

    real ref_half_ns = DEFAULT_REF_HALF_PS / 1000.0;
    real ref_mhz = 1000000.0 / (2.0 * DEFAULT_REF_HALF_PS);

    function integer abs_int;
        input integer value;
        begin
            abs_int = (value < 0) ? -value : value;
        end
    endfunction

    IntegerPLL_Top #(
        .DLF_FRAC_WIDTH(DLF_FRAC_WIDTH),
        .DLF_ACQ_BOOST_SHIFT(DLF_ACQ_BOOST_SHIFT),
        .DLF_ACQ_BOOST_AFTER(DLF_ACQ_BOOST_AFTER),
        .DLF_ACQ_RAIL_BOOST(DLF_ACQ_RAIL_BOOST),
        .DLF_ACQ_FORCE_RAIL_CODE(DLF_ACQ_FORCE_RAIL_CODE),
        .DLF_UPDATE_ON_PLLOUT(DLF_UPDATE_ON_PLLOUT),
        .DLF_PROP_RAIL_GUARD(DLF_PROP_RAIL_GUARD),
        .DCO_COARSE_BITS(DCO_COARSE_BITS)
    ) dut (
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
        forever begin
            #(ref_half_ns) ref_clk = ~ref_clk;
        end
    end

    always @(posedge pllo)
        pllo_edges = pllo_edges + 1;

    always @(posedge clkdiv_retimed)
        clkdiv_edges = clkdiv_edges + 1;

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
            mmd_ratio = cfg_mmd_ratio[7:0];

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
            pllo_edges_start = pllo_edges;
            clkdiv_edges_start = clkdiv_edges;
            bbpd_inc_count = 0;
            bbpd_dec_count = 0;
            bbpd_idle_count = 0;
            dlf_en = 1'b1;
            while ($time < run_deadline_ns) begin
                @(posedge clkdiv_retimed);
                if (bbpd_code == 2'b10)
                    bbpd_inc_count = bbpd_inc_count + 1;
                else if (bbpd_code == 2'b01)
                    bbpd_dec_count = bbpd_dec_count + 1;
                else
                    bbpd_idle_count = bbpd_idle_count + 1;
                current_code = dco_code;
                current_error_code = abs_int(current_code - cfg_target_code);
                if (current_error_code < min_abs_error_code)
                    min_abs_error_code = current_error_code;
                if ((lock_ns < 0) && (current_error_code <= cfg_target_tol))
                    lock_ns = $time - run_start_ns;
            end
            final_code = dco_code;
            pllo_edges_end = pllo_edges;
            clkdiv_edges_end = clkdiv_edges;
            case_passed = 1;

            if (expect_increase && final_code <= start_code)
                case_passed = 0;

            if (!expect_increase && final_code >= start_code)
                case_passed = 0;

            if (abs_int(final_code - cfg_target_code) > cfg_target_tol)
                case_passed = 0;

            if (lock_ns < 0)
                case_passed = 0;

            if ((pllo_edges_end - pllo_edges_start) < 10)
                case_passed = 0;

            if ((clkdiv_edges_end - clkdiv_edges_start) < 2)
                case_passed = 0;

            $display("RESULT: case=%0s pass=%0d ki=%0d kp=%0d init_dlf=%0d start_code=%0d final_code=%0d target_code=%0d tol_code=%0d run_ns=%0d lock_ns=%0d min_abs_error_code=%0d ref_mhz=%0.6f mmd_ratio=%0d pllo_edges=%0d clkdiv_edges=%0d bbpd_inc=%0d bbpd_dec=%0d bbpd_idle=%0d",
                     name, case_passed, cfg_ki, cfg_kp, init_code, start_code,
                     final_code, cfg_target_code, cfg_target_tol, cfg_run_ns,
                     lock_ns, min_abs_error_code, ref_mhz, cfg_mmd_ratio,
                     pllo_edges_end - pllo_edges_start,
                     clkdiv_edges_end - clkdiv_edges_start,
                     bbpd_inc_count, bbpd_dec_count, bbpd_idle_count);

            if (!case_passed && !cfg_allow_fail)
                $fatal(1, "FAIL: %0s did not acquire target", name);

            dlf_en = 1'b0;
            repeat (4) @(posedge ref_clk);
        end
    endtask

    initial begin
        ref_clk = 1'b0;
        reset_n = 1'b0;
        dlf_en = 1'b0;
        dlf_clear = 1'b0;
        dlf_override = 1'b0;
        dlf_in_pol = 1'b1;
        dlf_ext_data = 10'd0;
        cfg_ki = 255;
        cfg_kp = 4;
        cfg_target_code = DEFAULT_TARGET_DCO_CODE;
        cfg_target_tol = DEFAULT_TARGET_TOL_CODE;
        cfg_run_ns = 200000;
        cfg_low_init = 0;
        cfg_high_init = 1020;
        cfg_mmd_ratio = DEFAULT_MMD_RATIO;
        cfg_ref_half_ps = DEFAULT_REF_HALF_PS;
        cfg_allow_fail = 0;
        cfg_coarse_code = 5;
        pllo_edges = 0;
        clkdiv_edges = 0;

        if (!$value$plusargs("KI=%d", cfg_ki))
            cfg_ki = 255;
        if (!$value$plusargs("KP=%d", cfg_kp))
            cfg_kp = 4;
        if (!$value$plusargs("TARGET_CODE=%d", cfg_target_code))
            cfg_target_code = DEFAULT_TARGET_DCO_CODE;
        if (!$value$plusargs("TOL_CODE=%d", cfg_target_tol))
            cfg_target_tol = DEFAULT_TARGET_TOL_CODE;
        if (!$value$plusargs("RUN_NS=%d", cfg_run_ns))
            cfg_run_ns = 200000;
        if (!$value$plusargs("LOW_INIT=%d", cfg_low_init))
            cfg_low_init = 0;
        if (!$value$plusargs("HIGH_INIT=%d", cfg_high_init))
            cfg_high_init = 1020;
        if (!$value$plusargs("MMD_RATIO=%d", cfg_mmd_ratio))
            cfg_mmd_ratio = DEFAULT_MMD_RATIO;
        if (!$value$plusargs("REF_HALF_PS=%d", cfg_ref_half_ps))
            cfg_ref_half_ps = DEFAULT_REF_HALF_PS;
        if (!$value$plusargs("ALLOW_FAIL=%d", cfg_allow_fail))
            cfg_allow_fail = 0;
        if (!$value$plusargs("COARSE_CODE=%d", cfg_coarse_code))
            cfg_coarse_code = 5;

        ref_half_ns = cfg_ref_half_ps / 1000.0;
        ref_mhz = 1000000.0 / (2.0 * cfg_ref_half_ps);
        dlf_ki = cfg_ki[7:0];
        dlf_kp = cfg_kp[4:0];
        coarse_code = cfg_coarse_code[3:0];
        mmd_ratio = cfg_mmd_ratio[7:0];

        run_case("low-start", cfg_low_init[9:0], 1);
        run_case("high-start", cfg_high_init[9:0], 0);

        $display("PASS: PLL top behavioral acquisition test");
        $finish;
    end

endmodule

`default_nettype wire
