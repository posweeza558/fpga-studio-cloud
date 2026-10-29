/*
 * @Author: Groot
 * @Date: 2022-04-09 18:01:23
 * @LastEditTime: 2022-05-13 10:52:25
 * @LastEditors: Groot
 * @Description:
 * @FilePath: /openMIPS/vsrc/id_ex.v
 * 版权声明
 */
`include "define.v"

module id_ex (input wire clk,
              input wire rst,
              input wire[`AluOpBus] id_aluop,
              input wire [`AluSelBus] id_alusel,
              input wire[`RegBus] id_reg1,
              input wire[`RegBus] id_reg2,
              input wire[`RegAddBus] id_wd,
              input wire id_wreg,
              input wire[5:0] stall,
              input wire id_is_in_delayslot,
              input wire[`RegBus] id_link_address,
              input wire next_inst_in_delayslot_i,
              input wire[`RegBus] id_inst,
              output reg[`AluOpBus] ex_aluop,
              output reg[`AluSelBus] ex_alusel,
              output reg[`RegBus] ex_reg1,
              output reg[`RegBus] ex_reg2,
              output reg[`RegAddBus] ex_wd,
              output reg ex_wreg,
              output reg ex_is_in_delayslot,
              output reg[`RegBus] ex_link_address,
              output reg is_in_delayslot_o,
              output reg[`RegBus] ex_inst);
    
    always @(posedge clk)
    begin
        if (rst == `RstEnable) begin
            ex_aluop  <= `EXE_NOP_OP;
            ex_alusel <= `EXE_RES_NOP;
            ex_reg1   <= `ZeroWord;
            ex_reg2   <= `ZeroWord;
            ex_wd     <= `NOPRegAddr;
            ex_wreg   <= `WriteDisable;
            ex_is_in_delayslot  <= `NotInDelaySlot;
            ex_link_address     <= `ZeroWord;
            is_in_delayslot_o   <= `NotInDelaySlot;
            ex_inst   <= `ZeroWord;
        end
        else if (stall[2] == `Stop && stall[3] == `NoStop) begin
            ex_aluop  <= `EXE_NOP_OP;
            ex_alusel <= `EXE_RES_NOP;
            ex_reg1   <= `ZeroWord;
            ex_reg2   <= `ZeroWord;
            ex_wd     <= `NOPRegAddr;
            ex_wreg   <= `WriteDisable;
            ex_inst   <= `ZeroWord;
        end
        else if (stall[2] == `NoStop) begin
            ex_aluop  <= id_aluop;
            ex_alusel <= id_alusel;
            ex_reg1   <= id_reg1;
            ex_reg2   <= id_reg2;
            ex_wd     <= id_wd;
            ex_wreg   <= id_wreg;
            ex_is_in_delayslot  <= id_is_in_delayslot;
            ex_link_address     <= id_link_address;
            is_in_delayslot_o   <= next_inst_in_delayslot_i;
            ex_inst   <= id_inst;
        end
    end
endmodule //id_ex
