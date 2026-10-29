/*
 * @Author: Groot
 * @Date: 2022-04-09 18:01:23
 * @LastEditTime: 2022-05-14 16:18:32
 * @LastEditors: Groot
 * @Description:
 * @FilePath: /openMIPS/vsrc/id.v
 * 版权声明
 */
`include "define.v"

module id (input wire rst,
           input wire[`InstAddrBus] pc_i,
           input wire[`InstBus] inst_i,
           input wire[`RegBus] reg1_data_i,
           input wire[`RegBus] reg2_data_i,
           input wire ex_wreg_i,
                   input wire[`AluOpBus] ex_aluop_i,
           input wire[`RegAddBus] ex_wd_i,
           input wire[`InstBus] ex_wdata_i,
           input wire mem_wreg_i,
           input wire[`RegAddBus] mem_wd_i,
           input wire[`InstBus] mem_wdata_i,
           input wire is_in_delayslot_i,                //该指令是否位于延迟槽中
           output reg reg1_read_o,
           output reg reg2_read_o,
           output reg[`RegAddBus] reg1_addr_o,
           output reg[`RegAddBus] reg2_addr_o,
           output reg[`AluOpBus] aluop_o,
           output reg[`AluSelBus] alusel_o,
           output reg[`RegBus] reg1_o,
           output reg[`RegBus] reg2_o,
           output reg[`RegAddBus] wd_o,
           output reg wreg_o,
           output wire stallreq,
           output reg branch_flag_o,                    //是否发生转移
           output reg[`RegBus] branch_target_address_o, //转移目的地址
           output reg next_inst_in_delayslot_o,         //下一条进入译码阶段的指令是否在延迟槽中
           output reg is_in_delayslot_o,                //该指令是否位于延迟槽中
           output reg[`RegBus] link_addr_o,              //返回地址
           output wire[`RegBus] inst_o
        //    output reg id_mem_ce
           );
    
    //取得指令的指令码，功能码
    //对于ori指令只需要通过判断第26-31bit的值，即可判断是否是ori指令
    // op = I-type的指令码
    wire[5:0] op = inst_i[31:26];
    // op2 = 移位指令使用
    wire[4:0] op2 = inst_i[10:6];
    // op3 = R-type指令的指令码
    wire[5:0] op3 = inst_i[5:0];
    //
    wire[4:0] op4 = inst_i[20:16];
    
    //保存指令执行需要的立即数
    reg[`RegBus] imm;
    
    //指令是否有效
    reg instvalid;
    reg text;

    wire[`RegBus] pc_plus_4;
    wire[`RegBus] pc_plus_8;
    wire[`RegBus] imm_sll2_signedext;

    wire pre_inst_is_load;

    assign pc_plus_4 = pc_i + 4;            //保存当前译码阶段指令的下一条指令的地址
    assign pc_plus_8 = pc_i + 8;            //保存当前译码阶段指令的下一条的下一条指令的地址
    assign imm_sll2_signedext = {{14{inst_i[15]}}, inst_i[15:0], 2'b00};    //imm_sll2_signedext对应分支指令中的offset左移两位（×4），再进行符号扩展至32位
    reg stallreq_for_reg1_loadrelate;
    reg stallreq_for_reg2_loadrelate;
    assign stallreq = stallreq_for_reg1_loadrelate | stallreq_for_reg2_loadrelate;
    assign inst_o = inst_i;

    assign pre_inst_is_load = ( (ex_aluop_i == `EXE_LB_OP) ||
                                (ex_aluop_i == `EXE_LBU_OP)||
                                (ex_aluop_i == `EXE_LH_OP) ||
                                (ex_aluop_i == `EXE_LHU_OP)||
                                (ex_aluop_i == `EXE_LW_OP) ||
                                (ex_aluop_i == `EXE_LWR_OP)||
                                (ex_aluop_i == `EXE_LWL_OP)||
                                (ex_aluop_i == `EXE_LL_OP) ||
                                (ex_aluop_i == `EXE_SC_OP)) ? 1'b1 : 1'b0;

    //****************************第一段：对指令进行译码***************************
    always @(*) begin
        if (rst == `RstEnable) begin
            aluop_o     <= `EXE_NOP_OP;
            alusel_o    <= `EXE_RES_NOP;
            wd_o        <= `NOPRegAddr;
            wreg_o      <= `WriteDisable;
            instvalid   <= `InstValid;
            reg1_read_o <= `ReadDisable;
            reg2_read_o <= `ReadDisable;
            reg1_addr_o <= `NOPRegAddr;
            reg2_addr_o <= `NOPRegAddr;
            imm         <= 32'h00000000;
            // inst_o      <= `ZeroWord;
            link_addr_o                 <= `ZeroWord;
            branch_target_address_o     <= `ZeroWord;
            branch_flag_o               <= `NotBranch;
            next_inst_in_delayslot_o    <= `NotInDelaySlot;
            // id_mem_ce   <= `ChipDisable;
        end
        else begin
            aluop_o     <= `EXE_NOP_OP;
            alusel_o    <= `EXE_RES_NOP;
            wd_o        <= inst_i[15:11]; //目的寄存器地址
            wreg_o      <= `WriteDisable;
            instvalid   <= `InstInvalid;
            reg1_read_o <= `ReadDisable;
            reg2_read_o <= `ReadDisable;
            reg1_addr_o <= inst_i[25:21];   //默认通过Regfile读端口1读取的寄存器地址
            reg2_addr_o <= inst_i[20:16];   //默认通过Regfile读端口2读取的寄存器地址
            imm         <= `ZeroWord;
            link_addr_o                 <= `ZeroWord;
            branch_target_address_o     <= `ZeroWord;
            branch_flag_o               <= `NotBranch;
            next_inst_in_delayslot_o    <= `NotInDelaySlot;
            case (op)
                `EXE_SPECIAL_INST : begin
                    case (op2)
                        5'b00000 : begin
                            case (op3)
                                `EXE_OR : begin
                                    wreg_o      <= `WriteEnable;
                                    aluop_o     <= `EXE_OR_OP;
                                    alusel_o    <= `EXE_RES_LOGIC;
                                    reg1_read_o <= `ReadEnable;
                                    reg2_read_o <= `ReadEnable;
                                    instvalid   <= `InstValid;
                                end
                                `EXE_AND : begin
                                    wreg_o      <= `WriteEnable;
                                    aluop_o     <= `EXE_AND_OP;
                                    alusel_o    <= `EXE_RES_LOGIC;
                                    reg1_read_o <= `ReadEnable;
                                    reg2_read_o <= `ReadEnable;
                                    instvalid   <= `InstValid;
                                end
                                `EXE_XOR : begin
                                    wreg_o      <= `WriteEnable;
                                    aluop_o     <= `EXE_XOR_OP;
                                    alusel_o    <= `EXE_RES_LOGIC;
                                    reg1_read_o <= `ReadEnable;
                                    reg2_read_o <= `ReadEnable;
                                    instvalid   <= `InstValid;
                                end
                                `EXE_NOR :begin
                                    wreg_o      <= `WriteEnable;
                                    aluop_o     <= `EXE_NOR_OP;
                                    alusel_o    <= `EXE_RES_LOGIC;
                                    reg1_read_o <= `ReadEnable;
                                    reg2_read_o <= `ReadEnable;
                                    instvalid   <= `InstValid;
                                end
                                `EXE_SLLV : begin
                                    wreg_o      <= `WriteEnable;
                                    aluop_o     <= `EXE_SLL_OP;
                                    alusel_o    <= `EXE_RES_SHIFT;
                                    reg1_read_o <= `ReadEnable;
                                    reg2_read_o <= `ReadEnable;
                                    instvalid   <= `InstValid;
                                end
                                `EXE_SRLV : begin
                                    wreg_o      <= `WriteEnable;
                                    aluop_o     <= `EXE_SRL_OP;
                                    alusel_o    <= `EXE_RES_SHIFT;
                                    reg1_read_o <= `ReadEnable;
                                    reg2_read_o <= `ReadEnable;
                                    instvalid   <= `InstValid;
                                end
                                `EXE_SRAV : begin
                                    wreg_o      <= `WriteEnable;
                                    aluop_o     <= `EXE_SRA_OP;
                                    alusel_o    <= `EXE_RES_SHIFT;
                                    reg1_read_o <= `ReadEnable;
                                    reg2_read_o <= `ReadEnable;
                                    instvalid   <= `InstValid;
                                end
                                `EXE_SYNC : begin
                                    wreg_o      <= `WriteEnable;
                                    alusel_o    <= `EXE_RES_NOP;
                                    aluop_o     <= `EXE_NOP_OP;
                                    reg1_read_o <= `ReadDisable;
                                    reg2_read_o <= `ReadEnable;
                                    instvalid   <= `InstValid;
                                end
                                `EXE_MOVZ : begin
                                    aluop_o     <= `EXE_MOVZ_OP;
                                    alusel_o    <= `EXE_RES_MOVE;
                                    reg1_read_o <= `ReadEnable;
                                    reg2_read_o <= `ReadEnable;
                                    instvalid   <= `InstValid;
                                    //reg2_o的值就是rt寄存器的值
                                    //如果rt为0,则能够将rs中的值移动到rt
                                    if (reg2_o == `ZeroWord) begin
                                        wreg_o	 <= `WriteEnable;
                                    end
                                    else begin
                                        wreg_o	 <= `WriteDisable;
                                    end
                                end
                                `EXE_MOVN : begin
                                    aluop_o     <= `EXE_MOVN_OP;
                                    alusel_o    <= `EXE_RES_MOVE;
                                    reg1_read_o <= `ReadEnable;
                                    reg2_read_o <= `ReadEnable;
                                    instvalid   <= `InstValid;
                                    //reg2_o的值就是rt寄存器的值
                                    //如果rt不为0,则能够将rs中的值移动到rt
                                    if (reg2_o != `ZeroWord) begin
                                        wreg_o	 <= `WriteEnable;
                                    end
                                    else begin
                                        wreg_o	 <= `WriteDisable;
                                    end
                                end
                                `EXE_MFHI : begin
                                    wreg_o      <= `WriteEnable;
                                    aluop_o	    <= `EXE_MFHI_OP;
                                    alusel_o    <= `EXE_RES_MOVE;
                                    reg1_read_o <= `ReadDisable;
                                    reg2_read_o <= `ReadDisable;
                                    instvalid   <= `InstValid;
                                end
                                `EXE_MFLO : begin
                                    wreg_o      <= `WriteEnable;
                                    aluop_o	    <= `EXE_MFLO_OP;
                                    alusel_o    <= `EXE_RES_MOVE;
                                    reg1_read_o <= `ReadDisable;
                                    reg2_read_o <= `ReadDisable;
                                    instvalid   <= `InstValid;
                                end
                                `EXE_MTHI : begin
                                    wreg_o      <= `WriteDisable;
                                    aluop_o     <= `EXE_MTHI_OP;
                                    reg1_read_o <= `ReadEnable;
                                    reg2_read_o <= `ReadDisable;
                                    instvalid   <= `InstValid;
                                end
                                `EXE_MTLO : begin
                                    wreg_o      <= `WriteDisable;
                                    aluop_o     <= `EXE_MTLO_OP;
                                    reg1_read_o <= `ReadEnable;
                                    reg2_read_o <= `ReadDisable;
                                    instvalid   <= `InstValid;
                                end
                                `EXE_ADD : begin
                                    wreg_o      <= `WriteEnable;
                                    aluop_o     <= `EXE_ADD_OP;
                                    alusel_o    <= `EXE_RES_ARITHMETIC;
                                    reg1_read_o <= `ReadEnable;
                                    reg2_read_o <= `ReadEnable;
                                    instvalid   <= `InstValid;
                                end
                                `EXE_ADDU : begin
                                    wreg_o      <= `WriteEnable;
                                    aluop_o     <= `EXE_ADDU_OP;
                                    alusel_o    <= `EXE_RES_ARITHMETIC;
                                    reg1_read_o <= `ReadEnable;
                                    reg2_read_o <= `ReadEnable;
                                    instvalid   <= `InstValid;
                                end
                                `EXE_SUB : begin
                                    wreg_o      <= `WriteEnable;
                                    aluop_o     <= `EXE_SUB_OP;
                                    alusel_o    <= `EXE_RES_ARITHMETIC;
                                    reg1_read_o <= `ReadEnable;
                                    reg2_read_o <= `ReadEnable;
                                    instvalid   <= `InstValid;
                                end
                                `EXE_SUBU : begin
                                    wreg_o      <= `WriteEnable;
                                    aluop_o     <= `EXE_SUBU_OP;
                                    alusel_o    <= `EXE_RES_ARITHMETIC;
                                    reg1_read_o <= `ReadEnable;
                                    reg2_read_o <= `ReadEnable;
                                    instvalid   <= `InstValid;
                                end
                                `EXE_SLT : begin
                                    wreg_o      <= `WriteEnable;
                                    aluop_o     <= `EXE_SLT_OP;
                                    alusel_o    <= `EXE_RES_ARITHMETIC;
                                    reg1_read_o <= `ReadEnable;
                                    reg2_read_o <= `ReadEnable;
                                    instvalid   <= `InstValid;
                                end
                                `EXE_SLTU : begin
                                    wreg_o      <= `WriteEnable;
                                    aluop_o     <= `EXE_SLTU_OP;
                                    alusel_o    <= `EXE_RES_ARITHMETIC;
                                    reg1_read_o <= `ReadEnable;
                                    reg2_read_o <= `ReadEnable;
                                    instvalid   <= `InstValid;
                                end
                                `EXE_MULT : begin
                                    wreg_o      <= `WriteDisable;
                                    aluop_o     <= `EXE_MULT_OP;
                                    reg1_read_o <= `ReadEnable;
                                    reg2_read_o <= `ReadEnable;
                                    instvalid   <= `InstValid;
                                end
                                `EXE_MULTU : begin
                                    wreg_o      <= `WriteDisable;
                                    aluop_o     <= `EXE_MULTU_OP;
                                    reg1_read_o <= `ReadEnable;
                                    reg2_read_o <= `ReadEnable;
                                    instvalid   <= `InstValid;
                                end
                                `EXE_DIV : begin
                                    wreg_o      <= `WriteDisable;
                                    aluop_o     <= `EXE_DIV_OP;
                                    reg1_read_o <= `ReadEnable;
                                    reg2_read_o <= `ReadEnable;
                                    instvalid   <= `InstValid;
                                end
                                `EXE_DIVU : begin
                                    wreg_o      <= `WriteDisable;
                                    aluop_o     <= `EXE_DIVU_OP;
                                    reg1_read_o <= `ReadEnable;
                                    reg2_read_o <= `ReadEnable;
                                    instvalid   <= `InstValid;
                                end
                                `EXE_JR : begin
                                    wreg_o                  <= `WriteDisable;
                                    aluop_o                 <= `EXE_JR_OP;
                                    alusel_o                <= `EXE_RES_JUMP_BRANCH;
                                    reg1_read_o             <= `ReadEnable;
                                    reg2_read_o             <= `ReadDisable;
                                    link_addr_o             <= `ZeroWord;
                                    branch_target_address_o <= reg1_o;
                                    branch_flag_o           <= `Branch;
                                    next_inst_in_delayslot_o<= `InDelaySlot;
                                    instvalid               <= `InstValid;
                                end
                                `EXE_JALR : begin
                                    wreg_o                  <= `WriteEnable;
                                    aluop_o                 <= `EXE_JALR_OP;
                                    alusel_o                <= `EXE_RES_JUMP_BRANCH;
                                    reg1_read_o             <= `ReadEnable;
                                    reg2_read_o             <= `ReadDisable;
                                    // wd_o                    <= inst_i[15:11];
                                    link_addr_o             <= pc_plus_8;
                                    branch_target_address_o <= reg1_o;
                                    branch_flag_o           <= `Branch;
                                    next_inst_in_delayslot_o<= `InDelaySlot;
                                    instvalid               <= `InstValid;
                                end
                                default : begin
                                end
                            endcase // case op3
                        end
                        default : begin
                        end
                    endcase //case op2
                end
                `EXE_SPECIAL_INST2 : begin
                    case (op3)
                        // wd_o为默认值
                        `EXE_CLZ : begin
                            wreg_o      <= `WriteEnable;
                            alusel_o    <= `EXE_RES_ARITHMETIC;
                            aluop_o     <= `EXE_CLZ_OP;
                            reg1_read_o <= `ReadEnable;
                            reg2_read_o <= `ReadDisable;
                            instvalid   <= `InstValid;
                        end
                        `EXE_CLO : begin
                            wreg_o      <= `WriteEnable;
                            alusel_o    <= `EXE_RES_ARITHMETIC;
                            aluop_o     <= `EXE_CLO_OP;
                            reg1_read_o <= `ReadEnable;
                            reg2_read_o <= `ReadDisable;
                            instvalid   <= `InstValid;
                        end
                        `EXE_MUL : begin
                            wreg_o      <= `WriteEnable;
                            alusel_o    <= `EXE_RES_MUL;
                            aluop_o     <= `EXE_MUL_OP;
                            reg1_read_o <= `ReadEnable;
                            reg2_read_o <= `ReadEnable;
                            instvalid   <= `InstValid;
                        end
                        `EXE_MADD : begin
                            wreg_o      <= `WriteDisable;
                            alusel_o    <= `EXE_RES_MUL;
                            aluop_o     <= `EXE_MADD_OP;
                            reg1_read_o <= `ReadEnable;
                            reg2_read_o <= `ReadEnable;
                            instvalid   <= `InstValid;
                        end
                        `EXE_MADDU : begin
                            wreg_o      <= `WriteDisable;
                            alusel_o    <= `EXE_RES_MUL;
                            aluop_o     <= `EXE_MADDU_OP;
                            reg1_read_o <= `ReadEnable;
                            reg2_read_o <= `ReadEnable;
                            instvalid   <= `InstValid;
                        end
                        `EXE_MSUB : begin
                            wreg_o      <= `WriteDisable;
                            alusel_o    <= `EXE_RES_MUL;
                            aluop_o     <= `EXE_MSUB_OP;
                            reg1_read_o <= `ReadEnable;
                            reg2_read_o <= `ReadEnable;
                            instvalid   <= `InstValid;
                        end
                        `EXE_MSUBU : begin
                            wreg_o      <= `WriteDisable;
                            alusel_o    <= `EXE_RES_MUL;
                            aluop_o     <= `EXE_MSUBU_OP;
                            reg1_read_o <= `ReadEnable;
                            reg2_read_o <= `ReadEnable;
                            instvalid   <= `InstValid;
                        end
                        default : begin
                        end
                    endcase
                end
                `EXE_REGIMM_INST : begin
                    case (op4)
                        `EXE_BLTZ : begin
                            wreg_o              <= `WriteDisable;
                            aluop_o             <= `EXE_BLTZ_OP;
                            alusel_o            <= `EXE_RES_JUMP_BRANCH;
                            reg1_read_o         <= `ReadEnable;
                            reg2_read_o         <= `ReadDisable;
                            if(reg1_o[31] == 1'b1) begin
                                branch_flag_o               <= `Branch;
                                next_inst_in_delayslot_o    <= `InDelaySlot;
                                branch_target_address_o     <= pc_plus_4 + imm_sll2_signedext;
                            end
                            instvalid           <= `InstValid;
                        end
                        `EXE_BLTZAL : begin
                            wreg_o              <= `WriteEnable;
                            aluop_o             <= `EXE_BLTZAL_OP;
                            alusel_o            <= `EXE_RES_JUMP_BRANCH;
                            reg1_read_o         <= `ReadEnable;
                            reg2_read_o         <= `ReadDisable;
                            link_addr_o         <= pc_plus_8;
                            wd_o                <= 5'b11111;
                            if(reg1_o[31] == 1'b1) begin
                                branch_flag_o               <= `Branch;
                                next_inst_in_delayslot_o    <= `InDelaySlot;
                                branch_target_address_o     <= pc_plus_4 + imm_sll2_signedext;
                            end
                        end
                        `EXE_BGEZ : begin
                            wreg_o              <= `WriteDisable;
                            aluop_o             <= `EXE_BGEZ_OP;
                            alusel_o            <= `EXE_RES_JUMP_BRANCH;
                            reg1_read_o         <= `ReadEnable;
                            reg2_read_o         <= `ReadDisable;
                            if(reg1_o[31] == 1'b0) begin
                                branch_flag_o               <= `Branch;
                                next_inst_in_delayslot_o    <= `InDelaySlot;
                                branch_target_address_o     <= pc_plus_4 + imm_sll2_signedext;
                            end
                            instvalid           <= `InstValid;
                        end
                        `EXE_BGEZAL : begin
                            wreg_o              <= `WriteEnable;
                            aluop_o             <= `EXE_BGEZAL_OP;
                            alusel_o            <= `EXE_RES_JUMP_BRANCH;
                            reg1_read_o         <= `ReadEnable;
                            reg2_read_o         <= `ReadDisable;
                            link_addr_o         <= pc_plus_8;
                            wd_o                <= 5'b11111;
                            if(reg1_o[31] == 1'b0) begin
                                branch_flag_o               <= `Branch;
                                next_inst_in_delayslot_o    <= `InDelaySlot;
                                branch_target_address_o     <= pc_plus_4 + imm_sll2_signedext;
                            end
                        end
                        default : begin
                            
                        end
                    endcase //op4
                end
                `EXE_ORI : begin            //依据op的值判断是否是ori指令
                    //ori指令需要将结果写入目的寄存器，所以wreg_o为WriteEnable
                    wreg_o <= `WriteEnable;
                    //运算类型是逻辑运算
                    alusel_o <= `EXE_RES_LOGIC;
                    //运算的子类型是逻辑“或”运算
                    aluop_o <= `EXE_OR_OP;
                    //需要通过Regfile的读端口1读取寄存器
                    reg1_read_o <= `ReadEnable;
                    //不需要通过Regfile的读端口2读取寄存器
                    reg2_read_o <= `ReadDisable;
                    //指令执行需要的立即数
                    imm <= {16'h0000,  inst_i[15:0]};
                    //指令执行要写的目的寄存器地址
                    wd_o <= inst_i[20:16];
                    //ori指令是有效指令
                    instvalid <= `InstValid;
                end
                `EXE_ANDI : begin
                    wreg_o      <= `WriteEnable;
                    alusel_o    <= `EXE_RES_LOGIC;
                    aluop_o     <= `EXE_AND_OP;
                    reg1_read_o <= `ReadEnable;
                    reg2_read_o <= `ReadDisable;
                    imm         <= {16'b0000, inst_i[15:0]};
                    wd_o        <= inst_i[20:16];
                    instvalid   <= `InstValid;
                end
                `EXE_XORI : begin
                    wreg_o      <= `WriteEnable;
                    alusel_o    <= `EXE_RES_LOGIC;
                    aluop_o     <= `EXE_XOR_OP;
                    reg1_read_o <= `ReadEnable;
                    reg2_read_o <= `ReadDisable;
                    imm         <= {16'b0000, inst_i[15:0]};
                    wd_o        <= inst_i[20:16];
                    instvalid   <= `InstValid;
                end
                // 将指令中的16bit立即数转移到高位，低位用16bit的0填充
                `EXE_LUI : begin
                    wreg_o      <= `WriteEnable;
                    alusel_o    <= `EXE_RES_LOGIC;
                    aluop_o     <= `EXE_OR_OP;
                    reg1_read_o <= `ReadEnable;
                    reg2_read_o <= `ReadDisable;
                    imm         <= {inst_i[15:0], 16'b0000};
                    wd_o        <= inst_i[20:16];
                    instvalid   <= `InstValid;
                end
                `EXE_PREF : begin
                    wreg_o      <= `WriteEnable;
                    alusel_o    <= `EXE_RES_NOP;
                    aluop_o     <= `EXE_NOP_OP;
                    reg1_read_o <= `ReadDisable;
                    reg2_read_o <= `ReadDisable;
                    instvalid   <= `InstValid;
                end
                //有待填写
                `EXE_ADDI : begin
                    wreg_o      <= `WriteEnable;
                    alusel_o    <= `EXE_RES_ARITHMETIC;
                    aluop_o     <= `EXE_ADD_OP;
                    reg1_read_o <= `ReadEnable;
                    reg2_read_o <= `ReadDisable;
                    imm         <= {{16{inst_i[15]}}, inst_i[15:0]};
                    wd_o        <= inst_i[20:16];
                    instvalid   <= `InstValid;
                end
                `EXE_ADDIU : begin
                    wreg_o      <= `WriteEnable;
                    alusel_o    <= `EXE_RES_ARITHMETIC;
                    aluop_o     <= `EXE_ADDU_OP;
                    reg1_read_o <= `ReadEnable;
                    reg2_read_o <= `ReadDisable;
                    imm         <= {{16{inst_i[15]}}, inst_i[15:0]};
                    wd_o        <= inst_i[20:16];
                    instvalid   <= `InstValid;
                end
                `EXE_SLTI : begin
                    wreg_o      <= `WriteEnable;
                    alusel_o    <= `EXE_RES_ARITHMETIC;
                    aluop_o     <= `EXE_SLT_OP;
                    reg1_read_o <= `ReadEnable;
                    reg2_read_o <= `ReadDisable;
                    imm         <= {{16{inst_i[15]}}, inst_i[15:0]};
                    wd_o        <= inst_i[20:16];
                    instvalid   <= `InstValid;
                end
                `EXE_SLTIU : begin
                    wreg_o      <= `WriteEnable;
                    alusel_o    <= `EXE_RES_ARITHMETIC;
                    aluop_o     <= `EXE_SLTU_OP;
                    reg1_read_o <= `ReadEnable;
                    reg2_read_o <= `ReadDisable;
                    imm         <= {{16{inst_i[15]}}, inst_i[15:0]};
                    wd_o        <= inst_i[20:16];
                    instvalid   <= `InstValid;
                end
                `EXE_J : begin
                    wreg_o                      <= `WriteDisable;
                    aluop_o                     <= `EXE_J_OP;
                    alusel_o                    <= `EXE_RES_JUMP_BRANCH;
                    reg1_read_o                 <= `ReadDisable;
                    reg2_read_o                 <= `ReadDisable;
                    branch_flag_o               <= `Branch;
                    link_addr_o                 <= `ZeroWord;
                    next_inst_in_delayslot_o    <= `InDelaySlot;
                    branch_target_address_o     <= {pc_plus_4[31:28], inst_i[25:0], 2'b00};                   
                    instvalid                   <= `InstValid;
                end
                `EXE_JAL : begin
                    wreg_o                      <= `WriteEnable;
                    aluop_o                     <= `EXE_JAL_OP;
                    alusel_o                    <= `EXE_RES_JUMP_BRANCH;
                    reg1_read_o                 <= `ReadDisable;
                    reg2_read_o                 <= `ReadDisable;
                    wd_o                        <= 5'b11111;                // JAL将返回地址先暂存到$32寄存器中
                    branch_flag_o               <= `Branch;
                    link_addr_o                 <= pc_plus_8;
                    next_inst_in_delayslot_o    <= `InDelaySlot;
                    branch_target_address_o     <= {pc_plus_4[31:28], inst_i[25:0], 2'b00};                    
                    instvalid                   <= `InstValid;                      
                end
                `EXE_BEQ : begin
                    wreg_o              <= `WriteDisable;
                    aluop_o             <= `EXE_BEQ_OP;
                    alusel_o            <= `EXE_RES_JUMP_BRANCH;
                    reg1_read_o         <= `ReadEnable;
                    reg2_read_o         <= `ReadEnable;
                    if (reg1_o == reg2_o) begin
                        branch_flag_o               <= `Branch;
                        next_inst_in_delayslot_o    <= `InDelaySlot;
                        branch_target_address_o     <=  pc_plus_4 + imm_sll2_signedext;
                    end
                    instvalid           <= `InstValid;
                end
                `EXE_BGTZ : begin
                    wreg_o              <= `WriteDisable;
                    aluop_o             <= `EXE_BGTZ_OP;
                    alusel_o            <= `EXE_RES_JUMP_BRANCH;
                    reg1_read_o         <= `ReadEnable;
                    reg2_read_o         <= `ReadDisable;
                    if(reg1_o[31] == 1'b0 && reg1_o != `ZeroWord) begin
                        branch_flag_o               <= `Branch;
                        next_inst_in_delayslot_o    <= `InDelaySlot;
                        branch_target_address_o     <=  pc_plus_4 + imm_sll2_signedext;
                    end
                    instvalid           <= `InstValid;
                end
                `EXE_BLEZ : begin
                    wreg_o              <= `WriteDisable;
                    aluop_o             <= `EXE_BLEZ_OP;
                    alusel_o            <= `EXE_RES_JUMP_BRANCH;
                    reg1_read_o         <= `ReadEnable;
                    reg2_read_o         <= `ReadDisable;
                    if (reg1_o[31] == 1'b1 || reg1_o == `ZeroWord) begin
                        branch_flag_o               <= `Branch;
                        next_inst_in_delayslot_o    <= `InDelaySlot;
                        branch_target_address_o     <=  pc_plus_4 + imm_sll2_signedext;
                    end
                    instvalid           <= `InstValid;
                end
                `EXE_BNE : begin
                    wreg_o              <= `WriteDisable;
                    aluop_o             <= `EXE_BNE_OP;
                    alusel_o            <= `EXE_RES_JUMP_BRANCH;
                    reg1_read_o         <= `ReadEnable;
                    reg2_read_o         <= `ReadEnable;
                    if (reg1_o != reg2_o) begin
                        branch_flag_o               <= `Branch;
                        next_inst_in_delayslot_o    <= `InDelaySlot;
                        branch_target_address_o     <=  pc_plus_4 + imm_sll2_signedext;
                    end
                    instvalid           <= `InstValid;
                end
                `EXE_LB : begin
                    wreg_o      <= `WriteEnable;
                    aluop_o     <= `EXE_LB_OP;
                    alusel_o    <= `EXE_RES_LOAD_STORE;
                    reg1_read_o <= `ReadEnable;
                    reg2_read_o <= `ReadDisable;
                    wd_o        <= op4;
                    instvalid   <= `InstValid;
                    // id_mem_ce   <= `ChipEnable;
                end
                `EXE_LBU : begin
                    wreg_o      <= `WriteEnable;
                    aluop_o     <= `EXE_LBU_OP;
                    alusel_o    <= `EXE_RES_LOAD_STORE;
                    reg1_read_o <= `ReadEnable;
                    reg2_read_o <= `ReadDisable;
                    wd_o        <= op4;
                    instvalid   <= `InstValid;
                end
                `EXE_LH : begin
                    wreg_o      <= `WriteEnable;
                    aluop_o     <= `EXE_LH_OP;
                    alusel_o    <= `EXE_RES_LOAD_STORE;
                    reg1_read_o <= `ReadEnable;
                    reg2_read_o <= `ReadDisable;
                    wd_o        <= op4;
                    instvalid   <= `InstValid;
                end
                `EXE_LHU : begin
                    wreg_o      <= `WriteEnable;
                    aluop_o     <= `EXE_LHU_OP;
                    alusel_o    <= `EXE_RES_LOAD_STORE;
                    reg1_read_o <= `ReadEnable;
                    reg2_read_o <= `ReadDisable;
                    wd_o        <= op4;
                    instvalid   <= `InstValid;
                end
                `EXE_LW : begin
                    wreg_o      <= `WriteEnable;
                    aluop_o     <= `EXE_LW_OP;
                    alusel_o    <= `EXE_RES_LOAD_STORE;
                    reg1_read_o <= `ReadEnable;
                    reg2_read_o <= `ReadDisable;
                    wd_o        <= op4;
                    instvalid   <= `InstValid;
                end
                `EXE_LWL : begin
                    wreg_o      <= `WriteEnable;
                    aluop_o     <= `EXE_LWL_OP;
                    alusel_o    <= `EXE_RES_LOAD_STORE;
                    reg1_read_o <= `ReadEnable;
                    reg2_read_o <= `ReadEnable;
                    wd_o        <= op4;
                    instvalid   <= `InstValid;
                end
                `EXE_LWR : begin
                    wreg_o      <= `WriteEnable;
                    aluop_o     <= `EXE_LWR_OP;
                    alusel_o    <= `EXE_RES_LOAD_STORE;
                    reg1_read_o <= `ReadEnable;
                    reg2_read_o <= `ReadEnable;
                    wd_o        <= op4;
                    instvalid   <= `InstValid;
                end
                `EXE_SB : begin
                    wreg_o      <= `WriteDisable;
                    aluop_o     <= `EXE_SB_OP;
                    alusel_o    <= `EXE_RES_LOAD_STORE;
                    reg1_read_o <= `ReadEnable;
                    reg2_read_o <= `ReadEnable;
                    instvalid   <= `InstValid;
                end
                `EXE_SH : begin
                    wreg_o      <= `WriteDisable;
                    aluop_o     <= `EXE_SH_OP;
                    alusel_o    <= `EXE_RES_LOAD_STORE;
                    reg1_read_o <= `ReadEnable;
                    reg2_read_o <= `ReadEnable;
                    instvalid   <= `InstValid;
                end
                `EXE_SW : begin
                    wreg_o      <= `WriteDisable;
                    aluop_o     <= `EXE_SW_OP;
                    alusel_o    <= `EXE_RES_LOAD_STORE;
                    reg1_read_o <= `ReadEnable;
                    reg2_read_o <= `ReadEnable;
                    instvalid   <= `InstValid;
                end
                `EXE_SWL : begin
                    wreg_o      <= `WriteDisable;
                    aluop_o     <= `EXE_SWL_OP;
                    alusel_o    <= `EXE_RES_LOAD_STORE;
                    reg1_read_o <= `ReadEnable;
                    reg2_read_o <= `ReadEnable;
                    instvalid   <= `InstValid;
                end
                `EXE_SWR : begin
                    wreg_o      <= `WriteDisable;
                    aluop_o     <= `EXE_SWR_OP;
                    alusel_o    <= `EXE_RES_LOAD_STORE;
                    reg1_read_o <= `ReadEnable;
                    reg2_read_o <= `ReadEnable;
                    instvalid   <= `InstValid;
                end
                default : begin
                end
            endcase //case op
            if (inst_i[31:21] == 11'b0) begin
                if (op3 == `EXE_SLL) begin
                    wreg_o      <= `WriteEnable;
                    alusel_o    <= `EXE_RES_SHIFT;
                    aluop_o     <= `EXE_SLL_OP;
                    reg1_read_o <= `ReadDisable;
                    reg2_read_o <= `ReadEnable;
                    imm[4:0]    <= inst_i[10:6];
                    wd_o        <= inst_i[15:11];
                    instvalid   <= `InstValid;
                end
                else if (op3 == `EXE_SRL) begin
                    wreg_o      <= `WriteEnable;
                    alusel_o    <= `EXE_RES_SHIFT;
                    aluop_o     <= `EXE_SRL_OP;
                    reg1_read_o <= `ReadDisable;
                    reg2_read_o <= `ReadEnable;
                    imm[4:0]    <= inst_i[10:6];
                    wd_o        <= inst_i[15:11];
                    instvalid   <= `InstValid;
                end
                else if (op3 == `EXE_SRA) begin
                    wreg_o      <= `WriteEnable;
                    alusel_o    <= `EXE_RES_SHIFT;
                    aluop_o     <= `EXE_SRA_OP;
                    reg1_read_o <= `ReadDisable;
                    reg2_read_o <= `ReadEnable;
                    imm[4:0]    <= inst_i[10:6];
                    wd_o        <= inst_i[15:11];
                    instvalid   <= `InstValid;
                end
            end
        end
    end //always

    // 输出变量is_in_delayslot_o表示本条指令是否是延迟槽指令
    always @(*) begin
        if (rst == `RstEnable) begin
            is_in_delayslot_o <= `NotInDelaySlot;
        end
        else begin
            is_in_delayslot_o <= is_in_delayslot_i;
        end
    end

    //****************************第二段：确定进行运算的源操作数1***************************
    //给reg1_赋值的过程增加了两种情况:
    //1. 如果Regfile模块读端口1要读取的寄存器就是执行阶段要写的目的寄存器，那么直接把执行阶段的结果ex_wdata_i作为reg1_o的值
    //2. 如果Regfile模块读端口1要读取的寄存器就是访存阶段要写的目的寄存器，那么直接把访存阶段的结果mem_wdata_i作为reg1_o的值
    always @(*) begin
        stallreq_for_reg1_loadrelate <= `NoStop;
        if (rst == `RstEnable) begin
            reg1_o <= `ZeroWord;
        end
        else if ((pre_inst_is_load == 1'b1) && (ex_wd_i == reg1_addr_o) && (reg1_read_o == `ReadEnable) && (ex_wd_i != `NOPRegAddr)) begin
            stallreq_for_reg1_loadrelate <= `Stop;
            reg1_o <= `ZeroWord;
        end
        else if ((reg1_read_o == `ReadEnable) && (ex_wreg_i == `ReadEnable) && (reg1_addr_o == ex_wd_i) && (ex_wd_i != `NOPRegAddr)) begin
            reg1_o <= ex_wdata_i;
        end
        else if ((reg1_read_o == `ReadEnable) && (mem_wreg_i == `ReadEnable) && (reg1_addr_o == mem_wd_i) && (mem_wd_i != `NOPRegAddr)) begin
            reg1_o <= mem_wdata_i;
        end
        else if (reg1_read_o == `ReadEnable) begin
            reg1_o <= reg1_data_i;                  //Regfile读端口1的输出值
        end
        else if (reg1_read_o == `ReadDisable) begin
            reg1_o <= imm;
        end
        else begin
            reg1_o <= `ZeroWord;
        end
    end

    //****************************第三段：确定进行运算的源操作数2***************************
    //给reg2赋值过程同样也增加了两种情况，参考第二段
    always @(*) begin
        stallreq_for_reg2_loadrelate <= `NoStop;
        if (rst == `RstEnable) begin
            reg2_o <= `ZeroWord;
        end
        else if ((pre_inst_is_load == 1'b1) && (ex_wd_i == reg2_addr_o) && (reg2_read_o == `ReadEnable) && (ex_wd_i != `NOPRegAddr)) begin
            stallreq_for_reg2_loadrelate <= `Stop;
            reg2_o <= `ZeroWord;
        end
        else if ((reg2_read_o == `ReadEnable) && (ex_wreg_i == `ReadEnable) && (reg2_addr_o == ex_wd_i) && (ex_wd_i != `NOPRegAddr)) begin
            reg2_o <= ex_wdata_i;
            text   <= 1'b1;
        end
        else if ((reg2_read_o == `ReadEnable) && (mem_wreg_i == `ReadEnable) && (reg2_addr_o == mem_wd_i) && (mem_wd_i != `NOPRegAddr)) begin
            reg2_o <= mem_wdata_i;
            text   <= 1'b0;
        end
        else if (reg2_read_o == `ReadEnable) begin
            reg2_o <= reg2_data_i;                              //Regfile读端口2的输出值
            text   <= 1'b1;
        end
        else if (reg2_read_o == `ReadDisable) begin
            reg2_o <= imm;                                      //立即数
            text   <= 1'b0;
        end
        else begin
            reg2_o <= `ZeroWord;
        end
    end
endmodule //id
