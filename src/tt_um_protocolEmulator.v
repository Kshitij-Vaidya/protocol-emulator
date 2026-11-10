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

    localparam addrWidth   = 8;
    localparam dataWidth   = 16;
    localparam pinWidth    = 32;
    localparam configWidth = 91;

    wire [pinWidth-1:0]    pinsIn = {12'd0, ui_in[7:3], 7'd0, uio_in};
    wire [pinWidth-1:0]    pinsSynced;
    wire [pinWidth-1:0]    syncBypass;

    wire                   miso;
    wire                   run;
    wire                   restart;
    wire                   coreSel;
    wire [7:0]             startPc;
    wire [15:0]            clkDiv;
    wire [4:0]             outBase;
    wire [4:0]             outCount;
    wire [4:0]             setBase;
    wire [2:0]             setCount;
    wire [4:0]             sideBase;
    wire [1:0]             sideCount;
    wire                   sideEn;
    wire                   sidePinDir;
    wire [4:0]             inBase;
    wire [4:0]             jmpPin;
    wire                   outShiftRight;
    wire                   inShiftRight;
    wire                   autoPull;
    wire                   autoPush;
    wire [4:0]             pullThreshold;
    wire [4:0]             pushThreshold;
    wire [7:0]             wrapBottom;
    wire [7:0]             wrapTop;
    wire                   hostExecEn;
    wire [dataWidth-1:0]   hostExecInstr;
    wire [addrWidth-1:0]   memAddr;
    wire                   memWriteEn;
    wire [dataWidth-1:0]   memWriteData;
    wire                   txWriteEn;
    wire [dataWidth-1:0]   txWriteData;
    wire                   rxReadEn;

    wire [configWidth-1:0] coreConfig = {startPc, clkDiv, outBase, outCount, setBase, setCount,
                                         sideBase, sideCount, sideEn, sidePinDir, inBase, jmpPin,
                                         outShiftRight, inShiftRight, autoPull, autoPush,
                                         pullThreshold, pushThreshold, wrapBottom, wrapTop};

    wire [1:0]             sliceSel = {coreSel, ~coreSel};
    wire [1:0]             ownsMem;
    wire [1:0]             active;
    wire [dataWidth-1:0]   memReadData [0:1];
    wire [dataWidth-1:0]   rxReadData  [0:1];
    wire [2:0]             txLevel     [0:1];
    wire [2:0]             rxLevel     [0:1];
    wire [dataWidth-1:0]   status      [0:1];
    wire [pinWidth-1:0]    pinOut      [0:1];
    wire [pinWidth-1:0]    pinDir      [0:1];

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
        .coreOwnsMem  (ownsMem[coreSel]),
        .active       (active[coreSel]),
        .flags        (status[coreSel][15:8]),
        .run          (run),
        .restart      (restart),
        .coreSel      (coreSel),
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
        .memReadData  (memReadData[coreSel]),
        .txWriteEn    (txWriteEn),
        .txWriteData  (txWriteData),
        .txLevel      (txLevel[coreSel]),
        .rxReadEn     (rxReadEn),
        .rxReadData   (rxReadData[coreSel]),
        .rxLevel      (rxLevel[coreSel])
    );

    coreSlice #(
        .configWidth(configWidth)
    ) coreSlice0 (
        .clk          (clk),
        .rstN         (rst_n),
        .run          (run & sliceSel[0]),
        .restart      (restart & sliceSel[0]),
        .coreConfig   (coreConfig),
        .pinsIn       (pinsSynced),
        .memAddr      (memAddr),
        .memWriteEn   (memWriteEn & sliceSel[0]),
        .memWriteData (memWriteData),
        .memReadData  (memReadData[0]),
        .ownsMem      (ownsMem[0]),
        .active       (active[0]),
        .hostExecEn   (hostExecEn & sliceSel[0]),
        .hostExecInstr(hostExecInstr),
        .txWriteEn    (txWriteEn & sliceSel[0]),
        .txWriteData  (txWriteData),
        .rxReadEn     (rxReadEn & sliceSel[0]),
        .rxReadData   (rxReadData[0]),
        .txLevel      (txLevel[0]),
        .rxLevel      (rxLevel[0]),
        .status       (status[0]),
        .pinOut       (pinOut[0]),
        .pinDir       (pinDir[0])
    );

    coreSlice #(
        .configWidth(configWidth)
    ) coreSlice1 (
        .clk          (clk),
        .rstN         (rst_n),
        .run          (run & sliceSel[1]),
        .restart      (restart & sliceSel[1]),
        .coreConfig   (coreConfig),
        .pinsIn       (pinsSynced),
        .memAddr      (memAddr),
        .memWriteEn   (memWriteEn & sliceSel[1]),
        .memWriteData (memWriteData),
        .memReadData  (memReadData[1]),
        .ownsMem      (ownsMem[1]),
        .active       (active[1]),
        .hostExecEn   (hostExecEn & sliceSel[1]),
        .hostExecInstr(hostExecInstr),
        .txWriteEn    (txWriteEn & sliceSel[1]),
        .txWriteData  (txWriteData),
        .rxReadEn     (rxReadEn & sliceSel[1]),
        .rxReadData   (rxReadData[1]),
        .txLevel      (txLevel[1]),
        .rxLevel      (rxLevel[1]),
        .status       (status[1]),
        .pinOut       (pinOut[1]),
        .pinDir       (pinDir[1])
    );

    wire [pinWidth-1:0] pinOutAll = pinOut[0] | pinOut[1];
    wire [pinWidth-1:0] pinDirAll = pinDir[0] | pinDir[1];

    assign uo_out  = {pinOutAll[14:8], miso};
    assign uio_out = pinOutAll[7:0];
    assign uio_oe  = pinDirAll[7:0];

    wire unusedSignals = &{ena, status[0][7:0], status[1][7:0], pinOutAll[31:15],
                           pinDirAll[31:8], 1'b0};

endmodule
