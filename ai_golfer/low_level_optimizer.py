#!/usr/bin/env python3
"""
Low-Level Optimizer - Wind-aware CMA-ES based shot parameter optimization
Robust, hazard-penalizing, stable optimizer for your golf AI.
"""

import math
import numpy as np
from typing import Tuple
from surrogate_physics import SurrogatePhysics


class ShotOptimizer:
    def __init__(self):
        self.surrogate = SurrogatePhysics()
        self.max_evaluations = 200       # CMA-ES budget
        self.population_size = 20        # CMA-ES population

    # ----------------------------------------------------------------------
    #   PUBLIC API
    # ----------------------------------------------------------------------

    def optimize_shot(self, ball_x: float, ball_y: float,
                      target_x: float, target_y: float,
                      angle_hint: float = 45.0,
                      wind_x: float = 0.0, wind_y: float = 0.0, wind_strength: float = 0.0,
                      terrain: str = 'fairway') -> Tuple[float, float, float, float, float, float]:
        """
        Full CMA-ES optimization wrapper.
        Returns (dirx, diry, angle, power, spinx, spiny)
        """
        dx = target_x - ball_x
        dy = target_y - ball_y
        distance = math.hypot(dx, dy)

        if distance < 1e-6:
            return 0.0, -1.0, 45.0, 0.0, 0.0, 0.0

        init_dirx = dx / distance
        init_diry = dy / distance
        init_power = min(distance / 8.0, 150.0)

        best_params, best_score = self._cmaes_optimize(
            ball_x, ball_y, target_x, target_y,
            init_dirx, init_diry, angle_hint, init_power,
            wind_x, wind_y, wind_strength, terrain
        )

        dirx, diry, angle, power, spinx, spiny = best_params

        print(
            f"  CMA-ES: dist={distance:.1f} "
            f"angle={angle:.1f}° power={power:.1f} "
            f"error={best_score:.1f}"
        )

        return dirx, diry, angle, power, spinx, spiny

    # ----------------------------------------------------------------------
    #   FULL CMA-ES OPTIMIZATION
    # ----------------------------------------------------------------------

    def _cmaes_optimize(self, ball_x, ball_y, target_x, target_y,
                        init_dirx, init_diry, init_angle, init_power,
                        wind_x, wind_y, wind_strength, terrain):

        init_dir_angle = math.atan2(init_diry, init_dirx)

        mean = np.array([
            init_dir_angle,    # 0 direction (radians)
            init_angle,        # 1 launch angle (degrees)
            init_power,        # 2 power
            0.0,               # 3 spinx
            0.0                # 4 spiny
        ], dtype=float)

        sigma = np.array([0.25, 8.0, 20.0, 1.5, 1.5], dtype=float)

        best_params = mean.copy()
        best_score = float("inf")

        # number of generations
        gens = max(1, self.max_evaluations // self.population_size)

        for gen in range(gens):

            population = []
            scores = []

            for _ in range(self.population_size):
                cand = mean + sigma * np.random.randn(5)

                # clamp sensible ranges
                cand[1] = np.clip(cand[1], 0.0, 75.0)    # angle degrees
                cand[2] = np.clip(cand[2], 5.0, 150.0)   # power
                cand[3] = np.clip(cand[3], -10.0, 10.0)  # spinx
                cand[4] = np.clip(cand[4], -10.0, 10.0)  # spiny

                score = self._evaluate_shot(
                    ball_x, ball_y, target_x, target_y,
                    cand, wind_x, wind_y, wind_strength, terrain
                )

                population.append(cand)
                scores.append(score)

                if score < best_score:
                    best_score = score
                    best_params = cand.copy()

            # keep best 50% as elite
            elite_idx = np.argsort(scores)[: max(1, self.population_size // 2)]
            mean = np.mean([population[i] for i in elite_idx], axis=0)

            # shrink exploration
            sigma *= 0.92

            # early stop
            if best_score < 4.0:
                break

        # convert best params to output format
        dir_angle = best_params[0]
        dirx = math.cos(dir_angle)
        diry = math.sin(dir_angle)
        return (
            np.array([dirx, diry, best_params[1], best_params[2], best_params[3], best_params[4]], dtype=float),
            best_score
        )

    # ----------------------------------------------------------------------
    #   SHOT EVALUATION (ROBUST, MULTI-SAMPLE, HAZARD-PENALIZING)
    # ----------------------------------------------------------------------

    def _evaluate_shot(self, ball_x, ball_y, target_x, target_y,
                       params, wind_x, wind_y, wind_strength, terrain):

        dir_ang = float(params[0])
        dirx = math.cos(dir_ang)
        diry = math.sin(dir_ang)
        angle = float(params[1])
        power = float(params[2])
        spinx = float(params[3])
        spiny = float(params[4])

        K = 5  # wind samples (trade-off accuracy vs cost)
        errors = []
        sand_hits = 0
        water_hits = 0

        for _ in range(K):
            wx = wind_x + np.random.randn() * 0.15 * wind_strength
            wy = wind_y + np.random.randn() * 0.15 * wind_strength

            final_x, final_y, meta = self.surrogate.simulate_shot(
                ball_x, ball_y,
                dirx, diry,
                angle, power,
                wx, wy, wind_strength,
                spinx, spiny,
                terrain
            )

            err = math.hypot(final_x - target_x, final_y - target_y)
            errors.append(err)

            # hazards detection using meta dict (surrogate must return meta)
            if isinstance(meta, dict):
                t = meta.get("terrain", None)
                if t == "sand":
                    sand_hits += 1
                if t == "water":
                    water_hits += 1

        mean_error = float(np.mean(errors))
        var_penalty = float(np.var(errors)) * 6.0

        sand_penalty = sand_hits * 2000.0
        water_penalty = water_hits * 5000.0

        return mean_error + var_penalty + sand_penalty + water_penalty

    # ----------------------------------------------------------------------
    #   FAST MODE: DRIFT-COMPENSATION
    # ----------------------------------------------------------------------

    def quick_optimize(self, ball_x, ball_y,
                       target_x, target_y,
                       angle_hint=45.0,
                       wind_x=0.0, wind_y=0.0, wind_strength=0.0,
                       terrain='fairway'):

        dx = target_x - ball_x
        dy = target_y - ball_y
        distance = math.hypot(dx, dy)

        if distance < 1e-6:
            return 0.0, -1.0, 45.0, 0.0

        # ------------------------------------------------------------------
        # SAFE SAND ESCAPE — preserve planner's direction, DO NOT aim to hole
        # ------------------------------------------------------------------
        if terrain == "sand":
            angle = 75.0
            power = 150.0

            # escape direction = exact target vector from planner
            dirx = dx / distance
            diry = dy / distance

            drift_x, drift_y = self._estimate_drift(
                ball_x, ball_y, dirx, diry,
                angle, power,
                wind_x, wind_y, wind_strength,
                terrain,
                samples=5,
                target_x=target_x,
                target_y=target_y
            )

            # compensate but clamp hazardous compensation
            comp_tx = target_x - drift_x
            comp_ty = target_y - drift_y
            cdx = comp_tx - ball_x
            cdy = comp_ty - ball_y
            cd = math.hypot(cdx, cdy)

            if cd > 1e-6:
                ndx = cdx / cd
                ndy = cdy / cd

                # SAFETY GUARD 1: if wind pushes compensation TOWARD sand/hazard → reject drift
                unsafe = False
                for t in np.linspace(0, 1, 6):
                    sx = ball_x + ndx * cd * t
                    sy = ball_y + ndy * cd * t
                    # use a realistic simulate_shot check from that intermediate point
                    fx, fy, meta = self.surrogate.simulate_shot(
                        sx, sy,
                        ndx, ndy,
                        angle, power,
                        wind_x, wind_y, wind_strength,
                        0.0, 0.0,
                        terrain
                    )
                    if isinstance(meta, dict) and (meta.get("terrain") in ("sand", "water")):
                        unsafe = True
                        break

                if not unsafe:
                    dirx, diry = ndx, ndy  # safe to use wind-corrected direction

            print("    💥 SAFE SAND ESCAPE")
            return dirx, diry, angle, power

        # ------------------------------------------------------------------
        # NORMAL SHOTS
        # ------------------------------------------------------------------
        # basic distance-based parameters
        if distance < 10:
            power = distance * 0.3; angle = 2.0
        elif distance < 20:
            power = distance * 0.35; angle = 5.0
        elif distance < 40:
            power = distance * 0.45; angle = 10.0
        elif distance < 70:
            power = distance * 0.6; angle = 18.0
        elif distance < 120:
            power = distance * 0.85; angle = 28.0
        elif distance < 200:
            power = distance * 0.75; angle = 35.0
        else:
            power = min(distance * 0.55, 150.0)
            angle = 38.0

        dirx = dx / distance
        diry = dy / distance

        # ------------------------------------------------------------------
        # WIND COMPENSATION — **SAFETY CHECK TO AVOID SAND**
        # ------------------------------------------------------------------
        if wind_strength > 0.1:

            drift_x, drift_y = self._estimate_drift(
                ball_x, ball_y, dirx, diry,
                angle, power,
                wind_x, wind_y, wind_strength,
                terrain,
                samples=5,
                target_x=target_x,
                target_y=target_y
            )

            comp_tx = target_x - 0.5 * drift_x
            comp_ty = target_y - 0.5 * drift_y
            cdx = comp_tx - ball_x
            cdy = comp_ty - ball_y
            cd = math.hypot(cdx, cdy)

            if cd > 1e-6:
                ndx = cdx / cd
                ndy = cdy / cd

                # SAFETY GUARD 2: ensure compensated direction does NOT cross sand
                safe = True
                for t in np.linspace(0, 1, 8):
                    sx = ball_x + ndx * cd * t
                    sy = ball_y + ndy * cd * t
                    fx, fy, meta = self.surrogate.simulate_shot(
                        sx, sy,
                        ndx, ndy,
                        angle, power,
                        wind_x, wind_y, wind_strength,
                        0.0, 0.0,
                        terrain
                    )
                    if isinstance(meta, dict) and (meta.get("terrain") in ("sand", "water")):
                        safe = False
                        break

                if safe:
                    dirx, diry = ndx, ndy

            print("    🌬️ SAFE WIND COMPENSATION")

        return dirx, diry, angle, power

    # ----------------------------------------------------------------------

    def _estimate_drift(self, ball_x, ball_y, dirx, diry,
                        angle, power,
                        wind_x, wind_y, wind_strength,
                        terrain,
                        samples=6,
                        target_x=None, target_y=None):

        if target_x is None or target_y is None:
            raise ValueError("target_x and target_y must be provided.")

        drifts = []

        for _ in range(samples):
            wx = wind_x + np.random.randn() * 0.2 * wind_strength
            wy = wind_y + np.random.randn() * 0.2 * wind_strength

            fx, fy, meta = self.surrogate.simulate_shot(
                ball_x, ball_y,
                dirx, diry,
                angle, power,
                wx, wy, wind_strength,
                0.0, 0.0,
                terrain
            )
            drifts.append((fx - target_x, fy - target_y))

        avg_dx = sum(d[0] for d in drifts) / samples
        avg_dy = sum(d[1] for d in drifts) / samples

        return avg_dx, avg_dy
