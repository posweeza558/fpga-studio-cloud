// =============================================================================
// File: alu_only_cpu.v
// Architecture: Minimalist 32-Bit ALU-Only Processor Core (MIPS-Compatible ALU)
//
// Description:
//   A pure Arithmetic Logic Unit (ALU) execution CPU core designed for 
//   high-speed arithmetic, logic, and bit-manipulation tasks.
//
// Features:
//   - 32-bit Program Counter (PC)
//   - 32 General-Purpose 32-bit Registers ( .. )
//   - Pure 32-bit Single-Cycle ALU:
//       * Arithmetic: ADD, ADDU, SUB, SUBU, MULT
//       * Bitwise Logic: AND, OR, XOR, NOR
//       * Barrel Shifter: SLL, SRL, SRA
//       * Comparisons: SLT, SLTU
//   - No Data Memory (D-MEM) / No Load-Store Unit
//   - No Peripheral MMIO (Standalone Compute Core, No FPGA Pin I/O)
// =============================================================================

	imescale 1ns / 1ps

module alu_only_cpu (
    input  wire        clk,           // System Clock
    input  wire        rst_n,         // Active-Low Reset
    output reg  [31:0] pc,            // Program Counter
    input  wire [31:0] instr,         // 32-bit Instruction input from ROM
    output reg  [31:0] alu_out,       // ALU Output Bus (Result of last computation)
    output wire        zero_flag,     // Zero Flag: Set when ALU result is 0
    output wire        negative_flag  // Negative Flag: Set when MSB of result is 1
);

    // =========================================================================
    // Instruction Fields (Standard 32-bit R-type & I-type Formats)
    // =========================================================================
    wire [5:0]  opcode = instr[31:26];
    wire [4:0]  rs     = instr[25:21];
    wire [4:0]  rt     = instr[20:16];
    wire [4:0]  rd     = instr[15:11];
    wire [4:0]  shamt  = instr[10:6];
    wire [5:0]  funct  = instr[5:0];
    wire [15:0] imm16  = instr[15:0];

    // Sign-extended & Zero-extended Immediates
    wire [31:0] sign_ext_imm = {{16{imm16[15]}}, imm16};
    wire [31:0] zero_ext_imm = {16'h0000, imm16};

    // =========================================================================
    // Register File: 32 x 32-bit (Register 0 is hardwired to 0)
    // =========================================================================
    reg [31:0] registers [0:31];
    integer i;

    wire [31:0] rdata1 = (rs == 5'd0) ? 32'd0 : registers[rs];
    wire [31:0] rdata2 = (rt == 5'd0) ? 32'd0 : registers[rt];

    // =========================================================================
    // ALU Input Multiplexers
    // =========================================================================
    wire is_itype = (opcode != 6'b000000);
    wire is_unsigned_imm = (opcode == 6'b001100) || (opcode == 6'b001101) || (opcode == 6'b001110);

    wire [31:0] alu_operand_a = rdata1;
    wire [31:0] alu_operand_b = is_itype ? (is_unsigned_imm ? zero_ext_imm : sign_ext_imm) : rdata2;
    wire [4:0]  write_reg     = is_itype ? rt : rd;
    wire        reg_write_en  = (write_reg != 5'd0);

    // =========================================================================
    // 32-Bit Arithmetic Logic Unit (ALU Core)
    // =========================================================================
    always @(*) begin
        if (opcode == 6'b000000) begin
            // R-Type Instructions based on Funct
            case (funct)
                6'h20: alu_out = alu_operand_a + alu_operand_b;                              // ADD
                6'h21: alu_out = alu_operand_a + alu_operand_b;                              // ADDU
                6'h22: alu_out = alu_operand_a - alu_operand_b;                              // SUB
                6'h23: alu_out = alu_operand_a - alu_operand_b;                              // SUBU
                6'h24: alu_out = alu_operand_a & alu_operand_b;                              // AND
                6'h25: alu_out = alu_operand_a | alu_operand_b;                              // OR
                6'h26: alu_out = alu_operand_a ^ alu_operand_b;                              // XOR
                6'h27: alu_out = ~(alu_operand_a | alu_operand_b);                           // NOR
                6'h2A: alu_out = ((alu_operand_a) < (alu_operand_b)) ? 32'd1 : 32'd0; // SLT (Signed)
                6'h2B: alu_out = (alu_operand_a < alu_operand_b) ? 32'd1 : 32'd0;            // SLTU (Unsigned)
                6'h00: alu_out = alu_operand_b << shamt;                                     // SLL (Shift Left Logical)
                6'h02: alu_out = alu_operand_b >> shamt;                                     // SRL (Shift Right Logical)
                6'h03: alu_out = (alu_operand_b) >>> shamt;                           // SRA (Shift Right Arithmetic)
                6'h04: alu_out = alu_operand_b << alu_operand_a[4:0];                        // SLLV (Variable)
                6'h06: alu_out = alu_operand_b >> alu_operand_a[4:0];                        // SRLV (Variable)
                6'h07: alu_out = (alu_operand_b) >>> alu_operand_a[4:0];              // SRAV (Variable)
                default: alu_out = 32'd0;
            endcase
        end else begin
            // I-Type ALU Instructions based on Opcode
            case (opcode)
                6'b001000: alu_out = alu_operand_a + alu_operand_b;                          // ADDI
                6'b001001: alu_out = alu_operand_a + alu_operand_b;                          // ADDIU
                6'b001100: alu_out = alu_operand_a & alu_operand_b;                          // ANDI
                6'b001101: alu_out = alu_operand_a | alu_operand_b;                          // ORI
                6'b001110: alu_out = alu_operand_a ^ alu_operand_b;                          // XORI
                6'b001010: alu_out = ((alu_operand_a) < (alu_operand_b)) ? 32'd1 : 32'd0; // SLTI
                6'b001011: alu_out = (alu_operand_a < alu_operand_b) ? 32'd1 : 32'd0;        // SLTIU
                6'b001111: alu_out = {imm16, 16'h0000};                                      // LUI (Load Upper Immediate)
                default:   alu_out = 32'd0;
            endcase
        end
    end

    // Flags
    assign zero_flag     = (alu_out == 32'd0);
    assign negative_flag = alu_out[31];

    // =========================================================================
    // Synchronous Program Counter & Register File Writeback
    // =========================================================================
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            pc <= 32'h00000000;
            for (i = 0; i < 32; i = i + 1) begin
                registers[i] <= 32'd0;
            end
        end else begin
            pc <= pc + 32'd4;
            if (reg_write_en) begin
                registers[write_reg] <= alu_out;
            end
        end
    end

endmodule
