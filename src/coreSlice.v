`default_nettype none

module coreSlice #(
    parameter configWidth = 91
) (
    input  wire                   clk,
    input  wire                   rstN,
    input  wire                   run,
    input  wire                   restart,
    input  wire [configWidth-1:0] coreConfig,
    input  wire [31:0]            pinsIn,
    input  wire [7:0]             memAddr,
    input  wire                   memWriteEn,
    input  wire [15:0]            memWriteData,
    output wire [15:0]            memReadData,
    output wire                   ownsMem,
    output wire                   active,
    input  wire                   hostExecEn,
    input  wire [15:0]            hostExecInstr,
    input  wire                   txWriteEn,
    input  wire [15:0]            txWriteData,
    input  wire                   rxReadEn,
    output wire [15:0]            rxReadData,
    output wire [2:0]             txLevel,
    output wire [2:0]             rxLevel,
    output wire [15:0]            status,
    input  wire [7:0]             flags,
    output wire [7:0]             flagSets,
    output wire [7:0]             flagClears,
    output wire [31:0]            pinOut,
    output wire [31:0]            pinDir
);

    wire [7:0]  startPc;
    wire [15:0] clkDiv;
    wire [4:0]  outBase;
    wire [4:0]  outCount;
    wire [4:0]  setBase;
    wire [2:0]  setCount;
    wire [4:0]  sideBase;
    wire [1:0]  sideCount;
    wire        sideEn;
    wire        sidePinDir;
    wire [4:0]  inBase;
    wire [4:0]  jmpPin;
    wire        outShiftRight;
    wire        inShiftRight;
    wire        autoPull;
    wire        autoPush;
    wire [4:0]  pullThreshold;
    wire [4:0]  pushThreshold;
    wire [7:0]  wrapBottom;
    wire [7:0]  wrapTop;
    wire [7:0]  fetchAddr;

    assign {startPc, clkDiv, outBase, outCount, setBase, setCount, sideBase, sideCount, sideEn,
            sidePinDir, inBase, jmpPin, outShiftRight, inShiftRight, autoPull, autoPush,
            pullThreshold, pushThreshold, wrapBottom, wrapTop} = coreConfig;

    assign ownsMem = run | active;

    progMem #(
        .addrWidth(8),
        .dataWidth(16)
    ) progMemInst (
        .clk      (clk),
        .memEn    (1'b1),
        .addr     (ownsMem ? fetchAddr : memAddr),
        .writeData(memWriteData),
        .writeEn  (memWriteEn),
        .readData (memReadData)
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
        .pinsIn       (pinsIn),
        .active       (active),
        .fetchAddr    (fetchAddr),
        .fetchData    (memReadData),
        .hostExecEn   (hostExecEn),
        .hostExecInstr(hostExecInstr),
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
