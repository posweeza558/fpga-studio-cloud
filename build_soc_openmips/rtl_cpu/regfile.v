/*
 * @Author: Groot
 * @Date: 2022-04-09 18:01:23
 * @LastEditTime: 2022-04-14 15:44:15
 * @LastEditors: Groot
 * @Description: 
 * @FilePath: /openMIPS/vsrc/regfile.v
 * 版权声明
 */
`include "define.v"

module regfile (input wire clk,
                input wire rst,
                

                //写端口
                input wire we,
                input wire[`RegAddBus] waddr,  //要写入的寄存器地址
                input wire[`RegBus] wdata,     //要写入的数据

                //读端口1
                input wire re1,                //读端口1使能信号
                input wire[`RegAddBus] raddr1, //第一个读寄存器端口要读取的寄存器的地址
                output reg[`RegBus] rdata1,    //第一个读寄存器端口输出的寄存器值

                //读端口2
                input wire re2,                //读端口2使能信号
                input wire[`RegAddBus] raddr2, //第二个读寄存器端口要读取的寄存器的地址
                output reg[`RegBus] rdata2    //第二个读寄存器端口输出的寄存器值
                );
    
    //*****************************第一段：定义32个32位寄存器***************************
    reg [`RegBus] regs[0:`RegNum-1];
    
    //*****************************第二段：写操作***************************
    always @(posedge clk) begin
        if (rst == `RstDisable) begin
            if ((we == `WriteEnable) && (waddr != `RegNumLog2'h0)) begin
                regs[waddr] <= wdata;
            end
        end
    end
    
    //*****************************第三段：读端口1的读操作***************************
    always @( * ) begin
        //复位信号有效，通用寄存器输出为0
        if (rst == `RstEnable) begin
            rdata1 <= `ZeroWord;
        end
        //复位信号无效，如果读零地址，通用寄存器输出为0
        else if (raddr1 == `RegNumLog2'h0) begin
        rdata1 <= `ZeroWord;
    end

    //如果第一个都寄存器端口要读取的目标寄存器与要写入的目的寄存器是同一个寄存器
    //直接将要写入的值作为第一个读寄存器端口的输出
    else if ((raddr1 == waddr) && (we == `WriteEnable) && (re1 == `ReadEnable)) begin
    rdata1 <= wdata;
    end

    //地址有效，输出对应地址中的数据
    else if (re1 == `ReadEnable) begin
    rdata1 <= regs[raddr1];
    end
    
    //地址无效，直接输出0
    else begin
    rdata1 <= `RegNumLog2'h0;
    end
    end
    
    //*****************************第四段：读端口2的读操作***************************
    always @( *) begin
        //复位信号有效，通用寄存器输出为0
        if (rst == `RstEnable) begin
            rdata2 <= `ZeroWord;
        end
        //复位信号无效，如果读零地址，通用寄存器输出为0
        else if (raddr2 == `RegNumLog2'h0) begin
        rdata2 <= `ZeroWord;
    end

    //如果第一个都寄存器端口要读取的目标寄存器与要写入的目的寄存器是同一个寄存器
    //直接将要写入的值作为第一个读寄存器端口的输出
    else if ((raddr2 == waddr) && (we == `WriteEnable) && (re2 == `ReadEnable)) begin
    rdata2 <= wdata;
    end

    //地址有效，输出对应地址中的数据
    else if (re2 == `ReadEnable) begin
    rdata2 <= regs[raddr2];
    end
    
    //地址无效，直接输出0
    else begin
    rdata2 <= `RegNumLog2'h0;
    end
    end
endmodule //regfile