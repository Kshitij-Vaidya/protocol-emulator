`default_nettype none

module fifo #(
    parameter dataWidth  = 16,
    parameter depth      = 4,
    parameter countWidth = $clog2(depth + 1)
) (
    input  wire                  clk,
    input  wire                  rstN,
    input  wire                  clear,
    input  wire                  pushEn,
    input  wire [dataWidth-1:0]  pushData,
    input  wire                  popEn,
    output wire [dataWidth-1:0]  headData,
    output wire                  empty,
    output wire                  full,
    output wire [countWidth-1:0] count
);

    localparam ptrWidth = $clog2(depth);

    localparam [countWidth-1:0] fullCount = depth;

    reg [dataWidth-1:0]  entries [0:depth-1];
    reg [ptrWidth-1:0]   readPtr;
    reg [ptrWidth-1:0]   writePtr;
    reg [countWidth-1:0] countQ;

    wire doPush = pushEn & ~full;
    wire doPop  = popEn & ~empty;

    assign headData = entries[readPtr];
    assign empty    = (countQ == {countWidth{1'b0}});
    assign full     = (countQ == fullCount);
    assign count    = countQ;

    always @(posedge clk) begin
        if (!rstN || clear) begin
            readPtr  <= {ptrWidth{1'b0}};
            writePtr <= {ptrWidth{1'b0}};
            countQ   <= {countWidth{1'b0}};
        end else begin
            if (doPush)
                writePtr <= writePtr + 1'b1;
            if (doPop)
                readPtr <= readPtr + 1'b1;
            if (doPush && !doPop)
                countQ <= countQ + 1'b1;
            else if (doPop && !doPush)
                countQ <= countQ - 1'b1;
        end
    end

    always @(posedge clk) begin
        if (!full)
            entries[writePtr] <= pushData;
    end

`ifdef FORMAL
    reg                  pastValid = 1'b0;
    reg [dataWidth-1:0]  model [0:depth-1];
    reg [countWidth-1:0] modelCount;

    wire [ptrWidth-1:0]   modelTail = modelCount - doPop;
    wire [countWidth-1:0] countNext = countQ + doPush - doPop;

    integer slot;

    always @(posedge clk) begin
        pastValid <= 1'b1;
        if (!rstN || clear) begin
            modelCount <= {countWidth{1'b0}};
        end else begin
            if (doPop)
                for (slot = 0; slot < depth - 1; slot = slot + 1)
                    model[slot] <= model[slot + 1];
            if (doPush)
                model[modelTail] <= pushData;
            modelCount <= countNext;
        end
    end

    always @(*) begin
        if (!pastValid)
            assume (!rstN);
        assert (depth == (1 << ptrWidth));
        if (pastValid) begin
            assert (countQ <= fullCount);
            assert (countQ == modelCount);
            assert (writePtr == readPtr + countQ[ptrWidth-1:0]);
            if (!empty)
                assert (headData == model[0]);
        end
    end

    genvar position;
    generate
        for (position = 0; position < depth; position = position + 1) begin : entryCheck
            wire [ptrWidth-1:0] slotPtr = readPtr + position;
            always @(*)
                if (pastValid && position < countQ)
                    assert (entries[slotPtr] == model[position]);
        end
    endgenerate

    wire active = pastValid && rstN && !clear;

    always @(*) begin
        cover (active && full && pushEn && popEn);
        cover (active && empty && popEn);
        cover (active && doPush && doPop && countQ == 2);
    end
`endif

endmodule
