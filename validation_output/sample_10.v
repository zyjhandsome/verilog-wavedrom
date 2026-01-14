module mig_7series_v2_3_poc_meta #
  (parameter SCANFROMRIGHT              = 0,
   parameter TCQ                        = 100,
   parameter TAPCNTRWIDTH               = 7,
   parameter TAPSPERKCLK                = 112)
  (/*AUTOARG*/
  // Outputs
  mmcm_edge_detect_done, poc_backup, mmcm_lbclk_edge_aligned,
  // Inputs
  rst, clk, mmcm_edge_detect_rdy, run, run_polarity, run_end,
  rise_lead_right, rise_trail_left, rise_lead_center,
  rise_trail_center, rise_trail_right, rise_lead_left, ninety_offsets,
  use_noise_window, ktap_at_right_edge, ktap_at_left_edge
  );

  localparam NINETY = TAPSPERKCLK/4;
  
  function [TAPCNTRWIDTH-1:0] offset (input [TAPCNTRWIDTH-1:0] a, 
                                      input [1:0] b,
                                      input integer base);
    integer offset_ii;
    begin
      offset_ii = (a + b * NINETY) < base
                     ? (a + b * NINETY) 
                     : (a + b * NINETY - base);
      offset = offset_ii[TAPCNTRWIDTH-1:0];
    end
  endfunction // offset

  function [TAPCNTRWIDTH-1:0] mod_sub (input [TAPCNTRWIDTH-1:0] a, 
                                       input [TAPCNTRWIDTH-1:0] b,
                                       input integer base); 
    begin
      mod_sub = (a>=b) ? a-b : a+base-b;
    end
  endfunction // mod_sub

  function [TAPCNTRWIDTH:0] center (input [TAPCNTRWIDTH-1:0] left, 
                                    input [TAPCNTRWIDTH-1:0] diff,
                                    input integer base);
    integer center_ii;
    begin
      center_ii = ({left, 1'b0} + diff < base * 2)
                    ? {left, 1'b0} + diff + 32'h0
	            : {left, 1'b0} + diff - base * 2;
      center = center_ii[TAPCNTRWIDTH:0];
    end
  endfunction // center

  input rst;
  input clk;


  input mmcm_edge_detect_rdy;

  wire reset_run_ends = rst || ~mmcm_edge_detect_rdy;

  // This input used only for the SVA.
  input [TAPCNTRWIDTH-1:0] run;
  
  input run_end;
  reg run_end_r, run_end_r1, run_end_r2, run_end_r3;
  always @(posedge clk) run_end_r <= #TCQ run_end;
  always @(posedge clk) run_end_r1 <= #TCQ run_end_r;
  always @(posedge clk) run_end_r2 <= #TCQ run_end_r1;
  always @(posedge clk) run_end_r3 <= #TCQ run_end_r2;

  input run_polarity;
  reg run_polarity_held_ns, run_polarity_held_r;
  always @(posedge clk) run_polarity_held_r <= #TCQ run_polarity_held_ns;
  always @(*) run_polarity_held_ns = run_end ? run_polarity : run_polarity_held_r;
  
  reg [1:0] run_ends_r;
  reg [1:0] run_ends_ns;
  always @(posedge clk) run_ends_r <= #TCQ run_ends_ns;
  always @(*) begin
    run_ends_ns = run_ends_r;
    if (reset_run_ends) run_ends_ns = 2'b0;
    else case (run_ends_r) 
           2'b00 : run_ends_ns = run_ends_r + {1'b0, run_end_r3 && run_polarity_held_r};
	   2'b01, 2'b10 : run_ends_ns = run_ends_r + {1'b0, run_end_r3};
	  endcase // case (run_ends_r)
  end

  reg done_r;
  wire done_ns = mmcm_edge_detect_rdy && &run_ends_r;
  always @(posedge clk) done_r <= #TCQ done_ns;
  output mmcm_edge_detect_done;
  assign mmcm_edge_detect_done = done_r;  

  input [TAPCNTRWIDTH-1:0] rise_lead_right;
  input [TAPCNTRWIDTH-1:0] rise_trail_left;
  input [TAPCNTRWIDTH-1:0] rise_lead_center;
  input [TAPCNTRWIDTH-1:0] rise_trail_center;
  input [TAPCNTRWIDTH-1:0] rise_trail_right;
  input [TAPCNTRWIDTH-1:0] rise_lead_left;

  input [1:0] ninety_offsets;
  wire [1:0] offsets = SCANFROMRIGHT == 1 ? ninety_offsets : 2'b00 - ninety_offsets;

  wire [TAPCNTRWIDTH-1:0] rise_lead_center_offset_ns = offset(rise_lead_center, offsets, TAPSPERKCLK);
  wire [TAPCNTRWIDTH-1:0] rise_trail_center_offset_ns = offset(rise_trail_center, offsets, TAPSPERKCLK);
  reg [TAPCNTRWIDTH-1:0] rise_lead_center_offset_r, rise_trail_center_offset_r;
  always @(posedge clk) rise_lead_center_offset_r <= #TCQ rise_lead_center_offset_ns;
  always @(posedge clk) rise_trail_center_offset_r <= #TCQ rise_trail_center_offset_ns;

  wire [TAPCNTRWIDTH-1:0] edge_diff_ns = mod_sub(rise_trail_center_offset_r, rise_lead_center_offset_r, TAPSPERKCLK);
  reg [TAPCNTRWIDTH-1:0] edge_diff_r;
  always @(posedge clk) edge_diff_r <= #TCQ edge_diff_ns;
  
  wire [TAPCNTRWIDTH:0] edge_center_ns = center(rise_lead_center_offset_r, edge_diff_r, TAPSPERKCLK);
  reg [TAPCNTRWIDTH:0] edge_center_r;
  always @(posedge clk) edge_center_r <= #TCQ edge_center_ns;

  input use_noise_window;
  wire [TAPCNTRWIDTH-1:0] left = use_noise_window ? rise_lead_left : rise_trail_left;
  wire [TAPCNTRWIDTH-1:0] right = use_noise_window ? rise_trail_right : rise_lead_right;

  wire [TAPCNTRWIDTH-1:0] center_diff_ns = mod_sub(right, left, TAPSPERKCLK);
  reg [TAPCNTRWIDTH-1:0] center_diff_r;
  always @(posedge clk) center_diff_r <= #TCQ center_diff_ns;
  
  wire [TAPCNTRWIDTH:0] window_center_ns = center(left, center_diff_r, TAPSPERKCLK);
  reg [TAPCNTRWIDTH:0] window_center_r;
  always @(posedge clk) window_center_r <= #TCQ window_center_ns;

  localparam TAPSPERKCLKX2 = TAPSPERKCLK * 2;

  wire [TAPCNTRWIDTH+1:0] left_center = {1'b0, SCANFROMRIGHT == 1 ? window_center_r : edge_center_r};
  wire [TAPCNTRWIDTH+1:0] right_center = {1'b0, SCANFROMRIGHT == 1 ? edge_center_r : window_center_r};
			  
  wire [TAPCNTRWIDTH+1:0] diff_ns = right_center >= left_center
                                     ? right_center - left_center
                                     : right_center + TAPSPERKCLKX2[TAPCNTRWIDTH+1:0] - left_center;
  
  reg [TAPCNTRWIDTH+1:0] diff_r;
  always @(posedge clk) diff_r <= #TCQ diff_ns;

  wire [TAPCNTRWIDTH+1:0] abs_diff = diff_r > TAPSPERKCLKX2[TAPCNTRWIDTH+1:0]/2
                                       ? TAPSPERKCLKX2[TAPCNTRWIDTH+1:0] - diff_r
                                       : diff_r;

  reg [TAPCNTRWIDTH+1:0] prev_ns, prev_r;
  always @(posedge clk) prev_r <= #TCQ prev_ns;
  always @(*) prev_ns = done_ns ? diff_r : prev_r;

  input ktap_at_right_edge;
  input ktap_at_left_edge;
  
  wire centering = !(ktap_at_right_edge || ktap_at_left_edge);
  wire diffs_eq = abs_diff == diff_r;
  reg diffs_eq_ns, diffs_eq_r;
  always @(*) diffs_eq_ns = centering && ((done_r && done_ns) ? diffs_eq : diffs_eq_r);
  always @(posedge clk) diffs_eq_r <= #TCQ diffs_eq_ns;

  reg edge_aligned_r;
  reg prev_valid_ns, prev_valid_r;
  always @(posedge clk) prev_valid_r <= #TCQ prev_valid_ns;
  always @(*) prev_valid_ns = (~rst && ~ktap_at_right_edge && ~ktap_at_left_edge && ~edge_aligned_r) && prev_valid_r | done_ns;

  wire indicate_alignment = ~rst && centering && done_ns;
  wire edge_aligned_ns = indicate_alignment && (~|diff_r || ~diffs_eq & diffs_eq_r);
  always @(posedge clk) edge_aligned_r <= #TCQ edge_aligned_ns;

  reg poc_backup_r;
  wire poc_backup_ns = edge_aligned_ns && abs_diff > prev_r;
  always @(posedge clk) poc_backup_r <= #TCQ poc_backup_ns;
  output poc_backup;
  assign poc_backup = poc_backup_r;

  output mmcm_lbclk_edge_aligned;
  assign mmcm_lbclk_edge_aligned = edge_aligned_r;
  
endmodule