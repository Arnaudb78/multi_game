import pygame

# Initialize Pygame
pygame.init()

# Couleurs
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
GRAY = (128, 128, 128)
BLUE = (0, 0, 255)

# Police
font = pygame.font.Font(None, 74)
small_font = pygame.font.Font(None, 36)


class Menu:
    def __init__(self, screen, default_host='127.0.0.1', default_port='12345'):
        self.screen = screen
        self.host_input = default_host
        self.port_input = default_port
        self.active_input = None
        self.cursor_visible = True
        self.cursor_timer = 0
        self.host_rect = None
        self.port_rect = None

    def draw_text_input(self, text, x, y, width, height, active):
        # Draw input box
        color = BLUE if active else GRAY
        pygame.draw.rect(self.screen, color, (x, y, width, height), 2)
        
        # Draw text
        text_surface = small_font.render(text, True, WHITE)
        self.screen.blit(text_surface, (x + 5, y + 5))
        
        # Draw cursor if active
        if active and self.cursor_visible:
            cursor_x = x + 5 + text_surface.get_width()
            pygame.draw.line(
                self.screen, WHITE,
                (cursor_x, y + 5),
                (cursor_x, y + height - 5), 2
            )
        
        return pygame.Rect(x, y, width, height)

    def draw(self):
        self.screen.fill(BLACK)
        
        # Titre
        title = font.render(
            'Jeu Shooter Multijoueur', True, WHITE
        )
        title_rect = title.get_rect(
            center=(self.screen.get_width()/2,
                   self.screen.get_height()/4)
        )
        self.screen.blit(title, title_rect)
        
        # Input fields
        input_height = 40
        input_width = 200
        
        # Host input
        host_label = small_font.render('Host IP:', True, WHITE)
        host_label_rect = host_label.get_rect(
            center=(self.screen.get_width()/2 - input_width/2 - 50,
                   self.screen.get_height()/2 - 60)
        )
        self.screen.blit(host_label, host_label_rect)
        
        self.host_rect = self.draw_text_input(
            self.host_input,
            self.screen.get_width()/2 - input_width/2,
            self.screen.get_height()/2 - 60,
            input_width,
            input_height,
            self.active_input == 'host'
        )
        
        # Port input
        port_label = small_font.render('Port:', True, WHITE)
        port_label_rect = port_label.get_rect(
            center=(self.screen.get_width()/2 - input_width/2 - 50,
                   self.screen.get_height()/2)
        )
        self.screen.blit(port_label, port_label_rect)
        
        self.port_rect = self.draw_text_input(
            self.port_input,
            self.screen.get_width()/2 - input_width/2,
            self.screen.get_height()/2,
            input_width,
            input_height,
            self.active_input == 'port'
        )
        
        # Bouton Start
        start_button = font.render('Start Game', True, WHITE)
        start_rect = start_button.get_rect(
            center=(self.screen.get_width()/2,
                   self.screen.get_height()/2 + 80)
        )
        pygame.draw.rect(self.screen, GREEN, start_rect.inflate(20, 20))
        self.screen.blit(start_button, start_rect)
        
        # Bouton Quit
        quit_button = font.render('Quit', True, WHITE)
        quit_rect = quit_button.get_rect(
            center=(self.screen.get_width()/2,
                   self.screen.get_height()/2 + 160)
        )
        pygame.draw.rect(self.screen, RED, quit_rect.inflate(20, 20))
        self.screen.blit(quit_button, quit_rect)
        
        pygame.display.flip()
        return start_rect, quit_rect, self.host_rect, self.port_rect

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = event.pos
            if self.host_rect and self.host_rect.collidepoint(mouse_pos):
                self.active_input = 'host'
            elif self.port_rect and self.port_rect.collidepoint(mouse_pos):
                self.active_input = 'port'
            else:
                self.active_input = None
        elif event.type == pygame.KEYDOWN:
            if self.active_input == 'host':
                if event.key == pygame.K_BACKSPACE:
                    self.host_input = self.host_input[:-1]
                elif event.key == pygame.K_RETURN:
                    self.active_input = 'port'
                elif len(self.host_input) < 15:  # Limit IP length
                    if event.unicode.isprintable():
                        self.host_input += event.unicode
            elif self.active_input == 'port':
                if event.key == pygame.K_BACKSPACE:
                    self.port_input = self.port_input[:-1]
                elif event.key == pygame.K_RETURN:
                    self.active_input = None
                elif len(self.port_input) < 5 and event.unicode.isdigit():
                    self.port_input += event.unicode

    def update(self):
        current_time = pygame.time.get_ticks()
        if current_time - self.cursor_timer > 500:  # Toggle every 500ms
            self.cursor_visible = not self.cursor_visible
            self.cursor_timer = current_time

    def get_connection_info(self):
        return self.host_input, int(self.port_input) 