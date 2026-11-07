`default_nettype none

module progMem #(
    parameter addrWidth = 8,
    parameter dataWidth = 16
) (
    input  wire                 clk,
    input  wire                 memEn,
    input  wire [addrWidth-1:0] addr,
    input  wire [dataWidth-1:0] writeData,
    input  wire                 writeEn,
    output wire [dataWidth-1:0] readData
);

    RM_IHPSG13_1P_256x16_c2_bm_bist sram (
        .A_CLK      (clk),
        .A_MEN      (memEn),
        .A_WEN      (writeEn),
        .A_REN      (~writeEn),
        .A_ADDR     (addr),
        .A_DIN      (writeData),
        .A_DLY      (1'b1),
        .A_DOUT     (readData),
        .A_BM       ({dataWidth{1'b1}}),
        .A_BIST_CLK (1'b0),
        .A_BIST_EN  (1'b0),
        .A_BIST_MEN (1'b0),
        .A_BIST_WEN (1'b0),
        .A_BIST_REN (1'b0),
        .A_BIST_ADDR({addrWidth{1'b0}}),
        .A_BIST_DIN ({dataWidth{1'b0}}),
        .A_BIST_BM  ({dataWidth{1'b0}})
    );

endmodule
