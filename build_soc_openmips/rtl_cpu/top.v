/*
 * @Author: Groot
 * @Date: 2022-04-09 18:01:23
 * @LastEditTime: 2022-05-18 11:24:34
 * @LastEditors: Groot
 * @Description:
 * @FilePath: /openMIPS/vsrc/top.v
 * 版权声明
 */
`include "define.v"
// `include "openmips.v"
// `include "inst_rom.v"
// `include "data_ram.v"
module top (input wire clk,
            input wire rst);
    //连接指令存储器
    wire[`InstAddrBus] inst_addr;
    wire[`InstBus] inst;
    wire rom_ce;

    //连接数据存储器
    wire[`RegBus] ram_addr_i;
    wire[`RegBus] ram_data_o;
    wire[3:0] ram_sel_i;
    wire ram_ce_i;
    wire ram_we_i;
    wire[`RegBus] ram_data_i;
    
    //例化处理器openMIPS
    openmips openmips0(.clk(clk),
    .rst(rst),
    .rom_data_i(inst),
    .rom_ce_o(rom_ce),
    .rom_addr_o(inst_addr),
    .ram_addr_o(ram_addr_i),
    .ram_data_o(ram_data_i),
    .ram_sel_o(ram_sel_i),
    .ram_we_o(ram_we_i),
    .ram_ce_o(ram_ce_i),
    .ram_data_i(ram_data_o));
    
    //例化指令存储器ROM
    inst_rom inst_rom0(.ce(rom_ce),
    .addr(inst_addr),
    .inst(inst));

    data_ram data_ram0(.clk(clk),
    .addr(ram_addr_i),
    .data_i(ram_data_i),
    .sel(ram_sel_i),
    .we(ram_we_i),
    .ce(ram_ce_i),
    .data_o(ram_data_o)
    );
endmodule //top
