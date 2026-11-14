module counter_bad3 (input clk, output reg [3:0] q);
    always @(posedge clk)
        q <= q + 1;
// Missing endmodule keyword at the end