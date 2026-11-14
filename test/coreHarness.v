`default_nettype none
`timescale 1ns/1ps

module coreHarness (
    input  wire        clk,
    input  wire        rstN,
    input  wire        run,
    input  wire        restart,
    input  wire [7:0]  startPc,
    input  wire [15:0] clkDiv,
    input  wire [4:0]  outBase,
    input  wire [4:0]  outCount,
    input  wire [4:0]  setBase,
    input  wire [2:0]  setCount,
    input  wire [4:0]  sideBase,
    input  wire [1:0]  sideCount,
    input  wire        sideEn,
    input  wire        sidePinDir,
    input  wire [4:0]  inBase,
    input  wire [4:0]  jmpPin,
    input  wire        outShiftRight,
    input  wire        inShiftRight,
    input  wire        autoPull,
    input  wire        autoPush,
    input  wire [4:0]  pullThreshold,
    input  wire [4:0]  pushThreshold,
    input  wire [7:0]  wrapBottom,
    input  wire [7:0]  wrapTop,
    input  wire [31:0] pinsIn,
    input  wire [31:0] syncBypass,
    input  wire        loadEn,
    input  wire [7:0]  loadAddr,
    input  wire [15:0] loadData,
    input  wire        txWriteEn,
    input  wire [15:0] txWriteData,
    input  wire        rxReadEn,
    output wire [15:0] rxReadData,
    output wire [2:0]  txLevel,
    output wire [2:0]  rxLevel,
    output wire [15:0] status,
    output wire        active,
    output wire [31:0] pinOut,
    output wire [31:0] pinDir
);

    initial begin
        $dumpfile("coreHarness.fst");
        $dumpvars(0, coreHarness);
    end

    wire [31:0] pinsSynced;
    wire [7:0]  fetchAddr;
    wire [15:0] fetchData;
    wire        coreOwnsMem = run | active;
    wire [7:0]  flags;
    wire [7:0]  flagSets;
    wire [7:0]  flagClears;

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
        .clear (restart),
        .sets  (flagSets),
        .clears(flagClears),
        .flags (flags)
    );

    progMem #(
        .addrWidth(8),
        .dataWidth(16)
    ) progMemInst (
        .clk      (clk),
        .memEn    (1'b1),
        .addr     (coreOwnsMem ? fetchAddr : loadAddr),
        .writeData(loadData),
        .writeEn  (loadEn & ~coreOwnsMem),
        .readData (fetchData)
    );

    core coreInst (
        .clk          (clk),
        .rstN         (rstN),
        .run          (run),
        .restart      (restart),
        .startPc      (startPc),
        .clkDiv       (clkDiv),
        .outBase      (outBase),
        .outCount     (outCount),
        .setBase      (setBase),
        .setCount     (setCount),
        .sideBase     (sideBase),
        .sideCount    (sideCount),
        .sideEn       (sideEn),
        .sidePinDir   (sidePinDir),
        .inBase       (inBase),
        .jmpPin       (jmpPin),
        .outShiftRight(outShiftRight),
        .inShiftRight (inShiftRight),
        .autoPull     (autoPull),
        .autoPush     (autoPush),
        .pullThreshold(pullThreshold),
        .pushThreshold(pushThreshold),
        .wrapBottom   (wrapBottom),
        .wrapTop      (wrapTop),
        .pinsIn       (pinsSynced),
        .active       (active),
        .fetchAddr    (fetchAddr),
        .fetchData    (fetchData),
        .hostExecEn   (1'b0),
        .hostExecInstr(16'd0),
        .txWriteEn    (txWriteEn),
        .txWriteData  (txWriteData),
        .rxReadEn     (rxReadEn),
        .rxReadData   (rxReadData),
        .txLevel      (txLevel),
        .rxLevel      (rxLevel),
        .status       (status),
        .flags        (flags),
        .flagSets     (flagSets),
        .flagClears   (flagClears),
        .pinOut       (pinOut),
        .pinDir       (pinDir)
    );

endmodule
