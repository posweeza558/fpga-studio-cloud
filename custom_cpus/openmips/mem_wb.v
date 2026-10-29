/*
 * @Author: Groot
 * @Date: 2022-04-09 18:01:23
 * @LastEditTime: 2022-05-03 21:58:11
 * @LastEditors: Groot
 * @Description:
 * @FilePath: /openMIPS/vsrc/mem_wb.v
 * 版权声明
 */
`include "define.v"

module mem_wb (input wire clk,
               input wire rst,
               input wire[5:0] stall,
               input wire[`RegAddBus] mem_wd,
               input wire mem_wreg,
               input wire[`RegBus] mem_wdata,
               output reg[`RegAddBus] wb_wd,
               output reg wb_wreg,
               output reg[`RegBus] wb_wdata,

               input wire mem_whilo,
               input wire[`RegBus] mem_hi,
               input wire[`RegBus] mem_lo,

               output reg wb_whilo,
               output reg[`RegBus] wb_hi,
               output reg[`RegBus] wb_lo
               );
    
    always @(posedge clk) begin
        if (rst == `RstEnable) begin
            wb_wd    <= `NOPRegAddr;
            wb_wreg  <= `WriteDisable;
            wb_wdata <= `ZeroWord;
            wb_whilo <= `WriteDisable;
            wb_hi    <= `ZeroWord;
		    wb_lo    <= `ZeroWord;
        end
        else if (stall[4] == `Stop && stall[5] == `NoStop) begin
            wb_wd    <= `NOPRegAddr;
            wb_wreg  <= `WriteDisable;
            wb_wdata <= `ZeroWord;
            wb_whilo <= `WriteDisable;
            wb_hi    <= `ZeroWord;
		    wb_lo    <= `ZeroWord;
        end
        else if (stall[4] == `NoStop) begin
            wb_wd    <= mem_wd;
            wb_wreg  <= mem_wreg;
            wb_wdata <= mem_wdata;
            wb_whilo <= mem_whilo;
            wb_hi    <= mem_hi;
            wb_lo    <= mem_lo;
        end
    end
    
endmodule //mem_wb
