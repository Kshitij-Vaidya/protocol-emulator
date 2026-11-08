`default_nettype none

module hostSpi (
    input  wire        clk,
    input  wire        rstN,
    input  wire        sck,
    input  wire        csN,
    input  wire        mosi,
    output wire        miso,
    input  wire        coreOwnsMem,
    input  wire        active,
    input  wire [7:0]  flags,
    output wire        run,
    output wire        restart,
    output wire [7:0]  startPc,
    output wire [15:0] clkDiv,
    output wire [4:0]  outBase,
    output wire [4:0]  outCount,
    output wire [4:0]  setBase,
    output wire [2:0]  setCount,
    output wire [4:0]  sideBase,
    output wire [1:0]  sideCount,
    output wire        sideEn,
    output wire        sidePinDir,
    output wire [4:0]  inBase,
    output wire [4:0]  jmpPin,
    output wire        outShiftRight,
    output wire        inShiftRight,
    output wire        autoPull,
    output wire        autoPush,
    output wire [4:0]  pullThreshold,
    output wire [4:0]  pushThreshold,
    output wire [7:0]  wrapBottom,
    output wire [7:0]  wrapTop,
    output wire [31:0] syncBypass,
    output wire        hostExecEn,
    output wire [15:0] hostExecInstr,
    output wire [7:0]  memAddr,
    output wire        memWriteEn,
    output wire [15:0] memWriteData,
    input  wire [15:0] memReadData,
    output wire        txWriteEn,
    output wire [15:0] txWriteData,
    input  wire [2:0]  txLevel,
    output wire        rxReadEn,
    input  wire [15:0] rxReadData,
    input  wire [2:0]  rxLevel
);

    localparam [6:0] regCtrl       = 7'h00;
    localparam [6:0] regStatus     = 7'h01;
    localparam [6:0] regMemAddr    = 7'h02;
    localparam [6:0] regMemData    = 7'h03;
    localparam [6:0] regStartPc    = 7'h04;
    localparam [6:0] regExec       = 7'h05;
    localparam [6:0] regClkDiv     = 7'h06;
    localparam [6:0] regPinOut     = 7'h07;
    localparam [6:0] regPinSet     = 7'h08;
    localparam [6:0] regPinSide    = 7'h09;
    localparam [6:0] regPinIn      = 7'h0A;
    localparam [6:0] regShift      = 7'h0B;
    localparam [6:0] regWrap       = 7'h0C;
    localparam [6:0] regTxFifo     = 7'h0D;
    localparam [6:0] regRxFifo     = 7'h0E;
    localparam [6:0] regBypassLow  = 7'h0F;
    localparam [6:0] regBypassHigh = 7'h10;
    localparam [6:0] regId         = 7'h11;

    localparam [15:0] idValue       = 16'h5045;
    localparam [15:0] shiftReset    = 16'b0010_0001_0000_0011;
    localparam [2:0]  fifoDepth     = 3'd4;
    localparam [1:0]  commandReload = 2'd1;
    localparam [1:0]  wordReload    = 2'd2;

    reg  [2:0]  sckQ;
    reg  [1:0]  csQ;
    reg  [1:0]  mosiQ;
    reg  [3:0]  bitIndex;
    reg         isData;
    reg         isWrite;
    reg  [6:0]  regAddr;
    reg  [15:0] shiftIn;
    reg  [15:0] shiftOut;
    reg         commandDone;
    reg         wordDone;
    reg  [1:0]  reloadCount;
    reg  [15:0] readValue;

    reg         runQ;
    reg         rejected;
    reg  [7:0]  memAddrQ;
    reg  [7:0]  startPcQ;
    reg  [15:0] clkDivQ;
    reg  [15:0] pinOutQ;
    reg  [15:0] pinSetQ;
    reg  [15:0] pinSideQ;
    reg  [15:0] pinInQ;
    reg  [15:0] shiftQ;
    reg  [15:0] wrapQ;
    reg  [31:0] syncBypassQ;

    wire        sckRise   = sckQ[1] & ~sckQ[2];
    wire        csActive  = ~csQ[1];
    wire        writeWord = wordDone && isWrite;
    wire        readWord  = wordDone && !isWrite;
    wire [15:0] status    = {flags, rxLevel, txLevel, rejected, active};
    wire        isTxFull  = (txLevel == fifoDepth);

    assign miso          = shiftOut[15];
    assign run           = runQ;
    assign restart       = writeWord && (regAddr == regCtrl) && shiftIn[1];
    assign startPc       = startPcQ;
    assign clkDiv        = clkDivQ;
    assign outBase       = pinOutQ[4:0];
    assign outCount      = pinOutQ[12:8];
    assign setBase       = pinSetQ[4:0];
    assign setCount      = pinSetQ[10:8];
    assign sideBase      = pinSideQ[4:0];
    assign sideCount     = pinSideQ[9:8];
    assign sideEn        = pinSideQ[10];
    assign sidePinDir    = pinSideQ[11];
    assign inBase        = pinInQ[4:0];
    assign jmpPin        = pinInQ[12:8];
    assign outShiftRight = shiftQ[0];
    assign inShiftRight  = shiftQ[1];
    assign autoPull      = shiftQ[2];
    assign autoPush      = shiftQ[3];
    assign pullThreshold = shiftQ[8:4];
    assign pushThreshold = shiftQ[13:9];
    assign wrapBottom    = wrapQ[7:0];
    assign wrapTop       = wrapQ[15:8];
    assign syncBypass    = syncBypassQ;
    assign hostExecEn    = writeWord && (regAddr == regExec) && !coreOwnsMem;
    assign hostExecInstr = shiftIn;
    assign memAddr       = memAddrQ;
    assign memWriteEn    = writeWord && (regAddr == regMemData) && !coreOwnsMem;
    assign memWriteData  = shiftIn;
    assign txWriteEn     = writeWord && (regAddr == regTxFifo);
    assign txWriteData   = shiftIn;
    assign rxReadEn      = readWord && (regAddr == regRxFifo);

    always @(*) begin
        case (regAddr)
            regCtrl:       readValue = {15'd0, runQ};
            regStatus:     readValue = status;
            regMemAddr:    readValue = {8'd0, memAddrQ};
            regMemData:    readValue = memReadData;
            regStartPc:    readValue = {8'd0, startPcQ};
            regClkDiv:     readValue = clkDivQ;
            regPinOut:     readValue = pinOutQ;
            regPinSet:     readValue = pinSetQ;
            regPinSide:    readValue = pinSideQ;
            regPinIn:      readValue = pinInQ;
            regShift:      readValue = shiftQ;
            regWrap:       readValue = wrapQ;
            regRxFifo:     readValue = (rxLevel == 3'd0) ? 16'd0 : rxReadData;
            regBypassLow:  readValue = syncBypassQ[15:0];
            regBypassHigh: readValue = syncBypassQ[31:16];
            regId:         readValue = idValue;
            default:       readValue = 16'd0;
        endcase
    end

    always @(posedge clk) begin
        if (!rstN) begin
            sckQ        <= 3'd0;
            csQ         <= 2'b11;
            mosiQ       <= 2'd0;
            bitIndex    <= 4'd0;
            isData      <= 1'b0;
            isWrite     <= 1'b0;
            regAddr     <= 7'd0;
            shiftIn     <= 16'd0;
            shiftOut    <= 16'd0;
            commandDone <= 1'b0;
            wordDone    <= 1'b0;
            reloadCount <= 2'd0;
        end else begin
            sckQ        <= {sckQ[1:0], sck};
            csQ         <= {csQ[0], csN};
            mosiQ       <= {mosiQ[0], mosi};
            commandDone <= 1'b0;
            wordDone    <= 1'b0;
            if (!csActive) begin
                bitIndex <= 4'd0;
                isData   <= 1'b0;
            end else if (sckRise) begin
                shiftIn  <= {shiftIn[14:0], mosiQ[1]};
                bitIndex <= bitIndex + 1'b1;
                if (!isData && bitIndex == 4'd7) begin
                    bitIndex    <= 4'd0;
                    isData      <= 1'b1;
                    commandDone <= 1'b1;
                end
                if (isData) begin
                    shiftOut <= {shiftOut[14:0], 1'b0};
                    wordDone <= (bitIndex == 4'd15);
                end
            end
            if (commandDone) begin
                isWrite     <= shiftIn[7];
                regAddr     <= shiftIn[6:0];
                reloadCount <= commandReload;
            end
            if (wordDone)
                reloadCount <= wordReload;
            if (reloadCount != 2'd0) begin
                reloadCount <= reloadCount - 1'b1;
                if (reloadCount == 2'd1)
                    shiftOut <= readValue;
            end
        end
    end

    always @(posedge clk) begin
        if (!rstN) begin
            runQ        <= 1'b0;
            rejected    <= 1'b0;
            memAddrQ    <= 8'd0;
            startPcQ    <= 8'd0;
            clkDivQ     <= 16'd1;
            pinOutQ     <= 16'd0;
            pinSetQ     <= 16'd0;
            pinSideQ    <= 16'd0;
            pinInQ      <= 16'd0;
            shiftQ      <= shiftReset;
            wrapQ       <= 16'hFF00;
            syncBypassQ <= 32'd0;
        end else if (writeWord) begin
            case (regAddr)
                regCtrl: begin
                    runQ     <= shiftIn[0];
                    rejected <= 1'b0;
                end
                regMemAddr:    memAddrQ <= shiftIn[7:0];
                regMemData: begin
                    memAddrQ <= memAddrQ + 1'b1;
                    if (coreOwnsMem)
                        rejected <= 1'b1;
                end
                regStartPc:    startPcQ <= shiftIn[7:0];
                regExec: begin
                    if (coreOwnsMem)
                        rejected <= 1'b1;
                end
                regClkDiv:     clkDivQ <= shiftIn;
                regPinOut:     pinOutQ <= shiftIn;
                regPinSet:     pinSetQ <= shiftIn;
                regPinSide:    pinSideQ <= shiftIn;
                regPinIn:      pinInQ <= shiftIn;
                regShift:      shiftQ <= shiftIn;
                regWrap:       wrapQ <= shiftIn;
                regTxFifo: begin
                    if (isTxFull)
                        rejected <= 1'b1;
                end
                regBypassLow:  syncBypassQ[15:0] <= shiftIn;
                regBypassHigh: syncBypassQ[31:16] <= shiftIn;
                default: ;
            endcase
        end else if (readWord && regAddr == regMemData) begin
            memAddrQ <= memAddrQ + 1'b1;
        end
    end

endmodule
