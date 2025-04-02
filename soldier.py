import pygame
import os
from enum import Enum


class SoldierState(Enum):
    IDLE = "Idle"
    IDLE_AIM = "Idle Aim"
    WALK = "Walk"
    WALK_AIM = "Walk Aim"
    SHOOT = "Shoot"
    THROW = "Throw"
    DEAD = "Dead"


class SoldierDirection(Enum):
    FRONT = "front"
    BACK = "back"
    LEFT = "left"
    RIGHT = "right"


class Soldier:
    def __init__(self, x, y, soldier_type, name):
        self.x = x
        self.y = y
        self.soldier_type = soldier_type
        self.name = name
        self.state = SoldierState.IDLE
        self.direction = SoldierDirection.FRONT
        self.animation_frame = 0
        self.animation_timer = 0
        self.animation_delay = 100  # milliseconds between frames
        self.images = {}
        self.scale_factor = 0.1  # Scale down to 40% of original size
        self.load_animations()

    def load_animations(self):
        # Handle case sensitivity for soldier type
        soldier_folder = "Rogue" if self.soldier_type == "Rogue" else "falcon"
        base_path = f"assets/soldiers/{soldier_folder}"
        
        for direction in SoldierDirection:
            self.images[direction] = {}
            for state in SoldierState:
                self.images[direction][state] = []
                # Load all frames for this state and direction
                for i in range(1, 5):  # Most animations have 4 frames
                    if state == SoldierState.DEAD and i > 5:  # Dead has 5 frames
                        break
                    try:
                        image_path = os.path.join(
                            base_path, 
                            direction.value, 
                            f"{state.value} ({i}).png"
                        )
                        # Load and convert image with alpha channel
                        image = pygame.image.load(image_path).convert_alpha()
                        # Scale down the image
                        new_size = (
                            int(image.get_width() * self.scale_factor),
                            int(image.get_height() * self.scale_factor)
                        )
                        image = pygame.transform.scale(image, new_size)
                        # Flip sprites to face the correct direction
                        if direction in [SoldierDirection.LEFT, SoldierDirection.RIGHT]:
                            image = pygame.transform.flip(image, True, False)
                        self.images[direction][state].append(image)
                    except FileNotFoundError:
                        # If we can't find the animation, try without the number
                        try:
                            image_path = os.path.join(
                                base_path, 
                                direction.value, 
                                f"{state.value}.png"
                            )
                            image = pygame.image.load(image_path).convert_alpha()
                            new_size = (
                                int(image.get_width() * self.scale_factor),
                                int(image.get_height() * self.scale_factor)
                            )
                            image = pygame.transform.scale(image, new_size)
                            # Flip sprites to face the correct direction
                            if direction in [SoldierDirection.LEFT, SoldierDirection.RIGHT]:
                                image = pygame.transform.flip(image, True, False)
                            self.images[direction][state].append(image)
                        except FileNotFoundError:
                            break

    def update(self, keys):
        # Update position based on keys
        if keys[pygame.K_LEFT]:
            self.x -= 5
            self.direction = SoldierDirection.LEFT
            self.state = SoldierState.WALK
        elif keys[pygame.K_RIGHT]:
            self.x += 5
            self.direction = SoldierDirection.RIGHT
            self.state = SoldierState.WALK
        elif keys[pygame.K_UP]:
            self.y -= 5
            self.direction = SoldierDirection.BACK
            self.state = SoldierState.WALK
        elif keys[pygame.K_DOWN]:
            self.y += 5
            self.direction = SoldierDirection.FRONT
            self.state = SoldierState.WALK
        else:
            self.state = SoldierState.IDLE

        # Update animation
        current_time = pygame.time.get_ticks()
        if current_time - self.animation_timer > self.animation_delay:
            self.animation_timer = current_time
            if (self.direction in self.images and 
                self.state in self.images[self.direction]):
                frames = self.images[self.direction][self.state]
                if frames:  # Only update if we have frames for this state
                    self.animation_frame = (self.animation_frame + 1) % len(frames)

    def draw(self, screen, camera_x, camera_y):
        # Get current animation frame
        if (self.direction in self.images and 
            self.state in self.images[self.direction] and 
            self.images[self.direction][self.state]):
            current_image = self.images[self.direction][self.state][self.animation_frame]
            
            # Calculate position to center the soldier
            draw_x = self.x - camera_x - current_image.get_width() // 2
            draw_y = self.y - camera_y - current_image.get_height() // 2
            
            # Draw the soldier
            screen.blit(current_image, (draw_x, draw_y))
            
            # Draw name above soldier
            font = pygame.font.Font(None, 28)
            label = font.render(self.name, True, (255, 255, 255))
            label_x = draw_x + current_image.get_width() // 2 - label.get_width() // 2
            label_y = draw_y - 20
            screen.blit(label, (label_x, label_y)) 