"""
High-Level Planner - Strategic waypoint selection using MapLoader terrain analysis
Avoids sand, avoids hazards, smart in wind, uses real pixel-based terrain.
"""

import math
from typing import List, Tuple, Optional, Dict
from surrogate_physics import SurrogatePhysics
from map_loader import MapLoader


class ShotType:
    DRIVE = "drive"
    LAYUP = "layup"
    CHIP = "chip"
    LOB = "lob"
    PUTT = "putt"


class HighLevelPlanner:
    def __init__(self, map_width: int = 640, map_height: int = 640):
        self.map_width = map_width
        self.map_height = map_height
        self.surrogate = SurrogatePhysics()
        self.map_loader = MapLoader()   # real terrain queries if caller doesn't pass a map

        # Optimized parameters per shot type
        self.shot_params = {
            ShotType.DRIVE: {"angle": 38.0, "power_range": (80, 150)},
            ShotType.LAYUP: {"angle": 35.0, "power_range": (40, 80)},
            ShotType.CHIP:  {"angle": 30.0, "power_range": (20, 50)},
            ShotType.LOB:   {"angle": 75.0, "power_range": (100, 150)},
            ShotType.PUTT:  {"angle": 5.0,  "power_range": (5, 30)},
        }

    # -------------------------------------------------------------

    def _near_sand(self, x: float, y: float, map_loader: MapLoader) -> bool:
        """Return True if any pixel within ±8px is sand (uses MapLoader)."""
        if map_loader is None:
            return False
        for dx in range(-8, 9):
            for dy in range(-8, 9):
                if map_loader.is_sand(x + dx, y + dy):
                    return True
        return False

    # -------------------------------------------------------------

    def _spiral_find_safe(self, cx: float, cy: float, map_loader: MapLoader,
                          max_radius: float = 240.0, step: float = 12.0) -> Tuple[float, float]:
        """
        Spiral search around (cx,cy) to find nearest point that is not sand/hazard.
        Returns a tuple (tx,ty). If none found within max_radius, returns (cx,cy).
        """
        if map_loader is None:
            return cx, cy

        # concentric rings
        r = step
        while r <= max_radius:
            # sample N points on ring proportional to circumference (clamped)
            samples = max(8, int(2 * math.pi * r / step))
            for i in range(samples):
                a = (i / samples) * 2 * math.pi
                tx = cx + math.cos(a) * r
                ty = cy + math.sin(a) * r

                tx = max(20.0, min(self.map_width - 20.0, tx))
                ty = max(20.0, min(self.map_height - 20.0, ty))

                try:
                    if not map_loader.is_hazard(tx, ty) and not map_loader.is_sand(tx, ty):
                        # also ensure short path to that point isn't full of hazards
                        clear, hcount, scount = map_loader.check_path_clear(cx, cy, tx, ty, num_samples=12)
                        if clear:
                            return tx, ty
                except Exception:
                    # defensive - continue searching
                    continue
            r += step
        return cx, cy

    # -------------------------------------------------------------

    def plan_strategy(self, ball_x: float, ball_y: float,
                        hole_x: float, hole_y: float,
                        terrain_map: Optional[object] = None,   # accept MapLoader instance
                        current_terrain: str = 'fairway',
                        wind_x: float = 0.0, wind_y: float = 0.0,
                        wind_strength: float = 0.0
                        ) -> Tuple[str, float, float]:
        """
        Wind-aware high-level planner that uses a MapLoader-like object (terrain_map)
        to avoid sand/hazards and find safe landing zones.

        terrain_map must implement: is_sand(x,y), is_hazard(x,y), check_path_clear(x1,y1,x2,y2)
        """

        # choose a map_loader to query
        map_loader = terrain_map if terrain_map is not None else self.map_loader

        dx = hole_x - ball_x
        dy = hole_y - ball_y
        distance = math.hypot(dx, dy)

        if distance < 1e-6:
            return ShotType.PUTT, hole_x, hole_y

        # =====================================================
        #  If ball currently in sand -> escape mode (priority)
        # =====================================================
        if current_terrain == "sand" or (map_loader is not None and map_loader.is_sand(ball_x, ball_y)):
            shot_type = ShotType.LOB

            # compute local sand centroid to push away from cluster
            sx = sy = 0.0
            count = 0
            if map_loader is not None:
                for ox in range(-24, 25, 6):
                    for oy in range(-24, 25, 6):
                        tx = ball_x + ox
                        ty = ball_y + oy
                        try:
                            if map_loader.is_sand(tx, ty):
                                sx += tx; sy += ty; count += 1
                        except Exception:
                            pass

            if count > 0:
                cx = sx / count
                cy = sy / count
                # prefer direction away from sand centroid
                ex = ball_x - cx
                ey = ball_y - cy
                ed = math.hypot(ex, ey)
                if ed < 1e-6:
                    # degenerate: nudge toward map center as fallback
                    ex, ey = (self.map_width/2 - ball_x), (self.map_height/2 - ball_y)
                    ed = math.hypot(ex, ey) or 1.0
                ex /= ed; ey /= ed

                # Slightly bias away from wind if wind would push into sand centroid
                wind_dot = wind_x * (cx - ball_x) + wind_y * (cy - ball_y)
                wind_mag = math.hypot(wind_x, wind_y)
                upwind_bias = 0.0
                if wind_mag > 8.0 and wind_dot > 0.0:
                    upwind_bias = -0.35  # push opposite the wind that pushes back to sand

                bx = ex + upwind_bias * wind_x
                by = ey + upwind_bias * wind_y
                bd = math.hypot(bx, by)
                if bd < 1e-6:
                    bx, by = ex, ey
                else:
                    bx /= bd; by /= bd

                # initial escape attempt distance
                escape_base = 100.0
                target_x = ball_x + bx * escape_base
                target_y = ball_y + by * escape_base

                # clamp inside playable area
                target_x = max(20.0, min(self.map_width - 20.0, target_x))
                target_y = max(20.0, min(self.map_height - 20.0, target_y))

                # If landing point is still sand/hazard, spiral-search for nearest safe spot
                try:
                    if map_loader is not None and (map_loader.is_sand(target_x, target_y) or map_loader.is_hazard(target_x, target_y)):
                        target_x, target_y = self._spiral_find_safe(target_x, target_y, map_loader,
                                                                   max_radius=220.0, step=14.0)
                except Exception:
                    # defensive: if queries fail just return hole as fallback
                    return shot_type, hole_x, hole_y

                print("  🏖️ SAND ESCAPE (map-aware): aiming for safe fairway")
                return shot_type, target_x, target_y

            # fallback - no local sand found: lob to hole (rare)
            return shot_type, hole_x, hole_y

        # =====================================================
        #  Short-range rules
        # =====================================================
        if distance < 20:
            return ShotType.PUTT, hole_x, hole_y
        if distance < 120:
            return ShotType.CHIP, hole_x, hole_y
        if distance < 200:
            return ShotType.LAYUP, hole_x, hole_y

        # =====================================================
        #  Long-range: handle high wind and candidate search
        # =====================================================
        # If wind is very strong, be conservative (prefer layup + wider search)
        very_strong_wind = wind_strength > 30.0
        strong_wind = wind_strength > 12.0

        # default direct waypoint
        drive_target_x, drive_target_y = self._find_waypoint(ball_x, ball_y, hole_x, hole_y, distance)

        # if direct path is clear: go for it (still respect very strong wind)
        if map_loader is not None:
            try:
                clear, hazards, sands = map_loader.check_path_clear(ball_x, ball_y, drive_target_x, drive_target_y)
                if clear and not very_strong_wind:
                    return ShotType.DRIVE, drive_target_x, drive_target_y
            except Exception:
                # if check fails, continue to candidate search
                pass

        # Candidate search:
        fan_candidates = 16 if very_strong_wind else (12 if strong_wind else 8)
        candidates = self.search_landing_zones(ball_x, ball_y, hole_x, hole_y,
                                               map_loader=map_loader, num_candidates=fan_candidates)

        if candidates:
            best_x, best_y, score = candidates[0]
            # if the best candidate is still a risky area, and wind is very strong, fallback to a safer close layup
            try:
                if map_loader is not None and (map_loader.is_sand(best_x, best_y) or map_loader.is_hazard(best_x, best_y)):
                    # try to find safe spot near ball
                    safe_x, safe_y = self._spiral_find_safe(ball_x, ball_y, map_loader, max_radius=160.0, step=12.0)
                    return ShotType.LAYUP, safe_x, safe_y
            except Exception:
                pass

            print("  🌬️ Selecting safer landing zone")
            return ShotType.LAYUP, best_x, best_y

        # fallback: direct drive waypoint
        return ShotType.DRIVE, drive_target_x, drive_target_y

    # -------------------------------------------------------------

    def _find_waypoint(self, ball_x: float, ball_y: float,
                       hole_x: float, hole_y: float,
                       distance: float) -> Tuple[float, float]:
        """Drive toward hole, but cap at ~250px."""
        max_shot = 250.0

        if distance > max_shot:
            dir_x = (hole_x - ball_x) / distance
            dir_y = (hole_y - ball_y) / distance

            wx = ball_x + dir_x * max_shot
            wy = ball_y + dir_y * max_shot

            wx = max(20, min(self.map_width - 20, wx))
            wy = max(20, min(self.map_height - 20, wy))

            return wx, wy

        return hole_x, hole_y

    # -------------------------------------------------------------

    def search_landing_zones(self, ball_x: float, ball_y: float,
                                hole_x: float, hole_y: float,
                                map_loader,
                                num_candidates: int = 8) -> List[Tuple[float, float, float]]:
        """
        Generate candidate landing zones in a fan and score with map_loader + surrogate.
        Returns list of (x,y,score) sorted ascending (lower better).
        """
        if map_loader is None:
            map_loader = self.map_loader

        distance = math.hypot(hole_x - ball_x, hole_y - ball_y)
        base_angle = math.atan2(hole_y - ball_y, hole_x - ball_x)

        candidates = []
        for i in range(num_candidates):
            angle_offset = (i - (num_candidates - 1)/2) * (0.2)  # roughly ±20 degrees fan
            angle = base_angle + angle_offset

            dist_factor = 0.75 + (i / max(1, num_candidates)) * 0.25
            target_dist = min(distance, 250.0) * dist_factor

            tx = ball_x + math.cos(angle) * target_dist
            ty = ball_y + math.sin(angle) * target_dist

            tx = max(20.0, min(self.map_width - 20.0, tx))
            ty = max(20.0, min(self.map_height - 20.0, ty))

            # Hard-reject hazards
            try:
                if map_loader.is_hazard(tx, ty):
                    score = 1e6
                elif map_loader.is_sand(tx, ty):
                    # big penalty but not absolute reject (we may still choose if nothing else)
                    score = 5e4 + target_dist
                else:
                    # surrogate score: prefer closer to hole and stable landings
                    score = self.surrogate.evaluate_landing_zone(tx, ty, hole_x, hole_y, 'fairway')
                    # soft penalty for proximity to sand
                    near_sand = False
                    for dx in range(-12, 13, 4):
                        for dy in range(-12, 13, 4):
                            if map_loader.is_sand(tx + dx, ty + dy):
                                near_sand = True
                                break
                        if near_sand:
                            break
                    if near_sand:
                        score += 400.0
            except Exception:
                score = self.surrogate.evaluate_landing_zone(tx, ty, hole_x, hole_y, 'fairway')

            candidates.append((tx, ty, score))

        candidates.sort(key=lambda x: x[2])
        return candidates

    # -------------------------------------------------------------

    def get_shot_parameters(self, shot_type: str):
        return self.shot_params.get(shot_type, self.shot_params[ShotType.LAYUP])
