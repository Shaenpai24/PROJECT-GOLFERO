"""
Map Loader - Load and analyze golf course terrain
"""
from PIL import Image
import numpy as np


class MapLoader:
    """Load and query terrain from golf_map.png"""
    
    def __init__(self, map_path="golf_map.png"):
        try:
            self.img = Image.open(map_path).convert('RGB')
            self.width, self.height = self.img.size
            self.pixels = np.array(self.img)
            print(f"Loaded map: {self.width}x{self.height}")
        except Exception as e:
            print(f"Could not load map: {e}")
            # Create dummy map
            self.width, self.height = 32, 32
            self.pixels = np.zeros((32, 32, 3), dtype=np.uint8)
            self.pixels[:, :] = [100, 200, 100]  # Green fairway
    
    def is_sand(self, x, y, screen_width=640, screen_height=640):
        """Check if position (x,y) in screen coordinates is sand"""
        # Convert screen coords to map coords
        map_x = int((x / screen_width) * self.width)
        map_y = int((y / screen_height) * self.height)
        
        # Clamp to bounds
        map_x = max(0, min(self.width - 1, map_x))
        map_y = max(0, min(self.height - 1, map_y))
        
        # Get pixel color
        r, g, b = self.pixels[map_y, map_x]
        
        # Sand detection (from C code)
        # R > 130 && G > 130 && B < 100 && abs(R - G) < 30
        if r > 130 and g > 130 and b < 100 and abs(int(r) - int(g)) < 30:
            return True
        return False
    
    def is_hazard(self, x, y, screen_width=640, screen_height=640):
        """Check if position is water/hazard"""
        map_x = int((x / screen_width) * self.width)
        map_y = int((y / screen_height) * self.height)
        
        map_x = max(0, min(self.width - 1, map_x))
        map_y = max(0, min(self.height - 1, map_y))
        
        r, g, b = self.pixels[map_y, map_x]
        
        # Water/hazard: B > 120 && B > G + 20 && B > R + 20
        if b > 120 and b > g + 20 and b > r + 20:
            return True
        return False
    
    def check_path_clear(self, x1, y1, x2, y2, num_samples=20):
        """
        Check if path from (x1,y1) to (x2,y2) avoids sand/hazards
        Returns: (is_clear, hazard_count, sand_count)
        """
        hazard_count = 0
        sand_count = 0
        
        for i in range(num_samples):
            t = i / (num_samples - 1) if num_samples > 1 else 0
            x = x1 + t * (x2 - x1)
            y = y1 + t * (y2 - y1)
            
            if self.is_hazard(x, y):
                hazard_count += 1
            elif self.is_sand(x, y):
                sand_count += 1
        
        # Stricter: no hazards, minimal sand
        is_clear = (hazard_count == 0 and sand_count < 2)
        return is_clear, hazard_count, sand_count
