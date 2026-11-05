// SPDX-License-Identifier: Apache-2.0
// Compatibility names absent from the pinned HS timing views.
// Pin order maps directly to shipped UDPs, preserving notifier and supply checks.
`timescale 1ns/1ps
`default_nettype none
module sky130_fd_sc_hs__u_df_p_r_no_pg(output Q,input D,CLK,RESET,NOTIFIER,VPWR,VGND);
 sky130_fd_sc_hs__udp_dff$PR_pp$PG$N model(Q,D,CLK,RESET,NOTIFIER,VPWR,VGND);
endmodule
module sky130_fd_sc_hs__u_df_p_s_no_pg(output Q,input D,CLK,SET,NOTIFIER,VPWR,VGND);
 sky130_fd_sc_hs__udp_dff$PS_pp$PG$N model(Q,D,CLK,SET,NOTIFIER,VPWR,VGND);
endmodule
module sky130_fd_sc_hs__u_df_p_no_pg(output Q,input D,CLK,NOTIFIER,VPWR,VGND);
 sky130_fd_sc_hs__udp_dff$P_pp$PG$N model(Q,D,CLK,NOTIFIER,VPWR,VGND);
endmodule
`default_nettype wire
