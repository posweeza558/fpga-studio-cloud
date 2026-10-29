/*
 * @Author: Groot
 * @Date: 2022-04-09 18:01:23
 * @LastEditTime: 2022-05-14 15:27:24
 * @LastEditors: Groot
 * @Description:
 * @FilePath: /openMIPS/vsrc/mem.v
 * 版权声明
 */
`include "define.v"

module mem (input wire rst,
            input wire[`RegAddBus] wd_i,
            input wire wreg_i,
            input wire[`RegBus] wdata_i,
            output reg[`RegAddBus] wd_o,
            output reg wreg_o,
            output reg[`RegBus] wdata_o,
            input wire whilo_i,
            input wire[`RegBus] hi_i,
            input wire[`RegBus] lo_i,
            output reg whilo_o,
            output reg[`RegBus] hi_o,
            output reg[`RegBus] lo_o,
            input wire[`AluOpBus] aluop_i,
            input wire[`RegBus] mem_addr_i,
            input wire[`RegBus] reg2_i,
            input wire[`RegBus] mem_data_i,
            output reg[`RegBus] mem_addr_o,
            output reg mem_we_o,
            output reg[3:0] mem_sel_o,
            output reg[`RegBus] mem_data_o,
            output reg mem_ce_o);
    
    // wire[`RegBus] zero32;
    // reg mem_we;

    // assign mem_we_o = mem_we;
    // assign zero32   = `ZeroWord;

    always @(*) begin
        if (rst == `RstEnable) begin
            wd_o    <= `NOPRegAddr;
            wreg_o  <= `WriteDisable;
            wdata_o <= `ZeroWord;
            whilo_o <= `WriteDisable;
            hi_o    <= `ZeroWord;
            lo_o    <= `ZeroWord;
            mem_addr_o  <= `ZeroWord;
            mem_we_o    <= `WriteDisable;
            mem_sel_o   <= 4'b0000;
            mem_data_o  <= `ZeroWord;
            mem_ce_o    <= `ChipDisable;
        end
        else begin
            wd_o    <= wd_i;
            wreg_o  <= wreg_i;
            wdata_o <= wdata_i;
            whilo_o <= whilo_i;
            hi_o    <= hi_i;
            lo_o    <= lo_i;
            mem_addr_o  <= ZeroWord;
            mem_we_o    <= WriteDisable;
            mem_sel_o   <= 4'b0000;
            mem_data_o  <= ZeroWord;
            mem_ce_o    <= ChipDisable;
            case (aluop_i)
                `EXE_LB_OP : begin
                    mem_addr_o  <= mem_addr_i;
                    mem_we_o    <= `WriteDisable;
                    mem_ce_o    <= `ChipEnable;
                    case (mem_addr_i[1:0])
                        2'b00 : begin
                            wdata_o <= {{24{mem_data_i[31]}}, mem_data_i[31:24]};
                            mem_sel_o   <= 4'b1000;
                        end
                        2'b01 : begin
                            wdata_o <= {{24{mem_data_i[23]}}, mem_data_i[23:16]};
                            mem_sel_o   <= 4'b0100;
                        end
                        2'b10 : begin
                            wdata_o <= {{24{mem_data_i[15]}}, mem_data_i[15:8]};
                            mem_sel_o   <= 4'b0010;
                        end
                        2'b11 : begin
                            wdata_o <= {{24{mem_data_i[7]}}, mem_data_i[7:0]};
                            mem_sel_o   <= 4'b0001;
                        end
                        default : begin
                            wdata_o     <= `ZeroWord;
                        end
                    endcase
                end
                `EXE_LBU_OP : begin
                    mem_addr_o  <= mem_addr_i;
                    mem_we_o    <= `WriteDisable;
                    mem_ce_o    <= `ChipEnable;
                    case (mem_addr_i[1:0])
                        2'b00 : begin
                            wdata_o <= {{24{1'b0}}, mem_data_i[31:24]};
                            mem_sel_o   <= 4'b1000;
                        end
                        2'b01 : begin
                            wdata_o <= {{24{1'b0}}, mem_data_i[23:16]};
                            mem_sel_o   <= 4'b0100;
                        end
                        2'b10 : begin
                            wdata_o <= {{24{1'b0}}, mem_data_i[15:8]};
                            mem_sel_o   <= 4'b0010;
                        end
                        2'b11 : begin
                            wdata_o <= {{24{1'b0}}, mem_data_i[7:0]};
                            mem_sel_o   <= 4'b0001;
                        end
                        default : begin
                            wdata_o     <= `ZeroWord;
                        end
                    endcase
                end
                `EXE_LH_OP : begin
                    mem_addr_o  <= mem_addr_i;
                    mem_we_o    <= `WriteDisable;
                    mem_ce_o    <= `ChipEnable;
                    case (mem_addr_i[1:0])
                        2'b00 : begin
                            wdata_o     <= {{16{mem_data_i[31]}},mem_data_i[31:16]};
                            mem_sel_o   <= 4'b1100;
                        end
                        2'b10 : begin
                            wdata_o     <= {{16{mem_data_i[15]}},mem_data_i[15:0]};
                            mem_sel_o   <= 4'b0011;
                        end
                        default : begin
                            wdata_o     <= `ZeroWord;
                        end
                    endcase
                end
                `EXE_LHU_OP : begin
                    mem_addr_o  <= mem_addr_i;
                    mem_we_o    <= `WriteDisable;
                    mem_ce_o    <= `ChipEnable;
                    case (mem_addr_i[1:0])
                        2'b00 : begin
                            wdata_o     <= {{16{1'b0}},mem_data_i[31:16]};
                            mem_sel_o   <= 4'b1100;
                        end
                        2'b10 : begin
                            wdata_o     <= {{16{1'b0}},mem_data_i[15:0]};
                            mem_sel_o   <= 4'b0011;
                        end
                        default : begin
                            wdata_o     <= `ZeroWord;
                        end
                    endcase
                end
                `EXE_LW_OP : begin
                    mem_addr_o  <= mem_addr_i;
                    mem_we_o    <= `WriteDisable;
                    mem_ce_o    <= `ChipEnable;
                    wdata_o     <= mem_data_i;
                    mem_sel_o   <= 4'b1111;
                end
                `EXE_LWL_OP : begin
                    mem_addr_o  <= {mem_addr_i[31:2], 2'b00};
                    mem_we_o    <= `WriteDisable;
                    mem_ce_o    <= `ChipEnable;
                    mem_sel_o   <= 4'b1111;
                    case (mem_addr_i[1:0])
                        2'b00 : begin
                            wdata_o <= mem_data_i;
                        end 
                        2'b01 : begin
                            wdata_o <= {mem_data_i[23:0], reg2_i[7:0]};
                        end
                        2'b10 : begin
                            wdata_o <= {mem_data_i[15:0], reg2_i[15:0]};
                        end
                        2'b11 : begin
                            wdata_o <= {mem_data_i[7:0], reg2_i[23:0]};
                        end
                        default : begin
                            wdata_o <= `ZeroWord;
                        end 
                    endcase
                end
                `EXE_LWR_OP : begin
                    mem_addr_o  <= {mem_addr_i[31:2], 2'b00};
                    mem_we_o    <= `WriteDisable;
                    mem_ce_o    <= `ChipEnable;
                    mem_sel_o   <= 4'b1111;
                    case (mem_addr_i[1:0])
                        2'b00 : begin
                            wdata_o <= {reg2_i[31:8], mem_data_i[31:24]};
                        end
                        2'b01 : begin
                            wdata_o <= {reg2_i[31:16], mem_data_i[31:16]};
                        end
                        2'b10 : begin
                            wdata_o <= {reg2_i[31:24], mem_data_i[31:8]};
                        end
                        2'b11 : begin
                            wdata_o <= mem_data_i;
                        end
                        default : begin
                            
                        end
                    endcase
                end
                `EXE_SB_OP : begin
                    mem_addr_o  <= mem_addr_i;
                    mem_we_o    <= `WriteEnable;
                    mem_ce_o    <= `ChipEnable;
                    // mem_data_o  <= 
                    case (mem_addr_i[1:0])
                        2'b00 : begin
                            mem_data_o  <= {reg2_i[7:0],{24{1'b0}}};
                            mem_sel_o   <= 4'b1000;
                        end
                        2'b01 : begin
                            mem_data_o  <= {{8{1'b0}},reg2_i[7:0],{16{1'b0}}};
                            mem_sel_o   <= 4'b0100;
                        end
                        2'b10 : begin
                            mem_data_o  <= {{16{1'b0}},reg2_i[7:0],{8{1'b0}}};
                            mem_sel_o   <= 4'b0010;
                        end
                        2'b11 : begin
                            mem_data_o  <= {{24{1'b0}},reg2_i[7:0]};
                            mem_sel_o   <= 4'b0001;
                        end
                        default : begin
                            mem_sel_o   <= 4'b0000;
                        end
                    endcase
                end
                `EXE_SH_OP : begin
                    mem_addr_o  <= mem_addr_i;
                    mem_we_o    <= `WriteEnable;
                    mem_ce_o    <= `ChipEnable;
                    case (mem_addr_i[1:0])
                        2'b00 : begin
                            mem_data_o  <= {reg2_i[16:0],{16{1'b0}}};
                            mem_sel_o   <= 4'b1100;
                        end
                        2'b10 : begin
                            mem_data_o  <= {{16{1'b0}},reg2_i[16:0]};
                            mem_sel_o   <= 4'b0011;
                        end
                        default : begin
                            mem_sel_o   <= 4'b0000;
                        end
                    endcase
                end
                `EXE_SW_OP : begin
                    mem_addr_o  <= mem_addr_i;
                    mem_we_o    <= `WriteEnable;
                    mem_ce_o    <= `ChipEnable;
                    mem_data_o  <= reg2_i;
                    mem_sel_o   <= 4'b1111;
                end
                `EXE_SWL_OP : begin
                    mem_addr_o  <= mem_addr_i;
                    mem_we_o    <= `WriteEnable;
                    mem_ce_o    <= `ChipEnable;
                    case (mem_addr_i[1:0])
                        2'b00 : begin
                            mem_sel_o   <= 4'b1111;
                            mem_data_o  <= reg2_i;
                        end
                        2'b01 : begin
                            mem_sel_o   <= 4'b0111;
                            mem_data_o  <= {{8{1'b0}},reg2_i[31:8]};
                        end
                        2'b10 : begin
                            mem_sel_o   <= 4'b0011;
                            mem_data_o  <= {{16{1'b0}},reg2_i[31:16]};
                        end
                        2'b11 : begin
                            mem_sel_o   <= 4'b0001;
                            mem_data_o  <= {{24{1'b0}},reg2_i[31:24]};
                        end
                        default : begin
                            mem_sel_o   <= 4'b0000;
                        end
                    endcase
                end
                `EXE_SWR_OP : begin
                    mem_addr_o  <= mem_addr_i;
                    mem_we_o    <= `WriteEnable;
                    mem_ce_o    <= `ChipEnable;
                    case (mem_addr_i[1:0])
                        2'b00 : begin
                            mem_sel_o   <= 4'b1000;
                            mem_data_o  <= {reg2_i[7:0],{24{1'b0}}};
                        end
                        2'b01 : begin
                            mem_sel_o   <= 4'b1100;
                            mem_data_o  <= {reg2_i[15:0],{16{1'b0}}};
                        end
                        2'b10 : begin
                            mem_sel_o   <= 4'b1110;
                            mem_data_o  <= {reg2_i[24:0],{8{1'b0}}};
                        end
                        2'b11 : begin
                            mem_sel_o   <= 4'b1111;
                            mem_data_o  <= reg2_i;
                        end
                        default : begin
                            mem_sel_o   <= 4'b0000;
                        end
                    endcase
                end
                default : begin
                    mem_addr_o  <= `ZeroWord;
                    mem_we_o    <= `WriteDisable;
                    mem_sel_o   <= 4'b0000;
                    mem_data_o  <= `ZeroWord;
                    mem_ce_o    <= `ChipDisable;
                end
            endcase
        end
    end
    
endmodule //mem
