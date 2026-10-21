module hang_tb;
  reg clk = 0;
  always #1 clk = ~clk;
endmodule
