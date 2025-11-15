"""
Low-Level Optimizer - CMA-ES based shot parameter optimization
Finds exact direction, angle, power, and spin for target
"""
import math
import numpy as np
from typing import Tuple, Callable, Optional
from surrogate_physics import SurrogatePhysics


class ShotOptimizer:
    """CMA-ES optimizer for precise shot parameters"""
    
    def __init__(self):
        self.surrogate = SurrogatePhysics()
        self.max_evaluations = 200
        self.population_size = 20
    
    def optimize_shot(self, ball_x: float, ball_y: float,
                     target_x: float, target_y: float,
                     angle_hint: float = 45.0,
                     wind_x: float = 0.0, wind_y: float = 0.0, 
                     wind_strength: float = 0.0,
                     terrain: str = 'fairway') -> Tuple[float, float, float, float, float, float]:
        """
        Optimize shot parameters using CMA-ES
        
        Returns:
            (dirx, diry, angle, power, spinx, spiny)
        """
        # Initial guess
        dx = target_x - ball_x
        dy = target_y - ball_y
        distance = math.sqrt(dx**2 + dy**2)
        
        if distance < 1e-6:
            return 0.0, -1.0, 45.0, 0.0, 0.0, 0.0
        
        init_dirx = dx / distance
        init_diry = dy / distance
        init_power = min(distance / 8.0, 150.0)
        
        # Use simplified CMA-ES (manual implementation)
        best_params, best_score = self._cmaes_optimize(
            ball_x, ball_y, target_x, target_y,
            init_dirx, init_diry, angle_hint, init_power,
            wind_x, wind_y, wind_strength, terrain
        )
        
        dirx, diry, angle, power, spinx, spiny = best_params
        
        print(f"  Optimizer: distance={distance:.1f}, angle={angle:.1f}°, "
              f"power={power:.1f}, final_error={best_score:.1f}")
        
        return dirx, diry, angle, power, spinx, spiny
    
    def _cmaes_optimize(self, ball_x: float, ball_y: float,
                       target_x: float, target_y: float,
                       init_dirx: float, init_diry: float,
                       init_angle: float, init_power: float,
                       wind_x: float, wind_y: float, wind_strength: float,
                       terrain: str) -> Tuple[np.ndarray, float]:
        """
        Simplified CMA-ES implementation
        
        Parameters to optimize:
        [0] direction_angle (radians)
        [1] launch_angle (degrees)
        [2] power (0-150)
        [3] spinx (-10 to 10)
        [4] spiny (-10 to 10)
        """
        # Initial mean
        init_dir_angle = math.atan2(init_diry, init_dirx)
        mean = np.array([
            init_dir_angle,
            init_angle,
            init_power,
            0.0,  # spinx
            0.0   # spiny
        ])
        
        # Initial step sizes
        sigma = np.array([0.3, 10.0, 20.0, 2.0, 2.0])
        
        best_params = mean.copy()
        best_score = float('inf')
        
        # Simple evolution strategy
        for generation in range(self.max_evaluations // self.population_size):
            # Generate population
            population = []
            scores = []
            
            for _ in range(self.population_size):
                # Sample candidate
                candidate = mean + sigma * np.random.randn(5)
                
                # Clamp to valid ranges
                candidate[1] = np.clip(candidate[1], 0.0, 75.0)  # angle
                candidate[2] = np.clip(candidate[2], 5.0, 150.0)  # power
                candidate[3] = np.clip(candidate[3], -10.0, 10.0)  # spinx
                candidate[4] = np.clip(candidate[4], -10.0, 10.0)  # spiny
                
                # Evaluate
                score = self._evaluate_shot(
                    ball_x, ball_y, target_x, target_y,
                    candidate, wind_x, wind_y, wind_strength, terrain
                )
                
                population.append(candidate)
                scores.append(score)
                
                if score < best_score:
                    best_score = score
                    best_params = candidate.copy()
            
            # Update mean (select top 50%)
            sorted_indices = np.argsort(scores)
            elite_size = self.population_size // 2
            elite_indices = sorted_indices[:elite_size]
            
            elite_population = [population[i] for i in elite_indices]
            mean = np.mean(elite_population, axis=0)
            
            # Adapt sigma (simple rule)
            sigma *= 0.95
            
            # Early stopping if very close
            if best_score < 5.0:
                break
        
        # Convert back to shot parameters
        dir_angle = best_params[0]
        dirx = math.cos(dir_angle)
        diry = math.sin(dir_angle)
        angle = best_params[1]
        power = best_params[2]
        spinx = best_params[3]
        spiny = best_params[4]
        
        return np.array([dirx, diry, angle, power, spinx, spiny]), best_score
    
    def _evaluate_shot(self, ball_x: float, ball_y: float,
                      target_x: float, target_y: float,
                      params: np.ndarray,
                      wind_x: float, wind_y: float, wind_strength: float,
                      terrain: str) -> float:
        """Evaluate shot quality (distance to target) - includes wind in simulation"""
        dir_angle = params[0]
        dirx = math.cos(dir_angle)
        diry = math.sin(dir_angle)
        angle = params[1]
        power = params[2]
        spinx = params[3]
        spiny = params[4]
        
        # Simulate using surrogate physics WITH WIND
        final_x, final_y, _ = self.surrogate.simulate_shot(
            ball_x, ball_y, dirx, diry, angle, power,
            wind_x, wind_y, wind_strength, spinx, spiny, terrain
        )
        
        # Distance to target
        error = math.sqrt((final_x - target_x)**2 + (final_y - target_y)**2)
        
        return error
    
    def quick_optimize(self, ball_x: float, ball_y: float,
                      target_x: float, target_y: float,
                      angle_hint: float = 45.0,
                      wind_x: float = 0.0, wind_y: float = 0.0, 
                      wind_strength: float = 0.0,
                      terrain: str = 'fairway') -> Tuple[float, float, float, float]:
        """
        Quick optimization with wind compensation
        
        Returns:
            (dirx, diry, angle, power)
        """
        dx = target_x - ball_x
        dy = target_y - ball_y
        distance = math.sqrt(dx**2 + dy**2)
        
        if distance < 1e-6:
            return 0.0, -1.0, 45.0, 0.0
        
        # SAND ESCAPE: Use maximum power!
        if terrain == 'sand':
            # In sand, use MAXIMUM power to escape
            power = 150.0  # Always max power in sand
            angle = 75.0   # VERY high angle to minimize ground contact
            
            # Still need wind compensation even in sand!
            dirx = dx / distance
            diry = dy / distance
            
            # Simulate to get actual wind drift
            test_x, test_y, _ = self.surrogate.simulate_shot(
                ball_x, ball_y, dirx, diry, angle, power,
                wind_x, wind_y, wind_strength, 0.0, 0.0, terrain
            )
            
            # Calculate drift
            drift_x = test_x - target_x
            drift_y = test_y - target_y
            drift_distance = math.sqrt(drift_x**2 + drift_y**2)
            
            # Clamp compensation to avoid overshooting
            max_compensation = distance * 0.5
            if drift_distance > max_compensation:
                scale = max_compensation / drift_distance
                drift_x *= scale
                drift_y *= scale
            
            # Compensate by aiming opposite to drift
            compensated_x = target_x - drift_x
            compensated_y = target_y - drift_y
            
            dx_comp = compensated_x - ball_x
            dy_comp = compensated_y - ball_y
            dist_comp = math.sqrt(dx_comp**2 + dy_comp**2)
            
            if dist_comp > 1e-6:
                dirx = dx_comp / dist_comp
                diry = dy_comp / dist_comp
            
            print(f"    💥 SAND ESCAPE: MAX POWER (150) + HIGH ANGLE (70°) + WIND COMP")
            return dirx, diry, angle, power
        
        # Power estimation based on distance (VERY CONSERVATIVE near hole)
        if distance < 10:
            # Super close - barely tap it
            power = distance * 0.3
            angle = 2.0
        elif distance < 20:
            # Very close - super gentle putt
            power = distance * 0.35
            angle = 5.0
        elif distance < 40:
            # Close putt - gentle
            power = distance * 0.45
            angle = 10.0
        elif distance < 70:
            # Short chip - controlled
            power = distance * 0.6
            angle = 18.0
        elif distance < 120:
            # Medium chip - moderate power
            power = distance * 0.85
            angle = 28.0
        elif distance < 200:
            # Approach shot - controlled aggression
            power = distance * 0.75
            angle = 35.0
        else:
            # Long drive - maximum distance
            power = min(distance * 0.55, 150.0)
            angle = 38.0  # Optimal angle for distance
        
        # Initial direction
        dirx = dx / distance
        diry = dy / distance
        
        # Wind compensation: simulate shot and adjust
        if abs(wind_strength) > 0.1:
            # Test shot with current parameters
            test_x, test_y, _ = self.surrogate.simulate_shot(
                ball_x, ball_y, dirx, diry, angle, power,
                wind_x, wind_y, wind_strength, 0.0, 0.0, terrain
            )
            
            # Calculate drift from target
            drift_x = test_x - target_x
            drift_y = test_y - target_y
            drift_distance = math.sqrt(drift_x**2 + drift_y**2)
            
            # If drift is significant, compensate
            if drift_distance > 5.0:
                # Clamp compensation to avoid overshooting
                # Don't compensate more than 50% of the distance to target
                max_compensation = distance * 0.5
                if drift_distance > max_compensation:
                    # Scale down the drift
                    scale = max_compensation / drift_distance
                    drift_x *= scale
                    drift_y *= scale
                    drift_distance = max_compensation
                
                # Aim opposite to the drift
                compensated_x = target_x - drift_x
                compensated_y = target_y - drift_y
                
                dx_comp = compensated_x - ball_x
                dy_comp = compensated_y - ball_y
                dist_comp = math.sqrt(dx_comp**2 + dy_comp**2)
                
                if dist_comp > 1e-6:
                    dirx = dx_comp / dist_comp
                    diry = dy_comp / dist_comp
                    print(f"    🌬️  Wind compensation: drift={drift_distance:.1f}px, adjusted aim")
        
        return dirx, diry, angle, power
