`default_nettype none

module uartTx #(
    parameter clkFreqHz = 50_000_000,
    parameter baudRate  = 115_200
) (
    input  wire       clk,
    input  wire       rstN,
    input  wire [7:0] txData,
    input  wire       txValid,
    output wire       txReady,
    output wire       txOut
);

    localparam clksPerBit   = (clkFreqHz + baudRate / 2) / baudRate;
    localparam baudCntWidth = $clog2(clksPerBit);
    localparam frameBits    = 10;
    localparam bitsCntWidth = $clog2(frameBits + 1);

    localparam [baudCntWidth-1:0] lastBaudCnt = clksPerBit[baudCntWidth-1:0] - 1'b1;
    localparam [bitsCntWidth-1:0] fullFrame   = frameBits;

    reg [frameBits-1:0]    frame;
    reg [bitsCntWidth-1:0] bitsLeft;
    reg [baudCntWidth-1:0] baudCnt;

    assign txReady = (bitsLeft == {bitsCntWidth{1'b0}});
    assign txOut   = frame[0];

    always @(posedge clk) begin
        if (!rstN) begin
            frame    <= {frameBits{1'b1}};
            bitsLeft <= {bitsCntWidth{1'b0}};
            baudCnt  <= {baudCntWidth{1'b0}};
        end else if (txReady) begin
            if (txValid) begin
                frame    <= {1'b1, txData, 1'b0};
                bitsLeft <= fullFrame;
                baudCnt  <= {baudCntWidth{1'b0}};
            end
        end else if (baudCnt == lastBaudCnt) begin
            frame    <= {1'b1, frame[frameBits-1:1]};
            bitsLeft <= bitsLeft - 1'b1;
            baudCnt  <= {baudCntWidth{1'b0}};
        end else begin
            baudCnt <= baudCnt + 1'b1;
        end
    end

endmodule
