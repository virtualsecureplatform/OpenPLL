// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
// Independent ideal-cell test of enable decoding and output division only.
module tb_strength_dco_controls;
    reg reset_n=1;
    reg [46:0] coarse=0;
    wire out;
    wire [62:0] drive_enable;
    genvar g;
    generate for(g=0;g<63;g=g+1) begin: observe
        assign drive_enable[g]=dut.gen_drive[g].osc_driver.TE;
    end endgenerate
    integer code,bit_index,driver,enabled,edges=0,cycle;
    IntegerPLL_DCO_STRENGTH_DIV dut(.RESET_N(reset_n),
        .COARSETHERMAL_CODE(coarse),.DCO_THERM({255{1'b1}}),.PLLOUT(out));
    always @(posedge out) edges=edges+1;
    function integer expected;
        input integer setting;
        begin case(setting)
            0:expected=63;1:expected=53;2:expected=44;3:expected=37;
            4:expected=31;5:expected=26;6:expected=22;7:expected=18;
            8:expected=15;9:expected=13;10:expected=11;default:expected=9;
        endcase end
    endfunction
    initial begin
        force dut.osc_node=0;
        for(code=0;code<48;code=code+1) begin
            reset_n=0;
            for(bit_index=0;bit_index<47;bit_index=bit_index+1)
                coarse[bit_index]=(bit_index<code);
            #1;
            if(drive_enable!==63'b0) $fatal(1,"reset leaves a parallel driver enabled");
            reset_n=1;#1;
            enabled=0;
            for(driver=0;driver<63;driver=driver+1) begin
                if(drive_enable[driver]===1'b1) enabled=enabled+1;
                else if(drive_enable[driver]!==1'b0) $fatal(1,"unknown enable");
            end
            if(enabled!=expected(code%12)) $fatal(1,"wrong strength for coarse=%0d",code);
            edges=0;
            for(cycle=0;cycle<64;cycle=cycle+1) begin
                force dut.osc_node=1;#5;force dut.osc_node=0;#5;
            end
            if(edges!=64/(1<<(code/12))) $fatal(1,"wrong divider for coarse=%0d edges=%0d",code,edges);
        end
        $display("strength_dco_controls=pass all_48_codes");$finish;
    end
endmodule
module sky130_fd_sc_hd__nand2_1(input A,B,output Y);assign Y=~(A&B);endmodule
module sky130_fd_sc_hd__inv_1(input A,output Y);assign Y=~A;endmodule
module sky130_fd_sc_hd__and2_4(input A,B,output X);assign X=A&B;endmodule
module sky130_fd_sc_hd__buf_1(input A,output X);assign X=A;endmodule
module sky130_fd_sc_hd__mux2_1(input A0,A1,S,output X);assign X=S?A1:A0;endmodule
module sky130_fd_sc_hd__mux2_4(input A0,A1,S,output X);assign X=S?A1:A0;endmodule
module sky130_fd_sc_hd__einvp_1(input A,TE,output Z);assign Z=TE?~A:1'bz;endmodule
module sky130_fd_sc_hd__dfrtp_1(input CLK,D,RESET_B,output reg Q);
    always @(posedge CLK or negedge RESET_B) if(!RESET_B) Q<=0;else Q<=D;
endmodule
