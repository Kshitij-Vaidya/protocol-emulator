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

    localparam numCores    = 2;
    localparam dataWidth   = 16;
    localparam pinWidth    = 32;
    localparam configWidth = 91;

    wire [pinWidth-1:0]             pinsIn = {12'd0, ui_in[7:3], 7'd0, uio_in};
    wire [pinWidth-1:0]             pinsSynced;
    wire [pinWidth-1:0]             syncBypass;

    wire                            miso;
    wire [numCores-1:0]             run;
    wire [numCores-1:0]             restart;
    wire [numCores*configWidth-1:0] coreConfig;
    wire [numCores-1:0]             hostExecEn;
    wire [dataWidth-1:0]            hostExecInstr;
    wire [numCores*8-1:0]           memAddr;
    wire [numCores-1:0]             memWriteEn;
    wire [dataWidth-1:0]            memWriteData;
    wire [numCores*dataWidth-1:0]   memReadData;
    wire [numCores-1:0]             txWriteEn;
    wire [dataWidth-1:0]            txWriteData;
    wire [numCores*3-1:0]           txLevel;
    wire [numCores-1:0]             rxReadEn;
    wire [numCores*dataWidth-1:0]   rxReadData;
    wire [numCores*3-1:0]           rxLevel;
    wire [numCores-1:0]             ownsMem;
    wire [numCores-1:0]             active;
    wire [numCores*dataWidth-1:0]   status;
    wire [numCores*pinWidth-1:0]    pinOut;
    wire [numCores*pinWidth-1:0]    pinDir;
    wire [numCores*8-1:0]           flagSets;
    wire [numCores*8-1:0]           flagClears;
    wire [7:0]                      flags;

    wire [pinWidth-1:0] pinOutAll = pinOut[0 +: pinWidth] | pinOut[pinWidth +: pinWidth];
    wire [pinWidth-1:0] pinDirAll = pinDir[0 +: pinWidth] | pinDir[pinWidth +: pinWidth];

    pinSync #(
        .width(pinWidth)
    ) pinSyncInst (
        .clk    (clk),
        .rstN   (rst_n),
        .pinsIn (pinsIn),
        .bypass (syncBypass),
        .pinsOut(pinsSynced)
    );

    flagBank #(
        .width(8)
    ) flagBankInst (
        .clk   (clk),
        .rstN  (rst_n),
        .clear (|restart),
        .sets  (flagSets[0 +: 8] | flagSets[8 +: 8]),
        .clears(flagClears[0 +: 8] | flagClears[8 +: 8]),
        .flags (flags)
    );

    hostSpi #(
        .numCores   (numCores),
        .configWidth(configWidth)
    ) hostSpiInst (
        .clk          (clk),
        .rstN         (rst_n),
        .sck          (ui_in[0]),
        .csN          (ui_in[1]),
        .mosi         (ui_in[2]),
        .miso         (miso),
        .coreOwnsMem  (ownsMem),
        .active       (active),
        .flags        (flags),
        .run          (run),
        .restart      (restart),
        .coreConfig   (coreConfig),
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

    coreSlice #(
        .configWidth(configWidth)
    ) coreSlice0 (
        .clk          (clk),
        .rstN         (rst_n),
        .run          (run[0]),
        .restart      (restart[0]),
        .coreConfig   (coreConfig[0 +: configWidth]),
        .pinsIn       (pinsSynced),
        .memAddr      (memAddr[0 +: 8]),
        .memWriteEn   (memWriteEn[0]),
        .memWriteData (memWriteData),
        .memReadData  (memReadData[0 +: dataWidth]),
        .ownsMem      (ownsMem[0]),
        .active       (active[0]),
        .hostExecEn   (hostExecEn[0]),
        .hostExecInstr(hostExecInstr),
        .txWriteEn    (txWriteEn[0]),
        .txWriteData  (txWriteData),
        .rxReadEn     (rxReadEn[0]),
        .rxReadData   (rxReadData[0 +: dataWidth]),
        .txLevel      (txLevel[0 +: 3]),
        .rxLevel      (rxLevel[0 +: 3]),
        .status       (status[0 +: dataWidth]),
        .flags        (flags),
        .flagSets     (flagSets[0 +: 8]),
        .flagClears   (flagClears[0 +: 8]),
        .pinOut       (pinOut[0 +: pinWidth]),
        .pinDir       (pinDir[0 +: pinWidth])
    );

    coreSlice #(
        .configWidth(configWidth)
    ) coreSlice1 (
        .clk          (clk),
        .rstN         (rst_n),
        .run          (run[1]),
        .restart      (restart[1]),
        .coreConfig   (coreConfig[configWidth +: configWidth]),
        .pinsIn       (pinsSynced),
        .memAddr      (memAddr[8 +: 8]),
        .memWriteEn   (memWriteEn[1]),
        .memWriteData (memWriteData),
        .memReadData  (memReadData[dataWidth +: dataWidth]),
        .ownsMem      (ownsMem[1]),
        .active       (active[1]),
        .hostExecEn   (hostExecEn[1]),
        .hostExecInstr(hostExecInstr),
        .txWriteEn    (txWriteEn[1]),
        .txWriteData  (txWriteData),
        .rxReadEn     (rxReadEn[1]),
        .rxReadData   (rxReadData[dataWidth +: dataWidth]),
        .txLevel      (txLevel[3 +: 3]),
        .rxLevel      (rxLevel[3 +: 3]),
        .status       (status[dataWidth +: dataWidth]),
        .flags        (flags),
        .flagSets     (flagSets[8 +: 8]),
        .flagClears   (flagClears[8 +: 8]),
        .pinOut       (pinOut[pinWidth +: pinWidth]),
        .pinDir       (pinDir[pinWidth +: pinWidth])
    );

    assign uo_out  = {pinOutAll[14:8], miso};
    assign uio_out = pinOutAll[7:0];
    assign uio_oe  = pinDirAll[7:0];

    wire unusedSignals = &{ena, status, pinOutAll[31:15], pinDirAll[31:8], 1'b0};

endmodule
