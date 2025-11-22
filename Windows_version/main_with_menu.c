/*
 * Golf Game with Menu - Pure Raylib/C
 * Fast, clean, no Python dependencies
 * 
 * Compile: gcc main_with_menu.c -o golf_menu -lraylib -lm -lpthread -ldl
 */

#include "raylib.h"
#include <math.h>
#include <stdio.h>
#include <stdbool.h>
#include <stdlib.h>
#include <time.h>

// Physics constants (same as main.c)
#define GRAVITY_ACCEL 800.0f
#define DT 0.016f
#define MAP_SIZE 32
#define TILE_SIZE 20
#define LAUNCH_SCALE 4.0f
#define Z_SCALE 0.6f
#define AIR_DRAG_COEF 1.6f
#define MAX_DRAG_DISTANCE 150.0f
#define STOP_SPEED 2.0f
#define MAX_WIND_STRENGTH 50.0f
#define WIND_SMOOTHNESS 0.25f
#define GROUND_WIND_FACTOR 0.08f
#define MAGNUS_COEF 0.0012f
#define MAGNUS_MAX 10.0f
#define SPIN_AIR_DAMP 0.996f
#define SPIN_GROUND_DAMP 0.985f
#define LOW_SPEED_KILL 4.5f
#define SCREEN_WIDTH (MAP_SIZE * TILE_SIZE)
#define SCREEN_HEIGHT (MAP_SIZE * TILE_SIZE)


// Game screens
typedef enum {
    SCREEN_MENU = 0,
    SCREEN_MANUAL,
    SCREEN_AI_DEMO,
    SCREEN_VS_MODE
} GameScreen;

// Turn type for VS mode
typedef enum {
    TURN_PLAYER = 0,
    TURN_AI,
    TURN_FINISHED
} TurnType;

// All the structs from main.c
typedef struct {
    float rollDamping;
    float bounceFactor;
    float launchFactor;
    bool isHazard;
    bool isSolid;
    bool isSand;
} TerrainProps;

typedef struct {
    float dirX, dirY;
    float targetStrength;
    float appliedStrength;
    float timer;
} Wind;

typedef struct {
    float x, y, z;
    float vx, vy, vz;
    float spinX, spinY, spinZ;
    float radius;
    bool inAir;
    bool isMoving;
    float lastX, lastY;
    float angle;
    bool userSetSpin;
} Ball;

typedef struct {
    Ball ball;
    Ball aiBall;  // Separate ball for AI in VS mode
    Wind wind;
    Image mapImage;
    Texture2D mapTexture;
    Vector2 dragStart;
    bool isDragging;
    int strokes;
    bool gameWon;
    bool aiWon;  // Track if AI finished
    Vector2 holePos;
} GameState;

// Utility functions
static int clampInt(int v, int a, int b) {
    return (v < a) ? a : (v > b) ? b : v;
}

static float clampf(float v, float a, float b) {
    return (v < a) ? a : (v > b) ? b : v;
}
float LerpFloat(float a, float b, float t) {
    return a + (b - a) * t;
}

// Copy all physics functions from main.c
TerrainProps getTerrainProps(Color c) {
    TerrainProps p = {0.96f, 0.60f, 1.0f, false, false, false};
    int R = c.r, G = c.g, B = c.b;
    
    if (R < 30 && G < 30 && B < 30) return p;
    if (R > 150 && R > G + 40 && R > B + 40) return p;
    
    if (B > 120 && B > G + 20 && B > R + 20) {
        p.rollDamping = 0.92f; p.bounceFactor = 0.0f; p.launchFactor = 0.0f; p.isHazard = true;
        return p;
    }
    
    if ((R < 70 && G < 80 && B < 70) && (G <= R + 20)) {
        p.rollDamping = 0.40f; p.bounceFactor = 0.0f; p.launchFactor = 0.40f; p.isSolid = true;
        return p;
    }
    
    if (R > 130 && G > 130 && B < 100 && abs(R - G) < 30 && (R + G) > 260 && G < 200) {
        p.rollDamping = 0.45f; p.bounceFactor = 0.05f; p.launchFactor = 0.35f; p.isSand = true;
        return p;
    }
    
    if (G > 200 && R > 80 && B < 150 && G > R && G > B) {
        p.rollDamping = 0.98f; p.bounceFactor = 0.75f; p.launchFactor = 1.05f;
        return p;
    }
    
    if (G >= 85 && G <= 170 && G > R + 8 && G > B + 8 && R <= 120 && B <= 120) {
        p.rollDamping = 0.80f; p.bounceFactor = 0.55f; p.launchFactor = 0.85f;
        return p;
    }
    
    return p;
}

TerrainProps getTerrainAt(Image *map, float x, float y) {
    int imgW = map->width, imgH = map->height;
    x = clampf(x, 0, SCREEN_WIDTH - 1);
    y = clampf(y, 0, SCREEN_HEIGHT - 1);
    int px = clampInt((int)((x / SCREEN_WIDTH) * imgW), 0, imgW - 1);
    int py = clampInt((int)((y / SCREEN_HEIGHT) * imgH), 0, imgH - 1);
    return getTerrainProps(GetImageColor(*map, px, py));
}

void updateWind(Wind *w, float dt) {
    w->timer -= dt;
    if (w->timer <= 0.0f) {
        float angle = ((float)rand() / RAND_MAX) * 2.0f * PI;
        w->dirX = cosf(angle);
        w->dirY = sinf(angle);
        w->targetStrength = ((float)rand() / RAND_MAX) * MAX_WIND_STRENGTH;
        w->timer = 3.0f + ((float)rand() / RAND_MAX) * 3.0f;
    }
    w->appliedStrength += (w->targetStrength - w->appliedStrength) * WIND_SMOOTHNESS;
}

Vector2 findHolePosition(Image *map) {
    for (int y = 0; y < map->height; y++) {
        for (int x = 0; x < map->width; x++) {
            Color c = GetImageColor(*map, x, y);
            if (c.r < 30 && c.g < 30 && c.b < 30)
                return (Vector2){ x * TILE_SIZE + TILE_SIZE*0.5f, y * TILE_SIZE + TILE_SIZE*0.5f };
        }
    }
    return (Vector2){ -1, -1 };
}

Vector2 findStartPosition(Image *map) {
    for (int y = 0; y < map->height; y++) {
        for (int x = 0; x < map->width; x++) {
            Color c = GetImageColor(*map, x, y);
            if (c.r > 150 && c.r > c.g + 40 && c.r > c.b + 40)
                return (Vector2){ x * TILE_SIZE + TILE_SIZE*0.5f, y * TILE_SIZE + TILE_SIZE*0.5f };
        }
    }
    return (Vector2){ SCREEN_WIDTH*0.5f, SCREEN_HEIGHT*0.5f };
}

void initBall(Ball *ball, Vector2 startPos) {
    ball->x = startPos.x; ball->y = startPos.y; ball->z = 0.0f;
    ball->vx = ball->vy = ball->vz = 0.0f;
    ball->spinX = ball->spinY = ball->spinZ = 0.0f;
    ball->radius = 6.0f;
    ball->inAir = false; ball->isMoving = false;
    ball->lastX = startPos.x; ball->lastY = startPos.y;
    ball->angle = 45.0f;
    ball->userSetSpin = false;
}

void shootBall(Ball *ball, Image *map, float dirx, float diry, float power, float angleDeg) {
    float len = sqrtf(dirx*dirx + diry*diry);
    if (len < 1e-6f) { dirx = 0.0f; diry = -1.0f; len = 1.0f; }
    dirx /= len; diry /= len;
    
    TerrainProps terrain = getTerrainAt(map, ball->x, ball->y);
    float angleRad = angleDeg * (PI / 180.0f);
    float baseLaunch = power * LAUNCH_SCALE * terrain.launchFactor;
    
    if (terrain.isSand) baseLaunch *= 0.45f;
    
    float horizontalSpeed = baseLaunch * cosf(angleRad);
    ball->vx = horizontalSpeed * dirx;
    ball->vy = horizontalSpeed * diry;
    ball->vz = baseLaunch * sinf(angleRad) * Z_SCALE;
    
    if (!ball->userSetSpin) {
        ball->spinY = baseLaunch * 0.02f;
        ball->spinX = -dirx * baseLaunch * 0.01f;
    } else {
        ball->spinY += baseLaunch * 0.005f;
        ball->spinX += -dirx * baseLaunch * 0.0025f;
    }
    
    ball->spinX = clampf(ball->spinX, -baseLaunch * 0.08f, baseLaunch * 0.08f);
    ball->spinY = clampf(ball->spinY, -baseLaunch * 0.25f, baseLaunch * 0.25f);
    
    ball->inAir = (ball->vz > 1.0f);
    ball->isMoving = true;
    
    if (ball->z <= 0.0f) {
        ball->lastX = ball->x;
        ball->lastY = ball->y;
    }
    
    ball->userSetSpin = false;
}

void updateBall(Ball *ball, Image *map, Wind wind, float dt) {
    if (!ball->isMoving) return;
    
    bool bouncedThisFrame = false;
    ball->vz -= GRAVITY_ACCEL * dt;
    ball->x += ball->vx * dt;
    ball->y += ball->vy * dt;
    ball->z += ball->vz * dt;
    
    bool airborne = (ball->z > 1.0f) || ball->inAir;
    
    if (airborne) {
        ball->vx += wind.dirX * wind.appliedStrength * dt;
        ball->vy += wind.dirY * wind.appliedStrength * dt;
    } else {
        ball->vx += wind.dirX * wind.appliedStrength * dt * GROUND_WIND_FACTOR;
        ball->vy += wind.dirY * wind.appliedStrength * dt * GROUND_WIND_FACTOR;
    }
    
    if (airborne) {
        float magnusX = clampf(-ball->spinY * ball->vy * MAGNUS_COEF, -MAGNUS_MAX, MAGNUS_MAX);
        float magnusY = clampf(ball->spinY * ball->vx * MAGNUS_COEF, -MAGNUS_MAX, MAGNUS_MAX);
        ball->vx += magnusX;
        ball->vy += magnusY;
    }
    
    if (airborne) {
        ball->spinX *= SPIN_AIR_DAMP;
        ball->spinY *= SPIN_AIR_DAMP;
        ball->spinZ *= SPIN_AIR_DAMP;
    } else {
        ball->spinX *= SPIN_GROUND_DAMP;
        ball->spinY *= SPIN_GROUND_DAMP;
        ball->spinZ *= SPIN_GROUND_DAMP;
    }
    
    TerrainProps terrain = getTerrainAt(map, ball->x, ball->y);
    
    if (ball->z <= 0.0f) {
        ball->z = 0.0f;
        if (fabsf(ball->vz) < 6.0f) {
            ball->vz = 0.0f;
            ball->inAir = false;
        }
        
        if (terrain.isHazard) {
            ball->x = ball->lastX; ball->y = ball->lastY;
            ball->vx = ball->vy = ball->vz = 0.0f;
            ball->inAir = false; ball->isMoving = false;
            return;
        }
        
        if (terrain.isSand) {
            float speed = sqrtf(ball->vx*ball->vx + ball->vy*ball->vy);
            if (speed < 40.0f) {
                ball->vx = ball->vy = ball->vz = 0.0f;
                ball->inAir = false; ball->isMoving = false;
            } else {
                ball->vx *= 0.06f; ball->vy *= 0.06f; ball->vz = 0.0f; ball->inAir = false;
            }
            ball->lastX = ball->x; ball->lastY = ball->y;
        }
        else if (terrain.isSolid) {
            ball->x = ball->lastX; ball->y = ball->lastY;
            ball->vx *= -0.25f; ball->vy *= -0.25f; ball->vz = 0.0f; ball->inAir = false;
        }
        else {
            ball->vx *= terrain.rollDamping;
            ball->vy *= terrain.rollDamping;
            
            if (terrain.bounceFactor > 0.01f && ball->vz < -10.0f) {
                ball->vz = -ball->vz * terrain.bounceFactor;
                ball->inAir = (ball->vz > 4.0f);
                bouncedThisFrame = true;
            } else {
                ball->vz = 0.0f;
                ball->inAir = false;
            }
            
            if (!ball->inAir) { ball->lastX = ball->x; ball->lastY = ball->y; }
        }
    }
    
    if (airborne && !bouncedThisFrame) {
        ball->vx -= ball->vx * AIR_DRAG_COEF * dt;
        ball->vy -= ball->vy * AIR_DRAG_COEF * dt;
    }
    
    if (ball->z <= 0.0f && !ball->inAir && (fabsf(ball->vx) > 0.0f || fabsf(ball->vy) > 0.0f)) {
        TerrainProps t2 = getTerrainAt(map, ball->x, ball->y);
        ball->vx *= t2.rollDamping;
        ball->vy *= t2.rollDamping;
    }
    
    ball->x = clampf(ball->x, 0, SCREEN_WIDTH - 1);
    ball->y = clampf(ball->y, 0, SCREEN_HEIGHT - 1);
    
    float speed = sqrtf(ball->vx*ball->vx + ball->vy*ball->vy);
    if (speed < STOP_SPEED && ball->z <= 0.05f && fabsf(ball->vz) < 0.2f) {
        ball->vx = ball->vy = ball->vz = 0.0f;
        ball->inAir = false; ball->isMoving = false;
    } else if (speed < LOW_SPEED_KILL && ball->z <= 0.05f && !ball->inAir) {
        ball->vx = ball->vy = 0.0f;
        ball->isMoving = false;
    }
}

void drawBall(const Ball *ball) {
    float heightFactor = 1.0f + (ball->z / 10.0f);
    float size = ball->radius * heightFactor;
    float shadowAlpha = fmaxf(0.12f, 1.0f / (1.0f + ball->z / 30.0f));
    DrawCircleV((Vector2){ ball->x, ball->y }, ball->radius * 0.9f, Fade(BLACK, shadowAlpha));
    DrawCircleV((Vector2){ ball->x, ball->y - ball->z * 0.9f }, size, WHITE);
    DrawCircleLines((int)ball->x, (int)(ball->y - ball->z * 0.9f), (int)size, BLACK);
}

bool isNearHole(float x, float y, Vector2 holePos) {
    if (holePos.x < 0) return false;
    float dx = x - holePos.x, dy = y - holePos.y;
    return sqrtf(dx*dx + dy*dy) < 15.0f;
}
 

// Menu drawing
void DrawMenuButton(Rectangle r, const char *txt, bool quit, Vector2 mouse) {
    bool hover = CheckCollisionPointRec(mouse, r);

    float scale = hover ? 1.05f : 1.0f;

    Rectangle scaled = {
        r.x - (r.width * scale - r.width) / 2,
        r.y - (r.height * scale - r.height) / 2,
        r.width * scale,
        r.height * scale
    };

    Color base = quit 
        ? (Color){200, 100, 100, 255}
        : (Color){100, 200, 100, 255};

    Color hoverCol = quit
        ? (Color){250, 150, 150, 255}
        : (Color){150, 250, 150, 255};

    DrawRectangleRec(scaled, hover ? hoverCol : base);
    DrawRectangleLinesEx(scaled, 3, BLACK);

    int textX = scaled.x + scaled.width/2 - MeasureText(txt, 22)/2;
    int textY = scaled.y + scaled.height/2 - 22/2 - (hover ? 2 : 0);

    DrawText(txt, textX, textY, 22, BLACK);
}
void DrawMenuScreen(void) {

    // --- 0. Background pulse (wind-like) ---
    float t = (sinf(GetTime() * 0.6f) + 1)/2; // 0→1 smooth pulse
    Color bg = {
    (unsigned char)LerpFloat(100, 120, t),
    (unsigned char)LerpFloat(200, 220, t),
    (unsigned char)LerpFloat(100, 120, t),
    255
    };

    ClearBackground(bg);

    // --- 1. Drop shadow title ---
    const char *title = "PROJECT GOLFERO";
    int titleX = SCREEN_WIDTH/2 - MeasureText(title, 50)/2;
    int titleY = 60;

    DrawText(title, titleX + 2, titleY + 2, 50, (Color){40, 40, 40, 255});
    DrawText(title, titleX,     titleY,     50, WHITE);

    // --- 2. Floating golf ball ---
    int bob = sin(GetTime() * 2.0f) * 4;
    DrawCircle(titleX + MeasureText(title, 50) + 35, titleY + 25 + bob, 14, WHITE);
    DrawCircle(titleX + MeasureText(title, 50) + 35 + 4, titleY + 25 + bob - 4, 4, LIGHTGRAY);

    // --- 3. Buttons ---
    Vector2 mouse = GetMousePosition();

    DrawMenuButton((Rectangle){200, 200, 240, 50}, "Manual Only", false, mouse);
    DrawMenuButton((Rectangle){200, 270, 240, 50}, "AI Demo", false, mouse);
    DrawMenuButton((Rectangle){200, 340, 240, 50}, "Manual vs AI", false, mouse);
    DrawMenuButton((Rectangle){200, 410, 240, 50}, "Quit", true, mouse);

    // --- 4. Info text ---
    DrawText("Manual: Play solo", SCREEN_WIDTH/2 - 80, 490, 16, BLACK);
    DrawText("AI Demo: Watch AI play", SCREEN_WIDTH/2 - 100, 510, 16, BLACK);
    DrawText("Manual vs AI: Take turns with AI", SCREEN_WIDTH/2 - 130, 530, 16, BLACK);
    DrawText("Press ESC to return to menu", SCREEN_WIDTH/2 - 120, 570, 14, DARKGRAY);
}


int CheckMenuClick(void) {
    if (!IsMouseButtonPressed(MOUSE_LEFT_BUTTON)) return -1;
    Vector2 mouse = GetMousePosition();
    
    Rectangle btn1 = {200, 200, 240, 50};
    Rectangle btn2 = {200, 270, 240, 50};
    Rectangle btn3 = {200, 340, 240, 50};
    Rectangle btn4 = {200, 410, 240, 50};
    
    if (CheckCollisionPointRec(mouse, btn1)) return 1; // Manual
    if (CheckCollisionPointRec(mouse, btn2)) return 2; // AI Demo
    if (CheckCollisionPointRec(mouse, btn3)) return 3; // Manual vs AI
    if (CheckCollisionPointRec(mouse, btn4)) return 4; // Quit
    
    return -1;
}

// AI Communication via named pipe
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <pthread.h>

#define AI_PIPE_NAME "/tmp/golf_ai_pipe"
#define STATE_PIPE_NAME "/tmp/golf_state_pipe"

bool ai_connecting = false;
bool ai_connected = false;
pthread_t ai_thread;

typedef struct {
    float dirx, diry, angle, power, spinx, spiny;
} AICommand;

typedef struct {
    float ball_x, ball_y, ball_z;
    float hole_x, hole_y;
    float wind_x, wind_y, wind_strength;
    int strokes;
    bool stopped;
    bool won;
} GameStateMsg;

int ai_pipe_fd = -1;
int state_pipe_fd = -1;

void* connectAIPipes(void* arg) {
    printf("AI pipes created. Waiting for Python AI to connect...\n");
    printf("(Start Python AI now: python3 ai_golfer/ai_pipe_client.py)\n");
    
    // Open for reading (blocks until Python opens for writing)
    ai_pipe_fd = open(AI_PIPE_NAME, O_RDONLY);
    printf("AI command pipe connected!\n");
    
    // Open for writing (blocks until Python opens for reading)  
    state_pipe_fd = open(STATE_PIPE_NAME, O_WRONLY);
    printf("State pipe connected!\n");
    
    // Now set both to non-blocking for game loop
    fcntl(ai_pipe_fd, F_SETFL, O_NONBLOCK);
    fcntl(state_pipe_fd, F_SETFL, O_NONBLOCK);
    
    ai_connected = true;
    ai_connecting = false;
    printf("✓ AI fully connected and ready!\n");
    
    return NULL;
}

void setupAIPipes(void) {
    // Create named pipes (ignore error if already exists)
    mkfifo(AI_PIPE_NAME, 0666);
    mkfifo(STATE_PIPE_NAME, 0666);
    
    // Start connection in background thread
    ai_connecting = true;
    pthread_create(&ai_thread, NULL, connectAIPipes, NULL);
}

void sendGameStateWithWon(GameState *game, bool won) {
    if (state_pipe_fd < 0) {
        printf("State pipe not open!\n");
        return;
    }
    
    GameStateMsg msg = {
        .ball_x = game->ball.x,
        .ball_y = game->ball.y,
        .ball_z = game->ball.z,
        .hole_x = game->holePos.x,
        .hole_y = game->holePos.y,
        .wind_x = game->wind.dirX,
        .wind_y = game->wind.dirY,
        .wind_strength = game->wind.appliedStrength,
        .strokes = game->strokes,
        .stopped = !game->ball.isMoving,
        .won = won
    };
    
    ssize_t written = write(state_pipe_fd, &msg, sizeof(GameStateMsg));
    if (written < 0) {
        printf("Failed to send state: %ld\n", (long)written);
    }
}

void sendGameState(GameState *game) {
    sendGameStateWithWon(game, game->gameWon);
}

bool readAICommand(AICommand *cmd) {
    if (ai_pipe_fd < 0) return false;
    
    ssize_t bytes = read(ai_pipe_fd, cmd, sizeof(AICommand));
    return bytes == sizeof(AICommand);
}

void cleanupAIPipes(void) {
    if (ai_pipe_fd >= 0) close(ai_pipe_fd);
    if (state_pipe_fd >= 0) close(state_pipe_fd);
    unlink(AI_PIPE_NAME);
    unlink(STATE_PIPE_NAME);
}

// Main function
int main(void) {
    srand((unsigned)time(NULL));
    InitWindow(SCREEN_WIDTH, SCREEN_HEIGHT, "Golf Game");
    SetTargetFPS(60);
    
    GameScreen currentScreen = SCREEN_MENU;
    GameState game = {0};
    bool gameInitialized = false;
    Vector2 startPos = {0};
    float aiThinkTimer = 0.0f;
    TurnType currentTurn = TURN_PLAYER;
    int playerStrokes = 0;
    int aiStrokes = 0;
    
    while (!WindowShouldClose()) {
        // Menu screen
        if (currentScreen == SCREEN_MENU) {
            int choice = CheckMenuClick();
            if (choice == 1) {
                currentScreen = SCREEN_MANUAL;
            } else if (choice == 2) {
                currentScreen = SCREEN_AI_DEMO;
            } else if (choice == 3) {
                currentScreen = SCREEN_VS_MODE;
            } else if (choice == 4) {
                break;
            }
            
            BeginDrawing();
            DrawMenuScreen();
            EndDrawing();
            continue;
        }
        
        // Initialize game on first entry
        if (!gameInitialized) {
            // Setup AI pipes if in AI mode or VS mode
            if (currentScreen == SCREEN_AI_DEMO || currentScreen == SCREEN_VS_MODE) {
                setupAIPipes();
            }
            
            game.mapImage = LoadImage("golf_map.png");
            if (game.mapImage.data == NULL) {
                game.mapImage = GenImageColor(MAP_SIZE, MAP_SIZE, (Color){100, 200, 100, 255});
                ImageDrawCircle(&game.mapImage, 5, 25, 2, RED);
                ImageDrawCircle(&game.mapImage, 25, 5, 2, BLACK);
                ImageDrawRectangle(&game.mapImage, 10, 10, 8, 8, BLUE);
                ImageDrawRectangle(&game.mapImage, 15, 20, 5, 5, (Color){180,120,60,255});
                ImageDrawRectangle(&game.mapImage, 7, 7, 6, 6, (Color){75,105,47,255});
                ImageDrawRectangle(&game.mapImage, 20, 12, 5, 6, (Color){80,140,60,255});
            }
            
            game.mapTexture = LoadTextureFromImage(game.mapImage);
            startPos = findStartPosition(&game.mapImage);
            game.holePos = findHolePosition(&game.mapImage);
            initBall(&game.ball, startPos);
            
            // In VS mode, initialize AI ball at same start position
            if (currentScreen == SCREEN_VS_MODE) {
                initBall(&game.aiBall, startPos);
            }
            
            game.strokes = 0;
            game.isDragging = false;
            game.gameWon = false;
            game.aiWon = false;
            game.wind.dirX = 1.0f;
            game.wind.dirY = 0.0f;
            game.wind.targetStrength = 0.0f;
            game.wind.appliedStrength = 0.0f;
            game.wind.timer = 4.0f;
            
            gameInitialized = true;
        }
        
        // Back to menu
        if (IsKeyPressed(KEY_ESCAPE)) {
            currentScreen = SCREEN_MENU;
            gameInitialized = false;
            UnloadTexture(game.mapTexture);
            UnloadImage(game.mapImage);
            continue;
        }
        
        Vector2 mousePos = GetMousePosition();
        
        // Manual mode input (and VS mode when it's player's turn)
        bool allowManualInput = (currentScreen == SCREEN_MANUAL) || 
                                (currentScreen == SCREEN_VS_MODE && currentTurn == TURN_PLAYER);
        
        if (allowManualInput && !game.ball.isMoving && !game.gameWon) {
            if (IsKeyDown(KEY_UP)) game.ball.angle = fminf(75.0f, game.ball.angle + 0.8f);
            if (IsKeyDown(KEY_DOWN)) game.ball.angle = fmaxf(0.0f, game.ball.angle - 0.8f);
            
            if (IsKeyPressed(KEY_A)) { game.ball.spinX -= 1.0f; game.ball.userSetSpin = true; }
            if (IsKeyPressed(KEY_D)) { game.ball.spinX += 1.0f; game.ball.userSetSpin = true; }
            if (IsKeyPressed(KEY_W)) { game.ball.spinY += 1.0f; game.ball.userSetSpin = true; }
            if (IsKeyPressed(KEY_S)) { game.ball.spinY -= 1.0f; game.ball.userSetSpin = true; }
            
            if (IsMouseButtonPressed(MOUSE_LEFT_BUTTON)) {
                game.dragStart = mousePos;
                game.isDragging = true;
            }
            
            if (game.isDragging && IsMouseButtonReleased(MOUSE_LEFT_BUTTON)) {
                game.isDragging = false;
                float dx = game.dragStart.x - mousePos.x;
                float dy = game.dragStart.y - mousePos.y;
                float rawPower = sqrtf(dx*dx + dy*dy);
                if (rawPower > MAX_DRAG_DISTANCE) rawPower = MAX_DRAG_DISTANCE;
                
                if (rawPower > 5.0f) {
                    float mag = sqrtf(dx*dx + dy*dy) + 1e-6f;
                    shootBall(&game.ball, &game.mapImage, dx/mag, dy/mag, rawPower, game.ball.angle);
                    game.strokes++;
                    
                    // In VS mode, track player strokes and switch turn
                    if (currentScreen == SCREEN_VS_MODE) {
                        playerStrokes++;
                        currentTurn = TURN_AI;
                    }
                }
            }
        }
        
        // AI mode - listen for Python AI commands
        if (currentScreen == SCREEN_AI_DEMO) {
            // Only send state if AI is connected
            if (ai_connected && !game.ball.isMoving) {
                static int send_counter = 0;
                if (send_counter++ % 60 == 0) {  // Send once per second
                    sendGameState(&game);
                }
            }
            
            // Check for AI command
            if (ai_connected && !game.ball.isMoving && !game.gameWon) {
                AICommand cmd;
                if (readAICommand(&cmd)) {
                    printf("AI Shot %d: dir=(%.3f,%.3f) angle=%.1f power=%.1f\n", 
                           game.strokes + 1, cmd.dirx, cmd.diry, cmd.angle, cmd.power);
                    
                    shootBall(&game.ball, &game.mapImage, cmd.dirx, cmd.diry, cmd.power, cmd.angle);
                    game.strokes++;
                }
            }
            
            // Show connection status
            if (ai_connecting) {
                DrawText("Waiting for Python AI to connect...", 10, SCREEN_HEIGHT - 90, 16, YELLOW);
                DrawText("Run: python3 ai_golfer/ai_pipe_client.py", 10, SCREEN_HEIGHT - 70, 14, LIGHTGRAY);
            } else if (!ai_connected) {
                DrawText("AI not connected", 10, SCREEN_HEIGHT - 90, 16, RED);
            }
        }
        
        // VS Mode - separate balls for player and AI
        if (currentScreen == SCREEN_VS_MODE) {
            // Check if player ball reached hole
            if (!game.ball.isMoving && !game.gameWon && isNearHole(game.ball.x, game.ball.y, game.holePos)) {
                game.gameWon = true;
                printf("Player finished in %d strokes!\n", playerStrokes);
                // Immediately switch to AI if it hasn't finished
                if (!game.aiWon) {
                    currentTurn = TURN_AI;
                    printf("Switching to AI to finish...\n");
                }
            }
            
            // Check if AI ball reached hole
            if (!game.aiBall.isMoving && !game.aiWon && isNearHole(game.aiBall.x, game.aiBall.y, game.holePos)) {
                game.aiWon = true;
                printf("AI finished in %d strokes!\n", aiStrokes);
            }
            
            // Send AI ball state to Python AI
            if (ai_connected && !game.aiBall.isMoving && !game.aiWon) {
                static int send_counter = 0;
                if (send_counter++ % 60 == 0) {
                    // Temporarily swap balls to send AI ball state
                    Ball temp = game.ball;
                    game.ball = game.aiBall;
                    // In VS mode, always send won=false so Python AI doesn't exit
                    sendGameStateWithWon(&game, false);
                    game.ball = temp;
                }
            }
            
            // AI's turn - shoot AI ball
            if (currentTurn == TURN_AI && ai_connected && !game.aiBall.isMoving && !game.aiWon) {
                AICommand cmd;
                if (readAICommand(&cmd)) {
                    printf("AI Shot %d: dir=(%.3f,%.3f) angle=%.1f power=%.1f\n", 
                           aiStrokes + 1, cmd.dirx, cmd.diry, cmd.angle, cmd.power);
                    
                    shootBall(&game.aiBall, &game.mapImage, cmd.dirx, cmd.diry, cmd.power, cmd.angle);
                    aiStrokes++;
                    
                    // Switch turn: if player finished, DON'T switch (stay AI); otherwise switch to player
                    if (!game.gameWon) {
                        currentTurn = TURN_PLAYER;
                    }
                    // If player finished, turn stays TURN_AI so AI continues
                }
            }
            
            // If AI finished but player hasn't, switch to player turn
            if (currentTurn == TURN_AI && game.aiWon && !game.gameWon && !game.aiBall.isMoving) {
                currentTurn = TURN_PLAYER;
                printf("AI finished! Player continues playing...\n");
            }
            
            // If player finished but AI hasn't, force switch to AI turn
            if (currentTurn == TURN_PLAYER && game.gameWon && !game.aiWon && !game.ball.isMoving) {
                currentTurn = TURN_AI;
                printf("Player finished! AI continues playing...\n");
            }
            
            // Show turn indicator
            if (!game.gameWon && !game.aiWon) {
                if (currentTurn == TURN_PLAYER) {
                    DrawText("YOUR TURN", SCREEN_WIDTH/2 - 60, 10, 24, GREEN);
                } else {
                    DrawText("AI TURN", SCREEN_WIDTH/2 - 50, 10, 24, YELLOW);
                }
            }
            
            // Show scores
            char scoreText[64];
            sprintf(scoreText, "You: %d | AI: %d", playerStrokes, aiStrokes);
            DrawText(scoreText, SCREEN_WIDTH/2 - 60, 40, 20, WHITE);
            
            // Show final result if both finished
            if (game.gameWon && game.aiWon) {
                DrawRectangle(SCREEN_WIDTH/2 - 150, SCREEN_HEIGHT/2 - 80, 300, 160, (Color){0, 0, 0, 200});
                DrawText("GAME OVER!", SCREEN_WIDTH/2 - 80, SCREEN_HEIGHT/2 - 60, 28, WHITE);
                
                char result[128];
                if (playerStrokes < aiStrokes) {
                    sprintf(result, "YOU WIN! %d vs %d", playerStrokes, aiStrokes);
                    DrawText(result, SCREEN_WIDTH/2 - 100, SCREEN_HEIGHT/2 - 20, 20, GREEN);
                } else if (aiStrokes < playerStrokes) {
                    sprintf(result, "AI WINS! %d vs %d", aiStrokes, playerStrokes);
                    DrawText(result, SCREEN_WIDTH/2 - 100, SCREEN_HEIGHT/2 - 20, 20, RED);
                } else {
                    sprintf(result, "TIE! Both: %d strokes", playerStrokes);
                    DrawText(result, SCREEN_WIDTH/2 - 100, SCREEN_HEIGHT/2 - 20, 20, YELLOW);
                }
                
                DrawText("Press R to restart", SCREEN_WIDTH/2 - 80, SCREEN_HEIGHT/2 + 20, 18, LIGHTGRAY);
                DrawText("Press ESC for menu", SCREEN_WIDTH/2 - 85, SCREEN_HEIGHT/2 + 45, 18, LIGHTGRAY);
            }
            
            // Show connection status
            if (ai_connecting) {
                DrawText("Waiting for AI...", 10, SCREEN_HEIGHT - 70, 16, YELLOW);
            } else if (!ai_connected) {
                DrawText("AI not connected!", 10, SCREEN_HEIGHT - 70, 16, RED);
            }
        }
        
        if (IsKeyPressed(KEY_R)) {
            initBall(&game.ball, startPos);
            game.strokes = 0;
            game.gameWon = false;
            
            // In VS mode, also reset AI ball and scores
            if (currentScreen == SCREEN_VS_MODE) {
                initBall(&game.aiBall, startPos);
                game.aiWon = false;
                playerStrokes = 0;
                aiStrokes = 0;
                currentTurn = TURN_PLAYER;
            }
        }
        
        updateWind(&game.wind, DT);
        updateBall(&game.ball, &game.mapImage, game.wind, DT);
        
        // In VS mode, also update AI ball
        if (currentScreen == SCREEN_VS_MODE) {
            updateBall(&game.aiBall, &game.mapImage, game.wind, DT);
        }
        
        // Check win condition (handled in VS mode section for VS, here for other modes)
        if (currentScreen != SCREEN_VS_MODE) {
            if (!game.ball.isMoving && isNearHole(game.ball.x, game.ball.y, game.holePos)) {
                game.gameWon = true;
            }
        }
        
        // Draw
        BeginDrawing();
        ClearBackground((Color){30,30,30,255});
        
        DrawTexturePro(game.mapTexture,
                       (Rectangle){ 0, 0, (float)game.mapImage.width, (float)game.mapImage.height },
                       (Rectangle){ 0, 0, (float)SCREEN_WIDTH, (float)SCREEN_HEIGHT },
                       (Vector2){ 0,0 }, 0.0f, WHITE);
        
        if (!game.ball.isMoving && !game.gameWon) {
            float maxLen = 40.0f, minLen = 10.0f;
            float indicatorLen = maxLen - (game.ball.angle / 75.0f) * (maxLen - minLen);
            DrawLineEx((Vector2){game.ball.x, game.ball.y}, 
                      (Vector2){game.ball.x, game.ball.y - indicatorLen}, 3.0f, ORANGE);
            DrawCircleV((Vector2){game.ball.x, game.ball.y - indicatorLen}, 4.0f, ORANGE);
        }
        
        if (game.isDragging) {
            float dx = game.dragStart.x - mousePos.x;
            float dy = game.dragStart.y - mousePos.y;
            float power = sqrtf(dx*dx + dy*dy);
            if (power > MAX_DRAG_DISTANCE) power = MAX_DRAG_DISTANCE;
            float aimEndX = game.ball.x + dx + game.wind.dirX * game.wind.appliedStrength * 0.3f;
            float aimEndY = game.ball.y + dy + game.wind.dirY * game.wind.appliedStrength * 0.3f;
            Color col = (sqrtf(dx*dx + dy*dy) > MAX_DRAG_DISTANCE) ? RED : YELLOW;
            DrawLineEx((Vector2){game.ball.x, game.ball.y}, (Vector2){aimEndX, aimEndY}, 3.0f, col);
            DrawCircleV((Vector2){aimEndX, aimEndY}, 5.0f, col);
            DrawText(TextFormat("Power: %.0f / %.0f", power, MAX_DRAG_DISTANCE), 10, SCREEN_HEIGHT - 30, 20, WHITE);
        }
        
        // Draw player ball (white)
        if (!game.gameWon) drawBall(&game.ball);
        
        // Draw AI ball (different color) in VS mode
        if (currentScreen == SCREEN_VS_MODE && !game.aiWon) {
            // Draw AI ball with different color
            float heightFactor = 1.0f + (game.aiBall.z / 10.0f);
            float size = game.aiBall.radius * heightFactor;
            float shadowAlpha = fmaxf(0.12f, 1.0f / (1.0f + game.aiBall.z / 30.0f));
            DrawCircleV((Vector2){ game.aiBall.x, game.aiBall.y }, game.aiBall.radius * 0.9f, Fade(BLACK, shadowAlpha));
            DrawCircleV((Vector2){ game.aiBall.x, game.aiBall.y - game.aiBall.z * 0.9f }, size, YELLOW);  // Yellow for AI
            DrawCircleLines((int)game.aiBall.x, (int)(game.aiBall.y - game.aiBall.z * 0.9f), (int)size, BLACK);
        }
        
        // Show strokes - in VS mode show both player and AI
        if (currentScreen == SCREEN_VS_MODE) {
            DrawText(TextFormat("Your Strokes: %d", playerStrokes), 10, 10, 20, WHITE);
            DrawText(TextFormat("AI Strokes: %d", aiStrokes), 10, 35, 20, YELLOW);
            DrawText(TextFormat("Height: %.1f", game.ball.z), 10, 60, 16, WHITE);
            float speed = sqrtf(game.ball.vx*game.ball.vx + game.ball.vy*game.ball.vy);
            DrawText(TextFormat("Speed: %.2f", speed), 10, 80, 16, WHITE);
        } else {
            DrawText(TextFormat("Strokes: %d", game.strokes), 10, 10, 20, WHITE);
            DrawText(TextFormat("Height: %.1f", game.ball.z), 10, 35, 16, WHITE);
            float speed = sqrtf(game.ball.vx*game.ball.vx + game.ball.vy*game.ball.vy);
            DrawText(TextFormat("Speed: %.2f", speed), 10, 55, 16, WHITE);
        }
        
        float windArrowX = SCREEN_WIDTH - 80, windArrowY = 40;
        float arrowLen = 30.0f + (game.wind.appliedStrength / MAX_WIND_STRENGTH) * 30.0f;
        DrawLineEx((Vector2){windArrowX, windArrowY}, 
                  (Vector2){windArrowX + game.wind.dirX * arrowLen, windArrowY + game.wind.dirY * arrowLen}, 
                  3.0f, SKYBLUE);
        DrawCircleV((Vector2){windArrowX + game.wind.dirX * arrowLen, windArrowY + game.wind.dirY * arrowLen}, 5.0f, SKYBLUE);
        DrawText(TextFormat("Wind: %.1f", game.wind.appliedStrength), SCREEN_WIDTH - 100, 60, 14, WHITE);
        
        if (game.gameWon) {
            DrawText("HOLE IN!", SCREEN_WIDTH/2 - 60, SCREEN_HEIGHT/2, 30, YELLOW);
            DrawText(TextFormat("Strokes: %d", game.strokes), SCREEN_WIDTH/2 - 60, SCREEN_HEIGHT/2 + 35, 20, WHITE);
        }
        
        if (!game.ball.isMoving && !game.gameWon) {
            DrawText("DRAG from ball to aim", 10, 140, 16, LIGHTGRAY);
            DrawText("UP/DOWN - Loft angle", 10, 160, 16, LIGHTGRAY);
            DrawText(TextFormat("Loft: %.0f°", game.ball.angle), 10, 180, 16, LIGHTGRAY);
            DrawText("ESC - Menu | R - Reset", 10, SCREEN_HEIGHT - 60, 16, LIGHTGRAY);
        }
        
        EndDrawing();
    }
    
    if (gameInitialized) {
        UnloadTexture(game.mapTexture);
        UnloadImage(game.mapImage);
    }
    
    cleanupAIPipes();
    CloseWindow();
    return 0;
}
