import pygame
import os
from enum import Enum


class VehicleType(Enum):
    TANK = "tank"
    # Future vehicle types can be added here
    # CAR = "car"
    # HELICOPTER = "helicopter"


class VehicleDirection(Enum):
    FRONT = "front"
    BACK = "back"
    LEFT = "left"
    RIGHT = "right"


class Vehicle:
    def __init__(self, x, y, vehicle_type, map_width, map_height):
        self.x = x
        self.y = y
        self.vehicle_type = vehicle_type
        self.direction = VehicleDirection.FRONT
        self.speed = 3  # Base speed for vehicles
        self.occupied = False  # Whether a player is inside
        self.player_inside = None  # Reference to player inside
        self.map_width = map_width
        self.map_height = map_height
        self.health = 100
        self.max_health = 100
        self.display_health = 100  # For animation
        self.show_damaged = False  # Flag to show damage animation
        self.damage_timer = 0  # Timer for showing the health bar depleting
        self.images = {}
        self.current_image = None
        self.load_images()
        self.interaction_distance = 100  # Distance for player to interact with vehicle
        self.hitbox_width = 0
        self.hitbox_height = 0
        self.player_nearby = False

    def load_images(self):
        # Base method to be overridden by specific vehicle types
        pass

    def update(self, keys=None):
        # Base update method to be overridden
        pass

    def is_near_player(self, player_x, player_y):
        # Check if player is close enough to enter the vehicle
        dx = abs(self.x - player_x)
        dy = abs(self.y - player_y)
        return dx < self.interaction_distance and dy < self.interaction_distance

    def enter_vehicle(self, player):
        if not self.occupied and self.is_near_player(player.x, player.y):
            self.occupied = True
            self.player_inside = player
            # Store player's position before entering
            player.prev_x = player.x
            player.prev_y = player.y
            # Hide the player (handled in client.py)
            return True
        return False

    def exit_vehicle(self):
        if self.occupied and self.player_inside:
            # Position player near the vehicle
            exit_offset = 50  # Distance to place player from vehicle when exiting
            
            if self.direction == VehicleDirection.LEFT:
                exit_x = self.x - exit_offset
                exit_y = self.y
            elif self.direction == VehicleDirection.RIGHT:
                exit_x = self.x + exit_offset
                exit_y = self.y
            elif self.direction == VehicleDirection.BACK:
                exit_x = self.x
                exit_y = self.y - exit_offset
            else:  # FRONT
                exit_x = self.x
                exit_y = self.y + exit_offset
            
            # Ensure player is within map bounds
            exit_x = max(0, min(exit_x, self.map_width - 50))
            exit_y = max(0, min(exit_y, self.map_height - 50))
            
            # Update player position
            self.player_inside.x = exit_x
            self.player_inside.y = exit_y
            
            player = self.player_inside
            self.occupied = False
            self.player_inside = None
            return player
        
        return None

    def draw_health_bar(self, screen, x, y):
        # Health bar dimensions
        bar_width = 60  # Wider bar
        bar_height = 8  # Taller bar for better visibility
        
        # Update display health for smooth animation
        if self.damage_timer > 0:
            self.damage_timer -= 1
            
            # Gradually decrease display health to match actual health
            if self.display_health > self.health:
                self.display_health -= (self.display_health - self.health) / (self.damage_timer + 1)
                if abs(self.display_health - self.health) < 0.1:
                    self.display_health = self.health
            
            # Reset timer when done
            if self.damage_timer <= 0 or self.display_health <= self.health:
                self.show_damaged = False
                self.display_health = self.health
        
        # Calculate health percentage based on display health
        health_percentage = self.display_health / self.max_health
        
        # Add a black outline for better visibility
        pygame.draw.rect(
            screen,
            (0, 0, 0),
            (x - 2, y - 17, bar_width + 4, bar_height + 4)
        )
        
        # Draw background (red)
        pygame.draw.rect(
            screen,
            (255, 0, 0),
            (x, y - 15, bar_width, bar_height)
        )
        
        # Choose color based on health percentage (green -> yellow -> red gradient)
        if health_percentage > 0.6:
            color = (0, 255, 0)  # Green for high health
        elif health_percentage > 0.3:
            color = (255, 255, 0)  # Yellow for medium health
        else:
            color = (255, 165, 0)  # Orange for low health
        
        # Draw foreground proportional to health
        pygame.draw.rect(
            screen,
            color,
            (x, y - 15, int(bar_width * health_percentage), bar_height)
        )
        
        # Show health value when tank is being damaged
        if self.show_damaged:
            font = pygame.font.Font(None, 20)
            health_text = font.render(f"{int(self.display_health)}/{self.max_health}", True, (255, 255, 255))
            screen.blit(health_text, (x + bar_width + 5, y - 17))

    def draw(self, screen, camera_x, camera_y):
        if self.current_image:
            draw_x = self.x - camera_x - self.current_image.get_width() // 2
            draw_y = self.y - camera_y - self.current_image.get_height() // 2
            screen.blit(self.current_image, (draw_x, draw_y))
            
            # Draw health bar
            self.draw_health_bar(screen, draw_x + self.current_image.get_width() // 2 - 25, draw_y)
            
            # Draw text indicating status
            font = pygame.font.Font(None, 24)
            if self.occupied:
                text = font.render("Occupied", True, (255, 0, 0))
                screen.blit(text, (draw_x + self.current_image.get_width() // 2 - text.get_width() // 2, 
                                  draw_y - 30))
            # Draw "Press E to Enter" text if player is nearby but not inside
            elif self.player_nearby:
                text = font.render("Press E to Enter", True, (255, 255, 255))
                screen.blit(text, (draw_x + self.current_image.get_width() // 2 - text.get_width() // 2, 
                                  draw_y - 30))

    def take_damage(self, damage):
        """Applies damage to the vehicle and returns whether it was destroyed"""
        old_health = self.health
        self.health = max(0, self.health - damage)
        
        # Initialize damage animation
        self.show_damaged = True
        self.damage_timer = 40  # Show health change for 40 frames (slow depletion)
        
        return self.health <= 0


class Tank(Vehicle):
    def __init__(self, x, y, map_width, map_height):
        super().__init__(x, y, VehicleType.TANK, map_width, map_height)
        self.speed = 2  # Tanks are slower
        self.rotation_speed = 2  # Slow rotation
        self.damage = 20  # High damage
        self.shoot_cooldown = 1000  # Longer cooldown between shots (in milliseconds)
        self.last_shot_time = 0
        self.player_nearby = False  # Flag for rendering "Press E to Enter" text

    def load_images(self):
        # Load tank images for each direction
        try:
            # Get the absolute path of the current file
            current_file_path = os.path.abspath(__file__)
            # Go up two directories to reach the multiplayer directory
            multiplayer_dir = os.path.dirname(os.path.dirname(current_file_path))
            # Construct the path to the assets directory
            base_path = os.path.join(multiplayer_dir, 'assets', 'vehicules')
            
            # Load tank images for different directions
            self.images[VehicleDirection.FRONT] = pygame.image.load(os.path.join(base_path, "tank_1.png")).convert_alpha()
            self.images[VehicleDirection.BACK] = pygame.image.load(os.path.join(base_path, "tank_2.png")).convert_alpha()
            self.images[VehicleDirection.LEFT] = pygame.image.load(os.path.join(base_path, "tank_3.png")).convert_alpha()
            self.images[VehicleDirection.RIGHT] = pygame.image.load(os.path.join(base_path, "tank_4.png")).convert_alpha()
            
            # Scale down the images if needed
            scale_factor = 0.15  # Adjust as needed
            for direction in self.images:
                original = self.images[direction]
                new_size = (int(original.get_width() * scale_factor), 
                            int(original.get_height() * scale_factor))
                self.images[direction] = pygame.transform.scale(original, new_size)
                # Set black as the transparent color
                self.images[direction].set_colorkey((0, 0, 0))
            
            # Set initial image
            self.current_image = self.images[VehicleDirection.FRONT]
            
            # Set hitbox dimensions based on the image size
            self.hitbox_width = self.current_image.get_width()
            self.hitbox_height = self.current_image.get_height()
            
        except Exception as e:
            print(f"Error loading tank images: {str(e)}")

    def update(self, keys=None):
        if self.occupied and keys:
            # Handle tank movement
            old_x, old_y = self.x, self.y
            
            if keys[pygame.K_LEFT]:
                self.direction = VehicleDirection.LEFT
                self.x -= self.speed
            elif keys[pygame.K_RIGHT]:
                self.direction = VehicleDirection.RIGHT
                self.x += self.speed
            elif keys[pygame.K_UP]:
                self.direction = VehicleDirection.BACK
                self.y -= self.speed
            elif keys[pygame.K_DOWN]:
                self.direction = VehicleDirection.FRONT
                self.y += self.speed
                
            # Update the current image based on direction
            self.current_image = self.images[self.direction]
            
            # Keep tank within map boundaries
            self.x = max(0, min(self.x, self.map_width - self.hitbox_width))
            self.y = max(0, min(self.y, self.map_height - self.hitbox_height))
            
            # If player is inside the tank, update player position to match tank
            if self.player_inside:
                self.player_inside.x = self.x
                self.player_inside.y = self.y
                
            # Check if the tank moved (for collision detection)
            return old_x != self.x or old_y != self.y
        
        return False

    def shoot(self):
        # Tank shooting logic (to be implemented)
        current_time = pygame.time.get_ticks()
        if current_time - self.last_shot_time > self.shoot_cooldown:
            self.last_shot_time = current_time
            # Tank shooting logic would go here
            return True
        return False 