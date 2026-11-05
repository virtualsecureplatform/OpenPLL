`timescale 1ns/1ps
// Digital startup/CDC regression with a synthetic clock; no physical lock claim.
module tb_programmed400;
    reg refclk=0, pllout=1, reset_n=0, enabled=0, stall=0;
    reg [5:0] coarse=1;
    reg [7:0] seed=128, ki=4;
    reg [4:0] kp=0;
    reg polarity=1;
    wire oscillator_reset_n, ready, tracking, busy, failed, divided, detector_reset_n;
    wire [5:0] observed_coarse;
    wire [7:0] fine;
    wire [9:0] dlf;
    wire [46:0] coarse_therm;
    wire [254:0] fine_therm;
    integer passes=0, i, phase_index;
    always #20 refclk=~refclk;
    always #1.25 begin
        if(oscillator_reset_n && !stall) pllout=~pllout;
        else pllout=1;
    end
    IntegerPLL_ProgrammedCore dut (
        .REFCLK(refclk),.PLLOUT(pllout),.RESET_N(reset_n),.PLL_ENABLE(enabled),
        .STARTUP_COARSE(coarse),.STARTUP_FINE(seed),.STARTUP_INCREASING(polarity),
        .KI(ki),.KP(kp),.BBPD(2'b00),.OSC_RESET_N(oscillator_reset_n),
        .CONFIG_READY(ready),.TRACKING(tracking),.CONFIG_BUSY(busy),.FAILED(failed),
        .CLKDIV_RETIMED(divided),.BBPD_RESET_N(detector_reset_n),
        .COARSE_CODE(observed_coarse),.DCO_CODE(fine),.DLF_CODE(dlf),
        .COARSETHERMAL_CODE(coarse_therm),.DCO_THERM(fine_therm));

    task reset_case;
        input integer phase_ns;
        begin
            reset_n=0;enabled=0;stall=0;
            #3;
            if(oscillator_reset_n!==0 || tracking!==0 || detector_reset_n!==0)
                $fatal(1,"reset must assert with stopped clocks: osc=%b tracking=%b detector=%b state=%b",oscillator_reset_n,tracking,detector_reset_n,dut.startup.state);
            repeat(2) @(negedge refclk);
            #(phase_ns+1) reset_n=1;
        end
    endtask
    task await_ready;
        begin
            i=0;
            while(!ready && !failed && i<100) begin @(negedge refclk);i=i+1;end
            if(!ready || failed || tracking || fine!==seed || observed_coarse!==coarse)
                $fatal(1,"programmed open-loop startup failed seed=%0d state=%0d",seed,dut.startup.state);
            passes=passes+1;
        end
    endtask
    task await_tracking;
        begin
            i=0;
            while(!tracking && !failed && i<100) begin @(negedge refclk);i=i+1;end
            if(!tracking || failed || !detector_reset_n)
                $fatal(1,"loaded configuration did not enable tracking");
            repeat(20) @(negedge refclk);
            if(fine!==seed || !ready || busy || !tracking)
                $fatal(1,"zero-decision loop did not retain seed");
            passes=passes+1;
        end
    endtask
    task expect_failure;
        input integer max_cycles;
        begin
            i=0;
            while(!failed && i<max_cycles) begin @(negedge refclk);i=i+1;end
            if(!failed || oscillator_reset_n || tracking || detector_reset_n)
                $fatal(1,"failure did not stop oscillator and loop");
            repeat(5) @(negedge refclk);
            if(!failed) $fatal(1,"failure must remain sticky until reset");
            passes=passes+1;
        end
    endtask

    initial begin
        // Deliver an explicit reset edge after every observer is installed.
        reset_n=0;#1 reset_n=1;#1 reset_n=0;
        for(phase_index=0;phase_index<4;phase_index=phase_index+1) begin
            coarse=phase_index==3 ? 47 : phase_index;
            seed=phase_index==0 ? 8 : (phase_index==3 ? 247 : 128);
            polarity=phase_index[0];
            reset_case(phase_index*10);
            await_ready;
            // Open-loop readback and the physical thermometer preset agree.
            if(fine_therm !== ~({255{1'b1}} >> (255-seed)))
                $fatal(1,"fine thermometer ordering/polarity mismatch");
            enabled=1;await_tracking;
            // Check real divide-by-16 edge spacing, not just a status bit.
            @(posedge divided);
            begin : count_divider
                integer count;
                count=0;
                fork
                    begin repeat(16) begin @(posedge pllout);count=count+1;end end
                    begin @(posedge divided);#0.001;
                        if(count!=16) $fatal(1,"feedback divider is not sixteen");
                    end
                join
            end
            passes=passes+1;
            #0.3 enabled=0;#0.001;
            if(tracking || detector_reset_n || fine!==seed)
                $fatal(1,"disable failed to restore programmed seed immediately");
            await_ready;enabled=1;await_tracking;
            stall=1;#5;reset_n=0;#0.001;
            if(tracking || oscillator_reset_n || detector_reset_n)
                $fatal(1,"reset failed with stopped oscillator");
            reset_case(phase_index*10);await_ready;enabled=1;await_tracking;
        end
        // A stopped oscillator must time out without a DCO-domain clock.
        coarse=1;seed=128;reset_case(0);stall=1;
        expect_failure(530);stall=0;
        // All configuration limits and a changed live bundle are rejected.
        coarse=48;reset_case(0);expect_failure(12);
        coarse=1;seed=7;reset_case(0);expect_failure(12);
        seed=248;reset_case(0);expect_failure(12);
        seed=128;ki=0;reset_case(0);expect_failure(12);
        ki=4;reset_case(0);await_ready;seed=129;expect_failure(12);
        seed=128;reset_case(0);await_ready;enabled=1;await_tracking;
        polarity=~polarity;expect_failure(12);
        $display("PASS: programmed400 digital startup controls checks=%0d; no physical lock qualification",passes);
        $finish;
    end
    initial begin #100000;$fatal(1,"regression timeout");end
endmodule
