// ==============================================================================
// FPGA Studio — Hardware USB-UART Live Program Loader (115200 8-N-1 @ 25 MHz)
// Protocol: "PROG" + uint32_le(word_count) + word_count * uint32_le(inst_word)
// ==============================================================================
module uart_prog_loader #(
    parameter integer CLKS_PER_BIT = 217 // 25,000,000 Hz / 115,200 baud = 217
) (
    input  wire        clk,
    input  wire        rst,
    input  wire        uart_rx_i,
    output reg         prog_busy_o,
    output reg         prog_we_o,
    output reg         prog_dmem_we_o,
    output reg  [11:0] prog_addr_o,
    output reg  [31:0] prog_wdata_o,
    output wire        rx_byte_valid_o,
    output wire [7:0]  rx_byte_data_o
);

    // 1. Double-flop synchronizer on UART RX pin
    reg rx_sync1, rx_sync2;
    always @(posedge clk) begin
        rx_sync1 <= uart_rx_i;
        rx_sync2 <= rx_sync1;
    end

    // 2. 8-N-1 UART Byte Receiver
    localparam RX_IDLE  = 2'd0,
               RX_START = 2'd1,
               RX_DATA  = 2'd2,
               RX_STOP  = 2'd3;

    reg [1:0]  rx_state;
    reg [15:0] clk_cnt;
    reg [2:0]  bit_idx;
    reg [7:0]  rx_shift;
    reg        byte_ready;
    reg [7:0]  byte_val;

    assign rx_byte_valid_o = byte_ready && !prog_busy_o;
    assign rx_byte_data_o  = byte_val;

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            rx_state   <= RX_IDLE;
            clk_cnt    <= 16'd0;
            bit_idx    <= 3'd0;
            rx_shift   <= 8'd0;
            byte_ready <= 1'b0;
            byte_val   <= 8'd0;
        end else begin
            byte_ready <= 1'b0;
            case (rx_state)
                RX_IDLE: begin
                    clk_cnt <= 16'd0;
                    bit_idx <= 3'd0;
                    if (rx_sync2 == 1'b0)
                        rx_state <= RX_START;
                end
                RX_START: begin
                    if (clk_cnt == (CLKS_PER_BIT / 2)) begin
                        if (rx_sync2 == 1'b0) begin
                            clk_cnt  <= 16'd0;
                            rx_state <= RX_DATA;
                        end else begin
                            rx_state <= RX_IDLE;
                        end
                    end else begin
                        clk_cnt <= clk_cnt + 16'd1;
                    end
                end
                RX_DATA: begin
                    if (clk_cnt == CLKS_PER_BIT - 1) begin
                        clk_cnt <= 16'd0;
                        rx_shift[bit_idx] <= rx_sync2;
                        if (bit_idx == 3'd7) begin
                            bit_idx  <= 3'd0;
                            rx_state <= RX_STOP;
                        end else begin
                            bit_idx <= bit_idx + 3'd1;
                        end
                    end else begin
                        clk_cnt <= clk_cnt + 16'd1;
                    end
                end
                RX_STOP: begin
                    if (clk_cnt == CLKS_PER_BIT - 1) begin
                        clk_cnt    <= 16'd0;
                        byte_val   <= rx_shift;
                        byte_ready <= 1'b1;
                        rx_state   <= RX_IDLE;
                    end else begin
                        clk_cnt <= clk_cnt + 16'd1;
                    end
                end
            endcase
        end
    end

    // 3. "PROG" (IMEM) & "DMEM" (Data Memory) Packet State Machine
    localparam ST_M0   = 3'd0,
               ST_M1   = 3'd1,
               ST_M2   = 3'd2,
               ST_M3   = 3'd3,
               ST_LEN  = 3'd4,
               ST_DATA = 3'd5;

    reg [2:0]  st;
    reg        is_dmem;
    reg [1:0]  sub_byte;
    reg [31:0] words_rem;
    reg [31:0] word_buf;
    wire [31:0] next_word = {byte_val, word_buf[31:8]};

    always @(posedge clk or posedge rst) begin
        if (rst) begin
            st             <= ST_M0;
            is_dmem        <= 1'b0;
            sub_byte       <= 2'd0;
            words_rem      <= 32'd0;
            word_buf       <= 32'd0;
            prog_busy_o    <= 1'b0;
            prog_we_o      <= 1'b0;
            prog_dmem_we_o <= 1'b0;
            prog_addr_o    <= 12'd0;
            prog_wdata_o   <= 32'd0;
        end else begin
            prog_we_o      <= 1'b0;
            prog_dmem_we_o <= 1'b0;
            if (byte_ready) begin
                case (st)
                    ST_M0: begin
                        if (byte_val == 8'h50) begin // 'P' ("PROG")
                            is_dmem <= 1'b0;
                            st      <= ST_M1;
                        end else if (byte_val == 8'h44) begin // 'D' ("DMEM")
                            is_dmem <= 1'b1;
                            st      <= ST_M1;
                        end
                    end
                    ST_M1: begin
                        if (!is_dmem && byte_val == 8'h52) st <= ST_M2;      // 'R'
                        else if (is_dmem && byte_val == 8'h4D) st <= ST_M2;  // 'M'
                        else if (byte_val == 8'h50) begin is_dmem <= 1'b0; st <= ST_M1; end
                        else if (byte_val == 8'h44) begin is_dmem <= 1'b1; st <= ST_M1; end
                        else st <= ST_M0;
                    end
                    ST_M2: begin
                        if (!is_dmem && byte_val == 8'h4F) st <= ST_M3;      // 'O'
                        else if (is_dmem && byte_val == 8'h45) st <= ST_M3;  // 'E'
                        else if (byte_val == 8'h50) begin is_dmem <= 1'b0; st <= ST_M1; end
                        else if (byte_val == 8'h44) begin is_dmem <= 1'b1; st <= ST_M1; end
                        else st <= ST_M0;
                    end
                    ST_M3: begin
                        if ((!is_dmem && byte_val == 8'h47) || (is_dmem && byte_val == 8'h4D)) begin // 'G' or 'M'
                            st          <= ST_LEN;
                            sub_byte    <= 2'd0;
                            prog_busy_o <= 1'b1;
                        end else if (byte_val == 8'h50) begin
                            is_dmem <= 1'b0;
                            st      <= ST_M1;
                        end else if (byte_val == 8'h44) begin
                            is_dmem <= 1'b1;
                            st      <= ST_M1;
                        end else begin
                            st <= ST_M0;
                        end
                    end
                    ST_LEN: begin
                        word_buf <= next_word;
                        if (sub_byte == 2'd3) begin
                            sub_byte    <= 2'd0;
                            prog_addr_o <= is_dmem ? next_word[27:16] : 12'd0;
                            if ((is_dmem ? {16'd0, next_word[15:0]} : next_word) == 32'd0) begin
                                prog_busy_o <= 1'b0;
                                st          <= ST_M0;
                            end else begin
                                words_rem <= is_dmem ? {16'd0, next_word[15:0]} : next_word;
                                st        <= ST_DATA;
                            end
                        end else begin
                            sub_byte <= sub_byte + 2'd1;
                        end
                    end
                    ST_DATA: begin
                        word_buf <= next_word;
                        if (sub_byte == 2'd3) begin
                            sub_byte       <= 2'd0;
                            prog_we_o      <= ~is_dmem;
                            prog_dmem_we_o <= is_dmem;
                            prog_wdata_o   <= next_word;
                            if (words_rem <= 32'd1) begin
                                prog_busy_o <= 1'b0;
                                st          <= ST_M0;
                            end else begin
                                words_rem   <= words_rem - 32'd1;
                                prog_addr_o <= prog_addr_o + 12'd1;
                            end
                        end else begin
                            sub_byte <= sub_byte + 2'd1;
                        end
                    end
                    default: st <= ST_M0;
                endcase
            end
        end
    end
endmodule
