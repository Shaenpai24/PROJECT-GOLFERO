# Requirements Document

## Introduction

This specification defines a comprehensive wind, spin, and Magnus effect system for the top-down golf physics engine. The system will add realistic environmental factors (wind) and ball physics (spin and Magnus effect) that affect ball trajectory during flight. Players will have control over spin parameters before shots, and visual feedback will indicate wind conditions. The system must integrate cleanly with the existing terrain-based physics without breaking current functionality.

## Glossary

- **Golf_Engine**: The existing C-based top-down golf physics simulation system using Raylib for rendering
- **Wind_System**: A global environmental force that affects airborne ball trajectory
- **Spin_System**: Ball rotation mechanics that generate Magnus forces during flight
- **Magnus_Effect**: The aerodynamic force perpendicular to ball motion caused by spin
- **Airborne_State**: The condition when ball.z > 0 or ball.inAir == true
- **Launch_Phase**: The moment when shootBall() is called and initial velocities are set
- **Player_Control_Phase**: The period when ball.isMoving == false and player can adjust parameters

## Requirements

### Requirement 1: Global Wind System

**User Story:** As a player, I want dynamic wind conditions that affect my shots, so that I must account for environmental factors in my strategy

#### Acceptance Criteria

1. THE Golf_Engine SHALL maintain a Wind struct containing dirX (float), dirY (float), strength (float), and timer (float) fields
2. WHEN timer reaches zero, THE Golf_Engine SHALL randomize wind direction to any angle and set strength between 0 and 60 pixels per second
3. WHEN timer reaches zero, THE Golf_Engine SHALL reset timer to a random value between 4.0 and 7.0 seconds
4. WHILE ball is in Airborne_State, THE Golf_Engine SHALL apply wind force by adding (wind.dirX * wind.strength * dt) to ball.vx and (wind.dirY * wind.strength * dt) to ball.vy each frame
5. WHEN ball is not in Airborne_State, THE Golf_Engine SHALL NOT apply wind forces to ball velocity

### Requirement 2: Ball Spin Mechanics

**User Story:** As a player, I want my golf ball to have realistic spin that affects its flight path, so that shots behave like real golf

#### Acceptance Criteria

1. THE Golf_Engine SHALL add spinX (float), spinY (float), and spinZ (float) fields to the Ball struct
2. WHEN shootBall() is called during Launch_Phase, THE Golf_Engine SHALL set ball.spinY to (baseLaunch * 0.02) to simulate backspin
3. WHEN shootBall() is called during Launch_Phase, THE Golf_Engine SHALL set ball.spinX to (-dirx * baseLaunch * 0.01) to simulate sidespin based on shot direction
4. WHEN shootBall() is called during Launch_Phase, THE Golf_Engine SHALL set ball.spinZ to 0.0
5. WHILE ball is in Airborne_State, THE Golf_Engine SHALL apply spin forces to ball trajectory

### Requirement 3: Magnus Effect Physics

**User Story:** As a player, I want spin to create curved ball flight through Magnus forces, so that I can shape my shots strategically

#### Acceptance Criteria

1. WHILE ball is in Airborne_State, THE Golf_Engine SHALL calculate magnusX as (-ball.spinY * ball.vy * 0.0008)
2. WHILE ball is in Airborne_State, THE Golf_Engine SHALL calculate magnusY as (ball.spinY * ball.vx * 0.0008)
3. WHILE ball is in Airborne_State, THE Golf_Engine SHALL add magnusX to ball.vx each frame
4. WHILE ball is in Airborne_State, THE Golf_Engine SHALL add magnusY to ball.vy each frame
5. WHEN ball is not in Airborne_State, THE Golf_Engine SHALL NOT apply Magnus forces

### Requirement 4: Player Spin Control

**User Story:** As a player, I want to manually adjust spin before my shot, so that I can intentionally curve or control ball flight

#### Acceptance Criteria

1. WHEN A key is pressed during Player_Control_Phase, THE Golf_Engine SHALL decrease ball.spinX by 1.0 to add left sidespin
2. WHEN D key is pressed during Player_Control_Phase, THE Golf_Engine SHALL increase ball.spinX by 1.0 to add right sidespin
3. WHEN W key is pressed during Player_Control_Phase, THE Golf_Engine SHALL increase ball.spinY by 1.0 to add backspin
4. WHEN S key is pressed during Player_Control_Phase, THE Golf_Engine SHALL decrease ball.spinY by 1.0 to add topspin
5. WHEN ball.isMoving equals true, THE Golf_Engine SHALL ignore all spin control key inputs
6. WHEN ball.isMoving equals false AND game.gameWon equals false, THE Golf_Engine SHALL accept spin control key inputs

### Requirement 5: Wind Visual Indicator

**User Story:** As a player, I want to see wind direction and strength on screen, so that I can plan my shots accordingly

#### Acceptance Criteria

1. THE Golf_Engine SHALL draw an arrow on screen indicating wind direction using wind.dirX and wind.dirY
2. THE Golf_Engine SHALL scale arrow length proportionally to wind.strength
3. THE Golf_Engine SHALL display text showing current wind strength value in pixels per second
4. THE Golf_Engine SHALL position wind indicator in a screen location that does not obscure gameplay
5. THE Golf_Engine SHALL render wind indicator every frame regardless of ball state

### Requirement 6: Wind-Affected Aim Trajectory

**User Story:** As a player, I want my aim line to show how wind will affect my shot, so that I can compensate for wind during aiming

#### Acceptance Criteria

1. WHEN player is dragging to aim a shot, THE Golf_Engine SHALL calculate aimEndX as (ball.x + dx + wind.dirX * wind.strength * 0.4)
2. WHEN player is dragging to aim a shot, THE Golf_Engine SHALL calculate aimEndY as (ball.y + dy + wind.dirY * wind.strength * 0.4)
3. WHEN player is dragging to aim a shot, THE Golf_Engine SHALL render aim line from ball position to adjusted aim endpoint
4. WHEN player is not dragging, THE Golf_Engine SHALL NOT render wind-adjusted aim line
5. THE Golf_Engine SHALL apply wind adjustment factor of 0.4 to prevent over-compensation in visual feedback

### Requirement 7: System Integration and Compatibility

**User Story:** As a developer, I want the new systems to integrate cleanly with existing code, so that terrain physics and gameplay remain functional

#### Acceptance Criteria

1. THE Golf_Engine SHALL initialize Wind struct with dirX=0, dirY=0, strength=0, timer=5.0 at game start
2. THE Golf_Engine SHALL initialize Ball spin fields (spinX, spinY, spinZ) to 0.0 when initBall() is called
3. WHEN updateBall() is called, THE Golf_Engine SHALL apply wind and Magnus forces before terrain physics calculations
4. WHEN ball lands (z <= 0), THE Golf_Engine SHALL preserve existing bounce, terrain damping, and hazard logic without modification
5. THE Golf_Engine SHALL compile successfully with gcc using flags: -lraylib -lm -lpthread -ldl
6. THE Golf_Engine SHALL maintain compatibility with C99 standard
7. THE Golf_Engine SHALL NOT modify existing TerrainProps struct or terrain detection logic
