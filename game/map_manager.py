import pygame
import pytmx


class MapManager:
    def __init__(self, map_path):
        self.tmx_data = pytmx.load_pygame(map_path)
        self.tile_width = self.tmx_data.tilewidth
        self.tile_height = self.tmx_data.tileheight
        self.map_width = self.tmx_data.width
        self.map_height = self.tmx_data.height
     
        # Create a surface for the entire map
        self.map_surface = pygame.Surface((
            self.map_width * self.tile_width,
            self.map_height * self.tile_height
        ))
        self.map_surface.fill((0, 0, 0))  # Black background
      
        # Render the map once
        self._render_map()
    
    def _render_map(self):
        # Get the first layer (assuming it's the ground layer)
        layer = self.tmx_data.get_layer_by_name("Tile Layer 1")
        
        # Render each tile
        for x, y, tile in layer.tiles():
            if tile:
                self.map_surface.blit(
                    tile,
                    (x * self.tile_width, y * self.tile_height)
                )
        
    def draw(self, screen, camera_x=0, camera_y=0):
        # Draw the map surface with camera offset
        screen.blit(self.map_surface, (-camera_x, -camera_y))

    def get_map_size(self):
        return (
            self.map_width * self.tile_width,
            self.map_height * self.tile_height
        )
