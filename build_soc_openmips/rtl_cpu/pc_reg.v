/*
 * @Author: Groot
 * @Date: 2022-04-09 18:01:23
 * @LastEditTime: 2022-05-20 10:48:41
 * @LastEditors: Groot
 * @Description:
 * @FilePath: /openMIPS/vsrc/pc_reg.v
 * 版权声明
 */
`include "define.v"

module pc_reg (input wire clk,
               input wire rst,
               input wire[5:0] stall,
               input branch_flag_i,
               output reg ce,
               output reg[`InstAddrBus] pc,
               input wire[`RegBus] branch_target_address_i);
    
    //clk时钟信号
    //rst复位信号
    //ce指令存储器使能信号
    //pc要读取的指令地址
    
    always @(posedge clk) begin //时钟上升沿触发
        if (ce == `ChipDisable) begin   //指令存储器使能信号无效的时候，pc保持为0
            pc <= 32'h00000000;
        end
        // 当stall[0]为NoStop时，pc加4，否则，保持pc不变
        else if (stall[0] == `NoStop) begin              //指令存储器使能信号有效的时候，pc在每个时钟加1
            if (branch_flag_i == `Branch) begin
                pc <= branch_target_address_i;
            end
            else begin
                pc <= pc + 4'h4;
            end
        end
    end
    
    always @(posedge clk) begin //时钟上升沿触发
        if (rst == `RstEnable) begin //复位信号有效的时候，指令存储器使能信号无效
            ce <= `ChipDisable;
        end
        else begin              //复位信号无效的时候，指令存储器使能信号有效
            ce <= `ChipEnable;
        end
    end
endmodule //pc_reg
