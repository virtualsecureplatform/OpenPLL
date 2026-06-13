// SPDX-License-Identifier: Apache-2.0
`timescale 1ns/1ps
`default_nettype none

/// sta-blackbox

(* blackbox *)
module sky130_fd_sc_hd__and2_1 (
    output wire X,
    input wire A,
    input wire B
);
endmodule

(* blackbox *)
module sky130_fd_sc_hd__and2b_1 (
    output wire X,
    input wire A_N,
    input wire B
);
endmodule

(* blackbox *)
module sky130_fd_sc_hd__buf_1 (
    output wire X,
    input wire A
);
endmodule

(* blackbox *)
module sky130_fd_sc_hd__conb_1 (
    output wire HI,
    output wire LO
);
endmodule

(* blackbox *)
module sky130_fd_sc_hd__dfrtp_1 (
    output wire Q,
    input wire CLK,
    input wire D,
    input wire RESET_B
);
endmodule

(* blackbox *)
module sky130_fd_sc_hd__einvp_1 (
    output wire Z,
    input wire A,
    input wire TE
);
endmodule

(* blackbox *)
module sky130_fd_sc_hd__inv_1 (
    output wire Y,
    input wire A
);
endmodule

(* blackbox *)
module sky130_fd_sc_hd__nand2_1 (
    output wire Y,
    input wire A,
    input wire B
);
endmodule

`default_nettype wire
