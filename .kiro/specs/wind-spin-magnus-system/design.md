# Design Document: Wind, Spin, and Magnus Effect System

## Overview

This design implements a comprehensive physics enhancement for the golf engine by adding three interconnected systems: global wind forces, ball spin mechanics, and Magnus effect aerodynamics. The implementation follows a clean integration approach that preserves all existing terrain physics while adding new forces that only affect airborne balls. The design prioritizes minimal code changes, clear separation of concerns, and realistic physics behavior.

## Architecture

### System Components

The architecture consists of four main components:

1. **Wind Management System** - Handles wind state, randomization, and force application
2. **Spin State System** - Manages ball spin values and player control inputs
3. **Magnus Force Calculator** - Computes aerodynamic forces from spin during flight
4. **Visual Feedback System** - Renders wind indicators and adjusted aim trajectories

### Data Flow

```
Game Loop
    ├─> Update Wind Timer → Randomize if expired
    ├─> Process Player Input → Adjust spin (if stationary)
    ├─> Update Ball Physics
    │       ├─> Apply Gravity
    │       ├─> Update Position
    │       ├─> [IF AIRBORNE] Apply Wind Forces
    │       ├─> [IF AIRBORNE] Apply Magnus Forces
    │       ├─> Apply Air Drag
    │       └─> Handle Terrain Collision & Damping
    └─> Render
            ├─> Draw Wind Indicator
            ├─> Draw Aim Line (with wind adjustment)
            └─> Draw Ball
```

### Integration Points

The new systems integrate at specific points in the existing code:

- **Struct Extensions**: Add fields to existing Ball struct and GameState struct
- **Initialization**: Extend initBall() and game initialization
- **Launch Phase**: Extend shootBall() to set initial spin values
- **Physics Update**: Insert wind and Magnus calculations in updateBall() before terrain logic
- **Input Handling**: Add spin control keys in main loop's input section
- **Rendering**: Add wind indicator and modify aim line calculation

## Components and Interfaces

### 1. Wind Struct

```c
typedef struct {
    float dirX, dirY;  // Normalized direction vector
    float strength;    // Wind speed in px/s (0-60)
    float timer;       // Countdown to next wind change (seconds)
} Wind;
```

**Purpose**: Encapsulates all wind state in a single struct for clean organization.

**Design Decisions**:
- Direction stored as normalized vector for efficient force calculation
- Strength separate from direction allows independent randomization
- Timer enables automatic wind changes without external timing logic

### 2. Extended Ball Struct

```c
typedef struct {
    // ... existing fields ...
    float spinX, spinY, spinZ; // NEW: Spin components
} Ball;
```

**Purpose**: Adds spin state to ball without disrupting existing physics fields.

**Design Decisions**:
- Three-axis spin allows future expansion (e.g., spinZ for roll spin)
- Float precision matches existing velocity fields
- Placed at end of struct to minimize memory layout changes

### 3. Wind Update Function

```c
void updateWind(Wind *w, float dt) {
    w->timer -= dt;
    if (w->timer <= 0.0f) {
        // Randomize direction (0-360 degrees)
        float angle = ((float)rand() / RAND_MAX) * 2.0f * PI;
        w->dirX = cosf(angle);
        w->dirY = sinf(angle);
        
        // Randomize strength (0-60 px/s)
        w->strength = ((float)rand() / RAND_MAX) * 60.0f;
        
        // Reset timer (4-7 seconds)
        w->timer = 4.0f + ((float)rand() / RAND_MAX) * 3.0f;
    }
}
```

**Purpose**: Encapsulates wind randomization logic in a single function.

**Design Decisions**:
- Uses standard C rand() for simplicity (no external RNG needed)
- Trigonometric direction generation ensures uniform distribution
- Timer range (4-7s) provides dynamic but not chaotic wind changes

### 4. Wind Force Application

**Location**: Inside updateBall(), after position update, only when ball.inAir == true

```c
// Apply wind force (only when airborne)
if (ball->inAir) {
    ball->vx += wind.dirX * wind.strength * dt;
    ball->vy += wind.dirY * wind.strength * dt;
}
```

**Design Decisions**:
- Simple additive force model (realistic for golf ball speeds)
- Conditional on inAir flag prevents ground-rolling wind effects
- Uses dt for frame-rate independence

### 5. Spin Initialization at Launch

**Location**: Inside shootBall(), after velocity calculation

```c
// Set default spin based on shot
ball->spinY = baseLaunch * 0.02f;  // Backspin
ball->spinX = -dirx * baseLaunch * 0.01f;  // Sidespin from shot direction
ball->spinZ = 0.0f;
```

**Design Decisions**:
- Backspin proportional to launch power (harder hits = more spin)
- Sidespin based on shot direction creates natural curve
- Coefficients (0.02, 0.01) tuned for subtle but noticeable effect
- Negative sign on spinX creates realistic right-to-left curve for rightward shots

### 6. Magnus Effect Calculation

**Location**: Inside updateBall(), after wind forces, only when ball.inAir == true

```c
// Apply Magnus effect (only when airborne)
if (ball->inAir) {
    float magnusX = -ball->spinY * ball->vy * 0.0008f;
    float magnusY =  ball->spinY * ball->vx * 0.0008f;
    ball->vx += magnusX;
    ball->vy += magnusY;
}
```

**Design Decisions**:
- Magnus force perpendicular to velocity (cross product simplified for 2D)
- Coefficient 0.0008 provides realistic curve without overpowering trajectory
- Negative sign on magnusX creates proper lift direction for backspin
- Applied as velocity change (force integration) rather than acceleration

**Physics Rationale**: Magnus force F = k × (ω × v), where ω is spin and v is velocity. In 2D top-down view, spinY (backspin) creates forces perpendicular to motion direction.

### 7. Player Spin Control

**Location**: Main game loop, in input handling section, before drag detection

```c
// Spin control (only when ball is stationary)
if (!game.ball.isMoving && !game.gameWon) {
    if (IsKeyPressed(KEY_A)) game.ball.spinX -= 1.0f;  // Left spin
    if (IsKeyPressed(KEY_D)) game.ball.spinX += 1.0f;  // Right spin
    if (IsKeyPressed(KEY_W)) game.ball.spinY += 1.0f;  // More backspin
    if (IsKeyPressed(KEY_S)) game.ball.spinY -= 1.0f;  // Topspin
}
```

**Design Decisions**:
- Uses IsKeyPressed() for discrete increments (not continuous hold)
- WASD keys for intuitive directional control
- Unit increments allow fine-tuning without overwhelming effect
- Conditional on !isMoving prevents mid-flight spin changes

### 8. Wind Visual Indicator

**Location**: Rendering section, drawn every frame

```c
// Draw wind indicator (top-right corner)
float windArrowX = SCREEN_WIDTH - 80;
float windArrowY = 40;
float arrowLen = 30.0f + (wind.strength / 60.0f) * 30.0f;  // 30-60px length
Vector2 arrowStart = {windArrowX, windArrowY};
Vector2 arrowEnd = {
    windArrowX + wind.dirX * arrowLen,
    windArrowY + wind.dirY * arrowLen
};

DrawLineEx(arrowStart, arrowEnd, 3.0f, SKYBLUE);
DrawCircleV(arrowEnd, 5.0f, SKYBLUE);  // Arrowhead
DrawText(TextFormat("Wind: %.0f", wind.strength), 
         SCREEN_WIDTH - 100, 60, 16, WHITE);
```

**Design Decisions**:
- Top-right position avoids gameplay area and existing UI
- Arrow length scales with strength (visual magnitude indication)
- Sky blue color distinguishes from other UI elements
- Numeric strength display for precise information

### 9. Wind-Adjusted Aim Line

**Location**: Drag rendering section, modifies existing aim line calculation

```c
if (game.isDragging) {
    float dx = game.dragStart.x - mousePos.x;
    float dy = game.dragStart.y - mousePos.y;
    float power = sqrtf(dx*dx + dy*dy);
    if (power > MAX_DRAG_DISTANCE) power = MAX_DRAG_DISTANCE;
    
    // Apply wind adjustment to aim endpoint
    float aimEndX = game.ball.x + dx + game.wind.dirX * game.wind.strength * 0.4f;
    float aimEndY = game.ball.y + dy + game.wind.dirY * game.wind.strength * 0.4f;
    
    // ... existing rendering code ...
}
```

**Design Decisions**:
- Factor 0.4 provides visual hint without exact trajectory prediction
- Additive adjustment (not multiplicative) for linear wind effect
- Applied to endpoint only (start remains at ball position)
- Preserves existing power capping and color logic

## Data Models

### Wind State

- **dirX, dirY**: Float values representing normalized direction vector (magnitude = 1.0)
- **strength**: Float in range [0.0, 60.0] representing wind speed in pixels per second
- **timer**: Float countdown in seconds, range [0.0, 7.0]

### Ball Spin State

- **spinX**: Float representing sidespin (negative = left curve, positive = right curve)
- **spinY**: Float representing backspin/topspin (positive = backspin/lift, negative = topspin/drop)
- **spinZ**: Float reserved for future roll spin mechanics (currently unused)

**Typical Value Ranges**:
- Default launch: spinY ≈ 3-12, spinX ≈ -3 to 3
- Player-adjusted: spinX ≈ -10 to 10, spinY ≈ -5 to 15
- Magnus force magnitude: ≈ 0.01 to 0.5 px/s² (subtle but cumulative)

## Error Handling

### Division by Zero Protection

- Wind direction normalization: Already handled by trigonometric generation (always produces unit vector)
- Spin calculations: No division operations, only multiplication
- Existing code already protects against zero-length drag vectors

### Boundary Conditions

- **Wind strength**: Clamped by random generation to [0, 60]
- **Wind timer**: Reset to positive value immediately when reaching zero
- **Spin values**: No explicit limits (player can accumulate large values, but Magnus coefficient keeps effect reasonable)
- **Ball position**: Existing boundary clamping preserved

### State Consistency

- **Spin reset**: When initBall() is called (reset, water hazard), spin values reset to 0.0
- **Wind persistence**: Wind state persists across shots and resets (global environmental factor)
- **Airborne check**: Both wind and Magnus forces use existing ball.inAir flag for consistency

## Testing Strategy

### Unit Testing Approach

Since this is a single-file C program with Raylib dependencies, formal unit tests are impractical. Instead, use manual verification with debug output:

1. **Wind System Verification**
   - Add printf() in updateWind() to log direction and strength changes
   - Verify timer resets occur in 4-7 second intervals
   - Confirm strength values stay in [0, 60] range

2. **Spin Initialization Verification**
   - Add printf() in shootBall() to log initial spin values
   - Verify spinY scales with baseLaunch
   - Verify spinX correlates with shot direction

3. **Magnus Effect Verification**
   - Add printf() in updateBall() to log Magnus forces when airborne
   - Verify forces are zero when ball is grounded
   - Observe ball trajectory curves in direction consistent with spin

4. **Player Control Verification**
   - Display current spin values on screen
   - Verify WASD keys modify spin only when ball is stationary
   - Confirm spin values persist until next shot

### Integration Testing

1. **Terrain Compatibility**
   - Test shots on each terrain type (sand, rough, fairway, smooth, water, forest)
   - Verify wind/Magnus forces don't interfere with terrain damping
   - Confirm bounce behavior unchanged

2. **Multi-Shot Scenarios**
   - Verify spin resets between shots
   - Confirm wind changes occur during gameplay
   - Test rapid successive shots

3. **Edge Cases**
   - Zero wind strength (should behave like original engine)
   - Maximum wind strength (60 px/s)
   - Extreme spin values (player holds WASD for extended time)
   - Very short shots (low power)

### Visual Verification

1. **Wind Indicator**
   - Verify arrow points in correct direction
   - Confirm length scales with strength
   - Check text displays correct numeric value

2. **Aim Line Adjustment**
   - Verify aim line shifts in wind direction
   - Confirm adjustment magnitude feels intuitive
   - Test with various wind strengths

### Performance Considerations

- All new calculations are simple arithmetic (no expensive operations)
- Wind update occurs once per frame (negligible cost)
- Magnus calculations only when airborne (conditional execution)
- No additional memory allocations (all stack-based)
- Expected performance impact: < 1% (unmeasurable on modern hardware)

## Implementation Notes

### Code Organization

- Wind struct definition: After TerrainProps, before Ball struct
- updateWind() function: After getTerrainAt(), before initBall()
- Wind/Magnus forces: Inside updateBall(), after position update, before air drag
- Spin controls: In main loop, after angle controls, before drag detection
- Wind indicator: In rendering section, after terrain info, before game won check

### Compilation

No changes to compilation command:
```bash
gcc main.c -o golf -lraylib -lm -lpthread -ldl
```

The math.h functions (cosf, sinf, sqrtf) are already used in existing code.

### Backward Compatibility

- Existing save files: N/A (no save system)
- Existing gameplay: Fully preserved when wind strength is zero
- Existing controls: No conflicts (WASD keys were unused)
- Existing physics: All terrain logic unchanged

### Future Enhancements

Potential extensions not included in this design:

- Spin decay over time (spin reduces during flight)
- Terrain-dependent spin (rough terrain reduces spin on launch)
- Visual spin indicator on ball (rotation animation)
- Wind gusts (temporary strength spikes)
- Altitude-dependent wind (stronger wind at higher z values)
- spinZ integration for roll behavior on ground
