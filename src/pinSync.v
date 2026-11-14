`default_nettype none

module pinSync #(
    parameter width = 32
) (
    input  wire             clk,
    input  wire             rstN,
    input  wire [width-1:0] pinsIn,
    input  wire [width-1:0] bypass,
    output wire [width-1:0] pinsOut
);

    reg [width-1:0] stage1;
    reg [width-1:0] stage2;

    assign pinsOut = (stage2 & ~bypass) | (pinsIn & bypass);

    always @(posedge clk) begin
        if (!rstN) begin
            stage1 <= {width{1'b0}};
            stage2 <= {width{1'b0}};
        end else begin
            stage1 <= pinsIn;
            stage2 <= stage1;
        end
    end

`ifdef FORMAL
    reg pastValid  = 1'b0;
    reg past2Valid = 1'b0;

    always @(*)
        assert ((pinsOut & bypass) == (pinsIn & bypass));

    always @(posedge clk) begin
        pastValid  <= 1'b1;
        past2Valid <= pastValid;
        if (past2Valid && $past(rstN) && $past(rstN, 2))
            assert ((pinsOut & ~bypass) == ($past(pinsIn, 2) & ~bypass));
        if (pastValid && !$past(rstN))
            assert ((pinsOut & ~bypass) == {width{1'b0}});
    end
`endif

endmodule
