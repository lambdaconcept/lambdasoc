(* cxxrtl_blackbox, cxxrtl_template = "DATA_BITS" *)
module serial_rx(...);
	parameter ID = "";
	parameter DATA_BITS = 8;

	(* cxxrtl_edge = "p" *) input clk;
	input rst;
	(* cxxrtl_sync, cxxrtl_width = "DATA_BITS" *) output [DATA_BITS - 1:0] data;
	(* cxxrtl_sync *) output err_overflow;
	(* cxxrtl_sync *) output err_frame;
	(* cxxrtl_sync *) output err_parity;
	(* cxxrtl_sync *) output rdy;
	input ack;
endmodule

(* cxxrtl_blackbox, cxxrtl_template = "DATA_BITS" *)
module serial_tx(...);
	parameter ID = "";
	parameter DATA_BITS = 8;

	(* cxxrtl_edge = "p" *) input clk;
	input rst;
	(* cxxrtl_width = "DATA_BITS" *) input [DATA_BITS - 1:0] data;
	(* cxxrtl_sync *) output rdy;
	input ack;
endmodule
