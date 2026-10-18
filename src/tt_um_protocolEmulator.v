`default_nettype none

module tt_um_protocolEmulator (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);

    localparam syncStages = 3;

    reg  [syncStages-1:0] sendSync;
    wire                  sendPulse = sendSync[syncStages-2] & ~sendSync[syncStages-1];
    wire                  txOut;
    wire                  txReady;

    always @(posedge clk) begin
        if (!rst_n)
            sendSync <= {syncStages{1'b0}};
        else
            sendSync <= {sendSync[syncStages-2:0], uio_in[0]};
    end

    uartTx #(
        .clkFreqHz(50_000_000),
        .baudRate (115_200)
    ) uartTxInst (
        .clk    (clk),
        .rstN   (rst_n),
        .txData (ui_in),
        .txValid(sendPulse),
        .txReady(txReady),
        .txOut  (txOut)
    );

    assign uo_out  = {6'b0, txReady, txOut};
    assign uio_out = 8'b0;
    assign uio_oe  = 8'b0;

    wire unusedInputs = &{ena, uio_in[7:1], 1'b0};

endmodule
