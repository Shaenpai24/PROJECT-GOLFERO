"""
Surrogate Physics - Fast approximation for shot planning
Simplified physics model for rapid evaluation during optimization
"""
import math
from typing import Tuple, List
import numpy as np


class SurrogatePhysics:
    """Fast physics approximation for planning"""
    
    def __init__(self):
        # Physics constants (EXACT match from main.c)
        self.GRAVITY = 800.0
        self.DT = 0.016
        self.LAUNCH_SCALE = 4.0
        self.Z_SCALE = 0.6
        self.AIR_DRAG = 1.6
        self.STOP_SPEED = 2.0
        self.MAX_STEPS = 1000
        self.WIND_SMOOTHNESS = 0.25
        self.GROUND_WIND_FACTOR = 0.08
        self.SPIN_AIR_DAMP = 0.996
        self.SPIN_GROUND_DAMP = 0.985
        self.wind_smooth = 0.0  # Smoothed wind strength
        
        # Terrain approximations
        self.terrain_damping = {
            'fairway': 0.96,
            'rough': 0.80,
            'sand': 0.45,
            'smooth': 0.98,
            'water': 0.0,  # hazard
            'forest': 0.40  # hazard
        }
        
        self.terrain_bounce = {
            'fairway': 0.60,
            'rough': 0.55,
            'sand': 0.05,
            'smooth': 0.75,
            'water': 0.0,
            'forest': 0.0
        }
    
    def simulate_shot(self, start_x: float, start_y: float, 
                     dirx: float, diry: float, angle: float, power: float,
                     wind_x: float = 0.0, wind_y: float = 0.0, wind_strength: float = 0.0,
                     spinx: float = 0.0, spiny: float = 0.0,
                     terrain: str = 'fairway', debug: bool = False) -> Tuple[float, float, List[Tuple[float, float]]]:
        """
        Simulate a shot and return final position (EXACT C physics match)
        
        Returns:
            (final_x, final_y, trajectory_points)
        """
        # Normalize direction
        mag = math.sqrt(dirx**2 + diry**2)
        if mag < 1e-6:
            dirx, diry = 0.0, -1.0
        else:
            dirx /= mag
            diry /= mag
        
        # Initial velocity (EXACT match to C)
        angle_rad = math.radians(angle)
        launch = power * self.LAUNCH_SCALE
        
        horizontal_speed = launch * math.cos(angle_rad)
        vx = horizontal_speed * dirx
        vy = horizontal_speed * diry
        vz = launch * math.sin(angle_rad) * self.Z_SCALE
        
        # Reset wind smoothing for this shot
        self.wind_smooth = 0.0
        
        # Position
        x, y, z = start_x, start_y, 0.0
        
        # Trajectory tracking
        trajectory = [(x, y)]
        
        # Simulation loop
        for step in range(self.MAX_STEPS):
            # Gravity
            vz -= self.GRAVITY * self.DT
            
            # Update position
            x += vx * self.DT
            y += vy * self.DT
            z += vz * self.DT
            
            # Airborne check (EXACT match to C)
            airborne = z > 1.0
            
            # Update wind smoothing (EXACT match to C)
            self.wind_smooth += self.WIND_SMOOTHNESS * (wind_strength - self.wind_smooth)
            
            # Wind effect
            if airborne:
                # Airborne wind (use smoothed wind)
                vx += wind_x * self.wind_smooth * self.DT
                vy += wind_y * self.wind_smooth * self.DT
                
                # Magnus effect (EXACT match to C)
                magnus_x = -spiny * vy * 0.0012
                magnus_y = spiny * vx * 0.0012
                # Clamp magnus
                magnus_x = max(-10.0, min(10.0, magnus_x))
                magnus_y = max(-10.0, min(10.0, magnus_y))
                vx += magnus_x
                vy += magnus_y
                
                # Air drag
                vx -= vx * self.AIR_DRAG * self.DT
                vy -= vy * self.AIR_DRAG * self.DT
            else:
                # Ground wind (EXACT match to C)
                vx += wind_x * self.wind_smooth * self.GROUND_WIND_FACTOR * self.DT
                vy += wind_y * self.wind_smooth * self.GROUND_WIND_FACTOR * self.DT
            
            # Spin decay (EXACT match to C)
            if airborne:
                spinx *= self.SPIN_AIR_DAMP
                spiny *= self.SPIN_AIR_DAMP
            else:
                spinx *= self.SPIN_GROUND_DAMP
                spiny *= self.SPIN_GROUND_DAMP
            
            # Ground contact
            if z <= 0.0:
                z = 0.0
                
                # Bounce
                if abs(vz) > 10.0 and self.terrain_bounce.get(terrain, 0.6) > 0.01:
                    vz = -vz * self.terrain_bounce.get(terrain, 0.6)
                else:
                    vz = 0.0
                
                # Roll damping (EXACT match to C - use terrain damping)
                damping = self.terrain_damping.get(terrain, 0.96)
                vx *= damping
                vy *= damping
            
            # Track trajectory
            if step % 5 == 0:
                trajectory.append((x, y))
            
            # Stop condition
            speed = math.sqrt(vx**2 + vy**2)
            if speed < self.STOP_SPEED and z < 0.1 and abs(vz) < 0.2:
                break
        
        trajectory.append((x, y))
        return x, y, trajectory
    
    def estimate_shot_to_target(self, start_x: float, start_y: float,
                                target_x: float, target_y: float,
                                terrain: str = 'fairway') -> Tuple[float, float, float]:
        """
        Estimate shot parameters to reach target
        
        Returns:
            (dirx, diry, power) - initial guess for optimizer
        """
        dx = target_x - start_x
        dy = target_y - start_y
        distance = math.sqrt(dx**2 + dy**2)
        
        # Normalize direction
        if distance < 1e-6:
            return 0.0, -1.0, 0.0
        
        dirx = dx / distance
        diry = dy / distance
        
        # Estimate power (AGGRESSIVE for minimum strokes)
        # Account for terrain damping
        damping_factor = self.terrain_damping.get(terrain, 0.96)
        power = distance / (self.LAUNCH_SCALE * 1.2 * damping_factor)
        power = min(power, 150.0)  # Max drag distance
        
        return dirx, diry, power
    
    def evaluate_landing_zone(self, x: float, y: float, hole_x: float, hole_y: float,
                              terrain: str = 'fairway') -> float:
        """
        Score a landing zone (lower is better)
        """
        distance_to_hole = math.sqrt((x - hole_x)**2 + (y - hole_y)**2)
        
        # Terrain penalties
        terrain_penalty = {
            'fairway': 0.0,
            'smooth': -10.0,  # bonus
            'rough': 20.0,
            'sand': 50.0,
            'water': 1000.0,  # avoid
            'forest': 1000.0  # avoid
        }
        
        penalty = terrain_penalty.get(terrain, 0.0)
        
        return distance_to_hole + penalty
