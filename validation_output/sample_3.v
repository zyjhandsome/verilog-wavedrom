module  acl_fp_log_s5_altfp_log_and_or_v6b
	( 
	aclr,
	clken,
	clock,
	data,
	result) ;
	input   aclr;
	input   clken;
	input   clock;
	input   [7:0]  data;
	output   result;
`ifndef ALTERA_RESERVED_QIS
// synopsys translate_off
`endif
	tri0   aclr;
	tri1   clken;
	tri0   clock;
	tri0   [7:0]  data;
`ifndef ALTERA_RESERVED_QIS
// synopsys translate_on
`endif

	reg	[1:0]	connection_dffe0;
	reg	[0:0]	connection_dffe1;
	reg	connection_dffe2;
	wire  [7:0]  connection_r0_w;
	wire  [1:0]  connection_r1_w;
	wire  [0:0]  connection_r2_w;
	wire  [7:0]  operation_r1_w;
	wire  [1:0]  operation_r2_w;

	// synopsys translate_off
	initial
		connection_dffe0 = 0;
	// synopsys translate_on
	always @ ( posedge clock or  posedge aclr)
		if (aclr == 1'b1) connection_dffe0 <= 2'b0;
		else if  (clken == 1'b1)   connection_dffe0 <= {operation_r1_w[7], operation_r1_w[5]};
	// synopsys translate_off
	initial
		connection_dffe1 = 0;
	// synopsys translate_on
	always @ ( posedge clock or  posedge aclr)
		if (aclr == 1'b1) connection_dffe1 <= 1'b0;
		else if  (clken == 1'b1)   connection_dffe1 <= {operation_r2_w[1]};
	// synopsys translate_off
	initial
		connection_dffe2 = 0;
	// synopsys translate_on
	always @ ( posedge clock or  posedge aclr)
		if (aclr == 1'b1) connection_dffe2 <= 1'b0;
		else if  (clken == 1'b1)   connection_dffe2 <= connection_r2_w[0];
	assign
		connection_r0_w = data,
		connection_r1_w = connection_dffe0,
		connection_r2_w = connection_dffe1,
		operation_r1_w = {(operation_r1_w[6] | connection_r0_w[7]), connection_r0_w[6], (operation_r1_w[4] | connection_r0_w[5]), (operation_r1_w[3] | connection_r0_w[4]), (operation_r1_w[2] | connection_r0_w[3]), (operation_r1_w[1] | connection_r0_w[2]), (operation_r1_w[0] | connection_r0_w[1]), connection_r0_w[0]},
		operation_r2_w = {(operation_r2_w[0] | connection_r1_w[1]), connection_r1_w[0]},
		result = connection_dffe2;
endmodule