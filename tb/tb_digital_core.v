// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

module tb_digital_core;

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

    integer start_code;
    integer inc_code;
    integer dec_code;
    integer load_count;
    integer wait_cycles;

    function integer count255;
        input [254:0] value;
        integer i;
        begin
            count255 = 0;
            for (i = 0; i < 255; i = i + 1)
                count255 = count255 + value[i];
        end
    endfunction

    task check_first_bbpd_decision;
        input [1:0] first_code;
        input [1:0] expected_code;
        begin
            dlf_en = 1'b0;
            bbpd = 2'b00;
            @(posedge dut.dlf_update_edge);
            #1;
            repeat (1) @(posedge pllo);
            #1;
            repeat (1) @(posedge pllo);
            dlf_en = 1'b1;
            repeat (2) @(posedge pllo);
            bbpd = first_code;
            repeat (2) @(posedge pllo);
            bbpd = 2'b11;
            repeat (2) @(posedge pllo);
            bbpd = 2'b00;
            @(posedge dut.dlf_update_edge);
            repeat (1) @(posedge pllo);
            #1;
            if (dut.bbpd_decision !== expected_code) begin
                $display("FAIL: first BBPD decision lost: first=%b decision=%b",
                         first_code, dut.bbpd_decision);
                $fatal(1);
            end
        end
    endtask

    task send_bbpd_event;
        input [1:0] first_code;
        begin
            bbpd = 2'b00;
            repeat (1) @(posedge pllo);
            #1;
            bbpd = first_code;
            repeat (1) @(posedge pllo);
            #1;
            bbpd = 2'b11;
            repeat (1) @(posedge pllo);
            #1;
            bbpd = 2'b00;
        end
    endtask

    task send_bbpd_until_update;
        input [1:0] first_code;
        begin
            send_bbpd_event(first_code);
            @(posedge dut.dlf_update_edge);
            #1;
        end
    endtask

    IntegerPLL_DigitalCore dut (
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

`ifdef DEBUG_BBPD_LATCH
    always @(posedge pllo) begin
        $display("DBG t=%0t clkdiv=%b edge=%b bbpd=%b seen=%b next=%b decision=%b",
                 $time, clkdiv_retimed, dut.dlf_update_edge, bbpd,
                 dut.bbpd_seen, dut.bbpd_seen_next, dut.bbpd_decision);
    end
`endif

    initial begin
        reset_n = 1'b0;
        bbpd = 2'b00;
        dlf_en = 1'b0;
        dlf_clear = 1'b0;
        dlf_override = 1'b0;
        dlf_in_pol = 1'b1;
        dlf_ext_data = 10'd512;
        dlf_ki = 8'd32;
        dlf_kp = 8'd0;
        coarse_code = 4'd5;
        mmd_ratio = 8'd10;

        repeat (4) @(posedge pllo);
        reset_n = 1'b1;
        repeat (4) @(posedge pllo);

        dlf_clear = 1'b1;
        repeat (2) @(posedge clkdiv_retimed);
        dlf_clear = 1'b0;
        repeat (2) @(posedge clkdiv_retimed);

        if (coarse_therm !== 15'b000000000011111) begin
            $display("FAIL: coarse thermometer decode is %b", coarse_therm);
            $fatal(1);
        end

        check_first_bbpd_decision(2'b10, 2'b10);
        check_first_bbpd_decision(2'b01, 2'b01);

        dlf_en = 1'b1;
        dlf_ki = 8'd0;
        dlf_kp = 8'd4;
        wait_cycles = 0;
        while ((dlf_code !== 10'd516) && (wait_cycles < 8)) begin
            send_bbpd_until_update(2'b10);
            wait_cycles = wait_cycles + 1;
        end
        if (dlf_code !== 10'd516) begin
            $display("FAIL: DLF KP scaling failed: code=%0d", dlf_code);
            $fatal(1);
        end

        dlf_en = 1'b0;
        dlf_ki = 8'd32;
        dlf_kp = 8'd0;
        bbpd = 2'b00;
        #1;

        start_code = dlf_code;
        dlf_en = 1'b1;
        for (wait_cycles = 0; wait_cycles < 20; wait_cycles = wait_cycles + 1)
            send_bbpd_until_update(2'b10);
        inc_code = dlf_code;

        if (inc_code <= start_code) begin
            $display("FAIL: DLF did not increase: start=%0d inc=%0d",
                     start_code, inc_code);
            $fatal(1);
        end

        for (wait_cycles = 0; wait_cycles < 20; wait_cycles = wait_cycles + 1)
            send_bbpd_until_update(2'b01);
        dec_code = dlf_code;

        if (dec_code >= inc_code) begin
            $display("FAIL: DLF did not decrease: inc=%0d dec=%0d",
                     inc_code, dec_code);
            $fatal(1);
        end

        dlf_override = 1'b1;
        dlf_ext_data = 10'd123;
        repeat (2) @(posedge clkdiv_retimed);
        if (dlf_code !== 10'd123) begin
            $display("FAIL: DLF override failed: code=%0d", dlf_code);
            $fatal(1);
        end

        if (dco_code !== dlf_code[9:2]) begin
            $display("FAIL: DCO code decode failed: dco_code=%0d dlf_code=%0d",
                     dco_code, dlf_code);
            $fatal(1);
        end

        dlf_ext_data = 10'd0;
        repeat (2) @(posedge clkdiv_retimed);
        load_count = count255(dco_therm);
        if (dco_code !== 8'd0 || load_count !== 255) begin
            $display("FAIL: DCO minimum code polarity failed: dco_code=%0d loads=%0d",
                     dco_code, load_count);
            $fatal(1);
        end

        dlf_ext_data = 10'd1020;
        repeat (2) @(posedge clkdiv_retimed);
        load_count = count255(dco_therm);
        if (dco_code !== 8'd255 || load_count !== 0) begin
            $display("FAIL: DCO maximum code polarity failed: dco_code=%0d loads=%0d",
                     dco_code, load_count);
            $fatal(1);
        end

        $display("PASS: digital core smoke test");
        $finish;
    end

endmodule

`default_nettype wire
