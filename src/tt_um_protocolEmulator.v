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
    localparam addrWidth  = 8;
    localparam dataWidth  = 16;
    localparam byteWidth  = 8;
    localparam cmdWidth   = 2;
    localparam hostWidth  = 1 + cmdWidth + byteWidth;

    localparam [cmdWidth-1:0] cmdSetAddr   = 2'b01;
    localparam [cmdWidth-1:0] cmdWriteLow  = 2'b10;
    localparam [cmdWidth-1:0] cmdWriteHigh = 2'b11;

    reg  [syncStages-1:0] sendSync;
    wire                  sendPulse = sendSync[syncStages-2] & ~sendSync[syncStages-1];

    reg  [hostWidth-1:0]  hostMeta;
    reg  [hostWidth-1:0]  hostQ;
    wire [byteWidth-1:0]  dataQ    = hostQ[byteWidth-1:0];
    wire [cmdWidth-1:0]   cmdQ     = hostQ[byteWidth+cmdWidth-1:byteWidth];
    wire                  byteSelQ = hostQ[hostWidth-1];

    reg                   memEn;
    reg  [addrWidth-1:0]  addr;
    reg  [byteWidth-1:0]  lowByte;
    wire                  writeEn   = (cmdQ == cmdWriteHigh);
    wire [dataWidth-1:0]  writeData = {dataQ, lowByte};
    wire [dataWidth-1:0]  readData;
    wire [byteWidth-1:0]  txData    = byteSelQ ? readData[dataWidth-1:byteWidth]
                                               : readData[byteWidth-1:0];
    wire                  txOut;
    wire                  txReady;

    always @(posedge clk) begin
        if (!rst_n) begin
            sendSync <= {syncStages{1'b0}};
            hostMeta <= {hostWidth{1'b0}};
            hostQ    <= {hostWidth{1'b0}};
            memEn    <= 1'b0;
            addr     <= {addrWidth{1'b0}};
            lowByte  <= {byteWidth{1'b0}};
        end else begin
            sendSync <= {sendSync[syncStages-2:0], uio_in[0]};
            hostMeta <= {uio_in[3:1], ui_in};
            hostQ    <= hostMeta;
            memEn    <= 1'b1;
            if (cmdQ == cmdSetAddr)
                addr <= dataQ;
            if (cmdQ == cmdWriteLow)
                lowByte <= dataQ;
        end
    end

    progMem #(
        .addrWidth(addrWidth),
        .dataWidth(dataWidth)
    ) progMemInst (
        .clk      (clk),
        .memEn    (memEn),
        .addr     (addr),
        .writeData(writeData),
        .writeEn  (writeEn),
        .readData (readData)
    );

    uartTx #(
        .clkFreqHz(50_000_000),
        .baudRate (115_200)
    ) uartTxInst (
        .clk    (clk),
        .rstN   (rst_n),
        .txData (txData),
        .txValid(sendPulse),
        .txReady(txReady),
        .txOut  (txOut)
    );

    assign uo_out  = {6'b0, txReady, txOut};
    assign uio_out = 8'b0;
    assign uio_oe  = 8'b0;

    wire unusedInputs = &{ena, uio_in[7:4], 1'b0};

endmodule
