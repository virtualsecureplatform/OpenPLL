// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1fs
module tb_bbpd_event_cdc;
    parameter integer RATIO=4;
    parameter integer SEPARATE_CAPTURE=0;
    reg independent_test=0, independent_capture=0;
    // Start capture ungated so the explicit global reset edge also reaches
    // the pulse-clocked flop models before either pulse clock has run.
    reg pll=0, reset_n=1, enable=1, clear=0;
    reg [1:0] bbpd=0;
    wire divided;
    wire [7:0] code;
    integer phase_index, pulses;
    real phase, fast_period=1000.0/(25.0*RATIO);
    IntegerPLL_DigitalCore #(.DLF_FRAC_WIDTH(2),.DLF_PROP_RAIL_GUARD(1),
        .MMD_REGISTER_CONFIG(1),.MMD_RATIO_WIDTH(5),.MMD_COUNTDOWN(1),
        .SYNCHRONIZE_RESETS(1),.REGISTER_BBPD_DECISION(1),.BBPD_EVENT_CDC(1),
        .BBPD_CAPTURE_INDEPENDENT(SEPARATE_CAPTURE)) dut(
        .BBPD_CAPTURE_EN(independent_test ? independent_capture : (enable && !clear)),
        .PLLOUT(pll),.RESET_N(reset_n),.BBPD(bbpd),.DLF_En(enable),
        .DLF_Clear(clear),.DLF_Ext_Override(1'b0),.DLF_IN_POL(1'b1),
        .DLF_Ext_Data(10'd512),.DLF_KI(8'd16),.DLF_KP(5'd0),
        .COARSEBINARY_CODE(6'd0),.MMDCLKDIV_RATIO(RATIO[7:0]),
        .CLKDIV_RETIMED(divided),.DCO_CODE(code));
    always #(fast_period/2.0) pll=~pll;
    task settle_seed;
        begin
            clear=1;enable=1;bbpd=0;
            repeat(8) @(posedge divided);
            #0.001;clear=0;
            repeat(8) @(posedge divided);
            #0.001;if(code!==128) $fatal(1,"seed/pending event was not cleared code=%0d dlf=%0d decision=%b pipe=%b reset=%b",code,dut.DLF_CODE,dut.bbpd_decision,dut.gen_event_cdc.up_pipe,dut.dlf_reset_n);
        end
    endtask
    task stream;
        input [1:0] direction;
        begin
            @(posedge divided);#(phase);
            for(pulses=0;pulses<16;pulses=pulses+1) begin
                bbpd=direction;#0.05;bbpd=0;#39.95;
            end
            repeat(8) @(posedge divided);#0.001;
        end
    endtask
    initial begin
        #0.1;reset_n=0;#25;reset_n=1;
        for(phase_index=0;phase_index<8;phase_index=phase_index+1) begin
            case(phase_index)
                0:phase=0.001;
                1:phase=0.05;
                2:phase=fast_period-0.01;
                3:phase=fast_period+0.01;
                4:phase=2*fast_period-0.01;
                5:phase=2*fast_period+0.01;
                6:phase=35.001;
                default:phase=39.99;
            endcase
            settle_seed();stream(2'b10);
            if(code!==144) $fatal(1,"UP events lost/duplicated ratio=%0d phase=%f code=%0d",RATIO,phase,code);
            stream(2'b01);
            if(code!==128) $fatal(1,"DN events lost/duplicated ratio=%0d phase=%f code=%0d",RATIO,phase,code);
            stream(2'b11);
            if(code!==128) $fatal(1,"simultaneous inputs produced a decision");
        end
        // Withdraw capture with a toggle pending in the receive pipeline.
        @(negedge pll);bbpd=2'b10;#0.05;bbpd=0;enable=0;
        repeat(8) @(posedge divided);#0.001;enable=1;
        repeat(8) @(posedge divided);#0.001;
        if(code!==128) $fatal(1,"disabled event replayed after re-enable");
        // Withdraw for less than one oscillator period after the first
        // receive stage has sampled a pulse, then re-arm without a new pulse.
        @(negedge pll);bbpd=2'b10;#0.05;bbpd=0;
        @(posedge pll);#0.001;enable=0;#1;enable=1;
        repeat(8) @(posedge divided);#0.001;
        if(code!==128) $fatal(1,"stale receive-stage sample replayed after short withdrawal");
        @(negedge pll);bbpd=2'b10;#0.05;bbpd=0;reset_n=0;#0.001;
        if(code!==0 || dut.gen_event_cdc.up_pipe!==0 || dut.gen_event_cdc.dn_pipe!==0)
            $fatal(1,"pending-event reset did not assert");
        #23;reset_n=1;settle_seed();
        if(SEPARATE_CAPTURE!=0) begin
            settle_seed;
            independent_test=1;independent_capture=1;clear=1;
            repeat(8) @(posedge divided);
            @(negedge pll);bbpd=2'b10;#0.05;bbpd=0;
            repeat(8) @(posedge pll);#0.001;
            if(dut.bbpd_up_event_toggle!==1'b1)
                $fatal(1,"fine clear incorrectly gates independent capture");
            independent_capture=0;clear=0;#0.001;
            if(dut.bbpd_up_event_toggle!==0 || dut.bbpd_receive_ready!==0)
                $fatal(1,"independent capture withdrawal failed");
            @(negedge pll);bbpd=2'b10;#0.05;bbpd=0;
            repeat(8) @(posedge divided);#0.001;
            if(dut.bbpd_up_event_toggle!==0 || code!==128)
                $fatal(1,"disabled capture accepted event with fine loop enabled");
            independent_capture=1;repeat(8) @(posedge divided);#0.001;
            if(code!==128) $fatal(1,"independent capture replays stale event");
        end
        $display("bbpd_event_cdc=pass ratio=%0d phases=8 pulses=384 width_ns=0.05",RATIO);
        $finish;
    end
    initial begin #100000;$fatal(1,"event CDC watchdog");end
endmodule
