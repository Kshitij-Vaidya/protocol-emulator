`default_nettype none
`timescale 1ns/1ps

module multiCoreHarness (
    input  wire         clk,
    input  wire         rstN,
    input  wire [1:0]   run,
    input  wire [1:0]   restart,
    input  wire [181:0] coreConfig,
    input  wire [31:0]  pinsIn,
    input  wire [31:0]  syncBypass,
    input  wire [1:0]   loadEn,
    input  wire [7:0]   loadAddr,
    input  wire [15:0]  loadData,
    input  wire [1:0]   txWriteEn,
    input  wire [31:0]  txWriteData,
    input  wire [1:0]   rxReadEn,
    output wire [31:0]  rxReadData,
    output wire [5:0]   txLevel,
    output wire [5:0]   rxLevel,
    output wire [7:0]   flags,
    output wire [31:0]  pinOut,
    output wire [31:0]  pinDir
);

    initial begin
        $dumpfile("multiCoreHarness.fst");
        $dumpvars(0, multiCoreHarness);
    end

    localparam configWidth = 91;

    wire [31:0] pinsSynced;
    wire [1:0]  ownsMem;
    wire [1:0]  active;
    wire [31:0] memReadData;
    wire [31:0] status;
    wire [15:0] flagSets;
    wire [15:0] flagClears;
    wire [63:0] slicePinOut;
    wire [63:0] slicePinDir;

    assign pinOut = slicePinOut[31:0] | slicePinOut[63:32];
    assign pinDir = slicePinDir[31:0] | slicePinDir[63:32];

    pinSync #(
        .width(32)
    ) pinSyncInst (
        .clk    (clk),
        .rstN   (rstN),
        .pinsIn (pinsIn),
        .bypass (syncBypass),
        .pinsOut(pinsSynced)
    );

    flagBank #(
        .width(8)
    ) flagBankInst (
        .clk   (clk),
        .rstN  (rstN),
        .clear (|restart),
        .sets  (flagSets[7:0] | flagSets[15:8]),
        .clears(flagClears[7:0] | flagClears[15:8]),
        .flags (flags)
    );

    coreSlice #(
        .configWidth(configWidth)
    ) coreSlice0 (
        .clk          (clk),
        .rstN         (rstN),
        .run          (run[0]),
        .restart      (restart[0]),
        .coreConfig   (coreConfig[0 +: configWidth]),
        .pinsIn       (pinsSynced),
        .memAddr      (loadAddr),
        .memWriteEn   (loadEn[0] & ~ownsMem[0]),
        .memWriteData (loadData),
        .memReadData  (memReadData[15:0]),
        .ownsMem      (ownsMem[0]),
        .active       (active[0]),
        .hostExecEn   (1'b0),
        .hostExecInstr(16'd0),
        .txWriteEn    (txWriteEn[0]),
        .txWriteData  (txWriteData[15:0]),
        .rxReadEn     (rxReadEn[0]),
        .rxReadData   (rxReadData[15:0]),
        .txLevel      (txLevel[2:0]),
        .rxLevel      (rxLevel[2:0]),
        .status       (status[15:0]),
        .flags        (flags),
        .flagSets     (flagSets[7:0]),
        .flagClears   (flagClears[7:0]),
        .pinOut       (slicePinOut[31:0]),
        .pinDir       (slicePinDir[31:0])
    );

    coreSlice #(
        .configWidth(configWidth)
    ) coreSlice1 (
        .clk          (clk),
        .rstN         (rstN),
        .run          (run[1]),
        .restart      (restart[1]),
        .coreConfig   (coreConfig[configWidth +: configWidth]),
        .pinsIn       (pinsSynced),
        .memAddr      (loadAddr),
        .memWriteEn   (loadEn[1] & ~ownsMem[1]),
        .memWriteData (loadData),
        .memReadData  (memReadData[31:16]),
        .ownsMem      (ownsMem[1]),
        .active       (active[1]),
        .hostExecEn   (1'b0),
        .hostExecInstr(16'd0),
        .txWriteEn    (txWriteEn[1]),
        .txWriteData  (txWriteData[31:16]),
        .rxReadEn     (rxReadEn[1]),
        .rxReadData   (rxReadData[31:16]),
        .txLevel      (txLevel[5:3]),
        .rxLevel      (rxLevel[5:3]),
        .status       (status[31:16]),
        .flags        (flags),
        .flagSets     (flagSets[15:8]),
        .flagClears   (flagClears[15:8]),
        .pinOut       (slicePinOut[63:32]),
        .pinDir       (slicePinDir[63:32])
    );

    wire unusedSignals = &{memReadData, status, active, 1'b0};

endmodule
