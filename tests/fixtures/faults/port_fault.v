module counter8 (input clock_wrong_name, input rst_n, output reg [7:0] count);
  always @(posedge clock_wrong_name) begin
    if (!rst_n) count <= 8'd0;
    else        count <= count + 8'd1;
  end
endmodule
