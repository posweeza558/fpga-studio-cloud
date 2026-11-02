// =============================================================================
// FPGA Studio — Synthesizable 32-Bit 5-Stage Pipelined RISC-V RV32IM Processor
// Pipeline Stages: IF -> ID -> EX -> MEM -> WB
// Features:
//   - Full RV32I Base Integer ISA + RV32M Hardware Multiply/Divide Extension
//   - Hardware Data Forwarding Unit (EX/MEM -> EX, MEM/WB -> EX, WB -> ID)
//   - Hardware Load-Use Hazard Detection Unit (1-cycle stall bubble insertion)
//   - Early ID-Stage JAL Target Resolution (1-cycle flush) & EX-Stage Branch/JALR (2-cycle flush)
//   - Iterative 32-cycle radix-2 divider for DIV/DIVU/REM/REMU (stalls pipeline; no huge
//     combinational divider, so it closes timing on Artix-7 @ 25 MHz)
//   - Simulation-only performance counters (`ifndef SYNTHESIS) — plain event counts, no tuning
//   - Simulation-only RTL_ILLEGAL report for unsupported opcodes (executed as NOP in hardware)
// Halt convention: fetching the all-zero word 0x00000000 (an illegal RISC-V encoding, used as
// the zero padding after the program) stops the PC; the pipeline then drains and idles.
// =============================================================================
`timescale 1ns / 1ps

module riscv_rv32i (
    input  wire        clk,
    input  wire        rst,

    // Instruction Memory (ROM) Interface
    input  wire [31:0] rom_data_i,
    output wire [31:0] rom_addr_o,
    output wire        rom_ce_o,

    // Data Memory (RAM & MMIO) Interface
    input  wire [31:0] ram_data_i,
    output wire [31:0] ram_addr_o,
    output reg  [31:0] ram_data_o,
    output wire        ram_we_o,
    output reg  [3:0]  ram_sel_o,
    output wire        ram_ce_o
);

    // =========================================================================
    // Forward Declarations for Pipeline Control & Feedback Signals
    // =========================================================================
    wire        load_use_stall;
    wire        div_stall;
    wire        id_jal_taken;
    wire [31:0] id_jal_target;
    reg         ex_branch_taken;
    reg  [31:0] ex_branch_target;
    wire        branch_flush = id_jal_taken | ex_branch_taken;

    // =========================================================================
    // STAGE 1: Instruction Fetch (IF)
    // =========================================================================
    reg  [31:0] pc;
    wire [31:0] pc_plus_4   = pc + 32'd4;
    wire        fetch_valid = ~rst & (rom_data_i != 32'h00000000);

    assign rom_addr_o = pc;
    assign rom_ce_o   = ~rst;

    wire [31:0] next_pc = ex_branch_taken ? ex_branch_target :
                          div_stall       ? pc               :
                          id_jal_taken    ? id_jal_target    :
                          load_use_stall  ? pc               :
                          fetch_valid     ? pc_plus_4        : pc;

    always @(posedge clk) begin
        if (rst) begin
            pc <= 32'h00000000;
        end else begin
            pc <= next_pc;
        end
    end

    // =========================================================================
    // PIPELINE REGISTER: IF/ID
    // =========================================================================
    reg [31:0] if_id_pc;
    reg [31:0] if_id_inst;
    reg        if_id_valid;

    always @(posedge clk) begin
        if (rst) begin
            if_id_pc    <= 32'd0;
            if_id_inst  <= 32'h00000013; // NOP
            if_id_valid <= 1'b0;
        end else if (ex_branch_taken || (!load_use_stall && id_jal_taken)) begin
            if_id_pc    <= 32'd0;
            if_id_inst  <= 32'h00000013; // Flush wrong-path instruction
            if_id_valid <= 1'b0;
        end else if (!load_use_stall && !div_stall) begin
            if_id_pc    <= pc;
            if_id_inst  <= fetch_valid ? rom_data_i : 32'h00000013;
            if_id_valid <= fetch_valid;
        end
    end

    // =========================================================================
    // STAGE 2: Instruction Decode, Register File & Hazard Detection (ID)
    // =========================================================================
    wire [6:0] id_opcode = if_id_inst[6:0];
    wire [4:0] id_rd     = if_id_inst[11:7];
    wire [2:0] id_funct3 = if_id_inst[14:12];
    wire [4:0] id_rs1    = if_id_inst[19:15];
    wire [4:0] id_rs2    = if_id_inst[24:20];
    wire [6:0] id_funct7 = if_id_inst[31:25];

    wire [31:0] id_imm_i = {{20{if_id_inst[31]}}, if_id_inst[31:20]};
    wire [31:0] id_imm_s = {{20{if_id_inst[31]}}, if_id_inst[31:25], if_id_inst[11:7]};
    wire [31:0] id_imm_b = {{19{if_id_inst[31]}}, if_id_inst[31], if_id_inst[7], if_id_inst[30:25], if_id_inst[11:8], 1'b0};
    wire [31:0] id_imm_u = {if_id_inst[31:12], 12'b0};
    wire [31:0] id_imm_j = {{11{if_id_inst[31]}}, if_id_inst[31], if_id_inst[19:12], if_id_inst[20], if_id_inst[30:21], 1'b0};

    wire id_is_op_reg = (id_opcode == 7'b0110011);
    wire id_is_op_imm = (id_opcode == 7'b0010011);
    wire id_is_load   = (id_opcode == 7'b0000011);
    wire id_is_store  = (id_opcode == 7'b0100011);
    wire id_is_branch = (id_opcode == 7'b1100011);
    wire id_is_jal    = (id_opcode == 7'b1101111);
    wire id_is_jalr   = (id_opcode == 7'b1100111);
    wire id_is_lui    = (id_opcode == 7'b0110111);
    wire id_is_auipc  = (id_opcode == 7'b0010111);
    wire id_is_muldiv = id_is_op_reg && (id_funct7 == 7'b0000001);
    wire id_is_fence  = (id_opcode == 7'b0001111); // single-hart, no caches -> architectural NOP

    // Opcodes implemented by this core (everything else is reported as illegal in simulation)
    wire id_known = id_is_op_imm || id_is_load || id_is_store || id_is_branch || id_is_jal ||
                    id_is_jalr || id_is_lui || id_is_auipc || id_is_fence ||
                    (id_is_op_reg && (id_funct7 == 7'b0000000 || id_funct7 == 7'b0100000 || id_funct7 == 7'b0000001));
    wire id_illegal = if_id_valid && !id_known;

    wire id_reg_we   = if_id_valid && id_known && (id_is_op_reg || id_is_op_imm || id_is_load || id_is_jal || id_is_jalr || id_is_lui || id_is_auipc);
    wire id_uses_rs1 = if_id_valid && (id_is_op_reg || id_is_op_imm || id_is_load || id_is_store || id_is_branch || id_is_jalr);
    wire id_uses_rs2 = if_id_valid && (id_is_op_reg || id_is_store || id_is_branch);

    // 32x32 General Purpose Register File (x0 hardwired to 0, WB->ID write-through)
    reg  [31:0] regs [0:31];
    wire        reg_we;
    wire [4:0]  mem_wb_rd_w;
    wire [31:0] wb_data;

    wire [31:0] id_rdata1 = (id_rs1 == 5'd0) ? 32'd0 :
                            (reg_we && (mem_wb_rd_w == id_rs1)) ? wb_data : regs[id_rs1];
    wire [31:0] id_rdata2 = (id_rs2 == 5'd0) ? 32'd0 :
                            (reg_we && (mem_wb_rd_w == id_rs2)) ? wb_data : regs[id_rs2];

    // Early JAL target calculation in ID (1-cycle control hazard flush)
    assign id_jal_taken  = !ex_branch_taken && !load_use_stall && !div_stall && if_id_valid && id_is_jal;
    assign id_jal_target = if_id_pc + id_imm_j;

    // =========================================================================
    // PIPELINE REGISTER: ID/EX
    // =========================================================================
    reg [31:0] id_ex_pc;
    reg [31:0] id_ex_inst;
    reg        id_ex_valid;
    reg [4:0]  id_ex_rs1;
    reg [4:0]  id_ex_rs2;
    reg [4:0]  id_ex_rd;
    reg        id_ex_uses_rs1;
    reg        id_ex_uses_rs2;
    reg [2:0]  id_ex_funct3;
    reg [6:0]  id_ex_funct7;
    reg [31:0] id_ex_rdata1;
    reg [31:0] id_ex_rdata2;
    reg [31:0] id_ex_imm_i;
    reg [31:0] id_ex_imm_s;
    reg [31:0] id_ex_imm_b;
    reg [31:0] id_ex_imm_u;
    reg        id_ex_is_op_reg;
    reg        id_ex_is_op_imm;
    reg        id_ex_is_load;
    reg        id_ex_is_store;
    reg        id_ex_is_branch;
    reg        id_ex_is_jal;
    reg        id_ex_is_jalr;
    reg        id_ex_is_lui;
    reg        id_ex_is_auipc;
    reg        id_ex_is_muldiv;
    reg        id_ex_reg_we;
    reg        id_ex_illegal;

    // Hardware Load-Use Hazard Detection Unit
    assign load_use_stall = !ex_branch_taken && id_ex_valid && id_ex_is_load && (id_ex_rd != 5'd0) &&
                            ((id_uses_rs1 && (id_ex_rd == id_rs1)) || (id_uses_rs2 && (id_ex_rd == id_rs2)));

    always @(posedge clk) begin
        if (rst || ex_branch_taken || load_use_stall) begin
            id_ex_pc        <= 32'd0;
            id_ex_inst      <= 32'h00000013;
            id_ex_valid     <= 1'b0;
            id_ex_rs1       <= 5'd0;
            id_ex_rs2       <= 5'd0;
            id_ex_rd        <= 5'd0;
            id_ex_uses_rs1  <= 1'b0;
            id_ex_uses_rs2  <= 1'b0;
            id_ex_funct3    <= 3'd0;
            id_ex_funct7    <= 7'd0;
            id_ex_rdata1    <= 32'd0;
            id_ex_rdata2    <= 32'd0;
            id_ex_imm_i     <= 32'd0;
            id_ex_imm_s     <= 32'd0;
            id_ex_imm_b     <= 32'd0;
            id_ex_imm_u     <= 32'd0;
            id_ex_is_op_reg <= 1'b0;
            id_ex_is_op_imm <= 1'b0;
            id_ex_is_load   <= 1'b0;
            id_ex_is_store  <= 1'b0;
            id_ex_is_branch <= 1'b0;
            id_ex_is_jal    <= 1'b0;
            id_ex_is_jalr   <= 1'b0;
            id_ex_is_lui    <= 1'b0;
            id_ex_is_auipc  <= 1'b0;
            id_ex_is_muldiv <= 1'b0;
            id_ex_reg_we    <= 1'b0;
            id_ex_illegal   <= 1'b0;
        end else if (div_stall) begin
            // Hold the divide instruction in EX until the iterative divider finishes
        end else begin
            id_ex_pc        <= if_id_pc;
            id_ex_inst      <= if_id_inst;
            id_ex_valid     <= if_id_valid;
            id_ex_rs1       <= id_rs1;
            id_ex_rs2       <= id_rs2;
            id_ex_rd        <= id_rd;
            id_ex_uses_rs1  <= id_uses_rs1;
            id_ex_uses_rs2  <= id_uses_rs2;
            id_ex_funct3    <= id_funct3;
            id_ex_funct7    <= id_funct7;
            id_ex_rdata1    <= id_rdata1;
            id_ex_rdata2    <= id_rdata2;
            id_ex_imm_i     <= id_imm_i;
            id_ex_imm_s     <= id_imm_s;
            id_ex_imm_b     <= id_imm_b;
            id_ex_imm_u     <= id_imm_u;
            id_ex_is_op_reg <= id_is_op_reg;
            id_ex_is_op_imm <= id_is_op_imm;
            id_ex_is_load   <= id_is_load;
            id_ex_is_store  <= id_is_store;
            id_ex_is_branch <= id_is_branch;
            id_ex_is_jal    <= id_is_jal;
            id_ex_is_jalr   <= id_is_jalr;
            id_ex_is_lui    <= id_is_lui;
            id_ex_is_auipc  <= id_is_auipc;
            id_ex_is_muldiv <= id_is_muldiv;
            id_ex_reg_we    <= id_reg_we;
            id_ex_illegal   <= id_illegal;
        end
    end

    // =========================================================================
    // STAGE 3: Execute, Forwarding Unit & Branch/JALR Resolution (EX)
    // =========================================================================
    reg        ex_mem_valid;
    reg        ex_mem_reg_we;
    reg        ex_mem_is_load;
    reg [4:0]  ex_mem_rd;
    reg [31:0] ex_mem_alu_res;

    // Hardware Forwarding Unit (2'b10 = EX/MEM->EX, 2'b01 = MEM/WB->EX, 2'b00 = ID/EX Reg)
    wire [1:0] fwd_a = (!id_ex_valid || !id_ex_uses_rs1 || (id_ex_rs1 == 5'd0)) ? 2'b00 :
                       (ex_mem_valid && ex_mem_reg_we && !ex_mem_is_load && (ex_mem_rd == id_ex_rs1)) ? 2'b10 :
                       (reg_we && (mem_wb_rd_w == id_ex_rs1)) ? 2'b01 : 2'b00;

    wire [1:0] fwd_b = (!id_ex_valid || !id_ex_uses_rs2 || (id_ex_rs2 == 5'd0)) ? 2'b00 :
                       (ex_mem_valid && ex_mem_reg_we && !ex_mem_is_load && (ex_mem_rd == id_ex_rs2)) ? 2'b10 :
                       (reg_we && (mem_wb_rd_w == id_ex_rs2)) ? 2'b01 : 2'b00;

    wire [31:0] rdata1 = (fwd_a == 2'b10) ? ex_mem_alu_res :
                         (fwd_a == 2'b01) ? wb_data        : id_ex_rdata1;

    wire [31:0] rdata2 = (fwd_b == 2'b10) ? ex_mem_alu_res :
                         (fwd_b == 2'b01) ? wb_data        : id_ex_rdata2;

    // Compatibility alias signals for waveform inspection
    wire [6:0] opcode    = id_ex_inst[6:0];
    wire [2:0] funct3    = id_ex_funct3;
    wire [6:0] funct7    = id_ex_funct7;
    wire [4:0] rs1       = id_ex_rs1;
    wire [4:0] rs2       = id_ex_rs2;
    wire [4:0] rd        = id_ex_rd;
    wire       is_muldiv = id_ex_is_muldiv;

    wire [31:0] alu_in2   = id_ex_is_op_imm ? id_ex_imm_i : rdata2;
    wire [4:0]  alu_shamt = id_ex_is_op_imm ? id_ex_inst[24:20] : rdata2[4:0];
    wire        sub_sra   = id_ex_is_op_reg ? id_ex_funct7[5] : (id_ex_is_op_imm && (id_ex_funct3 == 3'b101) && id_ex_funct7[5]);

    // Dedicated signed wire for SRA/SRAI to prevent Verilog ternary unsigned coercion
    wire signed [31:0] rdata1_signed = rdata1;
    wire        [31:0] sra_res       = rdata1_signed >>> alu_shamt;

    wire signed [63:0] prod_ss = $signed(rdata1) * $signed(rdata2);
    wire signed [63:0] prod_su = $signed({1'b0, rdata2}) * $signed(rdata1);
    wire        [63:0] prod_uu = {32'd0, rdata1} * {32'd0, rdata2};

    // -------------------------------------------------------------------------
    // Iterative radix-2 restoring divider (DIV/DIVU/REM/REMU), 32 iterations.
    // Operands are latched at start, so forwarding sources may leave the pipe.
    // -------------------------------------------------------------------------
    wire        ex_is_div  = id_ex_valid && id_ex_is_muldiv && id_ex_funct3[2];
    wire        div_signed = ~id_ex_funct3[0];          // 100 DIV, 110 REM signed
    reg         div_busy;
    reg         div_done;
    reg  [5:0]  div_cnt;
    reg  [31:0] div_quo;
    reg  [31:0] div_rem;
    reg  [31:0] div_dvs;
    reg         div_neg_q;
    reg         div_neg_r;
    reg  [31:0] div_q_res;
    reg  [31:0] div_r_res;
    wire        div_start  = ex_is_div && !div_busy && !div_done;
    assign      div_stall  = ex_is_div && !div_done;

    wire        dv_a_neg   = div_signed && rdata1[31];
    wire        dv_b_neg   = div_signed && rdata2[31];
    wire [31:0] dv_a_abs   = dv_a_neg ? (~rdata1 + 32'd1) : rdata1;
    wire [31:0] dv_b_abs   = dv_b_neg ? (~rdata2 + 32'd1) : rdata2;
    wire [32:0] div_trial  = {div_rem, div_quo[31]} - {1'b0, div_dvs};

    always @(posedge clk) begin
        if (rst) begin
            div_busy  <= 1'b0;
            div_done  <= 1'b0;
            div_cnt   <= 6'd0;
            div_quo   <= 32'd0;
            div_rem   <= 32'd0;
            div_dvs   <= 32'd0;
            div_neg_q <= 1'b0;
            div_neg_r <= 1'b0;
            div_q_res <= 32'd0;
            div_r_res <= 32'd0;
        end else if (div_done) begin
            div_done <= 1'b0;                           // result consumed this cycle
        end else if (div_start) begin
            if (rdata2 == 32'd0) begin                  // RISC-V: x/0 = -1, x%0 = x
                div_q_res <= 32'hFFFFFFFF;
                div_r_res <= rdata1;
                div_done  <= 1'b1;
            end else begin
                div_busy  <= 1'b1;
                div_cnt   <= 6'd32;
                div_quo   <= dv_a_abs;
                div_rem   <= 32'd0;
                div_dvs   <= dv_b_abs;
                div_neg_q <= dv_a_neg ^ dv_b_neg;
                div_neg_r <= dv_a_neg;
            end
        end else if (div_busy) begin
            if (!div_trial[32]) begin
                div_rem <= div_trial[31:0];
                div_quo <= {div_quo[30:0], 1'b1};
            end else begin
                div_rem <= {div_rem[30:0], div_quo[31]};
                div_quo <= {div_quo[30:0], 1'b0};
            end
            div_cnt <= div_cnt - 6'd1;
            if (div_cnt == 6'd1) begin
                div_busy  <= 1'b0;
                div_done  <= 1'b1;
                div_q_res <= div_neg_q ? (~(div_trial[32] ? {div_quo[30:0], 1'b0} : {div_quo[30:0], 1'b1}) + 32'd1)
                                       :  (div_trial[32] ? {div_quo[30:0], 1'b0} : {div_quo[30:0], 1'b1});
                div_r_res <= div_neg_r ? (~(div_trial[32] ? {div_rem[30:0], div_quo[31]} : div_trial[31:0]) + 32'd1)
                                       :  (div_trial[32] ? {div_rem[30:0], div_quo[31]} : div_trial[31:0]);
            end
        end
    end

    reg [31:0] alu_raw;
    always @(*) begin
        if (id_ex_is_muldiv) begin
            case (id_ex_funct3)
                3'b000: alu_raw = prod_ss[31:0];                                // MUL
                3'b001: alu_raw = prod_ss[63:32];                               // MULH
                3'b010: alu_raw = prod_su[63:32];                               // MULHSU
                3'b011: alu_raw = prod_uu[63:32];                               // MULHU
                3'b100, 3'b101: alu_raw = div_q_res;                            // DIV / DIVU
                default:        alu_raw = div_r_res;                            // REM / REMU
            endcase
        end else begin
            case (id_ex_funct3)
                3'b000: alu_raw = (id_ex_is_op_reg && sub_sra) ? (rdata1 - rdata2) : (rdata1 + alu_in2);
                3'b001: alu_raw = rdata1 << alu_shamt;
                3'b010: alu_raw = ($signed(rdata1) < $signed(alu_in2)) ? 32'd1 : 32'd0;
                3'b011: alu_raw = (rdata1 < alu_in2) ? 32'd1 : 32'd0;
                3'b100: alu_raw = rdata1 ^ alu_in2;
                3'b101: alu_raw = sub_sra ? sra_res : (rdata1 >> alu_shamt);
                3'b110: alu_raw = rdata1 | alu_in2;
                3'b111: alu_raw = rdata1 & alu_in2;
            endcase
        end
    end

    wire [31:0] ex_eff_addr = id_ex_is_store ? (rdata1 + id_ex_imm_s) : (rdata1 + id_ex_imm_i);
    wire [31:0] alu_res = id_ex_is_lui   ? id_ex_imm_u :
                          id_ex_is_auipc ? (id_ex_pc + id_ex_imm_u) :
                          (id_ex_is_jal || id_ex_is_jalr) ? (id_ex_pc + 32'd4) :
                          (id_ex_is_load || id_ex_is_store) ? ex_eff_addr : alu_raw;

    // Conditional Branch & JALR Resolution in EX (2-cycle flush when taken)
    reg branch_cond;
    always @(*) begin
        branch_cond = 1'b0;
        if (id_ex_is_branch) begin
            case (id_ex_funct3)
                3'b000: branch_cond = (rdata1 == rdata2);                   // BEQ
                3'b001: branch_cond = (rdata1 != rdata2);                   // BNE
                3'b100: branch_cond = ($signed(rdata1) <  $signed(rdata2)); // BLT
                3'b101: branch_cond = ($signed(rdata1) >= $signed(rdata2)); // BGE
                3'b110: branch_cond = (rdata1 <  rdata2);                   // BLTU
                3'b111: branch_cond = (rdata1 >= rdata2);                   // BGEU
                default: branch_cond = 1'b0;
            endcase
        end
        ex_branch_taken  = id_ex_valid && (id_ex_is_jalr || (id_ex_is_branch && branch_cond));
        ex_branch_target = id_ex_is_jalr ? ((rdata1 + id_ex_imm_i) & ~32'd1) : (id_ex_pc + id_ex_imm_b);
    end

    wire branch_taken = ex_branch_taken | id_jal_taken;

    // =========================================================================
    // PIPELINE REGISTER: EX/MEM
    // =========================================================================
    reg [31:0] ex_mem_pc;
    reg [31:0] ex_mem_inst;
    reg [31:0] ex_mem_wdata;
    reg        ex_mem_is_store;
    reg [2:0]  ex_mem_funct3;

    always @(posedge clk) begin
        if (rst) begin
            ex_mem_pc       <= 32'd0;
            ex_mem_inst     <= 32'h00000013;
            ex_mem_valid    <= 1'b0;
            ex_mem_alu_res  <= 32'd0;
            ex_mem_wdata    <= 32'd0;
            ex_mem_rd       <= 5'd0;
            ex_mem_reg_we   <= 1'b0;
            ex_mem_is_load  <= 1'b0;
            ex_mem_is_store <= 1'b0;
            ex_mem_funct3   <= 3'd0;
        end else if (div_stall) begin
            // Divider busy: send a bubble down the pipe while the divide stays in EX
            ex_mem_valid    <= 1'b0;
            ex_mem_reg_we   <= 1'b0;
            ex_mem_is_load  <= 1'b0;
            ex_mem_is_store <= 1'b0;
            ex_mem_inst     <= 32'h00000013;
            ex_mem_pc       <= 32'd0;
        end else begin
            ex_mem_pc       <= id_ex_pc;
            ex_mem_inst     <= id_ex_inst;
            ex_mem_valid    <= id_ex_valid;
            ex_mem_alu_res  <= alu_res;
            ex_mem_wdata    <= rdata2;
            ex_mem_rd       <= id_ex_rd;
            ex_mem_reg_we   <= id_ex_reg_we;
            ex_mem_is_load  <= id_ex_is_load;
            ex_mem_is_store <= id_ex_is_store;
            ex_mem_funct3   <= id_ex_funct3;
        end
    end

    // =========================================================================
    // STAGE 4: Data Memory & MMIO Access (MEM)
    // =========================================================================
    wire [31:0] eff_addr = ex_mem_alu_res;
    assign ram_addr_o = eff_addr;
    assign ram_we_o   = ex_mem_valid & ex_mem_is_store & ~rst;
    assign ram_ce_o   = ex_mem_valid & (ex_mem_is_load | ex_mem_is_store) & ~rst;

    always @(*) begin
        ram_data_o = ex_mem_wdata;
        ram_sel_o  = 4'b1111;
        if (ex_mem_valid && ex_mem_is_store) begin
            case (ex_mem_funct3)
                3'b000: begin // SB
                    ram_data_o = {4{ex_mem_wdata[7:0]}};
                    ram_sel_o  = 4'b0001 << eff_addr[1:0];
                end
                3'b001: begin // SH
                    ram_data_o = {2{ex_mem_wdata[15:0]}};
                    ram_sel_o  = eff_addr[1] ? 4'b1100 : 4'b0011;
                end
                default: begin // SW
                    ram_data_o = ex_mem_wdata;
                    ram_sel_o  = 4'b1111;
                end
            endcase
        end
    end

    reg [7:0]  load_byte;
    reg [15:0] load_half;
    reg [31:0] load_val;
    always @(*) begin
        case (eff_addr[1:0])
            2'b00: load_byte = ram_data_i[7:0];
            2'b01: load_byte = ram_data_i[15:8];
            2'b10: load_byte = ram_data_i[23:16];
            2'b11: load_byte = ram_data_i[31:24];
        endcase
        load_half = eff_addr[1] ? ram_data_i[31:16] : ram_data_i[15:0];
        case (ex_mem_funct3)
            3'b000: load_val = {{24{load_byte[7]}}, load_byte};   // LB
            3'b001: load_val = {{16{load_half[15]}}, load_half};  // LH
            3'b010: load_val = ram_data_i;                        // LW
            3'b100: load_val = {24'd0, load_byte};                // LBU
            3'b101: load_val = {16'd0, load_half};                // LHU
            default: load_val = ram_data_i;
        endcase
    end

    wire [31:0] mem_stage_out = ex_mem_is_load ? load_val : ex_mem_alu_res;

    // =========================================================================
    // PIPELINE REGISTER: MEM/WB & STAGE 5: Writeback (WB)
    // =========================================================================
    reg [31:0] mem_wb_pc;
    reg [31:0] mem_wb_inst;
    reg        mem_wb_valid;
    reg [31:0] mem_wb_wdata;
    reg [4:0]  mem_wb_rd;
    reg        mem_wb_reg_we;

    always @(posedge clk) begin
        if (rst) begin
            mem_wb_pc     <= 32'd0;
            mem_wb_inst   <= 32'h00000013;
            mem_wb_valid  <= 1'b0;
            mem_wb_wdata  <= 32'd0;
            mem_wb_rd     <= 5'd0;
            mem_wb_reg_we <= 1'b0;
        end else begin
            mem_wb_pc     <= ex_mem_pc;
            mem_wb_inst   <= ex_mem_inst;
            mem_wb_valid  <= ex_mem_valid;
            mem_wb_wdata  <= mem_stage_out;
            mem_wb_rd     <= ex_mem_rd;
            mem_wb_reg_we <= ex_mem_reg_we;
        end
    end

    assign wb_data     = mem_wb_wdata;
    assign mem_wb_rd_w = mem_wb_rd;
    assign reg_we      = mem_wb_valid & mem_wb_reg_we;

    integer idx;
    initial begin
        for (idx = 0; idx < 32; idx = idx + 1)
            regs[idx] = 32'd0;
    end

    always @(posedge clk) begin
        if (rst) begin
            for (idx = 0; idx < 32; idx = idx + 1)
                regs[idx] <= 32'd0;
        end else if (reg_we && (mem_wb_rd != 5'd0)) begin
            regs[mem_wb_rd] <= wb_data;
        end
    end


`ifndef SYNTHESIS
    // =========================================================================
    // Simulation-only Performance Counters (plain event counts, no windowing)
    //   rtl_cycle_cnt      : clock cycles since reset while the pipeline is active
    //   rtl_inst_retired   : instructions written back (valid in WB)
    //   rtl_mem_done       : instructions that completed the MEM stage (used by the
    //                        testbench to stop exactly after N instructions' stores)
    //   rtl_load_stalls    : cycles the load-use hazard unit froze IF/ID
    //   rtl_div_stalls     : cycles the iterative divider froze the pipeline
    //   rtl_ex_fwds        : register values bypassed EX/MEM -> EX (once per register)
    //   rtl_mem_fwds       : register values bypassed MEM/WB -> EX (once per register)
    //   rtl_branch_flushes : wrong-path pipeline slots squashed (JAL=1, branch/JALR=2)
    // =========================================================================
    reg [31:0] rtl_cycle_cnt;
    reg [31:0] rtl_inst_retired;
    reg [31:0] rtl_mem_done;
    reg [31:0] rtl_load_stalls;
    reg [31:0] rtl_div_stalls;
    reg [31:0] rtl_ex_fwds;
    reg [31:0] rtl_mem_fwds;
    reg [31:0] rtl_branch_flushes;

    wire       pipe_active  = fetch_valid | if_id_valid | id_ex_valid | ex_mem_valid | mem_wb_valid;
    wire       fwd_count_en = id_ex_valid && (!div_stall || div_start);
    wire       fwd_b_unique = (id_ex_rs2 != id_ex_rs1) || (fwd_a != fwd_b);
    wire [1:0] ex_fwd_inc   = ((fwd_a == 2'b10) ? 2'd1 : 2'd0) + (((fwd_b == 2'b10) && fwd_b_unique) ? 2'd1 : 2'd0);
    wire [1:0] mem_fwd_inc  = ((fwd_a == 2'b01) ? 2'd1 : 2'd0) + (((fwd_b == 2'b01) && fwd_b_unique) ? 2'd1 : 2'd0);
    wire [1:0] flush_inc    = ex_branch_taken ? 2'd2 : (id_jal_taken ? 2'd1 : 2'd0);

    always @(posedge clk) begin
        if (rst) begin
            rtl_cycle_cnt      <= 32'd0;
            rtl_inst_retired   <= 32'd0;
            rtl_mem_done       <= 32'd0;
            rtl_load_stalls    <= 32'd0;
            rtl_div_stalls     <= 32'd0;
            rtl_ex_fwds        <= 32'd0;
            rtl_mem_fwds       <= 32'd0;
            rtl_branch_flushes <= 32'd0;
        end else if (pipe_active) begin
            rtl_cycle_cnt      <= rtl_cycle_cnt + 32'd1;
            rtl_inst_retired   <= rtl_inst_retired + {31'd0, mem_wb_valid};
            rtl_mem_done       <= rtl_mem_done + {31'd0, ex_mem_valid};
            rtl_load_stalls    <= rtl_load_stalls + {31'd0, load_use_stall};
            rtl_div_stalls     <= rtl_div_stalls + {31'd0, div_stall};
            rtl_branch_flushes <= rtl_branch_flushes + {30'd0, flush_inc};
            if (fwd_count_en) begin
                rtl_ex_fwds  <= rtl_ex_fwds + {30'd0, ex_fwd_inc};
                rtl_mem_fwds <= rtl_mem_fwds + {30'd0, mem_fwd_inc};
            end
        end
    end

    // Report unsupported instructions instead of silently swallowing them
    always @(posedge clk) begin
        if (!rst && id_ex_valid && id_ex_illegal && !div_stall)
            $display("RTL_ILLEGAL pc=0x%08X inst=0x%08X (executed as NOP)", id_ex_pc, id_ex_inst);
    end
`endif

endmodule
