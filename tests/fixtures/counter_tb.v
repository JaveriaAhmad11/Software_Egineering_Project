`timescale 1ns/1ps
module counter_tb;
  reg clk = 0, rst_n = 0;
  wire [7:0] count;
  counter8 dut (.clk(clk), .rst_n(rst_n), .count(count));
  always #5 clk = ~clk;
  initial begin
    #12 rst_n = 1;
    #100;
    if (count == 8'd10) $display("PASS count=%0d", count);
    else                $display("FAIL count=%0d", count);
    $finish;
  end
endmodule
