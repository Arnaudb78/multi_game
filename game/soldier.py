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


class Bullet:
    def __init__(self, x, y, direction):
        self.x = x
        self.y = y
        self.direction = direction
        self.speed = 10
        self.images = []
        self.animation_frame = 0
        self.animation_timer = 0
        self.animation_delay = 50
        self.load_images()
        
    def load_images(self):
        # Get the absolute path of the current file
        current_file_path = os.path.abspath(__file__)
        # Go up two directories to reach the multiplayer directory
        multiplayer_dir = os.path.dirname(os.path.dirname(current_file_path))
        # Construct the path to the assets directory
        base_path = os.path.join(multiplayer_dir, 'assets', 'Objects', 'Bullet')
        
        # Verify the directory exists
        if not os.path.exists(base_path):
            print(f"Bullet assets directory not found: {base_path}")
            return
        
        prefix = "Horizontal" if self.direction in [SoldierDirection.LEFT, SoldierDirection.RIGHT] else "Vertical"
        for i in range(1, 11):
            try:
                image_path = os.path.join(base_path, f"{prefix} ({i}).png")
                image = pygame.image.load(image_path).convert_alpha()
                image.set_colorkey((0, 0, 0))
                # Scale up the image
                scale_factor = 0.3  # Increased from 0.1 to 0.3
                new_size = (
                    int(image.get_width() * scale_factor),
                    int(image.get_height() * scale_factor)
                )
                image = pygame.transform.scale(image, new_size)
                self.images.append(image)
            except Exception as e:
                print(f"Error loading bullet image {i}: {str(e)}")
                break

    def update(self):
        # Update position based on direction
        if self.direction == SoldierDirection.LEFT:
            self.x -= self.speed
        elif self.direction == SoldierDirection.RIGHT:
            self.x += self.speed
        elif self.direction == SoldierDirection.BACK:
            self.y -= self.speed
        elif self.direction == SoldierDirection.FRONT:
            self.y += self.speed

        # Update animation
        current_time = pygame.time.get_ticks()
        if current_time - self.animation_timer > self.animation_delay:
            self.animation_timer = current_time
            if self.images:
                self.animation_frame = (self.animation_frame + 1) % len(self.images)

    def draw(self, screen, camera_x, camera_y):
        if self.images and self.animation_frame < len(self.images):
            current_image = self.images[self.animation_frame]
            draw_x = self.x - camera_x - current_image.get_width() // 2
            draw_y = self.y - camera_y - current_image.get_height() // 2
            screen.blit(current_image, (draw_x, draw_y))


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
        self.bullets = []
        self.shoot_cooldown = 0
        self.shoot_delay = 500  # milliseconds between shots
        self.max_health = 100
        self.health = self.max_health
        self.is_dead = False
        self.load_animations()

    def load_animations(self):
        # Handle case sensitivity for soldier type
        soldier_folder = "rogue" if self.soldier_type.lower() == "rogue" else "falcon"
        
        # Get the absolute path of the current file
        current_file_path = os.path.abspath(__file__)
        
        # Go up two directories to reach the multiplayer directory
        multiplayer_dir = os.path.dirname(os.path.dirname(current_file_path))
        
        # Construct the path to the assets directory
        base_path = os.path.join(multiplayer_dir, 'assets', 'soldiers', soldier_folder)
        
        # Verify the directory exists
        if not os.path.exists(base_path):
            print(f"Soldier assets directory not found: {base_path}")
            return
        
        for direction in SoldierDirection:
            self.images[direction] = {}
            for state in SoldierState:
                self.images[direction][state] = []
                # Load all frames for this state and direction
                frame_count = 4 if state != SoldierState.DEAD else 5
                for i in range(1, frame_count + 1):
                    try:
                        image_path = os.path.join(
                            base_path, 
                            direction.value, 
                            f"{state.value} ({i}).png"
                        )
                        
                        # Load and convert image with alpha channel
                        image = pygame.image.load(image_path).convert_alpha()
                        # Remove black background
                        image.set_colorkey((0, 0, 0))
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
                    except Exception as e:
                        print(f"Error loading image for {state.value} {direction.value} frame {i}: {str(e)}")
                        continue

    def update(self, keys, other_soldiers=None):
        # Skip update if dead
        if self.health <= 0:
            self.state = SoldierState.DEAD
            self.is_dead = True
            return
        
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

        # Handle shooting
        if keys[pygame.K_SPACE] and self.shoot_cooldown <= 0:
            self.shoot()
            self.shoot_cooldown = self.shoot_delay

        # Update shoot cooldown
        if self.shoot_cooldown > 0:
            self.shoot_cooldown -= pygame.time.get_ticks() - self.animation_timer

        # Update bullets
        for bullet in self.bullets[:]:
            bullet.update()
            
            # Remove bullets that are off screen
            if (bullet.x < -100 or bullet.x > 2000 or 
                bullet.y < -100 or bullet.y > 2000):
                self.bullets.remove(bullet)

    def shoot(self):
        # Create a new bullet based on the soldier's direction
        bullet = Bullet(self.x, self.y, self.direction)
        self.bullets.append(bullet)
        
        # Only change to SHOOT state if we have animation frames for it
        if (self.direction in self.images and 
            SoldierState.SHOOT in self.images[self.direction] and 
            self.images[self.direction][SoldierState.SHOOT]):
            self.state = SoldierState.SHOOT

    def take_damage(self, amount):
        self.health = max(0, self.health - amount)
        if self.health <= 0:
            self.state = SoldierState.DEAD
            self.is_dead = True

    def draw_health_bar(self, screen, x, y):
        # Health bar dimensions
        bar_width = 50
        bar_height = 5
        outline_width = 2

        # Calculate health percentage
        health_percentage = self.health / self.max_health

        # Draw outline
        pygame.draw.rect(screen, (0, 0, 0), (x - outline_width, y - outline_width, 
                                            bar_width + outline_width * 2, 
                                            bar_height + outline_width * 2))

        # Draw background (red)
        pygame.draw.rect(screen, (255, 0, 0), (x, y, bar_width, bar_height))

        # Draw health (green)
        health_width = int(bar_width * health_percentage)
        pygame.draw.rect(screen, (0, 255, 0), (x, y, health_width, bar_height))

    def draw(self, screen, camera_x, camera_y):
        # Get current animation frame
        if (self.direction in self.images and 
            self.state in self.images[self.direction] and 
            self.images[self.direction][self.state]):
            frames = self.images[self.direction][self.state]
            if frames and self.animation_frame < len(frames):
                current_image = frames[self.animation_frame]
                
                # Calculate position to center the soldier
                draw_x = self.x - camera_x - current_image.get_width() // 2
                draw_y = self.y - camera_y - current_image.get_height() // 2
                
                # Draw the soldier
                screen.blit(current_image, (draw_x, draw_y))
                
                # Draw name above soldier (only if alive)
                if self.health > 0:
                    font = pygame.font.Font(None, 28)
                    label = font.render(self.name, True, (255, 255, 255))
                    label_x = draw_x + current_image.get_width() // 2 - label.get_width() // 2
                    label_y = draw_y - 20
                    screen.blit(label, (label_x, label_y))

                    # Draw health bar
                    health_bar_x = draw_x + current_image.get_width() // 2 - 25  # Center the health bar
                    health_bar_y = draw_y - 40  # Position above the name
                    self.draw_health_bar(screen, health_bar_x, health_bar_y)

        # Draw bullets
        for bullet in self.bullets:
            bullet.draw(screen, camera_x, camera_y) 