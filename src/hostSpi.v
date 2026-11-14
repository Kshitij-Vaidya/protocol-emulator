`default_nettype none

module hostSpi #(
    parameter numCores    = 2,
    parameter configWidth = 91
) (
    input  wire                            clk,
    input  wire                            rstN,
    input  wire                            sck,
    input  wire                            csN,
    input  wire                            mosi,
    output wire                            miso,
    input  wire [numCores-1:0]             coreOwnsMem,
    input  wire [numCores-1:0]             active,
    input  wire [7:0]                      flags,
    output wire [numCores-1:0]             run,
    output wire [numCores-1:0]             restart,
    output wire [numCores*configWidth-1:0] coreConfig,
    output wire [31:0]                     syncBypass,
    output wire [numCores-1:0]             hostExecEn,
    output wire [15:0]                     hostExecInstr,
    output wire [numCores*8-1:0]           memAddr,
    output wire [numCores-1:0]             memWriteEn,
    output wire [15:0]                     memWriteData,
    input  wire [numCores*16-1:0]          memReadData,
    output wire [numCores-1:0]             txWriteEn,
    output wire [15:0]                     txWriteData,
    input  wire [numCores*3-1:0]           txLevel,
    output wire [numCores-1:0]             rxReadEn,
    input  wire [numCores*16-1:0]          rxReadData,
    input  wire [numCores*3-1:0]           rxLevel
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
    localparam [6:0] regCoreSel    = 7'h12;
    localparam [6:0] regRunAll     = 7'h13;

    localparam [15:0] idValue       = 16'h5045;
    localparam [15:0] shiftReset    = 16'b0010_0001_0000_0011;
    localparam [2:0]  fifoDepth     = 3'd4;
    localparam [1:0]  commandReload = 2'd1;
    localparam [1:0]  wordReload    = 2'd2;
    localparam        selBits       = (numCores > 1) ? $clog2(numCores) : 1;
    localparam        restartShift  = 4;

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
    reg  [1:0]  coreSelQ;
    reg  [31:0] syncBypassQ;

    wire [numCores-1:0]    runAll;
    wire [numCores-1:0]    rejectedAll;
    wire [numCores*8-1:0]  startPcAll;
    wire [numCores*16-1:0] clkDivAll;
    wire [numCores*16-1:0] pinOutAll;
    wire [numCores*16-1:0] pinSetAll;
    wire [numCores*16-1:0] pinSideAll;
    wire [numCores*16-1:0] pinInAll;
    wire [numCores*16-1:0] shiftAll;
    wire [numCores*16-1:0] wrapAll;

    wire        sckRise   = sckQ[1] & ~sckQ[2];
    wire        csActive  = ~csQ[1];
    wire        writeWord = wordDone && isWrite;
    wire        readWord  = wordDone && !isWrite;
    wire        selValid  = (coreSelQ < numCores);
    wire [selBits-1:0] sel = selValid ? coreSelQ[selBits-1:0] : {selBits{1'b0}};
    wire [7:0]  selStatus = {rxLevel[sel*3 +: 3], txLevel[sel*3 +: 3], rejectedAll[sel], active[sel]};
    wire [15:0] selRxHead = (rxLevel[sel*3 +: 3] == 3'd0) ? 16'd0 : rxReadData[sel*16 +: 16];

    assign miso          = shiftOut[15];
    assign run           = runAll;
    assign syncBypass    = syncBypassQ;
    assign hostExecInstr = shiftIn;
    assign memWriteData  = shiftIn;
    assign txWriteData   = shiftIn;

    always @(*) begin
        readValue = 16'd0;
        case (regAddr)
            regStatus:     readValue = {flags, selValid ? selStatus : 8'd0};
            regBypassLow:  readValue = syncBypassQ[15:0];
            regBypassHigh: readValue = syncBypassQ[31:16];
            regId:         readValue = idValue;
            regCoreSel:    readValue = {14'd0, coreSelQ};
            regRunAll:     readValue = {{(16 - numCores){1'b0}}, runAll};
            default: begin
                if (selValid) begin
                    case (regAddr)
                        regCtrl:     readValue = {15'd0, runAll[sel]};
                        regMemAddr:  readValue = {8'd0, memAddr[sel*8 +: 8]};
                        regMemData:  readValue = memReadData[sel*16 +: 16];
                        regStartPc:  readValue = {8'd0, startPcAll[sel*8 +: 8]};
                        regClkDiv:   readValue = clkDivAll[sel*16 +: 16];
                        regPinOut:   readValue = pinOutAll[sel*16 +: 16];
                        regPinSet:   readValue = pinSetAll[sel*16 +: 16];
                        regPinSide:  readValue = pinSideAll[sel*16 +: 16];
                        regPinIn:    readValue = pinInAll[sel*16 +: 16];
                        regShift:    readValue = shiftAll[sel*16 +: 16];
                        regWrap:     readValue = wrapAll[sel*16 +: 16];
                        regRxFifo:   readValue = selRxHead;
                        default:     readValue = 16'd0;
                    endcase
                end
            end
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
            coreSelQ    <= 2'd0;
            syncBypassQ <= 32'd0;
        end else if (writeWord) begin
            case (regAddr)
                regCoreSel:    coreSelQ <= shiftIn[1:0];
                regBypassLow:  syncBypassQ[15:0] <= shiftIn;
                regBypassHigh: syncBypassQ[31:16] <= shiftIn;
                default: ;
            endcase
        end
    end

    genvar coreIdx;
    generate
        for (coreIdx = 0; coreIdx < numCores; coreIdx = coreIdx + 1) begin : perCore
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

            wire isSel      = selValid && (coreSelQ == coreIdx);
            wire selWrite   = writeWord && isSel;
            wire isTxFull   = (txLevel[coreIdx*3 +: 3] == fifoDepth);
            wire runAllWord = writeWord && (regAddr == regRunAll);

            assign runAll[coreIdx]                     = runQ;
            assign rejectedAll[coreIdx]                = rejected;
            assign startPcAll[coreIdx*8 +: 8]          = startPcQ;
            assign clkDivAll[coreIdx*16 +: 16]         = clkDivQ;
            assign pinOutAll[coreIdx*16 +: 16]         = pinOutQ;
            assign pinSetAll[coreIdx*16 +: 16]         = pinSetQ;
            assign pinSideAll[coreIdx*16 +: 16]        = pinSideQ;
            assign pinInAll[coreIdx*16 +: 16]          = pinInQ;
            assign shiftAll[coreIdx*16 +: 16]          = shiftQ;
            assign wrapAll[coreIdx*16 +: 16]           = wrapQ;
            assign memAddr[coreIdx*8 +: 8]             = memAddrQ;

            assign restart[coreIdx]    = (selWrite && (regAddr == regCtrl) && shiftIn[1])
                                         || (runAllWord && shiftIn[restartShift + coreIdx]);
            assign hostExecEn[coreIdx] = selWrite && (regAddr == regExec) && !coreOwnsMem[coreIdx];
            assign memWriteEn[coreIdx] = selWrite && (regAddr == regMemData) && !coreOwnsMem[coreIdx];
            assign txWriteEn[coreIdx]  = selWrite && (regAddr == regTxFifo);
            assign rxReadEn[coreIdx]   = readWord && isSel && (regAddr == regRxFifo);

            assign coreConfig[coreIdx*configWidth +: configWidth] = {
                startPcQ,
                clkDivQ,
                pinOutQ[4:0],
                pinOutQ[12:8],
                pinSetQ[4:0],
                pinSetQ[10:8],
                pinSideQ[4:0],
                pinSideQ[9:8],
                pinSideQ[10],
                pinSideQ[11],
                pinInQ[4:0],
                pinInQ[12:8],
                shiftQ[0],
                shiftQ[1],
                shiftQ[2],
                shiftQ[3],
                shiftQ[8:4],
                shiftQ[13:9],
                wrapQ[7:0],
                wrapQ[15:8]
            };

            always @(posedge clk) begin
                if (!rstN) begin
                    runQ     <= 1'b0;
                    rejected <= 1'b0;
                    memAddrQ <= 8'd0;
                    startPcQ <= 8'd0;
                    clkDivQ  <= 16'd1;
                    pinOutQ  <= 16'd0;
                    pinSetQ  <= 16'd0;
                    pinSideQ <= 16'd0;
                    pinInQ   <= 16'd0;
                    shiftQ   <= shiftReset;
                    wrapQ    <= 16'hFF00;
                end else if (runAllWord) begin
                    runQ <= shiftIn[coreIdx];
                end else if (selWrite) begin
                    case (regAddr)
                        regCtrl: begin
                            runQ     <= shiftIn[0];
                            rejected <= 1'b0;
                        end
                        regMemAddr: memAddrQ <= shiftIn[7:0];
                        regMemData: begin
                            memAddrQ <= memAddrQ + 1'b1;
                            if (coreOwnsMem[coreIdx])
                                rejected <= 1'b1;
                        end
                        regStartPc: startPcQ <= shiftIn[7:0];
                        regExec: begin
                            if (coreOwnsMem[coreIdx])
                                rejected <= 1'b1;
                        end
                        regClkDiv:  clkDivQ <= shiftIn;
                        regPinOut:  pinOutQ <= shiftIn;
                        regPinSet:  pinSetQ <= shiftIn;
                        regPinSide: pinSideQ <= shiftIn;
                        regPinIn:   pinInQ <= shiftIn;
                        regShift:   shiftQ <= shiftIn;
                        regWrap:    wrapQ <= shiftIn;
                        regTxFifo: begin
                            if (isTxFull)
                                rejected <= 1'b1;
                        end
                        default: ;
                    endcase
                end else if (readWord && isSel && regAddr == regMemData) begin
                    memAddrQ <= memAddrQ + 1'b1;
                end
            end
        end
    endgenerate

endmodule
