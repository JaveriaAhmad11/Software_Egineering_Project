module counter_mutant (input clk, output reg [3:0] q);
    always @(posedge clk)
        q <= q + 2; // Functionally wrong increment value expected by testbench
endmodule