/**
 * ==============================================================================
 * FPGA Studio / Digilent Nexys A7 - Interactive VGA Snake Game
 * ==============================================================================
 * Display: VGA 640x480 Framebuffer (80x60 Grid mapped at 0xFF000000)
 * Controls: Directional Push Buttons (MMIO at 0xF000000C)
 *   - BTNU (Up, Bit 1)    : Move Up
 *   - BTND (Down, Bit 4)  : Move Down
 *   - BTNL (Left, Bit 2)  : Move Left
 *   - BTNR (Right, Bit 3) : Move Right
 *   - BTNC (Center, Bit 0): Restart Game
 * Peripherals:
 *   - 7-Segment (0xF0000008) : Live Score Counter
 *   - 16 LEDs   (0xF0000000) : Binary Progress Lights
 *   - RGB LEDs  (0xF0000018) : Game Status (Green = Play, Red = Game Over)
 *   - UART TX   (0xF0000010) : Live Terminal Announcer
 * ==============================================================================
 */

#include "nexys_a7.h"

#define GRID_W 80
#define GRID_H 60
#define MAX_SNAKE_LEN 64

// Color Palette (24-bit RGB)
#define COLOR_BG      0x0A0E0C  // Dark green-tinted background
#define COLOR_WALL    0x1ED760  // Spotify Accent Green Border
#define COLOR_HEAD    0x00FFCC  // Bright Neon Cyan-Green Head
#define COLOR_BODY    0x1DB954  // Spotify Body Green
#define COLOR_FOOD    0xFF3344  // Crisp Apple Red

// Draw a single tile on the 80x60 VGA screen
static inline void vga_draw_pixel(int x, int y, unsigned int color) {
    if (x >= 0 && x < GRID_W && y >= 0 && y < GRID_H) {
        VGA_VRAM[y * GRID_W + x] = color;
    }
}

void main() {
    int snake_x[MAX_SNAKE_LEN];
    int snake_y[MAX_SNAKE_LEN];
    int snake_len;
    int dir_x, dir_y;
    int food_x, food_y;
    int score;
    int game_over;
    unsigned int last_btn = 0;

restart:
    // 1. Initialize Game State Immediately
    snake_len = 4;
    snake_x[0] = 40; snake_y[0] = 30; // Head
    snake_x[1] = 39; snake_y[1] = 30;
    snake_x[2] = 38; snake_y[2] = 30;
    snake_x[3] = 37; snake_y[3] = 30; // Tail
    dir_x = 1;
    dir_y = 0;
    food_x = 55;
    food_y = 20;
    score = 0;
    game_over = 0;

    SEG7 = 0;
    LED = 0;
    RGB_LED = 0x00FF00; // Status: Active Green

    // 2. Draw Walls & Borders First (Screen appears instantly on VGA)
    for (int x = 0; x < GRID_W; x++) {
        vga_draw_pixel(x, 0, COLOR_WALL);
        vga_draw_pixel(x, GRID_H - 1, COLOR_WALL);
    }
    for (int y = 0; y < GRID_H; y++) {
        vga_draw_pixel(0, y, COLOR_WALL);
        vga_draw_pixel(GRID_W - 1, y, COLOR_WALL);
    }

    // 3. Draw Snake & Food
    for (int i = 1; i < snake_len; i++) {
        vga_draw_pixel(snake_x[i], snake_y[i], COLOR_BODY);
    }
    vga_draw_pixel(snake_x[0], snake_y[0], COLOR_HEAD);
    vga_draw_pixel(food_x, food_y, COLOR_FOOD);

    uart_print("> Snake Ready!\r\n");

    // 4. Main Game Loop
    while (!game_over) {
        // Read Button Inputs (Sample input multiple times for responsive controls)
        for (int delay = 0; delay < 20; delay++) {
            unsigned int btn = BTN;
            if (btn != last_btn) {
                last_btn = btn;
                if ((btn & BTN_UP) && dir_y != 1) {
                    dir_x = 0; dir_y = -1;
                } else if ((btn & BTN_DOWN) && dir_y != -1) {
                    dir_x = 0; dir_y = 1;
                } else if ((btn & BTN_LEFT) && dir_x != 1) {
                    dir_x = -1; dir_y = 0;
                } else if ((btn & BTN_RIGHT) && dir_x != -1) {
                    dir_x = 1; dir_y = 0;
                } else if (btn & BTN_CENTER) {
                    goto restart;
                }
            }
        }

        // Compute Next Head Position
        int next_x = snake_x[0] + dir_x;
        int next_y = snake_y[0] + dir_y;

        // Collision Check: Border Walls
        if (next_x <= 0 || next_x >= GRID_W - 1 || next_y <= 0 || next_y >= GRID_H - 1) {
            game_over = 1;
            break;
        }

        // Collision Check: Self-Bite
        for (int i = 1; i < snake_len; i++) {
            if (snake_x[i] == next_x && snake_y[i] == next_y) {
                game_over = 1;
                break;
            }
        }
        if (game_over) break;

        // Check Food Consumption
        int ate_food = (next_x == food_x && next_y == food_y);
        if (ate_food) {
            score++;
            SEG7 = score;
            LED = (1 << (score > 16 ? 16 : score)) - 1;

            if (snake_len < MAX_SNAKE_LEN - 1) {
                snake_len++;
            }

            // Reposition Food
            food_x = 4 + ((food_x * 7 + score * 13) % (GRID_W - 8));
            food_y = 4 + ((food_y * 11 + score * 17) % (GRID_H - 8));
            vga_draw_pixel(food_x, food_y, COLOR_FOOD);

            uart_print("> [FOOD EATEN] Score: ");
            uart_putchar('0' + (score % 10));
            uart_print("\r\n");
        } else {
            // Erase Old Tail
            vga_draw_pixel(snake_x[snake_len - 1], snake_y[snake_len - 1], COLOR_BG);
        }

        // Move Body Segments
        for (int i = snake_len - 1; i > 0; i--) {
            snake_x[i] = snake_x[i - 1];
            snake_y[i] = snake_y[i - 1];
        }
        snake_x[0] = next_x;
        snake_y[0] = next_y;

        // Draw New Head and update previous head to body
        vga_draw_pixel(snake_x[0], snake_y[0], COLOR_HEAD);
        if (snake_len > 1) {
            vga_draw_pixel(snake_x[1], snake_y[1], COLOR_BODY);
        }
    }

    // Game Over Sequence
    RGB_LED = 0xFF0000; // Red Game Over Light
    uart_print("\r\n>>> GAME OVER! Press BTNC (Center) to Restart <<<\r\n");

    // Wait for BTNC to restart
    while (1) {
        if (BTN & BTN_CENTER) {
            goto restart;
        }
    }
}
