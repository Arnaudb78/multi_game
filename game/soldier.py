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
        
        # Handle direction as string or enum
        if isinstance(direction, str):
            for dir_enum in SoldierDirection:
                if dir_enum.value == direction:
                    self.direction = dir_enum
                    break
            else:
                # Default to FRONT if string direction not found
                self.direction = SoldierDirection.FRONT
        else:
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
        
        # Determine prefix based on direction
        if isinstance(self.direction, SoldierDirection):
            prefix = "Horizontal" if self.direction in [SoldierDirection.LEFT, SoldierDirection.RIGHT] else "Vertical"
        else:
            # Default to Horizontal if direction is unknown
            prefix = "Horizontal"
            
        for i in range(1, 11):
            try:
                image_path = os.path.join(base_path, f"{prefix} ({i}).png")
                if not os.path.exists(image_path):
                    continue
                    
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
                
        # Create placeholder image if no images were loaded
        if not self.images:
            placeholder = pygame.Surface((10, 5))
            placeholder.fill((255, 255, 0))  # Yellow bullet
            self.images.append(placeholder)

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
        else:
            # Default movement if direction is unknown
            self.x += self.speed

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
        self.damage_resistance = self._get_damage_resistance()
        self.last_damage_time = 0
        self.damage_effect_duration = 500  # milliseconds
        self.is_damaged = False
        self.load_animations()

    def _get_damage_resistance(self):
        # Différents types de soldats ont différentes résistances aux dégâts
        resistances = {
            "falcon": 0.8,  # 20% de réduction des dégâts
            "rogue": 0.6    # 40% de réduction des dégâts
        }
        return resistances.get(self.soldier_type.lower(), 1.0)

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
        
        # Set default death animation - will be used if specific death animations are missing
        default_dead_frames = []
        
        # First try to load at least one death animation to use as default
        for direction in SoldierDirection:
            dir_path = os.path.join(base_path, direction.value)
            if os.path.exists(dir_path):
                for i in range(1, 6):  # Dead animation has 5 frames
                    try:
                        image_path = os.path.join(dir_path, f"Dead ({i}).png")
                        if os.path.exists(image_path):
                            image = pygame.image.load(image_path).convert_alpha()
                            image.set_colorkey((0, 0, 0))
                            new_size = (
                                int(image.get_width() * self.scale_factor),
                                int(image.get_height() * self.scale_factor)
                            )
                            image = pygame.transform.scale(image, new_size)
                            if direction in [SoldierDirection.LEFT, SoldierDirection.RIGHT]:
                                image = pygame.transform.flip(image, True, False)
                            default_dead_frames.append(image)
                    except Exception:
                        pass
                if default_dead_frames:
                    break
        
        # If we couldn't find any death animation, create a simple red square
        if not default_dead_frames:
            for i in range(5):  # Create 5 frames
                surface = pygame.Surface((30, 30))
                surface.fill((255, 0, 0))
                default_dead_frames.append(surface)
        
        # Load all animations for each state and direction
        for direction in SoldierDirection:
            self.images[direction] = {}
            for state in SoldierState:
                self.images[direction][state] = []
                
                # Special handling for DEAD state
                if state == SoldierState.DEAD:
                    # Use default death animation
                    self.images[direction][state] = default_dead_frames.copy()
                    continue
                
                # For other states, load frames as normal
                frame_count = 4  # Most animations have 4 frames
                for i in range(1, frame_count + 1):
                    try:
                        image_path = os.path.join(
                            base_path, 
                            direction.value, 
                            f"{state.value} ({i}).png"
                        )
                        
                        if not os.path.exists(image_path):
                            continue
                            
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
                
                # If no frames were loaded for this state, add a placeholder
                if not self.images[direction][state] and state != SoldierState.DEAD:
                    placeholder = pygame.Surface((30, 30))
                    placeholder.fill((0, 255, 0) if state == SoldierState.IDLE else (0, 0, 255))
                    self.images[direction][state].append(placeholder)

    def update(self, keys, other_soldiers=None):
        # Mettre à jour l'effet visuel de dégâts
        current_time = pygame.time.get_ticks()
        if self.is_damaged and current_time - self.last_damage_time > self.damage_effect_duration:
            self.is_damaged = False
            
        # Handle death animation
        if self.health <= 0:
            self.state = SoldierState.DEAD
            self.is_dead = True
            
            # Ensure death animation plays through once
            current_time = pygame.time.get_ticks()
            if current_time - self.animation_timer > self.animation_delay:
                self.animation_timer = current_time
                frames = []
                if (self.direction in self.images and 
                    SoldierState.DEAD in self.images[self.direction]):
                    frames = self.images[self.direction][SoldierState.DEAD]
                
                if frames and self.animation_frame < len(frames) - 1:
                    # Only increment frame if not at the last frame of death animation
                    self.animation_frame = (self.animation_frame + 1)
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
        if self.health <= 0:
            return  # Already dead, don't take more damage
            
        # Appliquer la résistance aux dégâts
        actual_damage = amount * self.damage_resistance
        self.health = max(0, self.health - actual_damage)
        
        # Activer l'effet visuel de dégâts
        self.is_damaged = True
        self.last_damage_time = pygame.time.get_ticks()
        
        if self.health <= 0:
            self.state = SoldierState.DEAD
            self.is_dead = True
            self.animation_frame = 0  # Reset animation frame to start death animation from beginning

    def revive(self, x, y):
        """Revive the soldier at the specified position"""
        self.health = self.max_health
        self.is_dead = False
        self.state = SoldierState.IDLE
        self.x = x
        self.y = y
        self.animation_frame = 0
        self.bullets.clear()

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
                
                # Draw the soldier with damage effect if needed
                if self.is_damaged:
                    # Create a red-tinted version of the image
                    tinted_image = current_image.copy()
                    tinted_image.fill((255, 0, 0, 128), special_flags=pygame.BLEND_RGBA_MULT)
                    screen.blit(tinted_image, (draw_x, draw_y))
                else:
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

    def serialize_bullet(self):
        """Convert bullet objects to simple data for network transmission"""
        bullet_data = []
        for bullet in self.bullets:
            bullet_data.append((
                bullet.x, 
                bullet.y, 
                bullet.direction.value if hasattr(bullet.direction, 'value') else bullet.direction
            ))
        return bullet_data 