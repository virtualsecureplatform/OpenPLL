// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
module tb_mmd_registered_config;
    reg clk=0, reset_n=1;
    reg [7:0] ratio=2, delayed_ratio=2;
    wire actual, reference;
    integer cycle=0, setting, period, last_rise, rises, sample;
    reg previous=0;
    reg [31:0] random_state=32'h81429357;
    IntegerPLL_MMD_Retimer #(.REGISTER_CONFIG(1)) dut(
        .DIV_IN(clk),.RESET_N(reset_n),.CLK_DIV_RATIO(ratio),.CLKDIV_RETIMED(actual));
    IntegerPLL_MMD_Retimer model(
        .DIV_IN(clk),.RESET_N(reset_n),.CLK_DIV_RATIO(delayed_ratio),.CLKDIV_RETIMED(reference));
    always #1.111 clk=~clk;
    always @(posedge clk or negedge reset_n)
        if(!reset_n) delayed_ratio<=2;
        else delayed_ratio<=ratio;
    always @(posedge clk) begin
        cycle=cycle+1;
        #0.001;
        if(reset_n && actual!==reference)
            $fatal(1,"registered configuration differs from delayed legacy ratio");
    end
    initial begin
        #0.1;reset_n=0;#0.1;reset_n=1;
        for(setting=0;setting<256;setting=setting+1) begin
            @(negedge clk);ratio=setting;
            period=setting<2 ? 2 : setting;
            repeat(2*period+4) @(negedge clk);
            last_rise=-1;rises=0;previous=actual;
            for(sample=0;sample<3*period+2;sample=sample+1) begin
                @(posedge clk);#0.002;
                if(actual && !previous) begin
                    if(last_rise>=0 && cycle-last_rise!=period)
                        $fatal(1,"wrong output period ratio=%0d actual=%0d",setting,cycle-last_rise);
                    last_rise=cycle;rises=rises+1;
                end
                previous=actual;
            end
            if(rises<3) $fatal(1,"missing divided edges");
        end
        for(sample=0;sample<1000;sample=sample+1) begin
            @(negedge clk);
            random_state=random_state*32'd1664525+32'd1013904223;
            ratio=random_state[7:0];
            if(sample%127==0) begin
                reset_n=0;#0.001;
                if(actual!==0) $fatal(1,"reset did not withdraw divided clock");
                reset_n=1;
            end
        end
        repeat(5) @(negedge clk);
        $display("mmd_registered_config=pass ratios=256 live_changes=1000");$finish;
    end
    initial begin #500000;$fatal(1,"divider watchdog");end
endmodule
