// ==============================================================================
// FPGA Studio — Digilent Nexys A7-100T SoC Top Module (openmips)
// Connects CPU Core + Reprogrammable 16KB IMEM + 16KB Byte-Lane DMEM + MMIO + UART
// ==============================================================================
module nexys_a7_soc_top (
    input  wire        CLK100MHZ,
    input  wire        CPU_RESETN,
    input  wire [15:0] SW,
    output reg  [15:0] LED,
    output reg  [6:0]  SEG_CA,
    output wire        SEG_DP,
    output reg  [7:0]  SEG_AN,
    input  wire        BTNC,
    input  wire        BTNU,
    input  wire        BTNL,
    input  wire        BTNR,
    input  wire        BTND,
    output wire        LED16_R,
    output wire        LED16_G,
    output wire        LED16_B,
    output wire        LED17_R,
    output wire        LED17_G,
    output wire        LED17_B,
    input  wire        UART_TXD_IN,
    output reg         UART_RXD_OUT
);

    // 1. 25 MHz CPU System Clock Divider (ensures clean Artix-7 timing closure)
    reg [1:0] clk_div = 2'd0;
    always @(posedge CLK100MHZ) clk_div <= clk_div + 2'd1;
    wire sys_clk = clk_div[1]; // 25 MHz
    wire ext_rst = ~CPU_RESETN;

    // 2. USB-UART Live Program Loader ("PROG" & "DMEM" protocol @ 115200 baud)
    wire        prog_busy;
    wire        prog_we;
    wire        prog_dmem_we;
    wire [11:0] prog_addr;
    wire [31:0] prog_wdata;
    wire        rx_valid;
    wire [7:0]  rx_byte;

    uart_prog_loader #(
        .CLKS_PER_BIT(217)
    ) u_loader (
        .clk             (sys_clk),
        .rst             (ext_rst),
        .uart_rx_i       (UART_TXD_IN),
        .prog_busy_o     (prog_busy),
        .prog_we_o       (prog_we),
        .prog_dmem_we_o  (prog_dmem_we),
        .prog_addr_o     (prog_addr),
        .prog_wdata_o    (prog_wdata),
        .rx_byte_valid_o (rx_valid),
        .rx_byte_data_o  (rx_byte)
    );

    wire cpu_rst = ext_rst | prog_busy;

    // 3. Reprogrammable 4096-word (16 KB) Instruction Memory
    (* ram_style = "distributed" *) reg [31:0] imem [0:4095];
    initial begin
        $readmemh("program.hex", imem);
    end

    wire [31:0] rom_addr;
    wire        rom_ce;
    wire [31:0] rom_data = rom_ce ? imem[rom_addr[13:2]] : 32'd0;

    always @(posedge sys_clk) begin
        if (prog_we)
            imem[prog_addr] <= prog_wdata;
    end

    // 4. CPU Core Instantiation (openmips)
    wire [31:0] ram_addr;
    wire [31:0] ram_wdata;
    reg  [31:0] ram_rdata;
    wire        ram_we;
    wire        ram_ce;
    wire [3:0]  ram_sel;

    openmips u_cpu (
        .clk (sys_clk),
        .rst (cpu_rst),
        .rom_addr_o (rom_addr),
        .rom_data_i (rom_data),
        .rom_ce_o (rom_ce),
        .ram_addr_o (ram_addr),
        .ram_data_o (ram_wdata),
        .ram_data_i (ram_rdata),
        .ram_we_o (ram_we),
        .ram_ce_o (ram_ce),
        .ram_sel_o (ram_sel)
    );

    // 5. 4096-word (16 KB) Byte-Lane Data Memory
    (* ram_style = "distributed" *) reg [31:0] dmem [0:4095];
    initial begin
        $readmemh("dmem_init.hex", dmem);
    end

    wire is_mmio = (ram_addr[31:24] == 8'hF0) || (ram_addr[31:24] == 8'hFF);
    wire dmem_we = ram_ce && ram_we && !is_mmio;
    wire [11:0] dmem_idx = ram_addr[13:2];

    always @(posedge sys_clk) begin
        if (prog_dmem_we) begin
            dmem[prog_addr] <= prog_wdata;
        end else if (dmem_we) begin
            if (ram_sel[0]) dmem[dmem_idx][7:0]   <= ram_wdata[7:0];
            if (ram_sel[1]) dmem[dmem_idx][15:8]  <= ram_wdata[15:8];
            if (ram_sel[2]) dmem[dmem_idx][23:16] <= ram_wdata[23:16];
            if (ram_sel[3]) dmem[dmem_idx][31:24] <= ram_wdata[31:24];
        end
    end

    // 6. MMIO Peripherals & 115200-baud UART TX
    reg [31:0] seg7_reg;
    reg [23:0] rgb_reg;
    reg [7:0]  rx_latched;
    reg        rx_has_byte;

    // UART Transmitter (25 MHz / 217 = 115200 baud)
    reg [3:0]  tx_bit_idx;
    reg [15:0] tx_clk_cnt;
    reg [9:0]  tx_frame;
    reg        tx_busy;

    wire [5:0] btn_bus = {ext_rst, BTND, BTNR, BTNL, BTNU, BTNC};

    always @(posedge sys_clk or posedge cpu_rst) begin
        if (cpu_rst) begin
            LED          <= 16'd0;
            seg7_reg     <= 32'd0;
            rgb_reg      <= 24'd0;
            rx_latched   <= 8'd0;
            rx_has_byte  <= 1'b0;
            UART_RXD_OUT <= 1'b1;
            tx_busy      <= 1'b0;
            tx_clk_cnt   <= 16'd0;
            tx_bit_idx   <= 4'd0;
            tx_frame     <= 10'h3FF;
        end else begin
            if (rx_valid) begin
                rx_latched  <= rx_byte;
                rx_has_byte <= 1'b1;
            end

            // UART TX shifting
            if (tx_busy) begin
                UART_RXD_OUT <= tx_frame[0];
                if (tx_clk_cnt == 16'd216) begin
                    tx_clk_cnt <= 16'd0;
                    tx_frame   <= {1'b1, tx_frame[9:1]};
                    if (tx_bit_idx == 4'd9)
                        tx_busy <= 1'b0;
                    else
                        tx_bit_idx <= tx_bit_idx + 4'd1;
                end else begin
                    tx_clk_cnt <= tx_clk_cnt + 16'd1;
                end
            end else begin
                UART_RXD_OUT <= 1'b1;
            end

            // MMIO Writes
            if (ram_ce && ram_we) begin
                case (ram_addr)
                    32'hF0000000:  LED      <= ram_wdata[15:0];
                    32'hF0000008: seg7_reg <= ram_wdata;
                    32'hF0000018:  rgb_reg  <= ram_wdata[23:0];
                    32'hF0000010: begin
                        if (!tx_busy) begin
                            tx_frame   <= {1'b1, ram_wdata[7:0], 1'b0};
                            tx_busy    <= 1'b1;
                            tx_clk_cnt <= 16'd0;
                            tx_bit_idx <= 4'd0;
                        end
                    end
                    default: ;
                endcase
            end

            // Clear UART RX ready flag on read
            if (ram_ce && !ram_we && ram_addr == 32'hF0000010)
                rx_has_byte <= 1'b0;
        end
    end

    // MMIO & Data Memory Read Mux
    always @(*) begin
        if (!ram_ce) begin
            ram_rdata = 32'd0;
        end else if (is_mmio) begin
            case (ram_addr)
                32'hF0000000:  ram_rdata = {16'd0, LED};
                32'hF0000004:   ram_rdata = {16'd0, SW};
                32'hF0000008: ram_rdata = seg7_reg;
                32'hF000000C:  ram_rdata = {26'd0, btn_bus};
                32'hF0000010: ram_rdata = {24'd0, rx_latched};
                32'hF0000014: ram_rdata = {30'd0, ~tx_busy, rx_has_byte};
                32'hF0000018:  ram_rdata = {8'd0, rgb_reg};
                default:             ram_rdata = 32'd0;
            endcase
        end else begin
            ram_rdata = dmem[dmem_idx];
        end
    end

    // 7. 8-Digit Multiplexed 7-Segment Display Driver
    assign SEG_DP = 1'b1;
    reg [16:0] scan_cnt = 17'd0;
    always @(posedge sys_clk) scan_cnt <= scan_cnt + 17'd1;
    wire [2:0] digit_sel = scan_cnt[16:14];
    wire [3:0] nibble = seg7_reg[digit_sel * 4 +: 4];

    always @(*) begin
        SEG_AN = ~(8'b0000_0001 << digit_sel);
        case (nibble)
            4'h0: SEG_CA = 7'b1000000;
            4'h1: SEG_CA = 7'b1111001;
            4'h2: SEG_CA = 7'b0100100;
            4'h3: SEG_CA = 7'b0110000;
            4'h4: SEG_CA = 7'b0011001;
            4'h5: SEG_CA = 7'b0010010;
            4'h6: SEG_CA = 7'b0000010;
            4'h7: SEG_CA = 7'b1111000;
            4'h8: SEG_CA = 7'b0000000;
            4'h9: SEG_CA = 7'b0010000;
            4'hA: SEG_CA = 7'b0001000;
            4'hB: SEG_CA = 7'b0000011;
            4'hC: SEG_CA = 7'b1000110;
            4'hD: SEG_CA = 7'b0100001;
            4'hE: SEG_CA = 7'b0000110;
            4'hF: SEG_CA = 7'b0001110;
        endcase
    end

    // 8. PWM Driver for RGB LEDs (LD16, LD17 — 25% max duty cycle per Digilent spec)
    reg [9:0] pwm_cnt = 10'd0;
    always @(posedge sys_clk) pwm_cnt <= pwm_cnt + 10'd1;
    assign LED16_R = (pwm_cnt < {2'b00, rgb_reg[23:20], 4'd0});
    assign LED16_G = (pwm_cnt < {2'b00, rgb_reg[19:16], 4'd0});
    assign LED16_B = (pwm_cnt < {2'b00, rgb_reg[15:12], 4'd0});
    assign LED17_R = (pwm_cnt < {2'b00, rgb_reg[11:8],  4'd0});
    assign LED17_G = (pwm_cnt < {2'b00, rgb_reg[7:4],   4'd0});
    assign LED17_B = (pwm_cnt < {2'b00, rgb_reg[3:0],   4'd0});

endmodule
