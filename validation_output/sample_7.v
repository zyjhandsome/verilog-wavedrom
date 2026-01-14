module BB(
          /*AUTOINPUT*/
          /*AUTOOUTPUT*/
          input wire       clock,
          input wire       reset,
          input wire       test_enable,
          input wire       core_code_idle,
          input wire       core_code_error,
          input wire [7:0] core_data,
          input wire [8:0] mbist_done,
          input wire [8:0] mbist_fail,
          output wire      mbist_rst,
          output reg       mbist_test
          );
endmodule