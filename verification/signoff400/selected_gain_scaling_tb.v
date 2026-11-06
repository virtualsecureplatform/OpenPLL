`timescale 1ns/1ps
module selected_gain_scaling_tb;
reg clk=0, reset_n=0, clear=0;
reg [7:0] ki=0;
reg [4:0] kp=0;
reg [1:0] bbpd=0;
wire [9:0] code;
integer checks=0;
IntegerPLL_DLF #(.FRAC_WIDTH(2),.PROP_RAIL_GUARD(1)) dut(
 .CLK(clk),.RESET_N(reset_n),.DLF_En(1'b1),.DLF_Clear(clear),
 .DLF_Ext_Override(1'b0),.DLF_Update(1'b1),.DLF_IN_POL(1'b1),
 .DLF_Ext_Data(10'd916),.DLF_KI(ki),.DLF_KP(kp),.BBPD(bbpd),
 .DLF_CODE(code));
task tick; begin #5;clk=1;#1;clk=0;#4;end endtask
task seed; begin
 reset_n=0;bbpd=0;kp=0;ki=0;tick;
 reset_n=1;clear=1;tick;clear=0;#1;
 if(code!==916 || dut.integ_acc!==3664) $fatal(1,"seed mapping");
end endtask
task integral_case;
 input integer gain, direction, count;
 integer i, expected;
 begin
 seed;ki=gain;bbpd=(direction==1)?2'b10:2'b01;
 for(i=1;i<=count;i=i+1) begin
  tick;expected=3664+direction*gain*i;
  if(dut.integ_acc!==expected || code!==(expected/4) || code[9:2]!==(expected/16))
   $fatal(1,"gain=%0d dir=%0d update=%0d acc=%0d expected=%0d",gain,direction,i,dut.integ_acc,expected);
  checks=checks+1;
 end
 end
endtask
initial begin
 integral_case(1,1,32);integral_case(1,-1,32);
 integral_case(4,1,16);integral_case(4,-1,16);
 integral_case(16,1,8);integral_case(16,-1,8);
 seed;kp=4;bbpd=2'b10;#1;
 if(code[9:2]!==230 || dut.integ_acc!==3664) $fatal(1,"positive proportional scaling");
 bbpd=2'b01;#1;
 if(code[9:2]!==228 || dut.integ_acc!==3664) $fatal(1,"negative proportional scaling");
 bbpd=0;#1;
 if(code[9:2]!==229) $fatal(1,"proportional term did not withdraw");
 $display("PASS selected gain scaling: %0d integral updates plus three proportional checks",checks);
 $finish;
end
endmodule
