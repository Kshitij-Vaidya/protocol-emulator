`default_nettype none

module core (
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
    output wire        active,
    output wire [7:0]  fetchAddr,
    input  wire [15:0] fetchData,
    input  wire        hostExecEn,
    input  wire [15:0] hostExecInstr,
    input  wire        txWriteEn,
    input  wire [15:0] txWriteData,
    input  wire        rxReadEn,
    output wire [15:0] rxReadData,
    output wire [2:0]  txLevel,
    output wire [2:0]  rxLevel,
    output wire [15:0] status,
    input  wire [7:0]  flags,
    output reg  [7:0]  flagSets,
    output reg  [7:0]  flagClears,
    output reg  [31:0] pinOut,
    output reg  [31:0] pinDir
);

    localparam dataWidth = 16;
    localparam pinWidth  = 32;

    localparam [2:0] opJmp      = 3'd0;
    localparam [2:0] opWait     = 3'd1;
    localparam [2:0] opIn       = 3'd2;
    localparam [2:0] opOut      = 3'd3;
    localparam [2:0] opPushPull = 3'd4;
    localparam [2:0] opMov      = 3'd5;
    localparam [2:0] opSet      = 3'd6;
    localparam [2:0] opFlag     = 3'd7;

    localparam [4:0] fullCount = 5'd16;

    reg                 activeQ;
    reg [15:0]          divCount;
    reg [3:0]           delayCount;
    reg [7:0]           pc;
    reg [dataWidth-1:0] x;
    reg [dataWidth-1:0] y;
    reg [dataWidth-1:0] t;
    reg [dataWidth-1:0] isr;
    reg [dataWidth-1:0] osr;
    reg [4:0]           isrCount;
    reg [4:0]           osrCount;
    reg [dataWidth-1:0] waitTicks;
    reg [dataWidth-1:0] pendingExec;
    reg                 pendingExecValid;
    reg                 isStalled;
    reg                 timeoutFlag;

    reg [7:0]           pcNext;
    reg [dataWidth-1:0] xNext;
    reg [dataWidth-1:0] yNext;
    reg [dataWidth-1:0] tNext;
    reg [dataWidth-1:0] isrNext;
    reg [dataWidth-1:0] osrNext;
    reg [4:0]           isrCountNext;
    reg [4:0]           osrCountNext;
    reg [dataWidth-1:0] waitTicksNext;
    reg [dataWidth-1:0] pendingExecNext;
    reg                 pendingExecValidNext;
    reg                 isStalledNext;
    reg                 timeoutFlagNext;
    reg [3:0]           delayCountNext;
    reg [pinWidth-1:0]  pinOutNext;
    reg [pinWidth-1:0]  pinDirNext;
    reg                 complete;
    reg                 jumpEn;
    reg [7:0]           jumpTarget;
    reg                 execSet;
    reg                 txPop;
    reg                 rxPush;
    reg [dataWidth-1:0] rxPushData;

    wire                 txEmpty;
    wire                 txFull;
    wire                 rxEmpty;
    wire                 rxFull;
    wire [dataWidth-1:0] txHead;

    wire                 hostExec  = hostExecEn && !activeQ;
    wire                 tick      = activeQ && (divCount == 16'd0);
    wire                 halting   = activeQ && !run;
    wire [15:0]          divLimit  = (clkDiv == 16'd0) ? 16'd0 : clkDiv - 1'b1;
    wire                 execute   = (tick && (delayCount == 4'd0)) || hostExec;
    wire                 stalled   = isStalled && !hostExec;
    wire [dataWidth-1:0] coreInstr = pendingExecValid ? pendingExec : fetchData;
    wire [dataWidth-1:0] instr     = hostExec ? hostExecInstr : coreInstr;
    wire [2:0]           opcode    = instr[15:13];
    wire [3:0]           timing    = instr[12:9];
    wire [8:0]           ops       = instr[8:0];

    wire [2:0] delayBits  = 3'd4 - {1'b0, sideCount} - {2'b0, sideEn};
    wire [3:0] delay      = timing & ~(4'hF << delayBits);
    wire       sideActive = (sideCount != 2'd0) && (!sideEn || timing[3]);
    wire [3:0] sideValue  = (timing >> delayBits) & ~(4'hF << sideCount);

    wire [4:0]           bitCount  = (ops[3:0] == 4'd0) ? fullCount : {1'b0, ops[3:0]};
    wire [dataWidth-1:0] countMask = ~({dataWidth{1'b1}} << bitCount);
    wire [5:0]           inSum     = {1'b0, isrCount} + {1'b0, bitCount};
    wire [4:0]           inSat     = (inSum > {1'b0, fullCount}) ? fullCount : inSum[4:0];
    wire                 pushDue   = autoPush && (inSat >= pushThreshold);
    wire                 refill    = autoPull && (osrCount >= pullThreshold);
    wire [dataWidth-1:0] osrSrc    = refill ? txHead : osr;
    wire [4:0]           osrBase   = refill ? 5'd0 : osrCount;
    wire [5:0]           outSum    = {1'b0, osrBase} + {1'b0, bitCount};
    wire [4:0]           outSat    = (outSum > {1'b0, fullCount}) ? fullCount : outSum[4:0];

    wire [31:0]          osrWide    = {16'b0, osrSrc};
    wire [31:0]          osrAligned = osrWide >> (fullCount - bitCount);
    wire [dataWidth-1:0] outData    = (outShiftRight ? osrSrc : osrAligned[15:0]) & countMask;
    wire [31:0]          osrShifted = outShiftRight ? (osrWide >> bitCount) : (osrWide << bitCount);

    wire [31:0]          pinsRotated = rotateRight(pinsIn, inBase);
    wire [dataWidth-1:0] pinsRead    = pinsRotated[15:0];
    wire [dataWidth-1:0] statusValue = {flags, 5'b0, timeoutFlag, rxFull, txEmpty};

    reg  [dataWidth-1:0] inSource;
    wire [dataWidth-1:0] inData     = inSource & countMask;
    wire [31:0]          isrWide    = {16'b0, isr};
    wire [31:0]          inAligned  = {16'b0, inData} << (fullCount - bitCount);
    wire [31:0]          inRight    = (isrWide >> bitCount) | inAligned;
    wire [31:0]          inLeft     = (isrWide << bitCount) | {16'b0, inData};
    wire [dataWidth-1:0] isrShifted = inShiftRight ? inRight[15:0] : inLeft[15:0];

    reg  [dataWidth-1:0] movSource;
    reg  [dataWidth-1:0] aluFirst;
    reg  [dataWidth-1:0] movResult;
    wire [dataWidth-1:0] movReversed;
    wire                 aluSubtract = ops[5];
    wire [dataWidth-1:0] aluSum      = prefixAdd(aluFirst, aluSubtract ? ~movSource : movSource, aluSubtract);

    reg                  jmpTaken;
    reg                  waitLevel;
    wire [dataWidth-1:0] waitStart = stalled ? waitTicks : t;
    wire [4:0]           setWidth  = {2'b0, setCount};
    wire [dataWidth-1:0] setData   = {10'b0, ops[5:0]};

    wire                 pinWriteSet   = (opcode == opSet);
    wire [4:0]           pinWriteBase  = pinWriteSet ? setBase : outBase;
    wire [4:0]           pinWriteCount = pinWriteSet ? setWidth : outCount;
    wire [dataWidth-1:0] pinWriteValue = pinWriteSet ? setData : (opcode == opOut) ? outData : movResult;

    genvar bitIdx;
    generate
        for (bitIdx = 0; bitIdx < dataWidth; bitIdx = bitIdx + 1) begin : reverseBits
            assign movReversed[bitIdx] = movSource[dataWidth-1-bitIdx];
        end
    endgenerate

    function [31:0] rotateLeft;
        input [31:0] value;
        input [4:0]  amount;
        begin
            rotateLeft = (value << amount) | (value >> (6'd32 - {1'b0, amount}));
        end
    endfunction

    function [31:0] rotateRight;
        input [31:0] value;
        input [4:0]  amount;
        begin
            rotateRight = (value >> amount) | (value << (6'd32 - {1'b0, amount}));
        end
    endfunction

    function [15:0] prefixAdd;
        input [15:0] first;
        input [15:0] second;
        input        carryIn;
        reg   [15:0] groupGen;
        reg   [15:0] groupProp;
        reg   [15:0] carries;
        integer      span;
        integer      bitPos;
        begin
            groupGen  = first & second;
            groupProp = first ^ second;
            groupGen[0] = groupGen[0] | (groupProp[0] & carryIn);
            for (span = 1; span < 16; span = span * 2)
                for (bitPos = 15; bitPos >= span; bitPos = bitPos - 1) begin
                    groupGen[bitPos]  = groupGen[bitPos] | (groupProp[bitPos] & groupGen[bitPos-span]);
                    groupProp[bitPos] = groupProp[bitPos] & groupProp[bitPos-span];
                end
            carries   = {groupGen[14:0], carryIn};
            prefixAdd = first ^ second ^ carries;
        end
    endfunction

    function [31:0] writeField;
        input [31:0] current;
        input [4:0]  base;
        input [4:0]  count;
        input [15:0] value;
        reg   [31:0] mask;
        begin
            mask       = rotateLeft(~(32'hFFFF_FFFF << count), base);
            writeField = (current & ~mask) | (rotateLeft({16'b0, value}, base) & mask);
        end
    endfunction

    fifo #(
        .dataWidth(dataWidth),
        .depth    (4)
    ) txFifo (
        .clk     (clk),
        .rstN    (rstN),
        .clear   (restart),
        .pushEn  (txWriteEn),
        .pushData(txWriteData),
        .popEn   (txPop),
        .headData(txHead),
        .empty   (txEmpty),
        .full    (txFull),
        .count   (txLevel)
    );

    fifo #(
        .dataWidth(dataWidth),
        .depth    (4)
    ) rxFifo (
        .clk     (clk),
        .rstN    (rstN),
        .clear   (restart),
        .pushEn  (rxPush),
        .pushData(rxPushData),
        .popEn   (rxReadEn),
        .headData(rxReadData),
        .empty   (rxEmpty),
        .full    (rxFull),
        .count   (rxLevel)
    );

    assign active    = activeQ;
    assign fetchAddr = activeQ ? pcNext : pc;
    assign status    = statusValue;

    always @(*) begin
        case (ops[8:6])
            3'd0:    jmpTaken = 1'b1;
            3'd1:    jmpTaken = (x == 16'd0);
            3'd2:    jmpTaken = (x != 16'd0);
            3'd3:    jmpTaken = (y != 16'd0);
            3'd4:    jmpTaken = (x != y);
            3'd5:    jmpTaken = pinsIn[jmpPin];
            3'd6:    jmpTaken = (osrCount < pullThreshold);
            default: jmpTaken = timeoutFlag;
        endcase
    end

    always @(*) begin
        case (ops[7:6])
            2'd0:    waitLevel = pinsIn[ops[4:0]];
            2'd1:    waitLevel = pinsIn[inBase + ops[4:0]];
            2'd2:    waitLevel = flags[ops[2:0]];
            default: waitLevel = 1'b0;
        endcase
    end

    always @(*) begin
        case (ops[8:6])
            3'd0:    inSource = pinsRead;
            3'd1:    inSource = x;
            3'd2:    inSource = y;
            3'd6:    inSource = isr;
            3'd7:    inSource = osr;
            default: inSource = 16'd0;
        endcase
    end

    always @(*) begin
        case (ops[2:0])
            3'd0:    movSource = pinsRead;
            3'd1:    movSource = x;
            3'd2:    movSource = y;
            3'd3:    movSource = 16'd0;
            3'd4:    movSource = statusValue;
            3'd5:    movSource = isr;
            3'd6:    movSource = osr;
            default: movSource = t;
        endcase
    end

    always @(*) begin
        case (ops[8:6])
            3'd1:    aluFirst = x;
            3'd2:    aluFirst = y;
            3'd3:    aluFirst = t;
            default: aluFirst = 16'd0;
        endcase
    end

    always @(*) begin
        case (ops[5:3])
            3'd0:    movResult = movSource;
            3'd1:    movResult = ~movSource;
            3'd2:    movResult = movReversed;
            3'd3,
            3'd4:    movResult = aluSum;
            3'd5:    movResult = aluFirst & movSource;
            3'd6:    movResult = aluFirst | movSource;
            default: movResult = aluFirst ^ movSource;
        endcase
    end

    always @(*) begin
        pcNext               = pc;
        xNext                = x;
        yNext                = y;
        tNext                = t;
        isrNext              = isr;
        osrNext              = osr;
        isrCountNext         = isrCount;
        osrCountNext         = osrCount;
        waitTicksNext        = waitTicks;
        pendingExecNext      = pendingExec;
        pendingExecValidNext = pendingExecValid;
        isStalledNext        = isStalled;
        timeoutFlagNext      = timeoutFlag;
        delayCountNext       = delayCount;
        flagSets             = 8'd0;
        flagClears           = 8'd0;
        pinOutNext           = pinOut;
        pinDirNext           = pinDir;
        complete             = 1'b0;
        jumpEn               = 1'b0;
        jumpTarget           = pc + {{2{ops[5]}}, ops[5:0]};
        execSet              = 1'b0;
        txPop                = 1'b0;
        rxPush               = 1'b0;
        rxPushData           = isr;

        if (tick && delayCount != 4'd0) begin
            delayCountNext = delayCount - 1'b1;
        end else if (execute) begin
            if (sideActive && sidePinDir)
                pinDirNext = writeField(pinDir, sideBase, {3'b0, sideCount}, {12'b0, sideValue});
            else if (sideActive)
                pinOutNext = writeField(pinOut, sideBase, {3'b0, sideCount}, {12'b0, sideValue});

            case (opcode)
                opJmp: begin
                    complete = 1'b1;
                    jumpEn   = jmpTaken;
                    if (ops[8:6] == 3'd2)
                        xNext = x - 1'b1;
                    if (ops[8:6] == 3'd3)
                        yNext = y - 1'b1;
                end
                opWait: begin
                    if (!stalled)
                        timeoutFlagNext = 1'b0;
                    if (waitLevel == ops[8]) begin
                        complete = 1'b1;
                        if (ops[7:6] == 2'd2 && ops[8])
                            flagClears[ops[2:0]] = 1'b1;
                    end else if (ops[5]) begin
                        if (waitStart == 16'd0) begin
                            complete        = 1'b1;
                            timeoutFlagNext = 1'b1;
                        end else begin
                            waitTicksNext = waitStart - 1'b1;
                        end
                    end
                end
                opIn: begin
                    if (!(pushDue && rxFull)) begin
                        complete = 1'b1;
                        if (pushDue) begin
                            rxPush       = 1'b1;
                            rxPushData   = isrShifted;
                            isrNext      = 16'd0;
                            isrCountNext = 5'd0;
                        end else begin
                            isrNext      = isrShifted;
                            isrCountNext = inSat;
                        end
                    end
                end
                opOut: begin
                    if (!(refill && txEmpty)) begin
                        complete     = 1'b1;
                        txPop        = refill;
                        osrNext      = osrShifted[15:0];
                        osrCountNext = outSat;
                        case (ops[8:6])
                            3'd0: pinOutNext = writeField(pinOutNext, pinWriteBase, pinWriteCount, pinWriteValue);
                            3'd1: xNext = outData;
                            3'd2: yNext = outData;
                            3'd4: pinDirNext = writeField(pinDirNext, pinWriteBase, pinWriteCount, pinWriteValue);
                            3'd5: begin
                                jumpEn     = 1'b1;
                                jumpTarget = outData[7:0];
                            end
                            3'd6: begin
                                isrNext      = outData;
                                isrCountNext = bitCount;
                            end
                            3'd7: begin
                                execSet         = 1'b1;
                                pendingExecNext = outData;
                            end
                            default: ;
                        endcase
                    end
                end
                opPushPull: begin
                    if (!ops[8]) begin
                        if (ops[7] && isrCount < pushThreshold) begin
                            complete = 1'b1;
                        end else if (!rxFull) begin
                            complete     = 1'b1;
                            rxPush       = 1'b1;
                            isrNext      = 16'd0;
                            isrCountNext = 5'd0;
                        end else if (!ops[6]) begin
                            complete     = 1'b1;
                            isrNext      = 16'd0;
                            isrCountNext = 5'd0;
                        end
                    end else begin
                        if (ops[7] && osrCount < pullThreshold) begin
                            complete = 1'b1;
                        end else if (!txEmpty) begin
                            complete     = 1'b1;
                            txPop        = 1'b1;
                            osrNext      = txHead;
                            osrCountNext = 5'd0;
                        end else if (!ops[6]) begin
                            complete     = 1'b1;
                            osrNext      = x;
                            osrCountNext = 5'd0;
                        end
                    end
                end
                opMov: begin
                    complete = 1'b1;
                    case (ops[8:6])
                        3'd0: pinOutNext = writeField(pinOutNext, pinWriteBase, pinWriteCount, pinWriteValue);
                        3'd1: xNext = movResult;
                        3'd2: yNext = movResult;
                        3'd3: tNext = movResult;
                        3'd4: begin
                            execSet         = 1'b1;
                            pendingExecNext = movResult;
                        end
                        3'd5: begin
                            jumpEn     = 1'b1;
                            jumpTarget = movResult[7:0];
                        end
                        3'd6: begin
                            isrNext      = movResult;
                            isrCountNext = 5'd0;
                        end
                        default: begin
                            osrNext      = movResult;
                            osrCountNext = 5'd0;
                        end
                    endcase
                end
                opSet: begin
                    complete = 1'b1;
                    case (ops[8:6])
                        3'd0: pinOutNext = writeField(pinOutNext, pinWriteBase, pinWriteCount, pinWriteValue);
                        3'd1: xNext = setData;
                        3'd2: yNext = setData;
                        3'd3: tNext = setData;
                        3'd4: pinDirNext = writeField(pinDirNext, pinWriteBase, pinWriteCount, pinWriteValue);
                        default: ;
                    endcase
                end
                opFlag: begin
                    case (ops[8:7])
                        2'd0: begin
                            complete           = 1'b1;
                            flagSets[ops[2:0]] = 1'b1;
                        end
                        2'd1: begin
                            complete             = 1'b1;
                            flagClears[ops[2:0]] = 1'b1;
                        end
                        2'd2: begin
                            if (!stalled)
                                flagSets[ops[2:0]] = 1'b1;
                            else
                                complete = !flags[ops[2:0]];
                        end
                        default: complete = 1'b1;
                    endcase
                end
                default: ;
            endcase

            if (hostExec) begin
                if (complete && jumpEn)
                    pcNext = jumpTarget;
                if (complete && execSet)
                    pendingExecValidNext = 1'b1;
            end else if (complete) begin
                isStalledNext        = 1'b0;
                pendingExecValidNext = execSet;
                delayCountNext       = execSet ? 4'd0 : delay;
                if (jumpEn)
                    pcNext = jumpTarget;
                else if (!pendingExecValid)
                    pcNext = (pc == wrapTop) ? wrapBottom : pc + 1'b1;
            end else begin
                isStalledNext = 1'b1;
            end
        end
    end

    always @(posedge clk) begin
        if (!rstN || restart) begin
            activeQ          <= 1'b0;
            divCount         <= 16'd0;
            delayCount       <= 4'd0;
            pc               <= rstN ? startPc : 8'd0;
            x                <= 16'd0;
            y                <= 16'd0;
            t                <= 16'd0;
            isr              <= 16'd0;
            osr              <= 16'd0;
            isrCount         <= 5'd0;
            osrCount         <= fullCount;
            waitTicks        <= 16'd0;
            pendingExec      <= 16'd0;
            pendingExecValid <= 1'b0;
            isStalled        <= 1'b0;
            timeoutFlag      <= 1'b0;
            pinOut           <= 32'd0;
            pinDir           <= 32'd0;
        end else begin
            activeQ          <= run;
            divCount         <= (!activeQ || divCount >= divLimit) ? 16'd0 : divCount + 1'b1;
            delayCount       <= delayCountNext;
            pc               <= pcNext;
            x                <= xNext;
            y                <= yNext;
            t                <= tNext;
            isr              <= isrNext;
            osr              <= osrNext;
            isrCount         <= isrCountNext;
            osrCount         <= osrCountNext;
            waitTicks        <= waitTicksNext;
            pendingExec      <= pendingExecNext;
            pendingExecValid <= pendingExecValidNext;
            isStalled        <= isStalledNext;
            timeoutFlag      <= timeoutFlagNext;
            pinOut           <= pinOutNext;
            pinDir           <= pinDirNext;
            if (halting) begin
                delayCount       <= 4'd0;
                isStalled        <= 1'b0;
                pendingExecValid <= 1'b0;
            end
        end
    end

`ifdef FORMAL
    reg pastValid = 1'b0;

    always @(posedge clk)
        pastValid <= 1'b1;

    wire running = pastValid && rstN && !restart;

    always @(*) begin
        if (!pastValid)
            assume (!rstN);
        assert (!(hostExec && tick));
        assert (execute || (flagSets == 8'd0 && flagClears == 8'd0));
        if (running) begin
            assert (isrCount <= fullCount);
            assert (osrCount <= fullCount);
        end
    end

    always @(posedge clk) begin
        if (pastValid) begin
            if ($past(!rstN))
                assert (pc == 8'd0 && !activeQ && !isStalled && !pendingExecValid);
            if ($past(rstN && restart))
                assert (pc == $past(startPc) && !activeQ && delayCount == 4'd0 && !isStalled
                        && !pendingExecValid && pinDir == 32'd0);
            if ($past(running) && $stable(clkDiv))
                assert (!activeQ || divCount <= divLimit);
            if ($past(running && halting))
                assert (!isStalled && delayCount == 4'd0 && !pendingExecValid);
            if ($past(running && !execute && !halting)) begin
                assert ($stable(pc) && $stable(x) && $stable(y) && $stable(t));
                assert ($stable(isr) && $stable(osr) && $stable(isrCount) && $stable(osrCount));
                assert ($stable(pinOut) && $stable(pinDir));
                assert ($stable(pendingExecValid) && $stable(isStalled));
            end
            if ($past(running && tick && delayCount != 4'd0 && !halting))
                assert (delayCount == $past(delayCount) - 4'd1);
            if ($past(running && !tick && !execute && !halting))
                assert ($stable(delayCount));
            if ($past(running && execute && !hostExec) && isStalled)
                assert ($stable(pc) && delayCount == 4'd0);
            if ($past(running && execute && !hostExec && complete && !jumpEn && !pendingExecValid))
                assert (pc == (($past(pc) == $past(wrapTop)) ? $past(wrapBottom) : $past(pc) + 8'd1));
        end
    end

    always @(*) begin
        cover (running && isStalled && delayCount == 4'd0 && activeQ);
        cover (running && pendingExecValid);
        cover (running && delayCount == 4'd15);
    end
`endif

    wire unusedSignals = &{
        txFull,
        rxEmpty,
        osrShifted[31:16],
        pinsRotated[31:16],
        osrAligned[31:16],
        inRight[31:16],
        inLeft[31:16],
        1'b0
    };

endmodule
