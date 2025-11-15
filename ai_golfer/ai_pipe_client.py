#!/usr/bin/env python3
"""
AI Pipe Client - Connects Python AI to C game via named pipes
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
        # Wait for pipes to be created
        while not (os.path.exists(AI_PIPE) and os.path.exists(STATE_PIPE)):
            time.sleep(0.1)
        
        print("Opening pipes...")
        # Open pipes using os.open with non-blocking flag
        import fcntl
        
        # Open for writing (AI commands to C)
        ai_fd = os.open(AI_PIPE, os.O_WRONLY | os.O_NONBLOCK)
        self.ai_pipe = os.fdopen(ai_fd, 'wb', buffering=0)
        
        # Open for reading (game state from C)
        state_fd = os.open(STATE_PIPE, os.O_RDONLY | os.O_NONBLOCK)
        self.state_pipe = os.fdopen(state_fd, 'rb', buffering=0)
        
        print("Connected to game!")
    
    def read_game_state(self):
        """Read game state from C"""
        try:
            # GameStateMsg struct: 8 floats + 1 int + 2 bools (with padding)
            # float ball_x, ball_y, ball_z, hole_x, hole_y, wind_x, wind_y, wind_strength
            # int strokes, bool stopped, bool won
            expected_size = 8*4 + 4 + 1 + 1 + 2  # 8 floats + 1 int + 2 bools + 2 padding = 48 bytes
            data = self.state_pipe.read(expected_size)
            if not data or len(data) < expected_size:
                return None
            
            # Unpack: 8 floats, 1 int, 2 bools with padding
            values = struct.unpack('8fi??xx', data)
            
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
        except Exception as e:
            # print(f"Error reading state: {e}")
            return None
    
    def send_shot(self, dirx, diry, angle, power, spinx=0.0, spiny=0.0):
        """Send shot command to C"""
        # AICommand struct: 6 floats
        data = struct.pack('6f', dirx, diry, angle, power, spinx, spiny)
        self.ai_pipe.write(data)
        self.ai_pipe.flush()
        print(f"  → Sent: dir=({dirx:.3f},{diry:.3f}) angle={angle:.1f}° power={power:.1f}")
    
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
            
            no_state_count = 0  # Reset counter when we get state
            
            if state['won']:
                print(f"\n🏆 HOLE IN! Total strokes: {state['strokes']}")
                break
            
            if not state['stopped']:
                shot_sent = False  # Ball is moving, reset flag
                time.sleep(0.1)
                continue
            
            # Ball has stopped - check if we need to take a shot
            current_pos = (state['ball_x'], state['ball_y'])
            
            # Only shoot if ball position changed (or first shot) and we haven't sent a shot yet
            if shot_sent:
                # Check if ball actually moved since last shot
                if last_ball_pos is not None:
                    dist_moved = math.sqrt((current_pos[0] - last_ball_pos[0])**2 + 
                                          (current_pos[1] - last_ball_pos[1])**2)
                    if dist_moved > 1.0:
                        # Ball moved! Ready for next shot
                        shot_sent = False
                        print(f"Ball moved {dist_moved:.1f}px, ready for next shot")
                time.sleep(0.1)
                continue
                
            if last_ball_pos is not None:
                # Check if ball actually moved
                dist_moved = math.sqrt((current_pos[0] - last_ball_pos[0])**2 + 
                                      (current_pos[1] - last_ball_pos[1])**2)
                if dist_moved < 1.0:  # Ball didn't move, skip
                    time.sleep(0.1)
                    continue
            
            last_ball_pos = current_pos
            
            ball_x, ball_y = state['ball_x'], state['ball_y']
            hole_x, hole_y = state['hole_x'], state['hole_y']
            
            distance = math.sqrt((hole_x - ball_x)**2 + (hole_y - ball_y)**2)
            
            print(f"\n--- Stroke {state['strokes'] + 1} ---")
            print(f"Ball: ({ball_x:.1f}, {ball_y:.1f})")
            print(f"Hole: ({hole_x:.1f}, {hole_y:.1f})")
            print(f"Distance: {distance:.1f} px")
            
            # Calculate distance moved THIS shot (before planning)
            if last_ball_pos is not None:
                self.last_distance_moved = math.sqrt((current_pos[0] - last_ball_pos[0])**2 + 
                                                     (current_pos[1] - last_ball_pos[1])**2)
            else:
                self.last_distance_moved = 0.0
            
            # Smart sand trap detection
            current_terrain = 'fairway'
            if self.last_distance_moved > 0 and self.last_distance_moved < 50.0:
                # If ball moved less than 50px, it's sand!
                current_terrain = 'sand'
                print(f"  🏖️  SAND DETECTED! Ball only moved {self.last_distance_moved:.1f}px")
            
            # Plan shot with terrain awareness
            shot_type, target_x, target_y = self.planner.plan_strategy(
                ball_x, ball_y, hole_x, hole_y,
                current_terrain=current_terrain
            )
            
            print(f"Strategy: {shot_type.upper()}")
            
            # Check if direct path is clear
            is_clear, hazard_count, sand_count = self.map_loader.check_path_clear(
                ball_x, ball_y, target_x, target_y
            )
            
            if not is_clear and current_terrain != 'sand':
                print(f"  ⚠️  Path blocked! Hazards: {hazard_count}, Sand: {sand_count}")
                # Try to find alternate target that avoids obstacles
                # Try multiple angles: 20, 40, 60 degrees left and right
                dx = target_x - ball_x
                dy = target_y - ball_y
                dist = math.sqrt(dx**2 + dy**2)
                
                best_target = None
                best_sand_count = sand_count
                
                for angle_deg in [15, 30, 45, 60, -15, -30, -45, -60]:
                    angle_offset = math.radians(angle_deg)
                    cos_a, sin_a = math.cos(angle_offset), math.sin(angle_offset)
                    new_dx = dx * cos_a - dy * sin_a
                    new_dy = dx * sin_a + dy * cos_a
                    alt_target_x = ball_x + new_dx
                    alt_target_y = ball_y + new_dy
                    
                    is_clear_alt, h_count, s_count = self.map_loader.check_path_clear(
                        ball_x, ball_y, alt_target_x, alt_target_y
                    )
                    
                    if is_clear_alt:
                        best_target = (alt_target_x, alt_target_y)
                        direction = "LEFT" if angle_deg > 0 else "RIGHT"
                        print(f"  ↰  Adjusted aim {direction} ({abs(angle_deg)}°) to avoid obstacles")
                        break
                    elif s_count < best_sand_count:
                        # At least less sand
                        best_target = (alt_target_x, alt_target_y)
                        best_sand_count = s_count
                
                if best_target:
                    target_x, target_y = best_target
            
            # Optimize
            shot_params = self.planner.get_shot_parameters(shot_type)
            angle_hint = shot_params["angle"]
            
            if self.fast_mode:
                dirx, diry, angle, power = self.optimizer.quick_optimize(
                    ball_x, ball_y, target_x, target_y, angle_hint,
                    state['wind_x'], state['wind_y'], state['wind_strength'],
                    terrain=current_terrain
                )
                spinx, spiny = 0.0, 0.0
            else:
                dirx, diry, angle, power, spinx, spiny = self.optimizer.optimize_shot(
                    ball_x, ball_y, target_x, target_y, angle_hint,
                    state['wind_x'], state['wind_y'], state['wind_strength']
                )
            
            # Send to C game
            self.send_shot(dirx, diry, angle, power, spinx, spiny)
            shot_sent = True  # Mark that we sent a shot
            
            time.sleep(0.5)  # Brief pause before next check
    
    def close(self):
        """Clean up"""
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
        print("\n\nStopped by user")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'client' in locals():
            client.close()


if __name__ == "__main__":
    main()
