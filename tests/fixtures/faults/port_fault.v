module counter_bad4 (input clock_wrong_name, output reg [3:0] q);
    always @(posedge clock_wrong_name)
        q <= q + 1;
endmodule