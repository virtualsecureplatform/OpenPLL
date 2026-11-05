// Compatibility names missing from the pinned HS functional views.
// These wrappers only map old helper names to the shipped HS UDP tables.
// No timing is modeled; the UDPs retain unknown-state and supply behavior.
`timescale 1ns/1ps
`default_nettype none
module sky130_fd_sc_hs__u_df_p_r_pg(output Q, input D, CLK, RESET, VPWR, VGND);
 sky130_fd_sc_hs__udp_dff$PR_pp$PG model(Q,D,CLK,RESET,VPWR,VGND);
endmodule
module sky130_fd_sc_hs__u_df_p_s_pg(output Q, input D, CLK, SET, VPWR, VGND);
 sky130_fd_sc_hs__udp_dff$PS_pp$PG model(Q,D,CLK,SET,VPWR,VGND);
endmodule
module sky130_fd_sc_hs__u_mux_2_1(output X, input A0,A1,S);
 sky130_fd_sc_hs__udp_mux_2to1 model(X,A0,A1,S);
endmodule
module sky130_fd_sc_hs__u_mux_2_1_inv(output Y, input A0,A1,S);
 sky130_fd_sc_hs__udp_mux_2to1_N model(Y,A0,A1,S);
endmodule
module sky130_fd_sc_hs__u_vpwr_vgnd(output Y, input A,VPWR,VGND);
 sky130_fd_sc_hs__udp_pwrgood_pp$PG model(Y,A,VPWR,VGND);
endmodule
`default_nettype wire
