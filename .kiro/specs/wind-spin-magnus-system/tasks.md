# Implementation Plan

- [x] 1. Add Wind struct and extend Ball struct with spin fields
  - Add Wind struct definition after TerrainProps struct with dirX, dirY, strength, and timer fields
  - Add spinX, spinY, spinZ float fields to Ball struct
  - Add Wind field to GameState struct
  - _Requirements: 1.1, 2.1, 7.1, 7.2_

- [x] 2. Implement wind update system
  - Create updateWind() function that decrements timer and randomizes wind when timer expires
  - Use rand() to generate random angle (0-2π) and convert to normalized dirX/dirY using cos/sin
  - Randomize strength between 0-60 px/s
  - Reset timer to random value between 4.0-7.0 seconds
  - Call updateWind() in main game loop before ball physics update
  - _Requirements: 1.2, 1.3, 7.1_

- [x] 3. Initialize wind and spin state at game start
  - Initialize game.wind with dirX=0, dirY=0, strength=0, timer=5.0 in main() after GameState creation
  - Modify initBall() to set ball->spinX, ball->spinY, ball->spinZ to 0.0
  - _Requirements: 2.1, 7.1, 7.2_

- [x] 4. Add spin initialization in shootBall()
  - After velocity calculation in shootBall(), set ball->spinY = baseLaunch * 0.02f for backspin
  - Set ball->spinX = -dirx * baseLaunch * 0.01f for sidespin based on shot direction
  - Set ball->spinZ = 0.0f
  - _Requirements: 2.2, 2.3, 2.4_

- [x] 5. Implement wind force application in updateBall()
  - Inside updateBall(), after position update (x += vx*dt, y += vy*dt, z += vz*dt)
  - Add conditional check: if (ball->inAir)
  - Apply wind forces: ball->vx += wind.dirX * wind.strength * dt
  - Apply wind forces: ball->vy += wind.dirY * wind.strength * dt
  - Place this code before existing air drag application
  - _Requirements: 1.4, 1.5, 7.3_

- [x] 6. Implement Magnus effect in updateBall()
  - Inside updateBall(), after wind force application, still within if (ball->inAir) block
  - Calculate magnusX = -ball->spinY * ball->vy * 0.0008f
  - Calculate magnusY = ball->spinY * ball->vx * 0.0008f
  - Apply Magnus forces: ball->vx += magnusX and ball->vy += magnusY
  - _Requirements: 2.5, 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 7. Add player spin control inputs
  - In main game loop, after angle control (UP/DOWN keys), before drag detection
  - Add conditional: if (!game.ball.isMoving && !game.gameWon)
  - Implement KEY_A: game.ball.spinX -= 1.0f (left spin)
  - Implement KEY_D: game.ball.spinX += 1.0f (right spin)
  - Implement KEY_W: game.ball.spinY += 1.0f (more backspin)
  - Implement KEY_S: game.ball.spinY -= 1.0f (topspin)
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [x] 8. Create wind visual indicator
  - In rendering section (BeginDrawing/EndDrawing), after terrain info display
  - Calculate arrow position: windArrowX = SCREEN_WIDTH - 80, windArrowY = 40
  - Calculate arrow length: arrowLen = 30.0f + (game.wind.strength / 60.0f) * 30.0f
  - Draw arrow line from (windArrowX, windArrowY) to (windArrowX + wind.dirX * arrowLen, windArrowY + wind.dirY * arrowLen) using DrawLineEx with 3.0f thickness and SKYBLUE color
  - Draw circle at arrow end with radius 5.0f and SKYBLUE color
  - Draw text showing wind strength: DrawText(TextFormat("Wind: %.0f", game.wind.strength), SCREEN_WIDTH - 100, 60, 16, WHITE)
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

- [x] 9. Modify aim line to show wind adjustment
  - In existing drag rendering code (if (game.isDragging) block)
  - After calculating dx, dy, and power
  - Modify aimEndX calculation: aimEndX = game.ball.x + dx + game.wind.dirX * game.wind.strength * 0.4f
  - Modify aimEndY calculation: aimEndY = game.ball.y + dy + game.wind.dirY * game.wind.strength * 0.4f
  - Keep existing DrawLineEx and DrawCircleV calls using adjusted aimEndX/aimEndY
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 10. Add spin display for player feedback
  - In rendering section, add text display showing current spin values
  - Display spinX and spinY values when ball is not moving
  - Position near existing control instructions (around y=200)
  - Use format: DrawText(TextFormat("Spin X: %.1f Y: %.1f", game.ball.spinX, game.ball.spinY), 10, 200, 16, LIGHTGRAY)
  - _Requirements: 4.1, 4.2, 4.3, 4.4_

- [x] 11. Verify compilation and integration
  - Compile code with: gcc main.c -o golf -lraylib -lm -lpthread -ldl
  - Verify no compilation errors or warnings
  - Test that game launches and existing functionality works
  - _Requirements: 7.5, 7.6_

- [ ]* 12. Manual testing and verification
  - Test wind system: observe wind changes every 4-7 seconds, verify arrow indicator updates
  - Test spin controls: press WASD keys when stationary, verify spin values change
  - Test Magnus effect: hit shots with different spin values, observe curved trajectories
  - Test wind forces: observe ball drift during flight in wind direction
  - Test terrain compatibility: verify all terrain types still work correctly (sand, water, rough, fairway, smooth, forest)
  - Test aim line adjustment: verify aim line shifts with wind during drag
  - Test edge cases: zero wind, maximum wind, extreme spin values, very short shots
  - _Requirements: All requirements_
