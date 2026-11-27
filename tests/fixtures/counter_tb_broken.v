// A testbench that does not compile (missing semicolon): a TESTBENCH problem, not an RTL bug.
`timescale 1ns/1ps
module counter8_tb;
  reg clk = 0
  counter8 dut (.clk(clk), .rst_n(1'b1), .count());
  initial $finish;
endmodule
