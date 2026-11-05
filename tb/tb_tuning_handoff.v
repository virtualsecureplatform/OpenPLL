// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
module tb_tuning_handoff;
    parameter integer APPLY_CYCLES=3;
    reg refclk=0,dco=0,reset_n=1,running=1;
    reg [33:0] command=0;
    wire [33:0] received;
    wire applied;
    integer tick=0,last_capture=-1000,trial,deadline;
    reg previous_ack=0;
    reg [33:0] captured;
    reg [31:0] random_state=32'h93712456;
    IntegerPLL_TuningHandoff #(.WIDTH(34),.APPLY_CYCLES(APPLY_CYCLES)) dut(
        .REFCLK(refclk),.DCOCLK(dco),.REF_RESET_N(reset_n),
        .DCO_RESET_N(reset_n),.COMMAND(command),
        .APPLIED_COMMAND(received),.APPLIED(applied));
    always #20 refclk=~refclk;
    always #1.111 if(running) dco=~dco;
    always @(posedge dco) begin
        tick=tick+1;
        if(reset_n && dut.capture_pending) begin
            last_capture=tick;captured=dut.payload;
        end
        #0.001;
        if(!reset_n) previous_ack=0;
        else begin
            if(tick==last_capture && received!==captured)
                $fatal(1,"payload capture was not atomic");
            if(dut.acknowledge!==previous_ack && tick-last_capture<APPLY_CYCLES)
                $fatal(1,"acknowledged before consumer apply interval");
            previous_ack=dut.acknowledge;
        end
    end
    task settle;
        begin
            deadline=0;
            while(!applied) begin
                @(posedge refclk);#0.002;
                deadline=deadline+1;
                if(deadline>30) $fatal(1,"handoff did not acknowledge latest command");
            end
            if(received!==command) $fatal(1,"acknowledged wrong command");
        end
    endtask
    initial begin
        #0.1;reset_n=0;#4;reset_n=1;
        settle(); // Initial zero payload must transfer, too.
        for(trial=0;trial<200;trial=trial+1) begin
            @(negedge refclk);
            random_state=random_state*32'd1664525+32'd1013904223;
            command={trial[1:0],random_state};
            #0.001;if(applied) $fatal(1,"stale acknowledgement on command change");
            settle();
        end
        @(negedge dco);running=0;
        @(negedge refclk);command=34'h3ffffffff;
        repeat(8) begin
            @(negedge refclk);command=command-1'b1;
            #0.001;if(applied) $fatal(1,"acknowledged with stopped destination");
        end
        running=1;settle();
        // Reset with a transfer outstanding, then recover the current bundle.
        @(negedge refclk);command=34'h123456789;
        #3;reset_n=0;#0.001;
        if(applied || received!==0) $fatal(1,"reset did not withdraw transfer");
        #7;previous_ack=0;reset_n=1;settle();
        $display("tuning_handoff=pass apply_cycles=%0d",APPLY_CYCLES);$finish;
    end
    initial begin #100000;$fatal(1,"handoff watchdog");end
endmodule
