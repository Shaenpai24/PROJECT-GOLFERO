# === surrogate_physics.py (FINAL CLEAN VERSION) ===

import math
import numpy as np

class SurrogatePhysics:
    def __init__(self):
        self.GRAVITY = 800.0
        self.DT = 0.016
        self.LAUNCH_SCALE = 4.0
        self.Z_SCALE = 0.6
        self.AIR_DRAG = 1.6
        self.STOP_SPEED = 2.0
        self.MAX_STEPS = 900
        self.WIND_SMOOTHNESS = 0.25
        self.GROUND_WIND_FACTOR = 0.08
        self.SPIN_AIR_DAMP = 0.996
        self.SPIN_GROUND_DAMP = 0.985

        self.wind_smooth = 0.0

        # match C physics
        self.terrain_damping = {
            "fairway": 0.96,
            "rough": 0.80,
            "sand": 0.45,
            "smooth": 0.98,
            "water": 0.0,
            "forest": 0.40,
        }

        self.terrain_bounce = {
            "fairway": 0.60,
            "rough": 0.55,
            "sand": 0.05,
            "smooth": 0.75,
            "water": 0.0,
            "forest": 0.0,
        }

    # --------------------------------------------------------------

    def simulate_shot(self, sx, sy, dirx, diry, angle, power,
                      wind_x, wind_y, wind_strength,
                      spinx, spiny, terrain):

        # --- normalize direction ---
        d = math.hypot(dirx, diry)
        if d < 1e-6:
            dirx, diry = 0.0, -1.0
        else:
            dirx /= d
            diry /= d

        # --- initial velocity (matches C) ---
        ang = math.radians(angle)
        launch = power * self.LAUNCH_SCALE
        horiz = launch * math.cos(ang)

        vx = horiz * dirx
        vy = horiz * diry
        vz = launch * math.sin(ang) * self.Z_SCALE

        x, y, z = sx, sy, 0.0
        self.wind_smooth = 0.0

        for _ in range(self.MAX_STEPS):

            # gravity
            vz -= self.GRAVITY * self.DT

            # integrate pos
            x += vx * self.DT
            y += vy * self.DT
            z += vz * self.DT

            airborne = z > 1.0

            # update smoothed wind
            self.wind_smooth += (wind_strength - self.wind_smooth) * self.WIND_SMOOTHNESS

            # apply wind
            if airborne:
                vx += wind_x * self.wind_smooth * self.DT
                vy += wind_y * self.wind_smooth * self.DT

                # magnus
                mx = -spiny * vy * 0.0012
                my =  spiny * vx * 0.0012
                mx = max(-10.0, min(10.0, mx))
                my = max(-10.0, min(10.0, my))
                vx += mx
                vy += my

                # drag
                vx -= vx * self.AIR_DRAG * self.DT
                vy -= vy * self.AIR_DRAG * self.DT

                spinx *= self.SPIN_AIR_DAMP
                spiny *= self.SPIN_AIR_DAMP

            else:
                vx += wind_x * self.wind_smooth * self.GROUND_WIND_FACTOR * self.DT
                vy += wind_y * self.wind_smooth * self.GROUND_WIND_FACTOR * self.DT

                spinx *= self.SPIN_GROUND_DAMP
                spiny *= self.SPIN_GROUND_DAMP

            # ground collision
            if z <= 0:
                z = 0
                if abs(vz) > 10 and self.terrain_bounce.get(terrain, 0) > 0.01:
                    vz = -vz * self.terrain_bounce.get(terrain, 0)
                else:
                    vz = 0

                damp = self.terrain_damping.get(terrain, 0.96)
                vx *= damp
                vy *= damp

            # stop
            if math.hypot(vx, vy) < self.STOP_SPEED and z < 0.1 and abs(vz) < 0.2:
                break

        return x, y, {"terrain": terrain}

    # --------------------------------------------------------------

    def evaluate_landing_zone(self, x, y, hx, hy, terrain):
        base = math.hypot(x - hx, y - hy)
        penalty = {
            "fairway": 0, "smooth": -10,
            "rough": 20, "sand": 50,
            "water": 1000, "forest": 1000
        }.get(terrain, 0)
        return base + penalty
