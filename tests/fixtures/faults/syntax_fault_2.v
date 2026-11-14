module counter_bad2 (input clk, output reg [3:0] q);
    always @(posedge clk)
        q <= undefined_signal + 1; // Using undeclared signal
endmodule