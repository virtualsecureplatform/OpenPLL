// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
module tb_mmd_countdown;
    parameter integer REGISTER_CONFIG=1;
    reg clk=0,reset_n=1;
    reg [4:0] ratio=2;
    wire divided;
    integer cycle=0,setting,trial,burst,sample,period,last_rise,rises;
    reg previous;
    reg [31:0] random_state=32'h18235476;
    // Independent period/high-time model checks every live-change cycle,
    // including transients before the stable-period checks below.
    integer model_config, model_remaining, model_high;
    reg model_raw, model_divided;
    wire [31:0] model_ratio = REGISTER_CONFIG ? model_config : (ratio<2 ? 2 : ratio);
    always @(posedge clk or negedge reset_n) begin
        if(!reset_n) begin
            model_config<=2;model_remaining<=0;model_high<=0;
            model_raw<=0;model_divided<=0;
        end else begin
            model_config<=ratio<2 ? 2 : ratio;
            model_divided<=model_raw;
            if(model_remaining==0) begin
                model_remaining<=model_ratio-1;
                model_high<=model_ratio/2-1;
                model_raw<=1;
            end else begin
                model_remaining<=model_remaining-1;
                model_raw<=model_high!=0;
                if(model_high!=0) model_high<=model_high-1;
            end
        end
    end
    always @(posedge clk) begin
        #0.002;
        if(divided!==model_divided)
            $fatal(1,"live countdown mismatch cycle=%0d ratio=%0d",cycle,ratio);
    end
    IntegerPLL_MMD_Retimer #(.RATIO_WIDTH(5),.REGISTER_CONFIG(REGISTER_CONFIG),.COUNTDOWN(1)) dut(
        .DIV_IN(clk),.RESET_N(reset_n),.CLK_DIV_RATIO(ratio),.CLKDIV_RETIMED(divided));
    always #1.111 clk=~clk;
    always @(posedge clk) cycle=cycle+1;
    task check_period;
        input integer value;
        begin
            @(negedge clk);ratio=value;
            period=value<2 ? 2 : value;
            // The old period is at most 31 clocks. Wait through its wrap
            // and a complete new period after the registered configuration.
            repeat(70) @(negedge clk);
            last_rise=-1;rises=0;previous=divided;
            for(sample=0;sample<4*period+2;sample=sample+1) begin
                @(posedge clk);#0.002;
                if(divided && !previous) begin
                    if(last_rise>=0 && cycle-last_rise!=period)
                        $fatal(1,"countdown period ratio=%0d actual=%0d",value,cycle-last_rise);
                    last_rise=cycle;rises=rises+1;
                end
                if(!divided && previous && last_rise>=0 && cycle-last_rise!=period/2)
                    $fatal(1,"countdown duty ratio=%0d high_clocks=%0d",value,cycle-last_rise);
                previous=divided;
            end
            if(rises<3) $fatal(1,"missing countdown edges");
        end
    endtask
    initial begin
        #0.1;reset_n=0;#0.1;reset_n=1;
        for(setting=0;setting<32;setting=setting+1) check_period(setting);
        for(trial=0;trial<200;trial=trial+1) begin
            for(burst=0;burst<20;burst=burst+1) begin
                @(negedge clk);
                random_state=random_state*32'd1664525+32'd1013904223;
                ratio=random_state[4:0];
                if(trial%7==0 && burst==10) begin
                    reset_n=0;#0.001;
                    if(divided!==0 || dut.counter!==0 || !dut.gen_countdown.reload_pending)
                        $fatal(1,"countdown reset failed");
                    reset_n=1;
                end
            end
            check_period(random_state[4:0]);
        end
        $display("mmd_countdown=pass ratios=32 burst_changes=4000 registered_config=%0d",REGISTER_CONFIG);$finish;
    end
    initial begin #1000000;$fatal(1,"countdown watchdog");end
endmodule
