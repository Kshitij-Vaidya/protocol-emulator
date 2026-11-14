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

`ifdef FORMAL
    reg pastValid = 1'b0;

    always @(posedge clk) begin
        pastValid <= 1'b1;
        if (pastValid && $past(rstN && !clear)) begin
            assert ((flags & $past(sets)) == $past(sets));
            assert ((flags & $past(clears & ~sets)) == {width{1'b0}});
            assert ((flags ^ $past(flags)) == ((flags ^ $past(flags)) & $past(sets | clears)));
        end
        if (pastValid && $past(!rstN || clear))
            assert (flags == {width{1'b0}});
    end
`endif

endmodule
