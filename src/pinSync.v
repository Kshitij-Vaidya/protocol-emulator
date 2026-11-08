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

endmodule
