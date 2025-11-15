"""
High-Level Planner - Strategic waypoint selection using A* search
Decides: drive, layup, chip, lob, putt based on terrain and distance
"""
import math
import heapq
from typing import List, Tuple, Optional, Dict
from surrogate_physics import SurrogatePhysics


class ShotType:
    DRIVE = "drive"      # Long distance, low angle
    LAYUP = "layup"      # Medium distance, safe positioning
    CHIP = "chip"        # Short distance, medium angle
    LOB = "lob"          # High angle, short distance
    PUTT = "putt"        # Very short, roll only


class HighLevelPlanner:
    """Strategic planning for shot selection"""
    
    def __init__(self, map_width: int = 640, map_height: int = 640):
        self.map_width = map_width
        self.map_height = map_height
        self.surrogate = SurrogatePhysics()
        
        # Shot type parameters (OPTIMIZED angles)
        self.shot_params = {
            ShotType.DRIVE: {"angle": 38.0, "power_range": (80, 150)},  # Optimal for distance
            ShotType.LAYUP: {"angle": 35.0, "power_range": (40, 80)},
            ShotType.CHIP: {"angle": 30.0, "power_range": (20, 50)},  # Lower for accuracy
            ShotType.LOB: {"angle": 75.0, "power_range": (100, 150)},  # VERY HIGH angle + MAX power for sand escape
            ShotType.PUTT: {"angle": 5.0, "power_range": (5, 30)}
        }
    
    def plan_strategy(self, ball_x: float, ball_y: float, 
                     hole_x: float, hole_y: float,
                     terrain_map: Optional[Dict] = None,
                     current_terrain: str = 'fairway') -> Tuple[str, float, float]:
        """
        Plan high-level strategy
        
        Returns:
            (shot_type, target_x, target_y)
        """
        distance = math.sqrt((hole_x - ball_x)**2 + (hole_y - ball_y)**2)
        
        # PRIORITY 1: Escape sand trap with MAXIMUM POWER!
        if current_terrain == 'sand':
            shot_type = ShotType.LOB
            # Use HIGH angle and MAXIMUM power to escape
            # Aim directly at hole - the high angle will get us out
            target_x, target_y = hole_x, hole_y
            print(f"  🏖️  SAND ESCAPE MODE! Using max power + high angle")
            return shot_type, target_x, target_y
        
        # Normal strategy (CONSERVATIVE and SMART)
        if distance < 20:
            shot_type = ShotType.PUTT
            target_x, target_y = hole_x, hole_y
        
        elif distance < 60:
            shot_type = ShotType.CHIP
            target_x, target_y = hole_x, hole_y
        
        elif distance < 120:
            shot_type = ShotType.CHIP  # Use chip for better control
            target_x, target_y = hole_x, hole_y
        
        elif distance < 200:
            shot_type = ShotType.LAYUP
            target_x, target_y = hole_x, hole_y
        
        else:
            shot_type = ShotType.DRIVE
            # Find intermediate waypoint
            target_x, target_y = self._find_waypoint(ball_x, ball_y, hole_x, hole_y, distance)
        
        return shot_type, target_x, target_y
    
    def _find_waypoint(self, ball_x: float, ball_y: float,
                      hole_x: float, hole_y: float, 
                      distance: float) -> Tuple[float, float]:
        """
        Find optimal intermediate waypoint for long shots
        Uses simplified A* over discretized landing zones
        """
        # For very long shots, aim for a point 200-250 units toward hole
        max_shot_distance = 250.0
        
        if distance > max_shot_distance:
            # Calculate waypoint
            direction_x = (hole_x - ball_x) / distance
            direction_y = (hole_y - ball_y) / distance
            
            waypoint_x = ball_x + direction_x * max_shot_distance
            waypoint_y = ball_y + direction_y * max_shot_distance
            
            # Clamp to map bounds
            waypoint_x = max(20, min(self.map_width - 20, waypoint_x))
            waypoint_y = max(20, min(self.map_height - 20, waypoint_y))
            
            return waypoint_x, waypoint_y
        else:
            # Direct shot possible
            return hole_x, hole_y
    
    def search_landing_zones(self, ball_x: float, ball_y: float,
                            hole_x: float, hole_y: float,
                            num_candidates: int = 8) -> List[Tuple[float, float, float]]:
        """
        Generate candidate landing zones in a fan pattern
        
        Returns:
            List of (x, y, score) tuples
        """
        distance = math.sqrt((hole_x - ball_x)**2 + (hole_y - ball_y)**2)
        base_angle = math.atan2(hole_y - ball_y, hole_x - ball_x)
        
        candidates = []
        
        # Generate fan of landing zones
        for i in range(num_candidates):
            # Angle variation
            angle_offset = (i - num_candidates/2) * 0.2  # ±20 degrees spread
            angle = base_angle + angle_offset
            
            # Distance variation (80-100% of max shot)
            distance_factor = 0.8 + (i / num_candidates) * 0.2
            target_distance = min(distance, 250.0) * distance_factor
            
            target_x = ball_x + math.cos(angle) * target_distance
            target_y = ball_y + math.sin(angle) * target_distance
            
            # Clamp to bounds
            target_x = max(20, min(self.map_width - 20, target_x))
            target_y = max(20, min(self.map_height - 20, target_y))
            
            # Score this landing zone
            score = self.surrogate.evaluate_landing_zone(
                target_x, target_y, hole_x, hole_y, 'fairway'
            )
            
            candidates.append((target_x, target_y, score))
        
        # Sort by score (lower is better)
        candidates.sort(key=lambda x: x[2])
        
        return candidates
    
    def get_shot_parameters(self, shot_type: str) -> Dict:
        """Get recommended parameters for shot type"""
        return self.shot_params.get(shot_type, self.shot_params[ShotType.LAYUP])
