// Hand-written reference testbench that follows prompts/testbench/v1.0 (S2-07 fixtures).
`timescale 1ns/1ps
module counter8_tb;
  reg clk = 0;
  reg rst_n = 0;
  wire [7:0] count;
  reg [7:0] expected;
  integer errors = 0;
  integer i;

  counter8 dut (.clk(clk), .rst_n(rst_n), .count(count));

  always #5 clk = ~clk;

  // behavioural reference model written from the specification, not copied from the DUT
  always @(posedge clk) begin
    if (!rst_n) expected <= 8'd0;
    else        expected <= expected + 8'd1;
  end

  // watchdog: the simulation can never hang
  initial begin
    #1000000;
    $display("FAIL: watchdog timeout");
    $finish;
  end

  task check;
    begin
      if (count !== expected) begin
        errors = errors + 1;
        $display("FAIL: t=%0t expected %0d got %0d", $time, expected, count);
      end
    end
  endtask

  initial begin
    rst_n = 0;
    repeat (2) @(negedge clk);
    check;                       // reset behaviour
    rst_n = 1;
    for (i = 0; i < 20; i = i + 1) begin
      @(negedge clk);
      check;                     // normal counting
    end
    rst_n = 0;                   // reset in the middle of operation
    repeat (2) @(negedge clk);
    check;
    rst_n = 1;
    for (i = 0; i < 5; i = i + 1) begin
      @(negedge clk);
      check;
    end
    if (errors == 0) $display("PASS");
    else             $display("FAIL: %0d mismatches", errors);
    $finish;
  end
endmodule
