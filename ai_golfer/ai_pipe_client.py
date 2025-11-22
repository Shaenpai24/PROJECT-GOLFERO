#!/usr/bin/env python3
"""
AI Pipe Client - Connects Python AI to C game via named pipes
Improved version with REAL MapLoader terrain detection (no more false sand).
"""

import struct
import os
import time
import math
from high_level_planner import HighLevelPlanner
from low_level_optimizer import ShotOptimizer
from map_loader import MapLoader

AI_PIPE = "/tmp/golf_ai_pipe"
STATE_PIPE = "/tmp/golf_state_pipe"


class PipeAIClient:
    """AI client that communicates with C game via pipes"""

    def __init__(self, fast_mode=True):
        self.planner = HighLevelPlanner()
        self.optimizer = ShotOptimizer()
        self.map_loader = MapLoader()
        self.fast_mode = fast_mode
        self.last_distance_moved = 0.0

        print("Waiting for C game to start...")
        while not (os.path.exists(AI_PIPE) and os.path.exists(STATE_PIPE)):
            time.sleep(0.1)

        print("Opening pipes...")
        import fcntl

        ai_fd = os.open(AI_PIPE, os.O_WRONLY | os.O_NONBLOCK)
        self.ai_pipe = os.fdopen(ai_fd, 'wb', buffering=0)

        state_fd = os.open(STATE_PIPE, os.O_RDONLY | os.O_NONBLOCK)
        self.state_pipe = os.fdopen(state_fd, 'rb', buffering=0)

        print("Connected to game!")

    # ------------------------------------------------------------

    def read_game_state(self):
        """Read game state from C engine (exact 40-byte struct)."""
        try:
            fmt = "<8fi??xx"           # EXACT layout: 40 bytes
            expected_size = 40
            data = self.state_pipe.read(expected_size)

            if not data or len(data) < expected_size:
                return None

            values = struct.unpack(fmt, data)

            return {
                'ball_x': values[0],
                'ball_y': values[1],
                'ball_z': values[2],
                'hole_x': values[3],
                'hole_y': values[4],
                'wind_x': values[5],
                'wind_y': values[6],
                'wind_strength': values[7],
                'strokes': values[8],
                'stopped': values[9],
                'won': values[10]
            }

        except BlockingIOError:
            return None
        except Exception:
            return None


    # ------------------------------------------------------------

    def send_shot(self, dirx, diry, angle, power, spinx=0.0, spiny=0.0):
        """Send final shot params to C"""
        data = struct.pack('6f', dirx, diry, angle, power, spinx, spiny)
        self.ai_pipe.write(data)
        self.ai_pipe.flush()
        print(f"  → Sent: dir=({dirx:.3f},{diry:.3f}) angle={angle:.1f}° power={power:.1f}")

    # ------------------------------------------------------------

    def play(self):
        """Main AI loop"""
        print("\n" + "="*60)
        print("🤖 AI GOLFER - Playing via C visualization")
        print("="*60)

        last_ball_pos = None
        no_state_count = 0
        shot_sent = False

        while True:
            state = self.read_game_state()
            if not state:
                no_state_count += 1
                if no_state_count % 50 == 0:
                    print(f"Waiting for game state... ({no_state_count} attempts)")
                time.sleep(0.1)
                continue

            no_state_count = 0

            if state['won']:
                print(f"\n🏆 HOLE IN! Total strokes: {state['strokes']}")
                break

            if not state['stopped']:
                shot_sent = False
                time.sleep(0.1)
                continue

            current_pos = (state['ball_x'], state['ball_y'])

            # Only shoot when ball has stopped AND didn’t just do a micro-jump
            if shot_sent:
                if last_ball_pos is not None:
                    dist_moved = math.dist(current_pos, last_ball_pos)
                    if dist_moved > 1.0:
                        shot_sent = False
                        print(f"Ball moved {dist_moved:.1f}px, ready for next shot")
                time.sleep(0.1)
                continue

            if last_ball_pos is not None:
                dist_moved = math.dist(current_pos, last_ball_pos)
                if dist_moved < 1.0:  # no real movement
                    time.sleep(0.1)
                    continue

            last_ball_pos = current_pos

            ball_x, ball_y = state['ball_x'], state['ball_y']
            hole_x, hole_y = state['hole_x'], state['hole_y']

            distance = math.dist((ball_x, ball_y), (hole_x, hole_y))

            print(f"\n--- Stroke {state['strokes'] + 1} ---")
            print(f"Ball: ({ball_x:.1f}, {ball_y:.1f})")
            print(f"Hole: ({hole_x:.1f}, {hole_y:.1f})")
            print(f"Distance: {distance:.1f} px")

            # ------------------------------------------------------------
            # REAL SAND DETECTION (via MapLoader)
            # ------------------------------------------------------------
            if self.map_loader.is_sand(ball_x, ball_y):
                current_terrain = "sand"
                print("  🏖️ SAND DETECTED BY MAP")
            else:
                current_terrain = "fairway"

            # ------------------------------------------------------------
            # Plan strategy
            # ------------------------------------------------------------
            shot_type, target_x, target_y = self.planner.plan_strategy(
                ball_x, ball_y, hole_x, hole_y,
                terrain_map=self.map_loader,
                current_terrain=current_terrain,
                wind_x=state['wind_x'], wind_y=state['wind_y'], wind_strength=state['wind_strength']
            )


            print(f"Strategy: {shot_type.upper()}")

            # ------------------------------------------------------------
            # Path check
            # ------------------------------------------------------------
            is_clear, hazard_count, sand_count = self.map_loader.check_path_clear(
                ball_x, ball_y, target_x, target_y
            )

            if not is_clear and current_terrain != 'sand':
                print(f"  ⚠️ Path blocked! Hazards={hazard_count}, Sand={sand_count}")

                dx = target_x - ball_x
                dy = target_y - ball_y

                best_target = None
                best_sand = sand_count

                for angle_deg in [15, 30, 45, 60, -15, -30, -45, -60]:
                    a = math.radians(angle_deg)
                    cos_a, sin_a = math.cos(a), math.sin(a)

                    new_dx = dx * cos_a - dy * sin_a
                    new_dy = dx * sin_a + dy * cos_a

                    alt_x = ball_x + new_dx
                    alt_y = ball_y + new_dy

                    clear, h2, s2 = self.map_loader.check_path_clear(
                        ball_x, ball_y, alt_x, alt_y
                    )

                    if clear:
                        best_target = (alt_x, alt_y)
                        print(f"  ↰ Adjusted aim by {abs(angle_deg)}°")
                        break

                    elif s2 < best_sand:
                        best_sand = s2
                        best_target = (alt_x, alt_y)

                if best_target:
                    target_x, target_y = best_target

            # ------------------------------------------------------------
            # Optimizer call
            # ------------------------------------------------------------
            angle_hint = self.planner.get_shot_parameters(shot_type)["angle"]

            if self.fast_mode:
                dirx, diry, angle, power = self.optimizer.quick_optimize(
                    ball_x, ball_y, target_x, target_y, angle_hint,
                    state['wind_x'], state['wind_y'], state['wind_strength'],
                    terrain=current_terrain
                )
                spinx = spiny = 0.0
            else:
                dirx, diry, angle, power, spinx, spiny = self.optimizer.optimize_shot(
                    ball_x, ball_y, target_x, target_y, angle_hint,
                    state['wind_x'], state['wind_y'], state['wind_strength']
                )

            self.send_shot(dirx, diry, angle, power, spinx, spiny)
            shot_sent = True
            time.sleep(0.5)

    # ------------------------------------------------------------

    def close(self):
        self.state_pipe.close()
        self.ai_pipe.close()


def main():
        import argparse
        parser = argparse.ArgumentParser(description="AI Pipe Client")
        parser.add_argument("--slow", action="store_true", help="Use full CMA-ES optimization")
        args = parser.parse_args()

        try:
            client = PipeAIClient(fast_mode=not args.slow)
            client.play()
        except KeyboardInterrupt:
            print("\nStopped by user")
        except Exception as e:
            print(f"\nError: {e}")
            import traceback
            traceback.print_exc()
        finally:
            if 'client' in locals():
                client.close()


if __name__ == "__main__":
    main()
