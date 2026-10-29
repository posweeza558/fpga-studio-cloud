/*
 * @Author: Groot
 * @Date: 2022-04-09 18:01:23
 * @LastEditTime: 2022-05-03 21:56:51
 * @LastEditors: Groot
 * @Description:
 * @FilePath: /openMIPS/vsrc/if_id.v
 * 版权声明
 */
`include "define.v"

module if_id (input wire clk,
              input wire rst,
              input wire[`InstAddrBus] if_pc,
              input wire[`InstBus] if_inst,
              input wire[5:0] stall,
              output reg[`InstAddrBus] id_pc,
              output reg[`InstBus] id_inst);
    
    always @(posedge clk) begin
        if (rst == `RstEnable) begin
            id_pc   <= `ZeroWord;               //复位的时候pc为0
            id_inst <= `ZeroWord;                //复位的时候指令也为0，实际就是空指令
        end
        else if (stall[1] == `Stop && stall[2] == `NoStop) begin
            id_pc   <= `ZeroWord;                   //其余时 刻向下传递取值阶段的值
            id_inst <= `ZeroWord;
        end
        else if (stall[1] == `NoStop) begin
            id_inst <= if_inst;
            id_pc   <= if_pc;
        end
    end
endmodule //if_id
    //其中只有一个时许电路，IF/ID模块只是简单的将取值阶段的结果在每个时钟周期的上升沿传递到译码阶段
