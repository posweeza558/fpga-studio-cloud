/*
 * @Author: Groot
 * @Date: 2022-04-13 16:14:33
 * @LastEditTime: 2022-04-14 15:48:57
 * @LastEditors: Groot
 * @Description:
 * @FilePath: /openMIPS/vsrc/hilo_reg.v
 * 版权声明
 */
`include "define.v"

module hilo_reg
    (
    input  wire rst,
    input  wire clk,
    
    //写端口
    input  wire we,
    input  wire[`RegBus] hi_i,
    input  wire[`RegBus] lo_i,
    
    //读端口
    output reg[`RegBus] hi_o,
    output reg[`RegBus] lo_o
    );
    
    always @(posedge clk ) begin
        if(rst == `RstEnable) begin
            hi_o <= `ZeroWord;
            lo_o <= `ZeroWord;
        end
        else if(we == `WriteEnable) begin
            hi_o <= hi_i;
            lo_o <= lo_i;
        end
    end //end always
endmodule
