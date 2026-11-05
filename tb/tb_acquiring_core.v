// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
module tb_acquiring_core;
    parameter integer DLF_UPDATE_ON_PLLOUT=0;
    reg refclk=0,dco=0,reset_n=1,enable=0,running=1;
    reg [4:0] divider=4;
    reg [1:0] bbpd=0;
    wire [5:0] coarse;
    wire [7:0] code;
    wire [9:0] dlf;
    wire divided,bbpd_reset,tracking,busy,failed;
    wire [46:0] coarse_therm;
    wire [254:0] therm;
    real phase=7.0,started,scale=1.0;
    reg [47:0] seen=0;
    IntegerPLL_AcquiringCore #(.DLF_UPDATE_ON_PLLOUT(DLF_UPDATE_ON_PLLOUT)) dut(
        .REFCLK(refclk),.PLLOUT(dco),.RESET_N(reset_n),.PLL_ENABLE(enable),
        .FEEDBACK_DIVIDER(divider),.BBPD(bbpd),.KI(8'd64),.KP(5'd0),
        .CLKDIV_RETIMED(divided),.BBPD_RESET_N(bbpd_reset),.TRACKING(tracking),
        .CONFIG_BUSY(busy),.FAILED(failed),.COARSE_CODE(coarse),.DCO_CODE(code),
        .DLF_CODE(dlf),.COARSETHERMAL_CODE(coarse_therm),.DCO_THERM(therm));
    always #20 refclk=~refclk;
    function real mhz;
        input [5:0] band;
        input [7:0] fine;
        begin
            case(band)
                17:mhz=104.0-fine*8.0/255.0;
                6:mhz=248.0+fine*4.0/255.0;
                4:mhz=297.0+fine*6.0/255.0;
                2:mhz=396.0+fine*8.0/255.0;
                0:mhz=445.0+fine*10.0/255.0;
                1:mhz=100.0;
                default:mhz=650.0+band*10.0+fine*0.02;
            endcase
        end
    endfunction
    initial begin
        if($value$plusargs("PHASE_NS=%f",phase)) begin end
        #(phase);
        forever begin
            #(500.0/(mhz(coarse,code)*scale));
            if(running) dco=~dco;
        end
    end
    always @(posedge refclk) if(enable&&!tracking) seen[coarse]<=1;
    // TUNING_APPLIED must include the actual fine-clock consumer, not just
    // a fast-domain copy of its bundle.
    always @(posedge refclk) begin
        #0.001;
        if(enable && !tracking && dut.applied && code!==dut.fine_seed)
            $fatal(1,"tuning acknowledged before fine-clock seed load");
    end
    always @(posedge tracking) begin
        if(dut.local_coarse!==coarse || dut.fine_command[33:28]!==coarse)
            $fatal(1,"tracking released with stale coarse bundle");
        if(code<8 || code>247 || !bbpd_reset || busy)
            #0.001; // Permit continuous assignments to settle in this slot.
        if(code<8 || code>247 || !bbpd_reset || busy)
            $fatal(1,"fine loop released without loaded seed");
    end
    task acquire;
        input [4:0] ratio;
        input [5:0] expected;
        reg [7:0] seed_code;
        begin
            @(negedge refclk);divider=ratio;seen=0;started=$realtime;
            #1;if(tracking || bbpd_reset) $fatal(1,"stale handoff on mode change");
            wait(tracking || failed);
            #1;
            if(failed || coarse!=expected || seen!==48'hffffffffffff)
                $fatal(1,"integrated scan failed ratio=%0d band=%0d",ratio,coarse);
            if($realtime-started>180000 || code<8 || code>247)
                $fatal(1,"handoff deadline or headroom failed");
            if(mhz(coarse,code)<ratio*25.0*0.99 || mhz(coarse,code)>ratio*25.0*1.01)
                $fatal(1,"seed outside capture neighborhood");
            $display("integrated ratio=%0d band=%0d code=%0d elapsed_ns=%0.3f",ratio,coarse,code,$realtime-started);
            // Exercise actual BBPD-event capture and transferred gain/polarity.
            seed_code=code;
            @(negedge dco);bbpd=2'b10;
            @(negedge dco);bbpd=0;
            repeat(8) @(posedge refclk);
            #1;
            // KI=64, two accumulator fractional bits, and two bits between
            // DLF_CODE and DCO_CODE produce exactly four fine-code steps.
            // Check magnitude as well as polarity to reject duplicate events.
            if((expected==17 && code!==seed_code-8'd4) ||
               (expected!=17 && code!==seed_code+8'd4))
                $fatal(1,"fine decision lost/duplicated or gain/polarity incorrect seed=%0d actual=%0d",seed_code,code);
            @(negedge dco);bbpd=2'b01;
            @(negedge dco);bbpd=0;
            repeat(8) @(posedge refclk);
            #1;if(code!=seed_code) $fatal(1,"opposite BBPD event did not restore fine code");
            #1000;
        end
    endtask
    initial begin
        #1;reset_n=0;#100;reset_n=1;enable=1;
        acquire(4,17);acquire(10,6);acquire(12,4);acquire(16,2);acquire(18,0);
        running=0;
        wait(!tracking);#1;
        if(bbpd_reset) $fatal(1,"BBPD active with stopped oscillator");
        wait(failed);
        // A stopped destination must assert reset immediately and retain
        // reset after the external release until its own clock resumes.
        #3;reset_n=0;#1;
        if(code!==0 || divided!==0 || tracking!==0 || dut.fine_reset_n!==0)
            $fatal(1,"stopped-domain reset did not assert");
        #17;reset_n=1;#100;
        if(code!==0 || tracking!==0 || dut.fine_reset_n!==0)
            $fatal(1,"stopped-domain reset released without clock");
        running=1;wait(tracking);#1000;
        enable=0;#1;
        if(tracking || bbpd_reset) $fatal(1,"disable did not withdraw tracking");
        divider=20;enable=1;#2000;
        if(tracking || bbpd_reset) $fatal(1,"retired 500 MHz divider accepted");
        enable=0;#1;divider=3;enable=1;#2000;
        if(tracking || bbpd_reset) $fatal(1,"invalid mode accepted");
        // Reset during an outstanding transfer must recover both CDC domains.
        divider=4;#75;reset_n=0;#27;reset_n=1;
        wait(tracking);#1000;
        started=$realtime;scale=0.97;
        wait(!tracking);wait(tracking);#1;
        if($realtime-started>170000) $fatal(1,"reacquisition leaves insufficient lock-validation budget");
        $display("integrated frequency-disturbance handoff_ns=%0.3f",$realtime-started);
        $display("acquiring_core=pass");$finish;
    end
    initial begin #2000000;$fatal(1,"integrated acquisition timeout");end
endmodule
