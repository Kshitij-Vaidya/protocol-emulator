`default_nettype none

module flagBank #(
    parameter width = 8
) (
    input  wire             clk,
    input  wire             rstN,
    input  wire             clear,
    input  wire [width-1:0] sets,
    input  wire [width-1:0] clears,
    output reg  [width-1:0] flags
);

    always @(posedge clk) begin
        if (!rstN || clear)
            flags <= {width{1'b0}};
        else
            flags <= (flags & ~clears) | sets;
    end

endmodule
