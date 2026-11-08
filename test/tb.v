`default_nettype none
`timescale 1ns/1ps

module tb ();
    initial begin
        $dumpfile("tb.fst");
        $dumpvars(0, tb);
        #1;
    end

    reg        clk;
    reg        rst_n;
    reg        ena;
    reg        hostSck;
    reg        hostCsN;
    reg        hostMosi;
    reg        pin15;
    reg  [3:0] pins16To19;
    reg  [7:0] uio_in;
    wire [7:0] ui_in = {pins16To19, pin15, hostMosi, hostCsN, hostSck};
    wire [7:0] uo_out;
    wire [7:0] uio_out;
    wire [7:0] uio_oe;

    wire       hostMiso = uo_out[0];
    wire       pin8     = uo_out[1];

    tt_um_protocolEmulator user_project (
        .ui_in  (ui_in),
        .uo_out (uo_out),
        .uio_in (uio_in),
        .uio_out(uio_out),
        .uio_oe (uio_oe),
        .ena    (ena),
        .clk    (clk),
        .rst_n  (rst_n)
    );

endmodule
