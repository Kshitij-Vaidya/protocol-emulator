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

    localparam addrWidth = 8;
    localparam dataWidth = 16;
    localparam pinWidth  = 32;

    wire [pinWidth-1:0]  pinsIn = {12'd0, ui_in[7:3], 7'd0, uio_in};
    wire [pinWidth-1:0]  pinsSynced;
    wire [pinWidth-1:0]  pinOut;
    wire [pinWidth-1:0]  pinDir;
    wire [pinWidth-1:0]  syncBypass;

    wire                 miso;
    wire                 run;
    wire                 restart;
    wire                 active;
    wire                 coreOwnsMem = run | active;
    wire [7:0]           startPc;
    wire [15:0]          clkDiv;
    wire [4:0]           outBase;
    wire [4:0]           outCount;
    wire [4:0]           setBase;
    wire [2:0]           setCount;
    wire [4:0]           sideBase;
    wire [1:0]           sideCount;
    wire                 sideEn;
    wire                 sidePinDir;
    wire [4:0]           inBase;
    wire [4:0]           jmpPin;
    wire                 outShiftRight;
    wire                 inShiftRight;
    wire                 autoPull;
    wire                 autoPush;
    wire [4:0]           pullThreshold;
    wire [4:0]           pushThreshold;
    wire [7:0]           wrapBottom;
    wire [7:0]           wrapTop;
    wire                 hostExecEn;
    wire [dataWidth-1:0] hostExecInstr;
    wire [addrWidth-1:0] memAddr;
    wire                 memWriteEn;
    wire [dataWidth-1:0] memWriteData;
    wire [addrWidth-1:0] fetchAddr;
    wire [dataWidth-1:0] memReadData;
    wire                 txWriteEn;
    wire [dataWidth-1:0] txWriteData;
    wire                 rxReadEn;
    wire [dataWidth-1:0] rxReadData;
    wire [2:0]           txLevel;
    wire [2:0]           rxLevel;
    wire [dataWidth-1:0] coreStatus;

    pinSync #(
        .width(pinWidth)
    ) pinSyncInst (
        .clk    (clk),
        .rstN   (rst_n),
        .pinsIn (pinsIn),
        .bypass (syncBypass),
        .pinsOut(pinsSynced)
    );

    hostSpi hostSpiInst (
        .clk          (clk),
        .rstN         (rst_n),
        .sck          (ui_in[0]),
        .csN          (ui_in[1]),
        .mosi         (ui_in[2]),
        .miso         (miso),
        .coreOwnsMem  (coreOwnsMem),
        .active       (active),
        .flags        (coreStatus[15:8]),
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
        .syncBypass   (syncBypass),
        .hostExecEn   (hostExecEn),
        .hostExecInstr(hostExecInstr),
        .memAddr      (memAddr),
        .memWriteEn   (memWriteEn),
        .memWriteData (memWriteData),
        .memReadData  (memReadData),
        .txWriteEn    (txWriteEn),
        .txWriteData  (txWriteData),
        .txLevel      (txLevel),
        .rxReadEn     (rxReadEn),
        .rxReadData   (rxReadData),
        .rxLevel      (rxLevel)
    );

    progMem #(
        .addrWidth(addrWidth),
        .dataWidth(dataWidth)
    ) progMemInst (
        .clk      (clk),
        .memEn    (1'b1),
        .addr     (coreOwnsMem ? fetchAddr : memAddr),
        .writeData(memWriteData),
        .writeEn  (memWriteEn),
        .readData (memReadData)
    );

    core coreInst (
        .clk          (clk),
        .rstN         (rst_n),
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
        .fetchData    (memReadData),
        .hostExecEn   (hostExecEn),
        .hostExecInstr(hostExecInstr),
        .txWriteEn    (txWriteEn),
        .txWriteData  (txWriteData),
        .rxReadEn     (rxReadEn),
        .rxReadData   (rxReadData),
        .txLevel      (txLevel),
        .rxLevel      (rxLevel),
        .status       (coreStatus),
        .pinOut       (pinOut),
        .pinDir       (pinDir)
    );

    assign uo_out  = {pinOut[14:8], miso};
    assign uio_out = pinOut[7:0];
    assign uio_oe  = pinDir[7:0];

    wire unusedSignals = &{ena, coreStatus[7:0], pinOut[31:15], pinDir[31:8], 1'b0};

endmodule
