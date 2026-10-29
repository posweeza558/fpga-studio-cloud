/*
 * @Author: Groot
 * @Date: 2022-04-09 18:01:23
 * @LastEditTime: 2022-05-13 11:23:41
 * @LastEditors: Groot
 * @Description:
 * @FilePath: /openMIPS/vsrc/ex_mem.v
 * 版权声明
 */
`include "define.v"

module ex_mem (input wire clk,
               input wire rst,
               input wire[5:0] stall,
               input wire[`RegAddBus] ex_wd,  //来自执行阶段的信息
               input wire ex_wreg,
               input wire[`RegBus] ex_wdata,
               output reg[`RegAddBus] mem_wd, //送到访存阶段的信息
               output reg mem_wreg,
               output reg[`RegBus] mem_wdata,
               input wire ex_whilo,
               input wire[`RegBus] ex_hi,
               input wire[`RegBus] ex_lo,
               output reg mem_whilo,
               output reg[`RegBus] mem_hi,
               output reg[`RegBus] mem_lo,
               input[`DoubleRegBus] hilo_i,
               input[1:0] cnt_i,
               output reg[`DoubleRegBus] hilo_o,
               output reg[1:0] cnt_o,
               input wire[`AluOpBus] ex_aluop,
               input wire[`RegBus] ex_mem_addr,
               input wire[`RegBus] ex_reg2,
               output reg[`AluOpBus] mem_aluop,
               output reg[`RegBus] mem_mem_addr,
               output reg[`RegBus] mem_reg2
               );
    
    always @(posedge clk) begin
        if (rst == `RstEnable) begin
            mem_wd    <= `NOPRegAddr;
            mem_wreg  <= `WriteDisable;
            mem_wdata <= `ZeroWord;
            mem_whilo <= `WriteDisable;
            mem_hi    <= `ZeroWord;
            mem_lo    <= `ZeroWord;
            hilo_o    <= {`ZeroWord, `ZeroWord};
            cnt_o     <= 2'b00;
            mem_aluop <= `EXE_NOP_OP;
            mem_mem_addr    <= `ZeroWord;
            mem_reg2  <= `ZeroWord;
        end
        else if (stall[3] == `Stop && stall[4] == `NoStop) begin
            mem_wd    <= `NOPRegAddr;
            mem_wreg  <= `WriteDisable;
            mem_wdata <= `ZeroWord;
            mem_whilo <= `WriteDisable;
            mem_hi    <= `ZeroWord;
            mem_lo    <= `ZeroWord;
            hilo_o    <= hilo_i;
            cnt_o     <= cnt_i;
            mem_aluop <= `EXE_NOP_OP;
            mem_mem_addr    <= `ZeroWord;
            mem_reg2  <= `ZeroWord; 
        end else if (stall[3] == `NoStop) begin
            mem_wd    <= ex_wd;
            mem_wreg  <= ex_wreg;
            mem_wdata <= ex_wdata;
            mem_whilo <= ex_whilo;
            mem_hi    <= ex_hi;
            mem_lo    <= ex_lo;
            hilo_o    <= {`ZeroWord, `ZeroWord};
            cnt_o     <= 2'b00;
            mem_aluop <= ex_aluop;
            mem_mem_addr    <= ex_mem_addr;
            mem_reg2  <= ex_reg2;
        end else begin
            hilo_o    <= hilo_i;
            cnt_o     <= cnt_i;   
        end
    end
    
    //来自执行阶段的信息
endmodule //ex_mem
