// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module tb_pll_100mhz_acquisition;
    integer seed_code = 93;
    integer diagnostic_coarse = -1;
    integer diagnostic_ki = -1;
    integer diagnostic_kp = -1;
    wire [7:0] applied_ki = diagnostic_ki < 0 ? dlf_ki : diagnostic_ki;
    wire [4:0] applied_kp = diagnostic_kp < 0 ? dlf_kp : diagnostic_kp;
    wire [5:0] applied_coarse = diagnostic_coarse < 0 ? coarse_code : diagnostic_coarse;
    real phase_ns = 0.0;
    real duration_ns = 80000.0;
    string trace_path;
    integer trace_fd;
    reg logging = 0;
    wire [9:0] seed_word = seed_code << 2;
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
    wire [4:0] dlf_kp;
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
        .DLF_Ext_Data(seed_word),
        .DLF_KI(applied_ki),
        .DLF_KP(applied_kp),
        .COARSEBINARY_CODE(applied_coarse),
        .MMDCLKDIV_RATIO(mmd_ratio),
        .PLLOUT(pllout),
        .PLLOUT_DIV(pllout_div),
        .CLKDIV_RETIMED(clkdiv_retimed),
        .BBPD_CODE(bbpd_code),
        .DCO_CODE(dco_code),
        .DLF_CODE(dlf_code)
    );


    initial begin
        if (!$value$plusargs("KI=%d", diagnostic_ki)) diagnostic_ki = -1;
        if (!$value$plusargs("KP=%d", diagnostic_kp)) diagnostic_kp = -1;
        if (diagnostic_ki < -1 || diagnostic_ki > 255 || diagnostic_kp < -1 || diagnostic_kp > 31)
            $fatal(1, "Invalid diagnostic gains");
        if (!$value$plusargs("COARSE=%d", diagnostic_coarse)) diagnostic_coarse = -1;
        if (diagnostic_coarse < -1 || diagnostic_coarse > 63)
            $fatal(1, "Invalid diagnostic coarse code");
        if (!$value$plusargs("SEED=%d", seed_code)) seed_code = 93;
        if (!$value$plusargs("PHASE_NS=%f", phase_ns)) phase_ns = 0.0;
        if (!$value$plusargs("DURATION_NS=%f", duration_ns)) duration_ns = 80000.0;
        if (!$value$plusargs("TRACE=%s", trace_path)) trace_path = "acquisition.csv";
        if (seed_code < 0 || seed_code > 255 || phase_ns < 0 || phase_ns >= 40)
            $fatal(1, "Invalid diagnostic seed or phase");
        trace_fd = $fopen(trace_path, "w");
        if (!trace_fd) $fatal(1, "Cannot open trace");
        $fdisplay(trace_fd, "event,time_ns,code,bbpd");
        ref_clk = 0;
        #(phase_ns);
        forever #20 ref_clk = ~ref_clk;
    end

    always @(posedge ref_clk)
        if (logging) $fdisplay(trace_fd, "REF,%0.3f,%0d,%0d", $realtime, dco_code, bbpd_code);
    always @(posedge clkdiv_retimed)
        if (logging) $fdisplay(trace_fd, "DIV,%0.3f,%0d,%0d", $realtime, dco_code, bbpd_code);
    always @(posedge pllout)
        if (logging) $fdisplay(trace_fd, "OUT,%0.3f,%0d,%0d", $realtime, dco_code, bbpd_code);

    // Diagnostic overrides affect preset data and optionally DCO band/gains.
    // The production controller, digital core, divider and DLF are unchanged.
    initial begin
        reset_n = 0;
        pll_enable = 0;
        feedback_divider = 4;
        #200 reset_n = 1;
        #80 pll_enable = 1;
        wait (tracking === 1'b1);
        logging = 1;
        $display("START seed=%0d phase_ns=%0.3f code=%0d time_ns=%0.3f",
                 seed_code, phase_ns, dco_code, $realtime);
        #(duration_ns);
        logging = 0;
        $fclose(trace_fd);
        $display("DONE code=%0d", dco_code);
        $finish;
    end
    initial begin
        #200000;
        $fatal(1, "Tracking or simulation timeout");
    end
endmodule
`default_nettype wire
