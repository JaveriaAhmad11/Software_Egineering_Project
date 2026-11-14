module counter8 (input clk, input rst_n, output reg [7:0] count);
  always @(posedge clk) begin
    if (!rst_n) count <= 8'd0;
    else        count <= undefined_signal + 8'd1;  // undeclared signal
  end
endmodule
