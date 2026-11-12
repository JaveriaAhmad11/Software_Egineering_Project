// Mutant of counter_good.v for testbench validation (S2-07): functionally WRONG on purpose.
// Same module name and ports, but it counts by 2 instead of 1.
module counter8 (input clk, input rst_n, output reg [7:0] count);
  always @(posedge clk) begin
    if (!rst_n) count <= 8'd0;
    else        count <= count + 8'd2;
  end
endmodule
